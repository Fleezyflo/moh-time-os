"""
AsanaWriter - Write-back integration for Asana.

Handles creating, updating, and commenting on Asana tasks via REST API.
Uses httpx for HTTP calls (not the asana SDK for writes).
"""

import logging
import os
import sqlite3
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

ASANA_API_BASE = "https://app.asana.com/api/1.0"
RATE_LIMIT_DELAY = 1  # seconds between retries after 429


@dataclass
class AsanaWriteResult:
    """Result of an Asana write operation."""

    success: bool
    gid: str | None = None  # Asana GID of created/updated task
    data: dict | None = None  # Response data from Asana
    error: str | None = None  # Error message if failed
    http_status: int | None = None  # HTTP status code


class AsanaWriter:
    """Write tasks, comments, and updates to Asana."""

    def __init__(
        self,
        personal_access_token: str | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize AsanaWriter.

        Args:
            personal_access_token: Asana PAT. If None, uses ASANA_PAT env var.
            dry_run: If True, validate payload without sending.
        """
        self.pat = personal_access_token or os.environ.get("ASANA_PAT")
        if not self.pat:
            raise ValueError(
                "No Asana PAT provided. Set ASANA_PAT env var or pass personal_access_token."
            )
        self.dry_run = dry_run
        self.base_url = ASANA_API_BASE

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> AsanaWriteResult:
        """
        Make authenticated request to Asana API.

        Handles rate limiting (429 with Retry-After header).
        """
        if self.dry_run:
            # Validate payload structure
            return AsanaWriteResult(
                success=True,
                data={"dry_run": True, "payload": json_data},
                gid=None,
            )

        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.pat}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.request(
                method,
                url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=30.0,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", RATE_LIMIT_DELAY))
                logger.warning(f"Asana API rate limited. Waiting {retry_after}s before retry.")
                time.sleep(retry_after)
                # Retry once
                response = httpx.request(
                    method,
                    url,
                    headers=headers,
                    json=json_data,
                    params=params,
                    timeout=30.0,
                )

            # Parse response
            if response.status_code in (200, 201):
                data = response.json().get("data", {})
                gid = data.get("gid")
                return AsanaWriteResult(
                    success=True,
                    gid=gid,
                    data=data,
                    http_status=response.status_code,
                )

            # Handle errors
            error_msg = f"Asana API error {response.status_code}"
            try:
                error_data = response.json()
                if "errors" in error_data:
                    error_msg += f": {error_data['errors']}"
            except (sqlite3.Error, ValueError, OSError, KeyError):
                error_msg += f": {response.text[:200]}"

            logger.error(error_msg)
            return AsanaWriteResult(
                success=False,
                error=error_msg,
                http_status=response.status_code,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Asana request failed: {str(e)}"
            logger.error(error_msg)
            return AsanaWriteResult(
                success=False,
                error=error_msg,
            )

    def create_task(
        self,
        project_gid: str,
        name: str,
        notes: str = "",
        assignee: str | None = None,
        due_on: str | None = None,
        custom_fields: dict | None = None,
    ) -> AsanaWriteResult:
        """
        Create a new task in Asana.

        Args:
            project_gid: Asana project GID
            name: Task name
            notes: Task notes/description
            assignee: Assignee user GID
            due_on: Due date in YYYY-MM-DD format
            custom_fields: Dict of custom field GID -> value

        Returns:
            AsanaWriteResult with created task GID
        """
        payload = {
            "data": {
                "name": name,
                "notes": notes or "",
                "projects": [project_gid],
            }
        }

        if assignee:
            payload["data"]["assignee"] = assignee
        if due_on:
            payload["data"]["due_on"] = due_on
        if custom_fields:
            payload["data"]["custom_fields"] = custom_fields

        return self._make_request("POST", "tasks", json_data=payload)

    def update_task(
        self,
        task_gid: str,
        updates: dict,
    ) -> AsanaWriteResult:
        """
        Update an existing task.

        Args:
            task_gid: Asana task GID
            updates: Dict with fields to update:
                - name: str
                - notes: str
                - assignee: str (user GID)
                - due_on: str (YYYY-MM-DD)
                - completed: bool
                - custom_fields: dict

        Returns:
            AsanaWriteResult with updated task GID
        """
        payload = {"data": {}}

        # Map common fields
        if "name" in updates:
            payload["data"]["name"] = updates["name"]
        if "notes" in updates:
            payload["data"]["notes"] = updates["notes"]
        if "assignee" in updates:
            payload["data"]["assignee"] = updates["assignee"]
        if "due_on" in updates:
            payload["data"]["due_on"] = updates["due_on"]
        if "completed" in updates:
            payload["data"]["completed"] = updates["completed"]
        if "custom_fields" in updates:
            payload["data"]["custom_fields"] = updates["custom_fields"]
        if "followers" in updates:
            payload["data"]["followers"] = updates["followers"]

        if not payload["data"]:
            return AsanaWriteResult(
                success=False,
                error="No valid fields to update",
            )

        return self._make_request("PUT", f"tasks/{task_gid}", json_data=payload)

    def complete_task(self, task_gid: str) -> AsanaWriteResult:
        """
        Mark a task as complete.

        Args:
            task_gid: Asana task GID

        Returns:
            AsanaWriteResult
        """
        return self.update_task(task_gid, {"completed": True})

    def add_comment(self, task_gid: str, text: str) -> AsanaWriteResult:
        """
        Add a comment to a task.

        Args:
            task_gid: Asana task GID
            text: Comment text

        Returns:
            AsanaWriteResult with comment GID
        """
        payload = {
            "data": {
                "text": text,
            }
        }

        return self._make_request(
            "POST",
            f"tasks/{task_gid}/stories",
            json_data=payload,
        )

    def add_subtask(
        self,
        parent_gid: str,
        name: str,
        assignee: str | None = None,
    ) -> AsanaWriteResult:
        """
        Create a subtask on a task.

        Args:
            parent_gid: Parent task GID
            name: Subtask name
            assignee: Assignee user GID

        Returns:
            AsanaWriteResult with subtask GID
        """
        payload = {
            "data": {
                "name": name,
            }
        }

        if assignee:
            payload["data"]["assignee"] = assignee

        return self._make_request(
            "POST",
            f"tasks/{parent_gid}/subtasks",
            json_data=payload,
        )

    def move_task_to_section(
        self,
        task_gid: str,
        section_gid: str,
    ) -> AsanaWriteResult:
        """
        Move a task to a section (for board/pipeline views).

        Args:
            task_gid: Task GID
            section_gid: Section GID

        Returns:
            AsanaWriteResult
        """
        {
            "data": {
                "project": section_gid.split("-")[0],  # Extract project from section
            }
        }

        # First add to project, then update section
        result = self.update_task(task_gid, {"projects": [section_gid.split("-")[0]]})
        if not result.success:
            return result

        # Now move to section
        return self._make_request(
            "POST",
            f"sections/{section_gid}/addTask",
            json_data={"data": {"task": task_gid}},
        )

    def add_tag(self, task_gid: str, tag_gid: str) -> AsanaWriteResult:
        """
        Add a tag to a task.

        Args:
            task_gid: Task GID
            tag_gid: Tag GID

        Returns:
            AsanaWriteResult
        """
        payload = {
            "data": {
                "tag": tag_gid,
            }
        }

        return self._make_request(
            "POST",
            f"tasks/{task_gid}/addTag",
            json_data=payload,
        )

    def add_follower(self, task_gid: str, follower_gid: str) -> AsanaWriteResult:
        """
        Add a follower to a task.

        Args:
            task_gid: Task GID
            follower_gid: User GID

        Returns:
            AsanaWriteResult
        """
        return self.update_task(task_gid, {"followers": [follower_gid]})
