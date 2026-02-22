# TC-2.1: Temporal Normalization Functions

## Objective

Replace wall-clock time calculations with business-time calculations throughout the intelligence layer. "3 days late" should mean 3 business days, not 3 calendar days. "Response time 48 hours" during a weekend should be "response time 0 business hours."

## Dependencies

- TC-1.1 (BusinessCalendar — provides is_working_day, working hours)
- `lib/ui_spec_v21/time_utils.py` (timezone handling)

## Deliverables

### Add to `lib/intelligence/temporal.py` (TemporalNormalizer class)

```python
class TemporalNormalizer:
    """Converts wall-clock durations to business-time durations."""

    def __init__(self, calendar: BusinessCalendar): ...

    def business_days_late(self, due_date: date, current_date: date = None) -> int:
        """How many business days late is something?
        Returns 0 if not yet due or due today.
        Returns negative if due in the future (business days until due).
        Excludes weekends and holidays.

        Example:
          due_date = Friday Feb 20 (working day)
          current_date = Monday Feb 23
          Calendar days late: 3
          Business days late: 1 (Sat + Sun skipped)
        """

    def business_hours_elapsed(self, start: datetime, end: datetime = None) -> float:
        """Business hours between two timestamps.
        Only counts hours within working windows (10-20 normal, 9-14 Ramadan).
        Skips weekends and holidays entirely.

        Example:
          start = Thursday 18:00
          end = Monday 10:00
          Wall clock: 64 hours
          Business hours: 2 (Thu 18-20) + 0 (Fri) + 0 (Sat) + 0 (Sun 0-10)
        """

    def business_hours_since(self, timestamp: datetime) -> float:
        """Convenience: business hours from timestamp to now."""

    def normalize_aging(self, created_date: date, current_date: date = None) -> dict:
        """Normalize an aging calculation (e.g., invoice aging) to business days.
        Returns:
        {
            "calendar_days": 45,
            "business_days": 32,
            "business_weeks": 6.4,
            "includes_holidays": ["UAE National Day"],
            "includes_ramadan_days": 5
        }
        """

    def expected_response_time(self, sent_at: datetime, context: DayContext = None) -> dict:
        """Calculate when a response is reasonably expected, accounting for context.
        Returns:
        {
            "sent_at": "2026-02-20T17:00:00Z",
            "normal_deadline": "2026-02-22T17:00:00Z",     # 48 wall-clock hours
            "business_deadline": "2026-02-24T11:00:00Z",    # 48 business hours (skips weekend)
            "context_adjusted": "2026-02-24T14:00:00Z",     # with Ramadan modifier if applicable
            "context_note": "Ramadan hours (9-14) extend expected response time"
        }
        """

    def task_age_weighted(self, created_date: date, status: str, current_date: date = None) -> float:
        """Compute a business-time-weighted task age factor.
        Used by cost-to-serve (ID-2.1) to weight task effort.

        Returns a multiplier:
          - Completed tasks within SLA: 1.0
          - Overdue 1-5 business days: 1.0 + (business_days_overdue × 0.1)
          - Overdue 6-15 business days: 1.5 + (excess_days × 0.05)
          - Overdue 15+ business days: 2.0 (capped)

        status: "completed" | "in_progress" | "overdue" | "blocked"
        """
```

### Integration Points

These functions replace raw date arithmetic in:

| Current Code | Current Approach | Replacement |
|-------------|-----------------|-------------|
| `time_utils.days_late()` | Calendar days | `TemporalNormalizer.business_days_late()` |
| `time_utils.days_overdue()` | Calendar days | `TemporalNormalizer.business_days_late()` |
| Signal threshold: `overdue_days >= 5` | Calendar days | Compare against `business_days_late()` |
| Invoice aging calculation | Calendar days | `normalize_aging().business_days` |
| Cost-to-serve task effort | Raw count | `task_age_weighted()` per task |
| Response time signals | Wall-clock hours | `business_hours_elapsed()` |

### Important: Non-Breaking Migration

The existing `time_utils.days_late()` and `days_overdue()` should NOT be modified — they're used elsewhere and tested. The TemporalNormalizer provides **new, parallel functions** that intelligence consumers can switch to incrementally. The old functions remain for backward compatibility.

## Validation

- business_days_late for task due Friday, checked Monday = 1 (not 3)
- business_hours_elapsed spanning a weekend = only counts working hours
- business_hours_elapsed during Ramadan uses 9-14 window (not 10-20)
- normalize_aging correctly identifies holidays in the range
- expected_response_time extends deadline across weekends
- task_age_weighted caps at 2.0 for very overdue tasks
- Zero business hours on a public holiday
- Edge: both start and end on non-working days → 0 business hours

## Estimated Effort

~200 lines
