"""Tests for schema V19 evolution (PR1a).

Verifies converge() creates all new tables and columns added in V19:
- notifications: dismissed, dismissed_at, task_id, recipient_id (N-I1..4)
- insights: severity (I-I1)
- saved_filters table (SF-1)
- couplings table (CP-1)

Uses real SQLite via create_fixture_db() — no mocks.
"""

import sqlite3

import pytest

from lib import schema_engine
from lib.schema import SCHEMA_VERSION, TABLES


@pytest.fixture
def fresh_db(tmp_path):
    """Create a fresh DB with full production schema."""
    db_path = tmp_path / "v19_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    schema_engine.create_fresh(conn)
    return conn


def _get_columns(conn, table_name):
    """Get column names for a table."""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _table_exists(conn, table_name):
    """Check if a table exists."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        [table_name],
    ).fetchone()
    return row is not None


class TestSchemaVersion:
    """Verify schema version was bumped."""

    def test_version_is_19(self):
        """SCHEMA_VERSION must be 19 after PR1a."""
        assert SCHEMA_VERSION == 19


class TestNotificationColumns:
    """Verify notifications table has new V19 columns (N-I1..4)."""

    def test_dismissed_column_exists(self, fresh_db):
        """dismissed (INTEGER DEFAULT 0) added for N-I1."""
        cols = _get_columns(fresh_db, "notifications")
        assert "dismissed" in cols

    def test_dismissed_at_column_exists(self, fresh_db):
        """dismissed_at (TEXT) added for N-I2."""
        cols = _get_columns(fresh_db, "notifications")
        assert "dismissed_at" in cols

    def test_task_id_column_exists(self, fresh_db):
        """task_id (TEXT) added for N-I3."""
        cols = _get_columns(fresh_db, "notifications")
        assert "task_id" in cols

    def test_recipient_id_column_exists(self, fresh_db):
        """recipient_id (TEXT) added for N-I4."""
        cols = _get_columns(fresh_db, "notifications")
        assert "recipient_id" in cols

    def test_dismissed_defaults_to_zero(self, fresh_db):
        """dismissed column defaults to 0 (not dismissed)."""
        fresh_db.execute(
            "INSERT INTO notifications (id, type, priority, title, created_at) "
            "VALUES ('n1', 'alert', 'normal', 'Test', datetime('now'))"
        )
        row = fresh_db.execute("SELECT dismissed FROM notifications WHERE id = 'n1'").fetchone()
        assert row["dismissed"] == 0

    def test_insert_with_new_columns(self, fresh_db):
        """Full insert using all V19 notification columns succeeds."""
        fresh_db.execute(
            "INSERT INTO notifications "
            "(id, type, priority, title, dismissed, dismissed_at, task_id, recipient_id, created_at) "
            "VALUES ('n2', 'alert', 'high', 'Urgent', 1, '2026-01-01T00:00:00', 'task_123', 'user_456', datetime('now'))"
        )
        row = fresh_db.execute("SELECT * FROM notifications WHERE id = 'n2'").fetchone()
        assert row["dismissed"] == 1
        assert row["dismissed_at"] == "2026-01-01T00:00:00"
        assert row["task_id"] == "task_123"
        assert row["recipient_id"] == "user_456"


class TestInsightsSeverity:
    """Verify insights table has severity column (I-I1)."""

    def test_severity_column_exists(self, fresh_db):
        """severity (TEXT DEFAULT 'medium') added for I-I1."""
        cols = _get_columns(fresh_db, "insights")
        assert "severity" in cols

    def test_severity_defaults_to_medium(self, fresh_db):
        """severity defaults to 'medium'."""
        fresh_db.execute(
            "INSERT INTO insights (id, type, domain, title, created_at) "
            "VALUES ('i1', 'anomaly', 'ops', 'Test insight', datetime('now'))"
        )
        row = fresh_db.execute("SELECT severity FROM insights WHERE id = 'i1'").fetchone()
        assert row["severity"] == "medium"

    def test_severity_custom_value(self, fresh_db):
        """Explicit severity values persist."""
        fresh_db.execute(
            "INSERT INTO insights (id, type, domain, title, severity, created_at) "
            "VALUES ('i2', 'anomaly', 'finance', 'Critical finding', 'critical', datetime('now'))"
        )
        row = fresh_db.execute("SELECT severity FROM insights WHERE id = 'i2'").fetchone()
        assert row["severity"] == "critical"


class TestSavedFiltersTable:
    """Verify saved_filters table exists and works (SF-1)."""

    def test_table_exists(self, fresh_db):
        """saved_filters table must be created by converge()."""
        assert _table_exists(fresh_db, "saved_filters")

    def test_has_expected_columns(self, fresh_db):
        """saved_filters has all required columns."""
        cols = _get_columns(fresh_db, "saved_filters")
        expected = {"id", "name", "filters", "created_by", "created_at", "updated_at"}
        assert expected == cols

    def test_insert_and_query(self, fresh_db):
        """Can insert and read back a saved filter."""
        fresh_db.execute(
            "INSERT INTO saved_filters (id, name, filters) "
            "VALUES ('sf1', 'My Filter', '{\"status\": \"active\"}')"
        )
        row = fresh_db.execute("SELECT * FROM saved_filters WHERE id = 'sf1'").fetchone()
        assert row["name"] == "My Filter"
        assert row["created_by"] == "system"  # DEFAULT


class TestCouplingsTable:
    """Verify couplings table exists and works (CP-1)."""

    def test_table_exists(self, fresh_db):
        """couplings table must be created by converge()."""
        assert _table_exists(fresh_db, "couplings")

    def test_has_expected_columns(self, fresh_db):
        """couplings has all 11 required columns from CouplingService."""
        cols = _get_columns(fresh_db, "couplings")
        expected = {
            "coupling_id",
            "anchor_ref_type",
            "anchor_ref_id",
            "entity_refs",
            "coupling_type",
            "strength",
            "why",
            "investigation_path",
            "confidence",
            "created_at",
            "updated_at",
        }
        assert expected == cols

    def test_insert_and_query(self, fresh_db):
        """Can insert a coupling row matching CouplingService's INSERT pattern."""
        import json

        fresh_db.execute(
            "INSERT INTO couplings "
            "(coupling_id, anchor_ref_type, anchor_ref_id, entity_refs, "
            " coupling_type, strength, why, investigation_path, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cpl_001",
                "signal_type",
                "revenue_anomaly",
                json.dumps([{"type": "client", "id": "c1"}, {"type": "client", "id": "c2"}]),
                "shared_signals",
                0.8,
                json.dumps({"signal_count": 4}),
                json.dumps(["signals", "invoices"]),
                0.75,
            ),
        )
        row = fresh_db.execute("SELECT * FROM couplings WHERE coupling_id = 'cpl_001'").fetchone()
        assert row["anchor_ref_type"] == "signal_type"
        assert row["strength"] == 0.8
        assert row["confidence"] == 0.75


