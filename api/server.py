"""
MOH TIME OS API Server - REST API for dashboard and integrations.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from typing import Optional
import json
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from lib.state_store import get_store
from lib.collectors import CollectorOrchestrator
from lib.analyzers import AnalyzerOrchestrator
from lib.governance import get_governance, DomainMode
from lib.autonomous_loop import AutonomousLoop
from lib.change_bundles import (
    create_task_bundle, create_bundle, mark_applied, mark_failed,
    get_bundle, rollback_bundle, list_bundles, list_rollbackable_bundles
)
from lib.calibration import CalibrationEngine


# FastAPI app initialization
app = FastAPI(
    title="MOH TIME OS API",
    description="Personal Operating System API - Direct control without AI",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Global instances
store = get_store()
collectors = CollectorOrchestrator(store=store)
analyzers = AnalyzerOrchestrator(store=store)
governance = get_governance(store=store)

# UI directory
UI_DIR = Path(__file__).parent.parent / "ui"


# Root endpoint
@app.get("/")
async def root():
    """Serve the dashboard UI."""
    return FileResponse(UI_DIR / "index.html")


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
    priority_queue = analyzers.priority_analyzer.analyze() if hasattr(analyzers, 'priority_analyzer') else []
    top_priorities = sorted(priority_queue, key=lambda x: x.get('score', 0), reverse=True)[:5]
    
    # Get today's events
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    events = store.query(
        "SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time",
        [today]
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
        "priorities": {
            "items": top_priorities,
            "total": len(priority_queue)
        },
        "calendar": {
            "events": [dict(e) for e in events],
            "event_count": len(events)
        },
        "decisions": {
            "pending": [dict(d) for d in pending_decisions],
            "pending_count": store.count("decisions", "approved IS NULL")
        },
        "anomalies": {
            "items": [dict(a) for a in anomalies],
            "total": store.count("insights", "type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now'))")
        },
        "sync_status": collectors.get_status()
    }


# ==== Time Endpoints ====

@app.get("/api/time/blocks")
async def get_time_blocks(date: Optional[str] = None, lane: Optional[str] = None):
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
            "is_available": block.is_available
        }
        
        if block.task_id:
            task = store.get("tasks", block.task_id)
            if task:
                block_dict["task_title"] = task.get("title", "")
                block_dict["task_status"] = task.get("status", "")
        
        result.append(block_dict)
    
    return {"date": date, "blocks": result, "total": len(result)}


@app.get("/api/time/summary")
async def get_time_summary(date: Optional[str] = None):
    """Get time summary for a date."""
    from datetime import date as dt
    from lib.time_truth import CalendarSync, Scheduler
    
    if not date:
        date = dt.today().isoformat()
    
    cs = CalendarSync(store)
    scheduler = Scheduler(store)
    
    day_summary = cs.get_day_summary(date)
    scheduling_summary = scheduler.get_scheduling_summary(date)
    
    return {
        "date": date,
        "time": day_summary,
        "scheduling": scheduling_summary
    }


@app.get("/api/time/brief")
async def get_time_brief(date: Optional[str] = None, format: str = "markdown"):
    """Get a brief time overview."""
    from datetime import date as dt
    from lib.time_truth import generate_time_brief
    
    if not date:
        date = dt.today().isoformat()
    
    brief = generate_time_brief(date, format)
    return {"date": date, "brief": brief}


@app.post("/api/time/schedule")
async def schedule_task(task_id: str, block_id: Optional[str] = None, date: Optional[str] = None):
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
        "block_id": result.block_id
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
async def get_commitments(status: Optional[str] = None, limit: int = 50):
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
                "created_at": c.created_at
            }
            for c in commitments
        ],
        "total": len(commitments)
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
                "source_type": c.source_type
            }
            for c in commitments
        ],
        "total": len(commitments)
    }


@app.get("/api/commitments/due")
async def get_commitments_due(date: Optional[str] = None):
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
                "task_id": c.task_id
            }
            for c in commitments
        ],
        "total": len(commitments)
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
async def get_capacity_utilization(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Get capacity utilization metrics."""
    from datetime import date, timedelta
    from lib.time_truth import CalendarSync
    
    if not start_date:
        start_date = date.today().isoformat()
    if not end_date:
        end_date = (date.today() + timedelta(days=7)).isoformat()
    
    cs = CalendarSync(store)
    utilization = cs.get_utilization(start_date, end_date)
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "utilization": utilization
    }


@app.get("/api/capacity/forecast")
async def get_capacity_forecast(days: int = 7):
    """Get capacity forecast for upcoming days."""
    from datetime import date, timedelta
    from lib.time_truth import Scheduler
    
    scheduler = Scheduler(store)
    forecasts = []
    
    for i in range(days):
        day = date.today() + timedelta(days=i)
        forecast = scheduler.get_day_forecast(day.isoformat())
        forecasts.append(forecast)
    
    return {"days": days, "forecasts": forecasts}


@app.get("/api/capacity/debt")
async def get_capacity_debt(lane: Optional[str] = None):
    """Get capacity debt (overcommitments)."""
    from lib.time_truth import get_capacity_debt
    
    debt = get_capacity_debt(store, lane=lane)
    return debt


@app.post("/api/capacity/debt/accrue")
async def accrue_debt(hours: Optional[float] = None):
    """Record accrued capacity debt."""
    from lib.time_truth import accrue_capacity_debt
    
    result = accrue_capacity_debt(store, hours=hours)
    return result


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
    clients = store.query("""
        SELECT * FROM clients 
        ORDER BY 
            CASE relationship_health 
                WHEN 'critical' THEN 1 
                WHEN 'poor' THEN 2 
                WHEN 'needs_attention' THEN 3 
                ELSE 4 
            END,
            tier
        LIMIT ?
    """, [limit])
    
    return {
        "clients": [dict(c) for c in clients],
        "total": len(clients)
    }


@app.get("/api/clients/at-risk")
async def get_at_risk_clients(limit: int = 50):
    """Get clients that are at risk."""
    clients = store.query("""
        SELECT * FROM clients 
        WHERE relationship_health IN ('poor', 'critical')
           OR (financial_ar_outstanding > 50000 AND financial_ar_aging IN ('60+', '90+'))
        ORDER BY 
            CASE relationship_health WHEN 'critical' THEN 1 WHEN 'poor' THEN 2 ELSE 3 END,
            financial_ar_outstanding DESC
        LIMIT ?
    """, [limit])
    
    return {
        "clients": [dict(c) for c in clients],
        "total": len(clients)
    }


