"""
Outbox Pattern — Durable intent recording before external side effects.

Guarantees:
1. Intent is durably recorded BEFORE any external API call.
2. External calls include an idempotency key derived from the intent ID.
3. If external call succeeds but local state update fails, the outbox
   entry tracks the external resource ID for reconciliation.
4. Retries are safe: the outbox prevents duplicate external effects
   by checking whether the intent was already fulfilled.
5. On restart, unfulfilled intents are visible for manual reconciliation.

Usage:
    outbox = get_outbox()

    # Record intent BEFORE calling external API
    intent_id = outbox.record_intent(
        handler="calendar",
        action="create_event",
        payload={"summary": "Meeting", ...},
        idempotency_key="action_abc123_calendar",
    )

    # Check if already fulfilled (idempotent retry)
    existing = outbox.get_fulfilled_intent(idempotency_key="action_abc123_calendar")
    if existing:
        return existing["external_resource_id"]

    # Call external API
    event_id = google_calendar.create_event(...)

    # Mark fulfilled with external resource ID
    outbox.mark_fulfilled(intent_id, external_resource_id=event_id)
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone

from lib import db as db_module

logger = logging.getLogger(__name__)

_OUTBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS side_effect_outbox (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    handler TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    external_resource_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    fulfilled_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0
)
"""

