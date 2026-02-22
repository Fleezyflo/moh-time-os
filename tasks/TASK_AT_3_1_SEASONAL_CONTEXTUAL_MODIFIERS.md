# AT-3.1: Seasonal & Contextual Modifiers

## Objective

Adjust signal sensitivity based on known calendar context. During Ramadan, communication volume naturally drops — that shouldn't trigger "communication_drop" signals. During Q4 crunch, slight overdue increases are normal. The system should account for predictable seasonal patterns rather than alerting on expected variations.

## Dependencies

- AT-2.1 (calibration engine — modifiers feed into threshold adjustments)
- Brief 17 IW-1.1 (thresholds.yaml — what gets modified)
- Brief 9 (Calendar & Communication — date awareness)

## Deliverables

### New file: `lib/intelligence/seasonal.py`

```python
class SeasonalModifier:
    """Applies seasonal and contextual adjustments to signal thresholds."""

    def __init__(self, thresholds_path: Path): ...

    def get_active_modifiers(self, date: date = None) -> list[dict]:
        """Return all modifiers active for the given date.
        Returns:
        [
            {
                "modifier_id": "ramadan_2026",
                "name": "Ramadan",
                "type": "religious_observance",
                "start_date": "2026-02-17",
                "end_date": "2026-03-19",
                "adjustments": {
                    "communication_drop": {"factor": 1.5, "reason": "Communication naturally decreases during Ramadan"},
                    "response_time_slow": {"factor": 1.3, "reason": "Response times typically increase during Ramadan"},
                    "task_completion_low": {"factor": 1.2, "reason": "Productivity patterns shift during Ramadan"}
                }
            }
        ]
        """

    def apply_seasonal_adjustments(self, base_thresholds: dict, date: date = None) -> dict:
        """Return a copy of thresholds with seasonal factors applied.
        Does NOT modify the original thresholds file.
        Returns:
        {
            "adjusted_thresholds": { ... },
            "active_modifiers": [...],
            "adjustments_applied": [
                {"signal_type": "communication_drop", "original": 0.3, "adjusted": 0.45, "modifier": "ramadan_2026"}
            ]
        }
        """

    def get_modifier_calendar(self, year: int = None) -> list[dict]:
        """Return the full modifier calendar for the year.
        Includes fixed dates (national holidays, fiscal periods) and
        calculated dates (Ramadan, Eid — computed from Hijri calendar).
        """

    def add_custom_modifier(self, modifier: dict) -> None:
        """Add a one-off modifier (e.g., company retreat, office move)."""

    def remove_modifier(self, modifier_id: str) -> None:
        """Remove a custom modifier."""
```

### Modifier Configuration: `config/seasonal_modifiers.yaml`

```yaml
# UAE & Dubai-specific seasonal modifiers
modifiers:
  # === Religious Observances ===
  ramadan:
    type: religious_observance
    recurrence: hijri_annual  # computed each year
    duration_days: 30
    adjustments:
      communication_drop: { factor: 1.5 }
      response_time_slow: { factor: 1.3 }
      task_completion_low: { factor: 1.2 }
      meeting_cancellation: { factor: 1.4 }

  eid_al_fitr:
    type: public_holiday
    recurrence: hijri_annual
    duration_days: 4
    adjustments:
      communication_drop: { factor: 2.0 }  # near-silence expected
      response_time_slow: { factor: 2.0 }
      task_completion_low: { factor: 1.5 }

  eid_al_adha:
    type: public_holiday
    recurrence: hijri_annual
    duration_days: 4
    adjustments:
      communication_drop: { factor: 2.0 }
      response_time_slow: { factor: 2.0 }
      task_completion_low: { factor: 1.5 }

  # === UAE National Holidays ===
  uae_national_day:
    type: public_holiday
    fixed_dates: ["12-02", "12-03"]
    adjustments:
      communication_drop: { factor: 1.8 }

  new_year:
    type: public_holiday
    fixed_dates: ["01-01"]
    adjustments:
      communication_drop: { factor: 1.5 }

  # === Business Cycles ===
  q4_close:
    type: fiscal_period
    fixed_dates_range: ["11-15", "12-31"]
    adjustments:
      task_overdue: { factor: 1.2 }  # slight tolerance for crunch
      invoice_aging: { factor: 0.9 }  # tighter on collections

  summer_slowdown:
    type: seasonal
    fixed_dates_range: ["07-01", "08-31"]
    adjustments:
      communication_drop: { factor: 1.3 }
      response_time_slow: { factor: 1.2 }

  # === Working Hours ===
  friday_saturday:
    type: weekend
    recurrence: weekly
    days: [4, 5]  # Friday=4, Saturday=5 in Python
    adjustments:
      communication_drop: { factor: 2.0 }
      response_time_slow: { factor: 2.0 }

  ramadan_working_hours:
    type: working_hours_shift
    recurrence: hijri_annual  # co-occurs with ramadan
    duration_days: 30
    notes: "UAE working hours typically 9-2 during Ramadan"
    adjustments:
      response_time_slow: { factor: 1.3 }
```

### Hijri Calendar Integration

Use the `hijri-converter` package (already commonly available) or a simple lookup table for the next 5 years:

```python
RAMADAN_DATES = {
    2026: ("2026-02-17", "2026-03-19"),
    2027: ("2027-02-07", "2027-03-08"),
    2028: ("2028-01-27", "2028-02-25"),
    # Pre-computed; update annually or use hijri-converter
}
```

### How Modifiers Interact with Calibration

Modifiers are applied **at signal evaluation time**, not stored permanently:

```
1. Daemon loads base thresholds from thresholds.yaml
2. SeasonalModifier.apply_seasonal_adjustments() returns adjusted copy
3. Signal detection uses adjusted thresholds for this cycle
4. Effectiveness scoring accounts for active modifiers:
   - If modifier was active when signal fired, mark in evidence
   - Calibration engine ignores fires during seasonal periods for
     threshold adjustment decisions (to avoid seasonal noise)
```

## Validation

- Ramadan modifier correctly activates during Ramadan dates
- Weekend modifier activates on Friday/Saturday (UAE weekend)
- Factor multiplication produces correct adjusted thresholds
- Multiple overlapping modifiers stack correctly (multiplicative)
- Custom modifiers can be added and removed
- Modifier calendar returns correct dates for current year
- Hijri date computation matches known Ramadan dates (±1 day tolerance)
- Signal fires during seasonal periods are excluded from calibration analysis

## Estimated Effort

~250 lines (excluding YAML config)
