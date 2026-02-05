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
    create_task_bundle,
    create_bundle,
    mark_applied,
    mark_failed,
    get_bundle,
    rollback_bundle,
    list_bundles,
    list_rollbackable_bundles,
)
from lib.calibration import CalibrationEngine

# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="MOH TIME OS API",
    description="Personal Operating System API - Direct control without AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
store = get_store()
collectors = CollectorOrchestrator(store=store)
analyzers = AnalyzerOrchestrator(store=store)
governance = get_governance(store=store)

UI_DIR = Path(__file__).parent.parent / "ui"

# =============================================================================
# ROOT / STATIC
# =============================================================================

@app.get("/")
async def root():
    return FileResponse(UI_DIR / "index.html")


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ApprovalAction(BaseModel):
    action: str


class ModeChange(BaseModel):
    mode: str


# =============================================================================
# OVERVIEW
# =============================================================================

@app.get("/api/overview")
async def get_overview():
    # Priority queue
    if hasattr(analyzers, "priority_analyzer"):
        priority_queue = analyzers.priority_analyzer.analyze()
    else:
        priority_queue = []
    top_priorities = sorted(priority_queue, key=lambda x: x.get("score", 0), reverse=True)[:5]

    # Today's events
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    events = store.query(
        "SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time",
        [today]
    )

    # Pending decisions
    pending_decisions = store.query(
        "SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC LIMIT 5"
    )

    # Anomalies
    anomalies = store.query(
        "SELECT * FROM insights WHERE type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now')) ORDER BY created_at DESC LIMIT 5"
    )

    return {
        "priorities": {
            "items": top_priorities,
            "total": len(priority_queue),
        },
        "calendar": {
            "events": [dict(e) for e in events],
            "event_count": len(events),
        },
        "decisions": {
            "pending": [dict(d) for d in pending_decisions],
            "pending_count": store.count("decisions", "approved IS NULL"),
        },
        "anomalies": {
            "items": [dict(a) for a in anomalies],
            "total": store.count("insights", "type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now'))"),
        },
        "sync_status": collectors.get_status(),
    }


# =============================================================================
# TIME BLOCKS
# =============================================================================

@app.get("/api/time/blocks")
async def get_time_blocks(date: Optional[str] = None, lane: Optional[str] = None):
    from datetime import datetime, timedelta
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    query = "SELECT * FROM time_blocks WHERE date(start_time) = ?"
    params = [date]
    
    if lane:
        query += " AND lane = ?"
        params.append(lane)
    
    query += " ORDER BY start_time"
    blocks = store.query(query, params)
    
    # Calculate summary
    total_minutes = sum(b.get("duration_minutes", 0) for b in blocks)
    by_lane = {}
    for b in blocks:
        l = b.get("lane", "unknown")
        by_lane[l] = by_lane.get(l, 0) + b.get("duration_minutes", 0)
    
    return {
        "date": date,
        "blocks": [dict(b) for b in blocks],
        "summary": {
            "total_minutes": total_minutes,
            "by_lane": by_lane,
        },
    }


@app.get("/api/time/summary")
async def get_time_summary(days: Optional[int] = None):
    from datetime import datetime, timedelta
    
    if days is None:
        days = 7
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    blocks = store.query(
        "SELECT * FROM time_blocks WHERE date(start_time) >= ? ORDER BY start_time",
        [start_date]
    )
    
    by_day = {}
    by_lane = {}
    
    for b in blocks:
        day = b.get("start_time", "")[:10]
        lane = b.get("lane", "unknown")
        mins = b.get("duration_minutes", 0)
        
        if day not in by_day:
            by_day[day] = {"total": 0, "lanes": {}}
        by_day[day]["total"] += mins
        by_day[day]["lanes"][lane] = by_day[day]["lanes"].get(lane, 0) + mins
        
        by_lane[lane] = by_lane.get(lane, 0) + mins
    
    return {
        "days": days,
        "by_day": by_day,
        "by_lane": by_lane,
        "total_minutes": sum(by_lane.values()),
    }


@app.get("/api/time/brief")
async def get_time_brief(date: Optional[str] = None, format: str = "markdown"):
    from datetime import datetime
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    blocks = store.query(
        "SELECT * FROM time_blocks WHERE date(start_time) = ? ORDER BY start_time",
        [date]
    )
    
    if format == "markdown":
        lines = [f"# Time Brief: {date}", ""]
        for b in blocks:
            start = b.get("start_time", "")[-8:-3]
            end = b.get("end_time", "")[-8:-3] if b.get("end_time") else "ongoing"
            lane = b.get("lane", "unknown")
            desc = b.get("description", "")
            lines.append(f"- **{start}-{end}** [{lane}] {desc}")
        return {"brief": "\n".join(lines)}
    else:
        return {"blocks": [dict(b) for b in blocks]}


@app.post("/api/time/schedule")
async def schedule_task(task_id: Optional[str] = None, slot: Optional[str] = None):
    if not task_id or not slot:
        raise HTTPException(status_code=400, detail="task_id and slot are required")
    
    # Parse slot
    try:
        from datetime import datetime
        start_time = datetime.fromisoformat(slot)
    except:
        raise HTTPException(status_code=400, detail="Invalid slot format")
    
    # Get task
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Create time block
    store.insert("time_blocks", {
        "task_id": task_id,
        "start_time": slot,
        "lane": task.get("lane", "work"),
        "description": task.get("title", ""),
    })
    
    return {"status": "scheduled", "task_id": task_id, "slot": slot}


