"""
Tests for BusinessCalendar — UAE/Dubai temporal context engine.

Brief 31 (TC), Task TC-1.1 + TC-5.1
"""

from datetime import date

import pytest

from lib.intelligence.temporal import BusinessCalendar, DayType


@pytest.fixture
def cal():
    """BusinessCalendar loaded from project config."""
    return BusinessCalendar()


class TestWeekend:
    """UAE weekend = Friday + Saturday."""

    def test_friday_is_weekend(self, cal):
        # 2026-02-20 is a Friday
        assert cal.is_weekend(date(2026, 2, 20)) is True

    def test_saturday_is_weekend(self, cal):
        # 2026-02-21 is a Saturday
        assert cal.is_weekend(date(2026, 2, 21)) is True

    def test_sunday_is_not_weekend(self, cal):
        # 2026-02-22 is a Sunday
        assert cal.is_weekend(date(2026, 2, 22)) is False

    def test_thursday_is_not_weekend(self, cal):
        assert cal.is_weekend(date(2026, 2, 19)) is False

    def test_monday_is_not_weekend(self, cal):
        assert cal.is_weekend(date(2026, 2, 23)) is False

    def test_weekend_not_working_day(self, cal):
        assert cal.is_working_day(date(2026, 2, 20)) is False  # Friday
        assert cal.is_working_day(date(2026, 2, 21)) is False  # Saturday


class TestPublicHolidays:
    """Fixed UAE public holidays."""

    def test_uae_national_day(self, cal):
        assert cal.is_public_holiday(date(2026, 12, 2)) is True

    def test_uae_national_day_2(self, cal):
        assert cal.is_public_holiday(date(2026, 12, 3)) is True

    def test_new_years(self, cal):
        assert cal.is_public_holiday(date(2026, 1, 1)) is True

    def test_commemoration_day(self, cal):
        assert cal.is_public_holiday(date(2026, 11, 30)) is True

    def test_holiday_is_not_working_day(self, cal):
        assert cal.is_working_day(date(2026, 12, 2)) is False

    def test_normal_day_not_holiday(self, cal):
        assert cal.is_public_holiday(date(2026, 3, 15)) is False


class TestRamadan:
    """Ramadan period detection and working hours."""

    def test_ramadan_2026_start(self, cal):
        assert cal.is_ramadan(date(2026, 2, 17)) is True

    def test_ramadan_2026_mid(self, cal):
        assert cal.is_ramadan(date(2026, 3, 1)) is True

    def test_ramadan_2026_end(self, cal):
        assert cal.is_ramadan(date(2026, 3, 19)) is True

    def test_not_ramadan(self, cal):
        assert cal.is_ramadan(date(2026, 5, 1)) is False

    def test_ramadan_day_number(self, cal):
        ctx = cal.get_day_context(date(2026, 2, 18))
        assert ctx.is_ramadan is True
        assert ctx.ramadan_day == 2  # Feb 17 is day 1

    def test_get_ramadan_dates(self, cal):
        r = cal.get_ramadan_dates(2026)
        assert r is not None
        assert r[0] == date(2026, 2, 17)
        assert r[1] == date(2026, 3, 19)

    def test_ramadan_unknown_year(self, cal):
        assert cal.get_ramadan_dates(2050) is None

    def test_ramadan_working_hours(self, cal):
        # During Ramadan, working hours are 9-14
        d = date(2026, 3, 1)  # Ramadan, Sunday (working day)
        assert cal.get_working_hours(d) == (9, 14)

    def test_ramadan_working_minutes(self, cal):
        d = date(2026, 3, 1)  # Ramadan working day
        assert cal.get_working_minutes(d) == 300  # 5 hours × 60


class TestEid:
    """Eid period detection."""

    def test_eid_al_fitr_2026(self, cal):
        assert cal.is_eid(date(2026, 3, 20)) is True
        assert cal.is_eid(date(2026, 3, 22)) is True

    def test_eid_al_adha_2026(self, cal):
        assert cal.is_eid(date(2026, 5, 27)) is True

    def test_eid_is_not_working_day(self, cal):
        assert cal.is_working_day(date(2026, 3, 20)) is False

    def test_eid_name(self, cal):
        ctx = cal.get_day_context(date(2026, 3, 20))
        assert ctx.is_eid is True
        assert ctx.eid_name == "Eid al-Fitr"


