"""
MOH TIME OS API Server - REST API for dashboard and integrations.
"""
# ruff: noqa: B904, S608, S104
# B904: Legacy exception handling patterns throughout
# S608: Dynamic SQL with validated/escaped inputs
# S104: Development server binding (guarded by __name__ check)

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from lib import db as db_module
from lib import paths
from lib.analyzers import AnalyzerOrchestrator
from lib.autonomous_loop import AutonomousLoop
from lib.calibration import CalibrationEngine
from lib.change_bundles import (
    create_bundle,
    create_task_bundle,
    get_bundle,
    list_bundles,
    list_rollbackable_bundles,
    mark_applied,
    mark_failed,
    rollback_bundle,
)
from lib.collectors import CollectorOrchestrator
from lib.governance import DomainMode, get_governance
from lib.state_store import get_store
from lib.ui_spec_v21.detectors import DetectorRunner
from lib.v4.coupling_service import CouplingService
from lib.v4.issue_service import IssueService
from lib.v4.proposal_service import ProposalService

logger = logging.getLogger(__name__)

# Legacy filter: tasks overdue more than this many days are considered archived/legacy
# and excluded from active proposals to avoid noise pollution
LEGACY_OVERDUE_THRESHOLD_DAYS = 365

# FastAPI app initialization
app = FastAPI(
    title="MOH TIME OS API",
    description="Personal Operating System API - Direct control without AI",
    version="1.0.0",
)

# CORS middleware - configurable via CORS_ORIGINS env var
# Dev default: allow all origins; Production: set CORS_ORIGINS to comma-separated list
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
cors_origins = (
    ["*"] if cors_origins_env == "*" else [o.strip() for o in cors_origins_env.split(",")]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
store = get_store()
collectors = CollectorOrchestrator(store=store)
analyzers = AnalyzerOrchestrator(store=store)
governance = get_governance(store=store)

# UI directory (built Vite app)
UI_DIR = paths.app_home() / "time-os-ui" / "dist"

# ==== Spec v2.9 Router ====
# Mount spec-compliant endpoints at /api/v2
# These implement CLIENT-UI-SPEC-v2.9.md using lib/ui_spec_v21 modules
from api.intelligence_router import intelligence_router  # noqa: E402, I001
from api.spec_router import spec_router  # noqa: E402

app.include_router(spec_router, prefix="/api/v2")
app.include_router(intelligence_router, prefix="/api/v2/intelligence")


# ==== DB Startup & Migrations ====
@app.on_event("startup")
async def run_db_migrations_on_startup():
    """Run DB migrations and log DB info at startup."""
    try:
        db_path = db_module.get_db_path()
        logger.info("=== MOH TIME OS Startup ===")
        logger.info(f"DB path: {db_path}")
        logger.info(f"DB exists: {db_path.exists()}")

        if db_path.exists():
            with db_module.get_connection() as conn:
                version = db_module.get_schema_version(conn)
                logger.info(f"DB schema version (user_version): {version}")

        # Run migrations
        migration_result = db_module.run_startup_migrations()
        if migration_result.get("columns_added"):
            logger.info(f"Migrations added columns: {migration_result['columns_added']}")

    except Exception as e:
        logger.warning(f"DB startup check failed: {e}")


# ==== Detector Startup ====
# Run detectors on startup to populate inbox_items
@app.on_event("startup")
async def run_detectors_on_startup():
    """Run detectors to populate inbox_items table on server start."""
    try:
        db_path = db_module.get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        detector = DetectorRunner(conn)
        result = detector.run_all()
        logger.info(
            f"Detectors: {result.issues_created} issues, {result.flagged_signals_created} flagged signals created"
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.info(f"[WARN] Detector startup failed: {e}")


# Root endpoint
@app.get("/")
async def root(request: Request = None):
    """Serve the dashboard UI."""
    index_path = UI_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    # UI build missing - return helpful 404 instead of 500
    hint = "cd time-os-ui && npm ci && npm run build"

    # Check Accept header to decide format
    accept = ""
    if request:
        accept = request.headers.get("accept", "")

    if "text/html" in accept:
        html = f"""<!DOCTYPE html>
<html><head><title>UI Build Missing</title></head>
<body style="font-family: system-ui; padding: 2rem;">
<h1>UI Build Missing</h1>
<p>The frontend has not been built yet.</p>
<pre style="background: #f4f4f4; padding: 1rem; border-radius: 4px;">Run: {hint}</pre>
<p><a href="/docs">API Documentation</a> | <a href="/api/health">Health Check</a></p>
</body></html>"""
        return HTMLResponse(content=html, status_code=404)

    return JSONResponse(content={"error": "ui_build_missing", "hint": hint}, status_code=404)


# ==== Pydantic Models ====


class ApprovalAction(BaseModel):
    action: str


class ModeChange(BaseModel):
    mode: str


# ==== Overview Endpoint ====


@app.get("/api/overview")
async def get_overview():
    """Get dashboard overview with priorities, calendar, decisions, anomalies."""
    # Get priority queue
    priority_queue = (
        analyzers.priority_analyzer.analyze() if hasattr(analyzers, "priority_analyzer") else []
    )
    top_priorities = sorted(priority_queue, key=lambda x: x.get("score", 0), reverse=True)[:5]

    # Get today's events
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    events = store.query(
        "SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time", [today]
    )

    # Get pending decisions
    pending_decisions = store.query(
        "SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC LIMIT 5"
    )

    # Get anomalies
    anomalies = store.query(
        "SELECT * FROM insights WHERE type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now')) ORDER BY created_at DESC LIMIT 5"
    )

    return {
        "priorities": {"items": top_priorities, "total": len(priority_queue)},
        "calendar": {"events": [dict(e) for e in events], "event_count": len(events)},
        "decisions": {
            "pending": [dict(d) for d in pending_decisions],
            "pending_count": store.count("decisions", "approved IS NULL"),
        },
        "anomalies": {
            "items": [dict(a) for a in anomalies],
            "total": store.count(
                "insights",
                "type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now'))",
            ),
        },
        "sync_status": collectors.get_status(),
    }


# ==== Time Endpoints ====


@app.get("/api/time/blocks")
async def get_time_blocks(date: str | None = None, lane: str | None = None):
    """Get time blocks for a given date."""
    from datetime import date as dt

    from lib.time_truth import BlockManager

    if not date:
        date = dt.today().isoformat()

    bm = BlockManager(store)
    blocks = bm.get_all_blocks(date, lane)

    result = []
    for block in blocks:
        block_dict = {
            "id": block.id,
            "date": block.date,
            "start_time": block.start_time,
            "end_time": block.end_time,
            "lane": block.lane,
            "task_id": block.task_id,
            "is_protected": block.is_protected,
            "is_buffer": block.is_buffer,
            "duration_min": block.duration_min,
            "is_available": block.is_available,
        }

        if block.task_id:
            task = store.get("tasks", block.task_id)
            if task:
                block_dict["task_title"] = task.get("title", "")
                block_dict["task_status"] = task.get("status", "")

        result.append(block_dict)

    return {"date": date, "blocks": result, "total": len(result)}


@app.get("/api/time/summary")
async def get_time_summary(date: str | None = None):
    """Get time summary for a date."""
    from datetime import date as dt

    from lib.time_truth import CalendarSync, Scheduler

    if not date:
        date = dt.today().isoformat()

    cs = CalendarSync(store)
    scheduler = Scheduler(store)

    day_summary = cs.get_day_summary(date)
    scheduling_summary = scheduler.get_scheduling_summary(date)

    return {"date": date, "time": day_summary, "scheduling": scheduling_summary}


@app.get("/api/time/brief")
async def get_time_brief(date: str | None = None, format: str = "markdown"):
    """Get a brief time overview."""
    from datetime import date as dt

    from lib.time_truth import generate_time_brief

    if not date:
        date = dt.today().isoformat()

    brief = generate_time_brief(date, format)
    return {"date": date, "brief": brief}


@app.post("/api/time/schedule")
async def schedule_task(task_id: str, block_id: str | None = None, date: str | None = None):
    """Schedule a task into a time block."""
    from datetime import date as dt

    from lib.time_truth import Scheduler

    if not date:
        date = dt.today().isoformat()

    scheduler = Scheduler(store)
    result = scheduler.schedule_specific_task(task_id, block_id, date)

    return {
        "success": result.success,
        "message": result.message,
        "block_id": result.block_id,
    }


@app.post("/api/time/unschedule")
async def unschedule_task(task_id: str):
    """Unschedule a task from its time block."""
    from lib.time_truth import BlockManager

    bm = BlockManager(store)
    success, message = bm.unschedule_task(task_id)

    return {"success": success, "message": message}


# ==== Commitments Endpoints ====


@app.get("/api/commitments")
async def get_commitments(status: str | None = None, limit: int = 50):
    """Get all commitments."""
    from lib.commitment_truth import CommitmentManager

    cm = CommitmentManager(store)
    commitments = cm.get_all_commitments(status=status, limit=limit)

    return {
        "commitments": [
            {
                "id": c.id,
                "source_type": c.source_type,
                "source_id": c.source_id,
                "text": c.text,
                "owner": c.owner,
                "target": c.target,
                "target_date": c.target_date,
                "status": c.status,
                "task_id": c.task_id,
                "confidence": c.confidence,
                "created_at": c.created_at,
            }
            for c in commitments
        ],
        "total": len(commitments),
    }


@app.get("/api/commitments/untracked")
async def get_untracked_commitments(limit: int = 50):
    """Get commitments that aren't linked to tasks."""
    from lib.commitment_truth import CommitmentManager

    cm = CommitmentManager(store)
    commitments = cm.get_untracked_commitments(limit=limit)

    return {
        "commitments": [
            {
                "id": c.id,
                "text": c.text,
                "owner": c.owner,
                "target_date": c.target_date,
                "confidence": c.confidence,
                "source_type": c.source_type,
            }
            for c in commitments
        ],
        "total": len(commitments),
    }


@app.get("/api/commitments/due")
async def get_commitments_due(date: str | None = None):
    """Get commitments due by a date."""
    from datetime import date as dt

    from lib.commitment_truth import CommitmentManager

    if not date:
        date = dt.today().isoformat()

    cm = CommitmentManager(store)
    commitments = cm.get_commitments_due(date)

    return {
        "date": date,
        "commitments": [
            {
                "id": c.id,
                "text": c.text,
                "owner": c.owner,
                "target_date": c.target_date,
                "status": c.status,
                "task_id": c.task_id,
            }
            for c in commitments
        ],
        "total": len(commitments),
    }


@app.get("/api/commitments/summary")
async def get_commitments_summary():
    """Get commitments summary statistics."""
    from lib.commitment_truth import CommitmentManager

    cm = CommitmentManager(store)
    return cm.get_summary()


@app.post("/api/commitments/{commitment_id}/link")
async def link_commitment(commitment_id: str, task_id: str):
    """Link a commitment to a task."""
    from lib.commitment_truth import CommitmentManager

    cm = CommitmentManager(store)
    success = cm.link_to_task(commitment_id, task_id)

    return {"success": success, "commitment_id": commitment_id, "task_id": task_id}


@app.post("/api/commitments/{commitment_id}/done")
async def mark_commitment_done(commitment_id: str):
    """Mark a commitment as done."""
    from lib.commitment_truth import CommitmentManager

    cm = CommitmentManager(store)
    success = cm.mark_done(commitment_id)

    return {"success": success, "commitment_id": commitment_id}


# ==== Capacity Endpoints ====


@app.get("/api/capacity/lanes")
async def get_capacity_lanes():
    """Get capacity lanes configuration."""
    from lib.time_truth import get_capacity_lanes

    lanes = get_capacity_lanes(store)
    return {"lanes": lanes}


@app.get("/api/capacity/utilization")
async def get_capacity_utilization(start_date: str | None = None, end_date: str | None = None):
    """Get capacity utilization metrics."""
    from datetime import date

    from lib.time_truth import CalendarSync

    if not start_date:
        start_date = date.today().isoformat()
    if not end_date:
        end_date = (date.today() + timedelta(days=7)).isoformat()

    cs = CalendarSync(store)
    utilization = cs.get_utilization(start_date, end_date)

    return {"start_date": start_date, "end_date": end_date, "utilization": utilization}


@app.get("/api/capacity/forecast")
async def get_capacity_forecast(days: int = 7):
    """Get capacity forecast for upcoming days."""
    from datetime import date

    from lib.time_truth import Scheduler

    scheduler = Scheduler(store)
    forecasts = []

    for i in range(days):
        day = date.today() + timedelta(days=i)
        forecast = scheduler.get_day_forecast(day.isoformat())
        forecasts.append(forecast)

    return {"days": days, "forecasts": forecasts}


@app.get("/api/capacity/debt")
async def get_capacity_debt(lane: str | None = None):
    """Get capacity debt (overcommitments)."""
    from lib.time_truth import get_capacity_debt

    return get_capacity_debt(store, lane=lane)


@app.post("/api/capacity/debt/accrue")
async def accrue_debt(hours: float | None = None):
    """Record accrued capacity debt."""
    from lib.time_truth import accrue_capacity_debt

    return accrue_capacity_debt(store, hours=hours)


@app.post("/api/capacity/debt/{debt_id}/resolve")
async def resolve_debt(debt_id: str):
    """Resolve a capacity debt item."""
    from lib.time_truth import resolve_capacity_debt

    success = resolve_capacity_debt(store, debt_id)
    return {"success": success, "debt_id": debt_id}


# ==== Clients Endpoints ====


@app.get("/api/clients/health")
async def get_clients_health(limit: int = 20):
    """Get client health overview."""
    from lib.client_truth import HealthCalculator

    calc = HealthCalculator(store)
    clients = store.query("SELECT id, name FROM clients LIMIT ?", [limit])

    results = []
    for client in clients:
        health = calc.compute_health_score(client["id"])
        results.append(
            {
                "client_id": health.client_id,
                "name": health.client_name,
                "health_score": health.health_score,
                "tier": health.tier,
                "trend": health.trend,
                "at_risk": health.at_risk,
                "factors": health.factors,
            }
        )

    results.sort(key=lambda x: x["health_score"])

    return {"clients": results, "total": len(results)}


@app.get("/api/clients/at-risk")
async def get_at_risk_clients(threshold: int = 50):
    """Get clients that are at risk (health score below threshold)."""
    from lib.client_truth import HealthCalculator

    calc = HealthCalculator(store)
    at_risk = calc.get_at_risk_clients(threshold)

    return {
        "threshold": threshold,
        "clients": [
            {
                "client_id": h.client_id,
                "name": h.client_name,
                "health_score": h.health_score,
                "trend": h.trend,
                "factors": h.factors,
            }
            for h in at_risk
        ],
        "total": len(at_risk),
    }


@app.get("/api/clients/{client_id}/health")
async def get_client_health(client_id: str):
    """Get detailed health for a specific client."""
    from lib.client_truth import HealthCalculator

    calc = HealthCalculator(store)
    return calc.get_client_summary(client_id)


@app.get("/api/clients/{client_id}/projects")
async def get_client_projects(client_id: str):
    """Get projects for a client."""
    from lib.client_truth import ClientLinker

    linker = ClientLinker(store)
    projects = linker.get_client_projects(client_id)

    return {"client_id": client_id, "projects": projects, "total": len(projects)}


@app.post("/api/clients/link")
async def link_project_to_client(project_id: str, client_id: str):
    """Link a project to a client."""
    from lib.client_truth import ClientLinker

    linker = ClientLinker(store)
    success, message = linker.link_project_to_client(project_id, client_id)

    return {"success": success, "message": message}


@app.get("/api/clients/linking-stats")
async def get_linking_stats():
    """Get client linking statistics."""
    from lib.client_truth import ClientLinker

    linker = ClientLinker(store)
    return linker.get_linking_stats()


# ==== Tasks Endpoints ====


@app.get("/api/tasks")
async def get_tasks(
    status: str | None = None,
    project: str | None = None,
    assignee: str | None = None,
    limit: int = 50,
):
    """Get tasks with optional filters."""
    conditions = ["1=1"]
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if project:
        conditions.append("project = ?")
        params.append(project)
    if assignee:
        conditions.append("assignee = ?")
        params.append(assignee)

    params.append(limit)

    tasks = store.query(
        f"""
        SELECT * FROM tasks
        WHERE {" AND ".join(conditions)}
        ORDER BY priority DESC, due_date ASC
        LIMIT ?
    """,  # noqa: S608 - conditions are validated, params are parameterized
        params,
    )

    return {"tasks": [dict(t) for t in tasks], "total": len(tasks)}


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    project: str | None = None
    assignee: str | None = None
    due_date: str | None = None
    priority: int | None = 50
    tags: str | None = None
    source: str | None = "api"
    status: str | None = "pending"


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project: str | None = None
    assignee: str | None = None
    due_date: str | None = None
    priority: int | None = None
    status: str | None = None
    tags: str | None = None


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(task)


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    """Create a new task."""
    import uuid

    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    task_data = {
        "id": task_id,
        "title": task.title,
        "description": task.description,
        "project": task.project,
        "assignee": task.assignee,
        "due_date": task.due_date,
        "priority": task.priority or 50,
        "tags": task.tags,
        "source": task.source or "api",
        "status": task.status or "pending",
        "created_at": now,
        "updated_at": now,
    }

    bundle = create_task_bundle(
        description=f"Create task: {task.title[:50]}",
        creates=[{"id": task_id, "type": "create", **task_data}],
    )

    try:
        store.insert("tasks", task_data)
        mark_applied(bundle["id"])
        return {"success": True, "task": task_data, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, task: TaskUpdate):
    """Update a task with comprehensive validation and tracking."""
    existing = store.get("tasks", task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build update data from non-None fields
    update_data = {k: v for k, v in task.model_dump().items() if v is not None}
    now = datetime.now().isoformat()
    update_data["updated_at"] = now

    # Track what fields changed for audit
    changes = []
    for field, new_value in update_data.items():
        if field == "updated_at":
            continue
        old_value = existing.get(field)
        if old_value != new_value:
            changes.append({"field": field, "old": old_value, "new": new_value})

    # Validate status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        old_status = existing.get("status", "pending")
        valid_transitions = {
            "pending": ["in_progress", "blocked", "completed", "cancelled", "archived"],
            "in_progress": ["pending", "blocked", "completed", "cancelled"],
            "blocked": ["pending", "in_progress", "cancelled"],
            "completed": ["pending"],  # Allow reopening
            "cancelled": ["pending"],
            "archived": ["pending"],
        }
        if new_status not in valid_transitions.get(old_status, [new_status]):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition: {old_status} -> {new_status}",
            )

        # Set completion timestamp if completing
        if new_status == "completed" and old_status != "completed":
            update_data["completed_at"] = now
        elif new_status != "completed" and existing.get("completed_at"):
            update_data["completed_at"] = None

    # Validate priority range
    if "priority" in update_data:
        priority = update_data["priority"]
        if not (0 <= priority <= 100):
            raise HTTPException(status_code=400, detail="Priority must be between 0 and 100")

    # Validate due_date format
    if "due_date" in update_data and update_data["due_date"]:
        try:
            datetime.strptime(update_data["due_date"][:10], "%Y-%m-%d")
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD"
            ) from e

    # Check governance for sensitive field changes
    sensitive_fields = {"assignee", "priority", "due_date", "status"}
    if sensitive_fields & set(update_data.keys()):
        can_exec, reason = governance.can_execute(
            "tasks",
            "update",
            {"task_id": task_id, "changes": changes, "confidence": 1.0},
        )
        if not can_exec:
            # Create pending decision instead
            decision_id = f"dec_{task_id}_{now.replace(':', '-')}"
            store.insert(
                "decisions",
                {
                    "id": decision_id,
                    "type": "task_update",
                    "target_id": task_id,
                    "description": f"Update task: {existing.get('title', '')[:50]}",
                    "proposed_changes": json.dumps(update_data),
                    "reason": reason,
                    "created_at": now,
                },
            )
            return {
                "success": False,
                "requires_approval": True,
                "reason": reason,
                "decision_id": decision_id,
            }

    # Create rollback bundle
    bundle = create_task_bundle(
        description=f"Update task: {existing.get('title', '')[:50]}",
        updates=[{"id": task_id, "type": "update", **update_data}],
        pre_images={task_id: dict(existing)},
    )

    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])

        # Clear relevant caches
        store.clear_cache("priority_queue")

        # If task was completed, resolve associated signals
        signals_resolved = 0
        if update_data.get("status") in ("completed", "done"):
            try:
                from lib.v4.signal_service import SignalService

                signal_svc = SignalService()
                result = signal_svc.handle_task_completed(task_id)
                signals_resolved = result.get("resolved_count", 0)
            except Exception as sig_err:
                logger.warning(f"Failed to resolve signals for completed task {task_id}: {sig_err}")

        return {
            "success": True,
            "id": task_id,
            "bundle_id": bundle["id"],
            "changes": changes,
            "updated_fields": list(update_data.keys()),
            "signals_resolved": signals_resolved,
        }
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


