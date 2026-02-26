"""
Tests for PatternTrendAnalyzer — pattern direction classification.

Brief 18 (ID), Task ID-5.1 + ID-6.1
"""

import sqlite3

import pytest

from lib.intelligence.pattern_trending import (
    PatternCycleSnapshot,
    PatternTrendAnalyzer,
)


@pytest.fixture
def analyzer(tmp_path):
    db_path = tmp_path / "test_patterns.db"
    return PatternTrendAnalyzer(db_path=db_path)


def _make_snapshots(
    pattern_key: str,
    pattern_type: str,
    presence: list[bool],
    entity_counts: list[int] | None = None,
    strengths: list[float] | None = None,
) -> list[PatternCycleSnapshot]:
    """Helper to build snapshot list from presence booleans."""
    n = len(presence)
    if entity_counts is None:
        entity_counts = [3] * n
    if strengths is None:
        strengths = [0.7] * n
    return [
        PatternCycleSnapshot(
            pattern_key=pattern_key,
            pattern_type=pattern_type,
            cycle_index=i,
            entity_count=entity_counts[i],
            evidence_strength=strengths[i],
            is_present=presence[i],
        )
        for i in range(n)
    ]


class TestClassifyDirection:
    """Direct direction classification tests."""

    def test_new_pattern(self, analyzer):
        # Present only in current cycle
        snaps = _make_snapshots("p1", "overdue_cluster", [True, False, False, False])
        result = analyzer.analyze_pattern_trend("p1", snaps)
        assert result.current_direction == "new"

    def test_persistent_pattern(self, analyzer):
        # Present in current + 4 past cycles
        snaps = _make_snapshots("p2", "comm_drop", [True, True, True, True, True])
        result = analyzer.analyze_pattern_trend("p2", snaps)
        assert result.current_direction == "persistent"

    def test_resolving_pattern(self, analyzer):
        # Not in current, was in past
        snaps = _make_snapshots("p3", "overdue_cluster", [False, True, True, True, True])
        result = analyzer.analyze_pattern_trend("p3", snaps)
        assert result.current_direction == "resolving"

    def test_worsening_by_entity_count(self, analyzer):
        # Current entity_count > avg of past * 1.2
        snaps = _make_snapshots(
            "p4",
            "health_cluster",
            presence=[True, True, True, True],
            entity_counts=[10, 3, 3, 3],  # current 10 vs avg 3 → worsening
            strengths=[0.7, 0.7, 0.7, 0.7],
        )
        result = analyzer.analyze_pattern_trend("p4", snaps)
        assert result.current_direction == "worsening"

    def test_worsening_by_evidence_strength(self, analyzer):
        snaps = _make_snapshots(
            "p5",
            "revenue_decline",
            presence=[True, True, True, True],
            entity_counts=[3, 3, 3, 3],
            strengths=[0.95, 0.5, 0.5, 0.5],  # current 0.95 vs avg 0.5 → worsening
        )
        result = analyzer.analyze_pattern_trend("p5", snaps)
        assert result.current_direction == "worsening"

    def test_empty_snapshots(self, analyzer):
        result = analyzer.analyze_pattern_trend("p_empty", [])
        assert result.current_direction == "new"
        assert result.current_entity_count == 0


class TestTrendMetrics:
    """Verify trend analysis metrics are computed correctly."""

    def test_avg_entity_count(self, analyzer):
        snaps = _make_snapshots(
            "m1",
            "test",
            presence=[True, True, True, True],
            entity_counts=[5, 2, 4, 6],
        )
        result = analyzer.analyze_pattern_trend("m1", snaps)
        # Past = [2, 4, 6], avg = 4.0
        assert result.avg_entity_count_last_5 == pytest.approx(4.0)

    def test_avg_evidence_strength(self, analyzer):
        snaps = _make_snapshots(
            "m2",
            "test",
            presence=[True, True, True],
            strengths=[0.9, 0.6, 0.8],
        )
        result = analyzer.analyze_pattern_trend("m2", snaps)
        # Past = [0.6, 0.8], avg = 0.7
        assert result.avg_evidence_strength_last_5 == pytest.approx(0.7)

    def test_cycles_present_count(self, analyzer):
        snaps = _make_snapshots(
            "m3",
            "test",
            presence=[True, True, False, True, False, True],
        )
        result = analyzer.analyze_pattern_trend("m3", snaps)
        # Past presence: [True, False, True, False, True] → 3 present
        assert result.cycles_present_in_last_5 == 3

    def test_presence_history_limited(self, analyzer):
        snaps = _make_snapshots(
            "m4",
            "test",
            presence=[True, True, True, True, True, True, True, True],
        )
        result = analyzer.analyze_pattern_trend("m4", snaps)
        # lookback_cycles=5, so presence history should be at most 6 (current + 5)
        assert len(result.cycle_presence_history) <= 6


class TestToDict:
    """Serialization."""

    def test_round_trip(self, analyzer):
        snaps = _make_snapshots("d1", "overdue_cluster", [True, True, True])
        result = analyzer.analyze_pattern_trend("d1", snaps)
        d = result.to_dict()
        assert d["pattern_key"] == "d1"
        assert d["pattern_type"] == "overdue_cluster"
        assert "current_direction" in d
        assert isinstance(d["avg_entity_count_last_5"], int | float)
        assert isinstance(d["avg_evidence_strength_last_5"], float)


class TestDBIntegration:
    """Test loading patterns from actual SQLite DB."""

    def test_refresh_all_from_db(self, tmp_path):
        db_path = tmp_path / "patterns.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE pattern_snapshots (
                pattern_id TEXT,
                pattern_type TEXT,
                cycle_id TEXT,
                detected_at TEXT,
                entities_json TEXT DEFAULT '[]',
                evidence_json TEXT DEFAULT '{}'
            )
            """
        )
        # Insert 4 cycles for one pattern
        for i in range(4):
            conn.execute(
                """
                INSERT INTO pattern_snapshots (
                    pattern_id, pattern_type, cycle_id, detected_at,
                    entities_json, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "overdue_cluster",
                    "overdue_cluster",
                    f"cycle_{i}",
                    f"2026-04-{15 - i}T10:00:00",
                    '["client_a", "client_b"]',
                    '{"confidence": 0.75}',
                ),
            )
        conn.commit()
        conn.close()

        analyzer = PatternTrendAnalyzer(db_path=db_path)
        trends = analyzer.refresh_all_pattern_trends()
        assert "overdue_cluster" in trends
        assert trends["overdue_cluster"].current_direction == "persistent"

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE pattern_snapshots (
                pattern_id TEXT,
                pattern_type TEXT,
                cycle_id TEXT,
                detected_at TEXT,
                entities_json TEXT DEFAULT '[]',
                evidence_json TEXT DEFAULT '{}'
            )
            """
        )
        conn.commit()
        conn.close()

        analyzer = PatternTrendAnalyzer(db_path=db_path)
        trends = analyzer.refresh_all_pattern_trends()
        assert trends == {}
