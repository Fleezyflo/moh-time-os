"""
AsanaSyncManager - Bidirectional task sync between local DB and Asana.

Maintains mappings, handles conflict detection, and batch sync operations.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from lib.db import get_connection
from lib.integrations.asana_writer import AsanaWriter, AsanaWriteResult

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    local_id: str
    asana_gid: str | None = None
    action: str | None = None  # 'create', 'update', 'comment'
    error: str | None = None
    conflict: bool = False


class AsanaSyncManager:
    """Manages bidirectional sync of tasks between local DB and Asana."""

    def __init__(self, writer: AsanaWriter | None = None, store=None):
        """
        Initialize sync manager.

        Args:
            writer: AsanaWriter instance. If None, creates one from env.
            store: StateStore instance for local DB access.
        """
        self.writer = writer or AsanaWriter()
        self.store = store

    def _ensure_mapping_table(self):
        """Create asana_task_mappings table if it doesn't exist."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS asana_task_mappings (
                    local_id TEXT PRIMARY KEY,
                    asana_gid TEXT NOT NULL UNIQUE,
                    project_gid TEXT,
                    local_updated_at TEXT,
                    asana_updated_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to create mapping table: {e}")
            raise

    def _get_mapping(self, local_id: str) -> dict | None:
        """Get Asana GID for a local task ID."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT asana_gid, project_gid, asana_updated_at FROM asana_task_mappings WHERE local_id = ?",
                (local_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "asana_gid": row[0],
                    "project_gid": row[1],
                    "asana_updated_at": row[2],
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"Failed to query mapping: {e}")
            return None

    def _save_mapping(
        self,
        local_id: str,
        asana_gid: str,
        project_gid: str | None = None,
        local_updated_at: str | None = None,
    ) -> bool:
        """Save or update task mapping."""
        now = datetime.now().isoformat()
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Use parameterized query to avoid SQL injection
            cursor.execute(
                """
                INSERT INTO asana_task_mappings
                (local_id, asana_gid, project_gid, local_updated_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(local_id) DO UPDATE SET
                    asana_gid = excluded.asana_gid,
                    project_gid = excluded.project_gid,
                    local_updated_at = excluded.local_updated_at,
                    updated_at = excluded.updated_at
            """,
                (
                    local_id,
                    asana_gid,
                    project_gid,
                    local_updated_at or now,
                    now,
                    now,
                ),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to save mapping: {e}")
            return False

    def sync_task_to_asana(
        self,
        local_task_id: str,
        project_gid: str,
    ) -> SyncResult:
        """
        Sync a local task to Asana (create or update).

        Args:
            local_task_id: Local task ID
            project_gid: Asana project GID

        Returns:
            SyncResult with success status and Asana GID
        """
        self._ensure_mapping_table()

        # Get local task
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (local_task_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return SyncResult(
                    success=False,
                    local_id=local_task_id,
                    error=f"Local task not found: {local_task_id}",
                )

            # Convert row to dict (assuming row factory isn't set)
            task = dict(zip([desc[0] for desc in cursor.description], row, strict=False))
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch local task: {e}")
            return SyncResult(
                success=False,
                local_id=local_task_id,
                error=f"Database error: {str(e)}",
            )

        # Check if we have existing mapping
        mapping = self._get_mapping(local_task_id)

        if mapping:
            # Update existing task
            asana_gid = mapping["asana_gid"]

            # Check for conflict (task was modified in Asana after local update)
            local_updated = task.get("updated_at")
            asana_updated = mapping.get("asana_updated_at")

            if asana_updated and local_updated:
                try:
                    local_dt = datetime.fromisoformat(local_updated)
                    asana_dt = datetime.fromisoformat(asana_updated)
                    if asana_dt > local_dt:
                        return SyncResult(
                            success=False,
                            local_id=local_task_id,
                            asana_gid=asana_gid,
                            error="Conflict: task was modified in Asana after local update",
                            conflict=True,
                        )
                except (ValueError, TypeError):
                    pass  # Continue if dates are unparseable

            # Update task
            updates = {
                "name": task.get("title", "Untitled"),
                "notes": task.get("notes", ""),
                "completed": task.get("status") == "completed",
            }

            if task.get("assignee"):
                updates["assignee"] = task["assignee"]
            if task.get("due_date"):
                updates["due_on"] = task["due_date"][:10]  # Extract YYYY-MM-DD

            result = self.writer.update_task(asana_gid, updates)

            if result.success:
                self._save_mapping(
                    local_task_id,
                    asana_gid,
                    project_gid,
                    task.get("updated_at"),
                )
                return SyncResult(
                    success=True,
                    local_id=local_task_id,
                    asana_gid=asana_gid,
                    action="update",
                )

            return SyncResult(
                success=False,
                local_id=local_task_id,
                asana_gid=asana_gid,
                error=result.error,
            )

        # Create new task
        result = self.writer.create_task(
            project_gid=project_gid,
            name=task.get("title", "Untitled"),
            notes=task.get("notes", ""),
            assignee=task.get("assignee"),
            due_on=task.get("due_date")[:10] if task.get("due_date") else None,
        )

        if result.success and result.gid:
            self._save_mapping(
                local_task_id,
                result.gid,
                project_gid,
                task.get("updated_at"),
            )
            return SyncResult(
                success=True,
                local_id=local_task_id,
                asana_gid=result.gid,
                action="create",
            )

        return SyncResult(
            success=False,
            local_id=local_task_id,
            error=result.error,
        )

    def sync_completion(self, local_task_id: str) -> SyncResult:
        """
        Mark a task as complete in Asana.

        Args:
            local_task_id: Local task ID

        Returns:
            SyncResult
        """
        self._ensure_mapping_table()

        mapping = self._get_mapping(local_task_id)
        if not mapping:
            return SyncResult(
                success=False,
                local_id=local_task_id,
                error="No Asana mapping found for this task",
            )

        asana_gid = mapping["asana_gid"]
        result = self.writer.complete_task(asana_gid)

        if result.success:
            self._save_mapping(local_task_id, asana_gid, mapping.get("project_gid"))
            return SyncResult(
                success=True,
                local_id=local_task_id,
                asana_gid=asana_gid,
                action="complete",
            )

        return SyncResult(
            success=False,
            local_id=local_task_id,
            asana_gid=asana_gid,
            error=result.error,
        )

    def post_status_comment(self, local_task_id: str, status_text: str) -> SyncResult:
        """
        Post a status comment to a task in Asana.

        Args:
            local_task_id: Local task ID
            status_text: Comment text

        Returns:
            SyncResult
        """
        self._ensure_mapping_table()

        mapping = self._get_mapping(local_task_id)
        if not mapping:
            return SyncResult(
                success=False,
                local_id=local_task_id,
                error="No Asana mapping found for this task",
            )

        asana_gid = mapping["asana_gid"]
        result = self.writer.add_comment(asana_gid, status_text)

        if result.success:
            return SyncResult(
                success=True,
                local_id=local_task_id,
                asana_gid=asana_gid,
                action="comment",
            )

        return SyncResult(
            success=False,
            local_id=local_task_id,
            asana_gid=asana_gid,
            error=result.error,
        )

    def bulk_sync(self, task_ids: list[str], project_gid: str) -> list[SyncResult]:
        """
        Sync multiple tasks to Asana.

        Args:
            task_ids: List of local task IDs
            project_gid: Asana project GID

        Returns:
            List of SyncResult objects
        """
        results = []
        for task_id in task_ids:
            result = self.sync_task_to_asana(task_id, project_gid)
            results.append(result)
        return results