@app.post("/api/time/unschedule")
async def unschedule_task(block_id: str):
    block = store.get("time_blocks", block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Time block not found")
    
    store.delete("time_blocks", block_id)
    return {"status": "unscheduled", "block_id": block_id}


# =============================================================================
# COMMITMENTS
# =============================================================================

@app.get("/api/commitments")
async def get_commitments(status: Optional[str] = None, limit: int = 50):
    query = "SELECT * FROM commitments"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY due_date ASC LIMIT ?"
    params.append(limit)
    
    commitments = store.query(query, params)
    
    return {
        "commitments": [dict(c) for c in commitments],
        "total": store.count("commitments", f"status = '{status}'" if status else None),
    }


@app.get("/api/commitments/untracked")
async def get_untracked_commitments(limit: int = 50):
    # Find tasks that look like commitments but aren't tracked
    commitments = store.query(
        """SELECT * FROM tasks 
           WHERE (title LIKE '%commit%' OR title LIKE '%promise%' OR title LIKE '%deadline%')
           AND id NOT IN (SELECT task_id FROM commitments WHERE task_id IS NOT NULL)
           LIMIT ?""",
        [limit]
    )
    return {"untracked": [dict(c) for c in commitments]}


@app.get("/api/commitments/due")
async def get_commitments_due(days: Optional[int] = None):
    from datetime import datetime, timedelta
    
    if days is None:
        days = 7
    
    due_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    
    commitments = store.query(
        "SELECT * FROM commitments WHERE due_date <= ? AND status != 'done' ORDER BY due_date ASC",
        [due_date]
    )
    
    return {
        "due_within_days": days,
        "commitments": [dict(c) for c in commitments],
    }


@app.get("/api/commitments/summary")
async def get_commitments_summary():
    total = store.count("commitments")
    done = store.count("commitments", "status = 'done'")
    overdue = store.count("commitments", "due_date < date('now') AND status != 'done'")
    
    return {
        "total": total,
        "done": done,
        "pending": total - done,
        "overdue": overdue,
    }


@app.post("/api/commitments/{commitment_id}/link")
async def link_commitment(commitment_id: str, task_id: str):
    commitment = store.get("commitments", commitment_id)
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")
    
    store.update("commitments", commitment_id, {"task_id": task_id})
    return {"status": "linked", "commitment_id": commitment_id, "task_id": task_id}


@app.post("/api/commitments/{commitment_id}/done")
async def mark_commitment_done(commitment_id: str):
    commitment = store.get("commitments", commitment_id)
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")
    
    store.update("commitments", commitment_id, {"status": "done"})
    return {"status": "marked_done", "commitment_id": commitment_id}


# =============================================================================
# CAPACITY
# =============================================================================

@app.get("/api/capacity/lanes")
async def get_capacity_lanes():
    lanes = store.query("SELECT DISTINCT lane FROM time_blocks")
    lane_names = [l.get("lane") for l in lanes if l.get("lane")]
    
    # Add default lanes
    default_lanes = ["work", "personal", "health", "learning"]
    all_lanes = list(set(lane_names + default_lanes))
    
    return {"lanes": all_lanes}


@app.get("/api/capacity/utilization")
async def get_capacity_utilization(start_date: Optional[str] = None, end_date: Optional[str] = None):
    from datetime import datetime, timedelta
    
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    blocks = store.query(
        "SELECT * FROM time_blocks WHERE date(start_time) BETWEEN ? AND ?",
        [start_date, end_date]
    )
    
    total_available = 8 * 60 * 7  # 8 hours/day, 7 days
    total_used = sum(b.get("duration_minutes", 0) for b in blocks)
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_available_minutes": total_available,
        "total_used_minutes": total_used,
        "utilization_percent": round(total_used / total_available * 100, 1) if total_available > 0 else 0,
    }


@app.get("/api/capacity/forecast")
async def get_capacity_forecast(days: int = 7):
    from datetime import datetime, timedelta
    
    # Get historical average
    history = store.query(
        "SELECT date(start_time) as day, SUM(duration_minutes) as total FROM time_blocks GROUP BY day ORDER BY day DESC LIMIT 14"
    )
    
    if history:
        avg_daily = sum(h.get("total", 0) for h in history) / len(history)
    else:
        avg_daily = 0
    
    forecast = []
    for i in range(days):
        day = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        forecast.append({
            "date": day,
            "forecast_minutes": round(avg_daily),
        })
    
    return {"forecast": forecast}


@app.get("/api/capacity/debt")
async def get_capacity_debt(lane: Optional[str] = None):
    query = "SELECT * FROM capacity_debt"
    params = []
    
    if lane:
        query += " WHERE lane = ?"
        params.append(lane)
    
    query += " ORDER BY created_at DESC"
    debt = store.query(query, params) if params else store.query(query)
    
    return {"debt": [dict(d) for d in debt]}


@app.post("/api/capacity/debt/accrue")
async def accrue_debt(lane: Optional[str] = None, minutes: int = 0, reason: str = ""):
    if not lane or minutes <= 0:
        raise HTTPException(status_code=400, detail="lane and positive minutes required")
    
    debt_id = store.insert("capacity_debt", {
        "lane": lane,
        "minutes": minutes,
        "reason": reason,
        "status": "pending",
    })
    
    return {"status": "accrued", "debt_id": debt_id}


@app.post("/api/capacity/debt/{debt_id}/resolve")
async def resolve_debt(debt_id: str):
    debt = store.get("capacity_debt", debt_id)
    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")
    
    store.update("capacity_debt", debt_id, {"status": "resolved"})
    return {"status": "resolved", "debt_id": debt_id}


# =============================================================================
# CLIENTS
# =============================================================================

@app.get("/api/clients/health")
async def get_clients_health(limit: int = 20):
    clients = store.query(
        "SELECT * FROM clients ORDER BY health_score ASC LIMIT ?",
        [limit]
    )
    
    # Enrich with project counts
    result = []
    for c in clients:
        client_dict = dict(c)
        client_dict["project_count"] = store.count("projects", f"client_id = '{c.get('id')}'")
        result.append(client_dict)
    
    result.sort(key=lambda x: x.get("health_score", 100))
    return {"clients": result}


@app.get("/api/clients/at-risk")
async def get_at_risk_clients(threshold: int = 50):
    clients = store.query(
        "SELECT * FROM clients WHERE health_score < ? ORDER BY health_score ASC",
        [threshold]
    )
    return {"at_risk": [dict(c) for c in clients]}


