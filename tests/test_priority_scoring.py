"""
Tests for PriorityScorer — multi-criteria priority ranking.

Brief 23 (PS), Task PS-1.1
"""

import pytest

from lib.intelligence.priority_scoring import (
    PrioritizedEntity,
    PriorityScorer,
    classify_urgency,
    compute_data_quality_score,
    compute_health_inverse_score,
    compute_revenue_score,
    compute_signal_severity_score,
    compute_staleness_score,
    compute_trajectory_score,
)


class TestClassifyUrgency:
    def test_critical(self):
        assert classify_urgency(90) == "critical"

    def test_high(self):
        assert classify_urgency(75) == "high"

    def test_elevated(self):
        assert classify_urgency(55) == "elevated"

    def test_normal(self):
        assert classify_urgency(35) == "normal"

    def test_low(self):
        assert classify_urgency(20) == "low"


class TestComponentScores:
    def test_signal_severity(self):
        assert compute_signal_severity_score(0, 0) == 0.0
        assert compute_signal_severity_score(1, 0) == 30.0
        assert compute_signal_severity_score(2, 1) == 75.0
        assert compute_signal_severity_score(4, 0) == 100.0  # capped

    def test_health_inverse(self):
        assert compute_health_inverse_score(100) == 0.0
        assert compute_health_inverse_score(0) == 100.0
        assert compute_health_inverse_score(70) == 30.0

    def test_trajectory(self):
        assert compute_trajectory_score(5.0) == 0.0  # positive = no priority
        assert compute_trajectory_score(0.0) == 0.0
        assert compute_trajectory_score(-5.0) == 50.0
        assert compute_trajectory_score(-10.0) == 100.0
        assert compute_trajectory_score(-15.0) == 100.0  # capped

    def test_staleness(self):
        assert compute_staleness_score(0) == 0.0
        assert compute_staleness_score(3) == 0.0
        assert compute_staleness_score(14) == pytest.approx(50.0)
        assert compute_staleness_score(30) == pytest.approx(80.0)
        assert compute_staleness_score(60) >= 80.0

    def test_revenue_score(self):
        assert compute_revenue_score(0, 50000) == 0.0
        assert compute_revenue_score(25000, 50000) == 50.0
        assert compute_revenue_score(50000, 50000) == 100.0

    def test_data_quality(self):
        assert compute_data_quality_score(1.0) == 0.0
        assert compute_data_quality_score(0.0) == 100.0
        assert compute_data_quality_score(0.5) == 50.0


@pytest.fixture
def scorer():
    return PriorityScorer()


class TestScoreEntity:
    def test_healthy_entity(self, scorer):
        result = scorer.score_entity(
            entity_type="client",
            entity_id="c1",
            health_score=85,
            critical_signals=0,
            warning_signals=0,
        )
        assert result.priority_score < 30
        assert result.urgency_level in ("normal", "low")

    def test_critical_entity(self, scorer):
        result = scorer.score_entity(
            entity_type="client",
            entity_id="c1",
            health_score=20,
            critical_signals=2,
            warning_signals=1,
            trajectory_velocity=-8.0,
        )
        assert result.priority_score > 50
        assert result.urgency_level in ("critical", "high", "elevated")
        assert "low health score" in result.reason

    def test_stale_entity(self, scorer):
        result = scorer.score_entity(
            entity_type="client",
            entity_id="c1",
            health_score=70,
            days_since_review=45,
        )
        assert result.factors.staleness_score > 80

    def test_to_dict(self, scorer):
        result = scorer.score_entity(
            entity_type="client",
            entity_id="c1",
            health_score=50,
        )
        d = result.to_dict()
        assert "priority_score" in d
        assert "urgency_level" in d
        assert "factors" in d


class TestRankEntities:
    def test_ranking_order(self, scorer):
        entities = [
            {"entity_type": "client", "entity_id": "healthy", "health_score": 90},
            {
                "entity_type": "client",
                "entity_id": "critical",
                "health_score": 20,
                "critical_signals": 2,
            },
            {
                "entity_type": "client",
                "entity_id": "moderate",
                "health_score": 50,
                "warning_signals": 1,
            },
        ]
        ranked = scorer.rank_entities(entities)
        assert ranked[0].entity_id == "critical"
        assert ranked[0].priority_rank == 1
        assert ranked[-1].entity_id == "healthy"
        assert ranked[-1].priority_rank == 3

    def test_empty_list(self, scorer):
        assert scorer.rank_entities([]) == []


class TestAttentionQueue:
    def test_max_items(self, scorer):
        entities = [
            {
                "entity_type": "client",
                "entity_id": f"c{i}",
                "health_score": 10,
                "critical_signals": 3,
                "trajectory_velocity": -10.0,
                "monthly_revenue": 50000,
                "data_quality": 0.1,
            }
            for i in range(20)
        ]
        queue = scorer.get_attention_queue(entities, max_items=5)
        assert len(queue) == 5

    def test_min_urgency_filter(self, scorer):
        entities = [
            {
                "entity_type": "client",
                "entity_id": "critical",
                "health_score": 5,
                "critical_signals": 4,
                "trajectory_velocity": -10.0,
                "monthly_revenue": 50000,
                "data_quality": 0.0,
            },
            {"entity_type": "client", "entity_id": "healthy", "health_score": 95},
        ]
        queue = scorer.get_attention_queue(entities, min_urgency="elevated")
        critical_ids = [e.entity_id for e in queue]
        assert "critical" in critical_ids


class TestPriorityDistribution:
    def test_distribution(self, scorer):
        entities = [
            {"entity_type": "client", "entity_id": "c1", "health_score": 10, "critical_signals": 3},
            {"entity_type": "client", "entity_id": "c2", "health_score": 50, "warning_signals": 1},
            {"entity_type": "client", "entity_id": "c3", "health_score": 90},
        ]
        dist = scorer.get_priority_distribution(entities)
        assert sum(dist.values()) == 3
        assert dist["critical"] >= 0
        assert dist["low"] >= 0
