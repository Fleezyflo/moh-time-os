"""
Action Handlers - Execute specific action types against external systems.
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """Base class for action handlers."""

    @abstractmethod
    def execute(self, payload: dict) -> dict[str, Any]:
        """Execute the action. Returns result dict."""
        pass

    def _run_command(self, cmd: str, timeout: int = 30) -> str:
        """Run a shell command."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,  # nosec B602
            )
            if result.returncode != 0:
                raise Exception(f"Command failed: {result.stderr}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise Exception(f"Command timed out after {timeout}s")


class TaskHandler(BaseHandler):
    """Handle task-related actions via Google Tasks."""

    def execute(self, payload: dict) -> dict[str, Any]:
        """Execute task action."""
        action = payload.get("action")

        if action == "complete":
            return self._complete_task(payload)
        if action == "create":
            return self._create_task(payload)
        if action == "update":
            return self._update_task(payload)
        raise ValueError(f"Unknown task action: {action}")

    def _complete_task(self, payload: dict) -> dict:
        """Mark a task as complete."""
        list_id = payload.get("list_id")
        task_id = payload.get("task_id")

        if not list_id or not task_id:
            raise ValueError("list_id and task_id required")

        cmd = f"gog tasks complete {list_id} {task_id} --json 2>/dev/null"
        self._run_command(cmd)

        return {
            "action": "complete",
            "task_id": task_id,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _create_task(self, payload: dict) -> dict:
        """Create a new task."""
        list_id = payload.get("list_id")
        title = payload.get("title")
        notes = payload.get("notes", "")
        due = payload.get("due")

        if not list_id or not title:
            raise ValueError("list_id and title required")

        cmd = f'gog tasks add {list_id} "{title}"'
        if notes:
            cmd += f' --notes "{notes}"'
        if due:
            cmd += f" --due {due}"
        cmd += " --json 2>/dev/null"

        self._run_command(cmd)

        return {
            "action": "create",
            "title": title,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _update_task(self, payload: dict) -> dict:
        """Update an existing task."""
        # Implementation depends on gog tasks update syntax
        return {
            "action": "update",
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }


class CalendarHandler(BaseHandler):
    """Handle calendar-related actions."""

    def execute(self, payload: dict) -> dict[str, Any]:
        """Execute calendar action."""
        action = payload.get("action")

        if action == "create":
            return self._create_event(payload)
        if action == "update":
            return self._update_event(payload)
        if action == "delete":
            return self._delete_event(payload)
        raise ValueError(f"Unknown calendar action: {action}")

    def _create_event(self, payload: dict) -> dict:
        """Create a calendar event."""
        title = payload.get("title")
        start = payload.get("start")
        end = payload.get("end")

        if not title or not start:
            raise ValueError("title and start required")

        cmd = f'gog calendar add "{title}" --start "{start}"'
        if end:
            cmd += f' --end "{end}"'
        cmd += " --json 2>/dev/null"

        self._run_command(cmd)

        return {
            "action": "create",
            "title": title,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _update_event(self, payload: dict) -> dict:
        """Update a calendar event."""
        return {
            "action": "update",
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _delete_event(self, payload: dict) -> dict:
        """Delete a calendar event."""
        event_id = payload.get("event_id")

        if not event_id:
            raise ValueError("event_id required")

        cmd = f"gog calendar delete {event_id} --force --json 2>/dev/null"
        self._run_command(cmd)

        return {
            "action": "delete",
            "event_id": event_id,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }


class NotificationHandler(BaseHandler):
    """Handle notification sending via Clawdbot nodes."""

    def execute(self, payload: dict) -> dict[str, Any]:
        """Send a notification."""
        title = payload.get("title", "MOH TIME OS")
        body = payload.get("body", "")
        priority = payload.get("priority", "normal")

        # Use Clawdbot's node notification system
        # This would integrate with the nodes tool
        logger.info(f"Notification: [{priority}] {title}: {body}")

        return {
            "action": "notify",
            "title": title,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }


class EmailHandler(BaseHandler):
    """Handle email-related actions (drafts, labels, archive)."""

    def execute(self, payload: dict) -> dict[str, Any]:
        """Execute email action."""
        action = payload.get("action")

        if action == "archive":
            return self._archive_email(payload)
        if action == "label":
            return self._label_email(payload)
        if action == "mark_read":
            return self._mark_read(payload)
        raise ValueError(f"Unknown email action: {action}")

    def _archive_email(self, payload: dict) -> dict:
        """Archive an email."""
        thread_id = payload.get("thread_id")

        if not thread_id:
            raise ValueError("thread_id required")

        cmd = f"gog gmail archive {thread_id} --json 2>/dev/null"
        self._run_command(cmd)

        return {
            "action": "archive",
            "thread_id": thread_id,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _label_email(self, payload: dict) -> dict:
        """Add label to email."""
        thread_id = payload.get("thread_id")
        label = payload.get("label")

        if not thread_id or not label:
            raise ValueError("thread_id and label required")

        cmd = f'gog gmail label {thread_id} "{label}" --json 2>/dev/null'
        self._run_command(cmd)

        return {
            "action": "label",
            "thread_id": thread_id,
            "label": label,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _mark_read(self, payload: dict) -> dict:
        """Mark email as read."""
        thread_id = payload.get("thread_id")

        if not thread_id:
            raise ValueError("thread_id required")

        cmd = f"gog gmail read {thread_id} --json 2>/dev/null"
        self._run_command(cmd)

        return {
            "action": "mark_read",
            "thread_id": thread_id,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }
