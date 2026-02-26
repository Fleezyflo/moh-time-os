"""
Notification Handler - Executes notification actions.

Handles:
- Creating notifications
- Triggering immediate sends
- Managing notification preferences
"""

import json
from datetime import datetime
import sqlite3


class NotificationHandler:
    """Handles notification-related action execution."""

    def __init__(self, store, notifier=None, config: dict = None):
        self.store = store
        self.notifier = notifier
        self.config = config or {}

    def execute(self, action: dict) -> dict:
        """
        Execute a notification action.

        Args:
            action: {
                'action_type': 'create'|'send_immediate'|'batch'|'cancel',
                'data': {...}
            }

        Returns:
            {success: bool, result?: any, error?: str}
        """
        action_type = action.get("action_type")

        handlers = {
            "create": self._create_notification,
            "send_immediate": self._send_immediate,
            "batch": self._batch_notifications,
            "cancel": self._cancel_notification,
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

    def _create_notification(self, action: dict) -> dict:
        """Create a notification for later delivery."""
        data = action.get("data", {})

        notif_id = self.store.insert(
            "notifications",
            {
                "id": f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                "type": data.get("type", "alert"),
                "priority": data.get("priority", "normal"),
                "title": data["title"],
                "body": data.get("body"),
                "action_url": data.get("action_url"),
                "action_data": json.dumps(data.get("action_data"))
                if data.get("action_data")
                else None,
                "channels": json.dumps(data.get("channels")) if data.get("channels") else None,
                "created_at": datetime.now().isoformat(),
            },
        )

        return {"success": True, "notification_id": notif_id}

    def _send_immediate(self, action: dict) -> dict:
        """Create and immediately send a notification."""
        action.get("data", {})

        # Create the notification
        create_result = self._create_notification(action)
        if not create_result["success"]:
            return create_result

        # If we have a notifier, process immediately
        if self.notifier:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            results = loop.run_until_complete(self.notifier.process_pending())

            return {
                "success": True,
                "notification_id": create_result["notification_id"],
                "delivery": results,
            }

        return create_result

    def _batch_notifications(self, action: dict) -> dict:
        """Create multiple notifications for batched delivery."""
        items = action.get("data", {}).get("items", [])

        created = []
        for item in items:
            result = self._create_notification({"data": item})
            if result["success"]:
                created.append(result["notification_id"])

        return {
            "success": True,
            "created_count": len(created),
            "notification_ids": created,
        }

    def _cancel_notification(self, action: dict) -> dict:
        """Cancel a pending notification."""
        notif_id = action.get("notification_id")

        if not notif_id:
            return {"success": False, "error": "notification_id required"}

        # Check if already sent
        notif = self.store.get("notifications", notif_id)
        if notif and notif.get("sent_at"):
            return {"success": False, "error": "Notification already sent"}

        self.store.delete("notifications", notif_id)

        return {"success": True, "notification_id": notif_id}

    def _log_action(self, action: dict, result: dict):
        """Log action to database."""
        self.store.insert(
            "actions",
            {
                "id": f"action_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                "domain": "notifications",
                "action_type": action.get("action_type"),
                "target_id": result.get("notification_id"),
                "data": json.dumps(action.get("data", {})),
                "result": json.dumps(result),
                "status": "completed" if result.get("success") else "failed",
                "created_at": datetime.now().isoformat(),
            },
        )
