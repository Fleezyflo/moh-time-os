# TC-1.1: Business Calendar Engine

## Objective

Central calendar engine that answers: "What kind of day is this?" for any given date. Powers all temporal intelligence decisions. The intelligence layer queries this instead of doing its own date math.

## Dependencies

- Brief 9 (Calendar & Communication — event data)
- `lib/ui_spec_v21/time_utils.py` (timezone infrastructure, Dubai default)

## Deliverables

### New file: `lib/intelligence/temporal.py` (BusinessCalendar class)

```python
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from enum import Enum
from typing import Optional
import yaml

class DayType(Enum):
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
    is_weekend: bool             # Friday or Saturday (UAE)
    is_public_holiday: bool
    holiday_name: Optional[str]
    is_ramadan: bool
    ramadan_day: Optional[int]   # day 1-30 within Ramadan, or None
    is_eid: bool
    eid_name: Optional[str]
    season: str                  # "normal", "q4_close", "summer_slowdown"
    working_hours: tuple[int, int]  # (start_hour, end_hour) — shifts during Ramadan
    working_minutes: int         # available working minutes this day

class BusinessCalendar:
    """Central temporal context engine for Dubai/UAE business operations."""

    def __init__(self, config_path: Path = None):
        """Load from config/business_calendar.yaml.
        Falls back to hardcoded defaults if config missing.
        """

    def get_day_context(self, d: date = None) -> DayContext:
        """Return full context for a given date. Defaults to today (Dubai TZ)."""

    def is_working_day(self, d: date) -> bool:
        """True if the date is a working day (not weekend, not holiday)."""

    def is_weekend(self, d: date) -> bool:
        """True if Friday (weekday=4) or Saturday (weekday=5). UAE weekend."""

    def is_public_holiday(self, d: date) -> bool:
        """True if the date falls on a UAE public holiday or religious holiday."""

    def get_working_hours(self, d: date) -> tuple[int, int]:
        """Return (start_hour, end_hour) for the given date.
        Normal: (10, 20)
        Ramadan: (9, 14)
        Holiday: (0, 0)
        """

    def get_working_minutes(self, d: date) -> int:
        """Available working minutes for the given date.
        Normal working day: 600 (10h × 60)
        Ramadan working day: 300 (5h × 60)
        Weekend/holiday: 0
        """

    def business_days_between(self, start: date, end: date) -> int:
        """Count working days between two dates (exclusive of end).
        Skips weekends and holidays.
        """

    def add_business_days(self, start: date, days: int) -> date:
        """Add N business days to a date, skipping weekends and holidays."""

    def get_ramadan_dates(self, year: int) -> Optional[tuple[date, date]]:
        """Return (start, end) of Ramadan for given year.
        Uses lookup table for 2024-2030, computed from Hijri calendar.
        Returns None if year not in range.
        """

    def get_eid_dates(self, year: int) -> list[tuple[str, date, date]]:
        """Return list of (name, start, end) for Eid al-Fitr and Eid al-Adha."""

    def get_season(self, d: date) -> str:
        """Return season classification: 'normal', 'q4_close', 'summer_slowdown'."""
```

### Configuration: `config/business_calendar.yaml`

```yaml
# UAE/Dubai Business Calendar Configuration
timezone: "Asia/Dubai"

# UAE Weekend (ISO weekday numbering: Monday=0, Sunday=6)
weekend_days: [4, 5]  # Friday, Saturday

# Standard working hours
working_hours:
  normal:
    start: 10
    end: 20
  ramadan:
    start: 9
    end: 14

# Ramadan dates (pre-computed from Hijri calendar)
# Update annually; dates approximate ±1 day
ramadan:
  2024: { start: "2024-03-11", end: "2024-04-09" }
  2025: { start: "2025-02-28", end: "2025-03-30" }
  2026: { start: "2026-02-17", end: "2026-03-19" }
  2027: { start: "2027-02-07", end: "2027-03-08" }
  2028: { start: "2028-01-27", end: "2028-02-25" }
  2029: { start: "2029-01-15", end: "2029-02-13" }
  2030: { start: "2030-01-05", end: "2030-02-03" }

# Eid dates (post-Ramadan and Dhul Hijjah)
eid_al_fitr:
  2026: { start: "2026-03-20", end: "2026-03-23" }
  2027: { start: "2027-03-09", end: "2027-03-12" }
  # Add more years as needed

eid_al_adha:
  2026: { start: "2026-05-27", end: "2026-05-30" }
  2027: { start: "2027-05-16", end: "2027-05-19" }
  # Add more years as needed

# Fixed UAE public holidays (month-day)
public_holidays:
  - { name: "New Year's Day", date: "01-01" }
  - { name: "Commemoration Day", date: "11-30" }
  - { name: "UAE National Day", date: "12-02" }
  - { name: "UAE National Day (Day 2)", date: "12-03" }

# Business seasons (date ranges, MM-DD format)
seasons:
  q4_close:
    start: "11-15"
    end: "12-31"
  summer_slowdown:
    start: "07-01"
    end: "08-31"
```

### Key Design Decisions

1. **Lookup table over library**: Pre-computed Ramadan dates avoid a `hijri-converter` dependency. Update the YAML annually. Dates are approximate (±1 day) — acceptable for threshold adjustment, not for prayer times.

2. **UAE weekend = Friday + Saturday**: This is hardcoded in config, not computed. If UAE changes its weekend (as it did in 2022 from Fri-Sat to Sat-Sun for government — private sector varies), update the YAML.

3. **Working hours shift during Ramadan**: The entire system knows that Ramadan working days are 5 hours, not 10. This affects capacity calculations, expected response times, and overdue thresholds.

4. **No dependency on external services**: Everything is local — YAML config and date math. No API calls to calendar services for business day calculation.

## Validation

- `is_weekend` returns True for Friday and Saturday, False for Sunday through Thursday
- `is_public_holiday` returns True for Dec 2 (UAE National Day)
- `get_ramadan_dates(2026)` returns (2026-02-17, 2026-03-19)
- `business_days_between("2026-02-19", "2026-02-23")` = 3 (Thu-Fri-Sat-Sun-Mon → skips Fri+Sat)
- During Ramadan, `get_working_minutes` returns 300, not 600
- `get_day_context` during Ramadan returns `is_ramadan=True`, correct `ramadan_day`
- `get_season("2026-07-15")` returns "summer_slowdown"
- `get_season("2026-12-01")` returns "q4_close"
- Missing year in Ramadan lookup returns None (not crash)
- `add_business_days` correctly skips weekends AND holidays

## Estimated Effort

~250 lines
