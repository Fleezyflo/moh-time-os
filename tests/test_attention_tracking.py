"""
Tests for AttentionTracker — attention debt and investment tracking.

Brief 30 (AT), Task AT-1.1
"""

import pytest

from lib.intelligence.attention_tracking import (
    AttentionTracker,
    classify_debt_level,
)


@pytest.fixture
def tracker(tmp_path):
    db_path = tmp_path / "test_attention.db"
    return AttentionTracker(db_path=db_path)


class TestClassifyDebtLevel:
    def test_healthy(self):
        assert classify_debt_level(0) == "healthy"

    def test_minor(self):
        assert classify_debt_level(1) == "minor"

    def test_moderate(self):
        assert classify_debt_level(2) == "moderate"

    def test_severe(self):
        assert classify_debt_level(5) == "severe"


class TestRecordAttention:
    def test_basic_record(self, tracker):
        event = tracker.record_attention(
            "client",
            "c1",
            "review",
            duration_minutes=15.0,
        )
        assert event.id is not None
        assert event.entity_type == "client"
        assert event.entity_id == "c1"
        assert event.duration_minutes == 15.0

    def test_to_dict(self, tracker):
        event = tracker.record_attention("client", "c1", "check_in")
        d = event.to_dict()
        assert "entity_type" in d
        assert "event_type" in d


class TestAttentionDebt:
    def test_no_attention_has_debt(self, tracker):
        debt = tracker.get_attention_debt("client", "c1")
        # No events recorded → high debt
        assert debt.actual_reviews_last_week == 0
        assert debt.days_since_attention == 999

    def test_recent_attention_no_debt(self, tracker):
        tracker.record_attention("client", "c1", "review")
        tracker.record_attention("client", "c1", "review")
        debt = tracker.get_attention_debt("client", "c1")
        assert debt.actual_reviews_last_week == 2
        assert debt.debt_level == "healthy"
        assert debt.days_since_attention == 0

    def test_to_dict(self, tracker):
        debt = tracker.get_attention_debt("client", "c1")
        d = debt.to_dict()
        assert "debt_level" in d
        assert "expected_reviews_per_week" in d


class TestAttentionSummary:
    def test_empty_summary(self, tracker):
        summary = tracker.get_attention_summary()
        assert summary.total_entities == 0
        assert summary.total_attention_minutes_week == 0.0

    def test_summary_with_data(self, tracker):
        tracker.record_attention("client", "c1", "review", duration_minutes=20)
        tracker.record_attention("client", "c1", "review", duration_minutes=15)
        tracker.record_attention("client", "c2", "check_in", duration_minutes=5)

        summary = tracker.get_attention_summary()
        assert summary.total_entities == 2
        assert summary.total_attention_minutes_week == 40.0
        assert summary.avg_attention_per_entity == 20.0

    def test_summary_filtered_by_type(self, tracker):
        tracker.record_attention("client", "c1", "review", duration_minutes=10)
        tracker.record_attention("project", "p1", "review", duration_minutes=5)

        summary = tracker.get_attention_summary(entity_type="client")
        assert summary.total_entities == 1

    def test_to_dict(self, tracker):
        summary = tracker.get_attention_summary()
        d = summary.to_dict()
        assert "debt_distribution" in d
        assert "most_attended" in d


class TestNeglectedEntities:
    def test_finds_neglected(self, tracker):
        # c1 has attention, c2 and c3 don't
        tracker.record_attention("client", "c1", "review")

        neglected = tracker.get_neglected_entities(
            "client",
            ["c1", "c2", "c3"],
            days_threshold=1,
        )
        ids = [n.entity_id for n in neglected]
        assert "c2" in ids
        assert "c3" in ids
        assert "c1" not in ids

    def test_sorted_by_staleness(self, tracker):
        neglected = tracker.get_neglected_entities(
            "client",
            ["c1", "c2"],
            days_threshold=0,
        )
        # Both neglected, sorted by days_since descending
        assert len(neglected) == 2
