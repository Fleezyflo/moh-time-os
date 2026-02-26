"""
Tests for score history (trend tracking) functionality.

Tests:
- record_score persists to DB
- get_score_trend returns correct structure
- record_all_scores processes all entity types
- trend calculation works correctly
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib.intelligence.scorecard import (
    get_score_history_summary,
    get_score_trend,
    record_score,
)
from lib.migrations.v30_score_history import run_migration, verify_migration


@pytest.fixture
def test_db():
    """Create a test database with score_history table."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Run migration to create table
    run_migration(db_path)
    assert verify_migration(db_path), "Migration failed"

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def sample_scorecard():
    """Sample scorecard dict for testing."""
    return {
        "entity_type": "client",
        "entity_id": "test-client-1",
        "entity_name": "Test Client",
        "composite_score": 75.5,
        "composite_classification": "healthy",
        "dimensions": [
            {"name": "operational_health", "score": 80.0, "classification": "healthy"},
            {"name": "financial_health", "score": 70.0, "classification": "stable"},
        ],
        "scored_at": datetime.now().isoformat(),
        "data_completeness": 0.9,
    }


class TestRecordScore:
    """Tests for record_score function."""

    def test_record_score_success(self, test_db, sample_scorecard):
        """Test that record_score saves to database."""
        result = record_score(sample_scorecard, db_path=test_db)
        assert result is True

        # Verify in DB
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM score_history WHERE entity_id = ?", ("test-client-1",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[2] == "test-client-1"  # entity_id
        assert row[3] == 75.5  # composite_score

    def test_record_score_replaces_same_day(self, test_db, sample_scorecard):
        """Test that recording twice on same day replaces."""
        record_score(sample_scorecard, db_path=test_db)

        # Update score and record again
        sample_scorecard["composite_score"] = 85.0
        record_score(sample_scorecard, db_path=test_db)

        # Should still be only 1 record
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM score_history WHERE entity_id = ?", ("test-client-1",))
        count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT composite_score FROM score_history WHERE entity_id = ?", ("test-client-1",)
        )
        score = cursor.fetchone()[0]
        conn.close()

        assert count == 1
        assert score == 85.0  # Updated value

    def test_record_score_rejects_none_score(self, test_db):
        """Test that None scores are not recorded."""
        scorecard = {
            "entity_type": "client",
            "entity_id": "test-client-2",
            "composite_score": None,
        }
        result = record_score(scorecard, db_path=test_db)
        assert result is False

    def test_record_score_rejects_empty_dict(self, test_db):
        """Test that empty dict is not recorded."""
        result = record_score({}, db_path=test_db)
        assert result is False


class TestGetScoreTrend:
    """Tests for get_score_trend function."""

    def test_trend_empty_history(self, test_db):
        """Test trend with no history returns insufficient_data."""
        result = get_score_trend("client", "nonexistent", days=30, db_path=test_db)

        assert result["trend"] == "insufficient_data"
        assert result["history"] == []
        assert result["current_score"] is None

    def test_trend_with_history(self, test_db):
        """Test trend calculation with history data."""
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()

        # Insert test data spanning multiple days
        base_date = datetime.now()
        for i in range(10):
            date = base_date - timedelta(days=i)
            score = 50 + i * 3  # Increasing scores going back in time
            cursor.execute(
                """
                INSERT INTO score_history
                (entity_type, entity_id, composite_score, dimensions_json,
                 data_completeness, recorded_at, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "client",
                    "trend-test-client",
                    score,
                    "[]",
                    0.9,
                    date.isoformat(),
                    date.strftime("%Y-%m-%d"),
                ),
            )

        conn.commit()
        conn.close()

        result = get_score_trend("client", "trend-test-client", days=30, db_path=test_db)

        assert result["entity_type"] == "client"
        assert result["entity_id"] == "trend-test-client"
        assert len(result["history"]) == 10
        assert result["data_points"] == 10
        assert result["current_score"] is not None
        assert result["period_high"] is not None
        assert result["period_low"] is not None

    def test_trend_improving(self, test_db):
        """Test that improving scores are detected."""
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()

        base_date = datetime.now()
        scores = [40, 45, 50, 55, 60, 65, 70]  # Improving

        for i, score in enumerate(scores):
            date = base_date - timedelta(days=len(scores) - 1 - i)
            cursor.execute(
                """
                INSERT INTO score_history
                (entity_type, entity_id, composite_score, dimensions_json,
                 data_completeness, recorded_at, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "client",
                    "improving-client",
                    score,
                    "[]",
                    0.9,
                    date.isoformat(),
                    date.strftime("%Y-%m-%d"),
                ),
            )

        conn.commit()
        conn.close()

        result = get_score_trend("client", "improving-client", days=30, db_path=test_db)

        assert result["trend"] == "improving"
        assert result["change_pct"] > 0

    def test_trend_declining(self, test_db):
        """Test that declining scores are detected."""
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()

        base_date = datetime.now()
        scores = [70, 65, 60, 55, 50, 45, 40]  # Declining

        for i, score in enumerate(scores):
            date = base_date - timedelta(days=len(scores) - 1 - i)
            cursor.execute(
                """
                INSERT INTO score_history
                (entity_type, entity_id, composite_score, dimensions_json,
                 data_completeness, recorded_at, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "client",
                    "declining-client",
                    score,
                    "[]",
                    0.9,
                    date.isoformat(),
                    date.strftime("%Y-%m-%d"),
                ),
            )

        conn.commit()
        conn.close()

        result = get_score_trend("client", "declining-client", days=30, db_path=test_db)

        assert result["trend"] == "declining"
        assert result["change_pct"] < 0


class TestGetScoreHistorySummary:
    """Tests for get_score_history_summary function."""

    def test_summary_empty(self, test_db):
        """Test summary with empty table."""
        result = get_score_history_summary(db_path=test_db)

        assert result["total_records"] == 0
        assert result["by_entity_type"] == {}

    def test_summary_with_data(self, test_db):
        """Test summary with data."""
        conn = sqlite3.connect(str(test_db))
        cursor = conn.cursor()

        now = datetime.now()

        # Insert test data
        for _i, (etype, eid) in enumerate(
            [
                ("client", "c1"),
                ("client", "c2"),
                ("project", "p1"),
                ("person", "per1"),
            ]
        ):
            cursor.execute(
                """
                INSERT INTO score_history
                (entity_type, entity_id, composite_score, dimensions_json,
                 data_completeness, recorded_at, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (etype, eid, 75.0, "[]", 0.9, now.isoformat(), now.strftime("%Y-%m-%d")),
            )

        conn.commit()
        conn.close()

        result = get_score_history_summary(db_path=test_db)

        assert result["total_records"] == 4
        assert "client" in result["by_entity_type"]
        assert result["by_entity_type"]["client"]["count"] == 2
        assert result["by_entity_type"]["project"]["count"] == 1
        assert result["by_entity_type"]["person"]["count"] == 1


class TestMigration:
    """Tests for migration script."""

    def test_migration_creates_table(self):
        """Test that migration creates the table."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        result = run_migration(db_path)

        assert "score_history" in result["tables_created"]
        assert verify_migration(db_path)

        db_path.unlink(missing_ok=True)

    def test_migration_idempotent(self):
        """Test that migration can be run multiple times safely."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        # Run twice
        result1 = run_migration(db_path)
        result2 = run_migration(db_path)

        # Both should succeed
        assert result1["errors"] == []
        assert result2["errors"] == []
        assert verify_migration(db_path)

        db_path.unlink(missing_ok=True)
