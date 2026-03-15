"""
Outbox-safe send_sync wrapper for notification channels.

Wraps direct channel.send_sync() calls (used by daemon, morning_brief,
and autonomous_loop) with the durable-intent outbox pattern.

Usage:
    from lib.notifier.channels.safe_send import safe_send_sync

    result = safe_send_sync(
        channel=google_chat_channel,
        message="Daily digest...",
        title="Morning Brief",
        caller="morning_brief",
    )

This ensures:
1. Durable intent before external send
2. Fulfilled/failed tracking
3. Retry-safe via idempotency key
4. Reconciliation visibility for failed sends
"""

import hashlib
import logging

from lib.outbox import SideEffectOutbox, get_outbox

logger = logging.getLogger(__name__)

_HANDLER = "notification"


def safe_send_sync(
    channel: object,
    message: str,
    title: str | None = None,
    caller: str = "unknown",
    outbox: SideEffectOutbox | None = None,
    **kwargs: object,
) -> dict:
    """Send a notification via channel.send_sync() with outbox protection.

    Args:
        channel: Any notification channel with a send_sync(message, ...) method.
        message: Message content to send.
        title: Optional title for the message.
        caller: Identifying label for the caller (e.g. "daemon", "morning_brief").
        outbox: Optional outbox instance (uses singleton if not provided).
        **kwargs: Additional keyword arguments forwarded to send_sync().

    Returns:
        dict with status/success/error keys from channel.send_sync(),
        or a synthetic result if the outbox shows already fulfilled.
    """
    _outbox = outbox or get_outbox()

    # Idempotency key based on caller + message content hash
    msg_hash = hashlib.sha256(f"{caller}:{title}:{message[:500]}".encode()).hexdigest()[:16]
    idem_key = f"notif_{caller}_{msg_hash}"

    # Check for already-fulfilled intent
    fulfilled = _outbox.get_fulfilled_intent(idempotency_key=idem_key)
    if fulfilled:
        logger.debug("Notification already sent (outbox fulfilled): %s", idem_key)
        return {
            "status": "already_sent",
            "success": True,
            "message_id": fulfilled.get("external_resource_id", ""),
        }

    # Record durable intent BEFORE external send
    intent_id = _outbox.record_intent(
        handler=_HANDLER,
        action=f"send_sync_{caller}",
        payload={
            "caller": caller,
            "title": title,
            "message_preview": message[:200],
        },
        idempotency_key=idem_key,
    )

    # Call the actual channel.send_sync()
    try:
        if title:
            result = channel.send_sync(message, title=title, **kwargs)
        else:
            result = channel.send_sync(message, **kwargs)
    except (ValueError, OSError, AttributeError) as e:
        error_msg = f"send_sync exception: {e}"
        logger.error("safe_send_sync failed for %s: %s", caller, error_msg)
        _outbox.mark_failed(intent_id, error=error_msg)
        return {"status": "error", "success": False, "error": error_msg}

    # Mark based on result
    if isinstance(result, dict) and result.get("success"):
        ext_id = result.get("message_id") or result.get("response", "")
        _outbox.mark_fulfilled(intent_id, external_resource_id=str(ext_id)[:500])
    else:
        error = ""
        if isinstance(result, dict):
            error = result.get("error", "Unknown send error")
        else:
            error = str(result)[:500]
        _outbox.mark_failed(intent_id, error=error)

    return result if isinstance(result, dict) else {"status": "unknown", "success": False}
