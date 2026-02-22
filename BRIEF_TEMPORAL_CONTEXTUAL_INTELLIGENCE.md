# Brief 31: Temporal & Contextual Intelligence
> **Status:** DESIGNED | **Priority:** P2 | **Prefix:** TC

## Problem

The intelligence layer treats all time equally. A 3-day response lag during Ramadan is culturally normal, but the system fires a "response_time_slow" signal. An overdue task from Friday 6pm to Monday 9am counts as 3 calendar days late when it's really 0 business days late. Score normalization weights a 90-day-old data point identically to yesterday's. The daemon doesn't know the difference between a working hour and a weekend.

Dubai's business calendar is unique: Friday-Saturday weekends, Ramadan working hours (typically 9am-2pm), Hijri-calculated holidays, summer slowdowns (July-August), and Q4 fiscal crunch. Without temporal context, intelligence outputs generate noise instead of insight.

The core infrastructure already exists — `time_utils.py` handles Dubai timezone and ISO 8601 normalization, `lanes.yaml` defines per-lane working hours, and `scheduling_engine.py` has hardcoded SEW windows. But none of this feeds into the intelligence layer.

## Dependencies

- **Requires:** Brief 9 (Calendar & Communication — date awareness foundation)
- **Requires:** Brief 17 IW-1.1 (thresholds.yaml and signal detection)
- **Enhances:** Brief 18 (Intelligence Depth — scoring, patterns, cost-to-serve)
- **Enhances:** Brief 30 AT-3.1 (Seasonal Modifiers — consumes the calendar TC provides)
- **Enhances:** Brief 27 DQ-2.1 (Completeness Scorer — time-aware expectations)

## Scope

Build temporal awareness into the intelligence foundation layer. Three capabilities:

1. **Business Calendar** — Know what today "means" (working day, weekend, holiday, Ramadan, Q4, summer)
2. **Temporal Normalization** — Measure overdue/late/aging in business time, not wall-clock time
3. **Recency Weighting** — Score normalization that decays older data and weights recent data higher

## Architecture

```
config/business_calendar.yaml     ←  holiday dates, Ramadan dates, season definitions
           ↓
lib/intelligence/temporal.py      ←  BusinessCalendar, TemporalNormalizer, RecencyWeighter
           ↓
Consumers:
  - signals.py (threshold evaluation with temporal context)
  - scoring.py (recency-weighted normalization)
  - cost_to_serve.py (business-time effort calculation)
  - health_unifier.py (recency-weighted trend analysis)
  - seasonal.py (AT-3.1 consumes BusinessCalendar directly)
```

## Tasks

| Task | Title | Est. Lines |
|------|-------|------------|
| TC-1.1 | Business Calendar Engine | ~250 |
| TC-2.1 | Temporal Normalization Functions | ~200 |
| TC-3.1 | Recency-Weighted Score Normalization | ~200 |
| TC-4.1 | Signal Age & Persistence Tracking | ~200 |
| TC-5.1 | Temporal Intelligence Validation | ~250 |

## Estimated Effort

~1,100 lines. 5 tasks. Medium.

## Success Criteria

- Business days overdue calculated correctly (excluding weekends and holidays)
- Ramadan and Eid dates auto-computed from Hijri calendar
- Score normalization decays older data (configurable half-life)
- Signal age tracked from first detection to current state
- Signals include persistence classification (new/ongoing/escalated/chronic)
- No hardcoded dates — all from config/business_calendar.yaml or computed
