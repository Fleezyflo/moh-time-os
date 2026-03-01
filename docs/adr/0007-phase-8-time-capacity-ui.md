# ADR-0007: Phase 8 Time & Capacity UI Pages

## Status
Accepted

## Context
Phase 8 adds two new UI pages (Schedule and Capacity) that wire 10 existing backend endpoints to the frontend. The backend endpoints (`/api/time/blocks`, `/api/time/summary`, `/api/time/schedule`, `/api/time/unschedule`, `/api/capacity/lanes`, `/api/capacity/utilization`, `/api/capacity/forecast`, `/api/capacity/debt`, `/api/events`, `/api/day/{date}`, `/api/week`) already exist in `api/server.py` and are production-ready. No backend changes are made in this phase.

## Decision
Wire the existing time and capacity endpoints to new frontend pages following the established Phase 6-7 patterns:

1. Add 11 fetch functions and 11 TypeScript interfaces to `lib/api.ts`
2. Add 9 data-fetching hooks to `lib/hooks.ts`
3. Create Schedule page with day view (time block grid by lane), week view, events tab, and schedule/unschedule task actions
4. Create Capacity page with utilization gauges (SVG), forecast bar chart, and debt tracker
5. Create 5 new components: TimeBlockGrid, WeekView, ScheduleTaskDialog, CapacityGauge, ForecastChart
6. Add `/schedule` and `/capacity` routes to the nav

## Consequences
- Two new nav items increase navigation width -- acceptable given the information density they provide
- System map grows from 21 to 23 UI routes
- Capacity debt endpoints (accrue/resolve) return 501 -- UI shows empty state for debt until backend implements them
- No backend changes, no migration impact, no API surface changes