@app.get("/api/clients/{client_id}/health")
async def get_client_health(client_id: str):
    """Get detailed health for a specific client."""
    client = store.get("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return dict(client)


@app.get("/api/clients/{client_id}/projects")
async def get_client_projects(client_id: str):
    """Get projects for a client."""
    projects = store.query(
        "SELECT * FROM projects WHERE client_id = ? ORDER BY updated_at DESC",
        [client_id]
    )
    return {"client_id": client_id, "projects": [dict(p) for p in projects]}


@app.post("/api/clients/link")
async def link_project_to_client(project_id: str, client_id: str):
    """Link a project to a client."""
    store.update("projects", project_id, {"client_id": client_id, "updated_at": datetime.now().isoformat()})
    return {"success": True, "project_id": project_id, "client_id": client_id}


@app.get("/api/clients/linking-stats")
async def get_linking_stats():
    """Get statistics about project-client linking."""
    total_projects = store.count("projects", "1=1")
    linked = store.count("projects", "client_id IS NOT NULL")
    unlinked = total_projects - linked
    
    return {
        "total_projects": total_projects,
        "linked": linked,
        "unlinked": unlinked,
        "link_rate": linked / total_projects if total_projects > 0 else 0
    }


# ==== Tasks Endpoints ====

@app.get("/api/tasks")
async def get_tasks(status: Optional[str] = None, project: Optional[str] = None, assignee: Optional[str] = None, limit: int = 50):
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
    
    tasks = store.query(f"""
        SELECT * FROM tasks 
        WHERE {' AND '.join(conditions)}
        ORDER BY priority DESC, due_date ASC
        LIMIT ?
    """, params)
    
    return {
        "tasks": [dict(t) for t in tasks],
        "total": len(tasks)
    }


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[int] = 50
    tags: Optional[str] = None
    source: Optional[str] = "api"
    status: Optional[str] = "pending"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    project: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    tags: Optional[str] = None


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
        "updated_at": now
    }
    
    bundle = create_task_bundle(
        f"Create task: {task.title[:50]}",
        [{"id": task_id, "type": "create", **task_data}],
        {}
    )
    
    try:
        store.insert("tasks", task_data)
        mark_applied(bundle["id"])
        return {"success": True, "task": task_data, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, task: TaskUpdate):
    """Update a task."""
    existing = store.get("tasks", task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = {k: v for k, v in task.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now().isoformat()
    
    bundle = create_task_bundle(
        f"Update task: {existing.get('title', '')[:50]}",
        [{"id": task_id, "type": "update", **update_data}],
        {task_id: dict(existing)}
    )
    
    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])
        return {"success": True, "id": task_id, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


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
    except:
        notes = []
    
    notes.append({
        "text": body.note,
        "created_at": datetime.now().isoformat()
    })
    
    store.update("tasks", task_id, {
        "notes": json.dumps(notes),
        "updated_at": datetime.now().isoformat()
    })
    
    return {"success": True, "notes": notes}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete (archive) a task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    bundle = create_task_bundle(
        f"Delete task: {task.get('title', '')[:50]}",
        [{"id": task_id, "type": "delete"}],
        {task_id: dict(task)}
    )
    
    try:
        store.update("tasks", task_id, {"status": "deleted", "updated_at": datetime.now().isoformat()})
        mark_applied(bundle["id"])
        return {"success": True, "id": task_id, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==== Delegation Endpoints ====

class DelegateRequest(BaseModel):
    to: str
    note: Optional[str] = None
    due_date: Optional[str] = None


class EscalateRequest(BaseModel):
    to: str
    reason: Optional[str] = None


@app.post("/api/tasks/{task_id}/delegate")
async def delegate_task(task_id: str, body: DelegateRequest):
    """Delegate a task to someone."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    now = datetime.now().isoformat()
    update_data = {
        "assignee": body.to,
        "delegated_by": "moh",
        "delegated_at": now,
        "delegated_note": body.note,
        "updated_at": now
    }
    
    if body.due_date:
        update_data["due_date"] = body.due_date
    
    bundle = create_task_bundle(
        f"Delegate to {body.to}: {task.get('title', '')[:50]}",
        [{"id": task_id, **update_data}],
        {task_id: {"assignee": task.get("assignee"), "delegated_by": task.get("delegated_by")}}
    )
    
    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])
        return {"success": True, "id": task_id, "delegated_to": body.to, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/{task_id}/escalate")
async def escalate_task(task_id: str, body: EscalateRequest):
    """Escalate a task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    now = datetime.now().isoformat()
    update_data = {
        "escalated_to": body.to,
        "escalated_at": now,
        "escalation_reason": body.reason,
        "priority": min(100, (task.get("priority") or 50) + 20),
        "updated_at": now
    }
    
    bundle = create_task_bundle(
        f"Escalate to {body.to}: {task.get('title', '')[:50]}",
        [{"id": task_id, **update_data}],
        {task_id: {"escalated_to": task.get("escalated_to"), "priority": task.get("priority")}}
    )
    
    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])
        return {"success": True, "id": task_id, "escalated_to": body.to, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


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
        "updated_at": now
    }
    
    bundle = create_task_bundle(
        f"Recall task: {task.get('title', '')[:50]}",
        [{"id": task_id, **update_data}],
        {task_id: {"assignee": task.get("assignee"), "delegated_by": task.get("delegated_by")}}
    )
    
    try:
        store.update("tasks", task_id, update_data)
        mark_applied(bundle["id"])
        return {"success": True, "id": task_id, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/delegations")
async def get_delegations():
    """Get all delegated tasks."""
    delegated = store.query("""
        SELECT * FROM tasks 
        WHERE assignee IS NOT NULL AND assignee != '' 
        AND status NOT IN ('completed', 'done', 'cancelled', 'deleted')
        ORDER BY delegated_at DESC
    """)
    
    return {
        "delegations": [dict(t) for t in delegated],
        "total": len(delegated)
    }


# ==== Data Quality Endpoints ====

@app.get("/api/data-quality")
async def get_data_quality():
    """Get data quality metrics and cleanup suggestions."""
    # Get task statistics
    total_tasks = store.count("tasks", "1=1")
    pending_tasks = store.count("tasks", "status = 'pending'")
    completed_tasks = store.count("tasks", "status IN ('completed', 'done')")
    
    # Ancient tasks (>30 days overdue)
    ancient = store.query("""
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-30 days')
    """)
    ancient_count = ancient[0]["cnt"] if ancient else 0
    
    # Stale tasks (14-30 days overdue)
    stale = store.query("""
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-14 days')
          AND date(due_date) >= date('now', '-30 days')
    """)
    stale_count = stale[0]["cnt"] if stale else 0
    
    # Overdue
    overdue = store.query("""
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now')
    """)
    overdue_count = overdue[0]["cnt"] if overdue else 0
    
    # Tasks without due dates
    no_due_date = store.query("""
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status = 'pending' AND (due_date IS NULL OR due_date = '')
    """)
    no_due_count = no_due_date[0]["cnt"] if no_due_date else 0
    
    # Orphaned tasks (no project)
    orphaned = store.query("""
        SELECT COUNT(*) as cnt FROM tasks
        WHERE status = 'pending' AND (project IS NULL OR project = '')
    """)
    orphaned_count = orphaned[0]["cnt"] if orphaned else 0
    
    suggestions = _get_cleanup_suggestions(store)
    
    return {
        "statistics": {
            "total_tasks": total_tasks,
            "pending": pending_tasks,
            "completed": completed_tasks,
            "ancient": ancient_count,
            "stale": stale_count,
            "overdue": overdue_count,
            "no_due_date": no_due_count,
            "orphaned": orphaned_count
        },
        "health_score": max(0, 100 - (ancient_count * 5) - (stale_count * 2) - (overdue_count * 1)),
        "suggestions": suggestions
    }


def _get_cleanup_suggestions(store) -> list:
    """Generate cleanup suggestions based on data quality issues."""
    suggestions = []
    
    # Check for ancient tasks
    ancient = store.query("""
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-30 days')
        LIMIT 5
    """)
    if ancient:
        suggestions.append({
            "type": "ancient_tasks",
            "severity": "high",
            "message": f"Found {len(ancient)} tasks overdue by more than 30 days",
            "action": "/api/data-quality/cleanup/ancient",
            "sample": [dict(t) for t in ancient]
        })
    
    # Check for stale tasks
    stale = store.query("""
        SELECT id, title FROM tasks
        WHERE status NOT IN ('completed', 'done', 'cancelled', 'deleted')
          AND due_date IS NOT NULL
          AND date(due_date) < date('now', '-14 days')
          AND date(due_date) >= date('now', '-30 days')
        LIMIT 5
    """)
    if stale:
        suggestions.append({
            "type": "stale_tasks",
            "severity": "medium",
            "message": f"Found {len(stale)} tasks overdue by 14-30 days",
            "action": "/api/data-quality/cleanup/stale",
            "sample": [dict(t) for t in stale]
        })
    
    return suggestions


class CleanupRequest(BaseModel):
    task_ids: Optional[list] = None
    dry_run: Optional[bool] = False


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
            "confirm_endpoint": "/api/data-quality/cleanup/ancient?confirm=true"
        }
    
    bundle = create_task_bundle(
        f"Bulk archive {len(tasks)} ancient tasks",
        [{"id": t["id"], "type": "archive"} for t in tasks],
        {t["id"]: {"status": "pending"} for t in tasks}
    )
    
    for task in tasks:
        store.update("tasks", task["id"], {"status": "archived", "updated_at": datetime.now().isoformat()})
    
    mark_applied(bundle["id"])
    
    return {
        "success": True,
        "archived_count": len(tasks),
        "bundle_id": bundle["id"]
    }


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
            "confirm_endpoint": "/api/data-quality/cleanup/stale?confirm=true"
        }
    
    from lib.change_bundles import create_task_bundle, mark_applied
    
    bundle = create_task_bundle(
        f"Bulk archive {len(tasks)} stale tasks",
        [{"id": t["id"], "type": "archive"} for t in tasks],
        {t["id"]: {"status": "pending"} for t in tasks}
    )
    
    for task in tasks:
        store.update("tasks", task["id"], {"status": "archived", "updated_at": datetime.now().isoformat()})
    
    mark_applied(bundle["id"])
    
    return {
        "success": True,
        "archived_count": len(tasks),
        "bundle_id": bundle["id"]
    }


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
            store.update("tasks", task["id"], {
                "priority": new_priority,
                "updated_at": datetime.now().isoformat()
            })
            updated += 1
    
    return {
        "success": True,
        "tasks_updated": updated,
        "total_tasks": len(tasks),
        "message": f"Recalculated priorities for {updated} tasks"
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
        except:
            pass
    
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
        "total": len(tasks)
    }


