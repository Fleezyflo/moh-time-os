"""
Outbox-safe ChatInteractive wrapper.

Wraps all external mutation methods of ChatInteractive with the outbox
durable-intent pattern:
1. Check for fulfilled intent (idempotent skip)
2. Record durable intent BEFORE external API call
3. Call external API
4. Mark fulfilled with external resource ID, or mark failed
5. Retry-safe: same idempotency key returns same intent

This module is the ONLY sanctioned path for ChatInteractive mutations.
Direct use of ChatInteractive for mutations bypasses the outbox.
"""

import hashlib
import json
import logging

from lib.integrations.chat_interactive import ChatInteractive, ChatWriteResult
from lib.outbox import SideEffectOutbox, get_outbox

logger = logging.getLogger(__name__)

_HANDLER = "chat_interactive"


def _idem_key(action: str, **kwargs: object) -> str:
    """Generate a deterministic idempotency key from action and payload."""
    payload_str = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{action}:{payload_str}".encode()).hexdigest()[:16]
    return f"chat_{action}_{digest}"


class SafeChatInteractive:
    """Outbox-protected ChatInteractive facade.

    Every mutation method follows the durable-intent pattern:
    record intent → external call → mark fulfilled/failed.
    """

    def __init__(
        self,
        client: ChatInteractive | None = None,
        outbox: SideEffectOutbox | None = None,
    ):
        self._client = client or ChatInteractive(_direct_call_allowed=True)
        self._outbox = outbox or get_outbox()

    # ── send_message ─────────────────────────────────────────────

    def send_message(
        self,
        space_id: str,
        text: str,
        thread_key: str | None = None,
    ) -> ChatWriteResult:
        """Send a text message with outbox protection."""
        idem_key = _idem_key("send_message", space_id=space_id, text=text, thread_key=thread_key)

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return ChatWriteResult(
                success=True,
                message_name=fulfilled.get("external_resource_id"),
            )

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="send_message",
            payload={"space_id": space_id, "text": text[:200], "thread_key": thread_key},
            idempotency_key=idem_key,
        )

        result = self._client.send_message(space_id, text, thread_key)

        if result.success:
            self._outbox.mark_fulfilled(intent_id, external_resource_id=result.message_name or "")
        else:
            self._outbox.mark_failed(intent_id, error=result.error or "Unknown error")

        return result

    # ── send_card ────────────────────────────────────────────────

    def send_card(
        self,
        space_id: str,
        card: dict,
        thread_key: str | None = None,
    ) -> ChatWriteResult:
        """Send a card message with outbox protection."""
        idem_key = _idem_key(
            "send_card", space_id=space_id, card_id=card.get("id", "default"), thread_key=thread_key
        )

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return ChatWriteResult(
                success=True,
                message_name=fulfilled.get("external_resource_id"),
            )

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="send_card",
            payload={
                "space_id": space_id,
                "card_id": card.get("id", "default"),
                "thread_key": thread_key,
            },
            idempotency_key=idem_key,
        )

        result = self._client.send_card(space_id, card, thread_key)

        if result.success:
            self._outbox.mark_fulfilled(intent_id, external_resource_id=result.message_name or "")
        else:
            self._outbox.mark_failed(intent_id, error=result.error or "Unknown error")

        return result

    # ── update_message ───────────────────────────────────────────

    def update_message(
        self,
        message_name: str,
        text: str | None = None,
        card: dict | None = None,
    ) -> ChatWriteResult:
        """Update an existing message with outbox protection."""
        idem_key = _idem_key(
            "update_message", message_name=message_name, text=text, card_id=(card or {}).get("id")
        )

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return ChatWriteResult(
                success=True,
                message_name=fulfilled.get("external_resource_id"),
            )

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="update_message",
            payload={
                "message_name": message_name,
                "has_text": text is not None,
                "has_card": card is not None,
            },
            idempotency_key=idem_key,
        )

        result = self._client.update_message(message_name, text, card)

        if result.success:
            self._outbox.mark_fulfilled(
                intent_id, external_resource_id=result.message_name or message_name
            )
        else:
            self._outbox.mark_failed(intent_id, error=result.error or "Unknown error")

        return result

    # ── delete_message ───────────────────────────────────────────

    def delete_message(self, message_name: str) -> ChatWriteResult:
        """Delete a message with outbox protection."""
        idem_key = _idem_key("delete_message", message_name=message_name)

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return ChatWriteResult(success=True, message_name=message_name)

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="delete_message",
            payload={"message_name": message_name},
            idempotency_key=idem_key,
        )

        result = self._client.delete_message(message_name)

        if result.success:
            self._outbox.mark_fulfilled(intent_id, external_resource_id=message_name)
        else:
            self._outbox.mark_failed(intent_id, error=result.error or "Unknown error")

        return result

    # ── create_space ─────────────────────────────────────────────

    def create_space(
        self,
        display_name: str,
        space_type: str = "ROOM",
    ) -> ChatWriteResult:
        """Create a new space with outbox protection."""
        idem_key = _idem_key("create_space", display_name=display_name, space_type=space_type)

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return ChatWriteResult(
                success=True,
                space_name=fulfilled.get("external_resource_id"),
            )

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="create_space",
            payload={"display_name": display_name, "space_type": space_type},
            idempotency_key=idem_key,
        )

        result = self._client.create_space(display_name, space_type)

        if result.success:
            self._outbox.mark_fulfilled(intent_id, external_resource_id=result.space_name or "")
        else:
            self._outbox.mark_failed(intent_id, error=result.error or "Unknown error")

        return result

    # ── add_member ───────────────────────────────────────────────

    def add_member(
        self,
        space_name: str,
        member_email: str,
    ) -> ChatWriteResult:
        """Add a member to a space with outbox protection."""
        idem_key = _idem_key("add_member", space_name=space_name, member_email=member_email)

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return ChatWriteResult(success=True, data={"member": member_email})

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="add_member",
            payload={"space_name": space_name, "member_email": member_email},
            idempotency_key=idem_key,
        )

        result = self._client.add_member(space_name, member_email)

        if result.success:
            ext_id = (result.data or {}).get("name", f"{space_name}/members/{member_email}")
            self._outbox.mark_fulfilled(intent_id, external_resource_id=ext_id)
        else:
            self._outbox.mark_failed(intent_id, error=result.error or "Unknown error")

        return result