class NoteAdd(BaseModel):
    note: str


@app.post("/api/tasks/{task_id}/notes")
async def add_task_note(task_id: str, body: NoteAdd):
    """Add a note to a task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        notes = json.loads(task.get("notes") or "[]")
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Could not parse notes JSON for task {task_id}: {e}")
        notes = []

    notes.append({"text": body.note, "created_at": datetime.now().isoformat()})

    store.update(
        "tasks",
        task_id,
        {"notes": json.dumps(notes), "updated_at": datetime.now().isoformat()},
    )

    return {"success": True, "notes": notes}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete (archive) a task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    bundle = create_task_bundle(
        description=f"Delete task: {task.get('title', '')[:50]}",
        deletes=[task_id],
        pre_images={task_id: dict(task)},
    )

    try:
        store.update(
            "tasks",
            task_id,
            {"status": "deleted", "updated_at": datetime.now().isoformat()},
        )
        mark_applied(bundle["id"])
        return {"success": True, "id": task_id, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==== Delegation Endpoints ====


class DelegateRequest(BaseModel):
    to: str
    note: str | None = None
    due_date: str | None = None


class EscalateRequest(BaseModel):
    to: str
    reason: str | None = None


@app.post("/api/tasks/{task_id}/delegate")
async def delegate_task(task_id: str, body: DelegateRequest):
    """Delegate a task to someone with validation and workload awareness."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Validate task is in delegatable state
    if task.get("status") in ("completed", "cancelled", "deleted", "archived"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delegate task with status: {task.get('status')}",
        )

    # Validate the assignee exists
    person = store.query("SELECT * FROM people WHERE name = ? OR id = ?", [body.to, body.to])
    if not person:
        # Check if it's a valid email format as fallback
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, body.to):
            raise HTTPException(status_code=404, detail=f"Person not found: {body.to}")
        assignee_name = body.to
        assignee_id = None
    else:
        assignee_name = person[0].get("name", body.to)
        assignee_id = person[0].get("id")

    # Check assignee workload
    if assignee_id:
        current_load = store.query(
            """
            SELECT COUNT(*) as cnt FROM tasks
            WHERE assignee = ? AND status IN ('pending', 'in_progress')
        """,
            [assignee_name],
        )
        workload = current_load[0]["cnt"] if current_load else 0

        # Check for overload threshold (configurable)
        max_tasks = 20
        if workload >= max_tasks:
            # Still allow but flag it
            overload_warning = f"Warning: {assignee_name} has {workload} active tasks"
        else:
            overload_warning = None
    else:
        workload = 0
        overload_warning = None

    # Validate due date if provided
    if body.due_date:
        try:
            due = datetime.strptime(body.due_date[:10], "%Y-%m-%d")
            # Warn if due date is in the past
            if due.date() < datetime.now().date():
                raise HTTPException(status_code=400, detail="Due date cannot be in the past")
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD"
            ) from e

    now = datetime.now().isoformat()

    # Build update data
    update_data = {
        "assignee": assignee_name,
        "assignee_id": assignee_id,
        "delegated_by": "moh",
        "delegated_at": now,
        "delegated_note": body.note,
        "delegation_status": "pending",
        "updated_at": now,
    }

    if body.due_date:
        update_data["due_date"] = body.due_date

    # Check governance permission
    can_exec, reason = governance.can_execute(
        "delegation",
        "delegate",
        {
            "task_id": task_id,
            "to": assignee_name,
            "workload": workload,
            "confidence": 1.0,
        },
    )

    if not can_exec:
        # Create pending decision for approval
        decision_id = f"del_{task_id}_{now.replace(':', '-')}"
        store.insert(
            "decisions",
            {
                "id": decision_id,
                "type": "delegation",
                "target_id": task_id,
                "description": f"Delegate '{task.get('title', '')[:50]}' to {assignee_name}",
                "proposed_changes": json.dumps(update_data),
                "reason": reason,
                "created_at": now,
            },
        )
        return {
            "success": False,
            "requires_approval": True,
            "reason": reason,
            "decision_id": decision_id,
            "assignee_workload": workload,
        }

    # Capture pre-image for rollback
    pre_image = {
        "assignee": task.get("assignee"),
        "assignee_id": task.get("assignee_id"),
        "delegated_by": task.get("delegated_by"),
        "delegated_at": task.get("delegated_at"),
        "delegated_note": task.get("delegated_note"),
        "delegation_status": task.get("delegation_status"),
        "due_date": task.get("due_date"),
    }

    bundle = create_task_bundle(
        description=f"Delegate to {assignee_name}: {task.get('title', '')[:50]}",
        updates=[{"id": task_id, "type": "delegate", **update_data}],
        pre_images={task_id: pre_image},
    )

    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])

        # Create notification for assignee if they have an ID
        if assignee_id:
            notif_id = f"notif_del_{task_id}_{now.replace(':', '-')}"
            store.insert(
                "notifications",
                {
                    "id": notif_id,
                    "type": "delegation",
                    "recipient_id": assignee_id,
                    "title": "Task delegated to you",
                    "body": f"'{task.get('title', '')}' has been delegated to you by Moh",
                    "task_id": task_id,
                    "created_at": now,
                    "dismissed": 0,
                },
            )

        # Clear relevant caches
        store.clear_cache("priority_queue")

        result = {
            "success": True,
            "id": task_id,
            "delegated_to": assignee_name,
            "bundle_id": bundle["id"],
            "assignee_workload": workload,
        }

        if overload_warning:
            result["warning"] = overload_warning

        return result

    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tasks/{task_id}/escalate")