_IDEMPOTENCY_SCHEMA = """
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


class SideEffectOutbox:
    """
    Durable outbox for external side effects.

    Records intent before external calls. Tracks fulfillment.
    Prevents duplicate effects via idempotency keys.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or db_module.get_db_path_str()
        self._lock = threading.Lock()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self):
        conn = self._get_conn()
        try:
            conn.execute(_OUTBOX_SCHEMA)
            conn.execute(_IDEMPOTENCY_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def record_intent(
        self,
        handler: str,
        action: str,
        payload: dict,
        idempotency_key: str,
    ) -> str:
        """
        Durably record intent to perform an external side effect.

        If an intent with the same idempotency_key already exists and is
        fulfilled, returns the existing intent ID (no duplicate created).

        If an intent exists but is pending/failed, returns it for retry.

        Returns the intent ID.
        """
        from uuid import uuid4

        intent_id = f"intent_{uuid4().hex[:16]}"
        now = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            # Check for existing intent with same idempotency key
            existing = conn.execute(
                "SELECT id, status, external_resource_id FROM side_effect_outbox "
                "WHERE idempotency_key = ?",
                [idempotency_key],
            ).fetchone()

            if existing:
                return existing["id"]

            conn.execute(
                "INSERT INTO side_effect_outbox "
                "(id, idempotency_key, handler, action, payload, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                [
                    intent_id,
                    idempotency_key,
                    handler,
                    action,
                    json.dumps(payload),
                    now,
                ],
            )
            conn.commit()
            logger.info(
                "Outbox: recorded intent %s (handler=%s, action=%s, key=%s)",
                intent_id,
                handler,
                action,
                idempotency_key,
            )
            return intent_id
        finally:
            conn.close()

    def mark_fulfilled(
        self,
        intent_id: str,
        external_resource_id: str | None = None,
    ) -> bool:
        """
        Mark intent as fulfilled after successful external call.

        Stores the external_resource_id for reconciliation.
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            result = conn.execute(
                "UPDATE side_effect_outbox SET "
                "status = 'fulfilled', "
                "external_resource_id = ?, "
                "fulfilled_at = ?, "
                "attempts = attempts + 1 "
                "WHERE id = ?",
                [external_resource_id, now, intent_id],
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info(
                    "Outbox: fulfilled intent %s (external_id=%s)",
                    intent_id,
                    external_resource_id,
                )
                return True
            return False
        finally:
            conn.close()

    def mark_failed(self, intent_id: str, error: str) -> bool:
        """Mark intent as failed after external call failure."""
        conn = self._get_conn()
        try:
            result = conn.execute(
                "UPDATE side_effect_outbox SET "
                "status = 'failed', "
                "error = ?, "
                "attempts = attempts + 1 "
                "WHERE id = ?",
                [error[:500], intent_id],
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info("Outbox: failed intent %s: %s", intent_id, error[:100])
                return True
            return False
        finally:
            conn.close()

    def get_fulfilled_intent(self, idempotency_key: str) -> dict | None:
        """
        Get a fulfilled intent by idempotency key.

        Used by handlers to check if an effect was already performed
        before calling the external API (idempotent retry).
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM side_effect_outbox "
                "WHERE idempotency_key = ? AND status = 'fulfilled'",
                [idempotency_key],
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_intent(self, intent_id: str) -> dict | None:
        """Get an intent by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM side_effect_outbox WHERE id = ?",
                [intent_id],
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_pending_intents(self, handler: str | None = None) -> list[dict]:
        """Get all pending (unfulfilled) intents, optionally filtered by handler."""
        conn = self._get_conn()
        try:
            if handler:
                rows = conn.execute(
                    "SELECT * FROM side_effect_outbox "
                    "WHERE status IN ('pending', 'failed') AND handler = ? "
                    "ORDER BY created_at ASC",
                    [handler],
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM side_effect_outbox "
                    "WHERE status IN ('pending', 'failed') "
                    "ORDER BY created_at ASC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Reconciliation queries ──

    def get_all_intents(
        self,
        status: str | None = None,
        handler: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get intents with optional filters. For reconciliation UI.

        status: 'pending', 'fulfilled', 'failed', or None for all.
        handler: filter by handler name, or None for all.
        """
        conn = self._get_conn()
        try:
            # Build query with hardcoded filter branches — no f-string SQL
            params: list[str | int] = []

            if status and handler:
                query = (
                    "SELECT * FROM side_effect_outbox "
                    "WHERE status = ? AND handler = ? "
                    "ORDER BY created_at DESC LIMIT ?"
                )
                params = [status, handler, limit]
            elif status:
                query = (
                    "SELECT * FROM side_effect_outbox "
                    "WHERE status = ? "
                    "ORDER BY created_at DESC LIMIT ?"
                )
                params = [status, limit]
            elif handler:
                query = (
                    "SELECT * FROM side_effect_outbox "
                    "WHERE handler = ? "
                    "ORDER BY created_at DESC LIMIT ?"
                )
                params = [handler, limit]
            else:
                query = "SELECT * FROM side_effect_outbox ORDER BY created_at DESC LIMIT ?"
                params = [limit]

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Get intent counts by status. For reconciliation dashboard."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM side_effect_outbox GROUP BY status"
            ).fetchall()
            stats = {row["status"]: row["count"] for row in rows}
            return {
                "pending": stats.get("pending", 0),
                "fulfilled": stats.get("fulfilled", 0),
                "failed": stats.get("failed", 0),
                "total": sum(stats.values()),
            }
        finally:
            conn.close()

    def reset_failed_to_pending(self, intent_id: str) -> bool:
        """
        Reset a failed intent back to pending for retry.

        Used by reconciliation to re-attempt a failed external call.
        """
        conn = self._get_conn()
        try:
            result = conn.execute(
                "UPDATE side_effect_outbox SET status = 'pending', error = NULL "
                "WHERE id = ? AND status = 'failed'",
                [intent_id],
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info("Outbox: reset failed intent %s to pending", intent_id)
                return True
            return False
        finally:
            conn.close()

    def force_fulfill(self, intent_id: str, external_resource_id: str | None = None) -> bool:
        """
        Force-mark an intent as fulfilled (operator reconciliation).

        Use when the external effect is confirmed to have succeeded
        but the outbox was not updated (e.g., crash between external
        call and mark_fulfilled). This prevents duplicate on retry.
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            result = conn.execute(
                "UPDATE side_effect_outbox SET "
                "status = 'fulfilled', "
                "external_resource_id = ?, "
                "fulfilled_at = ?, "
                "error = 'force_fulfilled_by_operator' "
                "WHERE id = ? AND status IN ('pending', 'failed')",
                [external_resource_id, now, intent_id],
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info(
                    "Outbox: force-fulfilled intent %s (external_id=%s)",
                    intent_id,
                    external_resource_id,
                )
                return True
            return False
        finally:
            conn.close()

    # ── Idempotency key persistence ──

    def store_idempotency_key(self, key: str, action_id: str) -> bool:
        """
        Persist an idempotency key → action_id mapping.

        Returns True if stored, False if key already exists.
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO idempotency_keys (key, action_id, created_at) "
                "VALUES (?, ?, ?)",
                [key, action_id, now],
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def get_idempotency_action(self, key: str) -> str | None:
        """
        Look up an action_id by idempotency key.

        Returns action_id if key exists, None otherwise.
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT action_id FROM idempotency_keys WHERE key = ?",
                [key],
            ).fetchone()
            return row["action_id"] if row else None
        finally:
            conn.close()


# Singleton
_outbox: SideEffectOutbox | None = None
_outbox_lock = threading.Lock()


def get_outbox(db_path: str | None = None) -> SideEffectOutbox:
    """Get the singleton outbox instance."""
    global _outbox
    if _outbox is None:
        with _outbox_lock:
            if _outbox is None:
                _outbox = SideEffectOutbox(db_path)
    return _outbox
