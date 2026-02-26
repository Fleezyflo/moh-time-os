"""
Email Handler - Executes email-related actions.
"""

import json
import sqlite3
from datetime import datetime


class EmailHandler:
    """Handles email-related action execution."""

    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}

    def execute(self, action: dict) -> dict:
        """Execute an email action."""
        action_type = action.get("action_type")

        handlers = {
            "draft": self._create_draft,
            "mark_processed": self._mark_processed,
            "flag": self._flag_email,
        }

        handler = handlers.get(action_type)
        if not handler:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            return handler(action)
        except (sqlite3.Error, ValueError, OSError):
            raise  # was silently swallowed

    def _create_draft(self, action: dict) -> dict:
        """Create an email draft (requires approval to send)."""
        data = action.get("data", {})
        # Store as a decision requiring approval
        self.store.insert(
            "decisions",
            {
                "id": f"email_draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "domain": "email",
                "decision_type": "send",
                "description": f"Send email to {data.get('to')}: {data.get('subject')}",
                "input_data": json.dumps(data),
                "requires_approval": 1,
                "created_at": datetime.now().isoformat(),
            },
        )
        return {"success": True, "status": "draft_created"}

    def _mark_processed(self, action: dict) -> dict:
        """Mark a communication as processed."""
        comm_id = action.get("communication_id")
        self.store.update("communications", comm_id, {"processed": 1})
        return {"success": True, "communication_id": comm_id}

    def _flag_email(self, action: dict) -> dict:
        """Flag an email for follow-up."""
        comm_id = action.get("communication_id")
        self.store.update("communications", comm_id, {"requires_response": 1})
        return {"success": True, "communication_id": comm_id}
