"""
Asana Action Handler - Maps proposal implied_actions to AsanaWriter calls.

Connects the intelligence proposal system to Asana task management:
- create_task: Creates Asana tasks from proposals
- add_comment: Adds context comments to existing tasks
- update_status: Updates task status/custom fields

GAP-10-12: Proposal-to-Asana pipeline
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone

from lib.outbox import get_outbox

logger = logging.getLogger(__name__)


class AsanaActionHandler:
    """
    Handles Asana-related action execution from intelligence proposals.

    Maps proposal implied_actions to AsanaWriter API calls.
    Requires ASANA_PAT environment variable or explicit token.
    """

    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}
        self._writer = None

    def _get_writer(self):
        """Lazy-initialize AsanaWriter."""
        if self._writer is not None:
            return self._writer

        from lib.integrations.asana_writer import AsanaWriter

        dry_run = self.config.get("dry_run", False)
        self._writer = AsanaWriter(dry_run=dry_run)
        return self._writer

    def execute(self, action: dict) -> dict:
        """
        Execute an Asana action.

        Args:
            action: {
                'action_type': 'create_task' | 'add_comment' | 'update_status',
                'data': {...}
            }

        Returns:
            {success: bool, gid?: str, error?: str}
        """
        action_type = action.get("action_type")

        handlers = {
            "create_task": self._create_task,
            "add_comment": self._add_comment,
            "update_status": self._update_status,
        }

        handler = handlers.get(action_type)
        if not handler:
            return {"success": False, "error": f"Unknown Asana action type: {action_type}"}

        try:
            return handler(action)
        except (sqlite3.Error, ValueError, OSError):
            raise

    def _create_task(self, action: dict) -> dict:
        """
        Create an Asana task from proposal data.

        Expected data keys:
            name: Task name (required)
            project_gid: Asana project GID (required)
            notes: Task description
            assignee: Assignee email or GID
            due_on: Due date (YYYY-MM-DD)
            tags: List of tag GIDs
            custom_fields: Dict of custom field GID -> value
            proposal_id: Source proposal ID (for tracking)
        """
        data = action.get("data", {})
        name = data.get("name")
        project_gid = data.get("project_gid")

        if not name:
            return {"success": False, "error": "Task name is required"}
        if not project_gid:
            return {"success": False, "error": "project_gid is required"}

        outbox = get_outbox()
        proposal_id = data.get("proposal_id", "")
        idem_key = f"asana_create_{name}_{project_gid}_{proposal_id}"

        # Check if already fulfilled (idempotent retry)
        fulfilled = outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            logger.info(
                "Asana task already created (gid=%s)", fulfilled.get("external_resource_id")
            )
            return {
                "success": True,
                "gid": fulfilled.get("external_resource_id"),
                "already_executed": True,
            }

        writer = self._get_writer()

        task_data = {
            "name": name,
            "projects": [project_gid],
        }

        if data.get("notes"):
            task_data["notes"] = data["notes"]
        if data.get("assignee"):
            task_data["assignee"] = data["assignee"]
        if data.get("due_on"):
            task_data["due_on"] = data["due_on"]
        if data.get("tags"):
            task_data["tags"] = data["tags"]
        if data.get("custom_fields"):
            task_data["custom_fields"] = data["custom_fields"]

        # Add proposal reference in notes if available
        if proposal_id:
            note_suffix = f"\n\n---\nCreated by MOH Time OS (proposal: {proposal_id})"
            task_data["notes"] = task_data.get("notes", "") + note_suffix

        # Record durable intent BEFORE calling Asana API
        intent_id = outbox.record_intent(
            handler="asana",
            action="create_task",
            payload=data,
            idempotency_key=idem_key,
        )

        result = writer.create_task(task_data)

        if result.success:
            # Mark outbox fulfilled with Asana GID for reconciliation
            outbox.mark_fulfilled(intent_id, external_resource_id=result.gid)

            # Track in local store
            self.store.insert(
                "action_log",
                {
                    "id": f"asana_create_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    "action_type": "asana_create_task",
                    "target_id": result.gid,
                    "payload": json.dumps(data),
                    "result": json.dumps({"gid": result.gid}),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            return {"success": True, "gid": result.gid, "data": result.data}

        outbox.mark_failed(intent_id, error=result.error or "create_task failed")
        return {"success": False, "error": result.error}

    def _add_comment(self, action: dict) -> dict:
        """
        Add a comment to an existing Asana task.

        Expected data keys:
            task_gid: Asana task GID (required)
            text: Comment text (required)
            is_pinned: Whether to pin the comment
        """
        data = action.get("data", {})
        task_gid = data.get("task_gid")
        text = data.get("text")

        if not task_gid:
            return {"success": False, "error": "task_gid is required"}
        if not text:
            return {"success": False, "error": "Comment text is required"}

        outbox = get_outbox()
        # Idempotency key includes text hash to allow distinct comments
        text_hash = hash(text) & 0xFFFFFFFF  # 32-bit positive hash
        idem_key = f"asana_comment_{task_gid}_{text_hash}"

        # Check if already fulfilled
        fulfilled = outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            logger.info(
                "Asana comment already added (gid=%s)", fulfilled.get("external_resource_id")
            )
            return {
                "success": True,
                "gid": fulfilled.get("external_resource_id"),
                "already_executed": True,
            }

        # Record intent BEFORE calling Asana API
        intent_id = outbox.record_intent(
            handler="asana",
            action="add_comment",
            payload={"task_gid": task_gid, "text_hash": str(text_hash)},
            idempotency_key=idem_key,
        )

        writer = self._get_writer()
        result = writer.add_comment(task_gid, text, is_pinned=data.get("is_pinned", False))

        if result.success:
            outbox.mark_fulfilled(intent_id, external_resource_id=result.gid)
            return {"success": True, "gid": result.gid}

        outbox.mark_failed(intent_id, error=result.error or "add_comment failed")
        return {"success": False, "error": result.error}

    def _update_status(self, action: dict) -> dict:
        """
        Update task status or custom fields in Asana.

        Expected data keys:
            task_gid: Asana task GID (required)
            completed: bool (optional)
            custom_fields: Dict of custom field GID -> value (optional)
            assignee: New assignee (optional)
            due_on: New due date (optional)
        """
        data = action.get("data", {})
        task_gid = data.get("task_gid")

        if not task_gid:
            return {"success": False, "error": "task_gid is required"}

        updates = {}

        if "completed" in data:
            updates["completed"] = data["completed"]
        if "custom_fields" in data:
            updates["custom_fields"] = data["custom_fields"]
        if "assignee" in data:
            updates["assignee"] = data["assignee"]
        if "due_on" in data:
            updates["due_on"] = data["due_on"]

        if not updates:
            return {"success": False, "error": "No updates provided"}

        outbox = get_outbox()
        # Include update content hash for idempotency
        updates_hash = hash(json.dumps(updates, sort_keys=True, default=str)) & 0xFFFFFFFF
        idem_key = f"asana_update_{task_gid}_{updates_hash}"

        # Check if already fulfilled
        fulfilled = outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            logger.info(
                "Asana status update already fulfilled (gid=%s)",
                fulfilled.get("external_resource_id"),
            )
            return {
                "success": True,
                "gid": fulfilled.get("external_resource_id"),
                "already_executed": True,
            }

        # Record intent BEFORE calling Asana API
        intent_id = outbox.record_intent(
            handler="asana",
            action="update_status",
            payload={"task_gid": task_gid, "updates": updates},
            idempotency_key=idem_key,
        )

        writer = self._get_writer()
        result = writer.update_task(task_gid, updates)

        if result.success:
            outbox.mark_fulfilled(intent_id, external_resource_id=result.gid)
            return {"success": True, "gid": result.gid}

        outbox.mark_failed(intent_id, error=result.error or "update_status failed")
        return {"success": False, "error": result.error}