# ==== Team Endpoints ====

@app.get("/api/team")
async def get_team():
    """Get team members."""
    people = store.query("SELECT * FROM people ORDER BY name")
    
    result = []
    for p in people:
        person = dict(p)
        # Count delegated tasks
        delegated = store.count("tasks", f"assignee = '{p['name']}' AND status = 'pending'")
        person["delegated_tasks"] = delegated
        result.append(person)
    
    return {"team": result, "total": len(result)}


@app.get("/api/projects")
async def get_projects(client_id: Optional[str] = None, include_archived: bool = False, limit: int = 50):
    """Get projects list."""
    conditions = ["1=1"]
    params = []
    
    if client_id:
        conditions.append("client_id = ?")
        params.append(client_id)
    
    if not include_archived:
        conditions.append("enrollment_status != 'archived'")
    
    params.append(limit)
    
    projects = store.query(f"""
        SELECT * FROM projects 
        WHERE {' AND '.join(conditions)}
        ORDER BY updated_at DESC
        LIMIT ?
    """, params)
    
    return {"projects": [dict(p) for p in projects], "total": len(projects)}


# Additional imports for calendar
from datetime import datetime, timedelta


@app.get("/api/calendar")
async def api_calendar(start_date: Optional[str] = None, end_date: Optional[str] = None, view: str = "week"):
    """Get calendar events."""
    from datetime import date, timedelta
    
    if not start_date:
        start_date = date.today().isoformat()
    if not end_date:
        if view == "week":
            end_date = (date.today() + timedelta(days=7)).isoformat()
        else:
            end_date = (date.today() + timedelta(days=1)).isoformat()
    
    events = store.query("""
        SELECT * FROM events 
        WHERE date(start_time) >= ? AND date(start_time) <= ?
        ORDER BY start_time
    """, [start_date, end_date])
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "events": [dict(e) for e in events],
        "total": len(events)
    }


@app.get("/api/delegations")
async def api_delegations():
    """Get delegated tasks (alias)."""
    return await get_delegations()


@app.get("/api/inbox")
async def api_inbox(limit: int = 50):
    """Get inbox items (unprocessed communications, new tasks, etc.)."""
    items = store.query("""
        SELECT * FROM communications 
        WHERE processed = 0 OR processed IS NULL
        ORDER BY received_at DESC
        LIMIT ?
    """, [limit])
    
    return {"items": [dict(i) for i in items], "total": len(items)}


