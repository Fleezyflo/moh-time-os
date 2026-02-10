#!/usr/bin/env python3
"""
MOH Time OS — Google Tasks Integration

Projection with MOHOS/v1 encoding and idempotent updates.
"""

import json
import logging
import subprocess

from ..change_bundles import create_task_bundle
from ..config_store import get
from ..governance import can_write, get_domain_mode
from ..routing_engine import route_item

logger = logging.getLogger(__name__)

# Task list cache
_task_lists_cache = None


def get_task_lists() -> list[dict]:
    """Get all Google Tasks lists."""
    global _task_lists_cache

    if _task_lists_cache:
        return _task_lists_cache

    cmd = ["gog", "tasks", "lists", "--json"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            _task_lists_cache = data.get("tasklists", [])
            return _task_lists_cache
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not fetch task lists: {e}")

    return []


def find_list_id(list_name: str) -> str | None:
    """Find a task list ID by name."""
    lists = get_task_lists()

    for lst in lists:
        if lst.get("title", "").lower() == list_name.lower():
            return lst.get("id")

    return None


def get_tasks(list_id: str) -> list[dict]:
    """Get tasks from a specific list."""
    cmd = ["gog", "tasks", "list", list_id, "--json"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("tasks", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not fetch tasks from list {list_id}: {e}")

    return []


def find_by_dedupe_key(dedupe_key: str, list_id: str = None) -> dict | None:
    """Find a task by its dedupe key in notes."""
    lists_to_check = []

    lists_to_check = (
        [list_id] if list_id else [lst.get("id") for lst in get_task_lists()]
    )

    for lid in lists_to_check:
        tasks = get_tasks(lid)
        for task in tasks:
            notes = task.get("notes", "")
            if f"dedupe_key: {dedupe_key}" in notes:
                return {"task": task, "list_id": lid}

    return None


def create_task(
    item: dict,
    list_name: str = None,
) -> tuple[bool, str]:
    """
    Create a Google Task from an item.

    Uses MOHOS/v1 notes format and respects domain mode.
    """
    # Check domain mode
    if not can_write("tasks"):
        mode = get_domain_mode("tasks")
        return False, f"Tasks domain is in {mode.value} mode. Cannot create tasks."

    # Route item to determine destination
    routing = route_item(item)
    dest_list = list_name or routing["destination_list"]

    # Find list ID
    list_id = find_list_id(dest_list)
    if not list_id:
        return False, f"Task list not found: {dest_list}"

    # Check for existing task with same dedupe key
    dedupe_key = routing["dedupe_key"]
    existing = find_by_dedupe_key(dedupe_key, list_id)

    if existing:
        # Update instead of create
        return update_task(existing["task"]["id"], existing["list_id"], item)

    # Create change bundle
    bundle = create_task_bundle(
        description=f"Create task: {routing['title']}",
        creates=[
            {
                "id": dedupe_key,
                "title": routing["title"],
                "notes": routing["notes"],
                "due": routing.get("due"),
            }
        ],
    )

    # Execute via gog CLI
    cmd = [
        "gog",
        "tasks",
        "add",
        list_id,
        "--title",
        routing["title"],
        "--notes",
        routing["notes"],
    ]

    if routing.get("due"):
        cmd.extend(["--due", routing["due"]])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            from ..change_bundles import mark_applied

            mark_applied(bundle["id"])
            return True, f"Task created in {dest_list}"
        from ..change_bundles import mark_failed

        mark_failed(bundle["id"], result.stderr)
        return False, f"Failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout creating task: {routing['title']}")
        return False, "Error: Task creation timed out"
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Subprocess error creating task: {e}")
        return False, f"Error: {e}"


def update_task(
    task_id: str,
    list_id: str,
    item: dict,
) -> tuple[bool, str]:
    """Update an existing task."""
    if not can_write("tasks"):
        return False, "Tasks domain not in Execute mode"

    # Get current task for pre-image
    tasks = get_tasks(list_id)
    current = next((t for t in tasks if t.get("id") == task_id), None)

    if not current:
        return False, "Task not found"

    # Format new content
    routing = route_item(item)

    # Create bundle
    bundle = create_task_bundle(
        description=f"Update task: {routing['title']}",
        updates=[
            {
                "id": task_id,
                "title": routing["title"],
                "notes": routing["notes"],
            }
        ],
        pre_images={task_id: current},
    )

    # Execute update
    cmd = [
        "gog",
        "tasks",
        "update",
        list_id,
        task_id,
        "--title",
        routing["title"],
        "--notes",
        routing["notes"],
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            from ..change_bundles import mark_applied

            mark_applied(bundle["id"])
            return True, "Task updated"
        return False, f"Failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout updating task: {task_id}")
        return False, "Error: Task update timed out"
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Subprocess error updating task: {e}")
        return False, f"Error: {e}"


def complete_task(task_id: str, list_id: str) -> tuple[bool, str]:
    """Mark a task as complete."""
    if not can_write("tasks"):
        return False, "Tasks domain not in Execute mode"

    cmd = ["gog", "tasks", "complete", list_id, task_id]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, "Task completed"
        return False, f"Failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout completing task: {task_id}")
        return False, "Error: Task completion timed out"
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Subprocess error completing task: {e}")
        return False, f"Error: {e}"


def move_task(
    task_id: str,
    from_list_id: str,
    to_list_name: str,
) -> tuple[bool, str]:
    """Move a task to a different list."""
    if not can_write("tasks"):
        return False, "Tasks domain not in Execute mode"

    to_list_id = find_list_id(to_list_name)
    if not to_list_id:
        return False, f"Destination list not found: {to_list_name}"

    # Get task content
    tasks = get_tasks(from_list_id)
    task = next((t for t in tasks if t.get("id") == task_id), None)

    if not task:
        return False, "Task not found"

    # Create in new list
    cmd_add = [
        "gog",
        "tasks",
        "add",
        to_list_id,
        "--title",
        task.get("title", ""),
        "--notes",
        task.get("notes", ""),
    ]

    try:
        result = subprocess.run(cmd_add, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return False, f"Failed to create in destination: {result.stderr}"

        # Delete from old list
        cmd_del = ["gog", "tasks", "delete", from_list_id, task_id, "--force"]
        subprocess.run(cmd_del, capture_output=True, text=True, timeout=30)

        return True, f"Task moved to {to_list_name}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout moving task: {task_id}")
        return False, "Error: Task move timed out"
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Subprocess error moving task: {e}")
        return False, f"Error: {e}"


def sync_waiting_for_mirror(item: dict) -> tuple[bool, str]:
    """Mirror an item to the Waiting-for list if applicable."""
    routing = route_item(item)

    if not routing["mirror_to_waiting"]:
        return True, "No mirror needed"

    waiting_list = get("routing.task_lists.waiting_for", "Waiting For")
    list_id = find_list_id(waiting_list)

    if not list_id:
        return False, f"Waiting-for list not found: {waiting_list}"

    # Check if already mirrored
    dedupe_key = routing["dedupe_key"]
    existing = find_by_dedupe_key(dedupe_key, list_id)

    if existing:
        return True, "Already mirrored"

    # Create mirror task
    cmd = [
        "gog",
        "tasks",
        "add",
        list_id,
        "--title",
        routing["title"],
        "--notes",
        routing["notes"],
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Mirrored to {waiting_list}"
        return False, f"Failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout mirroring to waiting list: {routing['title']}")
        return False, "Error: Mirror operation timed out"
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Subprocess error mirroring to waiting list: {e}")
        return False, f"Error: {e}"
