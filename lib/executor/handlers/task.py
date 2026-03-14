"""
Task Handler - Executes task-related actions.

Handles:
- Task creation/updates in external systems (Asana, etc.)
- Status changes
- Assignment changes
- Priority updates
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone

from lib.outbox import get_outbox

task_logger = logging.getLogger(__name__)


class TaskHandler:
    """Handles task-related action execution."""

    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}

    def execute(self, action: dict) -> dict:
        """
        Execute a task action.

        Args:
            action: {
                'action_type': 'create'|'update'|'complete'|'assign'|'prioritize',
                'task_id': str (for updates),
                'data': {...}
            }

        Returns:
            {success: bool, result?: any, error?: str}
        """
        action_type = action.get("action_type")

        handlers = {
            "create": self._create_task,
            "update": self._update_task,
            "complete": self._complete_task,
            "assign": self._assign_task,
            "prioritize": self._prioritize_task,
            "snooze": self._snooze_task,
        }

        handler = handlers.get(action_type)
        if not handler:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            result = handler(action)

            # Log the action
            self._log_action(action, result)

            return result
        except (sqlite3.Error, ValueError, OSError):
            raise  # was silently swallowed

    def _create_task(self, action: dict) -> dict:
        """Create a new task."""
        data = action.get("data", {})

        # Create in local store
        task_id = self.store.insert(
            "tasks",
            {
                "id": data.get("id")
                or f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "source": data.get("source", "time_os"),
                "title": data["title"],
                "status": "pending",
                "priority": data.get("priority", 50),
                "due_date": data.get("due_date"),
                "due_time": data.get("due_time"),
                "assignee": data.get("assignee"),
                "project": data.get("project"),
                "lane": data.get("lane", "ops"),
                "tags": json.dumps(data.get("tags", [])),
                "context": json.dumps(data.get("context", {})),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Sync to external system if configured
        if data.get("sync_to_asana") and self.config.get("asana_enabled"):
            self._sync_to_asana(task_id, data)

        return {"success": True, "task_id": task_id}

    def _update_task(self, action: dict) -> dict:
        """Update an existing task."""
        task_id = action.get("task_id")
        data = action.get("data", {})

        if not task_id:
            return {"success": False, "error": "task_id required"}

        # Update local store
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.store.update("tasks", task_id, data)

        return {"success": True, "task_id": task_id}

    def _complete_task(self, action: dict) -> dict:
        """Mark a task as complete."""
        task_id = action.get("task_id")

        if not task_id:
            return {"success": False, "error": "task_id required"}

        self.store.update(
            "tasks",
            task_id,
            {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()},
        )

        # Sync to external system
        task = self.store.get("tasks", task_id)
        if task and task.get("source") == "asana" and task.get("source_id"):
            self._complete_in_asana(task["source_id"])

        return {"success": True, "task_id": task_id}

    def _assign_task(self, action: dict) -> dict:
        """Assign a task to someone."""
        task_id = action.get("task_id")
        assignee = action.get("data", {}).get("assignee")

        if not task_id or not assignee:
            return {"success": False, "error": "task_id and assignee required"}

        self.store.update(
            "tasks",
            task_id,
            {"assignee": assignee, "updated_at": datetime.now(timezone.utc).isoformat()},
        )

        return {"success": True, "task_id": task_id, "assignee": assignee}

    def _prioritize_task(self, action: dict) -> dict:
        """Update task priority."""
        task_id = action.get("task_id")
        priority = action.get("data", {}).get("priority")

        if not task_id or priority is None:
            return {"success": False, "error": "task_id and priority required"}

        self.store.update(
            "tasks",
            task_id,
            {"priority": priority, "updated_at": datetime.now(timezone.utc).isoformat()},
        )

        return {"success": True, "task_id": task_id, "priority": priority}

    def _snooze_task(self, action: dict) -> dict:
        """Snooze a task until a later date."""
        task_id = action.get("task_id")
        until = action.get("data", {}).get("until")

        if not task_id or not until:
            return {"success": False, "error": "task_id and until date required"}

        self.store.update(
            "tasks",
            task_id,
            {
                "status": "snoozed",
                "due_date": until,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"success": True, "task_id": task_id, "snoozed_until": until}

    def _sync_to_asana(self, task_id: str, data: dict):
        """
        Sync task to Asana via API with outbox safety.

        Uses the Asana client from config to create or update a task.
        Records durable intent before external call; prevents duplicate
        creation on retry.
        """
        asana_client = self.config.get("asana_client")
        if not asana_client:
            task_logger.warning("Asana client not configured; skipping sync for task %s", task_id)
            return

        outbox = get_outbox()
        existing_gid = data.get("asana_gid")

        try:
            project_gid = data.get("asana_project_gid")
            task_data = {
                "name": data.get("title", f"Task {task_id}"),
                "notes": data.get("notes", ""),
            }
            if data.get("due_date"):
                task_data["due_on"] = data["due_date"]
            if data.get("assignee_email"):
                task_data["assignee"] = data["assignee_email"]

            if existing_gid:
                # Update existing task
                idem_key = f"task_sync_update_{task_id}_{existing_gid}"
                fulfilled = outbox.get_fulfilled_intent(idempotency_key=idem_key)
                if fulfilled:
                    task_logger.info("Asana sync update already fulfilled for task %s", task_id)
                    return

                intent_id = outbox.record_intent(
                    handler="task_sync",
                    action="update_asana",
                    payload={"task_id": task_id, "asana_gid": existing_gid},
                    idempotency_key=idem_key,
                )

                asana_client.tasks.update_task(existing_gid, task_data)
                outbox.mark_fulfilled(intent_id, external_resource_id=existing_gid)
                task_logger.info("Updated Asana task %s for local task %s", existing_gid, task_id)
            else:
                # Create new task
                idem_key = f"task_sync_create_{task_id}"
                fulfilled = outbox.get_fulfilled_intent(idempotency_key=idem_key)
                if fulfilled:
                    task_logger.info("Asana sync create already fulfilled for task %s", task_id)
                    return

                intent_id = outbox.record_intent(
                    handler="task_sync",
                    action="create_asana",
                    payload={"task_id": task_id},
                    idempotency_key=idem_key,
                )

                if project_gid:
                    task_data["projects"] = [project_gid]
                result = asana_client.tasks.create_task(task_data)
                new_gid = result.get("gid", "")

                outbox.mark_fulfilled(intent_id, external_resource_id=new_gid)
                # Store Asana GID back to local record
                self.store.update("tasks", task_id, {"asana_gid": new_gid})
                task_logger.info("Created Asana task %s for local task %s", new_gid, task_id)

        except (sqlite3.Error, ValueError, OSError) as e:
            task_logger.error("Asana sync failed for task %s: %s", task_id, e)

    def _complete_in_asana(self, asana_id: str):
        """
        Mark task complete in Asana with outbox safety.

        Records durable intent before external call; prevents duplicate
        completion on retry.
        """
        asana_client = self.config.get("asana_client")
        if not asana_client:
            task_logger.warning("Asana client not configured; skipping complete for %s", asana_id)
            return

        outbox = get_outbox()
        idem_key = f"task_complete_asana_{asana_id}"

        # Check if already completed (idempotent retry)
        fulfilled = outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            task_logger.info("Asana task %s already marked complete", asana_id)
            return

        # Record intent BEFORE external call
        intent_id = outbox.record_intent(
            handler="task_sync",
            action="complete_asana",
            payload={"asana_id": asana_id},
            idempotency_key=idem_key,
        )

        try:
            asana_client.tasks.update_task(asana_id, {"completed": True})
            outbox.mark_fulfilled(intent_id, external_resource_id=asana_id)
            task_logger.info("Marked Asana task %s as complete", asana_id)
        except (sqlite3.Error, ValueError, OSError) as e:
            outbox.mark_failed(intent_id, error=str(e))
            task_logger.error("Failed to complete Asana task %s: %s", asana_id, e)

    def _log_action(self, action: dict, result: dict):
        """Log action to database."""
        self.store.insert(
            "actions",
            {
                "id": f"action_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}",
                "type": action.get("action_type", "task_action"),
                "target_system": "tasks",
                "payload": json.dumps(
                    {
                        "action": action,
                        "task_id": action.get("task_id"),
                        "data": action.get("data", {}),
                    }
                ),
                "status": "completed" if result.get("success") else "failed",
                "requires_approval": 0,
                "result": json.dumps(result),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
