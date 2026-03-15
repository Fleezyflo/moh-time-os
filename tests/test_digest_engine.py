"""Tests for digest engine.

Uses a real SQLite fixture DB -- no monkeypatching, no mocking.
DigestEngine receives a lightweight store adapter that speaks the
same query()/insert()/update() interface as StateStore.

Each test gets a fresh database (function-scoped tmp_path) so tests
cannot contaminate each other.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from lib.notifier.digest import DigestEngine


class _FixtureStore:
    """Minimal store matching the StateStore public interface that
    DigestEngine uses: query(), insert(), update().

    Backed by a real SQLite file so DigestEngine operates against an
    actual database.  Uses INSERT OR REPLACE to match StateStore.insert()
    semantics (safe_sql.insert_or_replace).
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    """Create a fixture store backed by a fresh per-test database.

    Uses create_fixture_db() to get the full schema (tables + indexes)
    matching production, then wraps it in _FixtureStore.
    """
    from tests.fixtures.fixture_db import create_fixture_db

    db_path = tmp_path / "digest_test.db"
    conn = create_fixture_db(db_path)
    conn.close()
    return _FixtureStore(db_path)


@pytest.fixture
def digest_engine(store):
    """Create digest engine with fixture store."""
    return DigestEngine(store)


@pytest.fixture
def setup_notifications(store):
    """Create test notifications and clear digest tables."""
    import uuid

    # Clear any previous test data
    store.query("DELETE FROM digest_queue")
    store.query("DELETE FROM digest_history")
    store.query("DELETE FROM notifications")

    # Add test notifications with unique IDs
    now = datetime.now(timezone.utc).isoformat()
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    id3 = str(uuid.uuid4())

    notif_sql = """
        INSERT OR IGNORE INTO notifications
            (id, type, priority, title, body, action_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    store.query(notif_sql, [id1, "proposal", "high", "New Proposal", "Test proposal", None, now])
    store.query(notif_sql, [id2, "issue", "high", "Bug Report", "Test issue", None, now])
    store.query(notif_sql, [id3, "watcher", "normal", "Pattern Alert", "Test pattern", None, now])


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

    def test_generate_digest_empty(self, digest_engine):
        """Test generating digest with no queued items."""
        digest = digest_engine.generate_digest("user_empty", "daily")
        assert digest is None

    def test_generate_digest_with_items(self, digest_engine):
        """Test generating digest with queued items."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif2", "issue", "medium", "daily")

        digest = digest_engine.generate_digest("user1", "daily")
        assert digest is not None
        assert digest["total"] == 2
        assert "proposals" in digest["categories"]

    def test_digest_groups_by_category(self, digest_engine):
        """Test digest groups items by category."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif2", "issue", "medium", "daily")
        digest_engine.queue_notification("user1", "notif3", "watcher", "low", "daily")

        digest = digest_engine.generate_digest("user1", "daily")
        assert "proposals" in digest["categories"]
        assert "issues" in digest["categories"]
        assert "watchers" in digest["categories"]

    def test_mark_as_processed(self, digest_engine, store):
        """Test marking items as processed via store.update()."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")

        success = digest_engine.mark_as_processed("user1", ["notif1"], "daily")
        assert success

        # Verify: generate_digest should return None (all processed)
        digest = digest_engine.generate_digest("user1", "daily")
        assert digest is None

        # Verify: the row has processed=1 and processed_at set
        rows = store.query(
            "SELECT processed, processed_at FROM digest_queue "
            "WHERE user_id = ? AND notification_id = ?",
            ["user1", "notif1"],
        )
        assert len(rows) > 0
        assert rows[0]["processed"] == 1
        assert rows[0]["processed_at"] is not None

    def test_record_digest_sent(self, digest_engine, store):
        """Test recording digest delivery."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest = digest_engine.generate_digest("user1", "daily")

        success = digest_engine.record_digest_sent(
            user_id="user1",
            bucket="daily",
            digest=digest,
            sent_time=datetime.now(timezone.utc).isoformat(),
        )
        assert success

        # Verify: row exists in digest_history
        history = store.query(
            "SELECT * FROM digest_history WHERE user_id = ? AND bucket = ?",
            ["user1", "daily"],
        )
        assert len(history) == 1
        assert history[0]["item_count"] == 1

    def test_get_pending_count(self, digest_engine):
        """Test getting pending notification counts."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest_engine.queue_notification("user1", "notif2", "issue", "medium", "hourly")

        counts = digest_engine.get_pending_count("user1")
        assert counts.get("daily", 0) == 1
        assert counts.get("hourly", 0) == 1

    def test_format_plaintext(self, digest_engine):
        """Test plaintext digest formatting."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest = digest_engine.generate_digest("user1", "daily")

        plaintext = digest_engine.format_plaintext(digest)
        assert "DAILY" in plaintext
        assert isinstance(plaintext, str)

    def test_format_plaintext_empty(self, digest_engine):
        """Test plaintext formatting with empty digest."""
        plaintext = digest_engine.format_plaintext(None)
        assert plaintext == "No notifications"

    def test_format_html(self, digest_engine):
        """Test HTML digest formatting."""
        digest_engine.queue_notification("user1", "notif1", "proposal", "high", "daily")
        digest = digest_engine.generate_digest("user1", "daily")

        html = digest_engine.format_html(digest)
        assert "<html>" in html
        assert isinstance(html, str)

    def test_format_html_empty(self, digest_engine):
        """Test HTML formatting with empty digest."""
        html = digest_engine.format_html(None)
        assert "<html>" in html
        assert "No notifications" in html

    def test_digest_summary_counts(self, digest_engine):
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

    def test_digest_ordering_by_severity(self, digest_engine):
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
    def test_full_digest_workflow(self, digest_engine, store):
        """Test complete digest workflow end-to-end against real DB."""
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
        digest_engine.record_digest_sent(
            "user1", "daily", digest, datetime.now(timezone.utc).isoformat()
        )

        # Verify history recorded
        history = store.query("SELECT * FROM digest_history WHERE user_id = 'user1'")
        assert len(history) == 1

        # Mark as processed
        digest_engine.mark_as_processed("user1", ["notif1", "notif2"], "daily")

        # Verify no pending items
        digest2 = digest_engine.generate_digest("user1", "daily")
        assert digest2 is None

        # Verify processed state in DB
        processed = store.query(
            "SELECT COUNT(*) as cnt FROM digest_queue WHERE user_id = 'user1' AND processed = 1"
        )
        assert processed[0]["cnt"] == 2
