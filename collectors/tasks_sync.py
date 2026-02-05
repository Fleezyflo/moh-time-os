#!/usr/bin/env python3
"""
Google Tasks bidirectional sync for Time OS.

Supports:
- Reading tasks from any list
- Adding new tasks
- Updating existing tasks
- Marking tasks complete/incomplete
- Lane-based routing to appropriate lists
"""

import json
import subprocess
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

# Import lane categorization
try:
    from lanes import categorize_task
except ImportError:
    categorize_task = None

# Task list IDs (from gog tasks lists)
LISTS = {
    "Main": "c0VUdndncDZlYU9zM3FWRA",
    "CS": "M2d5REppZjc1N2M2Z1pxbQ",
    "hrmny mgmt": "N1dYWk1CaHdQajlZM3lkYQ",
    "Personal": "NGMwX3lna3hCdnVNTkwzRg",
    "Moh Flow": "RGJuVjM2SW5nTnYtalVRbA",
    "Hrmny": "MTQyNTA2MjY5MzAwOTQ5NzA5NDU6MDow",
    "TimeOS — Proposals": "b2tJMTI3d2Z3cUFtTFdNUA",
    "TimeOS — Approved": "XzJBTWRIcUEzOTJUM2VfMQ",
    "TimeOS — Rejected": "VDZucDFZanVEd2phd0oydA",
    "TimeOS — Snoozed": "VlZUXzBkeV81TWlkUWRZSg",
}

# Lane to list mapping
LANE_TO_LIST = {
    "Finance": "hrmny mgmt",
    "People": "hrmny mgmt",
    "Creative": "CS",
    "Sales": "CS",
    "Operations": "hrmny mgmt",
    "Personal": "Personal",
    "Uncategorized": "Main",
}


def run_gog(args: list, timeout: int = 30) -> tuple[bool, dict | str]:
    """Run a gog command and return (success, result)."""
    cmd = ["gog"] + args + ["--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr or "Unknown error"
        return True, json.loads(result.stdout) if result.stdout.strip() else {}
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except json.JSONDecodeError as e:
        return False, f"JSON decode error: {e}"


def get_list_id(list_name: str) -> Optional[str]:
    """Get list ID by name."""
    return LISTS.get(list_name)


def list_tasks(list_name: str = "Main", include_completed: bool = False) -> list:
    """
    List all tasks from a given list.
    
    Returns list of task dicts with: id, title, notes, due, status, updated
    """
    list_id = get_list_id(list_name)
    if not list_id:
        return []
    
    args = ["tasks", "list", list_id]
    if include_completed:
        args.append("--show-completed")
    
    success, result = run_gog(args)
    if not success:
        print(f"Error listing tasks: {result}")
        return []
    
    tasks = result.get("tasks", [])
    return [
        {
            "id": t.get("id"),
            "title": t.get("title", ""),
            "notes": t.get("notes", ""),
            "due": t.get("due"),
            "status": t.get("status"),
            "updated": t.get("updated"),
            "list": list_name,
        }
        for t in tasks
    ]


def add_task(
    title: str,
    list_name: str = "Main",
    notes: str = "",
    due: str = "",
    auto_route: bool = True,
) -> Optional[dict]:
    """
    Add a new task.
    
    If auto_route=True, will categorize and route to appropriate list.
    due format: YYYY-MM-DD
    
    Returns created task dict or None on failure.
    """
    # Auto-route based on lane if enabled
    if auto_route and categorize_task:
        cat = categorize_task(title, notes)
        lane = cat.get("lane", "Uncategorized")
        routed_list = LANE_TO_LIST.get(lane, "Main")
        if routed_list != list_name:
            print(f"Auto-routing to '{routed_list}' (lane: {lane})")
            list_name = routed_list
    
    list_id = get_list_id(list_name)
    if not list_id:
        print(f"Unknown list: {list_name}")
        return None
    
    args = ["tasks", "add", list_id, "--title", title]
    if notes:
        args.extend(["--notes", notes])
    if due:
        args.extend(["--due", due])
    
    success, result = run_gog(args)
    if not success:
        print(f"Error adding task: {result}")
        return None
    
    return {
        "id": result.get("id"),
        "title": result.get("title"),
        "list": list_name,
        "status": "needsAction",
    }


def update_task(
    list_name: str,
    task_id: str,
    title: str = None,
    notes: str = None,
    due: str = None,
) -> bool:
    """Update an existing task."""
    list_id = get_list_id(list_name)
    if not list_id:
        return False
    
    args = ["tasks", "update", list_id, task_id]
    if title:
        args.extend(["--title", title])
    if notes is not None:
        args.extend(["--notes", notes])
    if due:
        args.extend(["--due", due])
    
    success, result = run_gog(args)
    return success


def complete_task(list_name: str, task_id: str) -> bool:
    """Mark a task as completed."""
    list_id = get_list_id(list_name)
    if not list_id:
        return False
    
    success, _ = run_gog(["tasks", "done", list_id, task_id])
    return success


def uncomplete_task(list_name: str, task_id: str) -> bool:
    """Mark a task as needs action."""
    list_id = get_list_id(list_name)
    if not list_id:
        return False
    
    success, _ = run_gog(["tasks", "undo", list_id, task_id])
    return success


def delete_task(list_name: str, task_id: str) -> bool:
    """Delete a task."""
    list_id = get_list_id(list_name)
    if not list_id:
        return False
    
    success, _ = run_gog(["tasks", "delete", list_id, task_id, "--force"])
    return success


def get_all_tasks(include_completed: bool = False) -> list:
    """Get tasks from all lists."""
    all_tasks = []
    for list_name in LISTS.keys():
        tasks = list_tasks(list_name, include_completed)
        all_tasks.extend(tasks)
    return all_tasks


def capture_from_text(text: str) -> Optional[dict]:
    """
    Capture a task from natural language text.
    
    Examples:
    - "Follow up with GMG re: invoice by Friday"
    - "Send Ramadan proposal to Dana tomorrow"
    """
    import re
    
    # Extract due date hints
    due = None
    today = datetime.now(timezone.utc)
    
    if "today" in text.lower():
        due = today.strftime("%Y-%m-%d")
    elif "tomorrow" in text.lower():
        from datetime import timedelta
        due = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "friday" in text.lower():
        # Find next Friday
        from datetime import timedelta
        days_ahead = 4 - today.weekday()  # Friday is 4
        if days_ahead <= 0:
            days_ahead += 7
        due = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    
    # Clean up the title
    title = text
    for word in ["by today", "by tomorrow", "by friday", "today", "tomorrow"]:
        title = re.sub(rf"\b{word}\b", "", title, flags=re.IGNORECASE)
    title = " ".join(title.split())  # Clean whitespace
    
    return add_task(title=title, due=due, auto_route=True)


if __name__ == "__main__":
    print("Task Lists:")
    print("-" * 40)
    for name, list_id in LISTS.items():
        print(f"  {name}: {list_id[:12]}...")
    
    print("\nTasks from Main list:")
    print("-" * 40)
    tasks = list_tasks("Main")
    for t in tasks[:5]:
        status = "✓" if t["status"] == "completed" else "○"
        due_str = f" (due: {t['due'][:10]})" if t.get("due") else ""
        print(f"  {status} {t['title'][:50]}{due_str}")
    
    print(f"\n... and {len(tasks) - 5} more" if len(tasks) > 5 else "")
