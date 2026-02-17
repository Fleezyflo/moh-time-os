"""Tests for notification delivery module."""

import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.intelligence.delivery import (
    DeliveryResult,
    deliver_pending,
    deliver_to_slack,
    format_slack_message,
    get_delivery_stats,
    get_slack_webhook_url,
)
from lib.intelligence.notifications import (
    Notification,
    NotificationPriority,
    NotificationType,
    ensure_notification_table,
    queue_notification,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Create the notification table
    ensure_notification_table(db_path)
    yield db_path

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def sample_notification():
    """Create a sample notification for testing."""
    return Notification(
        id="test-001",
        type=NotificationType.CRITICAL_SIGNAL,
        priority=NotificationPriority.HIGH,
        title="🚨 Critical: Overdue Task Count",
        body="Project X has 15 overdue tasks",
        entity_type="project",
        entity_id="proj-123",
        data={"overdue_count": 15, "threshold": 5},
        created_at=datetime.now().isoformat(),
    )


class TestSlackFormatting:
    """Test Slack message formatting."""

    def test_format_critical_signal(self, sample_notification):
        """Critical signals should be formatted with danger color."""
        message = format_slack_message(sample_notification)

        assert "attachments" in message
        assert len(message["attachments"]) == 1

        attachment = message["attachments"][0]
        assert attachment["color"] == "danger"
        assert attachment["title"] == sample_notification.title
        assert attachment["text"] == sample_notification.body

    def test_format_escalation(self):
        """Escalations should have orange color."""
        notification = Notification(
            id="esc-001",
            type=NotificationType.ESCALATION,
            priority=NotificationPriority.HIGH,
            title="⬆️ Escalated: Task overdue",
            body="Task escalated from warning to critical",
            entity_type="task",
            entity_id="task-456",
            data={},
            created_at=datetime.now().isoformat(),
        )
        message = format_slack_message(notification)
        assert message["attachments"][0]["color"] == "#FF8C00"

    def test_format_score_drop(self):
        """Score drops should have warning color."""
        notification = Notification(
            id="score-001",
            type=NotificationType.SCORE_DROP,
            priority=NotificationPriority.MEDIUM,
            title="📉 Score Drop: Client ABC",
            body="Score dropped from 85 to 65",
            entity_type="client",
            entity_id="client-789",
            data={"old_score": 85, "new_score": 65},
            created_at=datetime.now().isoformat(),
        )
        message = format_slack_message(notification)
        assert message["attachments"][0]["color"] == "warning"

    def test_format_pattern(self):
        """Patterns should have blue color."""
        notification = Notification(
            id="pat-001",
            type=NotificationType.PATTERN_DETECTED,
            priority=NotificationPriority.MEDIUM,
            title="🔺 Pattern: Revenue Concentration",
            body="Top 2 clients represent 60% of revenue",
            entity_type="portfolio",
            entity_id=None,
            data={},
            created_at=datetime.now().isoformat(),
        )
        message = format_slack_message(notification)
        assert message["attachments"][0]["color"] == "#2196F3"

    def test_format_proposal(self):
        """Proposals should have good (green) color."""
        notification = Notification(
            id="prop-001",
            type=NotificationType.PROPOSAL_GENERATED,
            priority=NotificationPriority.LOW,
            title="💡 Consider expanding team",
            body="Workload analysis suggests need for additional resources",
            entity_type="team",
            entity_id=None,
            data={},
            created_at=datetime.now().isoformat(),
        )
        message = format_slack_message(notification)
        assert message["attachments"][0]["color"] == "good"

    def test_format_includes_entity_field(self, sample_notification):
        """Message should include entity info when present."""
        message = format_slack_message(sample_notification)
        fields = message["attachments"][0]["fields"]

        entity_field = next((f for f in fields if f["title"] == "Entity"), None)
        assert entity_field is not None
        assert "project: proj-123" in entity_field["value"]


class TestDeliveryToSlack:
    """Test Slack webhook delivery."""

    def test_no_webhook_configured(self, sample_notification):
        """Should fail gracefully when webhook not configured."""
        with patch.dict(os.environ, {}, clear=True):
            success, error = deliver_to_slack(sample_notification)
            assert success is False
            assert "not configured" in error

    def test_successful_delivery(self, sample_notification):
        """Should succeed with valid webhook response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            success, error = deliver_to_slack(
                sample_notification, webhook_url="https://hooks.slack.com/test"
            )
            assert success is True
            assert error is None

    def test_http_error(self, sample_notification):
        """Should handle HTTP errors."""
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("https://test", 403, "Forbidden", {}, None),
        ):
            success, error = deliver_to_slack(
                sample_notification, webhook_url="https://hooks.slack.com/test"
            )
            assert success is False
            assert "403" in error


class TestDeliverPending:
    """Test batch delivery of pending notifications."""

    def test_no_webhook_skips_all(self, temp_db, sample_notification):
        """Without webhook, all notifications should be skipped."""
        queue_notification(sample_notification, db_path=temp_db)

        with patch.dict(os.environ, {}, clear=True):
            result = deliver_pending(limit=10, db_path=temp_db)

            assert result.skipped == 10
            assert result.delivered == 0
            assert "not configured" in result.errors[0]

    def test_delivers_pending_notifications(self, temp_db, sample_notification):
        """Should deliver and mark notifications."""
        queue_notification(sample_notification, db_path=temp_db)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = deliver_pending(
                limit=10,
                webhook_url="https://hooks.slack.com/test",
                db_path=temp_db,
            )

            assert result.total == 1
            assert result.delivered == 1
            assert result.failed == 0

        # Check notification is marked delivered
        conn = sqlite3.connect(str(temp_db))
        row = conn.execute(
            "SELECT delivered_at FROM notification_queue WHERE notification_id = ?",
            (sample_notification.id,),
        ).fetchone()
        conn.close()
        assert row[0] is not None

    def test_handles_partial_failure(self, temp_db):
        """Should continue delivering after failures."""
        # Queue two notifications
        notif1 = Notification(
            id="n1",
            type=NotificationType.CRITICAL_SIGNAL,
            priority=NotificationPriority.HIGH,
            title="First",
            body="First notification",
            entity_type=None,
            entity_id=None,
            data={},
            created_at=datetime.now().isoformat(),
        )
        notif2 = Notification(
            id="n2",
            type=NotificationType.CRITICAL_SIGNAL,
            priority=NotificationPriority.HIGH,
            title="Second",
            body="Second notification",
            entity_type=None,
            entity_id=None,
            data={},
            created_at=datetime.now().isoformat(),
        )
        queue_notification(notif1, db_path=temp_db)
        queue_notification(notif2, db_path=temp_db)

        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                import urllib.error

                raise urllib.error.HTTPError("https://test", 500, "Server Error", {}, None)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=side_effect):
            result = deliver_pending(
                limit=10,
                webhook_url="https://hooks.slack.com/test",
                db_path=temp_db,
            )

            assert result.total == 2
            assert result.delivered == 1
            assert result.failed == 1


class TestDeliveryStats:
    """Test delivery statistics."""

    def test_empty_stats(self, temp_db):
        """Stats should work with empty queue."""
        stats = get_delivery_stats(db_path=temp_db)

        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["delivered"] == 0

    def test_pending_count(self, temp_db, sample_notification):
        """Should count pending notifications."""
        queue_notification(sample_notification, db_path=temp_db)

        stats = get_delivery_stats(db_path=temp_db)
        assert stats["pending"] == 1
        assert stats["by_priority"].get("high") == 1
        assert stats["by_type"].get("critical_signal") == 1

    def test_webhook_configured_status(self, temp_db):
        """Should indicate webhook configuration status."""
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://test"}):
            stats = get_delivery_stats(db_path=temp_db)
            assert stats["webhook_configured"] is True

        with patch.dict(os.environ, {}, clear=True):
            stats = get_delivery_stats(db_path=temp_db)
            assert stats["webhook_configured"] is False


class TestDeliveryResult:
    """Test DeliveryResult dataclass."""

    def test_to_dict(self):
        """Should serialize correctly."""
        result = DeliveryResult(
            total=10,
            delivered=8,
            failed=2,
            skipped=0,
            errors=["error1", "error2"],
        )
        d = result.to_dict()

        assert d["total"] == 10
        assert d["delivered"] == 8
        assert d["failed"] == 2
        assert d["success_rate"] == 80.0
        assert len(d["errors"]) == 2

    def test_success_rate_empty(self):
        """Success rate should be 0 when no notifications."""
        result = DeliveryResult()
        assert result.to_dict()["success_rate"] == 0
