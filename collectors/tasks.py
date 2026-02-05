#!/usr/bin/env python3
"""Collect Google Tasks."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "out"


def get_task_lists() -> list:
    """Get all task lists."""
    cmd = ["gog", "tasks", "lists", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    data = json.loads(result.stdout)
    return data.get("tasklists", [])


def get_tasks(list_id: str) -> list:
    """Get tasks from a specific list."""
    cmd = ["gog", "tasks", "list", list_id, "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    data = json.loads(result.stdout)
    return data.get("tasks", [])


def collect_tasks() -> dict:
    """Fetch all tasks from all lists (parallel)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    now = datetime.now(timezone.utc)
    task_lists = get_task_lists()
    all_tasks = []
    
    def fetch_list_tasks(tl):
        list_id = tl.get("id")
        list_name = tl.get("title", "Unknown")
        tasks = get_tasks(list_id)
        for task in tasks:
            task["_list_id"] = list_id
            task["_list_name"] = list_name
        return tasks
    
    # Fetch all lists in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_list_tasks, tl) for tl in task_lists]
        for future in as_completed(futures):
            try:
                all_tasks.extend(future.result())
            except Exception:
                pass
    
    return {
        "collected_at": now.isoformat(),
        "lists": task_lists,
        "tasks": all_tasks
    }


def save(data: dict, filename: str = "tasks-all.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


if __name__ == "__main__":
    data = collect_tasks()
    path = save(data)
    print(f"Saved {len(data.get('tasks', []))} tasks from {len(data.get('lists', []))} lists to {path}")
