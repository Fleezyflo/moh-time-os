"""
Tests for RevenueAnalytics — revenue trends and financial intelligence.

Brief 15 (BI), Task BI-1.1
"""

import pytest

from lib.intelligence.revenue_analytics import (
    RevenueAnalytics,
    classify_tier,
    compute_hhi,
    compute_revenue_trend,
    simple_linear_projection,
)


class TestClassifyTier:
    def test_platinum(self):
        assert classify_tier(50000) == "platinum"

    def test_gold(self):
        assert classify_tier(20000) == "gold"

    def test_silver(self):
        assert classify_tier(8000) == "silver"

    def test_bronze(self):
        assert classify_tier(3000) == "bronze"

    def test_zero(self):
        assert classify_tier(0) == "bronze"


class TestComputeRevenueTrend:
    def test_growing(self):
        direction, pct = compute_revenue_trend([10000, 12000])
        assert direction == "growing"
        assert pct == pytest.approx(20.0)

    def test_declining(self):
        direction, pct = compute_revenue_trend([12000, 10000])
        assert direction == "declining"
        assert pct < -5

    def test_stable(self):
        direction, pct = compute_revenue_trend([10000, 10200])
        assert direction == "stable"

    def test_single_value(self):
        direction, pct = compute_revenue_trend([10000])
        assert direction == "stable"
        assert pct == 0.0


class TestComputeHHI:
    def test_perfectly_concentrated(self):
        assert compute_hhi([1.0]) == pytest.approx(1.0)

    def test_evenly_distributed(self):
        # 4 equal clients: 4 × 0.25² = 0.25
        hhi = compute_hhi([0.25, 0.25, 0.25, 0.25])
        assert hhi == pytest.approx(0.25)

    def test_empty(self):
        assert compute_hhi([]) == 0.0


class TestSimpleLinearProjection:
    def test_increasing(self):
        proj = simple_linear_projection([10, 20, 30], periods_ahead=1)
        assert proj == pytest.approx(40.0)

    def test_decreasing(self):
        proj = simple_linear_projection([30, 20, 10], periods_ahead=1)
        assert proj == pytest.approx(0.0)  # Clamped to 0

    def test_single_value(self):
        assert simple_linear_projection([100]) == 100.0


@pytest.fixture
def analytics():
    return RevenueAnalytics()


class TestAnalyzeClientRevenue:
    def test_growing_client(self, analytics):
        trend = analytics.analyze_client_revenue(
            entity_id="c1",
            monthly_revenues=[10000, 12000, 15000],
        )
        assert trend.current_monthly == 15000
        assert trend.trend_direction == "growing"
        assert trend.tier == "gold"
        assert trend.trailing_3m_avg == pytest.approx(12333.33, abs=1)

    def test_declining_client(self, analytics):
        trend = analytics.analyze_client_revenue(
            entity_id="c2",
            monthly_revenues=[20000, 15000, 10000],
        )
        assert trend.trend_direction == "declining"
        assert trend.monthly_change < 0

    def test_empty_revenues(self, analytics):
        trend = analytics.analyze_client_revenue(entity_id="c3")
        assert trend.current_monthly == 0.0
        assert trend.tier == "bronze"

    def test_to_dict(self, analytics):
        trend = analytics.analyze_client_revenue(
            entity_id="c1",
            monthly_revenues=[10000, 12000],
        )
        d = trend.to_dict()
        assert "tier" in d
        assert "trend_direction" in d


class TestForecastProfitability:
    def test_basic_forecast(self, analytics):
        forecast = analytics.forecast_profitability(
            entity_id="c1",
            monthly_revenues=[10000, 12000, 14000],
            monthly_costs=[6000, 7000, 8000],
        )
        assert forecast.current_margin_pct == pytest.approx(42.86, abs=0.1)
        assert forecast.revenue_projection > 14000
        assert forecast.confidence > 0

    def test_low_margin_risk(self, analytics):
        forecast = analytics.forecast_profitability(
            entity_id="c1",
            monthly_revenues=[10000, 10000, 10000],
            monthly_costs=[8500, 8500, 8500],
        )
        assert "low current margin" in forecast.risk_factors

    def test_empty_data(self, analytics):
        forecast = analytics.forecast_profitability(
            entity_id="c1",
            monthly_revenues=[],
            monthly_costs=[],
        )
        assert forecast.current_margin_pct == 0.0

    def test_to_dict(self, analytics):
        forecast = analytics.forecast_profitability(
            entity_id="c1",
            monthly_revenues=[10000, 12000],
            monthly_costs=[6000, 7000],
        )
        d = forecast.to_dict()
        assert "projected_margin_pct" in d
        assert "risk_factors" in d


