# ADR-0005: Capacity Endpoint Rewire

## Status
Accepted

## Context
The capacity endpoints in `api/server.py` referenced modules and functions that no longer exist (`lib.time_truth.get_capacity_lanes`, `lib.time_truth.Scheduler`, `lib.time_truth.get_capacity_debt`). Several endpoints called methods that were never implemented (marked with `# type: ignore[attr-defined]`), meaning they would crash at runtime.

This was discovered during the schema convergence work (replacing four divergent schema sources with a single `lib/schema.py`).

## Decision
1. **Rewire capacity endpoints** to use `lib.capacity_truth.CapacityCalculator` and `lib.capacity_truth.DebtTracker`, which are the actual implementations.
2. **Return 501** for `POST /api/capacity/debt/accrue` and `POST /api/capacity/debt/{debt_id}/resolve`, which have no implementation. This follows ADR-0002.
3. **Rewire day/week endpoints** to use `lib.time_truth.CalendarSync` directly instead of the non-existent `analyzers.time` attribute.

## Consequences
- Capacity endpoints now point to real implementations instead of crashing on missing methods.
- Two debt mutation endpoints honestly return 501 instead of crashing.
- Day and week analysis endpoints use CalendarSync directly.

## Affected Files
- api/server.py (capacity lanes, utilization, forecast, debt, day analysis, week analysis)
