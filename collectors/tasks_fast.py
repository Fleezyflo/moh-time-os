#!/usr/bin/env python3
"""Fast Google Tasks collector - only gets Main list."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "out"

# Main task list ID (cached to avoid extra API call)
MAIN_LIST_ID = "c0VUdndncDZlYU9zM3FWRA"


def get_tasks(list_id: str = MAIN_LIST_ID) -> list:
    """Get incomplete tasks from a list."""
    cmd = ["gog", "tasks", "list", list_id, "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        # Filter to incomplete only
        tasks = data.get("tasks", [])
        return [t for t in tasks if t.get("status") != "completed"]
    except:
        return []


def collect_tasks() -> dict:
    """Fetch incomplete tasks from main list."""
    now = datetime.now(timezone.utc)
    tasks = get_tasks()
    
    return {
        "collected_at": now.isoformat(),
        "list_id": MAIN_LIST_ID,
        "tasks": tasks
    }


def save(data: dict, filename: str = "tasks-main.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


if __name__ == "__main__":
    data = collect_tasks()
    path = save(data)
    print(f"Saved {len(data.get('tasks', []))} tasks to {path}")
