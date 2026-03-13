"""Tests for action handler schema-column fixes (A-I1, A-I2, A-I3, A-U1, A-S1).

Each test uses real SQLite with production schema via create_fixture_db().
Every assertion would fail if the code still referenced phantom columns.
"""

import json
import sqlite3
from contextlib import contextmanager

import pytest

from tests.fixtures.fixture_db import create_fixture_db

# =============================================================================
# FIXTURE STORE — real SQLite, per-test isolation
# =============================================================================


class _FixtureStore:
    """Lightweight store backed by real SQLite.

    Matches StateStore public interface: query, insert, update, get, delete.
    Uses INSERT OR REPLACE to match production safe_sql semantics.
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

    def get(self, table: str, row_id: str) -> dict | None:
        sql = f"SELECT * FROM {table} WHERE id = ?"  # noqa: S608
        with self._conn() as conn:
            row = conn.execute(sql, [row_id]).fetchone()
            return dict(row) if row else None

    def update(self, table: str, row_id: str, data: dict) -> bool:
        if not data:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in data)
        sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"  # noqa: S608
        values = list(data.values()) + [row_id]
        with self._conn() as conn:
            result = conn.execute(sql, values)
            return result.rowcount > 0

    def delete(self, table: str, id: str) -> bool:
        sql = f"DELETE FROM {table} WHERE id = ?"  # noqa: S608
        with self._conn() as conn:
            result = conn.execute(sql, [id])
            return result.rowcount > 0

    def count(self, table: str, where: str = None, params: list = None) -> int:
        sql = f"SELECT COUNT(*) as c FROM {table}"  # noqa: S608
        if where:
            sql += f" WHERE {where}"
        with self._conn() as conn:
            row = conn.execute(sql, params or []).fetchone()
            return row["c"] if row else 0


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def fixture_store(tmp_path):
    """Real SQLite fixture store with production schema."""
    db_path = tmp_path / "action_schema_test.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return _FixtureStore(db_path)


# =============================================================================
# A-I1: NotificationHandler._log_action() column fix
# =============================================================================


class TestNotificationLogAction:
    """Verify NotificationHandler._log_action() writes to actions table
    using only schema-valid columns.

    Bug fix A-I1: domain → (dropped), action_type → type,
    target_id → target_system, data → payload.
    """

    def test_log_action_inserts_with_valid_columns(self, fixture_store):
        """_log_action() must insert into actions without sqlite3.OperationalError."""
        from lib.executor.handlers.notification import NotificationHandler

        handler = NotificationHandler(store=fixture_store)
        action = {"action_type": "create", "data": {"title": "Test notif"}}
        result = {"success": True, "notification_id": "notif_001"}

        # This would raise sqlite3.OperationalError if phantom columns remain
        handler._log_action(action, result)

        rows = fixture_store.query("SELECT * FROM actions")
        assert len(rows) == 1
        row = rows[0]
        assert row["type"] == "create"
        assert row["target_system"] == "notifications"
        assert json.loads(row["payload"]) == {"title": "Test notif"}
        assert row["status"] == "completed"

    def test_log_action_failed_status(self, fixture_store):
        """Failed actions logged with status='failed'."""
        from lib.executor.handlers.notification import NotificationHandler

        handler = NotificationHandler(store=fixture_store)
        action = {"action_type": "send_immediate", "data": {}}
        result = {"success": False, "error": "notifier unavailable"}

        handler._log_action(action, result)

        rows = fixture_store.query("SELECT * FROM actions WHERE status = 'failed'")
        assert len(rows) == 1
        assert rows[0]["type"] == "send_immediate"

    def test_log_action_type_not_null(self, fixture_store):
        """type column is NOT NULL — action_type defaults to 'notification'."""
        from lib.executor.handlers.notification import NotificationHandler

        handler = NotificationHandler(store=fixture_store)
        action = {"data": {"title": "no type"}}  # Missing action_type
        result = {"success": True}

        handler._log_action(action, result)

        rows = fixture_store.query("SELECT type FROM actions")
        assert len(rows) == 1
        assert rows[0]["type"] == "notification"  # Default fallback


# =============================================================================
# A-I2: DelegationHandler._log_action() column fix
# =============================================================================


class TestDelegationLogAction:
    """Verify DelegationHandler._log_action() writes to actions table
    using only schema-valid columns.

    Bug fix A-I2: identical clone of A-I1.
    """

    def test_log_action_inserts_with_valid_columns(self, fixture_store):
        """_log_action() must insert without OperationalError."""
        from lib.executor.handlers.delegation import DelegationHandler

        handler = DelegationHandler(store=fixture_store)
        action = {
            "action_type": "delegate",
            "task_id": "task_123",
            "data": {"delegate_to": "alice@example.com"},
        }
        result = {"success": True, "task_id": "task_123", "delegated_to": "alice@example.com"}

        handler._log_action(action, result)

        rows = fixture_store.query("SELECT * FROM actions")
        assert len(rows) == 1
        row = rows[0]
        assert row["type"] == "delegate"
        assert row["target_system"] == "delegation"
        payload = json.loads(row["payload"])
        assert payload["delegate_to"] == "alice@example.com"

    def test_log_action_escalation(self, fixture_store):
        """Escalation actions use correct type value."""
        from lib.executor.handlers.delegation import DelegationHandler

        handler = DelegationHandler(store=fixture_store)
        action = {"action_type": "escalate", "task_id": "task_456", "data": {"reason": "blocked"}}
        result = {"success": True}

        handler._log_action(action, result)

        rows = fixture_store.query("SELECT type FROM actions")
        assert rows[0]["type"] == "escalate"


# =============================================================================
# A-I3: ActionFramework._store_proposal() column fix
# =============================================================================


class TestStoreProposal:
    """Verify ActionFramework._store_proposal() writes to actions table
    using only schema-valid columns.

    Bug fix A-I3: target_entity → target_system, target_id/risk_level/
    source/confidence_score → encoded in payload._meta JSON.
    """

    def test_store_proposal_inserts_with_valid_columns(self, fixture_store):
        """_store_proposal() must insert without OperationalError."""
        from lib.actions.action_framework import (
            ActionFramework,
            ActionProposal,
            ActionSource,
            RiskLevel,
        )

        fw = ActionFramework(store=fixture_store, dry_run=True)
        proposal = ActionProposal(
            id="action_test_001",
            type="task_create",
            target_entity="task",
            target_id="project_123",
            payload={"name": "Follow up", "notes": "Detected gap"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
            confidence_score=0.85,
            requires_approval=True,
        )

        fw._store_proposal(proposal)

        rows = fixture_store.query("SELECT * FROM actions WHERE id = 'action_test_001'")
        assert len(rows) == 1
        row = rows[0]
        assert row["type"] == "task_create"
        assert row["target_system"] == "task"
        assert row["requires_approval"] == 1
        assert row["status"] == "proposed"

        # Verify metadata encoded in payload
        payload = json.loads(row["payload"])
        assert payload["name"] == "Follow up"
        assert payload["_meta"]["target_id"] == "project_123"
        assert payload["_meta"]["risk_level"] == "low"
        assert payload["_meta"]["source"] == "signal"
        assert payload["_meta"]["confidence_score"] == 0.85

    def test_store_proposal_preserves_payload_data(self, fixture_store):
        """Original payload keys survive alongside _meta."""
        from lib.actions.action_framework import (
            ActionFramework,
            ActionProposal,
            ActionSource,
            RiskLevel,
        )

        fw = ActionFramework(store=fixture_store, dry_run=True)
        proposal = ActionProposal(
            id="action_test_002",
            type="email_send",
            target_entity="email",
            target_id="thread_abc",
            payload={"to": "bob@example.com", "subject": "Update"},
            risk_level=RiskLevel.MEDIUM,
            source=ActionSource.MANUAL,
            confidence_score=0.9,
            requires_approval=False,
        )

        fw._store_proposal(proposal)

        row = fixture_store.get("actions", "action_test_002")
        payload = json.loads(row["payload"])
        assert payload["to"] == "bob@example.com"
        assert payload["subject"] == "Update"
        assert "_meta" in payload


# =============================================================================
# A-U1: ActionFramework.reject_action() column fix
# =============================================================================


class TestRejectAction:
    """Verify reject_action() uses schema-valid columns.

    Bug fix A-U1: rejected_by and rejection_reason do not exist.
    Rejection info encoded into error (TEXT) and result (TEXT).
    """

    def test_reject_stores_in_error_and_result(self, fixture_store):
        """Rejection info written to error and result columns."""
        from lib.actions.action_framework import (
            ActionFramework,
            ActionProposal,
            ActionSource,
            ActionStatus,
            RiskLevel,
        )

        fw = ActionFramework(store=fixture_store, dry_run=True)

        # First store a proposal
        proposal = ActionProposal(
            id="action_reject_001",
            type="task_create",
            target_entity="task",
            target_id="proj_1",
            payload={"name": "Risky action"},
            risk_level=RiskLevel.HIGH,
            source=ActionSource.SIGNAL,
            confidence_score=0.6,
            requires_approval=True,
        )
        fw._store_proposal(proposal)

        # Now reject it
        result = fw.reject_action("action_reject_001", "moh", "Too risky for now")

        assert result is True

        row = fixture_store.get("actions", "action_reject_001")
        assert row["status"] == ActionStatus.REJECTED.value
        assert row["error"] == "Too risky for now"
        rejection = json.loads(row["result"])
        assert rejection["rejected_by"] == "moh"
        assert rejection["reason"] == "Too risky for now"

    def test_reject_nonexistent_returns_false(self, fixture_store):
        """Rejecting nonexistent action returns False."""
        from lib.actions.action_framework import ActionFramework

        fw = ActionFramework(store=fixture_store, dry_run=True)
        result = fw.reject_action("nonexistent_id", "moh", "n/a")
        assert result is False


# =============================================================================
# A-S1: ActionFramework.get_action_history() column fix
# =============================================================================


class TestGetActionHistory:
    """Verify get_action_history() uses schema-valid columns.

    Bug fix A-S1: target_id does not exist. Filter uses target_system instead.
    """

    def test_history_filters_by_target_system(self, fixture_store):
        """entity_id filter maps to target_system column."""
        # Insert two actions with different target_system values
        fixture_store.insert(
            "actions",
            {
                "id": "hist_001",
                "type": "task_create",
                "target_system": "task",
                "payload": "{}",
                "status": "success",
                "created_at": "2026-01-01T00:00:00",
            },
        )
        fixture_store.insert(
            "actions",
            {
                "id": "hist_002",
                "type": "email_send",
                "target_system": "email",
                "payload": "{}",
                "status": "success",
                "created_at": "2026-01-01T01:00:00",
            },
        )

        from lib.actions.action_framework import ActionFramework

        fw = ActionFramework(store=fixture_store, dry_run=True)

        # Filter by target_system = "task"
        results = fw.get_action_history(entity_id="task")
        assert len(results) == 1
        assert results[0]["id"] == "hist_001"

        # Filter by target_system = "email"
        results = fw.get_action_history(entity_id="email")
        assert len(results) == 1
        assert results[0]["id"] == "hist_002"

    def test_history_no_filter_returns_all(self, fixture_store):
        """No entity_id filter returns all terminal-status actions."""
        fixture_store.insert(
            "actions",
            {
                "id": "hist_003",
                "type": "x",
                "target_system": "t",
                "payload": "{}",
                "status": "success",
                "created_at": "2026-01-01T00:00:00",
            },
        )
        fixture_store.insert(
            "actions",
            {
                "id": "hist_004",
                "type": "y",
                "target_system": "t",
                "payload": "{}",
                "status": "failed",
                "created_at": "2026-01-01T01:00:00",
            },
        )

        from lib.actions.action_framework import ActionFramework

        fw = ActionFramework(store=fixture_store, dry_run=True)
        results = fw.get_action_history()
        assert len(results) == 2

    def test_history_type_filter(self, fixture_store):
        """action_type filter works on type column."""
        fixture_store.insert(
            "actions",
            {
                "id": "hist_005",
                "type": "task_create",
                "target_system": "task",
                "payload": "{}",
                "status": "rejected",
                "created_at": "2026-01-01T00:00:00",
            },
        )
        fixture_store.insert(
            "actions",
            {
                "id": "hist_006",
                "type": "email_send",
                "target_system": "email",
                "payload": "{}",
                "status": "success",
                "created_at": "2026-01-01T01:00:00",
            },
        )

        from lib.actions.action_framework import ActionFramework

        fw = ActionFramework(store=fixture_store, dry_run=True)
        results = fw.get_action_history(action_type="task_create")
        assert len(results) == 1
        assert results[0]["type"] == "task_create"
