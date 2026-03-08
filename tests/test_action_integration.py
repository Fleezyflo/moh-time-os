"""
End-to-end action integration tests.

GAP-10-09: Tests the full propose -> approve -> execute -> verify chain
across Asana and email handlers in dry_run mode.
"""

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
    """Provide a mock state store matching test_action_framework pattern."""
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
# NOTIFICATION MUTING TESTS
# =============================================================================


class TestNotificationMuting:
    """Tests for notification muting via NotificationEngine."""

    def test_mute_and_check(self, mock_store):
        """Mute an entity and verify is_muted returns True."""
        from lib.notifier.engine import NotificationEngine

        engine = NotificationEngine(mock_store)

        # Mock the query and count methods for muting
        mock_store.count = Mock(return_value=1)
        mock_store.query = Mock(return_value=[])

        mute_id = engine.mute_entity(
            entity_id="client:acme",
            mute_until="2026-12-31T23:59:59",
            reason="On vacation",
        )
        assert mute_id  # Should return a UUID string

        # Check muted
        assert engine.is_muted("client:acme") is True

    def test_unmute_clears_mute(self, mock_store):
        """Unmute should clear active mute."""
        from lib.notifier.engine import NotificationEngine

        engine = NotificationEngine(mock_store)

        # Simulate existing mute
        mock_store.query = Mock(return_value=[{"id": "mute_123"}])
        result = engine.unmute_entity("client:acme")
        assert result is True

    def test_unmute_no_active_mute(self, mock_store):
        """Unmuting when no active mute returns False."""
        from lib.notifier.engine import NotificationEngine

        engine = NotificationEngine(mock_store)
        mock_store.query = Mock(return_value=[])
        result = engine.unmute_entity("client:nonexistent")
        assert result is False


# =============================================================================
# NOTIFICATION ANALYTICS TESTS
# =============================================================================


class TestNotificationAnalytics:
    """Tests for notification delivery analytics."""

    def test_track_delivery(self, mock_store):
        """Track a delivery outcome."""
        from lib.notifier.engine import NotificationEngine

        engine = NotificationEngine(mock_store)

        analytics_id = engine.track_delivery(
            notification_id="notif_123",
            channel="google_chat",
            outcome="delivered",
        )
        assert analytics_id  # Should return UUID

    def test_analytics_summary(self, mock_store):
        """Analytics summary with mock data."""
        from lib.notifier.engine import NotificationEngine

        engine = NotificationEngine(mock_store)

        mock_store.query = Mock(
            return_value=[
                {"channel": "google_chat", "outcome": "delivered", "cnt": 10},
                {"channel": "google_chat", "outcome": "acted_on", "cnt": 3},
                {"channel": "email", "outcome": "delivered", "cnt": 5},
            ]
        )

        summary = engine.get_analytics_summary(days=30)
        assert summary["total_sent"] == 18
        assert "google_chat" in summary["by_channel"]
        assert summary["by_outcome"]["delivered"] == 15  # 10 + 5
        assert summary["action_rate"] > 0
