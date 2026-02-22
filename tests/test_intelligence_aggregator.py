"""
Tests for IntelligenceAggregator — cross-entity intelligence synthesis.

Brief 26 (IA), Task IA-1.1
"""

import pytest

from lib.intelligence.intelligence_aggregator import (
    CascadingRisk,
    EntityIntelligenceSummary,
    IntelligenceAggregator,
    PortfolioRollup,
    classify_health,
    determine_trend,
)


@pytest.fixture
def aggregator():
    return IntelligenceAggregator()


class TestClassifyHealth:
    def test_excellent(self):
        assert classify_health(85) == "excellent"

    def test_good(self):
        assert classify_health(70) == "good"

    def test_fair(self):
        assert classify_health(55) == "fair"

    def test_poor(self):
        assert classify_health(40) == "poor"

    def test_critical(self):
        assert classify_health(20) == "critical"


class TestDetermineTrend:
    def test_rising(self):
        assert determine_trend([3.0, 4.0, 5.0]) == "rising"

    def test_declining(self):
        assert determine_trend([-3.0, -4.0, -5.0]) == "declining"

    def test_stable(self):
        assert determine_trend([0.5, -0.5, 0.3]) == "stable"

    def test_volatile(self):
        # Avg near zero but huge spread → volatile
        assert determine_trend([8.0, -8.0, 1.0]) == "volatile"

    def test_empty(self):
        assert determine_trend([]) == "stable"


class TestBuildEntitySummary:
    def test_basic(self, aggregator):
        summary = aggregator.build_entity_summary(
            entity_type="client",
            entity_id="c1",
            health_score=75.0,
            signals=[
                {"severity": "CRITICAL", "evidence_text": "overdue invoices"},
                {"severity": "WARNING", "evidence_text": "low engagement"},
            ],
            trajectory_velocity=-3.0,
        )
        assert summary.entity_type == "client"
        assert summary.health_classification == "good"
        assert summary.critical_signal_count == 1
        assert summary.warning_signal_count == 1
        assert summary.trend_direction == "declining"
        assert len(summary.top_risks) == 2

    def test_no_signals(self, aggregator):
        summary = aggregator.build_entity_summary(
            entity_type="project",
            entity_id="p1",
            health_score=90.0,
        )
        assert summary.active_signal_count == 0
        assert summary.critical_signal_count == 0
        assert summary.health_classification == "excellent"
        assert summary.trend_direction == "stable"

    def test_to_dict(self, aggregator):
        summary = aggregator.build_entity_summary(
            entity_type="client",
            entity_id="c1",
            health_score=50.0,
        )
        d = summary.to_dict()
        assert "entity_type" in d
        assert "health_classification" in d
        assert "top_risks" in d


class TestDetectCascadingRisks:
    def test_detects_cascade(self, aggregator):
        summaries = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                critical_signal_count=2,
                health_score=30,
            ),
            EntityIntelligenceSummary(
                entity_type="project",
                entity_id="p1",
                health_score=60,
            ),
        ]
        relationships = [
            {
                "source_type": "client",
                "source_id": "c1",
                "target_type": "project",
                "target_id": "p1",
                "relationship": "owns",
            },
        ]
        risks = aggregator.detect_cascading_risks(summaries, relationships)
        assert len(risks) == 1
        assert risks[0].severity == "critical"
        assert len(risks[0].affected_entities) == 1

    def test_no_cascade_without_relationships(self, aggregator):
        summaries = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                critical_signal_count=1,
            ),
        ]
        risks = aggregator.detect_cascading_risks(summaries)
        assert len(risks) == 0

    def test_compounding_impact(self, aggregator):
        summaries = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                critical_signal_count=1,
                health_score=25,
            ),
            EntityIntelligenceSummary(
                entity_type="project",
                entity_id="p1",
                health_score=40,
            ),
        ]
        relationships = [
            {
                "source_type": "client",
                "source_id": "c1",
                "target_type": "project",
                "target_id": "p1",
                "relationship": "owns",
            },
        ]
        risks = aggregator.detect_cascading_risks(summaries, relationships)
        assert risks[0].affected_entities[0]["impact"] == "compounding"


class TestBuildPortfolioRollup:
    def test_basic_rollup(self, aggregator):
        summaries = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                health_score=85,
                active_signal_count=0,
                critical_signal_count=0,
                trend_direction="rising",
            ),
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c2",
                health_score=35,
                active_signal_count=2,
                critical_signal_count=1,
                trend_direction="declining",
            ),
            EntityIntelligenceSummary(
                entity_type="project",
                entity_id="p1",
                health_score=70,
                active_signal_count=1,
                critical_signal_count=0,
            ),
        ]
        rollup = aggregator.build_portfolio_rollup(summaries)
        assert rollup.total_clients == 2
        assert rollup.total_projects == 1
        assert rollup.avg_client_health == pytest.approx(60.0)
        assert rollup.total_active_signals == 3
        assert rollup.total_critical_signals == 1
        assert rollup.entities_declining == 1
        assert rollup.entities_rising == 1
        assert "client:c2" in rollup.attention_required

    def test_empty_rollup(self, aggregator):
        rollup = aggregator.build_portfolio_rollup([])
        assert rollup.total_clients == 0
        assert rollup.avg_client_health == 0.0

    def test_health_distribution(self, aggregator):
        summaries = [
            EntityIntelligenceSummary(entity_type="client", entity_id="c1", health_score=90),
            EntityIntelligenceSummary(entity_type="client", entity_id="c2", health_score=70),
            EntityIntelligenceSummary(entity_type="client", entity_id="c3", health_score=30),
        ]
        rollup = aggregator.build_portfolio_rollup(summaries)
        assert rollup.health_distribution["excellent"] == 1
        assert rollup.health_distribution["good"] == 1
        assert rollup.health_distribution["critical"] == 1

    def test_to_dict(self, aggregator):
        rollup = aggregator.build_portfolio_rollup([])
        d = rollup.to_dict()
        assert "generated_at" in d
        assert "cascading_risks" in d


class TestComparePeriods:
    def test_detects_improvement(self, aggregator):
        current = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                health_score=80,
                health_classification="excellent",
            ),
        ]
        previous = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                health_score=50,
                health_classification="fair",
            ),
        ]
        result = aggregator.compare_periods(current, previous)
        assert result["improved_count"] == 1
        assert result["degraded_count"] == 0
        assert result["portfolio_health_delta"] == 30.0

    def test_detects_degradation(self, aggregator):
        current = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                health_score=30,
                health_classification="critical",
            ),
        ]
        previous = [
            EntityIntelligenceSummary(
                entity_type="client",
                entity_id="c1",
                health_score=70,
                health_classification="good",
            ),
        ]
        result = aggregator.compare_periods(current, previous)
        assert result["degraded_count"] == 1
        assert result["portfolio_health_delta"] == -40.0

    def test_new_and_removed(self, aggregator):
        current = [
            EntityIntelligenceSummary(entity_type="client", entity_id="c2", health_score=60),
        ]
        previous = [
            EntityIntelligenceSummary(entity_type="client", entity_id="c1", health_score=60),
        ]
        result = aggregator.compare_periods(current, previous)
        assert "client:c2" in result["new_entities"]
        assert "client:c1" in result["removed_entities"]