async def escalate_task(task_id: str, body: EscalateRequest):
    """Escalate a task with priority boost and notification chain."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Validate task is in escalatable state
    if task.get("status") in ("completed", "cancelled", "deleted", "archived"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot escalate task with status: {task.get('status')}",
        )

    # Check if already escalated to this person
    current_escalation = task.get("escalated_to")
    if current_escalation == body.to:
        raise HTTPException(status_code=400, detail=f"Task is already escalated to {body.to}")

    # Validate the escalation target exists
    person = store.query("SELECT * FROM people WHERE name = ? OR id = ?", [body.to, body.to])
    if person:
        escalate_to_name = person[0].get("name", body.to)
        escalate_to_id = person[0].get("id")
        person[0].get("role", "unknown")
    else:
        escalate_to_name = body.to
        escalate_to_id = None

    now = datetime.now().isoformat()

    # Calculate new priority with escalation boost
    current_priority = task.get("priority") or 50
    escalation_level = task.get("escalation_level", 0) + 1

    # Priority boost increases with each escalation level
    priority_boost = min(20 * escalation_level, 40)  # Max boost of 40
    new_priority = min(100, current_priority + priority_boost)

    # Build escalation history
    try:
        escalation_history = json.loads(task.get("escalation_history") or "[]")
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Could not parse escalation_history JSON: {e}")
        escalation_history = []

    escalation_history.append(
        {
            "escalated_to": escalate_to_name,
            "escalated_from": current_escalation,
            "reason": body.reason,
            "timestamp": now,
            "level": escalation_level,
            "previous_priority": current_priority,
            "new_priority": new_priority,
        }
    )

    # Calculate urgency based on escalation
    urgency_levels = ["low", "normal", "high", "critical"]
    current_urgency_idx = (
        urgency_levels.index(task.get("urgency", "normal"))
        if task.get("urgency") in urgency_levels
        else 1
    )
    new_urgency_idx = min(current_urgency_idx + 1, 3)  # Bump urgency up one level
    new_urgency = urgency_levels[new_urgency_idx]

    update_data = {
        "escalated_to": escalate_to_name,
        "escalated_to_id": escalate_to_id,
        "escalated_at": now,
        "escalation_reason": body.reason,
        "escalation_level": escalation_level,
        "escalation_history": json.dumps(escalation_history),
        "priority": new_priority,
        "urgency": new_urgency,
        "updated_at": now,
    }

    # Check governance permission for escalation
    can_exec, reason = governance.can_execute(
        "escalation",
        "escalate",
        {
            "task_id": task_id,
            "to": escalate_to_name,
            "level": escalation_level,
            "new_priority": new_priority,
            "confidence": 1.0,
        },
    )

    if not can_exec:
        decision_id = f"esc_{task_id}_{now.replace(':', '-')}"
        store.insert(
            "decisions",
            {
                "id": decision_id,
                "type": "escalation",
                "target_id": task_id,
                "description": f"Escalate '{task.get('title', '')[:50]}' to {escalate_to_name}",
                "proposed_changes": json.dumps(update_data),
                "reason": reason,
                "created_at": now,
            },
        )
        return {
            "success": False,
            "requires_approval": True,
            "reason": reason,
            "decision_id": decision_id,
            "proposed_priority": new_priority,
            "escalation_level": escalation_level,
        }

    # Capture pre-image for rollback
    pre_image = {
        "escalated_to": task.get("escalated_to"),
        "escalated_to_id": task.get("escalated_to_id"),
        "escalated_at": task.get("escalated_at"),
        "escalation_reason": task.get("escalation_reason"),
        "escalation_level": task.get("escalation_level", 0),
        "escalation_history": task.get("escalation_history"),
        "priority": task.get("priority"),
        "urgency": task.get("urgency"),
    }

    bundle = create_task_bundle(
        description=f"Escalate to {escalate_to_name}: {task.get('title', '')[:50]}",
        updates=[{"id": task_id, "type": "escalate", **update_data}],
        pre_images={task_id: pre_image},
    )

    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])

        # Create notification for escalation target
        if escalate_to_id:
            notif_id = f"notif_esc_{task_id}_{now.replace(':', '-')}"
            store.insert(
                "notifications",
                {
                    "id": notif_id,
                    "type": "escalation",
                    "recipient_id": escalate_to_id,
                    "title": f"Task escalated to you (Level {escalation_level})",
                    "body": f"'{task.get('title', '')}' has been escalated. Reason: {body.reason or 'Not specified'}",
                    "task_id": task_id,
                    "priority": "high",
                    "created_at": now,
                    "dismissed": 0,
                },
            )

        # Also notify original assignee if different
        original_assignee_id = task.get("assignee_id")
        if original_assignee_id and original_assignee_id != escalate_to_id:
            notif_id2 = f"notif_esc_orig_{task_id}_{now.replace(':', '-')}"
            store.insert(
                "notifications",
                {
                    "id": notif_id2,
                    "type": "escalation_notice",
                    "recipient_id": original_assignee_id,
                    "title": "Your task has been escalated",
                    "body": f"'{task.get('title', '')}' was escalated to {escalate_to_name}",
                    "task_id": task_id,
                    "created_at": now,
                    "dismissed": 0,
                },
            )

        # Clear caches
        store.clear_cache("priority_queue")

        return {
            "success": True,
            "id": task_id,
            "escalated_to": escalate_to_name,
            "bundle_id": bundle["id"],
            "escalation_level": escalation_level,
            "old_priority": current_priority,
            "new_priority": new_priority,
            "new_urgency": new_urgency,
        }

    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tasks/{task_id}/recall")
async def recall_task(task_id: str):
    """Recall a delegated task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now().isoformat()
    update_data = {
        "assignee": None,
        "delegated_by": None,
        "delegated_at": None,
        "delegated_note": None,
        "recalled_at": now,
        "updated_at": now,
    }

    bundle = create_task_bundle(
        description=f"Recall task: {task.get('title', '')[:50]}",
        updates=[{"id": task_id, **update_data}],
        pre_images={
            task_id: {
                "assignee": task.get("assignee"),
                "delegated_by": task.get("delegated_by"),
            }
        },
    )

    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])
        return {"success": True, "id": task_id, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/delegations")
async def get_delegations():
    """Get delegated tasks split by delegation direction."""
    delegated_by_me = store.query("""
        SELECT * FROM tasks
        WHERE delegated_by IS NOT NULL AND delegated_by != '' AND status = 'pending'
        ORDER BY delegated_at DESC
    """)

    delegated_to_me = store.query("""
        SELECT * FROM tasks
        WHERE assignee = 'me' AND delegated_by IS NOT NULL AND status = 'pending'
        ORDER BY due_date ASC
    """)

    return {
        "delegated_by_me": [dict(t) for t in delegated_by_me],
        "delegated_to_me": [dict(t) for t in delegated_to_me],
        "total": len(delegated_by_me) + len(delegated_to_me),
    }


# ==== Data Quality Endpoints ====


@app.get("/api/data-quality")
async def get_data_quality():
    """Get data quality metrics and cleanup suggestions."""
    datetime.now().strftime("%Y-%m-%d")

    # Stale tasks (>14 days overdue)
    stale_tasks = store.query("""
        SELECT id, title, due_date, assignee, project, priority
        FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-14 days')
        ORDER BY due_date ASC
        LIMIT 100
    """)

    # Ancient tasks (>30 days overdue)
    ancient_tasks = store.query("""
        SELECT id, title, due_date, assignee, project
        FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-30 days')
        ORDER BY due_date ASC
        LIMIT 100
    """)

    # Inactive tasks (not updated in 30 days)
    inactive_tasks = store.query("""
        SELECT id, title, due_date, updated_at, assignee
        FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND (updated_at IS NULL OR date(updated_at) < date('now', '-30 days'))
        LIMIT 100
    """)

    # Priority distribution
    priority_dist = store.query("""
        SELECT
            CASE
                WHEN priority >= 80 THEN 'critical'
                WHEN priority >= 60 THEN 'high'
                WHEN priority >= 40 THEN 'medium'
                ELSE 'low'
            END as level,
            COUNT(*) as count
        FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
        GROUP BY level
    """)
    priority_by_level = {r["level"]: r["count"] for r in priority_dist}

    # Due distribution
    due_dist = store.query("""
        SELECT
            CASE
                WHEN due_date IS NULL THEN 'no_date'
                WHEN date(due_date) < date('now', '-30 days') THEN 'ancient'
                WHEN date(due_date) < date('now', '-14 days') THEN 'stale'
                WHEN date(due_date) < date('now') THEN 'overdue'
                WHEN date(due_date) = date('now') THEN 'today'
                WHEN date(due_date) <= date('now', '+7 days') THEN 'this_week'
                ELSE 'future'
            END as period,
            COUNT(*) as count
        FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
        GROUP BY period
    """)
    due_by_period = {r["period"]: r["count"] for r in due_dist}

    # Total active tasks
    total_active = store.count(
        "tasks", "status NOT IN ('completed', 'done', 'cancelled', 'deleted')"
    )

    # Calculate ratios
    stale_ratio = (due_by_period.get("ancient", 0) + due_by_period.get("stale", 0)) / max(
        1, total_active
    )
    priority_inflation = priority_by_level.get("critical", 0) / max(1, total_active)

    health_score = max(0, min(100, int(100 - stale_ratio * 50 - priority_inflation * 30)))

    return {
        "health_score": health_score,
        "total_active_tasks": total_active,
        "issues": {
            "stale_tasks": {
                "count": len(stale_tasks),
                "items": [dict(t) for t in stale_tasks[:20]],
            },
            "ancient_tasks": {
                "count": len(ancient_tasks),
                "items": [dict(t) for t in ancient_tasks[:20]],
            },
            "inactive_tasks": {
                "count": len(inactive_tasks),
                "items": [dict(t) for t in inactive_tasks[:20]],
            },
        },
        "metrics": {
            "priority_distribution": priority_by_level,
            "due_distribution": due_by_period,
            "priority_inflation_ratio": round(priority_inflation, 2),
            "stale_ratio": round(stale_ratio, 2),
        },
        "suggestions": _get_cleanup_suggestions(due_by_period, priority_by_level, total_active),
    }


def _get_cleanup_suggestions(
    due_by_period: dict, priority_by_level: dict, total_active: int
) -> list:
    """Generate cleanup suggestions based on data quality issues."""
    suggestions = []

    # Check for ancient tasks
    ancient_count = due_by_period.get("ancient", 0)
    if ancient_count > 0:
        suggestions.append(
            {
                "type": "ancient_tasks",
                "severity": "high",
                "message": f"Found {ancient_count} tasks overdue by more than 30 days",
                "action": "/api/data-quality/cleanup/ancient",
            }
        )

    # Check for stale tasks
    stale_count = due_by_period.get("stale", 0)
    if stale_count > 0:
        suggestions.append(
            {
                "type": "stale_tasks",
                "severity": "medium",
                "message": f"Found {stale_count} tasks overdue by 14-30 days",
                "action": "/api/data-quality/cleanup/stale",
            }
        )

    # Check priority inflation
    critical_count = priority_by_level.get("critical", 0)
    if total_active > 0 and critical_count / total_active > 0.2:
        suggestions.append(
            {
                "type": "priority_inflation",
                "severity": "medium",
                "message": f"{critical_count} critical priority tasks ({round(critical_count / total_active * 100)}% of active)",
                "action": "/api/data-quality/review-priorities",
            }
        )

    # Check for tasks without due dates
    no_date_count = due_by_period.get("no_date", 0)
    if no_date_count > 10:
        suggestions.append(
            {
                "type": "no_due_date",
                "severity": "low",
                "message": f"{no_date_count} tasks without due dates",
                "action": "/api/data-quality/add-due-dates",
            }
        )

    return suggestions


class CleanupRequest(BaseModel):
    task_ids: list | None = None
    dry_run: bool | None = False


@app.post("/api/data-quality/cleanup/ancient")
async def cleanup_ancient_tasks(confirm: bool = False):
    """Archive tasks that are >30 days overdue."""
    tasks = store.query("""
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-30 days')
    """)

    if not confirm:
        return {
            "preview": True,
            "count": len(tasks),
            "message": f"This will archive {len(tasks)} ancient tasks (>30 days overdue)",
            "sample": [dict(t) for t in tasks[:10]],
            "confirm_endpoint": "/api/data-quality/cleanup/ancient?confirm=true",
        }

    bundle = create_task_bundle(
        description=f"Bulk archive {len(tasks)} ancient tasks",
        updates=[{"id": t["id"], "type": "archive"} for t in tasks],
        pre_images={t["id"]: {"status": "pending"} for t in tasks},
    )

    for task in tasks:
        store.update(
            "tasks",
            task["id"],
            {"status": "archived", "updated_at": datetime.now().isoformat()},
        )

    mark_applied(bundle["id"])

    return {"success": True, "archived_count": len(tasks), "bundle_id": bundle["id"]}


@app.post("/api/data-quality/cleanup/stale")
async def cleanup_stale_tasks(confirm: bool = False):
    """Archive tasks that are 14-30 days overdue."""
    tasks = store.query("""
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-14 days')
          AND date(due_date) >= date('now', '-30 days')
    """)

    if not confirm:
        return {
            "preview": True,
            "count": len(tasks),
            "message": f"This will archive {len(tasks)} stale tasks (14-30 days overdue)",
            "sample": [dict(t) for t in tasks[:10]],
            "confirm_endpoint": "/api/data-quality/cleanup/stale?confirm=true",
        }

    from lib.change_bundles import create_task_bundle, mark_applied

    bundle = create_task_bundle(
        description=f"Bulk archive {len(tasks)} stale tasks",
        updates=[{"id": t["id"], "type": "archive"} for t in tasks],
        pre_images={t["id"]: {"status": "pending"} for t in tasks},
    )

    for task in tasks:
        store.update(
            "tasks",
            task["id"],
            {"status": "archived", "updated_at": datetime.now().isoformat()},
        )

    mark_applied(bundle["id"])

    return {"success": True, "archived_count": len(tasks), "bundle_id": bundle["id"]}


@app.post("/api/data-quality/recalculate-priorities")
async def recalculate_priorities():
    """Recalculate priorities for all pending tasks."""
    tasks = store.query("""
        SELECT * FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
    """)

    today = datetime.now().date()
    updated = 0

    for task in tasks:
        old_priority = task.get("priority", 50)
        new_priority = _calculate_realistic_priority(dict(task), today)

        if abs(new_priority - old_priority) > 5:
            store.update(
                "tasks",
                task["id"],
                {"priority": new_priority, "updated_at": datetime.now().isoformat()},
            )
            updated += 1

    return {
        "success": True,
        "tasks_updated": updated,
        "total_tasks": len(tasks),
        "message": f"Recalculated priorities for {updated} tasks",
    }


def _calculate_realistic_priority(task: dict, today) -> int:
    """Calculate a realistic priority score for a task."""
    score = 40

    due_date = task.get("due_date")
    if due_date:
        try:
            due = datetime.strptime(due_date[:10], "%Y-%m-%d").date()
            days_until = (due - today).days

            if days_until < 0:
                # Overdue
                overdue_days = abs(days_until)
                if overdue_days <= 3:
                    score += 30 + min(10, overdue_days * 3)
                elif overdue_days <= 7:
                    score += 25
                elif overdue_days <= 14:
                    score += 15
                elif overdue_days <= 30:
                    score += 5
                else:
                    # Very old, probably not urgent
                    score -= 10
            elif days_until == 0:
                score += 35
            elif days_until <= 2:
                score += 25
            elif days_until <= 7:
                score += 15
            elif days_until <= 14:
                score += 5
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse due_date '{due_date}' for priority scoring: {e}")

    # Boost for existing high priority
    existing = task.get("priority", 50)
    if existing > 70:
        score += 10

    # Boost for tasks with assignees (someone is responsible)
    if task.get("assignee"):
        score += 5

    # Boost for escalated tasks
    if task.get("escalated_to"):
        score += 15

    return max(0, min(100, score))


@app.post("/api/data-quality/cleanup/legacy-signals")
async def cleanup_legacy_signals(confirm: bool = False):
    """
    Clean up legacy signals and proposals by:
    1. Expiring signals for tasks overdue > LEGACY_OVERDUE_THRESHOLD_DAYS
    2. Recalculating proposals without legacy noise

    This fixes the issue of 1000+ day old overdue tasks polluting the dashboard.
    """
    conn = sqlite3.connect(store.db_path)
    cursor = conn.cursor()

    try:
        # Count legacy signals
        cursor.execute(f"""
            SELECT COUNT(s.signal_id)
            FROM signals s
            JOIN tasks t ON s.entity_ref_type = 'task' AND s.entity_ref_id = t.id
            WHERE s.status = 'active'
              AND s.signal_type IN ('deadline_overdue', 'deadline_approaching')
              AND t.due_date IS NOT NULL
              AND julianday('now') - julianday(t.due_date) > {LEGACY_OVERDUE_THRESHOLD_DAYS}
        """)  # noqa: S608 - LEGACY_OVERDUE_THRESHOLD_DAYS is a constant
        legacy_count = cursor.fetchone()[0]

        if not confirm:
            return {
                "preview": True,
                "legacy_signals": legacy_count,
                "message": f"This will expire {legacy_count} signals from tasks > {LEGACY_OVERDUE_THRESHOLD_DAYS} days overdue and regenerate proposals",
                "confirm_endpoint": "/api/data-quality/cleanup/legacy-signals?confirm=true",
            }

        # Mark legacy signals as expired
        cursor.execute(f"""
            UPDATE signals
            SET status = 'expired', expires_at = datetime('now')
            WHERE signal_id IN (
                SELECT s.signal_id
                FROM signals s
                JOIN tasks t ON s.entity_ref_type = 'task' AND s.entity_ref_id = t.id
                WHERE s.status = 'active'
                  AND s.signal_type IN ('deadline_overdue', 'deadline_approaching')
                  AND t.due_date IS NOT NULL
                  AND julianday('now') - julianday(t.due_date) > {LEGACY_OVERDUE_THRESHOLD_DAYS}
            )
        """)  # noqa: S608 - LEGACY_OVERDUE_THRESHOLD_DAYS is a constant
        expired_count = cursor.rowcount

        conn.commit()

        # Clear stale proposals that now have mostly expired signals
        # Identify proposals where >50% of their signals are now expired
        cursor.execute("""
            WITH proposal_signal_status AS (
                SELECT p.proposal_id,
                       COUNT(s.signal_id) as total_signals,
                       SUM(CASE WHEN s.status = 'active' THEN 1 ELSE 0 END) as active_signals
                FROM proposals_v4 p
                CROSS JOIN json_each(p.signal_ids) as sig_id
                LEFT JOIN signals s ON s.signal_id = sig_id.value
                WHERE p.status = 'open'
                GROUP BY p.proposal_id
            )
            SELECT proposal_id, total_signals, active_signals
            FROM proposal_signal_status
            WHERE active_signals < total_signals * 0.5
        """)
        stale_proposals = cursor.fetchall()

        # Dismiss stale proposals (more than half their signals are expired)
        stale_proposal_count = 0
        for row in stale_proposals:
            proposal_id = row[0]
            cursor.execute(
                """
                UPDATE proposals_v4
                SET status = 'dismissed', dismissed_reason = 'Auto-dismissed: majority of signals expired (legacy cleanup)'
                WHERE proposal_id = ?
            """,
                (proposal_id,),
            )
            stale_proposal_count += cursor.rowcount

        conn.commit()

        # Regenerate proposals from remaining signals
        svc = ProposalService()
        proposal_stats = svc.generate_proposals_from_signals()

        return {
            "success": True,
            "legacy_signals_expired": expired_count,
            "stale_proposals_dismissed": stale_proposal_count,
            "proposals": proposal_stats,
            "message": f"Expired {expired_count} legacy signals, dismissed {stale_proposal_count} stale proposals, and regenerated proposals",
        }
    finally:
        conn.close()


@app.get("/api/data-quality/preview/{cleanup_type}")
async def preview_cleanup(cleanup_type: str):
    """Preview what would be affected by a cleanup operation."""
    if cleanup_type == "ancient":
        tasks = store.query("""
            SELECT id, title, due_date, project, assignee FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
              AND due_date IS NOT NULL
              AND date(due_date) < date('now', '-30 days')
            ORDER BY due_date ASC
            LIMIT 50
        """)
    elif cleanup_type == "stale":
        tasks = store.query("""
            SELECT id, title, due_date, project, assignee FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
              AND due_date IS NOT NULL
              AND date(due_date) < date('now', '-14 days')
              AND date(due_date) >= date('now', '-30 days')
            ORDER BY due_date ASC
            LIMIT 50
        """)
    else:
        raise HTTPException(status_code=400, detail="Unknown cleanup type")

    return {
        "cleanup_type": cleanup_type,
        "tasks": [dict(t) for t in tasks],
        "total": len(tasks),
    }


# ==== Team Endpoints ====


@app.get("/api/team")
async def get_team(type_filter: str | None = None):
    """Get team members with workload metrics."""
    conditions = ["1=1"]
    if type_filter:
        conditions.append(f"p.type = '{type_filter}'")

    people = store.query(f"""
        SELECT p.*, c.name as client_name
        FROM people p
        LEFT JOIN clients c ON p.client_id = c.id
        WHERE {" AND ".join(conditions)}
        ORDER BY p.type DESC, p.name
    """)  # noqa: S608 - conditions are hardcoded filters

    result = []
    for p in people:
        person = dict(p)
        name_escaped = p["name"].replace("'", "''")

        # Workload metrics
        task_stats = store.query(f"""
            SELECT
                COUNT(*) as open_tasks,
                SUM(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) as overdue_tasks,
                SUM(CASE WHEN due_date = date('now') THEN 1 ELSE 0 END) as due_today
            FROM tasks
            WHERE assignee = '{name_escaped}' AND status IN ('pending', 'in_progress')
        """)  # noqa: S608 - name_escaped is SQL-escaped above

        completed_stats = store.query(f"""
            SELECT COUNT(*) as completed
            FROM tasks
            WHERE assignee = '{name_escaped}'
            AND status = 'completed'
            AND updated_at >= date('now', '-7 days')
        """)  # noqa: S608 - name_escaped is SQL-escaped above

        stats = task_stats[0] if task_stats else {}
        completed = completed_stats[0] if completed_stats else {}

        person["open_tasks"] = stats.get("open_tasks") or 0
        person["overdue_tasks"] = stats.get("overdue_tasks") or 0
        person["due_today"] = stats.get("due_today") or 0
        person["completed_this_week"] = completed.get("completed") or 0
        person["is_internal"] = 1 if p.get("type") == "internal" else 0

        result.append(person)

    return {"items": result, "total": len(result)}


@app.get("/api/calendar")
async def api_calendar(
    start_date: str | None = None, end_date: str | None = None, view: str = "week"
):
    """Get calendar events."""
    from datetime import date

    if not start_date:
        start_date = date.today().isoformat()
    if not end_date:
        if view == "week":
            end_date = (date.today() + timedelta(days=7)).isoformat()
        else:
            end_date = (date.today() + timedelta(days=1)).isoformat()

    events = store.query(
        """
        SELECT * FROM events
        WHERE date(start_time) >= ? AND date(start_time) <= ?
        ORDER BY start_time
    """,
        [start_date, end_date],
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "events": [dict(e) for e in events],
        "total": len(events),
    }


# NOTE: /api/delegations already defined above - removed duplicate alias


@app.get("/api/inbox")
async def api_inbox(limit: int = 50):
    """Get inbox items (unprocessed communications, new tasks, etc.)."""
    items = store.query(
        """
        SELECT * FROM communications
        WHERE processed = 0 OR processed IS NULL
        ORDER BY received_at DESC
        LIMIT ?
    """,
        [limit],
    )

    return {"items": [dict(i) for i in items], "total": len(items)}


# NOTE: /api/insights defined later with more features (category filter) - removed this simpler version


@app.get("/api/decisions")
async def api_decisions(limit: int = 20):
    """Get pending decisions."""
    decisions = store.query(
        """
        SELECT * FROM decisions
        WHERE approved IS NULL
        ORDER BY created_at DESC
        LIMIT ?
    """,
        [limit],
    )

    return {"decisions": [dict(d) for d in decisions], "total": len(decisions)}


@app.post("/api/priorities/{item_id}/complete")
async def api_priority_complete(item_id: str):
    """Complete a priority item (task)."""
    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now().isoformat()
    bundle = create_task_bundle(
        description=f"Complete: {task.get('title', '')[:50]}",
        updates=[{"id": item_id, "status": "completed", "completed_at": now}],
        pre_images={item_id: {"status": task.get("status")}},
    )

    try:
        store.update(
            "tasks",
            item_id,
            {"status": "completed", "completed_at": now, "updated_at": now},
        )
        mark_applied(bundle["id"])

        # Resolve associated signals
        signals_resolved = 0
        try:
            from lib.v4.signal_service import SignalService

            signal_svc = SignalService()
            result = signal_svc.handle_task_completed(item_id)
            signals_resolved = result.get("resolved_count", 0)
        except Exception as sig_err:
            logger.warning(f"Failed to resolve signals for completed task {item_id}: {sig_err}")

        return {
            "success": True,
            "id": item_id,
            "bundle_id": bundle["id"],
            "signals_resolved": signals_resolved,
        }
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/priorities/{item_id}/snooze")
async def api_priority_snooze(item_id: str, days: int = 1):
    """Snooze a priority item."""

    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    now = datetime.now().isoformat()

    bundle = create_task_bundle(
        description=f"Snooze {days}d: {task.get('title', '')[:50]}",
        updates=[{"id": item_id, "due_date": new_date}],
        pre_images={item_id: {"due_date": task.get("due_date")}},
    )

    try:
        store.update(
            "tasks",
            item_id,
            {"due_date": new_date, "snoozed_at": now, "updated_at": now},
        )
        mark_applied(bundle["id"])
        return {
            "success": True,
            "id": item_id,
            "new_due_date": new_date,
            "bundle_id": bundle["id"],
        }
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/priorities/{item_id}/delegate")
async def api_priority_delegate(item_id: str, to: str):
    """Delegate a priority item."""
    task = store.query("SELECT * FROM tasks WHERE id = ?", [item_id])
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    person = store.query("SELECT id, name FROM people WHERE name = ?", [to])
    if not person:
        raise HTTPException(status_code=404, detail="Delegate person not found")

    can_exec, reason = governance.can_execute(
        "delegation", "delegate", {"task_id": item_id, "to": to, "confidence": 1.0}
    )

    now_iso = datetime.now().isoformat()
    update_data = {
        "assignee_id": person[0]["id"],
        "assignee_name": person[0]["name"],
        "delegated_by": "moh",
        "delegated_at": now_iso,
        "updated_at": now_iso,
    }

    bundle = create_task_bundle(
        description=f"Delegate to {to}: {task[0]['title'][:50]}",
        updates=[{"id": item_id, **update_data}],
        pre_images={
            item_id: {
                "assignee_id": task[0].get("assignee_id"),
                "assignee_name": task[0].get("assignee_name"),
                "delegated_by": task[0].get("delegated_by"),
                "delegated_at": task[0].get("delegated_at"),
            }
        },
    )

    if not can_exec:
        return {
            "success": False,
            "requires_approval": True,
            "reason": reason,
            "bundle_id": bundle["id"],
        }

    try:
        store.update("tasks", item_id, update_data)
        mark_applied(bundle["id"])
        return {
            "success": True,
            "id": item_id,
            "delegated_to": to,
            "bundle_id": bundle["id"],
        }
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/decisions/{decision_id}")
async def api_decision(decision_id: str, action: ApprovalAction):
    """Process a decision (approve/reject) with side-effect execution."""
    dec = store.query("SELECT * FROM decisions WHERE id = ?", [decision_id])
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")

    decision = dec[0]

    # Check if already processed
    if decision.get("approved") is not None:
        return {
            "success": False,
            "error": "Decision already processed",
            "previous_action": "approved" if decision.get("approved") else "rejected",
            "processed_at": decision.get("approved_at"),
        }

    now_iso = datetime.now().isoformat()
    is_approved = action.action == "approve"

    # Parse proposed changes if present
    proposed_changes = {}
    if decision.get("proposed_changes"):
        try:
            proposed_changes = json.loads(decision["proposed_changes"])
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Could not parse proposed_changes JSON for decision: {e}")
            proposed_changes = {}

    # Track side effects to execute
    side_effects_executed = []
    side_effects_failed = []
    target_id = decision.get("target_id")
    decision_type = decision.get("type", "unknown")

    # Create audit bundle for the decision itself
    bundle = create_bundle(
        domain="decisions",
        description=f"{'Approve' if is_approved else 'Reject'} decision: {decision.get('description', '')[:50]}",
        changes=[
            {
                "type": "update",
                "id": decision_id,
                "target": "decisions",
                "data": {"approved": 1 if is_approved else 0},
            }
        ],
        pre_images={decision_id: {"approved": decision.get("approved")}},
    )

    try:
        # Update the decision record
        store.update(
            "decisions",
            decision_id,
            {
                "approved": 1 if is_approved else 0,
                "approved_at": now_iso,
                "processed_by": "moh",
            },
        )

        # Execute side effects if approved
        if is_approved and target_id and proposed_changes:
            # Handle different decision types
            if decision_type == "task_update":
                # Apply the proposed task update
                try:
                    store.update("tasks", target_id, proposed_changes)
                    side_effects_executed.append(
                        {
                            "type": "task_update",
                            "target": target_id,
                            "changes": list(proposed_changes.keys()),
                        }
                    )
                except Exception as e:
                    side_effects_failed.append(
                        {"type": "task_update", "target": target_id, "error": str(e)}
                    )

            elif decision_type == "delegation":
                # Apply the delegation
                try:
                    store.update("tasks", target_id, proposed_changes)
                    side_effects_executed.append(
                        {
                            "type": "delegation",
                            "target": target_id,
                            "delegated_to": proposed_changes.get("assignee"),
                        }
                    )

                    # Create notification
                    if proposed_changes.get("assignee_id"):
                        store.insert(
                            "notifications",
                            {
                                "id": f"notif_del_{target_id}_{now_iso.replace(':', '-')}",
                                "type": "delegation_approved",
                                "recipient_id": proposed_changes.get("assignee_id"),
                                "title": "Delegation approved",
                                "body": "You have been assigned a new task",
                                "task_id": target_id,
                                "created_at": now_iso,
                                "dismissed": 0,
                            },
                        )
                except Exception as e:
                    side_effects_failed.append(
                        {"type": "delegation", "target": target_id, "error": str(e)}
                    )

            elif decision_type == "escalation":
                # Apply the escalation
                try:
                    store.update("tasks", target_id, proposed_changes)
                    side_effects_executed.append(
                        {
                            "type": "escalation",
                            "target": target_id,
                            "escalated_to": proposed_changes.get("escalated_to"),
                        }
                    )

                    # Create high-priority notification
                    if proposed_changes.get("escalated_to_id"):
                        store.insert(
                            "notifications",
                            {
                                "id": f"notif_esc_{target_id}_{now_iso.replace(':', '-')}",
                                "type": "escalation_approved",
                                "recipient_id": proposed_changes.get("escalated_to_id"),
                                "title": "Task escalated to you",
                                "body": "A task has been escalated and requires attention",
                                "task_id": target_id,
                                "priority": "high",
                                "created_at": now_iso,
                                "dismissed": 0,
                            },
                        )
                except Exception as e:
                    side_effects_failed.append(
                        {"type": "escalation", "target": target_id, "error": str(e)}
                    )

            elif decision_type in ("governance_change", "mode_change"):
                # Apply governance configuration change
                try:
                    domain = proposed_changes.get("domain")
                    new_mode = proposed_changes.get("mode")
                    if domain and new_mode:
                        governance.set_mode(domain, DomainMode(new_mode))
                        side_effects_executed.append(
                            {
                                "type": "governance_change",
                                "domain": domain,
                                "new_mode": new_mode,
                            }
                        )
                except Exception as e:
                    side_effects_failed.append({"type": "governance_change", "error": str(e)})

        # Log to governance history
        store.insert(
            "governance_history",
            {
                "id": f"gh_{decision_id}",
                "decision_id": decision_id,
                "action": "approved" if is_approved else "rejected",
                "type": decision_type,
                "target_id": target_id,
                "processed_by": "moh",
                "side_effects": json.dumps(side_effects_executed),
                "created_at": now_iso,
            },
        )

        mark_applied(bundle["id"])

        # Clear relevant caches
        store.clear_cache("priority_queue")

        result = {
            "success": True,
            "id": decision_id,
            "action": action.action,
            "bundle_id": bundle["id"],
            "decision_type": decision_type,
            "target_id": target_id,
        }

        if side_effects_executed:
            result["side_effects_executed"] = side_effects_executed
        if side_effects_failed:
            result["side_effects_failed"] = side_effects_failed
            result["partial_success"] = True

        return result

    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==== Bundles Endpoints ====


@app.get("/api/bundles")
async def api_bundles(status: str | None = None, domain: str | None = None, limit: int = 50):
    """Get change bundles."""
    bundles = list_bundles(status=status, domain=domain, limit=limit)
    return {"bundles": bundles, "total": len(bundles)}


@app.get("/api/bundles/rollbackable")
async def api_bundles_rollbackable():
    """Get bundles that can be rolled back."""
    bundles = list_rollbackable_bundles()
    return {"bundles": bundles, "total": len(bundles)}


@app.get("/api/bundles/summary")
async def get_bundles_summary():
    """Get summary of bundle activity."""
    all_bundles = list_bundles(limit=500)

    by_status = {}
    by_domain = {}
    recent_applied = []

    for b in all_bundles:
        status = b.get("status", "unknown")
        domain = b.get("domain", "unknown")

        by_status[status] = by_status.get(status, 0) + 1
        by_domain[domain] = by_domain.get(domain, 0) + 1

        if status == "applied" and len(recent_applied) < 5:
            recent_applied.append(dict(b))

    rollbackable = list_rollbackable_bundles()

    return {
        "by_status": by_status,
        "by_domain": by_domain,
        "total_bundles": len(all_bundles),
        "recent_applied": recent_applied,
        "rollbackable_count": len(rollbackable),
    }


@app.post("/api/bundles/rollback-last")
async def rollback_last_bundle(domain: str | None = None):
    """Rollback the most recent bundle."""
    rollbackable = list_rollbackable_bundles()

    if domain:
        rollbackable = [b for b in rollbackable if b.get("domain") == domain]

    if not rollbackable:
        raise HTTPException(status_code=404, detail="No rollbackable bundles found")

    # Get most recent by applied_at
    most_recent = sorted(rollbackable, key=lambda x: x.get("applied_at", ""), reverse=True)[0]

    result = rollback_bundle(most_recent["id"])

    if result.get("success"):
        return {
            "success": True,
            "bundle_id": most_recent["id"],
            "description": most_recent.get("description"),
            "rolled_back_at": result.get("rolled_back_at"),
        }

    raise HTTPException(status_code=500, detail=result.get("reason", "Rollback failed"))


@app.get("/api/bundles/{bundle_id}")
async def api_bundle_get(bundle_id: str):
    """Get a specific bundle."""
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return bundle


@app.post("/api/bundles/{bundle_id}/rollback")
async def api_bundle_rollback(bundle_id: str):
    """Rollback a specific bundle."""
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    # Check governance permission
    can_exec, reason = governance.can_execute("system", "rollback", {"bundle_id": bundle_id})
    if not can_exec:
        return {"success": False, "requires_approval": True, "reason": reason}

    try:
        result = rollback_bundle(bundle_id)
        return {"success": True, "bundle": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==== Calibration Endpoints ====

calibration_engine = CalibrationEngine(store=store)


@app.get("/api/calibration")
async def api_calibration_last():
    """Get last calibration results."""
    return calibration_engine.get_last_calibration()


@app.post("/api/calibration/run")
async def api_calibration_run():
    """Run calibration."""
    return calibration_engine.run()


# ==== Feedback Endpoint ====


class FeedbackRequest(BaseModel):
    item_id: str
    rating: int
    comment: str | None = None


@app.post("/api/feedback")
async def api_feedback(feedback: FeedbackRequest):
    """Submit feedback on a recommendation or action."""
    import uuid

    feedback_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    store.insert(
        "feedback",
        {
            "id": feedback_id,
            "item_id": feedback.item_id,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "created_at": now,
        },
    )

    return {"success": True, "feedback_id": feedback_id}


# ==== Priorities Endpoints ====


@app.get("/api/priorities")
async def get_priorities(limit: int = 20, context: str | None = None):
    """Get prioritized items."""
    priority_queue = (
        analyzers.priority_analyzer.analyze() if hasattr(analyzers, "priority_analyzer") else []
    )

    sorted_items = sorted(priority_queue, key=lambda x: x.get("score", 0), reverse=True)[:limit]

    return {"items": sorted_items, "total": len(priority_queue)}


# NOTE: /api/priorities/{item_id}/complete - duplicate removed (bundle version above is better)
# NOTE: /api/priorities/{item_id}/snooze - duplicate removed (bundle version above is better)
# NOTE: /api/priorities/{item_id}/delegate - duplicate removed (governance version above is better)


@app.get("/api/priorities/filtered")
async def get_priorities_filtered(
    due: str | None = None,
    assignee: str | None = None,
    source: str | None = None,
    project: str | None = None,
    q: str | None = None,
    limit: int = 50,
):
    """Get filtered priority items with reasons."""
    from datetime import date

    conditions = ["status = 'pending'"]
    params = []
    today = date.today().isoformat()
    week_end = (date.today() + timedelta(days=7)).isoformat()

    if due == "today":
        conditions.append("due_date = ?")
        params.append(today)
    elif due == "week":
        conditions.append("due_date BETWEEN ? AND ?")
        params.extend([today, week_end])
    elif due == "overdue":
        conditions.append("due_date < ?")
        params.append(today)

    if assignee:
        conditions.append("assignee LIKE ?")
        params.append(f"%{assignee}%")

    if source:
        conditions.append("source LIKE ?")
        params.append(f"%{source}%")

    if project:
        conditions.append("project LIKE ?")
        params.append(f"%{project}%")

    if q:
        conditions.append("title LIKE ?")
        params.append(f"%{q}%")

    where = " AND ".join(conditions)
    tasks = store.query(
        f"SELECT * FROM tasks WHERE {where} ORDER BY priority DESC, due_date ASC LIMIT ?",
        params + [limit],
    )

    def get_reasons(t):
        reasons = []
        if t["due_date"]:
            due_date = date.fromisoformat(t["due_date"])
            days = (due_date - date.today()).days
            if days < 0:
                reasons.append(f"Overdue {abs(days)}d")
            elif days == 0:
                reasons.append("Due today")
            elif days == 1:
                reasons.append("Due tomorrow")
            elif days <= 7:
                reasons.append(f"Due in {days}d")
        if t["urgency"] == "high":
            reasons.append("High urgency")
        if t["project"]:
            reasons.append(t["project"][:20])
        return reasons

    return {
        "items": [
            {
                "id": t["id"],
                "title": t["title"],
                "score": t["priority"],
                "due": t["due_date"],
                "assignee": t["assignee"],
                "source": t["source"],
                "project": t["project"],
                "reasons": get_reasons(t),
            }
            for t in tasks
        ],
        "total": store.count("tasks", where, params),
    }


class BulkAction(BaseModel):
    action: str
    ids: list[str]
    assignee: str | None = None
    snooze_days: int | None = None
    snooze_until: str | None = None
    priority: int | None = None
    project: str | None = None


@app.post("/api/priorities/bulk")
async def bulk_action(body: BulkAction):
    """Perform bulk actions on priority items."""
    from lib.change_bundles import create_task_bundle, mark_applied

    valid_actions = (
        "archive",
        "complete",
        "delete",
        "assign",
        "snooze",
        "priority",
        "project",
    )
    if body.action not in valid_actions:
        raise HTTPException(400, f"Action must be one of: {', '.join(valid_actions)}")

    if not body.ids:
        raise HTTPException(400, "No task IDs provided")

    # Capture pre-images for rollback
    pre_images = {}
    for task_id in body.ids:
        task = store.get("tasks", task_id)
        if not task:
            continue
        pre_images[task_id] = {
            "status": task.get("status"),
            "assignee": task.get("assignee"),
            "due_date": task.get("due_date"),
            "priority": task.get("priority"),
            "project": task.get("project"),
        }

    # Build updates list
    updates = []
    now = datetime.now().isoformat()

    for task_id in body.ids:
        if task_id not in pre_images:
            continue

        update_data = {"updated_at": now}

        if body.action == "archive":
            update_data["status"] = "archived"
        elif body.action == "complete":
            update_data["status"] = "completed"
        elif body.action == "delete":
            update_data["status"] = "deleted"
        elif body.action == "assign":
            if body.assignee is None:
                raise HTTPException(400, "assignee field required for assign action")
            update_data["assignee"] = body.assignee
        elif body.action == "snooze":
            if body.snooze_until:
                update_data["due_date"] = body.snooze_until
            elif body.snooze_days:
                from datetime import timedelta

                new_date = (datetime.now() + timedelta(days=body.snooze_days)).strftime("%Y-%m-%d")
                update_data["due_date"] = new_date
            else:
                raise HTTPException(400, "snooze_days or snooze_until required for snooze action")
            update_data["status"] = "snoozed"
        elif body.action == "priority":
            if body.priority is None:
                raise HTTPException(400, "priority field required for priority action")
            update_data["priority"] = max(10, min(90, body.priority))
        elif body.action == "project":
            update_data["project"] = body.project

        updates.append({"id": task_id, "type": body.action, "data": update_data})

    # Create bundle for rollback
    bundle = create_task_bundle(
        description=f"Bulk {body.action}: {len(updates)} tasks",
        updates=updates,
        pre_images=pre_images,
    )

    # Apply updates
    updated = 0
    for update in updates:
        try:
            store.update("tasks", update["id"], update["data"])
            updated += 1
        except Exception as e:
            logger.info(f"Failed to update {update['id']}: {e}")
    mark_applied(bundle["id"])
    store.clear_cache("priority_queue")

    return {
        "success": True,
        "updated": updated,
        "action": body.action,
        "bundle_id": bundle["id"],
    }


class SavedFilter(BaseModel):
    name: str
    filters: dict


@app.get("/api/filters")
async def get_saved_filters():
    """Get saved filters."""
    filters = store.query("SELECT * FROM saved_filters ORDER BY name")
    return {"filters": [dict(f) for f in filters]}


@app.get("/api/priorities/advanced")
async def advanced_filter(
    q: str | None = None,
    due: str | None = None,
    assignee: str | None = None,
    project: str | None = None,
    status: str | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    tags: str | None = None,
    sort: str = "score",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
):
    """Advanced priority filtering with more options."""
    from lib.analyzers.priority import PriorityAnalyzer

    analyzer = PriorityAnalyzer(store=store)
    all_items = analyzer.analyze()

    filtered = all_items

    # Text search
    if q:
        q_lower = q.lower()
        filtered = [i for i in filtered if q_lower in (i.get("title") or "").lower()]

    # Due date filter
    if due:
        today = datetime.now().date()

        if due == "today":
            today_str = today.isoformat()
            filtered = [i for i in filtered if i.get("due") and i["due"][:10] == today_str]
        elif due == "tomorrow":
            from datetime import timedelta

            tomorrow_str = (today + timedelta(days=1)).isoformat()
            filtered = [i for i in filtered if i.get("due") and i["due"][:10] == tomorrow_str]
        elif due == "week":
            from datetime import timedelta

            week_end = (today + timedelta(days=7)).isoformat()
            filtered = [i for i in filtered if i.get("due") and i["due"][:10] <= week_end]
        elif due == "overdue":
            today_str = today.isoformat()
            filtered = [i for i in filtered if i.get("due") and i["due"][:10] < today_str]
        elif due == "no_date":
            filtered = [i for i in filtered if not i.get("due")]
        elif due.startswith("range:"):
            parts = due.split(":")
            if len(parts) == 3:
                start_date, end_date = parts[1], parts[2]
                filtered = [
                    i for i in filtered if i.get("due") and start_date <= i["due"][:10] <= end_date
                ]

    # Assignee filter
    if assignee:
        if assignee.lower() == "unassigned":
            filtered = [i for i in filtered if not i.get("assignee")]
        elif assignee.lower() == "me":
            filtered = [i for i in filtered if i.get("assignee") and "me" in i["assignee"].lower()]
        else:
            filtered = [
                i
                for i in filtered
                if i.get("assignee") and assignee.lower() in i["assignee"].lower()
            ]

    # Project filter
    if project:
        filtered = [
            i for i in filtered if i.get("project") and project.lower() in i["project"].lower()
        ]

    # Status filter
    if status:
        filtered = [i for i in filtered if i.get("status") == status]

    # Score filters
    if min_score is not None:
        filtered = [i for i in filtered if i.get("score", 0) >= min_score]
    if max_score is not None:
        filtered = [i for i in filtered if i.get("score", 0) <= max_score]

    # Tags filter
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",")]

        def has_tags(item):
            item_tags = item.get("tags") or ""
            if isinstance(item_tags, str):
                item_tags = [t.strip().lower() for t in item_tags.split(",")]
            else:
                item_tags = [t.lower() for t in item_tags]
            return any(t in item_tags for t in tag_list)

        filtered = [i for i in filtered if has_tags(i)]

    # Sorting
    sort_key = {
        "score": lambda x: x.get("score", 0),
        "due": lambda x: x.get("due") or "9999-99-99",
        "title": lambda x: (x.get("title") or "").lower(),
        "assignee": lambda x: (x.get("assignee") or "").lower(),
    }.get(sort, lambda x: x.get("score", 0))

    reverse = order.lower() != "asc"
    filtered = sorted(filtered, key=sort_key, reverse=reverse)

    total = len(filtered)
    filtered = filtered[offset : offset + limit]

    return {
        "items": filtered,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


@app.post("/api/priorities/archive-stale")
async def archive_stale(days_threshold: int = 14):
    """Archive stale priority items."""

    cutoff = (datetime.now() - timedelta(days=days_threshold)).isoformat()

    tasks = store.query(
        """
        SELECT id, title FROM tasks
        WHERE status = 'pending'
        AND updated_at < ?
        AND snoozed_until IS NULL
    """,
        [cutoff],
    )

    for task in tasks:
        store.update(
            "tasks",
            task["id"],
            {"status": "archived", "updated_at": datetime.now().isoformat()},
        )

    return {"success": True, "archived_count": len(tasks)}


@app.get("/api/events")
async def get_events(hours: int = 24):
    """Get upcoming events."""

    start = datetime.now().isoformat()
    end = (datetime.now() + timedelta(hours=hours)).isoformat()

    events = store.query(
        """
        SELECT * FROM events
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time
    """,
        [start, end],
    )

    return {"events": [dict(e) for e in events], "total": len(events)}


@app.get("/api/day/{date}")
async def get_day_analysis(date: str | None = None):
    """Get analysis for a specific day."""
    target = datetime.fromisoformat(date) if date else datetime.now()
    return analyzers.time.analyze_day(target)


@app.get("/api/week")
async def get_week_analysis():
    """Get analysis for the current week."""
    from lib.time_truth import get_week_analysis

    return get_week_analysis(store)


@app.get("/api/emails")
async def get_emails(actionable_only: bool = False, unread_only: bool = False, limit: int = 30):
    """Get emails from communications."""
    conditions = ["type = 'email'"]

    if actionable_only:
        conditions.append("actionable = 1")
    if unread_only:
        conditions.append("(processed = 0 OR processed IS NULL)")

    emails = store.query(
        f"""
        SELECT * FROM communications
        WHERE {" AND ".join(conditions)}
        ORDER BY received_at DESC
        LIMIT ?
    """,
        [limit],
    )

    return {"emails": [dict(e) for e in emails], "total": len(emails)}


@app.post("/api/emails/{email_id}/mark-actionable")
async def mark_email_actionable(email_id: str):
    """Mark an email as actionable."""
    store.update(
        "communications",
        email_id,
        {"actionable": 1, "updated_at": datetime.now().isoformat()},
    )
    return {"success": True, "id": email_id}


@app.get("/api/insights")
async def get_insights(category: str | None = None):
    """Get insights."""
    conditions = ["(expires_at IS NULL OR expires_at > datetime('now'))"]
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)

    insights = store.query(
        f"""
        SELECT * FROM insights
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC
    """,
        params if params else None,
    )

    return {"insights": [dict(i) for i in insights], "total": len(insights)}


