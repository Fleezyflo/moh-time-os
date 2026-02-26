"""
Tests for OutcomeTracker — signal resolution recording and metrics.

Brief 18 (ID), Task ID-4.1 + ID-6.1
"""

from datetime import datetime

import pytest

from lib.intelligence.outcome_tracker import OutcomeTracker


@pytest.fixture
def tracker(tmp_path):
    db_path = tmp_path / "test_outcomes.db"
    return OutcomeTracker(db_path=db_path)


class TestRecordOutcome:
    def test_natural_resolution(self, tracker):
        outcome = tracker.record_outcome(
            signal_key="sig_health::client_a",
            entity_type="client",
            entity_id="client_a",
            signal_type="health_declining",
            detected_at=datetime(2026, 4, 1, 10, 0),
            cleared_at=datetime(2026, 4, 10, 10, 0),
            health_before=55.0,
            health_after=72.0,
        )
        assert outcome.resolution_type == "natural"
        assert outcome.health_improved is True
        assert outcome.duration_days == pytest.approx(9.0)

    def test_addressed_resolution(self, tracker):
        outcome = tracker.record_outcome(
            signal_key="sig_overdue::client_b",
            entity_type="client",
            entity_id="client_b",
            signal_type="overdue_tasks",
            detected_at=datetime(2026, 4, 1, 10, 0),
            cleared_at=datetime(2026, 4, 5, 10, 0),
            health_before=60.0,
            health_after=75.0,
            actions_taken=["cleared_overdue_tasks", "reassigned_work"],
        )
        assert outcome.resolution_type == "addressed"
        assert outcome.health_improved is True

    def test_expired_resolution(self, tracker):
        outcome = tracker.record_outcome(
            signal_key="sig_comm::client_c",
            entity_type="client",
            entity_id="client_c",
            signal_type="comm_drop",
            detected_at=datetime(2026, 4, 1, 10, 0),
            cleared_at=datetime(2026, 4, 15, 10, 0),
            health_before=70.0,
            health_after=65.0,
        )
        assert outcome.resolution_type == "expired"
        assert outcome.health_improved is False

    def test_unknown_resolution(self, tracker):
        outcome = tracker.record_outcome(
            signal_key="sig_misc::client_d",
            entity_type="client",
            entity_id="client_d",
            signal_type="misc_signal",
            detected_at=datetime(2026, 4, 1, 10, 0),
            cleared_at=datetime(2026, 4, 10, 10, 0),
        )
        assert outcome.resolution_type == "unknown"

    def test_outcome_has_id(self, tracker):
        outcome = tracker.record_outcome(
            signal_key="sig_test::e",
            entity_type="client",
            entity_id="e",
            signal_type="test",
            detected_at=datetime(2026, 4, 1, 10, 0),
            cleared_at=datetime(2026, 4, 2, 10, 0),
        )
        assert outcome.id is not None
        assert len(outcome.id) > 0


class TestQueryOutcomes:
    def test_get_by_entity(self, tracker):
        tracker.record_outcome(
            signal_key="sig_1",
            entity_type="client",
            entity_id="client_a",
            signal_type="health_declining",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 5),
            health_before=50.0,
            health_after=70.0,
        )
        tracker.record_outcome(
            signal_key="sig_2",
            entity_type="client",
            entity_id="client_b",
            signal_type="overdue",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 5),
        )

        results = tracker.get_outcomes_for_entity("client", "client_a")
        assert len(results) == 1
        assert results[0].signal_key == "sig_1"

    def test_get_by_type(self, tracker):
        tracker.record_outcome(
            signal_key="sig_1",
            entity_type="client",
            entity_id="a",
            signal_type="health_declining",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 5),
        )
        tracker.record_outcome(
            signal_key="sig_2",
            entity_type="client",
            entity_id="b",
            signal_type="health_declining",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 5),
        )
        results = tracker.get_outcomes_by_type("health_declining")
        assert len(results) == 2

    def test_get_by_resolution(self, tracker):
        tracker.record_outcome(
            signal_key="sig_nat",
            entity_type="client",
            entity_id="a",
            signal_type="test",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 5),
            health_before=50.0,
            health_after=80.0,
        )
        results = tracker.get_outcomes_by_resolution("natural")
        assert len(results) == 1


class TestEffectivenessMetrics:
    def test_metrics_with_data(self, tracker):
        # Natural
        tracker.record_outcome(
            signal_key="s1",
            entity_type="client",
            entity_id="a",
            signal_type="health",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 5),
            health_before=50.0,
            health_after=75.0,
        )
        # Addressed
        tracker.record_outcome(
            signal_key="s2",
            entity_type="client",
            entity_id="b",
            signal_type="overdue",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 8),
            health_before=60.0,
            health_after=80.0,
            actions_taken=["fix"],
        )
        # Expired
        tracker.record_outcome(
            signal_key="s3",
            entity_type="client",
            entity_id="c",
            signal_type="comm",
            detected_at=datetime(2026, 4, 1),
            cleared_at=datetime(2026, 4, 10),
            health_before=70.0,
            health_after=65.0,
        )

        metrics = tracker.get_effectiveness_metrics()
        assert metrics["total_outcomes"] == 3
        assert metrics["resolution_type_breakdown"]["natural"] == 1
        assert metrics["resolution_type_breakdown"]["addressed"] == 1
        assert metrics["resolution_type_breakdown"]["expired"] == 1
        assert metrics["improvement_rate"] == pytest.approx(2 / 3, abs=0.01)
        assert metrics["action_success_rate"] == 1.0

    def test_metrics_empty(self, tracker):
        metrics = tracker.get_effectiveness_metrics()
        assert metrics["total_outcomes"] == 0
        assert metrics["improvement_rate"] == 0.0
