"""
End-to-end action integration tests.

GAP-10-09: Tests the full propose -> approve -> execute -> verify chain
across Asana and email handlers in dry_run mode.

Muting and analytics tests (TestNotificationMuting, TestNotificationAnalytics)
use real SQLite fixture DBs to verify persistence boundaries honestly.
ActionFramework tests use Mock stores (correct: they test state machine logic,
not persistence).
"""

import sqlite3
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from lib.actions.action_framework import (
    ActionFramework,
    ActionSource,
    RiskLevel,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_store():
    """Provide a mock state store matching test_action_framework pattern.

    Mock's auto-created .query() and .insert() satisfy DigestEngine's
    store interface without touching any real database.
    """
    store = Mock()
    store.data = {}

    def insert(table, data):
        if table not in store.data:
            store.data[table] = {}
        id_ = data.get("id", f"id_{len(store.data[table])}")
        store.data[table][id_] = data
        return id_

    def get(table, id_):
        if table in store.data and id_ in store.data[table]:
            return store.data[table][id_]
        return None

    def update(table, id_, updates):
        if table in store.data and id_ in store.data[table]:
            store.data[table][id_].update(updates)
            return True
        return False

    def query(q, params=None):
        if "WHERE status = ?" in q:
            status = params[0] if params else None
            table_name = "actions"
            if table_name in store.data:
                results = [v for v in store.data[table_name].values() if v.get("status") == status]
                if "LIMIT ?" in q:
                    limit = params[-1] if params else 50
                    results = results[:limit]
                return results
        if "WHERE status IN" in q:
            statuses = params[:3] if params else []
            table_name = "actions"
            if table_name in store.data:
                return [v for v in store.data[table_name].values() if v.get("status") in statuses]
        return []

    def count(table, where="", params=None):
        return 0

    store.insert = Mock(side_effect=insert)
    store.get = Mock(side_effect=get)
    store.update = Mock(side_effect=update)
    store.query = Mock(side_effect=query)
    store.count = Mock(side_effect=count)
    store.delete = Mock()
    return store


@pytest.fixture
def framework(mock_store):
    """Create ActionFramework in dry_run mode."""
    return ActionFramework(store=mock_store, dry_run=True)


# =============================================================================
# ASANA HANDLER INTEGRATION TESTS
# =============================================================================


class TestAsanaHandlerIntegration:
    """Tests for Asana action handler through the framework pipeline."""

    def test_propose_asana_create_task(self, framework):
        """Propose an Asana create_task action."""
        action_id = framework.propose_action(
            action_type="asana_create_task",
            target_entity="task",
            target_id="project_123",
            payload={
                "action_type": "create_task",
                "data": {
                    "name": "Follow up with Acme Corp",
                    "project_gid": "12345",
                    "notes": "Communication gap detected",
                    "due_on": "2026-03-15",
                },
            },
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
            confidence_score=0.85,
            requires_approval=True,
        )
        assert action_id.startswith("action_")

        # Verify it's in PROPOSED state
        pending = framework.get_pending_actions()
        assert len(pending) == 1
        assert pending[0]["type"] == "asana_create_task"

    def test_approve_and_execute_asana_task_dry_run(self, framework):
        """Full lifecycle: propose -> approve -> execute (dry_run)."""
        action_id = framework.propose_action(
            action_type="asana_create_task",
            target_entity="task",
            target_id="project_123",
            payload={
                "action_type": "create_task",
                "data": {
                    "name": "Test task",
                    "project_gid": "12345",
                },
            },
            risk_level=RiskLevel.LOW,
            source=ActionSource.PROPOSAL,
        )

        # Approve
        approved = framework.approve_action(action_id, approved_by="molham")
        assert approved is True

        # Execute (dry_run)
        result = framework.execute_action(action_id)
        assert result.success is True
        assert result.result_data["dry_run"] is True


# =============================================================================
# EMAIL HANDLER INTEGRATION TESTS
# =============================================================================


class TestEmailHandlerIntegration:
    """Tests for email draft_email handler through the framework pipeline."""

    def test_propose_draft_email(self, framework):
        """Propose a proactive email draft action."""
        action_id = framework.propose_action(
            action_type="draft_email",
            target_entity="email",
            target_id="client_acme",
            payload={
                "action_type": "draft_email",
                "data": {
                    "entity_id": "client_acme",
                    "entity_name": "Acme Corp",
                    "to": "contact@acme.com",
                    "days_since_contact": 18,
                },
            },
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
            confidence_score=0.9,
        )
        assert action_id.startswith("action_")

    def test_approve_and_execute_email_draft_dry_run(self, framework):
        """Full lifecycle for proactive email draft."""
        action_id = framework.propose_action(
            action_type="draft_email",
            target_entity="email",
            target_id="client_acme",
            payload={
                "action_type": "draft_email",
                "data": {
                    "entity_id": "client_acme",
                    "entity_name": "Acme Corp",
                    "to": "contact@acme.com",
                    "days_since_contact": 18,
                },
            },
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
        )

        approved = framework.approve_action(action_id, approved_by="molham")
        assert approved is True

        result = framework.execute_action(action_id)
        assert result.success is True
        assert result.result_data["dry_run"] is True


# =============================================================================
# REJECTION FLOW TESTS
# =============================================================================


class TestRejectionFlow:
    """Verify rejection prevents execution."""

    def test_reject_prevents_execution(self, framework):
        action_id = framework.propose_action(
            action_type="asana_create_task",
            target_entity="task",
            target_id="project_123",
            payload={"action_type": "create_task", "data": {"name": "Test", "project_gid": "123"}},
            risk_level=RiskLevel.MEDIUM,
            source=ActionSource.MANUAL,
        )

        rejected = framework.reject_action(action_id, rejected_by="molham", reason="Not needed")
        assert rejected is True

        result = framework.execute_action(action_id)
        assert result.success is False
        assert "Cannot execute action in state" in result.error


# =============================================================================
# CROSS-HANDLER TESTS
# =============================================================================


class TestCrossHandlerFlow:
    """Tests involving multiple handler types in sequence."""

    def test_multiple_actions_different_types(self, framework):
        """Propose and execute actions across different handler types."""
        # Propose Asana task
        asana_id = framework.propose_action(
            action_type="asana_create_task",
            target_entity="task",
            target_id="project_123",
            payload={"action_type": "create_task", "data": {"name": "Test", "project_gid": "123"}},
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
        )

        # Propose email draft
        email_id = framework.propose_action(
            action_type="draft_email",
            target_entity="email",
            target_id="client_acme",
            payload={
                "action_type": "draft_email",
                "data": {"entity_id": "client_acme", "to": "a@b.com", "days_since_contact": 14},
            },
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
        )

        # Both should be pending
        pending = framework.get_pending_actions()
        assert len(pending) == 2

        # Approve and execute both
        framework.approve_action(asana_id, approved_by="molham")
        framework.approve_action(email_id, approved_by="molham")

        r1 = framework.execute_action(asana_id)
        r2 = framework.execute_action(email_id)

        assert r1.success is True
        assert r2.success is True

    def test_idempotency_prevents_duplicate(self, framework):
        """Same idempotency key should return existing action ID."""
        id1 = framework.propose_action(
            action_type="asana_create_task",
            target_entity="task",
            target_id="project_123",
            payload={"action_type": "create_task", "data": {"name": "Test", "project_gid": "123"}},
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
            idempotency_key="unique_key_1",
        )

        id2 = framework.propose_action(
            action_type="asana_create_task",
            target_entity="task",
            target_id="project_123",
            payload={"action_type": "create_task", "data": {"name": "Test", "project_gid": "123"}},
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
            idempotency_key="unique_key_1",
        )

        assert id1 == id2


# =============================================================================
# REAL SQLITE FIXTURE STORE (for muting + analytics tests)
# =============================================================================


class _FixtureStore:
    """Lightweight store adapter backed by real SQLite.

    Matches the StateStore public interface that NotificationEngine uses:
    query(), insert(), update(), count(), delete().

    Uses INSERT OR REPLACE to match StateStore.insert() semantics
    (safe_sql.insert_or_replace).  Each test gets a fresh per-test DB
    via function-scoped tmp_path.
    """

    def __init__(self, db_path: str):
        self.db_path = str(db_path)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, sql: str, params: list = None) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(sql, params or []).fetchall()
            return [dict(row) for row in rows]

    def insert(self, table: str, data: dict) -> str:
        columns = list(data.keys())
        placeholders = ", ".join("?" for _ in columns)
        col_str = ", ".join(columns)
        sql = f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})"  # noqa: S608
        with self._conn() as conn:
            conn.execute(sql, [data[c] for c in columns])
        return data.get("id", "")

    def update(self, table: str, row_id: str, data: dict) -> bool:
        if not data:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in data)
        sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"  # noqa: S608
        values = list(data.values()) + [row_id]
        with self._conn() as conn:
            result = conn.execute(sql, values)
            return result.rowcount > 0

    def count(self, table: str, where: str = None, params: list = None) -> int:
        sql = f"SELECT COUNT(*) as c FROM {table}"  # noqa: S608
        if where:
            sql += f" WHERE {where}"
        with self._conn() as conn:
            row = conn.execute(sql, params or []).fetchone()
            return row["c"] if row else 0

    def delete(self, table: str, id: str) -> bool:
        sql = f"DELETE FROM {table} WHERE id = ?"  # noqa: S608
        with self._conn() as conn:
            result = conn.execute(sql, [id])
            return result.rowcount > 0


