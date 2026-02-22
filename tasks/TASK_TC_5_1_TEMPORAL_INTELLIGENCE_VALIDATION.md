# TC-5.1: Temporal Intelligence Validation

## Objective

Comprehensive test suite validating the temporal intelligence layer: business calendar, temporal normalization, recency weighting, and signal lifecycle tracking.

## Dependencies

- TC-1.1 through TC-4.1 (all temporal components)
- Brief 17 IW-1.1 (signal_state fixtures)

## Test Files

### `tests/test_business_calendar.py` (~70 lines)

- Friday (weekday=4) → is_weekend=True, is_working_day=False
- Saturday (weekday=5) → is_weekend=True
- Sunday through Thursday → is_working_day=True
- Dec 2 (UAE National Day) → is_public_holiday=True, is_working_day=False
- Feb 18, 2026 (mid-Ramadan) → is_ramadan=True, ramadan_day=2
- Mar 20, 2026 (Eid al-Fitr) → is_eid=True, is_working_day=False
- Jul 15, 2026 → season="summer_slowdown"
- Nov 20, 2026 → season="q4_close"
- Apr 15, 2026 → season="normal"
- business_days_between(Thu, Mon) = 1 (skips Fri+Sat)
- business_days_between includes no holidays in non-holiday week
- business_days_between correctly skips National Day
- add_business_days(Wednesday, 3) → Monday (skips Fri+Sat)
- get_working_hours during Ramadan → (9, 14)
- get_working_hours normal day → (10, 20)
- get_working_hours holiday → (0, 0)
- get_working_minutes Ramadan → 300
- get_working_minutes normal → 600
- get_working_minutes weekend → 0
- get_ramadan_dates(2026) → correct dates
- get_ramadan_dates(2050) → None (out of range)

### `tests/test_temporal_normalization.py` (~60 lines)

- business_days_late: due Friday, checked Monday → 1 (not 3)
- business_days_late: due today → 0
- business_days_late: due tomorrow → -1 (future)
- business_days_late: due Thursday, checked following Thursday → 5
- business_hours_elapsed: Thursday 18:00 to Monday 10:00 → 2.0 hours
- business_hours_elapsed: within single working day → correct hours
- business_hours_elapsed: entirely on weekend → 0
- business_hours_elapsed during Ramadan: uses 9-14 window
- normalize_aging: 45 calendar days with 2 weekends and 1 holiday → correct business days
- normalize_aging: identifies holidays in range
- expected_response_time: sent Friday 17:00 → business deadline skips weekend
- task_age_weighted: completed within SLA → 1.0
- task_age_weighted: overdue 3 business days → 1.3
- task_age_weighted: overdue 20 business days → capped at 2.0

### `tests/test_recency_weighter.py` (~60 lines)

- compute_weight for today → 1.0
- compute_weight for half_life ago → ≈0.5 (within 0.01 tolerance)
- compute_weight for 2× half_life ago → ≈0.25
- compute_weight floors at min_weight (never 0)
- weighted_average of identical values = that value
- weighted_average weights recent data higher
- weighted_trend: strictly increasing recent scores → "improving"
- weighted_trend: flat data → "stable"
- weighted_trend: declining recent, good old → "declining" + negative recency_delta
- weighted_percentile: value above all recent data → high percentile
- weighted_percentile: same as unweighted when all same date
- Config: half_life_business_days loaded from intelligence.yaml

### `tests/test_signal_lifecycle.py` (~80 lines)

- First detection → persistence=NEW, detection_count=1
- 2nd detection next cycle → persistence=RECENT, detection_count=2
- After 5 business days → persistence=ONGOING
- After 12 business days → persistence=CHRONIC
- Severity upgrade (watch→warning) → persistence=ESCALATING
- Metrics trending toward threshold → persistence=RESOLVING
- ESCALATING takes priority over CHRONIC
- RESOLVING takes priority over ONGOING
- Escalation history records old and new severity
- update_lifecycle_on_clear marks signal as resolved (doesn't delete)
- Chronic watch signal (14+ business days) auto-escalates to warning
- get_chronic_signals returns sorted list
- get_escalating_signals includes recently escalated only
- get_signal_age_distribution counts match individual classifications
- Age uses business days (weekend gap doesn't inflate age)
- Signal cleared and re-detected → new lifecycle (fresh detection_count)

### `tests/test_temporal_integration.py` (~50 lines)

Full pipeline tests:

- **Scenario: Ramadan communication drop**
  1. Seed score_history with declining communication scores during Ramadan dates
  2. BusinessCalendar confirms Ramadan is active
  3. TemporalNormalizer.expected_response_time returns extended deadline
  4. RecencyWeighter.weighted_trend accounts for Ramadan context

- **Scenario: Weekend overdue not inflated**
  1. Task due Friday 6pm
  2. Checked Monday 9am
  3. business_days_late → 0 (or 1 depending on start-of-day semantics)
  4. Signal threshold evaluated against business days, not calendar

- **Scenario: Chronic signal escalation**
  1. Seed signal detected 15 business days ago at "watch" severity
  2. SignalLifecycleTracker classifies as CHRONIC
  3. Auto-escalation rule upgrades to "warning"
  4. Escalation history records the change

- **Scenario: Recency-weighted trend reversal**
  1. Seed 30 days of score history: good old scores (80+), bad recent scores (50s)
  2. Unweighted average → ~65 (looks stable)
  3. Recency-weighted average → ~55 (reveals recent decline)
  4. weighted_trend.direction → "declining"

### Fixtures

Create `tests/fixtures/seed_temporal_data.py`:
- Score history spanning 90 days (mix of weekdays, weekends, holidays)
- Signal states with various first_detected_at dates (1 day to 30 days ago)
- Signals with escalation history (severity changes)
- Data points during Ramadan period
- Data points spanning UAE National Day holiday

## Validation

- All tests pass
- No test depends on system clock (all dates injected)
- Business calendar tests cover all UAE-specific cases
- Normalization tests verify wall-clock vs business-time difference
- Lifecycle tests verify all persistence classifications
- Integration tests verify end-to-end temporal awareness
- Edge cases: year boundary, Ramadan starting mid-week, holiday on Thursday

## Estimated Effort

~250 lines across 5 test files + 1 fixture file