class TestWorkingHours:
    """Working hours and minutes by context."""

    def test_normal_day_hours(self, cal):
        d = date(2026, 4, 15)  # Wednesday, normal
        assert cal.get_working_hours(d) == (10, 20)

    def test_normal_day_minutes(self, cal):
        assert cal.get_working_minutes(date(2026, 4, 15)) == 600  # 10h × 60

    def test_weekend_hours(self, cal):
        assert cal.get_working_hours(date(2026, 2, 20)) == (0, 0)  # Friday

    def test_weekend_minutes(self, cal):
        assert cal.get_working_minutes(date(2026, 2, 20)) == 0

    def test_holiday_hours(self, cal):
        assert cal.get_working_hours(date(2026, 12, 2)) == (0, 0)

    def test_holiday_minutes(self, cal):
        assert cal.get_working_minutes(date(2026, 12, 2)) == 0


class TestSeasons:
    """Season classification."""

    def test_q4_close(self, cal):
        assert cal.get_season(date(2026, 12, 1)) == "q4_close"
        assert cal.get_season(date(2026, 11, 20)) == "q4_close"

    def test_summer_slowdown(self, cal):
        assert cal.get_season(date(2026, 7, 15)) == "summer_slowdown"
        assert cal.get_season(date(2026, 8, 1)) == "summer_slowdown"

    def test_normal_season(self, cal):
        assert cal.get_season(date(2026, 4, 15)) == "normal"
        assert cal.get_season(date(2026, 10, 1)) == "normal"


class TestBusinessDays:
    """Business day calculations."""

    def test_business_days_skip_weekend(self, cal):
        # Thu Feb 19 to Mon Feb 23 = Thu(1), Fri(skip), Sat(skip), Sun(1), Mon(excl) = 2
        # Actually: Thu is 1 working day, Sun is 1, Mon excluded = 2
        result = cal.business_days_between(date(2026, 2, 19), date(2026, 2, 23))
        # Thu=working(1), Fri=weekend, Sat=weekend, Sun=working(1) = 2
        assert result == 2

    def test_business_days_same_day(self, cal):
        assert cal.business_days_between(date(2026, 2, 19), date(2026, 2, 19)) == 0

    def test_business_days_next_day_working(self, cal):
        # Wed to Thu = 1
        assert cal.business_days_between(date(2026, 2, 18), date(2026, 2, 19)) == 1

    def test_business_days_skip_holiday(self, cal):
        # Dec 1 (Tue) to Dec 4 (Fri)
        # Dec 1 = working(1), Dec 2 = holiday(skip), Dec 3 = holiday(skip), Dec 4 excluded
        result = cal.business_days_between(date(2026, 12, 1), date(2026, 12, 4))
        # Dec 1=Tue(working), Dec 2=Wed(holiday), Dec 3=Thu(holiday) = 1
        assert result == 1

    def test_add_business_days(self, cal):
        # Wed Feb 18 + 3 business days
        # Thu=1, Fri=skip, Sat=skip, Sun=2, Mon=3 → Feb 23
        result = cal.add_business_days(date(2026, 2, 18), 3)
        assert result == date(2026, 2, 23)

    def test_add_business_days_zero(self, cal):
        result = cal.add_business_days(date(2026, 2, 18), 0)
        assert result == date(2026, 2, 18)

    def test_negative_business_days(self, cal):
        # Reverse direction
        result = cal.business_days_between(date(2026, 2, 23), date(2026, 2, 19))
        assert result == -2


class TestDayContext:
    """Full day context."""

    def test_normal_working_day(self, cal):
        ctx = cal.get_day_context(date(2026, 4, 15))  # Wednesday
        assert ctx.day_type == DayType.WORKING
        assert ctx.is_working_day is True
        assert ctx.is_weekend is False
        assert ctx.is_ramadan is False
        assert ctx.season == "normal"

    def test_ramadan_working_day(self, cal):
        ctx = cal.get_day_context(date(2026, 3, 1))  # Sunday during Ramadan
        assert ctx.is_working_day is True
        assert ctx.is_ramadan is True
        assert ctx.working_hours == (9, 14)
        assert ctx.working_minutes == 300

    def test_weekend_context(self, cal):
        ctx = cal.get_day_context(date(2026, 2, 20))  # Friday
        assert ctx.day_type == DayType.WEEKEND
        assert ctx.is_working_day is False
        assert ctx.working_minutes == 0

    def test_eid_context(self, cal):
        ctx = cal.get_day_context(date(2026, 3, 20))  # Eid al-Fitr
        assert ctx.day_type == DayType.RELIGIOUS_OBSERVANCE
        assert ctx.is_eid is True
        assert ctx.is_working_day is False