@app.get("/api/insights")
async def api_insights(limit: int = 20):
    """Get insights."""
    insights = store.query("""
        SELECT * FROM insights 
        WHERE expires_at IS NULL OR expires_at > datetime('now')
        ORDER BY created_at DESC
        LIMIT ?
    """, [limit])
    
    return {"insights": [dict(i) for i in insights], "total": len(insights)}


@app.get("/api/decisions")
async def api_decisions(limit: int = 20):
    """Get pending decisions."""
    decisions = store.query("""
        SELECT * FROM decisions 
        WHERE approved IS NULL
        ORDER BY created_at DESC
        LIMIT ?
    """, [limit])
    
    return {"decisions": [dict(d) for d in decisions], "total": len(decisions)}


@app.post("/api/priorities/{item_id}/complete")
async def api_priority_complete(item_id: str):
    """Complete a priority item (task)."""
    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    now = datetime.now().isoformat()
    bundle = create_task_bundle(
        f"Complete: {task.get('title', '')[:50]}",
        [{"id": item_id, "status": "completed", "completed_at": now}],
        {item_id: {"status": task.get("status")}}
    )
    
    try:
        store.update("tasks", item_id, {"status": "completed", "completed_at": now, "updated_at": now})
        mark_applied(bundle["id"])
        return {"success": True, "id": item_id, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/priorities/{item_id}/snooze")
async def api_priority_snooze(item_id: str, days: int = 1):
    """Snooze a priority item."""
    from datetime import timedelta
    
    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    now = datetime.now().isoformat()
    
    bundle = create_task_bundle(
        f"Snooze {days}d: {task.get('title', '')[:50]}",
        [{"id": item_id, "due_date": new_date}],
        {item_id: {"due_date": task.get("due_date")}}
    )
    
    try:
        store.update("tasks", item_id, {"due_date": new_date, "snoozed_at": now, "updated_at": now})
        mark_applied(bundle["id"])
        return {"success": True, "id": item_id, "new_due_date": new_date, "bundle_id": bundle["id"]}
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
    
    can_exec, reason = governance.can_execute("delegation", "delegate", {
        "task_id": item_id,
        "to": to,
        "confidence": 1.0
    })
    
    now_iso = datetime.now().isoformat()
    update_data = {
        "assignee_id": person[0]["id"],
        "assignee_name": person[0]["name"],
        "delegated_by": "moh",
        "delegated_at": now_iso,
        "updated_at": now_iso
    }
    
    bundle = create_task_bundle(
        f"Delegate to {to}: {task[0]['title'][:50]}",
        [{"id": item_id, **update_data}],
        {item_id: {
            "assignee_id": task[0].get("assignee_id"),
            "assignee_name": task[0].get("assignee_name"),
            "delegated_by": task[0].get("delegated_by"),
            "delegated_at": task[0].get("delegated_at")
        }}
    )
    
    if not can_exec:
        return {"success": False, "requires_approval": True, "reason": reason, "bundle_id": bundle["id"]}
    
    try:
        store.update("tasks", item_id, update_data)
        mark_applied(bundle["id"])
        return {"success": True, "id": item_id, "delegated_to": to, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/decisions/{decision_id}")
async def api_decision(decision_id: str, action: ApprovalAction):
    """Process a decision (approve/reject)."""
    dec = store.query("SELECT * FROM decisions WHERE id = ?", [decision_id])
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    now_iso = datetime.now().isoformat()
    is_approved = 1 if action.action == "approve" else 0
    
    bundle = create_bundle(
        domain="decisions",
        description=f"{'Approve' if is_approved else 'Reject'} decision: {dec[0].get('description', '')[:50]}",
        changes=[{"type": "update", "id": decision_id, "target": "decisions", "data": {"approved": is_approved}}],
        pre_images={decision_id: {"approved": dec[0].get("approved")}}
    )
    
    try:
        store.update("decisions", decision_id, {"approved": is_approved, "approved_at": now_iso})
        mark_applied(bundle["id"])
        return {"success": True, "id": decision_id, "approved": action.action, "bundle_id": bundle["id"]}
    except Exception as e:
        mark_failed(bundle["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==== Bundles Endpoints ====

@app.get("/api/bundles")
async def api_bundles(status: Optional[str] = None, domain: Optional[str] = None, limit: int = 50):
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
    pending = store.count("change_bundles", "status = 'pending'")
    applied = store.count("change_bundles", "status = 'applied'")
    rolled_back = store.count("change_bundles", "status = 'rolled_back'")
    failed = store.count("change_bundles", "status = 'failed'")
    
    recent = store.query("""
        SELECT * FROM change_bundles 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    return {
        "counts": {
            "pending": pending,
            "applied": applied,
            "rolled_back": rolled_back,
            "failed": failed
        },
        "recent": [dict(b) for b in recent]
    }


@app.post("/api/bundles/rollback-last")
async def rollback_last_bundle(domain: Optional[str] = None):
    """Rollback the most recent bundle."""
    rollbackable = list_rollbackable_bundles(domain=domain)
    if not rollbackable:
        raise HTTPException(status_code=404, detail="No rollbackable bundles found")
    
    bundle_id = rollbackable[0]["id"]
    result = rollback_bundle(bundle_id)
    
    return {
        "success": True,
        "bundle_id": bundle_id,
        "result": result
    }


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
    
    result = rollback_bundle(bundle_id)
    return {"success": True, "bundle_id": bundle_id, "result": result}


# ==== Calibration Endpoints ====

calibration_engine = CalibrationEngine(store=store)


@app.get("/api/calibration")
async def api_calibration_last():
    """Get last calibration results."""
    return calibration_engine.get_last_calibration()


@app.post("/api/calibration/run")
async def api_calibration_run():
    """Run calibration."""
    result = calibration_engine.run()
    return result


# ==== Feedback Endpoint ====

class FeedbackRequest(BaseModel):
    item_id: str
    rating: int
    comment: Optional[str] = None


@app.post("/api/feedback")
async def api_feedback(feedback: FeedbackRequest):
    """Submit feedback on a recommendation or action."""
    import uuid
    
    feedback_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    store.insert("feedback", {
        "id": feedback_id,
        "item_id": feedback.item_id,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "created_at": now
    })
    
    return {"success": True, "feedback_id": feedback_id}


# ==== Priorities Endpoints ====

@app.get("/api/priorities")
async def get_priorities(limit: int = 20, context: Optional[str] = None):
    """Get prioritized items."""
    priority_queue = analyzers.priority_analyzer.analyze() if hasattr(analyzers, 'priority_analyzer') else []
    
    sorted_items = sorted(priority_queue, key=lambda x: x.get('score', 0), reverse=True)[:limit]
    
    return {"items": sorted_items, "total": len(priority_queue)}


@app.post("/api/priorities/{item_id}/complete")
async def complete_item(item_id: str):
    """Complete a priority item."""
    return await api_priority_complete(item_id)


@app.post("/api/priorities/{item_id}/snooze")
async def snooze_item(item_id: str, hours: int = 4):
    """Snooze a priority item."""
    from datetime import timedelta
    
    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    new_time = datetime.now() + timedelta(hours=hours)
    now = datetime.now().isoformat()
    
    store.update("tasks", item_id, {"snoozed_until": new_time.isoformat(), "updated_at": now})
    
    return {"success": True, "id": item_id, "snoozed_until": new_time.isoformat()}


class DelegateAction(BaseModel):
    to: str
    note: Optional[str] = None


@app.post("/api/priorities/{item_id}/delegate")
async def delegate_item(item_id: str, body: DelegateAction):
    """Delegate a priority item."""
    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    now = datetime.now().isoformat()
    store.update("tasks", item_id, {
        "assignee": body.to,
        "delegated_by": "moh",
        "delegated_at": now,
        "delegated_note": body.note,
        "updated_at": now
    })
    
    return {"success": True, "id": item_id, "delegated_to": body.to}


@app.get("/api/priorities/filtered")
async def get_priorities_filtered(
    project: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    limit: int = 50
):
    """Get filtered priority items."""
    priority_queue = analyzers.priority_analyzer.analyze() if hasattr(analyzers, 'priority_analyzer') else []
    
    filtered = priority_queue
    
    if project:
        filtered = [i for i in filtered if i.get("project") and project.lower() in i["project"].lower()]
    
    if assignee:
        if assignee.lower() == "unassigned":
            filtered = [i for i in filtered if not i.get("assignee")]
        else:
            filtered = [i for i in filtered if i.get("assignee") and assignee.lower() in i["assignee"].lower()]
    
    if status:
        filtered = [i for i in filtered if i.get("status") == status]
    
    if min_score is not None:
        filtered = [i for i in filtered if i.get("score", 0) >= min_score]
    
    if max_score is not None:
        filtered = [i for i in filtered if i.get("score", 0) <= max_score]
    
    sorted_items = sorted(filtered, key=lambda x: x.get('score', 0), reverse=True)[:limit]
    
    return {"items": sorted_items, "total": len(filtered)}


class BulkAction(BaseModel):
    action: str
    item_ids: list
    params: Optional[dict] = None


@app.post("/api/priorities/bulk")
async def bulk_action(body: BulkAction):
    """Perform bulk actions on priority items."""
    results = []
    
    for item_id in body.item_ids:
        try:
            if body.action == "complete":
                store.update("tasks", item_id, {"status": "completed", "updated_at": datetime.now().isoformat()})
                results.append({"id": item_id, "success": True})
            elif body.action == "archive":
                store.update("tasks", item_id, {"status": "archived", "updated_at": datetime.now().isoformat()})
                results.append({"id": item_id, "success": True})
            elif body.action == "snooze":
                days = body.params.get("days", 1) if body.params else 1
                new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
                store.update("tasks", item_id, {"due_date": new_date, "updated_at": datetime.now().isoformat()})
                results.append({"id": item_id, "success": True, "new_due_date": new_date})
            elif body.action == "delegate":
                to = body.params.get("to") if body.params else None
                if to:
                    store.update("tasks", item_id, {
                        "assignee": to,
                        "delegated_by": "moh",
                        "delegated_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    })
                    results.append({"id": item_id, "success": True, "delegated_to": to})
                else:
                    results.append({"id": item_id, "success": False, "error": "Missing 'to' parameter"})
            else:
                results.append({"id": item_id, "success": False, "error": f"Unknown action: {body.action}"})
        except Exception as e:
            results.append({"id": item_id, "success": False, "error": str(e)})
    
    success_count = sum(1 for r in results if r.get("success"))
    
    return {
        "success": success_count == len(body.item_ids),
        "total": len(body.item_ids),
        "succeeded": success_count,
        "results": results
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
    q: Optional[str] = None,
    project: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    tags: Optional[str] = None,
    due_range: Optional[str] = None,
    sort: str = "score",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0
):
    """Advanced priority filtering with more options."""
    priority_queue = analyzers.priority_analyzer.analyze() if hasattr(analyzers, 'priority_analyzer') else []
    filtered = priority_queue
    
    # Text search
    if q:
        q_lower = q.lower()
        filtered = [i for i in filtered if q_lower in (i.get("title") or "").lower() or q_lower in (i.get("description") or "").lower()]
    
    # Project filter
    if project:
        if project.lower() == "none":
            filtered = [i for i in filtered if not i.get("project")]
        else:
            filtered = [i for i in filtered if i.get("project") and project.lower() in i["project"].lower()]
    
    # Assignee filter
    if assignee:
        if assignee.lower() == "unassigned":
            filtered = [i for i in filtered if not i.get("assignee")]
        elif assignee.lower() == "me":
            filtered = [i for i in filtered if i.get("assignee") and "me" in i["assignee"].lower()]
        else:
            filtered = [i for i in filtered if i.get("assignee") and assignee.lower() in i["assignee"].lower()]
    
    # Status filter
    if status:
        filtered = [i for i in filtered if i.get("status") == status]
    
    # Score filters
    if min_score is not None:
        filtered = [i for i in filtered if i.get("score", 0) >= min_score]
    if max_score is not None:
        filtered = [i for i in filtered if i.get("score", 0) <= max_score]
    
    # Due date range
    if due_range:
        from datetime import date, timedelta
        today = date.today()
        
        if due_range == "today":
            filtered = [i for i in filtered if i.get("due") and i["due"][:10] == today.isoformat()]
        elif due_range == "week":
            end = (today + timedelta(days=7)).isoformat()
            filtered = [i for i in filtered if i.get("due") and today.isoformat() <= i["due"][:10] <= end]
        elif due_range == "overdue":
            filtered = [i for i in filtered if i.get("due") and i["due"][:10] < today.isoformat()]
    
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
        "assignee": lambda x: (x.get("assignee") or "").lower()
    }.get(sort, lambda x: x.get("score", 0))
    
    reverse = order.lower() != "asc"
    filtered = sorted(filtered, key=sort_key, reverse=reverse)
    
    total = len(filtered)
    filtered = filtered[offset:offset + limit]
    
    return {
        "items": filtered,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total
    }


@app.post("/api/priorities/archive-stale")
async def archive_stale(days_threshold: int = 14):
    """Archive stale priority items."""
    from datetime import timedelta
    
    cutoff = (datetime.now() - timedelta(days=days_threshold)).isoformat()
    
    tasks = store.query("""
        SELECT id, title FROM tasks
        WHERE status = 'pending' 
        AND updated_at < ?
        AND snoozed_until IS NULL
    """, [cutoff])
    
    for task in tasks:
        store.update("tasks", task["id"], {"status": "archived", "updated_at": datetime.now().isoformat()})
    
    return {"success": True, "archived_count": len(tasks)}


@app.get("/api/events")
async def get_events(hours: int = 24):
    """Get upcoming events."""
    from datetime import timedelta
    
    start = datetime.now().isoformat()
    end = (datetime.now() + timedelta(hours=hours)).isoformat()
    
    events = store.query("""
        SELECT * FROM events 
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time
    """, [start, end])
    
    return {"events": [dict(e) for e in events], "total": len(events)}


@app.get("/api/day/{date}")
async def get_day_analysis(date: str, context: Optional[str] = None):
    """Get analysis for a specific day."""
    from lib.time_truth import get_day_analysis
    
    return get_day_analysis(store, date, context=context)


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
    
    emails = store.query(f"""
        SELECT * FROM communications 
        WHERE {' AND '.join(conditions)}
        ORDER BY received_at DESC
        LIMIT ?
    """, [limit])
    
    return {"emails": [dict(e) for e in emails], "total": len(emails)}


@app.post("/api/emails/{email_id}/mark-actionable")
async def mark_email_actionable(email_id: str):
    """Mark an email as actionable."""
    store.update("communications", email_id, {"actionable": 1, "updated_at": datetime.now().isoformat()})
    return {"success": True, "id": email_id}


@app.get("/api/insights")
async def get_insights(category: Optional[str] = None):
    """Get insights."""
    conditions = ["(expires_at IS NULL OR expires_at > datetime('now'))"]
    params = []
    
    if category:
        conditions.append("category = ?")
        params.append(category)
    
    insights = store.query(f"""
        SELECT * FROM insights 
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
    """, params if params else None)
    
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
    
    notifications = store.query(f"""
        SELECT * FROM notifications 
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT ?
    """, [limit])
    
    return {"notifications": [dict(n) for n in notifications], "total": len(notifications)}


@app.get("/api/notifications/stats")
async def get_notification_stats():
    """Get notification statistics."""
    total = store.count("notifications", "1=1")
    unread = store.count("notifications", "(dismissed = 0 OR dismissed IS NULL)")
    
    return {"total": total, "unread": unread}


@app.post("/api/notifications/{notif_id}/dismiss")
async def dismiss_notification(notif_id: str):
    """Dismiss a notification."""
    store.update("notifications", notif_id, {"dismissed": 1, "dismissed_at": datetime.now().isoformat()})
    return {"success": True, "id": notif_id}


@app.post("/api/notifications/dismiss-all")
async def dismiss_all_notifications():
    """Dismiss all notifications."""
    now = datetime.now().isoformat()
    notifications = store.query("SELECT id FROM notifications WHERE dismissed = 0 OR dismissed IS NULL")
    
    for n in notifications:
        store.update("notifications", n["id"], {"dismissed": 1, "dismissed_at": now})
    
    return {"success": True, "dismissed_count": len(notifications)}


# ==== Approvals Endpoints ====

@app.get("/api/approvals")
async def get_approvals():
    """Get pending approvals."""
    approvals = store.query("SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC")
    return {"approvals": [dict(a) for a in approvals], "total": len(approvals)}


@app.post("/api/approvals/{decision_id}")
async def process_approval(decision_id: str, action: ApprovalAction):
    """Process an approval."""
    return await api_decision(decision_id, action)


class ModifyApproval(BaseModel):
    modifications: dict


@app.post("/api/approvals/{decision_id}/modify")
async def modify_approval(decision_id: str, body: ModifyApproval):
    """Modify and approve a decision."""
    dec = store.get("decisions", decision_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    now = datetime.now().isoformat()
    store.update("decisions", decision_id, {
        "approved": 1,
        "approved_at": now,
        "modifications": json.dumps(body.modifications)
    })
    
    return {"success": True, "id": decision_id, "modified": True}


# ==== Governance Endpoints ====

@app.get("/api/governance")
async def get_governance_status():
    """Get governance configuration and status."""
    return {
        "domains": governance.get_all_domains(),
        "emergency_brake": governance.is_emergency_brake_active(),
        "summary": governance.get_summary()
    }


@app.put("/api/governance/{domain}")
async def set_governance_mode(domain: str, body: ModeChange):
    """Set governance mode for a domain."""
    try:
        mode = DomainMode(body.mode)
        governance.set_mode(domain, mode)
        return {"success": True, "domain": domain, "mode": body.mode}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {body.mode}")


class ThresholdUpdate(BaseModel):
    threshold: float


@app.put("/api/governance/{domain}/threshold")
async def set_governance_threshold(domain: str, body: ThresholdUpdate):
    """Set confidence threshold for a domain."""
    governance.set_threshold(domain, body.threshold)
    return {"success": True, "domain": domain, "threshold": body.threshold}


@app.get("/api/governance/history")
async def get_governance_history(limit: int = 50):
    """Get governance action history."""
    history = store.query("""
        SELECT * FROM governance_history 
        ORDER BY created_at DESC 
        LIMIT ?
    """, [limit])
    
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
async def force_sync(source: Optional[str] = None):
    """Force a sync operation."""
    result = collectors.sync(source=source)
    return result


@app.post("/api/analyze")
async def run_analysis():
    """Run analysis."""
    result = analyzers.analyze()
    return result


@app.post("/api/cycle")
async def run_cycle():
    """Run a full autonomous cycle."""
    loop = AutonomousLoop(store, collectors, analyzers, governance)
    result = loop.run_cycle()
    return result


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "sync": collectors.get_status(),
        "governance": governance.get_summary()
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/summary")
async def get_summary():
    """Get a comprehensive summary."""
    priority_queue = analyzers.priority_analyzer.analyze() if hasattr(analyzers, 'priority_analyzer') else []
    
    # Get counts
    pending_tasks = store.count("tasks", "status = 'pending'")
    overdue_tasks = store.query("""
        SELECT COUNT(*) as cnt FROM tasks 
        WHERE status = 'pending' AND due_date < date('now')
    """)
    overdue_count = overdue_tasks[0]["cnt"] if overdue_tasks else 0
    
    pending_decisions = store.count("decisions", "approved IS NULL")
    
    return {
        "priorities": {
            "top_5": sorted(priority_queue, key=lambda x: x.get('score', 0), reverse=True)[:5],
            "total": len(priority_queue)
        },
        "tasks": {
            "pending": pending_tasks,
            "overdue": overdue_count
        },
        "decisions": {
            "pending": pending_decisions
        },
        "sync": collectors.get_status()
    }


@app.get("/api/search")
async def search_items(q: str, limit: int = 20):
    """Search across tasks, projects, and clients."""
    results = []
    
    # Search tasks
    tasks = store.query("""
        SELECT 'task' as type, id, title, status, project FROM tasks 
        WHERE title LIKE ? OR description LIKE ?
        LIMIT ?
    """, [f"%{q}%", f"%{q}%", limit])
    results.extend([dict(t) for t in tasks])
    
    # Search projects
    projects = store.query("""
        SELECT 'project' as type, id, name as title, status FROM projects 
        WHERE name LIKE ?
        LIMIT ?
    """, [f"%{q}%", limit])
    results.extend([dict(p) for p in projects])
    
    # Search clients
    clients = store.query("""
        SELECT 'client' as type, id, name as title, tier FROM clients 
        WHERE name LIKE ?
        LIMIT ?
    """, [f"%{q}%", limit])
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
            MAX(priority) as max_priority
        FROM tasks 
        WHERE status = 'pending' AND assignee IS NOT NULL AND assignee != ''
        GROUP BY assignee
        ORDER BY total DESC
    """)
    
    return {
        "workload": [dict(w) for w in workload],
        "total_assignees": len(workload)
    }


@app.get("/api/priorities/grouped")
async def get_grouped_priorities(group_by: str = "project", limit: int = 10):
    """Get priorities grouped by a field."""
    if group_by not in ("project", "assignee", "source"):
        group_by = "project"
    
    groups = store.query(f"""
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
    """, [limit])
    
    return {
        "groups": [
            {
                "name": g["group_name"],
                "total": g["total"],
                "overdue": g["overdue"] or 0,
                "max_priority": g["max_priority"] or 0
            }
            for g in groups
        ],
        "group_by": group_by
    }


@app.get("/api/clients")
async def get_clients(
    tier: Optional[str] = None,
    health: Optional[str] = None,
    ar_status: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100
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
            conditions.append("financial_ar_outstanding > 0 AND financial_ar_aging IN ('30+', '60+', '90+')")
        elif ar_status == "any":
            conditions.append("financial_ar_outstanding > 0")
        elif ar_status == "none":
            conditions.append("(financial_ar_outstanding IS NULL OR financial_ar_outstanding = 0)")
    
    if active_only:
        active_client_ids = store.query("""
            SELECT DISTINCT client_id FROM tasks 
            WHERE client_id IS NOT NULL 
            AND (updated_at >= date('now', '-90 days') OR status = 'pending')
            UNION
            SELECT DISTINCT client_id FROM projects 
            WHERE client_id IS NOT NULL 
            AND enrollment_status = 'enrolled'
        """)
        active_ids = [r["client_id"] for r in active_client_ids]
        
        if active_ids:
            placeholders = ",".join(["?" for _ in active_ids])
            conditions.append(f"id IN ({placeholders})")
            params.extend(active_ids)
        else:
            return {"items": [], "total": 0, "active_only": True}
    
    params.append(limit)
    
    clients = store.query(f"""
        SELECT * FROM clients 
        WHERE {' AND '.join(conditions)}
        ORDER BY 
            CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
            financial_ar_outstanding DESC NULLS LAST,
            name
        LIMIT ?
    """, params)
    
    result = []
    for c in clients:
        client_dict = dict(c)
        
        projects = store.query(
            "SELECT COUNT(*) as cnt FROM projects WHERE client_id = ? AND enrollment_status = 'enrolled'",
            [c["id"]]
        )
        client_dict["project_count"] = projects[0]["cnt"] if projects else 0
        
        tasks = store.query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE client_id = ? AND status = 'pending'",
            [c["id"]]
        )
        client_dict["open_task_count"] = tasks[0]["cnt"] if tasks else 0
        
        result.append(client_dict)
    
    return {"items": result, "total": len(result), "active_only": active_only}


@app.get("/api/clients/portfolio")
async def get_client_portfolio():
    """Get client portfolio overview."""
    tier_stats = store.query("""
        SELECT 
            tier,
            COUNT(*) as count,
            SUM(financial_ar_outstanding) as total_ar,
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
           OR (financial_ar_outstanding > 100000 AND financial_ar_aging = '90+')
        ORDER BY tier, financial_ar_outstanding DESC
        LIMIT 10
    """)
    
    totals = store.query("""
        SELECT 
            COUNT(*) as total_clients,
            SUM(financial_ar_outstanding) as total_ar,
            SUM(financial_annual_value) as total_annual_value
        FROM clients
    """)
    
    overdue_ar = store.query("""
        SELECT 
            COUNT(*) as count,
            COALESCE(SUM(financial_ar_outstanding), 0) as total
        FROM clients
        WHERE financial_ar_outstanding > 0 
        AND financial_ar_aging IN ('30+', '60+', '90+')
    """)
    
    return {
        "by_tier": [dict(t) for t in tier_stats],
        "by_health": [dict(h) for h in health_stats],
        "at_risk": [dict(r) for r in at_risk],
        "totals": dict(totals[0]) if totals else {},
        "overdue_ar": dict(overdue_ar[0]) if overdue_ar else {}
    }


@app.get("/api/clients/{client_id}")
async def get_client_detail(client_id: str):
    """Get detailed client information."""
    client = store.get("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client_dict = dict(client)
    
    # Get projects
    projects = store.query(
        "SELECT * FROM projects WHERE client_id = ? ORDER BY updated_at DESC",
        [client_id]
    )
    client_dict["projects"] = [dict(p) for p in projects]
    
    # Get tasks
    tasks = store.query(
        "SELECT * FROM tasks WHERE client_id = ? AND status = 'pending' ORDER BY priority DESC LIMIT 20",
        [client_id]
    )
    client_dict["open_tasks"] = [dict(t) for t in tasks]
    
    # Get recent communications
    comms = store.query(
        "SELECT * FROM communications WHERE client_id = ? ORDER BY received_at DESC LIMIT 10",
        [client_id]
    )
    client_dict["recent_communications"] = [dict(c) for c in comms]
    
    return client_dict


class ClientUpdate(BaseModel):
    tier: Optional[str] = None
    relationship_health: Optional[str] = None
    notes: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None


@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, body: ClientUpdate):
    """Update client information."""
    client = store.get("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now().isoformat()
    
    store.update("clients", client_id, update_data)
    
    return {"success": True, "id": client_id}


@app.get("/api/projects")
async def get_projects(client_id: Optional[str] = None, include_archived: bool = False, limit: int = 50):
    """Get projects with filters."""
    conditions = ["1=1"]
    params = []
    
    if client_id:
        conditions.append("client_id = ?")
        params.append(client_id)
    
    if not include_archived:
        conditions.append("enrollment_status != 'archived'")
    
    params.append(limit)
    
    projects = store.query(f"""
        SELECT * FROM projects 
        WHERE {' AND '.join(conditions)}
        ORDER BY updated_at DESC
        LIMIT ?
    """, params)
    
    return {"projects": [dict(p) for p in projects], "total": len(projects)}


@app.get("/api/projects/candidates")
async def get_project_candidates():
    """Get projects that could be enrolled."""
    projects = store.query("""
        SELECT * FROM projects 
        WHERE (enrollment_status IS NULL OR enrollment_status = 'candidate')
        ORDER BY updated_at DESC
    """)
    
    return {"projects": [dict(p) for p in projects], "total": len(projects)}


@app.get("/api/projects/enrolled")
async def get_enrolled_projects():
    """Get enrolled projects."""
    projects = store.query("""
        SELECT * FROM projects 
        WHERE enrollment_status = 'enrolled'
        ORDER BY updated_at DESC
    """)
    
    return {"projects": [dict(p) for p in projects], "total": len(projects)}


class EnrollmentAction(BaseModel):
    action: str
    reason: Optional[str] = None
    client_id: Optional[str] = None


@app.post("/api/projects/{project_id}/enrollment")
async def process_enrollment(project_id: str, body: EnrollmentAction):
    """Process project enrollment action."""
    project = store.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    now = datetime.now().isoformat()
    update_data = {"updated_at": now}
    
    if body.action == "enroll":
        update_data["enrollment_status"] = "enrolled"
        update_data["enrolled_at"] = now
        if body.client_id:
            update_data["client_id"] = body.client_id
    elif body.action == "reject":
        update_data["enrollment_status"] = "rejected"
        update_data["rejection_reason"] = body.reason
    elif body.action == "archive":
        update_data["enrollment_status"] = "archived"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")
    
    store.update("projects", project_id, update_data)
    
    return {"success": True, "id": project_id, "action": body.action}


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
    
    project_dict = dict(project)
    
    # Get tasks
    tasks = store.query(
        "SELECT * FROM tasks WHERE project = ? ORDER BY priority DESC",
        [project.get("name")]
    )
    project_dict["tasks"] = [dict(t) for t in tasks]
    project_dict["task_count"] = len(tasks)
    
    return project_dict


@app.post("/api/sync/xero")
async def sync_xero():
    """Sync with Xero."""
    result = collectors.sync(source="xero")
    return result


@app.post("/api/tasks/link")
async def bulk_link_tasks():
    """Bulk link tasks to projects/clients."""
    # TODO: Implement bulk linking
    return {"success": True, "message": "Bulk link not implemented yet"}


@app.post("/api/projects/propose")
async def propose_project(name: str, client_id: Optional[str] = None, type: str = "retainer"):
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
        "updated_at": now
    }
    
    store.insert("projects", project_data)
    
    return {"success": True, "project": project_data}


@app.get("/api/emails")
async def get_email_queue(limit: int = 20):
    """Get email queue."""
    emails = store.query("""
        SELECT * FROM communications 
        WHERE type = 'email' AND (processed = 0 OR processed IS NULL)
        ORDER BY received_at DESC
        LIMIT ?
    """, [limit])
    
    return {
        "items": [
            {
                "id": e.get("id"),
                "subject": e.get("subject"),
                "from": e.get("from_address") or e.get("sender"),
                "received": e.get("received_at") or e.get("created_at"),
                "snippet": (e.get("snippet") or e.get("body") or "")[:100],
                "thread_id": e.get("thread_id")
            }
            for e in emails
        ],
        "total": store.count("communications", "(processed = 0 OR processed IS NULL)")
    }


@app.post("/api/emails/{email_id}/dismiss")
async def dismiss_email(email_id: str):
    """Dismiss an email."""
    store.update("communications", email_id, {"processed": 1})
    return {"success": True, "id": email_id}


@app.get("/api/digest/weekly")
async def get_weekly_digest():
    """Get weekly digest."""
    from datetime import date, timedelta
    
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    
    completed = store.query("""
        SELECT * FROM tasks 
        WHERE status = 'completed' AND updated_at >= ?
        ORDER BY updated_at DESC
    """, [week_ago])
    
    slipped = store.query("""
        SELECT * FROM tasks 
        WHERE status = 'pending' AND due_date < date('now') AND due_date >= ?
        ORDER BY due_date ASC
    """, [week_ago])
    
    archived = store.query("""
        SELECT COUNT(*) as cnt FROM tasks 
        WHERE status = 'archived' AND updated_at >= ?
    """, [week_ago])
    
    return {
        "period": {"start": week_ago, "end": date.today().isoformat()},
        "completed": {
            "count": len(completed),
            "items": [
                {"id": t["id"], "title": t["title"], "completed_at": t["updated_at"]}
                for t in completed[:10]
            ]
        },
        "slipped": {
            "count": len(slipped),
            "items": [
                {"id": t["id"], "title": t["title"], "due": t["due_date"], "assignee": t["assignee"]}
                for t in slipped[:10]
            ]
        },
        "archived": archived[0]["cnt"] if archived else 0
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
    except:
        current = []
    
    if body.blocker_id not in current:
        current.append(body.blocker_id)
        store.update("tasks", task_id, {
            "blockers": json.dumps(current),
            "updated_at": datetime.now().isoformat()
        })
    
    return {"success": True, "blockers": current}


@app.delete("/api/tasks/{task_id}/block/{blocker_id}")
async def remove_blocker(task_id: str, blocker_id: str):
    """Remove a blocker from a task."""
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        current = json.loads(task.get("blockers") or "[]")
    except:
        current = []
    
    if blocker_id in current:
        current.remove(blocker_id)
        store.update("tasks", task_id, {
            "blockers": json.dumps(current),
            "updated_at": datetime.now().isoformat()
        })
    
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
        except:
            pass
    
    return {
        "blocked": [
            {
                "id": t["id"],
                "title": t["title"],
                "blockers": t["blockers"],
                "assignee": t["assignee"],
                "due": t["due_date"]
            }
            for t in blocked
        ],
        "blocking_count": len(blocking_ids),
        "total_blocked": len(blocked)
    }


# ==== SPA Fallback ====

@app.get("/{path:path}")
async def spa_fallback(path: str):
    """Serve the SPA for all non-API routes."""
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(UI_DIR / "index.html")


# ==== Main ====

def main():
    """Run the server."""
    uvicorn.run(app, host="0.0.0.0", port=8420)


if __name__ == "__main__":
    main()