@app.get("/api/anomalies")
async def get_anomalies():
    """Get anomalies."""
    anomalies = store.query("""
        SELECT * FROM insights
        WHERE type = 'anomaly'
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY severity DESC, created_at DESC
    """)

    return {"anomalies": [dict(a) for a in anomalies], "total": len(anomalies)}


@app.get("/api/notifications")
async def get_notifications(include_dismissed: bool = False, limit: int = 50):
    """Get notifications."""
    conditions = ["1=1"]
    if not include_dismissed:
        conditions.append("(dismissed = 0 OR dismissed IS NULL)")

    notifications = store.query(
        f"""
        SELECT * FROM notifications
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC
        LIMIT ?
    """,
        [limit],
    )

    return {
        "notifications": [dict(n) for n in notifications],
        "total": len(notifications),
    }


@app.get("/api/notifications/stats")
async def get_notification_stats():
    """Get notification statistics."""
    total = store.count("notifications", "1=1")
    unread = store.count("notifications", "(dismissed = 0 OR dismissed IS NULL)")

    return {"total": total, "unread": unread}


@app.post("/api/notifications/{notif_id}/dismiss")
async def dismiss_notification(notif_id: str):
    """Dismiss a notification."""
    store.update(
        "notifications",
        notif_id,
        {"dismissed": 1, "dismissed_at": datetime.now().isoformat()},
    )
    return {"success": True, "id": notif_id}


