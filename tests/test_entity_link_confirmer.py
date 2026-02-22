"""Tests for entity link auto-confirmer."""

import sqlite3
import tempfile

import pytest

from lib.entity_link_confirmer import (
    auto_confirm_links,
    flag_low_confidence_links,
    link_confirmation_report,
)


@pytest.fixture
def test_db():
    """Create test DB with entity_links."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(tmp.name)

    conn.executescript("""
        CREATE TABLE entity_links (
            link_id TEXT PRIMARY KEY,
            from_artifact_id TEXT,
            to_entity_type TEXT,
            to_entity_id TEXT,
            method TEXT,
            confidence REAL,
            confidence_reasons TEXT,
            status TEXT DEFAULT 'proposed',
            created_at TEXT,
            updated_at TEXT,
            confirmed_by TEXT,
            confirmed_at TEXT
        );

        -- High confidence proposed (should be confirmed at 0.85 threshold)
        INSERT INTO entity_links VALUES ('l1', 'a1', 'client', 'c1', 'naming', 0.95, '{}', 'proposed', '', '', NULL, NULL);
        INSERT INTO entity_links VALUES ('l2', 'a2', 'client', 'c2', 'headers', 0.88, '{}', 'proposed', '', '', NULL, NULL);

        -- Below threshold (should stay proposed)
        INSERT INTO entity_links VALUES ('l3', 'a3', 'client', 'c3', 'naming', 0.75, '{}', 'proposed', '', '', NULL, NULL);
        INSERT INTO entity_links VALUES ('l4', 'a4', 'person', 'p1', 'naming', 0.40, '{}', 'proposed', '', '', NULL, NULL);

        -- Already confirmed (should not be touched)
        INSERT INTO entity_links VALUES ('l5', 'a5', 'client', 'c1', 'rules', 0.99, '{}', 'confirmed', '', '', 'manual', '2025-01-01');
    """)

    conn.commit()
    conn.close()
    return tmp.name


class TestAutoConfirm:
    """Tests for auto_confirm_links."""

    def test_confirms_above_threshold(self, test_db):
        result = auto_confirm_links(test_db, confidence_threshold=0.85)
        assert result["confirmed"] == 2  # l1 (0.95) and l2 (0.88)

    def test_does_not_confirm_below_threshold(self, test_db):
        auto_confirm_links(test_db, confidence_threshold=0.85)
        conn = sqlite3.connect(test_db)
        status = conn.execute("SELECT status FROM entity_links WHERE link_id = 'l3'").fetchone()[0]
        conn.close()
        assert status == "proposed"

    def test_does_not_touch_already_confirmed(self, test_db):
        auto_confirm_links(test_db, confidence_threshold=0.85)
        conn = sqlite3.connect(test_db)
        row = conn.execute("SELECT confirmed_by FROM entity_links WHERE link_id = 'l5'").fetchone()
        conn.close()
        assert row[0] == "manual"  # Original confirmer preserved

    def test_dry_run_no_changes(self, test_db):
        result = auto_confirm_links(test_db, confidence_threshold=0.85, dry_run=True)
        assert result["dry_run"] is True
        assert result["would_confirm"] == 2
        assert result["confirmed"] == 0

        # Verify nothing changed
        conn = sqlite3.connect(test_db)
        proposed = conn.execute(
            "SELECT COUNT(*) FROM entity_links WHERE status = 'proposed'"
        ).fetchone()[0]
        conn.close()
        assert proposed == 4  # All still proposed

    def test_idempotent(self, test_db):
        r1 = auto_confirm_links(test_db, confidence_threshold=0.85)
        r2 = auto_confirm_links(test_db, confidence_threshold=0.85)
        assert r1["confirmed"] == 2
        assert r2["confirmed"] == 0  # Nothing left to confirm

    def test_sets_confirmed_by_field(self, test_db):
        auto_confirm_links(test_db, confidence_threshold=0.85)
        conn = sqlite3.connect(test_db)
        row = conn.execute("SELECT confirmed_by FROM entity_links WHERE link_id = 'l1'").fetchone()
        conn.close()
        assert row[0] == "auto_confirmer"


class TestFlagLowConfidence:
    """Tests for flag_low_confidence_links."""

    def test_flags_below_threshold(self, test_db):
        flagged = flag_low_confidence_links(test_db, threshold=0.50)
        assert len(flagged) == 1  # l4 at 0.40
        assert flagged[0]["link_id"] == "l4"

    def test_respects_limit(self, test_db):
        flagged = flag_low_confidence_links(test_db, threshold=0.99, limit=2)
        assert len(flagged) <= 2


class TestReport:
    """Tests for link_confirmation_report."""

    def test_report_has_required_fields(self, test_db):
        report = link_confirmation_report(test_db)
        assert "total_links" in report
        assert "status_distribution" in report
        assert "method_stats" in report
        assert report["total_links"] == 5
