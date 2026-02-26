"""
Tests for HealthUnifier — unified health score provider.
"""

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from lib.intelligence.health_unifier import (
    HealthScore,
    HealthUnifier,
    classify_score,
)


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with score_history table."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            composite_score REAL NOT NULL,
            dimensions_json TEXT,
            data_completeness REAL,
            recorded_at TEXT NOT NULL,
            recorded_date TEXT NOT NULL,
            UNIQUE(entity_type, entity_id, recorded_date)
        );

        CREATE INDEX idx_score_history_lookup
        ON score_history(entity_type, entity_id, recorded_date);
    """)
    conn.close()
    return db_path


def _insert_score(db_path, entity_type, entity_id, score, dims=None, days_ago=0):
    """Insert a score record days_ago days in the past."""
    dt = datetime.now() - timedelta(days=days_ago)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT OR REPLACE INTO score_history
           (entity_type, entity_id, composite_score, dimensions_json,
            data_completeness, recorded_at, recorded_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            entity_type,
            entity_id,
            score,
            json.dumps(dims or {}),
            0.85,
            dt.isoformat(),
            dt.strftime("%Y-%m-%d"),
        ),
    )
    conn.commit()
    conn.close()


class TestClassifyScore:
    def test_excellent(self):
        assert classify_score(85) == "excellent"

    def test_good(self):
        assert classify_score(70) == "good"

    def test_fair(self):
        assert classify_score(55) == "fair"

    def test_poor(self):
        assert classify_score(40) == "poor"

    def test_critical(self):
        assert classify_score(20) == "critical"

    def test_boundary_80(self):
        assert classify_score(80) == "excellent"

    def test_boundary_65(self):
        assert classify_score(65) == "good"


class TestHealthUnifier:
    def test_get_latest_health(self, test_db):
        _insert_score(test_db, "client", "c1", 72.5, {"delivery": 80, "comms": 65})

        hu = HealthUnifier(test_db)
        health = hu.get_latest_health("client", "c1")

        assert health is not None
        assert health.composite_score == 72.5
        assert health.classification == "good"
        assert health.dimensions["delivery"] == 80

    def test_get_latest_returns_most_recent(self, test_db):
        _insert_score(test_db, "client", "c1", 50.0, days_ago=5)
        _insert_score(test_db, "client", "c1", 75.0, days_ago=0)

        hu = HealthUnifier(test_db)
        health = hu.get_latest_health("client", "c1")

        assert health is not None
        assert health.composite_score == 75.0

    def test_get_latest_returns_none_for_missing(self, test_db):
        hu = HealthUnifier(test_db)
        health = hu.get_latest_health("client", "nonexistent")
        # Falls back to live computation which will fail in test env
        assert health is None

    def test_get_health_trend(self, test_db):
        for i in range(5):
            _insert_score(test_db, "client", "c1", 60 + i * 5, days_ago=4 - i)

        hu = HealthUnifier(test_db)
        trend = hu.get_health_trend("client", "c1", days=7)

        assert len(trend) == 5
        # Should be chronologically ordered (oldest first)
        assert trend[0].composite_score == 60
        assert trend[4].composite_score == 80

    def test_get_health_at_time(self, test_db):
        _insert_score(test_db, "client", "c1", 60, days_ago=10)
        _insert_score(test_db, "client", "c1", 70, days_ago=5)
        _insert_score(test_db, "client", "c1", 80, days_ago=0)

        hu = HealthUnifier(test_db)
        target_date = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        health = hu.get_health_at_time("client", "c1", target_date)

        assert health is not None
        assert health.composite_score == 60  # The one from 10 days ago (closest <= target)

    def test_get_all_latest_health(self, test_db):
        _insert_score(test_db, "client", "c1", 70)
        _insert_score(test_db, "client", "c2", 55)
        _insert_score(test_db, "client", "c3", 85)

        hu = HealthUnifier(test_db)
        all_health = hu.get_all_latest_health("client")

        assert len(all_health) == 3
        scores = {h.entity_id: h.composite_score for h in all_health}
        assert scores["c1"] == 70
        assert scores["c2"] == 55
        assert scores["c3"] == 85

    def test_record_health(self, test_db):
        hu = HealthUnifier(test_db)
        hu.record_health(
            "client",
            "c1",
            72.5,
            {"delivery": 80, "comms": 65},
            data_completeness=0.9,
        )

        health = hu.get_latest_health("client", "c1")
        assert health is not None
        assert health.composite_score == 72.5
        assert health.data_completeness == 0.9

    def test_record_replaces_same_day(self, test_db):
        hu = HealthUnifier(test_db)
        hu.record_health("client", "c1", 60, {})
        hu.record_health("client", "c1", 70, {})

        trend = hu.get_health_trend("client", "c1", days=1)
        assert len(trend) == 1
        assert trend[0].composite_score == 70

    def test_health_score_to_dict(self):
        hs = HealthScore(
            entity_type="client",
            entity_id="c1",
            composite_score=72.5,
            dimensions={"delivery": 80},
            data_completeness=0.85,
            recorded_at="2026-02-21T12:00:00",
            classification="good",
        )
        d = hs.to_dict()
        assert d["composite_score"] == 72.5
        assert d["classification"] == "good"
        assert d["data_completeness"] == 0.85
