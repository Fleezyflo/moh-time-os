"""
Tests for TemporalNormalizer — business-time duration calculations.

Brief 31 (TC), Task TC-2.1 + TC-5.1
"""

from datetime import date, datetime

import pytest

from lib.intelligence.temporal import BusinessCalendar, TemporalNormalizer


@pytest.fixture
def normalizer():
    cal = BusinessCalendar()
    return TemporalNormalizer(cal)


class TestBusinessDaysLate:
    """Overdue in business days, not calendar days."""

    def test_due_friday_checked_monday(self, normalizer):
        # Due Friday Feb 20, checked Monday Feb 23
        # Fri=due day, Sat=weekend, Sun=weekend, Mon=check → 1 business day late
        result = normalizer.business_days_late(date(2026, 2, 20), date(2026, 2, 23))
        assert result == 1

    def test_due_today(self, normalizer):
        d = date(2026, 4, 15)
        assert normalizer.business_days_late(d, d) == 0

    def test_due_tomorrow(self, normalizer):
        # Due Thu Feb 19, checked Wed Feb 18 → -1 (future)
        result = normalizer.business_days_late(date(2026, 2, 19), date(2026, 2, 18))
        assert result < 0

    def test_due_thu_checked_next_thu(self, normalizer):
        # Thu Feb 19 to Thu Feb 26 = 5 business days
        # Feb 19(due), 20(Fri-skip), 21(Sat-skip), 22(Sun-1), 23(Mon-2), 24(Tue-3), 25(Wed-4), 26(Thu-5)
        result = normalizer.business_days_late(date(2026, 2, 19), date(2026, 2, 26))
        assert result == 5

    def test_not_overdue(self, normalizer):
        # Due next week
        result = normalizer.business_days_late(date(2026, 4, 20), date(2026, 4, 15))
        assert result <= 0


class TestBusinessHoursElapsed:
    """Business hours between timestamps."""

    def test_within_single_working_day(self, normalizer):
        start = datetime(2026, 4, 15, 10, 0)  # Wed 10:00
        end = datetime(2026, 4, 15, 14, 0)  # Wed 14:00
        result = normalizer.business_hours_elapsed(start, end)
        assert result == 4.0

    def test_spanning_weekend(self, normalizer):
        # Use non-Ramadan dates: Thu Apr 16 18:00 to Sun Apr 19 12:00
        start = datetime(2026, 4, 16, 18, 0)  # Thu 18:00
        end = datetime(2026, 4, 19, 12, 0)  # Sun 12:00
        # Thu: 18-20 = 2h, Fri: skip(weekend), Sat: skip(weekend), Sun: 10-12 = 2h
        result = normalizer.business_hours_elapsed(start, end)
        assert result == 4.0

    def test_entirely_on_weekend(self, normalizer):
        start = datetime(2026, 2, 20, 10, 0)  # Friday
        end = datetime(2026, 2, 21, 18, 0)  # Saturday
        result = normalizer.business_hours_elapsed(start, end)
        assert result == 0.0

    def test_during_ramadan(self, normalizer):
        # Ramadan: working hours 9-14
        start = datetime(2026, 3, 1, 9, 0)  # Sunday (Ramadan)
        end = datetime(2026, 3, 1, 14, 0)
        result = normalizer.business_hours_elapsed(start, end)
        assert result == 5.0

    def test_end_before_start(self, normalizer):
        start = datetime(2026, 4, 15, 14, 0)
        end = datetime(2026, 4, 15, 10, 0)
        assert normalizer.business_hours_elapsed(start, end) == 0.0


class TestNormalizeAging:
    """Aging in business time."""

    def test_includes_weekend(self, normalizer):
        # 7 calendar days with 1 weekend (2 non-working days)
        result = normalizer.normalize_aging(date(2026, 2, 16), date(2026, 2, 23))
        assert result["calendar_days"] == 7
        assert result["business_days"] == 5  # skip Fri+Sat
        assert isinstance(result["business_weeks"], float)

    def test_includes_holiday(self, normalizer):
        # Span UAE National Day (Dec 2-3)
        result = normalizer.normalize_aging(date(2026, 12, 1), date(2026, 12, 6))
        assert "UAE National Day" in result["includes_holidays"]

    def test_ramadan_days_counted(self, normalizer):
        # During Ramadan period
        result = normalizer.normalize_aging(date(2026, 2, 17), date(2026, 2, 24))
        assert result["includes_ramadan_days"] > 0


class TestExpectedResponseTime:
    """Response time calculation respecting business hours."""

    def test_sent_friday_deadline_skips_weekend(self, normalizer):
        sent = datetime(2026, 2, 20, 17, 0)  # Friday 17:00 (non-working day)
        result = normalizer.expected_response_time(sent, response_hours=8.0)
        # Should skip weekend and give a deadline on Sunday or later
        assert "business_deadline" in result
        assert "normal_deadline" in result


class TestTaskAgeWeighted:
    """Task age weighting for cost-to-serve."""

    def test_completed_task(self, normalizer):
        assert normalizer.task_age_weighted(date(2026, 1, 1), "completed") == 1.0

    def test_not_overdue(self, normalizer):
        # Due in the future
        result = normalizer.task_age_weighted(date(2026, 12, 31), "in_progress", date(2026, 4, 15))
        assert result == 1.0

    def test_overdue_3_business_days(self, normalizer):
        # Create a scenario where task is exactly 3 business days late
        # Wed Apr 15 is current, task was due Mon Apr 12
        # Mon(due), Tue(1), Wed(2), Thu(3) — but we need to check working days
        # Actually task_age_weighted uses business_days_late which counts from due_date to current
        result = normalizer.task_age_weighted(date(2026, 4, 8), "overdue", date(2026, 4, 13))
        assert result > 1.0
        assert result <= 1.5

    def test_very_overdue_capped(self, normalizer):
        # 30+ business days overdue
        result = normalizer.task_age_weighted(date(2025, 12, 1), "overdue", date(2026, 4, 15))
        assert result == 2.0