@app.get("/api/clients/{client_id}/health")
async def get_client_health(client_id: str):
    client = store.get("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return dict(client)


@app.get("/api/clients/{client_id}/projects")
async def get_client_projects(client_id: str):
    projects = store.query(
        "SELECT * FROM projects WHERE client_id = ? ORDER BY created_at DESC",
        [client_id]
    )
    return {"projects": [dict(p) for p in projects]}


@app.post("/api/clients/link")
async def link_project_to_client(project_id: str, client_id: str):
    project = store.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    store.update("projects", project_id, {"client_id": client_id})
    return {"status": "linked"}


@app.get("/api/clients/linking-stats")
async def get_linking_stats():
    total_projects = store.count("projects")
    linked = store.count("projects", "client_id IS NOT NULL")
    unlinked = total_projects - linked
    
    return {
        "total_projects": total_projects,
        "linked": linked,
        "unlinked": unlinked,
    }


# =============================================================================
# TASKS
# =============================================================================

@app.get("/api/tasks")
async def get_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = 50
):
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if assignee:
        query += " AND assignee = ?"
        params.append(assignee)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    tasks = store.query(query, params)
    return {"tasks": [dict(t) for t in tasks]}


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "pending"
    due_date: Optional[str] = None
    assignee: Optional[str] = None
    project_id: Optional[str] = None
    lane: Optional[str] = "work"
    tags: Optional[list] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    assignee: Optional[str] = None
    project_id: Optional[str] = None
    lane: Optional[str] = None
    tags: Optional[list] = None


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(task)


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    task_data = task.model_dump(exclude_none=True)
    
    # Generate bundle for rollback
    bundle = create_task_bundle("create", task_data)
    
    task_id = store.insert("tasks", task_data)
    mark_applied(bundle["id"])
    
    return {"id": task_id, "bundle_id": bundle["id"], **task_data}


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, task: TaskUpdate):
    existing = store.get("tasks", task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    
    updates = task.model_dump(exclude_none=True)
    if not updates:
        return dict(existing)
    
    # Generate bundle for rollback
    bundle = create_task_bundle("update", {"id": task_id, "before": dict(existing), "after": updates})
    
    store.update("tasks", task_id, updates)
    mark_applied(bundle["id"])
    
    updated = store.get("tasks", task_id)
    return dict(updated)


class NoteAdd(BaseModel):
    content: str


@app.post("/api/tasks/{task_id}/notes")
async def add_task_note(task_id: str, note: NoteAdd):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    note_id = store.insert("task_notes", {
        "task_id": task_id,
        "content": note.content,
    })
    
    return {"note_id": note_id, "task_id": task_id}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Generate bundle for rollback
    bundle = create_task_bundle("delete", dict(task))
    
    store.delete("tasks", task_id)
    mark_applied(bundle["id"])
    
    return {"status": "deleted", "bundle_id": bundle["id"]}


class DelegateRequest(BaseModel):
    to: str
    reason: Optional[str] = None


class EscalateRequest(BaseModel):
    to: str
    reason: Optional[str] = None


@app.post("/api/tasks/{task_id}/delegate")
async def delegate_task(task_id: str, request: DelegateRequest):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    previous_assignee = task.get("assignee")
    
    store.update("tasks", task_id, {"assignee": request.to})
    store.insert("delegations", {
        "task_id": task_id,
        "from_user": previous_assignee,
        "to_user": request.to,
        "reason": request.reason,
        "type": "delegate",
    })
    
    return {"status": "delegated", "task_id": task_id, "to": request.to}


@app.post("/api/tasks/{task_id}/escalate")
async def escalate_task(task_id: str, request: EscalateRequest):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    previous_assignee = task.get("assignee")
    
    store.update("tasks", task_id, {"assignee": request.to, "priority": "high"})
    store.insert("delegations", {
        "task_id": task_id,
        "from_user": previous_assignee,
        "to_user": request.to,
        "reason": request.reason,
        "type": "escalate",
    })
    
    return {"status": "escalated", "task_id": task_id, "to": request.to}


@app.post("/api/tasks/{task_id}/recall")
async def recall_task(task_id: str):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Find last delegation
    delegations = store.query(
        "SELECT * FROM delegations WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
        [task_id]
    )
    
    if not delegations:
        raise HTTPException(status_code=400, detail="No delegation to recall")
    
    last = delegations[0]
    store.update("tasks", task_id, {"assignee": last.get("from_user")})
    
    return {"status": "recalled", "task_id": task_id}


@app.get("/api/delegations")
async def get_delegations():
    delegations = store.query(
        "SELECT * FROM delegations ORDER BY created_at DESC LIMIT 50"
    )
    return {"delegations": [dict(d) for d in delegations]}


# =============================================================================
# DATA QUALITY
# =============================================================================

@app.get("/api/data-quality")
async def get_data_quality():
    # Tasks stats
    total_tasks = store.count("tasks")
    tasks_no_due = store.count("tasks", "due_date IS NULL AND status != 'done'")
    tasks_no_priority = store.count("tasks", "priority IS NULL")
    
    # Stale tasks (no update in 30 days)
    stale_tasks = store.count("tasks", "updated_at < datetime('now', '-30 days') AND status != 'done'")
    
    # Ancient tasks (created > 90 days ago, still pending)
    ancient_tasks = store.count("tasks", "created_at < datetime('now', '-90 days') AND status = 'pending'")
    
    # Cleanup suggestions
    suggestions = _get_cleanup_suggestions(store)
    
    return {
        "total_tasks": total_tasks,
        "issues": {
            "no_due_date": tasks_no_due,
            "no_priority": tasks_no_priority,
            "stale": stale_tasks,
            "ancient": ancient_tasks,
        },
        "suggestions": suggestions,
        "health_score": max(0, 100 - (tasks_no_due + tasks_no_priority + stale_tasks + ancient_tasks)),
    }


def _get_cleanup_suggestions(store) -> list:
    suggestions = []
    
    stale = store.count("tasks", "updated_at < datetime('now', '-30 days') AND status != 'done'")
    if stale > 0:
        suggestions.append({
            "type": "stale",
            "count": stale,
            "message": f"{stale} tasks haven't been updated in 30+ days",
            "action": "Review and archive or update",
        })
    
    ancient = store.count("tasks", "created_at < datetime('now', '-90 days') AND status = 'pending'")
    if ancient > 0:
        suggestions.append({
            "type": "ancient",
            "count": ancient,
            "message": f"{ancient} tasks are 90+ days old and still pending",
            "action": "Archive or complete",
        })
    
    no_priority = store.count("tasks", "priority IS NULL")
    if no_priority > 0:
        suggestions.append({
            "type": "no_priority",
            "count": no_priority,
            "message": f"{no_priority} tasks have no priority set",
            "action": "Set priorities for better organization",
        })
    
    return suggestions


class CleanupRequest(BaseModel):
    dry_run: bool = True


@app.post("/api/data-quality/cleanup/ancient")
async def cleanup_ancient_tasks(dry_run: bool = False):
    tasks = store.query(
        "SELECT * FROM tasks WHERE created_at < datetime('now', '-90 days') AND status = 'pending'"
    )
    
    if dry_run:
        return {
            "dry_run": True,
            "would_archive": len(tasks),
            "tasks": [dict(t) for t in tasks],
        }
    
    archived = 0
    for t in tasks:
        store.update("tasks", t.get("id"), {"status": "archived"})
        archived += 1
    
    return {"archived": archived}


@app.post("/api/data-quality/cleanup/stale")
async def cleanup_stale_tasks(dry_run: bool = False):
    tasks = store.query(
        "SELECT * FROM tasks WHERE updated_at < datetime('now', '-30 days') AND status != 'done'"
    )
    
    if dry_run:
        return {
            "dry_run": True,
            "would_flag": len(tasks),
            "tasks": [dict(t) for t in tasks],
        }
    
    flagged = 0
    for t in tasks:
        # Add a tag or flag
        store.update("tasks", t.get("id"), {"needs_review": True})
        flagged += 1
    
    return {"flagged": flagged}


@app.post("/api/data-quality/recalculate-priorities")
async def recalculate_priorities():
    tasks = store.query(
        "SELECT * FROM tasks WHERE status != 'done' AND status != 'archived'"
    )
    
    updated = 0
    for t in tasks:
        new_priority = _calculate_realistic_priority(t)
        if new_priority != t.get("priority"):
            store.update("tasks", t.get("id"), {"priority": new_priority})
            updated += 1
    
    return {"recalculated": updated}


def _calculate_realistic_priority(task: dict) -> str:
    score = 0
    
    # Due date factor
    if task.get("due_date"):
        from datetime import datetime
        try:
            due = datetime.fromisoformat(task["due_date"])
            days_until = (due - datetime.now()).days
            if days_until < 0:
                score += 50  # Overdue
            elif days_until <= 1:
                score += 40
            elif days_until <= 7:
                score += 20
        except:
            pass
    
    # Age factor
    if task.get("created_at"):
        from datetime import datetime
        try:
            created = datetime.fromisoformat(task["created_at"])
            age_days = (datetime.now() - created).days
            if age_days > 30:
                score += 10
        except:
            pass
    
    # Existing priority weight
    current = task.get("priority", "medium")
    if current == "critical":
        score += 30
    elif current == "high":
        score += 20
    elif current == "low":
        score -= 10
    
    # Map score to priority
    if score >= 50:
        return "critical"
    elif score >= 30:
        return "high"
    elif score >= 10:
        return "medium"
    else:
        return "low"


@app.get("/api/data-quality/preview/{cleanup_type}")
async def preview_cleanup(cleanup_type: str):
    if cleanup_type == "ancient":
        tasks = store.query(
            "SELECT * FROM tasks WHERE created_at < datetime('now', '-90 days') AND status = 'pending' LIMIT 20"
        )
    elif cleanup_type == "stale":
        tasks = store.query(
            "SELECT * FROM tasks WHERE updated_at < datetime('now', '-30 days') AND status != 'done' LIMIT 20"
        )
    else:
        raise HTTPException(status_code=400, detail="Unknown cleanup type")
    
    return {"tasks": [dict(t) for t in tasks]}


# =============================================================================
# TEAM
# =============================================================================

@app.get("/api/team")
async def get_team():
    members = store.query("SELECT * FROM team_members ORDER BY name")
    
    result = []
    for m in members:
        member = dict(m)
        member["task_count"] = store.count("tasks", f"assignee = '{m.get('id')}'")
        result.append(member)
    
    return {"team": result}


@app.get("/api/projects")
async def get_projects(status: Optional[str] = None):
    query = "SELECT * FROM projects"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC"
    projects = store.query(query, params) if params else store.query(query)
    
    return {"projects": [dict(p) for p in projects]}


# =============================================================================
# CALENDAR
# =============================================================================

@app.get("/api/calendar")
async def api_calendar(start: Optional[str] = None, end: Optional[str] = None, view: str = "week"):
    from datetime import datetime, timedelta
    
    if start is None:
        start = datetime.now().strftime("%Y-%m-%d")
    
    if end is None:
        if view == "day":
            end = start
        elif view == "week":
            end = (datetime.fromisoformat(start) + timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            end = (datetime.fromisoformat(start) + timedelta(days=30)).strftime("%Y-%m-%d")
    
    events = store.query(
        "SELECT * FROM events WHERE date(start_time) BETWEEN ? AND ? ORDER BY start_time",
        [start, end]
    )
    
    return {"events": [dict(e) for e in events]}


@app.get("/api/delegations")
async def api_delegations():
    delegations = store.query(
        "SELECT * FROM delegations ORDER BY created_at DESC LIMIT 50"
    )
    return {"delegations": [dict(d) for d in delegations]}


@app.get("/api/inbox")
async def api_inbox(limit: int = 50):
    items = store.query(
        "SELECT * FROM inbox WHERE processed = 0 ORDER BY created_at DESC LIMIT ?",
        [limit]
    )
    return {"items": [dict(i) for i in items]}


@app.get("/api/insights")
async def api_insights(limit: int = 20):
    insights = store.query(
        "SELECT * FROM insights ORDER BY created_at DESC LIMIT ?",
        [limit]
    )
    return {"insights": [dict(i) for i in insights]}


@app.get("/api/decisions")
async def api_decisions(limit: int = 20):
    decisions = store.query(
        "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?",
        [limit]
    )
    return {"decisions": [dict(d) for d in decisions]}


# =============================================================================
# PRIORITIES
# =============================================================================

@app.post("/api/priorities/{item_id}/complete")
async def api_priority_complete(item_id: str):
    # Could be a task or other item
    task = store.get("tasks", item_id)
    if task:
        store.update("tasks", item_id, {"status": "done"})
        return {"status": "completed", "type": "task"}
    
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/priorities/{item_id}/snooze")
async def api_priority_snooze(item_id: str, hours: int = 1):
    from datetime import datetime, timedelta
    
    task = store.get("tasks", item_id)
    if task:
        snooze_until = (datetime.now() + timedelta(hours=hours)).isoformat()
        store.update("tasks", item_id, {"snoozed_until": snooze_until})
        return {"status": "snoozed", "until": snooze_until}
    
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/priorities/{item_id}/delegate")
async def api_priority_delegate(item_id: str, to: str):
    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Item not found")
    
    previous = task.get("assignee")
    store.update("tasks", item_id, {"assignee": to})
    store.insert("delegations", {
        "task_id": item_id,
        "from_user": previous,
        "to_user": to,
        "type": "delegate",
    })
    
    return {"status": "delegated", "to": to}


@app.post("/api/decisions/{decision_id}")
async def api_decision(decision_id: str, action: ApprovalAction):
    decision = store.get("decisions", decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    if action.action == "approve":
        store.update("decisions", decision_id, {"approved": True})
    elif action.action == "reject":
        store.update("decisions", decision_id, {"approved": False})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {"status": action.action + "d", "decision_id": decision_id}


# =============================================================================
# BUNDLES (CHANGE MANAGEMENT)
# =============================================================================

@app.get("/api/bundles")
async def api_bundles(status: Optional[str] = None, type: Optional[str] = None, limit: int = 50):
    return {"bundles": list_bundles(status=status, type=type, limit=limit)}


@app.get("/api/bundles/rollbackable")
async def api_bundles_rollbackable():
    return {"bundles": list_rollbackable_bundles()}


@app.get("/api/bundles/summary")
async def get_bundles_summary():
    all_bundles = list_bundles()
    
    by_status = {}
    by_type = {}
    
    for b in all_bundles:
        s = b.get("status", "unknown")
        t = b.get("type", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1
    
    return {
        "total": len(all_bundles),
        "by_status": by_status,
        "by_type": by_type,
    }


@app.post("/api/bundles/rollback-last")
async def rollback_last_bundle(type: Optional[str] = None):
    rollbackable = list_rollbackable_bundles()
    
    if type:
        rollbackable = [b for b in rollbackable if b.get("type") == type]
    
    if not rollbackable:
        raise HTTPException(status_code=404, detail="No rollbackable bundles found")
    
    last = rollbackable[0]
    result = rollback_bundle(last["id"])
    
    return {"status": "rolled_back", "bundle": result}


@app.get("/api/bundles/{bundle_id}")
async def api_bundle_get(bundle_id: str):
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return bundle


@app.post("/api/bundles/{bundle_id}/rollback")
async def api_bundle_rollback(bundle_id: str):
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    
    result = rollback_bundle(bundle_id)
    return {"status": "rolled_back", "bundle": result}


# =============================================================================
# CALIBRATION
# =============================================================================

calibration_engine = CalibrationEngine(store=store)


@app.get("/api/calibration")
async def api_calibration_last():
    return calibration_engine.get_last_calibration()


@app.post("/api/calibration/run")
async def api_calibration_run():
    return calibration_engine.run()


# =============================================================================
# FEEDBACK
# =============================================================================

class FeedbackRequest(BaseModel):
    type: str
    content: str
    context: Optional[dict] = None


@app.post("/api/feedback")
async def api_feedback(feedback: FeedbackRequest):
    feedback_id = store.insert("feedback", {
        "type": feedback.type,
        "content": feedback.content,
        "context": json.dumps(feedback.context) if feedback.context else None,
    })
    
    return {"status": "received", "feedback_id": feedback_id}


# =============================================================================
# PRIORITIES (ADVANCED)
# =============================================================================

@app.get("/api/priorities")
async def get_priorities(limit: int = 20, lane: Optional[str] = None):
    if hasattr(analyzers, "priority_analyzer"):
        priorities = analyzers.priority_analyzer.analyze()
    else:
        priorities = []
    
    if lane:
        priorities = [p for p in priorities if p.get("lane") == lane]
    
    priorities = sorted(priorities, key=lambda x: x.get("score", 0), reverse=True)[:limit]
    
    return {"priorities": priorities}


@app.post("/api/priorities/{item_id}/complete")
async def complete_item(item_id: str):
    task = store.get("tasks", item_id)
    if task:
        store.update("tasks", item_id, {"status": "done"})
        return {"status": "completed"}
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/priorities/{item_id}/snooze")
async def snooze_item(item_id: str, hours: int = 4):
    from datetime import datetime, timedelta
    
    snooze_until = (datetime.now() + timedelta(hours=hours)).isoformat()
    task = store.get("tasks", item_id)
    if task:
        store.update("tasks", item_id, {"snoozed_until": snooze_until})
        return {"status": "snoozed", "until": snooze_until}
    raise HTTPException(status_code=404, detail="Item not found")


class DelegateAction(BaseModel):
    to: str
    reason: Optional[str] = None


@app.post("/api/priorities/{item_id}/delegate")
async def delegate_item(item_id: str, action: DelegateAction):
    task = store.get("tasks", item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Item not found")
    
    store.update("tasks", item_id, {"assignee": action.to})
    store.insert("delegations", {
        "task_id": item_id,
        "to_user": action.to,
        "reason": action.reason,
    })
    
    return {"status": "delegated", "to": action.to}


@app.get("/api/priorities/filtered")
async def get_priorities_filtered(
    lane: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 50
):
    query = "SELECT * FROM tasks WHERE status != 'done' AND status != 'archived'"
    params = []
    
    if lane:
        query += " AND lane = ?"
        params.append(lane)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if status:
        query += " AND status = ?"
        params.append(status)
    if assignee:
        query += " AND assignee = ?"
        params.append(assignee)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    tasks = store.query(query, params)
    
    # Filter by tags if provided
    if tags:
        tag_list = tags.split(",")
        tasks = [t for t in tasks if has_tags(t, tag_list)]
    
    def get_reasons(task):
        reasons = []
        if task.get("due_date"):
            from datetime import datetime
            try:
                due = datetime.fromisoformat(task["due_date"])
                days = (due - datetime.now()).days
                if days < 0:
                    reasons.append(f"Overdue by {-days} days")
                elif days <= 1:
                    reasons.append("Due very soon")
            except:
                pass
        if task.get("priority") == "critical":
            reasons.append("Critical priority")
        return reasons
    
    result = []
    for t in tasks:
        item = dict(t)
        item["reasons"] = get_reasons(t)
        result.append(item)
    
    return {"items": result}


def has_tags(task, tag_list):
    task_tags = task.get("tags", [])
    if isinstance(task_tags, str):
        task_tags = task_tags.split(",")
    return any(t in task_tags for t in tag_list)


class BulkAction(BaseModel):
    action: str
    item_ids: list
    params: Optional[dict] = None


@app.post("/api/priorities/bulk")
async def bulk_action(request: BulkAction):
    results = []
    
    for item_id in request.item_ids:
        try:
            if request.action == "complete":
                store.update("tasks", item_id, {"status": "done"})
                results.append({"id": item_id, "status": "completed"})
            elif request.action == "archive":
                store.update("tasks", item_id, {"status": "archived"})
                results.append({"id": item_id, "status": "archived"})
            elif request.action == "snooze":
                from datetime import datetime, timedelta
                hours = request.params.get("hours", 4) if request.params else 4
                until = (datetime.now() + timedelta(hours=hours)).isoformat()
                store.update("tasks", item_id, {"snoozed_until": until})
                results.append({"id": item_id, "status": "snoozed"})
            elif request.action == "delegate":
                to = request.params.get("to") if request.params else None
                if to:
                    store.update("tasks", item_id, {"assignee": to})
                    results.append({"id": item_id, "status": "delegated"})
                else:
                    results.append({"id": item_id, "error": "No delegate target"})
            else:
                results.append({"id": item_id, "error": "Unknown action"})
        except Exception as e:
            results.append({"id": item_id, "error": str(e)})
    
    return {"results": results}


class SavedFilter(BaseModel):
    name: str
    criteria: dict


@app.get("/api/filters")
async def get_saved_filters():
    filters = store.query("SELECT * FROM saved_filters ORDER BY name")
    return {"filters": [dict(f) for f in filters]}


@app.get("/api/priorities/advanced")
async def advanced_filter(
    lane: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
    created_before: Optional[str] = None,
    created_after: Optional[str] = None,
    sort_by: str = "score",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0
):
    query = "SELECT * FROM tasks WHERE status != 'done' AND status != 'archived'"
    params = []
    
    if lane:
        query += " AND lane = ?"
        params.append(lane)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if status:
        query += " AND status = ?"
        params.append(status)
    if assignee:
        query += " AND assignee = ?"
        params.append(assignee)
    if due_before:
        query += " AND due_date <= ?"
        params.append(due_before)
    if due_after:
        query += " AND due_date >= ?"
        params.append(due_after)
    if created_before:
        query += " AND created_at <= ?"
        params.append(created_before)
    if created_after:
        query += " AND created_at >= ?"
        params.append(created_after)
    
    # Sorting
    if sort_by == "score":
        # Can't sort by computed score in SQL, will sort in Python
        pass
    elif sort_by in ["created_at", "updated_at", "due_date", "priority"]:
        query += f" ORDER BY {sort_by} {'DESC' if sort_dir == 'desc' else 'ASC'}"
    
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    tasks = store.query(query, params)
    
    # Compute scores and sort if needed
    def compute_score(t):
        s = 0
        if t.get("priority") == "critical":
            s += 40
        elif t.get("priority") == "high":
            s += 20
        if t.get("due_date"):
            from datetime import datetime
            try:
                days = (datetime.fromisoformat(t["due_date"]) - datetime.now()).days
                if days < 0:
                    s += 50
                elif days <= 3:
                    s += 30
            except:
                pass
        return s
    
    result = []
    for t in tasks:
        item = dict(t)
        item["score"] = compute_score(t)
        result.append(item)
    
    if sort_by == "score":
        result.sort(key=lambda x: x["score"], reverse=(sort_dir == "desc"))
    
    return {"items": result, "total": len(result)}


@app.post("/api/priorities/archive-stale")
async def archive_stale(days: int = 14):
    tasks = store.query(
        "SELECT * FROM tasks WHERE updated_at < datetime('now', ? || ' days') AND status != 'done'",
        [f"-{days}"]
    )
    
    archived = 0
    for t in tasks:
        store.update("tasks", t.get("id"), {"status": "archived"})
        archived += 1
    
    return {"archived": archived}


# =============================================================================
# EVENTS / DAY / WEEK
# =============================================================================

@app.get("/api/events")
async def get_events(hours: int = 24):
    from datetime import datetime, timedelta
    
    start = datetime.now().isoformat()
    end = (datetime.now() + timedelta(hours=hours)).isoformat()
    
    events = store.query(
        "SELECT * FROM events WHERE start_time BETWEEN ? AND ? ORDER BY start_time",
        [start, end]
    )
    
    return {"events": [dict(e) for e in events]}


@app.get("/api/day/{date}")
async def get_day_analysis(date: Optional[str] = None):
    from datetime import datetime
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Get all relevant data for the day
    events = store.query("SELECT * FROM events WHERE date(start_time) = ?", [date])
    blocks = store.query("SELECT * FROM time_blocks WHERE date(start_time) = ?", [date])
    tasks_due = store.query("SELECT * FROM tasks WHERE due_date = ?", [date])
    
    return {
        "date": date,
        "events": [dict(e) for e in events],
        "time_blocks": [dict(b) for b in blocks],
        "tasks_due": [dict(t) for t in tasks_due],
    }


@app.get("/api/week")
async def get_week_analysis():
    from datetime import datetime, timedelta
    
    today = datetime.now()
    start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    end = (today + timedelta(days=6 - today.weekday())).strftime("%Y-%m-%d")
    
    events = store.query(
        "SELECT * FROM events WHERE date(start_time) BETWEEN ? AND ? ORDER BY start_time",
        [start, end]
    )
    
    return {
        "week_start": start,
        "week_end": end,
        "events": [dict(e) for e in events],
    }


# =============================================================================
# EMAILS
# =============================================================================

@app.get("/api/emails")
async def get_emails(unread_only: bool = False, actionable_only: bool = False, limit: int = 30):
    query = "SELECT * FROM emails WHERE 1=1"
    
    if unread_only:
        query += " AND read = 0"
    if actionable_only:
        query += " AND actionable = 1"
    
    query += f" ORDER BY received_at DESC LIMIT {limit}"
    
    emails = store.query(query)
    return {"emails": [dict(e) for e in emails]}


@app.post("/api/emails/{email_id}/mark-actionable")
async def mark_email_actionable(email_id: str):
    email = store.get("emails", email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    store.update("emails", email_id, {"actionable": True})
    return {"status": "marked_actionable"}


# =============================================================================
# INSIGHTS / ANOMALIES
# =============================================================================

@app.get("/api/insights")
async def get_insights(type: Optional[str] = None):
    query = "SELECT * FROM insights"
    params = []
    
    if type:
        query += " WHERE type = ?"
        params.append(type)
    
    query += " ORDER BY created_at DESC LIMIT 50"
    
    insights = store.query(query, params) if params else store.query(query)
    return {"insights": [dict(i) for i in insights]}


@app.get("/api/anomalies")
async def get_anomalies():
    anomalies = store.query(
        "SELECT * FROM insights WHERE type = 'anomaly' ORDER BY created_at DESC LIMIT 20"
    )
    return {"anomalies": [dict(a) for a in anomalies]}


# =============================================================================
# NOTIFICATIONS
# =============================================================================

@app.get("/api/notifications")
async def get_notifications():
    notifications = store.query(
        "SELECT * FROM notifications WHERE dismissed = 0 ORDER BY created_at DESC LIMIT 50"
    )
    return {"notifications": [dict(n) for n in notifications]}


@app.get("/api/notifications/stats")
async def get_notification_stats():
    total = store.count("notifications", "dismissed = 0")
    by_type = store.query(
        "SELECT type, COUNT(*) as count FROM notifications WHERE dismissed = 0 GROUP BY type"
    )
    
    return {
        "total": total,
        "by_type": {r["type"]: r["count"] for r in by_type},
    }


@app.post("/api/notifications/{notif_id}/dismiss")
async def dismiss_notification(notif_id: str):
    store.update("notifications", notif_id, {"dismissed": True})
    return {"status": "dismissed"}


@app.post("/api/notifications/dismiss-all")
async def dismiss_all_notifications():
    store.execute("UPDATE notifications SET dismissed = 1 WHERE dismissed = 0")
    return {"status": "all_dismissed"}


# =============================================================================
# APPROVALS
# =============================================================================

@app.get("/api/approvals")
async def get_approvals():
    approvals = store.query(
        "SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC"
    )
    return {"approvals": [dict(a) for a in approvals]}


@app.post("/api/approvals/{decision_id}")
async def process_approval(decision_id: str, action: ApprovalAction):
    decision = store.get("decisions", decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    approved = action.action == "approve"
    store.update("decisions", decision_id, {"approved": approved})
    
    return {"status": "processed", "approved": approved}


class ModifyApproval(BaseModel):
    modifications: dict


@app.post("/api/approvals/{decision_id}/modify")
async def modify_approval(decision_id: str, request: ModifyApproval):
    decision = store.get("decisions", decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    store.update("decisions", decision_id, request.modifications)
    return {"status": "modified"}


# =============================================================================
# GOVERNANCE
# =============================================================================

@app.get("/api/governance")
async def get_governance_status():
    return governance.get_status()


@app.post("/api/governance/{domain}")
async def set_governance_mode(domain: str, mode: ModeChange):
    try:
        domain_mode = DomainMode(mode.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode.mode}")
    
    governance.set_mode(domain, domain_mode)
    return {"status": "updated", "domain": domain, "mode": mode.mode}


@app.post("/api/governance/{domain}/threshold")
async def set_governance_threshold(domain: str, threshold: float):
    governance.set_threshold(domain, threshold)
    return {"status": "updated", "domain": domain, "threshold": threshold}


@app.get("/api/governance/history")
async def get_governance_history():
    return governance.get_history()


@app.post("/api/governance/emergency-brake")
async def emergency_brake():
    governance.emergency_stop()
    return {"status": "emergency_brake_engaged"}


@app.get("/api/governance/emergency-brake")
async def get_emergency_brake_status():
    return {"engaged": governance.is_stopped()}


# =============================================================================
# SYNC
# =============================================================================

@app.get("/api/sync/status")
async def get_sync_status():
    return collectors.get_status()


@app.post("/api/sync")
async def trigger_sync():
    result = collectors.sync_all()
    return {"status": "synced", "result": result}


@app.post("/api/analyze")
async def trigger_analyze():
    result = analyzers.analyze_all()
    return {"status": "analyzed", "result": result}


@app.post("/api/cycle")
async def run_cycle():
    sync_result = collectors.sync_all()
    analyze_result = analyzers.analyze_all()
    return {
        "status": "cycle_complete",
        "sync": sync_result,
        "analyze": analyze_result,
    }


# =============================================================================
# STATUS / HEALTH
# =============================================================================

@app.get("/api/status")
async def get_status():
    return {
        "status": "ok",
        "store": "connected",
        "collectors": collectors.get_status(),
        "analyzers": "ready",
    }


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/summary")
async def get_summary():
    return {
        "tasks": {
            "total": store.count("tasks"),
            "pending": store.count("tasks", "status = 'pending'"),
            "done": store.count("tasks", "status = 'done'"),
        },
        "events": {
            "today": store.count("events", f"date(start_time) = '{datetime.now().strftime('%Y-%m-%d')}'"),
        },
        "decisions": {
            "pending": store.count("decisions", "approved IS NULL"),
        },
    }


@app.get("/api/search")
async def search(q: str, limit: int = 20):
    # Search across multiple tables
    tasks = store.query(
        "SELECT 'task' as type, id, title as name FROM tasks WHERE title LIKE ? LIMIT ?",
        [f"%{q}%", limit]
    )
    projects = store.query(
        "SELECT 'project' as type, id, name FROM projects WHERE name LIKE ? LIMIT ?",
        [f"%{q}%", limit]
    )
    clients = store.query(
        "SELECT 'client' as type, id, name FROM clients WHERE name LIKE ? LIMIT ?",
        [f"%{q}%", limit]
    )
    
    results = [dict(r) for r in tasks] + [dict(r) for r in projects] + [dict(r) for r in clients]
    return {"results": results[:limit]}


@app.get("/api/team/workload")
async def get_team_workload():
    members = store.query("SELECT * FROM team_members")
    
    workload = []
    for m in members:
        member_id = m.get("id")
        tasks = store.count("tasks", f"assignee = '{member_id}' AND status != 'done'")
        workload.append({
            "member": dict(m),
            "active_tasks": tasks,
        })
    
    return {"workload": workload}


@app.get("/api/priorities/grouped")
async def get_priorities_grouped():
    if hasattr(analyzers, "priority_analyzer"):
        priorities = analyzers.priority_analyzer.analyze()
    else:
        priorities = []
    
    by_lane = {}
    by_priority = {}
    
    for p in priorities:
        lane = p.get("lane", "unknown")
        prio = p.get("priority", "medium")
        
        if lane not in by_lane:
            by_lane[lane] = []
        by_lane[lane].append(p)
        
        if prio not in by_priority:
            by_priority[prio] = []
        by_priority[prio].append(p)
    
    return {
        "by_lane": by_lane,
        "by_priority": by_priority,
    }


@app.get("/api/clients")
async def get_clients():
    clients = store.query("SELECT * FROM clients ORDER BY name")
    return {"clients": [dict(c) for c in clients]}


# =============================================================================
# ADDITIONAL CLIENT ENDPOINTS
# =============================================================================

@app.get("/api/clients/portfolio")
async def get_clients_portfolio():
    clients = store.query("SELECT * FROM clients ORDER BY name")
    
    portfolio = []
    for c in clients:
        client = dict(c)
        client["projects"] = store.count("projects", f"client_id = '{c.get('id')}'")
        client["tasks"] = store.count("tasks", f"client_id = '{c.get('id')}'")
        portfolio.append(client)
    
    return {"portfolio": portfolio}


@app.get("/api/clients/{client_id}")
async def get_client(client_id: str):
    client = store.get("clients", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return dict(client)


# =============================================================================
# ADDITIONAL PROJECT ENDPOINTS
# =============================================================================

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    project = store.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(project)


@app.get("/api/projects/candidates")
async def get_project_candidates():
    # Find potential projects from task patterns
    candidates = store.query(
        """SELECT DISTINCT project_name, COUNT(*) as task_count 
           FROM tasks 
           WHERE project_id IS NULL AND project_name IS NOT NULL 
           GROUP BY project_name 
           HAVING task_count >= 3
           ORDER BY task_count DESC"""
    )
    return {"candidates": [dict(c) for c in candidates]}


@app.post("/api/projects/detect")
async def detect_projects():
    # Auto-detect projects from task patterns
    candidates = store.query(
        """SELECT DISTINCT project_name, COUNT(*) as task_count 
           FROM tasks 
           WHERE project_id IS NULL AND project_name IS NOT NULL 
           GROUP BY project_name 
           HAVING task_count >= 3"""
    )
    return {"detected": len(candidates), "candidates": [dict(c) for c in candidates]}


@app.get("/api/projects/enrolled")
async def get_enrolled_projects():
    projects = store.query(
        "SELECT * FROM projects WHERE status = 'active' ORDER BY name"
    )
    return {"projects": [dict(p) for p in projects]}


@app.post("/api/projects/propose")
async def propose_project(name: str, description: str = ""):
    project_id = store.insert("projects", {
        "name": name,
        "description": description,
        "status": "proposed",
    })
    return {"status": "proposed", "project_id": project_id}


@app.post("/api/projects/{project_id}/enrollment")
async def enroll_project(project_id: str, action: str = "enroll"):
    project = store.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if action == "enroll":
        store.update("projects", project_id, {"status": "active"})
    elif action == "unenroll":
        store.update("projects", project_id, {"status": "inactive"})
    
    return {"status": action + "ed", "project_id": project_id}


# =============================================================================
# ADDITIONAL TASK ENDPOINTS
# =============================================================================

@app.post("/api/tasks/link")
async def link_tasks(task_id: str, related_id: str, relation: str = "related"):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    store.insert("task_links", {
        "task_id": task_id,
        "related_id": related_id,
        "relation": relation,
    })
    
    return {"status": "linked"}


@app.post("/api/tasks/{task_id}/block")
async def add_blocker(task_id: str, blocker_id: str, reason: str = ""):
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    store.insert("task_blockers", {
        "task_id": task_id,
        "blocker_id": blocker_id,
        "reason": reason,
    })
    
    store.update("tasks", task_id, {"status": "blocked"})
    
    return {"status": "blocked", "blocker_id": blocker_id}


@app.delete("/api/tasks/{task_id}/block/{blocker_id}")
async def remove_blocker(task_id: str, blocker_id: str):
    store.delete_where("task_blockers", f"task_id = '{task_id}' AND blocker_id = '{blocker_id}'")
    
    # Check if still blocked
    remaining = store.count("task_blockers", f"task_id = '{task_id}'")
    if remaining == 0:
        store.update("tasks", task_id, {"status": "pending"})
    
    return {"status": "unblocked"}


# =============================================================================
# DEPENDENCIES
# =============================================================================

@app.get("/api/dependencies")
async def get_dependencies():
    deps = store.query(
        """SELECT t.id, t.title, t.status, 
                  tb.blocker_id, bt.title as blocker_title
           FROM tasks t
           LEFT JOIN task_blockers tb ON t.id = tb.task_id
           LEFT JOIN tasks bt ON tb.blocker_id = bt.id
           WHERE tb.blocker_id IS NOT NULL
           ORDER BY t.created_at DESC"""
    )
    return {"dependencies": [dict(d) for d in deps]}


# =============================================================================
# WEEKLY DIGEST
# =============================================================================

@app.get("/api/digest/weekly")
async def get_weekly_digest():
    from datetime import datetime, timedelta
    
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Tasks completed this week
    completed = store.query(
        "SELECT * FROM tasks WHERE status = 'done' AND updated_at >= ?",
        [week_ago]
    )
    
    # Tasks created this week
    created = store.query(
        "SELECT * FROM tasks WHERE created_at >= ?",
        [week_ago]
    )
    
    # Time logged this week
    time_blocks = store.query(
        "SELECT * FROM time_blocks WHERE date(start_time) >= ?",
        [week_ago]
    )
    total_minutes = sum(b.get("duration_minutes", 0) for b in time_blocks)
    
    # Decisions made
    decisions = store.query(
        "SELECT * FROM decisions WHERE approved IS NOT NULL AND updated_at >= ?",
        [week_ago]
    )
    
    return {
        "period": {"start": week_ago, "end": datetime.now().strftime("%Y-%m-%d")},
        "tasks": {
            "completed": len(completed),
            "created": len(created),
        },
        "time": {
            "total_minutes": total_minutes,
            "total_hours": round(total_minutes / 60, 1),
        },
        "decisions": len(decisions),
    }


# =============================================================================
# ADDITIONAL EMAIL ENDPOINT
# =============================================================================

@app.post("/api/emails/{email_id}/dismiss")
async def dismiss_email(email_id: str):
    email = store.get("emails", email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    store.update("emails", email_id, {"dismissed": True})
    return {"status": "dismissed"}


# =============================================================================
# SYNC XERO
# =============================================================================

@app.post("/api/sync/xero")
async def sync_xero():
    if hasattr(collectors, "xero_collector"):
        result = collectors.xero_collector.sync()
        return {"status": "synced", "result": result}
    return {"status": "xero_not_configured"}


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8420)
