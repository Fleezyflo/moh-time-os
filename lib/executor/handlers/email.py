"""
Email Handler - Executes email-related actions.

Supports:
- draft: Create email draft stored as a decision requiring approval
- draft_email: Proactive email draft from communication gap signal (GAP-10-13)
- mark_processed: Mark communication as processed
- flag: Flag email for follow-up
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone

from lib.outbox import get_outbox

logger = logging.getLogger(__name__)


class EmailHandler:
    """Handles email-related action execution."""

    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}
        self._writer = None

    def _get_writer(self):
        """Lazy-initialize GmailWriter."""
        if self._writer is not None:
            return self._writer

        try:
            from lib.integrations.gmail_writer import GmailWriter

            dry_run = self.config.get("dry_run", False)
            self._writer = GmailWriter(dry_run=dry_run)
            logger.info("EmailHandler: GmailWriter enabled")
        except (ImportError, ValueError, OSError) as e:
            logger.warning("EmailHandler: GmailWriter not available: %s", e)
            self._writer = None

        return self._writer

    def execute(self, action: dict) -> dict:
        """Execute an email action."""
        action_type = action.get("action_type")

        handlers = {
            "draft": self._create_draft,
            "draft_email": self._create_proactive_draft,
            "mark_processed": self._mark_processed,
            "flag": self._flag_email,
        }

        handler = handlers.get(action_type)
        if not handler:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            return handler(action)
        except (sqlite3.Error, ValueError, OSError):
            raise

    def _create_draft(self, action: dict) -> dict:
        """Create an email draft (requires approval to send)."""
        data = action.get("data", {})
        self.store.insert(
            "decisions",
            {
                "id": f"email_draft_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "domain": "email",
                "decision_type": "send",
                "description": f"Send email to {data.get('to')}: {data.get('subject')}",
                "input_data": json.dumps(data),
                "requires_approval": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"success": True, "status": "draft_created"}

    def _create_proactive_draft(self, action: dict) -> dict:
        """
        Create a proactive email draft from communication gap signal (GAP-10-13).

        Uses entity profile context to draft a relevant check-in email.
        Creates a Gmail draft via GmailWriter if available, otherwise stores locally.
        """
        data = action.get("data", {})
        entity_id = data.get("entity_id", "")
        entity_name = data.get("entity_name", entity_id)
        to_email = data.get("to", "")
        days_since = data.get("days_since_contact", 0)

        if not to_email:
            return {"success": False, "error": "Recipient email ('to') is required"}

        # Build contextual subject and body
        subject = f"Checking in — {entity_name}"
        body = (
            f"Hi,\n\n"
            f"It's been about {days_since} days since our last exchange. "
            f"I wanted to check in and see how things are going on your end.\n\n"
            f"Is there anything you need from us, or any updates to share?\n\n"
            f"Best regards"
        )

        # Enrich with entity profile context if available
        context_notes = data.get("context", "")
        if context_notes:
            body = (
                f"Hi,\n\n"
                f"It's been about {days_since} days since our last exchange. "
                f"{context_notes}\n\n"
                f"Is there anything you need from us, or any updates to share?\n\n"
                f"Best regards"
            )

        # Try to create Gmail draft via writer — with outbox safety
        writer = self._get_writer()
        gmail_draft_id = None
        if writer is not None:
            outbox = get_outbox()
            idem_key = f"email_draft_{entity_id}_{to_email}_{days_since}"

            # Check if already fulfilled (idempotent retry)
            fulfilled = outbox.get_fulfilled_intent(idempotency_key=idem_key)
            if fulfilled:
                gmail_draft_id = fulfilled.get("external_resource_id")
                logger.info(
                    "Email draft already created via Gmail for %s (draft_id=%s)",
                    entity_name,
                    gmail_draft_id,
                )
            else:
                # Record intent BEFORE calling Gmail API
                intent_id = outbox.record_intent(
                    handler="email",
                    action="create_draft",
                    payload={"to": to_email, "subject": subject, "entity_id": entity_id},
                    idempotency_key=idem_key,
                )

                result = writer.create_draft(to=to_email, subject=subject, body=body)
                if result.success:
                    gmail_draft_id = result.data.get("id") if result.data else None
                    outbox.mark_fulfilled(intent_id, external_resource_id=gmail_draft_id)
                    logger.info(
                        "Proactive email draft created via Gmail for %s (draft_id=%s)",
                        entity_name,
                        gmail_draft_id,
                    )
                else:
                    outbox.mark_failed(intent_id, error=result.error or "create_draft failed")

        # Always store as decision requiring approval
        decision_id = f"proactive_draft_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.store.insert(
            "decisions",
            {
                "id": decision_id,
                "domain": "email",
                "decision_type": "proactive_send",
                "description": f"Proactive check-in with {entity_name} ({to_email})",
                "input_data": json.dumps(
                    {
                        "to": to_email,
                        "subject": subject,
                        "body": body,
                        "entity_id": entity_id,
                        "entity_name": entity_name,
                        "days_since_contact": days_since,
                        "gmail_draft_id": gmail_draft_id,
                        "signal_id": data.get("signal_id", "sig_client_comm_gap"),
                    }
                ),
                "requires_approval": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {
            "success": True,
            "status": "proactive_draft_created",
            "decision_id": decision_id,
            "gmail_draft_id": gmail_draft_id,
        }

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