class TestPortfolioFinancials:
    def test_basic_portfolio(self, analytics):
        clients = [
            {
                "entity_id": "c1",
                "monthly_revenue": 30000,
                "monthly_cost": 15000,
                "health_score": 80,
                "trend_direction": "growing",
            },
            {
                "entity_id": "c2",
                "monthly_revenue": 10000,
                "monthly_cost": 7000,
                "health_score": 40,
                "trend_direction": "declining",
            },
        ]
        pf = analytics.compute_portfolio_financials(clients)
        assert pf.total_monthly_revenue == 40000
        assert pf.total_monthly_cost == 22000
        assert pf.portfolio_margin_pct == pytest.approx(45.0)
        assert pf.tier_distribution["platinum"] == 1
        assert pf.tier_distribution["silver"] == 1
        assert pf.at_risk_revenue == 10000
        assert pf.growing_revenue == 30000

    def test_empty_portfolio(self, analytics):
        pf = analytics.compute_portfolio_financials([])
        assert pf.total_monthly_revenue == 0.0

    def test_concentration(self, analytics):
        clients = [
            {"entity_id": "c1", "monthly_revenue": 90000, "monthly_cost": 50000},
            {"entity_id": "c2", "monthly_revenue": 10000, "monthly_cost": 5000},
        ]
        pf = analytics.compute_portfolio_financials(clients)
        assert pf.revenue_concentration_hhi > 0.5  # Very concentrated
        assert pf.top_client_revenue_pct == 90.0

    def test_to_dict(self, analytics):
        pf = analytics.compute_portfolio_financials([])
        d = pf.to_dict()
        assert "tier_distribution" in d
        assert "revenue_concentration_hhi" in d


class TestRevenueAlerts:
    def test_concentration_alert(self, analytics):
        clients = [
            {"entity_id": "c1", "monthly_revenue": 90000, "monthly_cost": 50000},
            {"entity_id": "c2", "monthly_revenue": 10000, "monthly_cost": 5000},
        ]
        alerts = analytics.get_revenue_alerts(clients)
        types = [a["type"] for a in alerts]
        assert "concentration_risk" in types

    def test_at_risk_revenue_alert(self, analytics):
        clients = [
            {
                "entity_id": "c1",
                "monthly_revenue": 30000,
                "monthly_cost": 15000,
                "health_score": 30,
                "trend_direction": "declining",
            },
            {
                "entity_id": "c2",
                "monthly_revenue": 10000,
                "monthly_cost": 5000,
                "health_score": 80,
                "trend_direction": "stable",
            },
        ]
        alerts = analytics.get_revenue_alerts(clients)
        types = [a["type"] for a in alerts]
        assert "at_risk_revenue" in types

    def test_no_alerts_healthy_portfolio(self, analytics):
        clients = [
            {
                "entity_id": "c1",
                "monthly_revenue": 20000,
                "monthly_cost": 10000,
                "health_score": 80,
                "trend_direction": "growing",
            },
            {
                "entity_id": "c2",
                "monthly_revenue": 20000,
                "monthly_cost": 10000,
                "health_score": 75,
                "trend_direction": "stable",
            },
            {
                "entity_id": "c3",
                "monthly_revenue": 20000,
                "monthly_cost": 10000,
                "health_score": 70,
                "trend_direction": "growing",
            },
        ]
        alerts = analytics.get_revenue_alerts(clients)
        # Should be minimal alerts with balanced, healthy portfolio
        critical_alerts = [a for a in alerts if a["severity"] == "critical"]
        assert len(critical_alerts) == 0