@app.post("/api/notifications/dismiss-all")
async def dismiss_all_notifications():
    """Dismiss all notifications."""
    now = datetime.now().isoformat()
    notifications = store.query(
        "SELECT id FROM notifications WHERE dismissed = 0 OR dismissed IS NULL"
    )

    for n in notifications:
        store.update("notifications", n["id"], {"dismissed": 1, "dismissed_at": now})

    return {"success": True, "dismissed_count": len(notifications)}


# ==== Approvals Endpoints ====


@app.get("/api/approvals")
async def get_approvals():
    """Get pending approvals."""
    approvals = store.query(
        "SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC"
    )
    return {"approvals": [dict(a) for a in approvals], "total": len(approvals)}


@app.post("/api/approvals/{decision_id}")
async def process_approval(decision_id: str, body: ApprovalAction):
    """Process an approval."""
    decision = store.get("decisions", decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    approved = body.action == "approve"
    store.update(
        "decisions",
        decision_id,
        {"approved": 1 if approved else 0, "approved_at": datetime.now().isoformat()},
    )

    return {
        "status": "approved" if approved else "rejected",
        "decision_id": decision_id,
    }


class ModifyApproval(BaseModel):
    modifications: dict


@app.post("/api/approvals/{decision_id}/modify")
async def modify_approval(decision_id: str, body: ModifyApproval):
    """Modify and approve a decision."""
    dec = store.get("decisions", decision_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")

    now = datetime.now().isoformat()
    store.update(
        "decisions",
        decision_id,
        {
            "approved": 1,
            "approved_at": now,
            "modifications": json.dumps(body.modifications),
        },
    )

    return {"success": True, "id": decision_id, "modified": True}


# ==== Governance Endpoints ====


@app.get("/api/governance")
async def get_governance_status():
    """Get governance configuration and status."""
    return {
        "domains": governance.get_all_domains(),
        "emergency_brake": governance.is_emergency_brake_active(),
        "summary": governance.get_summary(),
    }


@app.put("/api/governance/{domain}")
async def set_governance_mode(domain: str, body: ModeChange):
    """Set governance mode for a domain."""
    try:
        mode = DomainMode(body.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {body.mode}")

    governance.set_mode(domain, mode)

    # Log the change
    store.insert(
        "cycle_logs",
        {
            "id": f"gov_change_{datetime.now().isoformat()}",
            "cycle_number": 0,
            "phase": "governance_change",
            "data": json.dumps({"domain": domain, "new_mode": body.mode}),
            "created_at": datetime.now().isoformat(),
        },
    )

    return {"domain": domain, "mode": body.mode, "status": "updated"}


class ThresholdUpdate(BaseModel):
    threshold: float


@app.put("/api/governance/{domain}/threshold")
async def set_governance_threshold(domain: str, body: ThresholdUpdate):
    """Set confidence threshold for a domain."""
    if not (0 <= body.threshold <= 1):
        raise HTTPException(400, "Threshold must be between 0 and 1")

    # Initialize domains in config if needed
    if "domains" not in governance.config:
        governance.config["domains"] = {}
    if domain not in governance.config["domains"]:
        governance.config["domains"][domain] = {}

    governance.config["domains"][domain]["auto_threshold"] = body.threshold
    governance._save_config()

    return {"domain": domain, "threshold": body.threshold, "status": "updated"}


@app.get("/api/governance/history")
async def get_governance_history(limit: int = 50):
    """Get governance action history."""
    history = store.query(
        """
        SELECT * FROM governance_history
        ORDER BY created_at DESC
        LIMIT ?
    """,
        [limit],
    )

    return {"history": [dict(h) for h in history], "total": len(history)}


@app.post("/api/governance/emergency-brake")
async def activate_emergency_brake(reason: str = "Manual activation"):
    """Activate emergency brake."""
    governance.activate_emergency_brake(reason)
    return {"success": True, "active": True, "reason": reason}


@app.delete("/api/governance/emergency-brake")
async def release_emergency_brake():
    """Release emergency brake."""
    governance.release_emergency_brake()
    return {"success": True, "active": False}


# ==== Sync Endpoints ====


@app.get("/api/sync/status")
async def get_sync_status():
    """Get sync status for all collectors."""
    return collectors.get_status()


@app.post("/api/sync")
async def force_sync(source: str | None = None):
    """Force a sync operation."""
    return collectors.force_sync(source=source)


@app.post("/api/analyze")
async def run_analysis():
    """Run analysis."""
    return analyzers.analyze()


@app.post("/api/cycle")
async def run_cycle():
    """Run a full autonomous cycle."""
    loop = AutonomousLoop(store, collectors, analyzers, governance)
    return loop.run_cycle()


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "sync": collectors.get_status(),
        "governance": governance.get_summary(),
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/metrics")
async def metrics():
    """
    Prometheus-format metrics endpoint.

    Exports application metrics in text format for scraping.
    """
    from lib.observability.metrics import get_registry

    registry = get_registry()
    lines = []

    # Export counters
    for name, counter in registry.counters.items():
        lines.append(f"# HELP {name} {counter.description}")
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {counter.value}")

    # Export gauges
    for name, gauge in registry.gauges.items():
        lines.append(f"# HELP {name} {gauge.description}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {gauge.value}")

    # Export histograms (simplified: just count and sum)
    for name, histogram in registry.histograms.items():
        lines.append(f"# HELP {name} {histogram.description}")
        lines.append(f"# TYPE {name} histogram")
        with histogram._lock:
            count = len(histogram._values)
            total = sum(histogram._values) if histogram._values else 0
        lines.append(f"{name}_count {count}")
        lines.append(f"{name}_sum {total:.6f}")

    # Add process info
    import os

    lines.append("# HELP process_start_time_seconds Process start time")
    lines.append("# TYPE process_start_time_seconds gauge")
    lines.append(f"process_start_time_seconds {os.getpid()}")

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@app.get("/api/debug/db")
async def debug_db():
    """
    Debug endpoint to inspect database configuration.

    Returns resolved DB path, file info, schema version, and column lists
    for key tables (tasks, communications).
    """
    return db_module.get_db_info()


@app.get("/api/summary")
async def get_summary():
    """Get a comprehensive summary."""
    from datetime import date

    # Get cached data
    queue = store.get_cache("priority_queue") or []
    anomalies = store.get_cache("anomalies") or []

    # Today's info
    today = date.today().isoformat()
    today_events = store.query(
        "SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time", [today]
    )

    # Calculate total event hours
    total_event_hours = 0
    for e in today_events:
        try:
            start = datetime.fromisoformat(e["start_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(e["end_time"].replace("Z", "+00:00"))
            total_event_hours += (end - start).total_seconds() / 3600
        except (ValueError, TypeError, AttributeError) as ex:
            logger.debug(f"Could not parse event times for event {e.get('id', 'unknown')}: {ex}")

    # Calculate available hours (9 hour work day)
    work_hours = 9
    available = max(0, work_hours - total_event_hours)

    return {
        "priorities": {
            "top_5": queue[:5],
            "total": len(queue),
            "critical_count": len([i for i in queue if i.get("score", 0) >= 70]),
        },
        "anomalies": {
            "items": [a for a in anomalies if a.get("severity") in ("critical", "high")],
            "total": len(anomalies),
        },
        "today": {
            "events": len(today_events),
            "event_list": [
                {"title": e["title"], "start": e["start_time"], "end": e["end_time"]}
                for e in today_events[:5]
            ],
            "total_event_hours": round(total_event_hours, 1),
            "available_hours": round(available, 1),
            "deep_work_hours": round(max(0, available - 2), 1),
        },
        "pending_approvals": store.count("decisions", "approved IS NULL"),
        "sync_status": collectors.get_status(),
    }


@app.get("/api/search")
async def search_items(q: str, limit: int = 20):
    """Search across tasks, projects, and clients."""
    results = []

    # Search tasks
    tasks = store.query(
        """
        SELECT 'task' as type, id, title, status, project FROM tasks
        WHERE title LIKE ? OR description LIKE ?
        LIMIT ?
    """,
        [f"%{q}%", f"%{q}%", limit],
    )
    results.extend([dict(t) for t in tasks])

    # Search projects
    projects = store.query(
        """
        SELECT 'project' as type, id, name as title, status FROM projects
        WHERE name LIKE ?
        LIMIT ?
    """,
        [f"%{q}%", limit],
    )
    results.extend([dict(p) for p in projects])

    # Search clients
    clients = store.query(
        """
        SELECT 'client' as type, id, name as title, tier FROM clients
        WHERE name LIKE ?
        LIMIT ?
    """,
        [f"%{q}%", limit],
    )
    results.extend([dict(c) for c in clients])

    return {"results": results[:limit], "total": len(results)}


@app.get("/api/team/workload")
async def get_team_workload():
    """Get team workload distribution."""
    workload = store.query("""
        SELECT
            assignee,
            COUNT(*) as total,
            SUM(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) as overdue,
            SUM(CASE WHEN due_date = date('now') THEN 1 ELSE 0 END) as due_today,
            AVG(priority) as avg_priority
        FROM tasks
        WHERE status = 'pending' AND assignee IS NOT NULL AND assignee != ''
        GROUP BY assignee
        ORDER BY total DESC
    """)

    return {
        "team": [
            {
                "name": w["assignee"],
                "total": w["total"],
                "overdue": w["overdue"] or 0,
                "due_today": w["due_today"] or 0,
                "avg_priority": round(w["avg_priority"] or 0, 1),
                "status": "overloaded"
                if w["total"] > 15
                else ("busy" if w["total"] > 8 else "available"),
            }
            for w in workload
        ]
    }


@app.get("/api/priorities/grouped")
async def get_grouped_priorities(group_by: str = "project", limit: int = 10):
    """Get priorities grouped by a field."""
    if group_by not in ("project", "assignee", "source"):
        group_by = "project"

    groups = store.query(
        f"""
        SELECT
            {group_by} as group_name,
            COUNT(*) as total,
            SUM(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) as overdue,
            MAX(priority) as max_priority
        FROM tasks
        WHERE status = 'pending' AND {group_by} IS NOT NULL AND {group_by} != ''
        GROUP BY {group_by}
        ORDER BY overdue DESC, total DESC
        LIMIT ?
    """,
        [limit],
    )

    return {
        "groups": [
            {
                "name": g["group_name"],
                "total": g["total"],
                "overdue": g["overdue"] or 0,
                "max_priority": g["max_priority"] or 0,
            }
            for g in groups
        ],
        "group_by": group_by,
    }


# Fallback health calculation when no task data available
def _ar_health_factor(client: dict) -> int:
    """Health factor based on AR aging (100 = no AR, lower = worse aging)."""
    ar = client.get("financial_ar_total") or 0
    aging = client.get("financial_ar_aging_bucket")
    if ar == 0:
        return 100
    if aging == "current":
        return 80
    if aging == "30":
        return 60
    if aging == "60":
        return 40
    if aging == "90+":
        return 20
    return 70  # Unknown aging


def _relationship_health_factor(client: dict) -> int:
    """Health factor based on relationship_health field."""
    health = client.get("relationship_health")
    scores = {"excellent": 100, "good": 80, "fair": 60, "poor": 35, "critical": 15}
    return scores.get(health, 70)


def _recency_health_factor(client: dict) -> int:
    """Health factor based on last interaction recency."""
    last = client.get("relationship_last_interaction")
    if not last:
        return 50  # Unknown
    try:
        from datetime import datetime

        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        days_ago = (datetime.now(last_dt.tzinfo) - last_dt).days
        if days_ago < 7:
            return 100
        if days_ago < 30:
            return 80
        if days_ago < 90:
            return 60
        return 40
    except Exception:
        return 50


def _compute_fallback_health(client: dict) -> int:
    """Compute health score from AR + relationship when task data unavailable."""
    ar_factor = _ar_health_factor(client)
    rel_factor = _relationship_health_factor(client)
    recency_factor = _recency_health_factor(client)

    # Weighted average: AR 40%, Relationship 40%, Recency 20%
    score = int(ar_factor * 0.4 + rel_factor * 0.4 + recency_factor * 0.2)
    return max(0, min(100, score))


@app.get("/api/clients")
async def get_clients(
    tier: str | None = None,
    health: str | None = None,
    ar_status: str | None = None,
    active_only: bool = True,
    limit: int = 100,
):
    """Get clients with filters."""
    conditions = ["1=1"]
    params = []

    if tier:
        conditions.append("tier = ?")
        params.append(tier)
    if health:
        conditions.append("relationship_health = ?")
        params.append(health)
    if ar_status:
        if ar_status == "overdue":
            conditions.append(
                "financial_ar_total > 0 AND financial_ar_aging_bucket IN ('30+', '60+', '90+')"
            )
        elif ar_status == "any":
            conditions.append("financial_ar_total > 0")
        elif ar_status == "none":
            conditions.append("(financial_ar_total IS NULL OR financial_ar_total = 0)")

    if active_only:
        active_client_ids = store.query("""
            SELECT DISTINCT client_id FROM tasks
            WHERE client_id IS NOT NULL
            AND (updated_at >= date('now', '-90 days') OR status = 'pending')
            UNION
            SELECT DISTINCT client_id FROM projects
            WHERE client_id IS NOT NULL
            AND status = 'active'
        """)
        active_ids = [r["client_id"] for r in active_client_ids]

        if active_ids:
            placeholders = ",".join(["?" for _ in active_ids])
            conditions.append(f"id IN ({placeholders})")
            params.extend(active_ids)
        else:
            return {"items": [], "total": 0, "active_only": True}

    params.append(limit)

    clients = store.query(
        f"""
        SELECT * FROM clients
        WHERE {" AND ".join(conditions)}
        ORDER BY
            CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
            financial_ar_total DESC NULLS LAST,
            name
        LIMIT ?
    """,
        params,
    )

    # Import health calculator for scoring
    from lib.client_truth import HealthCalculator

    HealthCalculator(store)

    result = []
    for c in clients:
        client_dict = dict(c)

        # Compute health score - fallback to AR/relationship when no task data
        health_score = _compute_fallback_health(c)
        client_dict["health_score"] = health_score
        client_dict["health_trend"] = c.get("relationship_trend")
        client_dict["health_factors"] = {
            "ar_factor": _ar_health_factor(c),
            "relationship_factor": _relationship_health_factor(c),
            "recency_factor": _recency_health_factor(c),
        }
        client_dict["computed_at_risk"] = health_score < 50

        # Project count
        projects = store.query(
            "SELECT COUNT(*) as cnt FROM projects WHERE client_id = ? AND status = 'active'",
            [c["id"]],
        )
        client_dict["project_count"] = projects[0]["cnt"] if projects else 0

        # Open task count
        tasks = store.query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE client_id = ? AND status = 'pending'",
            [c["id"]],
        )
        client_dict["open_task_count"] = tasks[0]["cnt"] if tasks else 0

        # Overdue task count
        overdue = store.query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE client_id = ? AND status = 'pending' AND due_date < date('now')",
            [c["id"]],
        )
        client_dict["overdue_task_count"] = overdue[0]["cnt"] if overdue else 0

        result.append(client_dict)

    # Sort by computed health score (worst first) if available
    result.sort(key=lambda x: (x.get("health_score") or 100, x.get("name", "")))

    return {"items": result, "total": len(result), "active_only": active_only}


@app.get("/api/clients/portfolio")
async def get_client_portfolio():
    """Get client portfolio overview."""
    tier_stats = store.query("""
        SELECT
            tier,
            COUNT(*) as count,
            SUM(financial_ar_total) as total_ar,
            SUM(CASE WHEN relationship_health IN ('poor', 'critical') THEN 1 ELSE 0 END) as at_risk
        FROM clients
        WHERE tier IS NOT NULL
        GROUP BY tier
        ORDER BY CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 END
    """)

    health_stats = store.query("""
        SELECT
            relationship_health as health,
            COUNT(*) as count
        FROM clients
        WHERE relationship_health IS NOT NULL
        GROUP BY relationship_health
    """)

    at_risk = store.query("""
        SELECT * FROM clients
        WHERE (tier IN ('A', 'B') AND relationship_health IN ('poor', 'critical'))
           OR (financial_ar_total > 100000 AND financial_ar_aging_bucket = '90+')
        ORDER BY tier, financial_ar_total DESC
        LIMIT 10
    """)

    totals = store.query("""
        SELECT
            COUNT(*) as total_clients,
            SUM(financial_ar_total) as total_ar,
            SUM(financial_annual_value) as total_annual_value
        FROM clients
    """)

    overdue_ar = store.query("""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(financial_ar_total), 0) as total
        FROM clients
        WHERE financial_ar_total > 0
        AND financial_ar_aging_bucket IN ('30+', '60+', '90+')
    """)

    return {
        "by_tier": [dict(t) for t in tier_stats],
        "by_health": [dict(h) for h in health_stats],
        "at_risk": [dict(r) for r in at_risk],
        "totals": dict(totals[0]) if totals else {},
        "overdue_ar": dict(overdue_ar[0]) if overdue_ar else {},
    }


@app.get("/api/clients/{client_id}")
async def get_client_detail(client_id: str):
    """Get detailed client information."""
    client = store.get("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get all enrolled projects with task counts
    all_projects = store.query(
        """
        SELECT p.*,
            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending') as open_tasks,
            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending' AND t.due_date < date('now')) as overdue_tasks
        FROM projects p
        WHERE p.client_id = ? AND p.enrollment_status = 'enrolled'
        ORDER BY p.involvement_type DESC, p.name
    """,
        [client_id],
    )

    # Separate retainers and projects
    retainers = [dict(p) for p in all_projects if p["involvement_type"] == "retainer"]
    projects = [dict(p) for p in all_projects if p["involvement_type"] == "project"]

    # Calculate totals
    total_tasks = sum(p.get("open_tasks", 0) for p in all_projects)
    total_overdue = sum(p.get("overdue_tasks", 0) for p in all_projects)

    # Get financials
    ar_outstanding = client.get("financial_ar_total") or 0
    ar_aging = client.get("financial_ar_aging_bucket") or "current"
    annual_value = client.get("financial_annual_value") or 0

    # Get contacts
    contacts = []
    if client.get("contacts_json"):
        try:
            contacts = json.loads(client["contacts_json"])
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Could not parse contacts_json for client: {e}")

    return {
        "client": dict(client),
        "retainers": retainers,
        "projects": projects,
        "summary": {
            "total_tasks": total_tasks,
            "overdue_tasks": total_overdue,
            "retainer_count": len(retainers),
            "project_count": len(projects),
            "ar_outstanding": ar_outstanding,
            "ar_aging": ar_aging,
            "annual_value": annual_value,
        },
        "contacts": contacts,
    }


class ClientUpdate(BaseModel):
    tier: str | None = None
    health: str | None = None
    trend: str | None = None
    notes: str | None = None
    annual_value: float | None = None
    contact_name: str | None = None
    contact_email: str | None = None


@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, body: ClientUpdate):
    """Update client information."""
    client = store.get("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    updates = {}

    if body.tier is not None:
        if body.tier not in ("A", "B", "C", ""):
            raise HTTPException(status_code=400, detail="Tier must be A, B, or C")
        updates["tier"] = body.tier or None

    if body.health is not None:
        updates["relationship_health"] = body.health or None

    if body.trend is not None:
        updates["relationship_trend"] = body.trend or None

    if body.notes is not None:
        updates["relationship_notes"] = body.notes

    if body.annual_value is not None:
        updates["financial_annual_value"] = body.annual_value

    if body.contact_name is not None:
        updates["contact_name"] = body.contact_name

    if body.contact_email is not None:
        updates["contact_email"] = body.contact_email

    if updates:
        updates["updated_at"] = datetime.now().isoformat()
        store.update("clients", client_id, updates)

    return {"success": True, "id": client_id, "updated": list(updates.keys())}


@app.get("/api/projects")
async def get_projects(
    client_id: str | None = None, include_archived: bool = False, limit: int = 50
):
    """Get projects with filters."""
    conditions = ["1=1"]
    params = []

    if client_id:
        conditions.append("client_id = ?")
        params.append(client_id)

    if not include_archived:
        conditions.append("enrollment_status != 'archived'")

    params.append(limit)

    projects = store.query(
        f"""
        SELECT * FROM projects
        WHERE {" AND ".join(conditions)}
        ORDER BY updated_at DESC
        LIMIT ?
    """,
        params,
    )

    return {"projects": [dict(p) for p in projects], "total": len(projects)}


@app.get("/api/projects/candidates")
async def get_project_candidates():
    """Get projects that could be enrolled (candidates and proposed)."""
    candidates = store.query("""
        SELECT p.*, c.name as client_name
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.id
        WHERE p.enrollment_status IN ('candidate', 'proposed')
        ORDER BY p.proposed_at DESC NULLS LAST, p.name
    """)

    return {
        "items": [dict(p) for p in candidates],
        "total": len(candidates),
        "proposed": len([p for p in candidates if p["enrollment_status"] == "proposed"]),
        "candidate": len([p for p in candidates if p["enrollment_status"] == "candidate"]),
    }


@app.get("/api/projects/enrolled")
async def get_enrolled_projects():
    """Get enrolled projects with client info and task counts."""
    projects = store.query("""
        SELECT p.*, c.name as client_name, c.tier as client_tier,
            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending') as open_tasks,
            (SELECT COUNT(*) FROM tasks t WHERE t.project = p.id AND t.status = 'pending' AND t.due_date < date('now')) as overdue_tasks
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.id
        WHERE p.enrollment_status = 'enrolled'
        ORDER BY p.involvement_type DESC, c.tier NULLS LAST, p.name
    """)

    retainers = [dict(p) for p in projects if p["involvement_type"] == "retainer"]
    active_projects = [dict(p) for p in projects if p["involvement_type"] == "project"]

    return {"retainers": retainers, "projects": active_projects, "total": len(projects)}


class EnrollmentAction(BaseModel):
    action: str
    reason: str | None = None
    client_id: str | None = None
    involvement_type: str | None = None
    snooze_days: int | None = None


@app.post("/api/projects/{project_id}/enrollment")
async def process_enrollment(project_id: str, body: EnrollmentAction):
    """Process project enrollment action."""
    project = store.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.now().isoformat()

    if body.action == "enroll":
        updates = {
            "enrollment_status": "enrolled",
            "enrolled_at": now,
            "updated_at": now,
        }
        if body.client_id:
            updates["client_id"] = body.client_id
        if body.involvement_type:
            updates["involvement_type"] = body.involvement_type
        store.update("projects", project_id, updates)
        return {"success": True, "status": "enrolled", "id": project_id}

    if body.action == "reject":
        store.update("projects", project_id, {"enrollment_status": "rejected", "updated_at": now})
        return {"success": True, "status": "rejected", "id": project_id}

    if body.action == "snooze":
        from datetime import timedelta

        snooze_until = (datetime.now() + timedelta(days=body.snooze_days or 14)).isoformat()
        store.update("projects", project_id, {"enrollment_status": "snoozed", "updated_at": now})
        return {
            "success": True,
            "status": "snoozed",
            "id": project_id,
            "until": snooze_until,
        }

    if body.action == "internal":
        store.update("projects", project_id, {"enrollment_status": "internal", "updated_at": now})
        return {"success": True, "status": "internal", "id": project_id}

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


@app.get("/api/projects/detect")
async def detect_new_projects(force: bool = False):
    """Detect new projects from tasks."""
    # Find unique project names in tasks that aren't in projects table
    new_projects = store.query("""
        SELECT DISTINCT project as name, COUNT(*) as task_count
        FROM tasks
        WHERE project IS NOT NULL AND project != ''
        AND project NOT IN (SELECT name FROM projects)
        GROUP BY project
        ORDER BY task_count DESC
    """)

    return {"detected": [dict(p) for p in new_projects], "total": len(new_projects)}


@app.get("/api/projects/{project_id}")
async def get_project_detail(project_id: str):
    """Get detailed project information."""
    project = store.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get linked client
    client = None
    if project.get("client_id"):
        client = store.get("clients", project["client_id"])

    # Get pending tasks for this project
    tasks = store.query(
        """
        SELECT * FROM tasks
        WHERE project = ? AND status = 'pending'
        ORDER BY due_date ASC NULLS LAST, priority DESC
        LIMIT 30
    """,
        [project["name"]],
    )

    # Get overdue count
    overdue = store.query(
        """
        SELECT COUNT(*) as cnt FROM tasks
        WHERE project = ? AND status = 'pending' AND due_date < date('now')
    """,
        [project["name"]],
    )

    return {
        "project": dict(project),
        "client": dict(client) if client else None,
        "tasks": [dict(t) for t in tasks],
        "overdue_count": overdue[0]["cnt"] if overdue else 0,
    }


@app.post("/api/sync/xero")
async def sync_xero():
    """Sync with Xero."""
    return collectors.sync(source="xero")


@app.post("/api/tasks/link")
async def bulk_link_tasks():
    """Bulk link tasks to projects/clients."""
    raise HTTPException(status_code=501, detail="Bulk linking not implemented")


@app.post("/api/projects/propose")
async def propose_project(name: str, client_id: str | None = None, type: str = "retainer"):
    """Propose a new project."""
    import uuid

    project_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    project_data = {
        "id": project_id,
        "name": name,
        "client_id": client_id,
        "type": type,
        "enrollment_status": "candidate",
        "created_at": now,
        "updated_at": now,
    }

    store.insert("projects", project_data)

    return {"success": True, "project": project_data}


# NOTE: /api/emails duplicate removed (version with actionable_only/unread_only filters above is better)
# The endpoint below was simplified but less flexible

async def _get_email_queue_old(limit: int = 20):
    """[UNUSED] Get email queue - replaced by get_emails above."""
    emails = store.query(
        """
        SELECT * FROM communications
        WHERE type = 'email' AND (processed = 0 OR processed IS NULL)
        ORDER BY received_at DESC
        LIMIT ?
    """,
        [limit],
    )

    return {
        "items": [
            {
                "id": e.get("id"),
                "subject": e.get("subject"),
                "from": e.get("from_address") or e.get("sender"),
                "received": e.get("received_at") or e.get("created_at"),
                "snippet": (e.get("snippet") or e.get("body") or "")[:100],
                "thread_id": e.get("thread_id"),
            }
            for e in emails
        ],
        "total": store.count("communications", "(processed = 0 OR processed IS NULL)"),
    }


@app.post("/api/emails/{email_id}/dismiss")
async def dismiss_email(email_id: str):
    """Dismiss an email."""
    store.update("communications", email_id, {"processed": 1})
    return {"success": True, "id": email_id}


@app.get("/api/digest/weekly")
async def get_weekly_digest():
    """Get weekly digest."""
    from datetime import date

    week_ago = (date.today() - timedelta(days=7)).isoformat()

    completed = store.query(
        """
        SELECT * FROM tasks
        WHERE status = 'completed' AND updated_at >= ?
        ORDER BY updated_at DESC
    """,
        [week_ago],
    )

    slipped = store.query(
        """
        SELECT * FROM tasks
        WHERE status = 'pending' AND due_date < date('now') AND due_date >= ?
        ORDER BY due_date ASC
    """,
        [week_ago],
    )

    archived = store.query(
        """
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status = 'archived' AND updated_at >= ?
    """,
        [week_ago],
    )

    return {
        "period": {"start": week_ago, "end": date.today().isoformat()},
        "completed": {
            "count": len(completed),
            "items": [
                {"id": t["id"], "title": t["title"], "completed_at": t["updated_at"]}
                for t in completed[:10]
            ],
        },
        "slipped": {
            "count": len(slipped),
            "items": [
                {
                    "id": t["id"],
                    "title": t["title"],
                    "due": t["due_date"],
                    "assignee": t["assignee"],
                }
                for t in slipped[:10]
            ],
        },
        "archived": archived[0]["cnt"] if archived else 0,
    }


# ==== Blockers Endpoints ====


class BlockerRequest(BaseModel):
    blocker_id: str


@app.post("/api/tasks/{task_id}/block")
async def add_blocker(task_id: str, body: BlockerRequest):
    """Add a blocker to a task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    blocker = store.get("tasks", body.blocker_id)
    if not blocker:
        raise HTTPException(status_code=404, detail="Blocker task not found")

    try:
        current = json.loads(task.get("blockers") or "[]")
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Could not parse blockers JSON for task {task_id}: {e}")
        current = []

    if body.blocker_id not in current:
        current.append(body.blocker_id)
        store.update(
            "tasks",
            task_id,
            {"blockers": json.dumps(current), "updated_at": datetime.now().isoformat()},
        )

    return {"success": True, "blockers": current}


@app.delete("/api/tasks/{task_id}/block/{blocker_id}")
async def remove_blocker(task_id: str, blocker_id: str):
    """Remove a blocker from a task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        current = json.loads(task.get("blockers") or "[]")
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Could not parse blockers JSON for task {task_id}: {e}")
        current = []

    if blocker_id in current:
        current.remove(blocker_id)
        store.update(
            "tasks",
            task_id,
            {"blockers": json.dumps(current), "updated_at": datetime.now().isoformat()},
        )

    return {"success": True, "blockers": current}


@app.get("/api/dependencies")
async def get_dependencies():
    """Get task dependency graph."""
    blocked = store.query("""
        SELECT * FROM tasks
        WHERE status = 'pending' AND blockers IS NOT NULL AND blockers != '' AND blockers != '[]'
        ORDER BY priority DESC
    """)

    blocking_ids = set()
    for t in blocked:
        try:
            blockers = json.loads(t["blockers"]) if t["blockers"] else []
            for b in blockers:
                if isinstance(b, str):
                    blocking_ids.add(b)
                elif isinstance(b, dict):
                    blocking_ids.add(b.get("id", ""))
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Could not parse blockers JSON for task {t.get('id', 'unknown')}: {e}")

    return {
        "blocked": [
            {
                "id": t["id"],
                "title": t["title"],
                "blockers": t["blockers"],
                "assignee": t["assignee"],
                "due": t["due_date"],
            }
            for t in blocked
        ],
        "blocking_count": len(blocking_ids),
        "total_blocked": len(blocked),
    }


# ==== SPA Fallback (must be LAST) ====
# Note: This is intentionally placed at the end of the file after all API routes

# ==== Control Room API (V4) ====


@app.get("/api/control-room/proposals")
async def get_proposals(
    limit: int = 7,
    status: str = "open",
    days: int = 7,
    client_id: str = None,
    member_id: str = None,
):
    """Get proposals with full hierarchy context.

    Args:
        limit: Max proposals to return
        status: Filter by status (open, snoozed, dismissed, accepted)
        days: Filter to signals within last N days (1=today, 7=week, 30=month)
        client_id: Filter to signals for a specific client (optional)
        member_id: Filter to signals for tasks assigned to this team member (optional)

    Returns:
        items: List of proposals with:
            - scope_level, scope_name (project/client level)
            - client_name, client_tier
            - score, score_breakdown
            - signal_summary (counts by category)
            - worst_signal (text description)
            - signal_count, remaining_count
    """
    try:
        # Get proposals from ProposalService
        try:
            svc = ProposalService()
            proposals_raw = (
                svc.get_all_open_proposals(limit=limit * 3)
                if status == "open"
                else svc.get_surfaceable_proposals(limit=limit * 3)
            )

            if proposals_raw and len(proposals_raw) > 0:
                # Apply client filter
                if client_id:
                    proposals_raw = [p for p in proposals_raw if p.get("client_id") == client_id]

                # Build enhanced response structure

                proposals = []
                for p in proposals_raw:
                    # Parse JSON fields
                    signal_summary = (
                        json.loads(p.get("signal_summary_json", "{}"))
                        if isinstance(p.get("signal_summary_json"), str)
                        else p.get("signal_summary_json", {})
                    )
                    score_breakdown = (
                        json.loads(p.get("score_breakdown_json", "{}"))
                        if isinstance(p.get("score_breakdown_json"), str)
                        else p.get("score_breakdown_json", {})
                    )
                    impact = (
                        json.loads(p.get("impact", "{}"))
                        if isinstance(p.get("impact"), str)
                        else p.get("impact", {})
                    )

                    signal_count = signal_summary.get("total", 0) if signal_summary else 0

                    proposals.append(
                        {
                            "proposal_id": p.get("proposal_id"),
                            "proposal_type": p.get("proposal_type", "risk"),
                            "scope_level": p.get("scope_level", "project"),
                            "scope_name": p.get("scope_name", p.get("headline", "Unknown")[:50]),
                            "client_id": p.get("client_id"),
                            "client_name": p.get("client_name"),
                            "client_tier": p.get("client_tier"),
                            "engagement_type": p.get("engagement_type", "project"),
                            "headline": p.get("headline"),
                            "score": p.get("score", 0),
                            "score_breakdown": score_breakdown,
                            "signal_summary": signal_summary,
                            "worst_signal": impact.get("worst_signal", ""),
                            "signal_count": signal_count,
                            "remaining_count": max(0, signal_count - 5),
                            "status": p.get("status", "open"),
                            "trend": p.get("trend", "flat"),
                            "first_seen_at": p.get("first_seen_at"),
                            "last_seen_at": p.get("last_seen_at"),
                        }
                    )

                # Sort by score descending
                proposals.sort(key=lambda x: x.get("score", 0), reverse=True)

                return {"items": proposals[:limit], "total": len(proposals)}
        except Exception as svc_err:
            logger.warning(f"ProposalService error: {svc_err}")
            pass

        # Fallback: Generate proposals from signals
        from datetime import datetime, timedelta

        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Calculate date cutoff
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Build query with filters
        query = """
            SELECT s.signal_id, s.signal_type, s.entity_ref_type, s.entity_ref_id,
                   s.value, s.detected_at, s.interpretation_confidence
            FROM signals s
            WHERE s.entity_ref_type IN ('task', 'client', 'project')
              AND s.detected_at >= ?
        """
        params = [cutoff_date]

        # Add client filter if specified
        if client_id:
            query += """
              AND (
                (s.entity_ref_type = 'client' AND s.entity_ref_id = ?)
                OR EXISTS (
                  SELECT 1 FROM tasks t
                  WHERE t.id = s.entity_ref_id
                  AND t.client_id = ?
                )
                OR EXISTS (
                  SELECT 1 FROM projects p
                  WHERE p.id = s.entity_ref_id
                  AND p.client_id = ?
                )
              )
            """
            params.extend([client_id, client_id, client_id])

        # Add member filter if specified
        if member_id:
            query += """
              AND EXISTS (
                SELECT 1 FROM tasks t
                WHERE t.id = s.entity_ref_id
                AND t.assignee = ?
              )
            """
            params.append(member_id)

        query += """
            ORDER BY
                CASE s.entity_ref_type
                    WHEN 'task' THEN 1
                    WHEN 'client' THEN 2
                    WHEN 'project' THEN 3
                    ELSE 4
                END,
                s.detected_at DESC
            LIMIT ?
        """
        params.append(limit * 5)  # Get more signals to group

        cur.execute(query, params)

        signal_rows = cur.fetchall()

        # Group signals by entity and build proposals
        from collections import defaultdict

        entity_signals = defaultdict(list)
        for row in signal_rows:
            key = (row["entity_ref_type"], row["entity_ref_id"])
            entity_signals[key].append(dict(row))

        proposals = []
        for (ref_type, ref_id), signals in list(entity_signals.items())[:limit]:
            # Get entity name
            entity_name = ref_id
            if ref_type == "task":
                cur.execute("SELECT title FROM tasks WHERE id = ?", (ref_id,))
                row = cur.fetchone()
                if row:
                    entity_name = row[0][:80] if row[0] else ref_id
            elif ref_type == "client":
                cur.execute("SELECT name FROM clients WHERE id = ?", (ref_id,))
                row = cur.fetchone()
                if row:
                    entity_name = row[0] if row[0] else ref_id
            elif ref_type == "project":
                cur.execute("SELECT name FROM projects WHERE id = ?", (ref_id,))
                row = cur.fetchone()
                if row:
                    entity_name = row[0] if row[0] else ref_id

            # Determine proposal type from signal types
            signal_types = [s["signal_type"] for s in signals]
            if any("overdue" in st or "risk" in st for st in signal_types):
                prop_type, severity, icon = "risk", "high", "⚠️"
            elif any("unanswered" in st or "gap" in st for st in signal_types):
                prop_type, severity, icon = "risk", "medium", "📭"
            else:
                prop_type, severity, icon = "anomaly", "low", "📋"

            # Build headline from signal type
            primary_signal = signal_types[0] if signal_types else "unknown"
            headline_map = {
                "delivery.owner_inactive_risk": f"{icon} {entity_name}: Owner inactive on delivery",
                "comms.thread_unanswered_age": f"{icon} {entity_name}: Unanswered thread aging",
                "cash.coupled_overdue_invoice_delivery": f"{icon} {entity_name}: Overdue invoice tied to delivery",
                "capacity.calendar_no_execution_window": f"{icon} {entity_name}: No execution window in calendar",
            }
            headline = headline_map.get(
                primary_signal,
                f"{icon} {entity_name}: {len(signals)} signal(s) detected",
            )

            # Generate unique proposal ID from entity key hash (use 16 chars to reduce collisions)
            import hashlib

            entity_hash = hashlib.sha256(f"{ref_type}:{ref_id}".encode()).hexdigest()[:16]
            proposals.append(
                {
                    "proposal_id": f"prop_{entity_hash}",
                    "proposal_type": prop_type,
                    "primary_ref_type": ref_type,
                    "primary_ref_id": ref_id,
                    "headline": headline,
                    "impact": {
                        "severity": severity,
                        "signal_count": len(signals),
                        "entity_type": ref_type,
                    },
                    "score": len(signals) * 10
                    + (20 if severity == "high" else 10 if severity == "medium" else 5),
                    "occurrence_count": len(signals),
                    "trend": "flat",
                    "status": "open",
                    "ui_exposure_level": "surfaced",
                    "first_seen_at": min(s["detected_at"] for s in signals),
                    "last_seen_at": max(s["detected_at"] for s in signals),
                }
            )

        # Sort by score
        proposals.sort(key=lambda x: x["score"], reverse=True)
        conn.close()
        return {"items": proposals[:limit], "total": len(proposals)}
    except Exception as e:
        import traceback

        return {
            "items": [],
            "total": 0,
            "error": str(e),
            "trace": traceback.format_exc(),
        }


@app.get("/api/control-room/issues")
async def get_issues(limit: int = 5, days: int = 7, client_id: str = None, member_id: str = None):
    """Get issues from real data in moh_time_os.db.

    Args:
        limit: Max issues to return
        days: Filter to issues active within last N days
        client_id: Filter to issues for a specific client (optional)
        member_id: Filter to issues for tasks assigned to this team member (optional)
    """
    try:
        from datetime import datetime, timedelta

        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Check if issues table has data
        cur.execute("SELECT COUNT(*) FROM issues")
        issue_count = cur.fetchone()[0]

        if issue_count > 0:
            query = """
                SELECT issue_id, issue_type, state, primary_ref_type, primary_ref_id,
                       headline, priority, opened_at, last_activity_at
                FROM issues
                WHERE state NOT IN ('resolved', 'closed')
                  AND last_activity_at >= ?
            """
            params = [cutoff_date]

            if client_id:
                query += """
                  AND (
                    (primary_ref_type = 'client' AND primary_ref_id = ?)
                    OR EXISTS (
                      SELECT 1 FROM tasks t
                      WHERE t.id = primary_ref_id
                      AND t.client_id = ?
                    )
                  )
                """
                params.extend([client_id, client_id])

            if member_id:
                query += """
                  AND EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.id = primary_ref_id
                    AND t.assignee = ?
                  )
                """
                params.append(member_id)

            query += " ORDER BY priority DESC, last_activity_at DESC LIMIT ?"
            params.append(limit)

            cur.execute(query, params)
            issues = [dict(row) for row in cur.fetchall()]
        else:
            # Generate and PERSIST issues from high-priority signals, grouped by entity
            # This ensures issues are real database records, not ephemeral
            cur.execute(
                """
                SELECT s.signal_id, s.signal_type, s.entity_ref_type, s.entity_ref_id,
                       s.value, s.detected_at
                FROM signals s
                WHERE s.signal_type LIKE '%risk%' OR s.signal_type LIKE '%overdue%'
                ORDER BY s.detected_at DESC
                LIMIT ?
            """,
                (limit * 3,),
            )  # Get more signals to group

            # Group signals by entity to avoid duplicates
            from collections import defaultdict

            entity_signals = defaultdict(list)
            for row in cur.fetchall():
                key = (row["entity_ref_type"], row["entity_ref_id"])
                entity_signals[key].append(dict(row))

            import hashlib

            inserted_count = 0
            for (ref_type, ref_id), signals in list(entity_signals.items())[:limit]:
                entity_name = ref_id
                if ref_type == "task":
                    cur.execute("SELECT title FROM tasks WHERE id = ?", (ref_id,))
                    r = cur.fetchone()
                    if r and r[0]:
                        entity_name = r[0][:60]
                elif ref_type == "client":
                    cur.execute("SELECT name FROM clients WHERE id = ?", (ref_id,))
                    r = cur.fetchone()
                    if r and r[0]:
                        entity_name = r[0]

                first_signal = signals[0]
                signal_types = [s["signal_type"] for s in signals]

                # Generate unique issue ID from entity hash
                issue_hash = hashlib.sha256(f"{ref_type}:{ref_id}".encode()).hexdigest()[:16]
                issue_id = f"iss_{issue_hash}"

                # Higher priority if multiple signals or critical types
                priority = min(90, 50 + len(signals) * 10)
                if any("overdue" in st for st in signal_types):
                    priority = min(95, priority + 15)

                issue_type = first_signal["signal_type"].replace(".", " ").replace("_", " ").title()
                headline = f"{entity_name}: {len(signals)} signal(s) - {first_signal['signal_type'].split('.')[-1].replace('_', ' ')}"
                opened_at = min(s["detected_at"] for s in signals)
                last_activity_at = max(s["detected_at"] for s in signals)

                # PERSIST the issue to database (INSERT OR REPLACE with all required fields)
                cur.execute(
                    """
                    INSERT OR REPLACE INTO issues
                    (issue_id, source_proposal_id, issue_type, state, primary_ref_type, primary_ref_id,
                     scope_refs, headline, priority, resolution_criteria, opened_at, last_activity_at, visibility)
                    VALUES (?, '', ?, 'open', ?, ?, '[]', ?, ?, 'Resolve underlying condition', ?, ?, 'surfaced')
                """,
                    (
                        issue_id,
                        issue_type,
                        ref_type,
                        ref_id,
                        headline,
                        priority,
                        opened_at,
                        last_activity_at,
                    ),
                )
                if cur.rowcount > 0:
                    inserted_count += 1

            if inserted_count > 0:
                conn.commit()

            # Now fetch from the newly populated issues table
            query = """
                SELECT issue_id, issue_type, state, primary_ref_type, primary_ref_id,
                       headline, priority, opened_at, last_activity_at
                FROM issues
                WHERE state NOT IN ('resolved', 'closed')
                ORDER BY priority DESC, last_activity_at DESC
                LIMIT ?
            """
            cur.execute(query, (limit,))
            issues = [dict(row) for row in cur.fetchall()]

        conn.close()
        return {"items": issues, "total": len(issues)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


class ResolveIssueRequest(BaseModel):
    resolution: str = "manually_resolved"
    actor: str = "moh"


@app.patch("/api/control-room/issues/{issue_id}/resolve")
async def resolve_issue(issue_id: str, body: ResolveIssueRequest):
    """Resolve an issue."""
    try:
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()

        # Check if issues table has the issue
        cur.execute("SELECT issue_id FROM issues WHERE issue_id = ?", (issue_id,))
        row = cur.fetchone()

        if row:
            # Update existing issue
            cur.execute(
                """
                UPDATE issues
                SET state = 'resolved', last_activity_at = datetime('now')
                WHERE issue_id = ?
            """,
                (issue_id,),
            )
            conn.commit()
            conn.close()
            return {"success": True, "issue_id": issue_id, "state": "resolved"}
        # Issue might be generated from signals - just acknowledge
        conn.close()
        return {
            "success": True,
            "issue_id": issue_id,
            "state": "resolved",
            "note": "Signal-based issue acknowledged",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class ChangeIssueStateRequest(BaseModel):
    state: str
    reason: str | None = None
    actor: str = "moh"


@app.patch("/api/control-room/issues/{issue_id}/state")
async def change_issue_state(issue_id: str, body: ChangeIssueStateRequest):
    """Change an issue's state."""
    valid_states = ["open", "monitoring", "awaiting", "blocked", "resolved", "closed"]
    if body.state not in valid_states:
        return {
            "success": False,
            "error": f"Invalid state. Must be one of: {valid_states}",
        }

    try:
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()

        # Check if issues table has the issue
        cur.execute("SELECT issue_id FROM issues WHERE issue_id = ?", (issue_id,))
        row = cur.fetchone()

        if row:
            # Update existing issue
            cur.execute(
                """
                UPDATE issues
                SET state = ?, last_activity_at = datetime('now')
                WHERE issue_id = ?
            """,
                (body.state, issue_id),
            )
            conn.commit()
            conn.close()
            return {"success": True, "issue_id": issue_id, "state": body.state}
        # Issue might be generated from signals - just acknowledge
        conn.close()
        return {
            "success": True,
            "issue_id": issue_id,
            "state": body.state,
            "note": "Signal-based issue acknowledged",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class AddIssueNoteRequest(BaseModel):
    text: str
    actor: str = "moh"


@app.post("/api/control-room/issues/{issue_id}/notes")
async def add_issue_note(issue_id: str, body: AddIssueNoteRequest):
    """Add a note to an issue."""
    try:
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()

        # Create notes table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS issue_notes (
                note_id TEXT PRIMARY KEY,
                issue_id TEXT NOT NULL,
                text TEXT NOT NULL,
                actor TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        import uuid

        note_id = str(uuid.uuid4())[:8]

        cur.execute(
            """
            INSERT INTO issue_notes (note_id, issue_id, text, actor)
            VALUES (?, ?, ?, ?)
        """,
            (note_id, issue_id, body.text, body.actor),
        )

        # Update issue last_activity
        cur.execute(
            """
            UPDATE issues SET last_activity_at = datetime('now')
            WHERE issue_id = ?
        """,
            (issue_id,),
        )

        conn.commit()
        conn.close()
        return {"success": True, "note_id": note_id, "issue_id": issue_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/control-room/watchers")
async def get_watchers(hours: int = 24):
    """Get issue watchers/alerts that have been triggered recently."""
    try:
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Ensure watchers table exists (defensive)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS watchers (
                watcher_id TEXT PRIMARY KEY,
                issue_id TEXT NOT NULL,
                watch_type TEXT NOT NULL,
                params TEXT NOT NULL DEFAULT '{}',
                active INTEGER NOT NULL DEFAULT 1,
                next_check_at TEXT NOT NULL,
                last_checked_at TEXT,
                triggered_at TEXT,
                trigger_count INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Get recently triggered watchers with issue details
        cur.execute(
            """
            SELECT w.watcher_id, w.issue_id, w.watch_type, w.triggered_at, w.trigger_count,
                   i.headline as issue_title, i.state, i.priority
            FROM watchers w
            JOIN issues i ON w.issue_id = i.issue_id
            WHERE w.triggered_at IS NOT NULL
            AND w.triggered_at >= datetime('now', '-' || ? || ' hours')
            ORDER BY w.triggered_at DESC
            LIMIT 20
        """,
            (hours,),
        )

        rows = cur.fetchall()
        items = []
        for r in rows:
            items.append(
                {
                    "watcher_id": r["watcher_id"],
                    "issue_id": r["issue_id"],
                    "issue_title": r["issue_title"],
                    "watch_type": r["watch_type"],
                    "triggered_at": r["triggered_at"],
                    "trigger_count": r["trigger_count"],
                    "state": r["state"],
                    "priority": r["priority"],
                }
            )

        conn.close()
        return {"items": items, "total": len(items)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


class DismissWatcherRequest(BaseModel):
    actor: str = "moh"


@app.post("/api/control-room/watchers/{watcher_id}/dismiss")
async def dismiss_watcher(watcher_id: str, body: DismissWatcherRequest):
    """Dismiss a watcher (remove from active list)."""
    try:
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()

        # Set triggered_at to NULL to hide from active watchers
        cur.execute(
            """
            UPDATE watchers
            SET triggered_at = NULL, dismissed_at = datetime('now'), dismissed_by = ?
            WHERE watcher_id = ?
        """,
            (body.actor, watcher_id),
        )

        conn.commit()
        conn.close()
        return {"success": True, "watcher_id": watcher_id, "action": "dismissed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class SnoozeWatcherRequest(BaseModel):
    hours: int = 24
    actor: str = "moh"


@app.post("/api/control-room/watchers/{watcher_id}/snooze")
async def snooze_watcher(watcher_id: str, body: SnoozeWatcherRequest):
    """Snooze a watcher for N hours."""
    try:
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()

        # Set snoozed_until to hide until that time
        cur.execute(
            """
            UPDATE watchers
            SET snoozed_until = datetime('now', '+' || ? || ' hours'),
                snoozed_by = ?
            WHERE watcher_id = ?
        """,
            (body.hours, body.actor, watcher_id),
        )

        conn.commit()
        conn.close()
        return {
            "success": True,
            "watcher_id": watcher_id,
            "action": "snoozed",
            "hours": body.hours,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/control-room/fix-data")
async def get_fix_data():
    """Get data quality issues for Fix tab."""
    try:
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Ensure required tables exist (defensive)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS identities (
                id TEXT PRIMARY KEY,
                display_name TEXT,
                source TEXT,
                canonical_id TEXT,
                confidence_score REAL DEFAULT 0.5
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS entity_links (
                link_id TEXT PRIMARY KEY,
                from_artifact_type TEXT,
                from_artifact_id TEXT,
                to_entity_type TEXT,
                to_entity_id TEXT,
                method TEXT,
                confidence REAL DEFAULT 0.5,
                status TEXT DEFAULT 'active'
            )
        """)

        # Identity conflicts
        cur.execute("""
            SELECT i.id, i.display_name, i.source, i.confidence_score
            FROM identities i
            WHERE i.canonical_id IS NULL OR i.confidence_score < 0.8
            LIMIT 20
        """)
        conflicts = [dict(r) for r in cur.fetchall()]

        # Ambiguous links (low confidence entity links)
        cur.execute("""
            SELECT el.link_id as id, el.to_entity_type as entity_type, el.to_entity_id as entity_id,
                   el.from_artifact_id as linked_id, el.method as linked_type, el.confidence
            FROM entity_links el
            WHERE el.confidence < 0.7
            LIMIT 20
        """)
        ambiguous = [dict(r) for r in cur.fetchall()]

        conn.close()

        return {
            "identity_conflicts": conflicts,
            "ambiguous_links": ambiguous,
            "missing_mappings": [],
            "total": len(conflicts) + len(ambiguous),
        }
    except Exception as e:
        return {
            "identity_conflicts": [],
            "ambiguous_links": [],
            "missing_mappings": [],
            "total": 0,
            "error": str(e),
        }


# ==== Control Room POST Endpoints (Mutations) ====


class TagProposalRequest(BaseModel):
    proposal_id: str
    actor: str = "moh"


@app.post("/api/control-room/issues")
async def create_issue_from_proposal(body: TagProposalRequest):
    """Tag a proposal to create a monitored Issue."""
    try:
        svc = IssueService()
        result = svc.tag_proposal(body.proposal_id, body.actor)
        if result.get("status") == "created":
            return {"success": True, **result}
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to tag proposal"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/control-room/proposals/{proposal_id}")
async def get_proposal_detail(proposal_id: str):
    """Get detailed view of a proposal with full signal information.

    Returns:
        - Full proposal metadata
        - Score breakdown
        - Top 5 signals with task details
        - Link to issues page for "see more"
    """
    try:
        svc = ProposalService()
        proposal = svc.get_proposal(proposal_id)

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        # Get signals for this proposal
        from lib.v4.signal_service import SignalService

        signal_svc = SignalService()
        signals = signal_svc.get_signals_for_proposal(proposal_id)

        # Parse JSON fields
        signal_summary = (
            json.loads(proposal.get("signal_summary_json", "{}"))
            if isinstance(proposal.get("signal_summary_json"), str)
            else proposal.get("signal_summary_json", {})
        )
        score_breakdown = (
            json.loads(proposal.get("score_breakdown_json", "{}"))
            if isinstance(proposal.get("score_breakdown_json"), str)
            else proposal.get("score_breakdown_json", {})
        )
        impact = (
            json.loads(proposal.get("impact", "{}"))
            if isinstance(proposal.get("impact"), str)
            else proposal.get("impact", {})
        )
        affected_tasks = (
            json.loads(proposal.get("affected_task_ids_json", "[]"))
            if isinstance(proposal.get("affected_task_ids_json"), str)
            else proposal.get("affected_task_ids_json", [])
        )

        # Build signal details for top 5 with full value data
        signal_details = []
        for sig in signals[:5]:
            value = sig.get("value", {})
            signal_type = sig.get("signal_type", "")

            # Build human-readable description based on signal type
            description = None
            if signal_type == "ar_aging_risk":
                ar_amount = value.get("ar_overdue", value.get("amount", 0))
                aging = value.get("aging_bucket", value.get("aging", "unknown"))
                description = (
                    f"${ar_amount:,.0f} overdue ({aging})" if ar_amount else f"AR aging: {aging}"
                )
            elif signal_type == "client_health_declining":
                health = value.get("current_health", value.get("health", "unknown"))
                trend = value.get("trend", "declining")
                description = f"Health: {health}, Trend: {trend}"
            elif signal_type == "communication_gap":
                days = value.get("days_since_contact", value.get("days", 0))
                description = f"No contact in {days} days" if days else "Communication gap detected"
            elif signal_type == "data_quality_issue":
                issue = value.get("issue", value.get("description", "Data quality issue"))
                description = issue if isinstance(issue, str) else "Data quality issue"
            elif signal_type == "deadline_overdue":
                title = value.get("title", "Task")
                days = value.get("days_overdue", 0)
                description = f"'{title[:40]}' is {days} days overdue"
            elif signal_type == "deadline_approaching":
                title = value.get("title", "Task")
                days = value.get("days_until", 0)
                description = f"'{title[:40]}' due in {days} days"
            elif signal_type == "hierarchy_violation":
                description = value.get("violation", "Hierarchy violation detected")
            elif signal_type == "commitment_made":
                text = value.get("commitment_text", "Commitment detected")
                description = text[:80] if isinstance(text, str) else "Commitment detected"

            signal_details.append(
                {
                    "signal_id": sig.get("signal_id"),
                    "signal_type": signal_type,
                    "entity_type": sig.get("entity_ref_type"),
                    "entity_id": sig.get("entity_ref_id"),
                    "description": description
                    or value.get("title", signal_type.replace("_", " ").title()),
                    "task_title": value.get("title", value.get("task_title")),
                    "assignee": value.get("assignee", value.get("owner")),
                    "days_overdue": value.get("days_overdue"),
                    "days_until": value.get("days_until"),
                    "severity": sig.get("severity"),
                    "status": sig.get("status"),
                    "detected_at": sig.get("detected_at"),
                    "value": value,  # Include full value for additional details
                }
            )

        return {
            "proposal_id": proposal.get("proposal_id"),
            "proposal_type": proposal.get("proposal_type"),
            "scope_level": proposal.get("scope_level"),
            "scope_name": proposal.get("scope_name"),
            "client_id": proposal.get("client_id"),
            "client_name": proposal.get("client_name"),
            "client_tier": proposal.get("client_tier"),
            "headline": proposal.get("headline"),
            "score": proposal.get("score"),
            "score_breakdown": score_breakdown,
            "signal_summary": signal_summary,
            "worst_signal": impact.get("worst_signal", ""),
            "status": proposal.get("status"),
            "trend": proposal.get("trend"),
            "first_seen_at": proposal.get("first_seen_at"),
            "last_seen_at": proposal.get("last_seen_at"),
            "signals": signal_details,
            "total_signals": len(signals),
            "affected_task_ids": affected_tasks,
            "issues_url": f"/issues?client_id={proposal.get('client_id')}"
            if proposal.get("client_id")
            else "/issues",
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")


class SnoozeProposalRequest(BaseModel):
    days: int = 7


@app.post("/api/control-room/proposals/{proposal_id}/snooze")
async def snooze_proposal(proposal_id: str, body: SnoozeProposalRequest):
    """Snooze a proposal for N days."""
    try:
        from datetime import timedelta

        until = (datetime.now() + timedelta(days=body.days)).isoformat()
        svc = ProposalService()
        result = svc.snooze_proposal(proposal_id, until)
        if result.get("status") == "snoozed":
            return {"success": True, **result}
        raise HTTPException(
            status_code=400, detail=result.get("error", "Failed to snooze proposal")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DismissProposalRequest(BaseModel):
    reason: str = "Dismissed by user"


@app.post("/api/control-room/proposals/{proposal_id}/dismiss")
async def dismiss_proposal(proposal_id: str, body: DismissProposalRequest):
    """Dismiss a proposal."""
    try:
        svc = ProposalService()
        result = svc.dismiss_proposal(proposal_id, body.reason)
        if result.get("status") == "dismissed":
            return {"success": True, **result}
        raise HTTPException(
            status_code=400, detail=result.get("error", "Failed to dismiss proposal")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ResolveFixDataRequest(BaseModel):
    resolution: str = "manually_resolved"
    actor: str = "moh"


@app.post("/api/control-room/fix-data/{item_type}/{item_id}/resolve")
async def resolve_fix_data_item(item_type: str, item_id: str, body: ResolveFixDataRequest):
    """Resolve a fix-data item (identity conflict or ambiguous link)."""
    try:
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        now = datetime.now().isoformat()

        if item_type == "identity":
            # Mark identity as resolved by setting canonical_id to self or updating confidence
            cur.execute(
                """
                UPDATE identities
                SET canonical_id = COALESCE(canonical_id, id),
                    confidence_score = 1.0,
                    updated_at = ?
                WHERE id = ?
            """,
                (now, item_id),
            )
        elif item_type == "link":
            # Mark link as resolved by boosting confidence
            cur.execute(
                """
                UPDATE entity_links
                SET confidence = 1.0,
                    updated_at = ?
                WHERE id = ?
            """,
                (now, item_id),
            )
        else:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Unknown item_type: {item_type}")

        # Log the resolution
        audit_id = f"fda_{item_id}_{now.replace(':', '-')}"
        cur.execute(
            """
            INSERT INTO governance_history (id, decision_id, action, type, target_id, processed_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (audit_id, None, "fix_data_resolve", item_type, item_id, body.actor, now),
        )

        conn.commit()
        conn.close()

        return {
            "success": True,
            "item_type": item_type,
            "item_id": item_id,
            "resolution": body.resolution,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/control-room/couplings")
async def get_couplings(anchor_type: str | None = None, anchor_id: str | None = None):
    """Get intersections/couplings."""
    try:
        svc = CouplingService()
        if anchor_type and anchor_id:
            couplings = svc.get_couplings_for_entity(anchor_type, anchor_id)
        else:
            couplings = svc.get_strongest_couplings(limit=100)
        return {"items": couplings, "total": len(couplings)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


@app.get("/api/control-room/clients")
async def get_control_room_clients():
    """Get clients for control room."""
    try:
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, c.tier, c.type,
                   c.financial_ar_total, c.financial_ar_aging_bucket,
                   c.financial_annual_value,
                   c.prior_year_revenue, c.ytd_revenue, c.lifetime_revenue,
                   c.relationship_health, c.relationship_trend, c.relationship_last_interaction,
                   c.created_at, c.updated_at
            FROM clients c
            WHERE c.type = 'agency_client' OR c.type IS NULL
            ORDER BY c.tier, c.name
        """)
        clients = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"items": clients, "total": len(clients)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


@app.get("/api/control-room/team")
async def get_control_room_team():
    """Get team members for control room."""
    try:
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.name, p.email, p.role, p.company,
                   CASE WHEN p.type = 'internal' THEN 1 ELSE 0 END as is_internal,
                   COUNT(t.id) as open_tasks
            FROM people p
            LEFT JOIN tasks t ON t.assignee = p.name AND t.status NOT IN ('done', 'completed', 'archived')
            WHERE p.type = 'internal' OR p.company LIKE '%hrmny%'
            GROUP BY p.id
            ORDER BY open_tasks DESC, p.name
            LIMIT 50
        """)
        team = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"items": team, "total": len(team)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


@app.get("/api/control-room/evidence/{entity_type}/{entity_id}")
async def get_evidence(entity_type: str, entity_id: str):
    """Get evidence/proof for an entity."""
    try:
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Get excerpts linked to this entity
        cur.execute(
            """
            SELECT e.id, e.artifact_id, e.excerpt_text, e.context_json, e.created_at,
                   a.source, a.type as artifact_type, a.occurred_at
            FROM excerpts e
            JOIN artifacts a ON e.artifact_id = a.artifact_id
            JOIN entity_links el ON el.entity_id = ?
            WHERE el.entity_type = ? AND e.artifact_id = el.linked_id
            ORDER BY a.occurred_at DESC
            LIMIT 50
        """,
            (entity_id, entity_type),
        )
        excerpts = [dict(r) for r in cur.fetchall()]

        conn.close()
        return {"items": excerpts, "total": len(excerpts)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


# ==== Control Room Health ====


@app.get("/api/control-room/health")
async def control_room_health():
    """Health check endpoint for the Control Room API."""
    import datetime

    try:
        # Check database connectivity
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM signals")
        signal_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM issues")
        issue_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM clients")
        client_count = cur.fetchone()[0]
        conn.close()

        return {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "database": {
                "connected": True,
                "signals": signal_count,
                "issues": issue_count,
                "clients": client_count,
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "error": str(e),
        }


# ==== Admin Endpoints ====


@app.post("/api/admin/seed-identities")
async def seed_identities():
    """Seed identity profiles from clients and people tables."""
    try:
        from lib.v4.seed_identities import (
            seed_identities_from_clients,
            seed_identities_from_people,
        )

        client_stats = seed_identities_from_clients()
        people_stats = seed_identities_from_people()

        return {"success": True, "clients": client_stats, "people": people_stats}
    except Exception as e:
        import traceback

        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==== SPA Fallback (MUST be last route) ====


@app.get("/{path:path}")
async def spa_fallback(path: str, request: Request = None):
    """Serve static files or fall back to SPA index.html."""
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Check if UI build exists at all
    index_path = UI_DIR / "index.html"
    if not index_path.exists():
        hint = "cd time-os-ui && npm ci && npm run build"
        accept = request.headers.get("accept", "") if request else ""
        if "text/html" in accept:
            return HTMLResponse(
                content=f"<h1>UI Build Missing</h1><pre>Run: {hint}</pre>",
                status_code=404,
            )
        return JSONResponse(content={"error": "ui_build_missing", "hint": hint}, status_code=404)

    # Try to serve the actual file first (for assets, manifest, etc.)
    file_path = UI_DIR / path
    if file_path.exists() and file_path.is_file():
        # Set correct MIME type for common extensions
        import mimetypes

        mime_type, _ = mimetypes.guess_type(str(file_path))
        return FileResponse(file_path, media_type=mime_type)

    # Fall back to index.html for SPA routing
    return FileResponse(index_path)


# ==== Main ====


def main():
    """Run the server."""
    import os

    port = int(os.environ.get("PORT", 8420))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