@pytest.fixture
def fixture_store(tmp_path):
    """Create a real SQLite fixture store for muting/analytics tests.

    Uses create_fixture_db() for full production schema, then wraps
    in _FixtureStore.  Per-test isolation via function-scoped tmp_path.
    """
    from tests.fixtures.fixture_db import create_fixture_db

    db_path = tmp_path / "notif_engine_test.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return _FixtureStore(db_path)


@pytest.fixture
def notif_engine(fixture_store):
    """Create NotificationEngine with real SQLite fixture store."""
    from lib.notifier.engine import NotificationEngine

    return NotificationEngine(fixture_store)


# =============================================================================
# NOTIFICATION MUTING TESTS (real SQLite -- no mocks)
# =============================================================================


class TestNotificationMuting:
    """Tests for notification muting via NotificationEngine against real SQLite.

    Validates that mute_entity, unmute_entity, and is_muted operate correctly
    against the production schema (notification_mutes table).
    """

    def test_mute_and_check(self, notif_engine):
        """Mute an entity and verify is_muted returns True from real DB."""
        mute_id = notif_engine.mute_entity(
            entity_id="client:acme",
            mute_until="2026-12-31T23:59:59",
            reason="On vacation",
        )
        assert mute_id

        assert notif_engine.is_muted("client:acme") is True

    def test_mute_stores_entity_type(self, notif_engine, fixture_store):
        """Verify entity_type is extracted and stored correctly."""
        notif_engine.mute_entity(
            entity_id="client:acme",
            mute_until="2026-12-31T23:59:59",
            reason="Testing",
        )

        rows = fixture_store.query("SELECT entity_type, entity_id FROM notification_mutes")
        assert len(rows) == 1
        assert rows[0]["entity_type"] == "client"
        assert rows[0]["entity_id"] == "client:acme"

    def test_unmute_clears_mute(self, notif_engine):
        """Unmute should set mute_until to now, making is_muted return False."""
        notif_engine.mute_entity(
            entity_id="client:acme",
            mute_until="2026-12-31T23:59:59",
            reason="On vacation",
        )
        assert notif_engine.is_muted("client:acme") is True

        result = notif_engine.unmute_entity("client:acme")
        assert result is True

        assert notif_engine.is_muted("client:acme") is False

    def test_unmute_no_active_mute(self, notif_engine):
        """Unmuting when no active mute returns False."""
        result = notif_engine.unmute_entity("client:nonexistent")
        assert result is False

    def test_get_active_mutes(self, notif_engine):
        """get_active_mutes returns all currently active mutes from DB."""
        notif_engine.mute_entity("client:acme", "2026-12-31T23:59:59", "Vacation")
        notif_engine.mute_entity("project:alpha", "2026-12-31T23:59:59", "Paused")

        mutes = notif_engine.get_active_mutes()
        assert len(mutes) == 2
        entity_ids = {m["entity_id"] for m in mutes}
        assert "client:acme" in entity_ids
        assert "project:alpha" in entity_ids

    def test_expired_mute_not_active(self, notif_engine):
        """A mute with mute_until in the past should not show as muted."""
        notif_engine.mute_entity(
            entity_id="client:expired",
            mute_until="2020-01-01T00:00:00",
            reason="Old mute",
        )

        assert notif_engine.is_muted("client:expired") is False
        assert len(notif_engine.get_active_mutes()) == 0


