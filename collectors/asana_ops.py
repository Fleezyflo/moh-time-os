#!/usr/bin/env python3
"""
Asana Operational Intelligence collector.

Surfaces:
- Overdue tasks
- Blocked/stalled tasks (no activity in 7+ days)  
- Tasks missing assignee
- Tasks missing due date
- Workflow hygiene issues
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, date, timezone
from typing import Optional

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from engine.asana_client import (
    list_workspaces, list_projects, list_tasks_in_project,
    list_sections, asana_get
)

# hrmny workspace GID
HRMNY_WORKSPACE_GID = "1148006162435561"

# Stale threshold (days without update)
STALE_DAYS = 7


def get_all_incomplete_tasks(limit_projects: int = 20) -> list:
    """Get all incomplete tasks across projects."""
    all_tasks = []
    
    try:
        projects = list_projects(HRMNY_WORKSPACE_GID, archived=False)
        
        for proj in projects[:limit_projects]:
            proj_gid = proj.get("gid")
            proj_name = proj.get("name", "Unknown")
            
            try:
                tasks = list_tasks_in_project(proj_gid, completed=False)
                
                for task in tasks:
                    task["_project_name"] = proj_name
                    task["_project_gid"] = proj_gid
                    all_tasks.append(task)
            except Exception as e:
                print(f"Error fetching tasks from {proj_name}: {e}")
                continue
                
    except Exception as e:
        print(f"Error listing projects: {e}")
    
    return all_tasks


def get_task_details(task_gid: str) -> dict:
    """Get full task details including modified_at."""
    try:
        data = asana_get(
            f"tasks/{task_gid}",
            params={"opt_fields": "name,completed,due_on,assignee,assignee.name,modified_at,notes,tags,tags.name"}
        )
        return data.get("data", {})
    except:
        return {}


def analyze_tasks(tasks: list) -> dict:
    """
    Analyze tasks for operational issues.
    
    Returns dict with:
    - overdue: tasks past due date
    - stale: tasks not updated in 7+ days
    - no_assignee: tasks without assignee
    - no_due_date: tasks without due date
    """
    today = date.today()
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    
    results = {
        "overdue": [],
        "stale": [],
        "no_assignee": [],
        "no_due_date": [],
    }
    
    for task in tasks:
        task_name = task.get("name", "").strip()
        if not task_name:
            continue
            
        project_name = task.get("_project_name", "")
        assignee = task.get("assignee")
        assignee_name = assignee.get("name") if assignee else None
        due_on = task.get("due_on")
        task_gid = task.get("gid")
        
        task_info = {
            "name": task_name,
            "project": project_name,
            "assignee": assignee_name,
            "due": due_on,
            "gid": task_gid,
        }
        
        # Check overdue
        if due_on:
            try:
                due_date = date.fromisoformat(due_on)
                if due_date < today:
                    days_overdue = (today - due_date).days
                    task_info["days_overdue"] = days_overdue
                    results["overdue"].append(task_info)
            except:
                pass
        
        # Check no assignee
        if not assignee:
            results["no_assignee"].append(task_info)
        
        # Check no due date
        if not due_on:
            results["no_due_date"].append(task_info)
    
    # Sort overdue by days
    results["overdue"].sort(key=lambda x: -x.get("days_overdue", 0))
    
    return results


def get_stale_tasks(tasks: list, sample_size: int = 20) -> list:
    """
    Check for stale tasks (not modified in 7+ days).
    Only samples a subset to avoid too many API calls.
    """
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    stale = []
    
    # Sample tasks that have no due date or are not overdue (potential stale candidates)
    candidates = [t for t in tasks if not t.get("due_on")][:sample_size]
    
    for task in candidates:
        task_gid = task.get("gid")
        if not task_gid:
            continue
            
        details = get_task_details(task_gid)
        modified_at = details.get("modified_at")
        
        if modified_at:
            try:
                modified_dt = datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
                if modified_dt < stale_threshold:
                    days_stale = (datetime.now(timezone.utc) - modified_dt).days
                    stale.append({
                        "name": task.get("name", ""),
                        "project": task.get("_project_name", ""),
                        "assignee": details.get("assignee", {}).get("name") if details.get("assignee") else None,
                        "days_stale": days_stale,
                        "gid": task_gid,
                    })
            except:
                pass
    
    stale.sort(key=lambda x: -x.get("days_stale", 0))
    return stale


def generate_asana_report() -> dict:
    """Generate full Asana operational report."""
    print("Fetching Asana tasks...")
    tasks = get_all_incomplete_tasks(limit_projects=15)
    print(f"Found {len(tasks)} incomplete tasks")
    
    print("Analyzing tasks...")
    analysis = analyze_tasks(tasks)
    
    print("Checking for stale tasks...")
    stale = get_stale_tasks(tasks, sample_size=15)
    analysis["stale"] = stale
    
    analysis["total_tasks"] = len(tasks)
    
    return analysis


def format_report(report: dict) -> str:
    """Format report as markdown."""
    lines = [
        "## Asana Operational Status",
        f"Total incomplete tasks: {report['total_tasks']}",
        ""
    ]
    
    # Overdue
    overdue = report.get("overdue", [])
    if overdue:
        lines.append(f"### ⚠️ Overdue Tasks ({len(overdue)})")
        for t in overdue[:10]:
            days = t.get("days_overdue", 0)
            assignee = t.get("assignee") or "unassigned"
            lines.append(f"- {t['name']} ({days}d overdue) — {assignee}")
            lines.append(f"  Project: {t['project']}")
        if len(overdue) > 10:
            lines.append(f"  ... +{len(overdue) - 10} more")
        lines.append("")
    
    # Stale
    stale = report.get("stale", [])
    if stale:
        lines.append(f"### 🔇 Stale Tasks ({len(stale)})")
        for t in stale[:5]:
            days = t.get("days_stale", 0)
            assignee = t.get("assignee") or "unassigned"
            lines.append(f"- {t['name']} ({days}d no activity) — {assignee}")
        if len(stale) > 5:
            lines.append(f"  ... +{len(stale) - 5} more")
        lines.append("")
    
    # No assignee
    no_assignee = report.get("no_assignee", [])
    if no_assignee:
        lines.append(f"### 👤 Missing Assignee ({len(no_assignee)})")
        for t in no_assignee[:5]:
            lines.append(f"- {t['name']}")
            lines.append(f"  Project: {t['project']}")
        if len(no_assignee) > 5:
            lines.append(f"  ... +{len(no_assignee) - 5} more")
        lines.append("")
    
    # No due date
    no_due = report.get("no_due_date", [])
    if no_due:
        lines.append(f"### 📅 Missing Due Date ({len(no_due)})")
        for t in no_due[:5]:
            assignee = t.get("assignee") or "unassigned"
            lines.append(f"- {t['name']} — {assignee}")
        if len(no_due) > 5:
            lines.append(f"  ... +{len(no_due) - 5} more")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_asana_report()
    print("\n" + "=" * 50)
    print(format_report(report))
    
    print("\n--- Summary ---")
    print(f"Overdue: {len(report.get('overdue', []))}")
    print(f"Stale: {len(report.get('stale', []))}")
    print(f"No assignee: {len(report.get('no_assignee', []))}")
    print(f"No due date: {len(report.get('no_due_date', []))}")
