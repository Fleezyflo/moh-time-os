"""
Asana Collector - Pulls tasks from Asana via real API client.
"""

import json
import logging
from datetime import date, datetime
from typing import Any

from .base import BaseCollector

logger = logging.getLogger(__name__)

# hrmny workspace GID
HRMNY_WORKSPACE_GID = "1148006162435561"


class AsanaCollector(BaseCollector):
    """Collects tasks from Asana."""

    source_name = "asana"
    target_table = "tasks"

    def collect(self) -> dict[str, Any]:
        """Fetch tasks from Asana using real API client."""
        try:
            from engine.asana_client import list_projects, list_tasks_in_project

            all_tasks = []

            # Get projects from hrmny workspace
            projects = list_projects(HRMNY_WORKSPACE_GID, archived=False)

            # Limit to avoid timeout
            for proj in projects[:15]:
                proj_gid = proj.get("gid")
                proj_name = proj.get("name", "Unknown")

                try:
                    tasks = list_tasks_in_project(proj_gid, completed=False)

                    for task in tasks:
                        task["_project_name"] = proj_name
                        task["_project_gid"] = proj_gid
                        all_tasks.append(task)

                except Exception as e:
                    self.logger.warning(f"Failed to fetch tasks for project {proj_name}: {e}")

            return {"tasks": all_tasks}

        except Exception as e:
            self.logger.error(f"Asana collection failed: {e}")
            return {"tasks": []}

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Asana tasks to canonical format."""
        transformed = []
        now = datetime.now().isoformat()

        for task in raw_data.get("tasks", []):
            gid = task.get("gid")
            if not gid:
                continue

            # Parse due date
            due_on = task.get("due_on")  # YYYY-MM-DD format
            due_at = task.get("due_at")  # ISO datetime
            due_date = due_at or (f"{due_on}T23:59:59" if due_on else None)

            # Get assignee
            assignee = task.get("assignee", {})
            assignee_name = assignee.get("name") if assignee else None

            # Compute if overdue
            is_overdue = False
            if due_on:
                try:
                    due = datetime.strptime(due_on, "%Y-%m-%d").date()
                    is_overdue = due < date.today()
                except (ValueError, TypeError) as e:
                    logger.debug(
                        f"Could not parse due date '{due_on}' for task {task.get('gid', 'unknown')}: {e}"
                    )

            # Determine status
            if task.get("completed"):
                status = "completed"
            elif is_overdue:
                status = "overdue"
            else:
                status = "active"

            transformed.append(
                {
                    "id": f"asana_{gid}",
                    "source": "asana",
                    "source_id": gid,
                    "title": task.get("name", "Untitled"),
                    "status": status,
                    "priority": "high" if is_overdue else "normal",
                    "due_date": due_date,
                    "assignee": assignee_name,
                    "project": task.get("_project_name", ""),
                    "project_id": None,  # Will be linked by normalizer
                    "notes": task.get("notes", "")[:500] if task.get("notes") else "",
                    "tags": json.dumps([t.get("name") for t in task.get("tags", [])]),
                    "created_at": task.get("created_at", now),
                    "updated_at": task.get("modified_at", now),
                }
            )

        return transformed
