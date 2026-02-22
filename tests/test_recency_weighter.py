"""
Tests for RecencyWeighter — exponential decay weighting with business days.

Brief 31 (TC), Task TC-3.1 + TC-5.1
"""

from datetime import date

import pytest

from lib.intelligence.temporal import BusinessCalendar, RecencyWeighter


@pytest.fixture
def weighter():
    cal = BusinessCalendar()
    return RecencyWeighter(cal, half_life_days=14, min_weight=0.05)


class TestComputeWeight:
    """Exponential decay weight calculation."""

    def test_today_weight_is_one(self, weighter):
        ref = date(2026, 4, 15)
        assert weighter.compute_weight(ref, ref) == 1.0

    def test_future_date_weight_is_one(self, weighter):
        ref = date(2026, 4, 15)
        assert weighter.compute_weight(date(2026, 4, 20), ref) == 1.0

    def test_half_life_weight(self, weighter):
        # 14 business days ago should be ~0.5
        ref = date(2026, 4, 15)  # Wednesday
        # Go back ~3 calendar weeks (14 business days)
        past = weighter.calendar.add_business_days(ref, -14)
        w = weighter.compute_weight(past, ref)
        assert abs(w - 0.5) < 0.01

    def test_double_half_life_weight(self, weighter):
        # 28 business days ago should be ~0.25
        ref = date(2026, 4, 15)
        past = weighter.calendar.add_business_days(ref, -28)
        w = weighter.compute_weight(past, ref)
        assert abs(w - 0.25) < 0.02

    def test_weight_floors_at_min(self, weighter):
        # Very old date — should floor at min_weight
        w = weighter.compute_weight(date(2020, 1, 1), date(2026, 4, 15))
        assert w == weighter.min_weight


class TestWeightedAverage:
    """Recency-weighted averaging."""

    def test_identical_values(self, weighter):
        points = [(date(2026, 4, 10), 75.0), (date(2026, 4, 15), 75.0)]
        assert weighter.weighted_average(points, date(2026, 4, 15)) == pytest.approx(75.0)

    def test_recent_data_weighted_higher(self, weighter):
        # Old data = 90, recent data = 60
        # Weighted average should be closer to 60 (recent)
        ref = date(2026, 4, 15)
        old = weighter.calendar.add_business_days(ref, -28)
        points = [(old, 90.0), (ref, 60.0)]
        avg = weighter.weighted_average(points, ref)
        assert avg < 75.0  # Closer to 60 than to 75 (simple mean)
        assert avg > 60.0  # But not exactly 60

    def test_empty_data(self, weighter):
        assert weighter.weighted_average([], date(2026, 4, 15)) == 0.0


class TestWeightedTrend:
    """Recency-weighted trend analysis."""

    def test_increasing_recent_scores(self, weighter):
        ref = date(2026, 4, 15)
        # Generate increasing scores over 10 business days
        points = []
        for i in range(10):
            d = weighter.calendar.add_business_days(ref, -(9 - i))
            points.append((d, 50.0 + i * 5))  # 50, 55, 60, ..., 95
        result = weighter.weighted_trend(points, ref)
        assert result["direction"] == "improving"
        assert result["slope"] > 0

    def test_flat_data(self, weighter):
        ref = date(2026, 4, 15)
        points = []
        for i in range(5):
            d = weighter.calendar.add_business_days(ref, -(4 - i))
            points.append((d, 70.0))
        result = weighter.weighted_trend(points, ref)
        assert result["direction"] == "stable"

    def test_declining_recent_with_good_old(self, weighter):
        ref = date(2026, 4, 15)
        points = []
        # Old good scores
        for i in range(5):
            d = weighter.calendar.add_business_days(ref, -(20 - i))
            points.append((d, 85.0))
        # Recent bad scores
        for i in range(5):
            d = weighter.calendar.add_business_days(ref, -(4 - i))
            points.append((d, 50.0))
        result = weighter.weighted_trend(points, ref)
        assert result["recency_delta"] < 0  # Weighted mean < unweighted mean
        assert result["weighted_mean"] < result["unweighted_mean"]

    def test_single_point(self, weighter):
        ref = date(2026, 4, 15)
        result = weighter.weighted_trend([(ref, 70.0)], ref)
        assert result["direction"] == "stable"
        assert result["data_points"] == 1

    def test_empty_data(self, weighter):
        result = weighter.weighted_trend([], date(2026, 4, 15))
        assert result["data_points"] == 0
        assert result["direction"] == "stable"


class TestWeightedPercentile:
    """Recency-weighted percentile ranking."""

    def test_above_all(self, weighter):
        ref = date(2026, 4, 15)
        population = [(weighter.calendar.add_business_days(ref, -i), 50.0 + i) for i in range(10)]
        pct = weighter.weighted_percentile(100.0, population, ref)
        assert pct > 0.9

    def test_below_all(self, weighter):
        ref = date(2026, 4, 15)
        population = [(weighter.calendar.add_business_days(ref, -i), 50.0 + i) for i in range(10)]
        pct = weighter.weighted_percentile(0.0, population, ref)
        assert pct < 0.1

    def test_same_date_matches_unweighted(self, weighter):
        ref = date(2026, 4, 15)
        # All data from same date — weights are equal
        population = [(ref, v) for v in [40, 50, 60, 70, 80]]
        pct = weighter.weighted_percentile(60.0, population, ref)
        # Should be around 0.5 (median)
        assert 0.3 < pct < 0.7

    def test_empty_population(self, weighter):
        assert weighter.weighted_percentile(50.0, [], date(2026, 4, 15)) == 0.5
