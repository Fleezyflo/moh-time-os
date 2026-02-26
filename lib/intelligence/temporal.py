"""
Temporal Intelligence — Business calendar, normalization, and recency weighting.

Brief 31 (TC) — Temporal & Contextual Intelligence

Provides three core capabilities:
1. BusinessCalendar — Knows what kind of day any date is (working, weekend,
   holiday, Ramadan, season). UAE/Dubai specific.
2. TemporalNormalizer — Converts wall-clock durations to business-time.
   "3 days late" means 3 business days, not calendar days.
3. RecencyWeighter — Exponential decay weighting so recent data has more
   influence on scores and trends.

All temporal intelligence flows through this module. No other module should
do its own business-day math.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path

import yaml

from lib import paths

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

_DEFAULT_WEEKEND_DAYS = [4, 5]  # Friday, Saturday (UAE)
_DEFAULT_WORK_START = 10
_DEFAULT_WORK_END = 20
_DEFAULT_RAMADAN_START = 9
_DEFAULT_RAMADAN_END = 14


# =============================================================================
# DATA CLASSES
# =============================================================================


class DayType(Enum):
    """Classification of a calendar day."""

    WORKING = "working"
    WEEKEND = "weekend"
    PUBLIC_HOLIDAY = "public_holiday"
    RELIGIOUS_OBSERVANCE = "religious_observance"


@dataclass
class DayContext:
    """Complete temporal context for a single date."""

    date: date
    day_type: DayType
    is_working_day: bool
    is_weekend: bool
    is_public_holiday: bool
    holiday_name: str | None
    is_ramadan: bool
    ramadan_day: int | None  # Day 1-30 within Ramadan, or None
    is_eid: bool
    eid_name: str | None
    season: str  # "normal", "q4_close", "summer_slowdown"
    working_hours: tuple  # (start_hour, end_hour)
    working_minutes: int  # Available working minutes this day


# =============================================================================
# BUSINESS CALENDAR
# =============================================================================


class BusinessCalendar:
    """
    Central temporal context engine for Dubai/UAE business operations.

    Loads configuration from config/business_calendar.yaml. Falls back to
    hardcoded defaults if the config file is missing.
    """

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = paths.project_root() / "config" / "business_calendar.yaml"

        self._config = self._load_config(config_path)

        self._weekend_days: list[int] = self._config.get("weekend_days", _DEFAULT_WEEKEND_DAYS)

        wh = self._config.get("working_hours", {})
        normal = wh.get("normal", {})
        ramadan = wh.get("ramadan", {})
        self._normal_start: int = normal.get("start", _DEFAULT_WORK_START)
        self._normal_end: int = normal.get("end", _DEFAULT_WORK_END)
        self._ramadan_start: int = ramadan.get("start", _DEFAULT_RAMADAN_START)
        self._ramadan_end: int = ramadan.get("end", _DEFAULT_RAMADAN_END)

        # Build Ramadan lookup: year -> (start_date, end_date)
        self._ramadan_dates: dict[int, tuple[date, date]] = {}
        for year_str, dates in self._config.get("ramadan", {}).items():
            year = int(year_str)
            self._ramadan_dates[year] = (
                date.fromisoformat(dates["start"]),
                date.fromisoformat(dates["end"]),
            )

        # Build Eid lookup: year -> list of (name, start, end)
        self._eid_dates: dict[int, list[tuple[str, date, date]]] = {}
        for eid_name_key, eid_data in [
            ("Eid al-Fitr", self._config.get("eid_al_fitr", {})),
            ("Eid al-Adha", self._config.get("eid_al_adha", {})),
        ]:
            for year_str, dates in eid_data.items():
                year = int(year_str)
                if year not in self._eid_dates:
                    self._eid_dates[year] = []
                self._eid_dates[year].append(
                    (
                        eid_name_key,
                        date.fromisoformat(dates["start"]),
                        date.fromisoformat(dates["end"]),
                    )
                )

        # Fixed holidays: list of (name, month, day)
        self._fixed_holidays: list[tuple[str, int, int]] = []
        for h in self._config.get("public_holidays", []):
            parts = h["date"].split("-")
            self._fixed_holidays.append((h["name"], int(parts[0]), int(parts[1])))

        # Seasons: name -> (start_month, start_day, end_month, end_day)
        self._seasons: dict[str, tuple[int, int, int, int]] = {}
        for name, s in self._config.get("seasons", {}).items():
            sp = s["start"].split("-")
            ep = s["end"].split("-")
            self._seasons[name] = (int(sp[0]), int(sp[1]), int(ep[0]), int(ep[1]))

    @staticmethod
    def _load_config(config_path: Path) -> dict:
        """Load YAML config, return empty dict on failure."""
        if not config_path.exists():
            logger.warning("Business calendar config not found at %s, using defaults", config_path)
            return {}
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except (sqlite3.Error, ValueError, OSError) as exc:
            logger.error("Failed to load business calendar config: %s", exc)
            return {}

    # -------------------------------------------------------------------------
    # Core queries
    # -------------------------------------------------------------------------

    def get_day_context(self, d: date | None = None) -> DayContext:
        """Return full temporal context for a given date. Defaults to today."""
        if d is None:
            d = date.today()

        weekend = self.is_weekend(d)
        holiday = self.is_public_holiday(d)
        holiday_name = self._get_holiday_name(d)
        ramadan = self.is_ramadan(d)
        ramadan_day = self._get_ramadan_day(d) if ramadan else None
        eid = self.is_eid(d)
        eid_name = self._get_eid_name(d) if eid else None
        season = self.get_season(d)
        working_hours = self.get_working_hours(d)
        working_mins = self.get_working_minutes(d)

        if eid or holiday:
            day_type = DayType.RELIGIOUS_OBSERVANCE if eid else DayType.PUBLIC_HOLIDAY
        elif weekend:
            day_type = DayType.WEEKEND
        else:
            day_type = DayType.WORKING

        is_working = not weekend and not holiday and not eid

        return DayContext(
            date=d,
            day_type=day_type,
            is_working_day=is_working,
            is_weekend=weekend,
            is_public_holiday=holiday or eid,
            holiday_name=holiday_name or eid_name,
            is_ramadan=ramadan,
            ramadan_day=ramadan_day,
            is_eid=eid,
            eid_name=eid_name,
            season=season,
            working_hours=working_hours,
            working_minutes=working_mins,
        )

    def is_working_day(self, d: date) -> bool:
        """True if d is a working day (not weekend, not holiday, not Eid)."""
        return not self.is_weekend(d) and not self.is_public_holiday(d) and not self.is_eid(d)

    def is_weekend(self, d: date) -> bool:
        """True if Friday or Saturday (UAE weekend)."""
        return d.weekday() in self._weekend_days

    def is_public_holiday(self, d: date) -> bool:
        """True if d is a fixed UAE public holiday."""
        for _, month, day in self._fixed_holidays:
            if d.month == month and d.day == day:
                return True
        return False

    def is_ramadan(self, d: date) -> bool:
        """True if d falls within the Ramadan period for its year."""
        r = self._ramadan_dates.get(d.year)
        if r is None:
            return False
        return r[0] <= d <= r[1]

    def is_eid(self, d: date) -> bool:
        """True if d falls within any Eid period."""
        eids = self._eid_dates.get(d.year, [])
        for _, start, end in eids:
            if start <= d <= end:
                return True
        return False

    def get_working_hours(self, d: date) -> tuple:
        """Return (start_hour, end_hour) for the given date."""
        if not self.is_working_day(d):
            return (0, 0)
        if self.is_ramadan(d):
            return (self._ramadan_start, self._ramadan_end)
        return (self._normal_start, self._normal_end)

    def get_working_minutes(self, d: date) -> int:
        """Available working minutes for the given date."""
        start, end = self.get_working_hours(d)
        if start == 0 and end == 0:
            return 0
        return max(0, (end - start) * 60)

    def business_days_between(self, start: date, end: date) -> int:
        """
        Count working days between two dates (exclusive of end).
        Returns negative if start > end.
        """
        if start == end:
            return 0

        sign = 1
        if start > end:
            start, end = end, start
            sign = -1

        count = 0
        current = start
        while current < end:
            if self.is_working_day(current):
                count += 1
            current += timedelta(days=1)

        return count * sign

    def add_business_days(self, start: date, days: int) -> date:
        """Add N business days to a date, skipping weekends and holidays."""
        if days == 0:
            return start

        direction = 1 if days > 0 else -1
        remaining = abs(days)
        current = start

        while remaining > 0:
            current += timedelta(days=direction)
            if self.is_working_day(current):
                remaining -= 1

        return current

    def get_ramadan_dates(self, year: int) -> tuple | None:
        """Return (start, end) of Ramadan for given year, or None if not in lookup."""
        return self._ramadan_dates.get(year)

    def get_eid_dates(self, year: int) -> list[tuple[str, date, date]]:
        """Return list of (name, start, end) for Eid periods in a given year."""
        return self._eid_dates.get(year, [])

    def get_season(self, d: date) -> str:
        """Return season classification for a date."""
        md = (d.month, d.day)
        for name, (sm, sd, em, ed) in self._seasons.items():
            # Handle same-year ranges (no cross-year seasons expected)
            if (sm, sd) <= md <= (em, ed):
                return name
        return "normal"

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _get_holiday_name(self, d: date) -> str | None:
        """Return holiday name if d is a public holiday, else None."""
        for name, month, day in self._fixed_holidays:
            if d.month == month and d.day == day:
                return name
        return None

    def _get_ramadan_day(self, d: date) -> int | None:
        """Return the day number (1-based) within Ramadan."""
        r = self._ramadan_dates.get(d.year)
        if r is None or not (r[0] <= d <= r[1]):
            return None
        return (d - r[0]).days + 1

    def _get_eid_name(self, d: date) -> str | None:
        """Return Eid name if d falls in an Eid period."""
        eids = self._eid_dates.get(d.year, [])
        for name, start, end in eids:
            if start <= d <= end:
                return name
        return None


# =============================================================================
# TEMPORAL NORMALIZER
# =============================================================================


class TemporalNormalizer:
    """
    Converts wall-clock durations to business-time durations.

    "3 days late" should mean 3 business days, not 3 calendar days.
    "Response time 48 hours" during a weekend should be "0 business hours."
    """

    def __init__(self, calendar: BusinessCalendar):
        self.calendar = calendar

    def business_days_late(self, due_date: date, current_date: date | None = None) -> int:
        """
        How many business days late is something?

        Returns 0 if not yet due or due today.
        Returns negative if due in the future (business days until due).
        """
        if current_date is None:
            current_date = date.today()

        if current_date <= due_date:
            # Not late yet — return negative business days until due
            return -self.calendar.business_days_between(current_date, due_date)

        return self.calendar.business_days_between(due_date, current_date)

    def business_hours_elapsed(self, start: datetime, end: datetime | None = None) -> float:
        """
        Business hours between two timestamps.

        Only counts hours within working windows (10-20 normal, 9-14 Ramadan).
        Skips weekends and holidays entirely.
        """
        if end is None:
            end = datetime.now()

        if end <= start:
            return 0.0

        total_minutes = 0.0
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            if self.calendar.is_working_day(current_date):
                wh_start, wh_end = self.calendar.get_working_hours(current_date)

                # Determine effective start/end for this day
                if current_date == start.date():
                    day_start_hour = max(start.hour + start.minute / 60.0, wh_start)
                else:
                    day_start_hour = wh_start

                if current_date == end_date:
                    day_end_hour = min(end.hour + end.minute / 60.0, wh_end)
                else:
                    day_end_hour = wh_end

                if day_end_hour > day_start_hour:
                    total_minutes += (day_end_hour - day_start_hour) * 60.0

            current_date += timedelta(days=1)

        return round(total_minutes / 60.0, 2)

    def business_hours_since(self, timestamp: datetime) -> float:
        """Convenience: business hours from timestamp to now."""
        return self.business_hours_elapsed(timestamp, datetime.now())

    def normalize_aging(self, created_date: date, current_date: date | None = None) -> dict:
        """
        Normalize an aging calculation to business days.

        Returns dict with calendar_days, business_days, business_weeks,
        and context (holidays, Ramadan days in range).
        """
        if current_date is None:
            current_date = date.today()

        calendar_days = (current_date - created_date).days
        business_days = self.calendar.business_days_between(created_date, current_date)

        # Find holidays in the range
        holidays_in_range = []
        ramadan_days_in_range = 0
        d = created_date
        while d < current_date:
            if self.calendar.is_public_holiday(d) or self.calendar.is_eid(d):
                name = self.calendar._get_holiday_name(d) or self.calendar._get_eid_name(d)
                if name:
                    holidays_in_range.append(name)
            if self.calendar.is_ramadan(d) and self.calendar.is_working_day(d):
                ramadan_days_in_range += 1
            d += timedelta(days=1)

        return {
            "calendar_days": calendar_days,
            "business_days": business_days,
            "business_weeks": round(business_days / 5.0, 1) if business_days > 0 else 0.0,
            "includes_holidays": holidays_in_range,
            "includes_ramadan_days": ramadan_days_in_range,
        }

    def expected_response_time(self, sent_at: datetime, response_hours: float = 48.0) -> dict:
        """
        Calculate when a response is reasonably expected, accounting for
        business time and Ramadan context.
        """
        normal_deadline = sent_at + timedelta(hours=response_hours)

        # Walk forward through business hours
        remaining_hours = response_hours
        current = sent_at
        while remaining_hours > 0:
            ctx = self.calendar.get_day_context(current.date())
            if ctx.is_working_day:
                wh_start, wh_end = ctx.working_hours
                if current.date() == sent_at.date():
                    avail_start = max(current.hour + current.minute / 60.0, wh_start)
                else:
                    avail_start = wh_start
                avail_hours = max(0, wh_end - avail_start)
                if avail_hours >= remaining_hours:
                    business_deadline = datetime(
                        current.year,
                        current.month,
                        current.day,
                        int(avail_start + remaining_hours),
                        int(((avail_start + remaining_hours) % 1) * 60),
                    )
                    remaining_hours = 0
                else:
                    remaining_hours -= avail_hours
                    current = datetime(current.year, current.month, current.day) + timedelta(days=1)
            else:
                current = datetime(current.year, current.month, current.day) + timedelta(days=1)

        if remaining_hours > 0:
            business_deadline = current

        is_ramadan = self.calendar.is_ramadan(sent_at.date())
        context_note = ""
        if is_ramadan:
            context_note = "Ramadan hours (9-14) extend expected response time"

        return {
            "sent_at": sent_at.isoformat(),
            "normal_deadline": normal_deadline.isoformat(),
            "business_deadline": business_deadline.isoformat(),
            "context_note": context_note,
        }

    def task_age_weighted(
        self, created_date: date, status: str, current_date: date | None = None
    ) -> float:
        """
        Compute a business-time-weighted task age factor.

        Used by cost-to-serve (ID-2.1) to weight task effort.

        Returns a multiplier:
          - Completed tasks or not overdue: 1.0
          - Overdue 1-5 business days: 1.0 + (days × 0.1)
          - Overdue 6-15 business days: 1.5 + (excess × 0.05)
          - Overdue 15+ business days: 2.0 (capped)
        """
        if current_date is None:
            current_date = date.today()

        if status == "completed":
            return 1.0

        bd_late = self.business_days_late(created_date, current_date)
        if bd_late <= 0:
            return 1.0

        if bd_late <= 5:
            return 1.0 + (bd_late * 0.1)
        elif bd_late <= 15:
            return 1.5 + ((bd_late - 5) * 0.05)
        else:
            return 2.0


# =============================================================================
# RECENCY WEIGHTER
# =============================================================================


class RecencyWeighter:
    """
    Applies exponential decay weighting to temporal data series.

    Uses business days (not calendar days) for decay so data doesn't
    lose weight over weekends when no business activity happens.

    Default half-life: 14 business days (~3 calendar weeks).
    """

    def __init__(
        self,
        calendar: BusinessCalendar,
        half_life_days: int = 14,
        min_weight: float = 0.05,
    ):
        self.calendar = calendar
        self.half_life_days = half_life_days
        self.min_weight = min_weight

    def compute_weight(self, data_date: date, reference_date: date | None = None) -> float:
        """
        Compute decay weight for a single data point.

        Formula: weight = 2^(-business_days_ago / half_life_days)
        Floors at min_weight to ensure old data still counts slightly.
        """
        if reference_date is None:
            reference_date = date.today()

        if data_date >= reference_date:
            return 1.0

        bd_ago = self.calendar.business_days_between(data_date, reference_date)
        if bd_ago <= 0:
            return 1.0

        weight = 2.0 ** (-bd_ago / self.half_life_days)
        return max(weight, self.min_weight)

    def weighted_average(
        self, data_points: list[tuple[date, float]], reference_date: date | None = None
    ) -> float:
        """
        Compute recency-weighted average of (date, value) pairs.

        Formula: sum(value * weight) / sum(weight)
        Returns 0.0 if no data points.
        """
        if not data_points:
            return 0.0

        total_weighted = 0.0
        total_weight = 0.0

        for d, value in data_points:
            w = self.compute_weight(d, reference_date)
            total_weighted += value * w
            total_weight += w

        if total_weight == 0:
            return 0.0

        return total_weighted / total_weight

    def weighted_trend(
        self, data_points: list[tuple[date, float]], reference_date: date | None = None
    ) -> dict:
        """
        Compute recency-weighted trend analysis.

        Returns dict with direction, slope, weighted_mean, unweighted_mean,
        recency_delta, confidence, and data_points count.
        """
        if not data_points:
            return {
                "direction": "stable",
                "slope": 0.0,
                "weighted_mean": 0.0,
                "unweighted_mean": 0.0,
                "recency_delta": 0.0,
                "confidence": 0.0,
                "data_points": 0,
            }

        if reference_date is None:
            reference_date = date.today()

        # Compute weighted and unweighted means
        weighted_mean = self.weighted_average(data_points, reference_date)
        unweighted_mean = sum(v for _, v in data_points) / len(data_points)

        # Weighted linear regression
        # x = business days from earliest point, y = value
        if len(data_points) < 2:
            return {
                "direction": "stable",
                "slope": 0.0,
                "weighted_mean": round(weighted_mean, 2),
                "unweighted_mean": round(unweighted_mean, 2),
                "recency_delta": round(weighted_mean - unweighted_mean, 2),
                "confidence": 0.0,
                "data_points": len(data_points),
            }

        sorted_points = sorted(data_points, key=lambda p: p[0])
        earliest = sorted_points[0][0]

        xs = []
        ys = []
        ws = []
        for d, v in sorted_points:
            x = self.calendar.business_days_between(earliest, d)
            xs.append(float(x))
            ys.append(v)
            ws.append(self.compute_weight(d, reference_date))

        # Weighted linear regression: slope = Σ(w * (x - x̄) * (y - ȳ)) / Σ(w * (x - x̄)²)
        w_sum = sum(ws)
        x_mean = sum(w * x for w, x in zip(ws, xs, strict=False)) / w_sum
        y_mean = sum(w * y for w, y in zip(ws, ys, strict=False)) / w_sum

        numerator = sum(
            w * (x - x_mean) * (y - y_mean) for w, x, y in zip(ws, xs, ys, strict=False)
        )
        denominator = sum(w * (x - x_mean) ** 2 for w, x in zip(ws, xs, strict=False))

        if abs(denominator) < 1e-10:
            slope = 0.0
        else:
            slope = numerator / denominator

        # R² (coefficient of determination)
        ss_res = sum(
            w * (y - (y_mean + slope * (x - x_mean))) ** 2
            for w, x, y in zip(ws, xs, ys, strict=False)
        )
        ss_tot = sum(w * (y - y_mean) ** 2 for w, y in zip(ws, ys, strict=False))
        r_squared = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-10 else 0.0

        # Direction
        if slope > 0.3:
            direction = "improving"
        elif slope < -0.3:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "slope": round(slope, 4),
            "weighted_mean": round(weighted_mean, 2),
            "unweighted_mean": round(unweighted_mean, 2),
            "recency_delta": round(weighted_mean - unweighted_mean, 2),
            "confidence": round(max(0.0, min(1.0, r_squared)), 3),
            "data_points": len(data_points),
        }

    def weighted_percentile(
        self,
        value: float,
        population: list[tuple[date, float]],
        reference_date: date | None = None,
    ) -> float:
        """
        Where does this value rank among its recency-weighted peers?

        Returns 0.0-1.0 percentile. Recent peers count more.
        """
        if not population:
            return 0.5

        total_weight_below = 0.0
        total_weight = 0.0

        for d, v in population:
            w = self.compute_weight(d, reference_date)
            total_weight += w
            if v < value:
                total_weight_below += w
            elif v == value:
                total_weight_below += w * 0.5  # Half-weight for ties

        if total_weight == 0:
            return 0.5

        return total_weight_below / total_weight
