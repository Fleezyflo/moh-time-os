"""
Tasks Collector - Pulls tasks from Google Tasks via Service Account API.
Uses direct Google API with service account for domain-wide delegation.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from lib.credential_paths import google_sa_file

from .base import BaseCollector
from .resilience import COLLECTOR_ERRORS

logger = logging.getLogger(__name__)


def _sa_file():
    """Resolve SA file at call time to respect env overrides."""
    return google_sa_file()


# Service account configuration
SCOPES = ["https://www.googleapis.com/auth/tasks.readonly"]
DEFAULT_USER = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")


class TasksCollector(BaseCollector):
    """Collects tasks from Google Tasks using Service Account."""

    source_name = "tasks"
    target_table = "tasks"
    OUTPUT_TABLES = ["tasks"]

    def __init__(self, config: dict, store=None):
        super().__init__(config, store)
        self._service = None

    def _get_service(self, user: str = DEFAULT_USER):
        """Get Tasks API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                str(_sa_file()), scopes=SCOPES
            )
            creds = creds.with_subject(user)
            self._service = build("tasks", "v1", credentials=creds)
            return self._service
        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Failed to get Tasks service: {e}")
            raise

    def collect(self) -> dict[str, Any]:
        """Fetch tasks from Google Tasks using Service Account API."""
        try:
            service = self._get_service()
            all_tasks = []
            task_lists = []

            # Get all task lists with pagination
            page_token = None
            while True:
                result = (
                    service.tasklists()
                    .list(
                        maxResults=100,
                        pageToken=page_token,
                    )
                    .execute()
                )

                items = result.get("items", [])
                task_lists.extend(items)

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            self.logger.info(f"Found {len(task_lists)} task lists")

            # Get tasks from each list with pagination
            for tl in task_lists:
                list_id = tl.get("id")
                list_name = tl.get("title", "Unknown")

                if not list_id:
                    continue

                try:
                    page_token = None
                    while True:
                        result = (
                            service.tasks()
                            .list(
                                tasklist=list_id,
                                maxResults=100,
                                showCompleted=False,
                                showHidden=False,
                                pageToken=page_token,
                            )
                            .execute()
                        )

                        tasks = result.get("items", [])
                        for task in tasks:
                            task["_list_id"] = list_id
                            task["_list_name"] = list_name
                            all_tasks.append(task)

                        page_token = result.get("nextPageToken")
                        if not page_token:
                            break

                except COLLECTOR_ERRORS as e:
                    self.logger.warning(f"Failed to fetch tasks from list {list_name}: {e}")

            return {"tasks": all_tasks, "lists": task_lists}

        except COLLECTOR_ERRORS as e:
            self.logger.exception(f"Tasks collection failed: {e}")
            raise  # Propagate error to sync() which handles it properly

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Google Tasks to canonical format."""
        now = datetime.now(timezone.utc).isoformat()
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

    def _extract_due_date(self, task: dict) -> str | None:
        """Extract due date from task."""
        due = task.get("due")
        if due:
            # Format: 2024-01-15T00:00:00.000Z
            return str(due)[:10]  # Just the date part
        return None

    def _compute_priority(self, task: dict) -> int:
        """Compute priority score 0-100."""
        score = 50  # Base score

        # Due date urgency
        due = self._extract_due_date(task)
        if due:
            try:
                due_date = datetime.strptime(due, "%Y-%m-%d")
                days_until = (due_date - datetime.now(timezone.utc)).days

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
