"""
Delegation Handler - Executes delegation actions.

Handles:
- Delegating tasks to team members
- Sending handoff communications
- Tracking delegation status
- Escalation workflows
"""

import json
import sqlite3
from datetime import datetime


class DelegationHandler:
    """Handles delegation-related action execution."""

    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}
        self.delegation_config = self._load_delegation_config()

    def _load_delegation_config(self) -> dict:
        """Load delegation routing config."""
        # Would load from config/delegation.yaml
        return self.config.get("delegation", {})

    def execute(self, action: dict) -> dict:
        """
        Execute a delegation action.

        Args:
            action: {
                'action_type': 'delegate'|'escalate'|'handoff'|'recall',
                'task_id': str,
                'data': {...}
            }

        Returns:
            {success: bool, result?: any, error?: str}
        """
        action_type = action.get("action_type")

        handlers = {
            "delegate": self._delegate_task,
            "escalate": self._escalate_task,
            "handoff": self._send_handoff,
            "recall": self._recall_delegation,
        }

        handler = handlers.get(action_type)
        if not handler:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            result = handler(action)
            self._log_action(action, result)
            return result
        except (sqlite3.Error, ValueError, OSError):
            raise  # was silently swallowed

    def _delegate_task(self, action: dict) -> dict:
        """Delegate a task to someone."""
        task_id = action.get("task_id")
        data = action.get("data", {})
        delegate_to = data.get("delegate_to")

        if not task_id or not delegate_to:
            return {"success": False, "error": "task_id and delegate_to required"}

        # Get the task
        task = self.store.get("tasks", task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        # Update task assignment
        self.store.update(
            "tasks",
            task_id,
            {
                "assignee": delegate_to,
                "waiting_for": delegate_to,
                "status": "delegated",
                "updated_at": datetime.now().isoformat(),
                "context": json.dumps(
                    {
                        **json.loads(task.get("context") or "{}"),
                        "delegated_at": datetime.now().isoformat(),
                        "delegated_to": delegate_to,
                        "delegated_by": "moh",
                    }
                ),
            },
        )

        # Create handoff notification
        self._create_handoff_notification(task, delegate_to, data.get("message"))

        return {"success": True, "task_id": task_id, "delegated_to": delegate_to}

    def _escalate_task(self, action: dict) -> dict:
        """Escalate a task up the chain."""
        task_id = action.get("task_id")
        data = action.get("data", {})
        reason = data.get("reason", "Needs attention")

        if not task_id:
            return {"success": False, "error": "task_id required"}

        task = self.store.get("tasks", task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        # Get escalation path from config
        escalation_path = self.delegation_config.get("escalation", {}).get("default_path", [])

        # Find next escalation target
        current_assignee = task.get("assignee")
        next_target = None

        for i, target in enumerate(escalation_path):
            if target == current_assignee and i + 1 < len(escalation_path):
                next_target = escalation_path[i + 1]
                break

        if not next_target:
            next_target = "moh"  # Default escalation to Moh

        # Update task
        self.store.update(
            "tasks",
            task_id,
            {
                "assignee": next_target,
                "priority": min((task.get("priority") or 50) + 20, 100),  # Bump priority
                "status": "escalated",
                "updated_at": datetime.now().isoformat(),
                "context": json.dumps(
                    {
                        **json.loads(task.get("context") or "{}"),
                        "escalated_at": datetime.now().isoformat(),
                        "escalation_reason": reason,
                        "escalated_from": current_assignee,
                    }
                ),
            },
        )

        # Create escalation notification
        self.store.insert(
            "notifications",
            {
                "id": f"notif_escalate_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "type": "alert",
                "priority": "high",
                "title": f"Escalation: {task.get('title')}",
                "body": f"Task escalated from {current_assignee}. Reason: {reason}",
                "created_at": datetime.now().isoformat(),
            },
        )

        return {
            "success": True,
            "task_id": task_id,
            "escalated_to": next_target,
            "reason": reason,
        }

    def _send_handoff(self, action: dict) -> dict:
        """Send a handoff communication."""
        task_id = action.get("task_id")
        data = action.get("data", {})
        recipient = data.get("recipient")
        message = data.get("message")

        if not task_id or not recipient:
            return {"success": False, "error": "task_id and recipient required"}

        task = self.store.get("tasks", task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        self._create_handoff_notification(task, recipient, message)

        return {"success": True, "task_id": task_id, "recipient": recipient}

    def _recall_delegation(self, action: dict) -> dict:
        """Recall a delegated task."""
        task_id = action.get("task_id")

        if not task_id:
            return {"success": False, "error": "task_id required"}

        task = self.store.get("tasks", task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        previous_assignee = task.get("assignee")

        self.store.update(
            "tasks",
            task_id,
            {
                "assignee": "moh",
                "waiting_for": None,
                "status": "pending",
                "updated_at": datetime.now().isoformat(),
                "context": json.dumps(
                    {
                        **json.loads(task.get("context") or "{}"),
                        "recalled_at": datetime.now().isoformat(),
                        "recalled_from": previous_assignee,
                    }
                ),
            },
        )

        return {"success": True, "task_id": task_id, "recalled_from": previous_assignee}

    def _create_handoff_notification(self, task: dict, recipient: str, message: str = None):
        """Create a handoff notification."""
        # Get recipient info
        people = self.store.query("SELECT name, email FROM people WHERE email = ?", [recipient])
        recipient_name = people[0]["name"] if people else recipient

        body = f"Task: {task.get('title')}\n"
        if task.get("due_date"):
            body += f"Due: {task.get('due_date')}\n"
        if message:
            body += f"\n{message}"

        self.store.insert(
            "notifications",
            {
                "id": f"notif_handoff_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "type": "alert",
                "priority": "normal",
                "title": f"Delegated to {recipient_name}",
                "body": body,
                "created_at": datetime.now().isoformat(),
            },
        )

    def get_delegation_suggestions(self, task: dict) -> list:
        """Get suggested delegates for a task."""
        lane = task.get("lane", "ops")

        # Get routing config for lane
        routing = self.delegation_config.get("routing", {}).get(lane, {})
        primary = routing.get("primary")

        suggestions = []
        if primary:
            suggestions.append(
                {
                    "email": primary,
                    "role": "primary",
                    "reason": f"Primary delegate for {lane}",
                }
            )

        return suggestions

    def _log_action(self, action: dict, result: dict):
        """Log action to database."""
        self.store.insert(
            "actions",
            {
                "id": f"action_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                "domain": "delegation",
                "action_type": action.get("action_type"),
                "target_id": action.get("task_id"),
                "data": json.dumps(action.get("data", {})),
                "result": json.dumps(result),
                "status": "completed" if result.get("success") else "failed",
                "created_at": datetime.now().isoformat(),
            },
        )
