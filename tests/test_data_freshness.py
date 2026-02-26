"""
Tests for DataFreshnessTracker — freshness scoring and stale detection.

Brief 27 (DQ), Task DQ-1.1
"""

from datetime import datetime, timedelta

import pytest

from lib.intelligence.data_freshness import (
    DataFreshnessTracker,
    compute_freshness_score,
)


@pytest.fixture
def tracker(tmp_path):
    db_path = tmp_path / "test_freshness.db"
    return DataFreshnessTracker(db_path=db_path)


class TestComputeFreshnessScore:
    def test_just_collected(self):
        assert compute_freshness_score(0, 48) == 1.0

    def test_at_threshold(self):
        # At threshold (48h), score should be 0.5
        assert compute_freshness_score(48, 48) == pytest.approx(0.5)

    def test_at_double_threshold(self):
        # At 2x threshold, score = 0.0
        assert compute_freshness_score(96, 48) == 0.0

    def test_beyond_double_threshold(self):
        assert compute_freshness_score(200, 48) == 0.0

    def test_halfway(self):
        # At 24h with 48h threshold → score = 0.75
        assert compute_freshness_score(24, 48) == pytest.approx(0.75)

    def test_negative_hours(self):
        assert compute_freshness_score(-1, 48) == 1.0


class TestRecordCollection:
    def test_basic_record(self, tracker):
        tracker.record_collection("client", "c1", "harvest")
        records = tracker.get_freshness("client", "c1")
        assert len(records) == 1
        assert records[0].source == "harvest"
        assert records[0].freshness_score > 0.9  # just recorded

    def test_updates_on_rerecord(self, tracker):
        tracker.record_collection("client", "c1", "harvest", record_count=5)
        tracker.record_collection("client", "c1", "harvest", record_count=3)
        records = tracker.get_freshness("client", "c1", source="harvest")
        assert len(records) == 1

    def test_multiple_sources(self, tracker):
        tracker.record_collection("client", "c1", "harvest")
        tracker.record_collection("client", "c1", "email")
        records = tracker.get_freshness("client", "c1")
        assert len(records) == 2
        sources = {r.source for r in records}
        assert sources == {"harvest", "email"}


class TestEntityFreshness:
    def test_fresh_entity(self, tracker):
        tracker.record_collection("client", "c1", "harvest")
        tracker.record_collection("client", "c1", "email")

        freshness = tracker.get_entity_freshness("client", "c1")
        assert freshness.overall_freshness > 0.9
        assert len(freshness.stale_sources) == 0
        assert freshness.freshest_source is not None

    def test_no_data(self, tracker):
        freshness = tracker.get_entity_freshness("client", "unknown")
        assert freshness.overall_freshness == 0.0
        assert freshness.sources == []

    def test_stale_source_detected(self, tracker):
        # Record old collection
        old_time = datetime.now() - timedelta(hours=200)
        tracker.record_collection("client", "c1", "harvest", collected_at=old_time)
        tracker.record_collection("client", "c1", "email")  # fresh

        freshness = tracker.get_entity_freshness("client", "c1")
        assert "harvest" in freshness.stale_sources
        assert "email" not in freshness.stale_sources
        assert freshness.stalest_source == "harvest"

    def test_to_dict(self, tracker):
        tracker.record_collection("client", "c1", "harvest")
        freshness = tracker.get_entity_freshness("client", "c1")
        d = freshness.to_dict()
        assert "overall_freshness" in d
        assert "stale_sources" in d
        assert "sources" in d


class TestStaleSources:
    def test_no_stale_when_fresh(self, tracker):
        tracker.record_collection("client", "c1", "harvest")
        stale = tracker.get_stale_sources()
        assert len(stale) == 0

    def test_finds_stale(self, tracker):
        old_time = datetime.now() - timedelta(hours=200)
        tracker.record_collection("client", "c1", "harvest", collected_at=old_time)
        stale = tracker.get_stale_sources()
        assert len(stale) == 1
        assert stale[0].source == "harvest"

    def test_filter_by_entity_type(self, tracker):
        old_time = datetime.now() - timedelta(hours=200)
        tracker.record_collection("client", "c1", "harvest", collected_at=old_time)
        tracker.record_collection("project", "p1", "harvest", collected_at=old_time)

        stale = tracker.get_stale_sources(entity_type="client")
        assert len(stale) == 1
        assert stale[0].entity_type == "client"


class TestFreshnessDashboard:
    def test_dashboard_with_data(self, tracker):
        tracker.record_collection("client", "c1", "harvest")
        tracker.record_collection("client", "c1", "email")
        old_time = datetime.now() - timedelta(hours=200)
        tracker.record_collection("client", "c2", "harvest", collected_at=old_time)

        dashboard = tracker.get_freshness_dashboard()
        assert dashboard["total_tracked"] == 3
        assert dashboard["fresh_count"] >= 2
        assert dashboard["stale_count"] >= 1
        assert "harvest" in dashboard["avg_freshness_by_source"]
        assert dashboard["overall_freshness"] > 0

    def test_dashboard_empty(self, tracker):
        dashboard = tracker.get_freshness_dashboard()
        assert dashboard["total_tracked"] == 0
        assert dashboard["overall_freshness"] == 0.0
