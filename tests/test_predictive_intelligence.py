"""
Tests for PredictiveIntelligence — forecasting and early warnings.

Brief 24 (PI), Task PI-1.1
"""

import pytest

from lib.intelligence.predictive_intelligence import (
    PredictiveIntelligence,
    detect_decline_pattern,
    estimate_churn_probability,
    linear_forecast,
)


class TestLinearForecast:
    def test_increasing_trend(self):
        # Add slight noise so residual SE > 0 (perfect data yields zero-width CI)
        projected, lower, upper = linear_forecast([60, 66, 69, 76, 80], 1)
        assert projected > 80
        assert lower < projected
        assert upper > projected

    def test_single_value(self):
        projected, lower, upper = linear_forecast([50], 1)
        assert projected == 50.0

    def test_empty(self):
        projected, _, _ = linear_forecast([], 1)
        assert projected == 50.0  # default


class TestDetectDeclinePattern:
    def test_consistent_decline(self):
        assert detect_decline_pattern([80, 75, 70, 65, 60]) is True

    def test_stable_scores(self):
        assert detect_decline_pattern([70, 71, 69, 70, 72]) is False

    def test_too_few_values(self):
        assert detect_decline_pattern([70, 65]) is False


class TestEstimateChurnProbability:
    def test_high_risk(self):
        prob = estimate_churn_probability(
            health_score=25,
            trend_velocity=-8.0,
            days_since_contact=30,
            signal_count=3,
        )
        assert prob > 0.5

    def test_low_risk(self):
        prob = estimate_churn_probability(
            health_score=85,
            trend_velocity=2.0,
            days_since_contact=3,
            signal_count=0,
        )
        assert prob < 0.1

    def test_moderate_risk(self):
        prob = estimate_churn_probability(
            health_score=45,
            trend_velocity=-3.0,
            days_since_contact=20,
            signal_count=1,
        )
        assert 0.1 < prob < 0.7


@pytest.fixture
def pi():
    return PredictiveIntelligence()


class TestForecastHealth:
    def test_declining_forecast(self, pi):
        forecast = pi.forecast_health(
            "client",
            "c1",
            [80, 75, 70, 65, 60],
            periods_ahead=7,
        )
        assert forecast.projected_score < 60
        assert forecast.trend == "declining"
        assert forecast.confidence > 0

    def test_stable_forecast(self, pi):
        forecast = pi.forecast_health(
            "client",
            "c1",
            [70, 71, 69, 70, 72],
            periods_ahead=7,
        )
        assert forecast.trend == "stable"

    def test_to_dict(self, pi):
        forecast = pi.forecast_health("client", "c1", [70, 72, 74])
        d = forecast.to_dict()
        assert "projected_score" in d
        assert "confidence" in d


class TestGenerateEarlyWarnings:
    def test_health_decline_warning(self, pi):
        warnings = pi.generate_early_warnings(
            "client",
            "c1",
            health_scores=[80, 75, 70, 65, 60],
        )
        types = [w.warning_type for w in warnings]
        assert "health_decline" in types

    def test_churn_risk_warning(self, pi):
        warnings = pi.generate_early_warnings(
            "client",
            "c1",
            health_scores=[40],
            trend_velocity=-5.0,
            days_since_contact=25,
            signal_count=2,
        )
        types = [w.warning_type for w in warnings]
        assert "churn_risk" in types

    def test_revenue_decline_warning(self, pi):
        warnings = pi.generate_early_warnings(
            "client",
            "c1",
            monthly_revenue=20000,
            revenue_trend="declining",
        )
        types = [w.warning_type for w in warnings]
        assert "revenue_drop" in types

    def test_no_warnings_healthy(self, pi):
        warnings = pi.generate_early_warnings(
            "client",
            "c1",
            health_scores=[80, 82, 81, 83],
            trend_velocity=1.0,
            days_since_contact=3,
        )
        assert len(warnings) == 0


class TestGenerateRecommendations:
    def test_churn_recommendation(self, pi):
        from lib.intelligence.predictive_intelligence import EarlyWarning

        warnings = [
            EarlyWarning(
                "client",
                "c1",
                "churn_risk",
                "High churn risk",
                probability=0.6,
                time_horizon_days=30,
            ),
        ]
        recs = pi.generate_recommendations("client", "c1", warnings)
        assert len(recs) >= 1
        assert recs[0].urgency == "immediate"

    def test_staleness_recommendation(self, pi):
        recs = pi.generate_recommendations(
            "client",
            "c1",
            [],
            health_score=45,
            days_since_review=30,
        )
        assert len(recs) == 1
        assert "overdue" in recs[0].recommendation.lower()

    def test_to_dict(self, pi):
        recs = pi.generate_recommendations(
            "client",
            "c1",
            [],
            health_score=40,
            days_since_review=25,
        )
        if recs:
            d = recs[0].to_dict()
            assert "recommendation" in d
            assert "urgency" in d
