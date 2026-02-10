"""
Tasks Collector - Pulls tasks from Google Tasks via gog CLI.
REPLACES the broken Asana collector - uses real working commands.
"""

import json
from datetime import datetime
from typing import Any

from .base import BaseCollector


class TasksCollector(BaseCollector):
    """Collects tasks from Google Tasks."""

    source_name = "tasks"
    target_table = "tasks"

    def collect(self) -> dict[str, Any]:
        """Fetch tasks from Google Tasks using gog CLI."""
        try:
            all_tasks = []

            # Get all task lists
            output = self._run_command("gog tasks lists --json 2>/dev/null")
            lists_data = self._parse_json_output(output) if output.strip() else {}
            task_lists = lists_data.get("tasklists", [])

            # Get tasks from each list
            for tl in task_lists:
                list_id = tl.get("id")
                list_name = tl.get("title", "Unknown")

                if not list_id:
                    continue

                output = self._run_command(f"gog tasks list {list_id} --json 2>/dev/null")
                tasks_data = self._parse_json_output(output) if output.strip() else {}
                tasks = tasks_data.get("tasks", [])

                for task in tasks:
                    task["_list_id"] = list_id
                    task["_list_name"] = list_name
                    all_tasks.append(task)

            return {"tasks": all_tasks, "lists": task_lists}

        except Exception as e:
            self.logger.warning(f"Tasks collection failed: {e}")
            return {"tasks": [], "lists": []}

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Google Tasks to canonical format."""
        now = datetime.now().isoformat()
        transformed = []

        for task in raw_data.get("tasks", []):
            task_id = task.get("id")
            if not task_id:
                continue

            # Skip completed tasks
            if task.get("status") == "completed":
                continue

            transformed.append(
                {
                    "id": f"gtask_{task_id}",
                    "source": "google_tasks",
                    "source_id": task_id,
                    "title": task.get("title", "Untitled"),
                    "status": self._map_status(task),
                    "priority": self._compute_priority(task),
                    "due_date": self._extract_due_date(task),
                    "due_time": None,
                    "assignee": None,  # Google Tasks doesn't have assignees
                    "project": task.get("_list_name", ""),
                    "lane": "",
                    "sensitivity": "",
                    "tags": json.dumps([]),
                    "dependencies": json.dumps([]),
                    "blockers": json.dumps([]),
                    "context": json.dumps(task),
                    "created_at": task.get("updated", now),
                    "updated_at": now,
                    "synced_at": now,
                }
            )

        return transformed

    def _map_status(self, task: dict) -> str:
        """Map Google Tasks status to canonical status."""
        status = task.get("status", "")
        if status == "completed":
            return "done"
        return "pending"

    def _extract_due_date(self, task: dict) -> str:
        """Extract due date from task."""
        due = task.get("due")
        if due:
            # Format: 2024-01-15T00:00:00.000Z
            return due[:10]  # Just the date part
        return None

    def _compute_priority(self, task: dict) -> int:
        """Compute priority score 0-100."""
        score = 50  # Base score

        # Due date urgency
        due = self._extract_due_date(task)
        if due:
            try:
                due_date = datetime.strptime(due, "%Y-%m-%d")
                days_until = (due_date - datetime.now()).days

                if days_until < 0:
                    score += min(40, 40 + abs(days_until) * 2)  # Overdue
                elif days_until == 0:
                    score += 35  # Due today
                elif days_until == 1:
                    score += 25  # Due tomorrow
                elif days_until <= 3:
                    score += 15  # Due soon
                elif days_until <= 7:
                    score += 5  # Due this week
            except ValueError:
                pass

        # Notes indicate importance
        if task.get("notes"):
            score += 5

        return min(100, max(0, score))
