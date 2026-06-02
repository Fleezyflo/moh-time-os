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
from .reconcile import tombstone_missing
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

    def __init__(self, config: dict, store=None):
        super().__init__(config, store)
        self._service = None

    def sync(self) -> dict[str, Any]:
        """Run the base collect→transform→store cycle, then tombstone.

        Google Tasks deleted upstream must not linger: after a successful or
        partial sync we delete rows for source='google_tasks' whose id was NOT
        in the rows just stored. The seen-set is derived from
        ``self._last_synced_rows`` — the exact rows the single base sync() fetch
        stored — NOT a second collect(), which could diverge (a partial second
        fetch would tombstone just-stored live rows). tombstone_missing has an
        empty-guard, so a failed/empty fetch never wipes the table. The tombstone
        runs in its own try so a cleanup failure never flips a real success.
        """
        result = super().sync()
        # Skip tombstoning unless the fetch was COMPLETE: a partial task-list
        # fetch (some lists failed) leaves an incomplete seen-set, and deleting
        # the "missing" rows would wipe still-live tasks from the failed lists.
        primary_complete = self._last_raw_data.get("_primary_fetch_complete", False)
        if result.get("status") in ("success", "partial") and primary_complete:
            seen = {row["id"] for row in self._last_synced_rows if row.get("id")}
            try:
                tombstone_missing(
                    self.store.db_path, table="tasks", source="google_tasks", seen_ids=seen
                )
            except COLLECTOR_ERRORS as e:
                self.logger.warning("google_tasks tombstone failed (data retained): %s", e)
        elif not primary_complete:
            self.logger.info("google_tasks: partial fetch -- skipping tombstone (data retained)")
        return result

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
            failed_lists = 0
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
                    failed_lists += 1
                    self.logger.warning(f"Failed to fetch tasks from list {list_name}: {e}")

            # _primary_fetch_complete is True only when EVERY task list fetched
            # successfully. A partial fetch yields an incomplete task set, so
            # sync() must skip tombstoning (deleting "missing" rows would wipe
            # still-live tasks from the failed lists).
            return {
                "tasks": all_tasks,
                "lists": task_lists,
                "_primary_fetch_complete": failed_lists == 0,
            }

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
                # Parse as a timezone-aware UTC datetime so subtraction with
                # datetime.now(timezone.utc) is valid (was naive -> TypeError).
                due_date = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc)
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
            except (ValueError, TypeError) as e:
                logger.debug("Could not compute due-date urgency for '%s': %s", due, e)

        # Notes indicate importance
        if task.get("notes"):
            score += 5

        return min(100, max(0, score))