class TestConvergeIdempotent:
    """Verify converge() works on existing DB (ALTER TABLE ADD COLUMN)."""

    def test_converge_on_existing_db(self, tmp_path):
        """converge() on a DB missing V19 columns adds them."""
        db_path = tmp_path / "converge_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Create a minimal notifications table WITHOUT V19 columns
        conn.execute(
            "CREATE TABLE notifications ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'normal', "
            "title TEXT NOT NULL, body TEXT, action_url TEXT, action_data TEXT, channels TEXT, "
            "sent_at TEXT, read_at TEXT, acted_on_at TEXT, created_at TEXT NOT NULL)"
        )
        # Create insights WITHOUT severity
        conn.execute(
            "CREATE TABLE insights ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, domain TEXT NOT NULL, "
            "title TEXT NOT NULL, description TEXT, confidence REAL DEFAULT 0.5, "
            "data TEXT, actionable INTEGER DEFAULT 0, action_taken INTEGER DEFAULT 0, "
            "created_at TEXT NOT NULL, expires_at TEXT)"
        )
        conn.commit()

        # Now run converge
        schema_engine.converge(conn)

        # Verify new columns were added
        notif_cols = _get_columns(conn, "notifications")
        assert "dismissed" in notif_cols
        assert "dismissed_at" in notif_cols
        assert "task_id" in notif_cols
        assert "recipient_id" in notif_cols

        insight_cols = _get_columns(conn, "insights")
        assert "severity" in insight_cols

        # Verify new tables were created
        assert _table_exists(conn, "saved_filters")
        assert _table_exists(conn, "couplings")

        conn.close()


class TestSchemaDeclarations:
    """Verify schema.py TABLES dict has correct entries."""

    def test_notifications_in_tables(self):
        """notifications table declared with V19 columns."""
        notif = TABLES["notifications"]
        col_names = [c[0] for c in notif["columns"]]
        assert "dismissed" in col_names
        assert "dismissed_at" in col_names
        assert "task_id" in col_names
        assert "recipient_id" in col_names

    def test_insights_in_tables(self):
        """insights table declared with severity column."""
        insights = TABLES["insights"]
        col_names = [c[0] for c in insights["columns"]]
        assert "severity" in col_names

    def test_saved_filters_in_tables(self):
        """saved_filters table declared in TABLES dict."""
        assert "saved_filters" in TABLES
        cols = [c[0] for c in TABLES["saved_filters"]["columns"]]
        assert "id" in cols
        assert "name" in cols
        assert "filters" in cols

    def test_couplings_in_tables(self):
        """couplings table declared in TABLES dict."""
        assert "couplings" in TABLES
        cols = [c[0] for c in TABLES["couplings"]["columns"]]
        assert "coupling_id" in cols
        assert "anchor_ref_type" in cols
        assert "entity_refs" in cols