# =============================================================================
# NOTIFICATION ANALYTICS TESTS (real SQLite -- no mocks)
# =============================================================================


class TestNotificationAnalytics:
    """Tests for notification delivery analytics against real SQLite.

    Validates that track_delivery and get_analytics_summary operate correctly
    against the production schema (notification_analytics table).
    """

    def test_track_delivery(self, notif_engine, fixture_store):
        """Track a delivery outcome and verify row in DB."""
        analytics_id = notif_engine.track_delivery(
            notification_id="notif_123",
            channel="google_chat",
            outcome="delivered",
        )
        assert analytics_id

        rows = fixture_store.query(
            "SELECT * FROM notification_analytics WHERE id = ?",
            [analytics_id],
        )
        assert len(rows) == 1
        assert rows[0]["channel"] == "google_chat"
        assert rows[0]["outcome"] == "delivered"
        assert rows[0]["delivered_at"] is not None

    def test_track_delivery_outcome_timestamps(self, notif_engine, fixture_store):
        """Each outcome maps to its correct timestamp column."""
        id_delivered = notif_engine.track_delivery("n1", "chat", "delivered")
        id_opened = notif_engine.track_delivery("n2", "chat", "opened")
        id_acted = notif_engine.track_delivery("n3", "chat", "acted_on")

        r1 = fixture_store.query(
            "SELECT * FROM notification_analytics WHERE id = ?", [id_delivered]
        )
        assert r1[0]["delivered_at"] is not None
        assert r1[0]["opened_at"] is None

        r2 = fixture_store.query("SELECT * FROM notification_analytics WHERE id = ?", [id_opened])
        assert r2[0]["opened_at"] is not None
        assert r2[0]["delivered_at"] is None

        r3 = fixture_store.query("SELECT * FROM notification_analytics WHERE id = ?", [id_acted])
        assert r3[0]["acted_on_at"] is not None

    def test_track_delivery_failed_with_metadata(self, notif_engine, fixture_store):
        """Failed outcome stores metadata in failed_reason column."""
        analytics_id = notif_engine.track_delivery(
            notification_id="notif_fail",
            channel="email",
            outcome="failed",
            metadata={"error": "Connection refused"},
        )

        rows = fixture_store.query(
            "SELECT * FROM notification_analytics WHERE id = ?",
            [analytics_id],
        )
        assert len(rows) == 1
        assert rows[0]["outcome"] == "failed"
        assert "Connection refused" in rows[0]["failed_reason"]

    def test_analytics_summary(self, notif_engine):
        """Analytics summary aggregates from real DB rows."""
        notif_engine.track_delivery("n1", "google_chat", "delivered")
        notif_engine.track_delivery("n2", "google_chat", "delivered")
        notif_engine.track_delivery("n3", "google_chat", "acted_on")
        notif_engine.track_delivery("n4", "email", "delivered")

        summary = notif_engine.get_analytics_summary(days=30)
        assert summary["total_sent"] == 4
        assert "google_chat" in summary["by_channel"]
        assert summary["by_channel"]["google_chat"]["delivered"] == 2
        assert summary["by_outcome"]["delivered"] == 3
        assert summary["action_rate"] > 0
