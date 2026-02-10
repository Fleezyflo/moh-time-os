"""
Event/State Audit Trail.

Append-only event log for state reconstruction and debugging.
Supports:
- Event recording with trace/request IDs
- State replay from events
- Event querying by entity/type/time
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lib.observability import get_request_id
from lib.observability.tracing import get_trace_id

# ============================================================================
# Event Types
# ============================================================================


@dataclass
class AuditEvent:
    """An audit event."""

    event_id: str
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    timestamp: str
    request_id: str | None = None
    trace_id: str | None = None
    actor: str | None = None


# ============================================================================
# Audit Store
# ============================================================================


class AuditStore:
    """
    Append-only audit event store.

    Events are immutable once written.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create audit table if not exists."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                request_id TEXT,
                trace_id TEXT,
                actor TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_entity
            ON audit_events(entity_type, entity_id)
        """
        )
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_type
            ON audit_events(event_type)
        """
        )
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_events(timestamp)
        """
        )
        self.conn.commit()

    def record(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        actor: str | None = None,
    ) -> AuditEvent:
        """Record an audit event."""
        import secrets

        event = AuditEvent(
            event_id=f"evt-{secrets.token_hex(8)}",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=get_request_id(),
            trace_id=get_trace_id(),
            actor=actor,
        )

        self.conn.execute(
            """
            INSERT INTO audit_events
            (event_id, event_type, entity_type, entity_id, payload,
             timestamp, request_id, trace_id, actor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                event.event_id,
                event.event_type,
                event.entity_type,
                event.entity_id,
                json.dumps(event.payload),
                event.timestamp,
                event.request_id,
                event.trace_id,
                event.actor,
            ),
        )
        self.conn.commit()

        return event

    def get_events(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        event_type: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events."""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list[Any] = []

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)

        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)

        events = []
        for row in cursor.fetchall():
            events.append(
                AuditEvent(
                    event_id=row[0],
                    event_type=row[1],
                    entity_type=row[2],
                    entity_id=row[3],
                    payload=json.loads(row[4]),
                    timestamp=row[5],
                    request_id=row[6],
                    trace_id=row[7],
                    actor=row[8],
                )
            )

        return events


# ============================================================================
# State Replay
# ============================================================================


class StateReplayer:
    """
    Replays events to reconstruct entity state.

    Supports:
    - Point-in-time reconstruction
    - Event-by-event replay
    """

    def __init__(self, store: AuditStore):
        self.store = store

    def replay_entity(
        self,
        entity_type: str,
        entity_id: str,
        until: str | None = None,
    ) -> dict[str, Any]:
        """
        Replay events for an entity to reconstruct state.

        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            until: Optional timestamp to replay until

        Returns:
            Reconstructed state dict
        """
        events = self.store.get_events(
            entity_type=entity_type,
            entity_id=entity_id,
            limit=10000,
        )

        state: dict[str, Any] = {}

        for event in events:
            if until and event.timestamp > until:
                break

            # Apply event to state
            state = self._apply_event(state, event)

        return state

    def _apply_event(self, state: dict[str, Any], event: AuditEvent) -> dict[str, Any]:
        """Apply an event to state."""
        event_type = event.event_type

        if event_type.endswith("_created"):
            # Creation event sets initial state
            state = event.payload.copy()
            state["_created_at"] = event.timestamp
            state["_events"] = [event.event_id]

        elif event_type.endswith("_updated"):
            # Update event merges with existing state
            state.update(event.payload)
            state["_updated_at"] = event.timestamp
            state.setdefault("_events", []).append(event.event_id)

        elif event_type.endswith("_deleted"):
            # Deletion marks state as deleted
            state["_deleted"] = True
            state["_deleted_at"] = event.timestamp
            state.setdefault("_events", []).append(event.event_id)

        else:
            # Generic event - store in _events
            state.setdefault("_events", []).append(event.event_id)
            state[f"_last_{event_type}"] = event.timestamp

        return state


# ============================================================================
# Convenience Functions
# ============================================================================

_store: AuditStore | None = None


def init_audit(conn: sqlite3.Connection) -> AuditStore:
    """Initialize the global audit store."""
    global _store
    _store = AuditStore(conn)
    return _store


def get_store() -> AuditStore:
    """Get the global audit store."""
    if _store is None:
        raise RuntimeError("Audit store not initialized. Call init_audit() first.")
    return _store


def record_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
    actor: str | None = None,
) -> AuditEvent:
    """Record an audit event using the global store."""
    return get_store().record(event_type, entity_type, entity_id, payload, actor)
