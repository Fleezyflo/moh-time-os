"""Tests for digest engine (Phase 2)."""

from datetime import datetime

import pytest

from lib.notifier.digest import DigestEngine
from lib.store import DB_PATH, get_connection


@pytest.fixture(autouse=True)
def patch_db(monkeypatch, fixture_db_path):
    """Patch database path for all tests."""
    monkeypatch.setattr("lib.store.DB_PATH", fixture_db_path)


@pytest.fixture
def digest_engine():
    """Create digest engine."""
    return DigestEngine()


@pytest.fixture
def setup_notifications():
    """Create test notifications table."""
    import uuid

    with get_connection() as conn:
        # Clear any previous test data
        conn.execute("DELETE FROM digest_queue")
        conn.execute("DELETE FROM digest_history")
        try:
            conn.execute("DELETE FROM notifications")
        except:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                type TEXT,
                priority TEXT,
                severity TEXT,
                title TEXT,
                body TEXT,
                action_url TEXT,
                action_data TEXT,
                channels TEXT,
                created_at TEXT,
                sent_at TEXT
            )
        """)

        # Add test notifications with unique IDs
        now = datetime.now().isoformat()
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        id3 = str(uuid.uuid4())

        conn.execute(
            """
            INSERT OR IGNORE INTO notifications VALUES
            (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)
        """,
            (id1, "proposal", "high", "high", "New Proposal", "Test proposal", None, now),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO notifications VALUES
            (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)
        """,
            (id2, "issue", "high", "medium", "Bug Report", "Test issue", None, now),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO notifications VALUES
            (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)
        """,
            (id3, "watcher", "normal", "low", "Pattern Alert", "Test pattern", None, now),
        )


class TestDigestEngine:
    def test_queue_notification(self, digest_engine):
        """Test queuing a notification."""
        success = digest_engine.queue_notification(
            user_id="user1",
            notification_id="notif1",
            event_type="proposal",
            severity="high",
            bucket="daily",
        )
        assert success

    def test_queue_multiple_notifications(self, digest_engine):
        """Test queuing multiple notifications."""
        for i in range(5):
            success = digest_engine.queue_notification(
                user_id="user1",
                notification_id=f"notif_{i}",
                event_type="proposal",
                severity="high" if i % 2 == 0 else "low",
                bucket="daily",
            )
            assert success

    def test_categorize_event(self, digest_engine):
        """Test event categorization."""
        assert digest_engine._categorize_event("proposal") == "proposals"
        assert digest_engine._categorize_event("proposal_update") == "proposals"
        assert digest_engine._categorize_event("issue") == "issues"
        assert digest_engine._categorize_event("watcher") == "watchers"
        assert digest_engine._categorize_event("pattern") == "patterns"

    def test_generate_digest_empty(self, digest_engine, setup_notifications):
        """Test generating digest with no queued items."""
        digest = digest_engine.generate_digest("user_empty", "daily")
        assert digest is None

    def test_generate_digest_with_items(self, digest_engine, setup_notifications):
        """Test generating digest with queued items."""
        # Queue some items
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif2", "issue", "medium", "daily")

        digest = digest_engine.generate_digest("user1", "daily")
        assert digest is not None
        assert digest["total"] == 2
        assert "proposals" in digest["categories"]

    def test_digest_groups_by_category(self, digest_engine, setup_notifications):
        """Test digest groups items by category."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif2", "issue", "medium", "daily")
        digest_engine.queue_notification("user1", "notif3", "watcher", "low", "daily")

        digest = digest_engine.generate_digest("user1", "daily")
        assert "proposals" in digest["categories"]
        assert "issues" in digest["categories"]
        assert "watchers" in digest["categories"]

    def test_mark_as_processed(self, digest_engine, setup_notifications):
        """Test marking items as processed."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")

        success = digest_engine.mark_as_processed("user1", ["notif1"], "daily")
        assert success

        digest = digest_engine.generate_digest("user1", "daily")
        assert digest is None

    def test_record_digest_sent(self, digest_engine, setup_notifications):
        """Test recording digest delivery."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest = digest_engine.generate_digest("user1", "daily")

        success = digest_engine.record_digest_sent(
            user_id="user1",
            bucket="daily",
            digest=digest,
            sent_time=datetime.now().isoformat(),
        )
        assert success

    def test_get_pending_count(self, digest_engine, setup_notifications):
        """Test getting pending notification counts."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif2", "issue", "medium", "hourly")

        counts = digest_engine.get_pending_count("user1")
        assert counts.get("daily", 0) > 0
        assert counts.get("hourly", 0) > 0

    def test_format_plaintext(self, digest_engine, setup_notifications):
        """Test plaintext digest formatting."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest = digest_engine.generate_digest("user1", "daily")

        plaintext = digest_engine.format_plaintext(digest)
        assert "DAILY" in plaintext or "daily" in plaintext
        assert isinstance(plaintext, str)

    def test_format_plaintext_empty(self, digest_engine):
        """Test plaintext formatting with empty digest."""
        plaintext = digest_engine.format_plaintext(None)
        assert isinstance(plaintext, str)

    def test_format_html(self, digest_engine, setup_notifications):
        """Test HTML digest formatting."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest = digest_engine.generate_digest("user1", "daily")

        html = digest_engine.format_html(digest)
        assert "<html>" in html or "<HTML>" in html
        assert isinstance(html, str)

    def test_format_html_empty(self, digest_engine):
        """Test HTML formatting with empty digest."""
        html = digest_engine.format_html(None)
        assert isinstance(html, str)

    def test_digest_summary_counts(self, digest_engine, setup_notifications):
        """Test digest summary includes proper counts."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "critical", "daily")
        digest_engine.queue_notification("user1", "notif2", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif3", "issue", "medium", "daily")

        digest = digest_engine.generate_digest("user1", "daily")
        assert digest["summary"]["proposals"]["count"] == 2
        assert digest["summary"]["issues"]["count"] == 1

    @pytest.mark.parametrize("bucket", ["hourly", "daily", "weekly"])
    def test_queue_different_buckets(self, digest_engine, bucket):
        """Test queuing to different buckets."""
        success = digest_engine.queue_notification(
            user_id=f"user_{bucket}",
            notification_id=f"notif_{bucket}",
            event_type="test",
            severity="medium",
            bucket=bucket,
        )
        assert success

    def test_digest_ordering_by_severity(self, digest_engine, setup_notifications):
        """Test items ordered by severity in digest."""
        # Queue in opposite severity order
        digest_engine.queue_notification("user1", "notif3", "proposal", "low", "daily")
        digest_engine.queue_notification("user1", "notif1", "proposal", "critical", "daily")
        digest_engine.queue_notification("user1", "notif2", "proposal", "high", "daily")

        digest = digest_engine.generate_digest("user1", "daily")
        items = digest["categories"]["proposals"]
        # Items should be ordered by severity (critical first)
        assert items[0]["severity"] in ["critical", "high"]


class TestDigestIntegration:
    def test_full_digest_workflow(self, digest_engine, setup_notifications):
        """Test complete digest workflow."""
        # Queue items
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif2", "issue", "medium", "daily")

        # Generate digest
        digest = digest_engine.generate_digest("user1", "daily")
        assert digest is not None
        assert digest["total"] == 2

        # Format for delivery
        plaintext = digest_engine.format_plaintext(digest)
        html = digest_engine.format_html(digest)
        assert plaintext
        assert html

        # Record delivery
        digest_engine.record_digest_sent("user1", "daily", digest, datetime.now().isoformat())

        # Mark as processed
        digest_engine.mark_as_processed("user1", ["notif1", "notif2"], "daily")

        # Verify no pending items
        digest2 = digest_engine.generate_digest("user1", "daily")
        assert digest2 is None
