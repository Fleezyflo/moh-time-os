# Brief 23: Predictive Scheduling & Resource Optimization

## Status: DESIGNED
## Priority: P2 — Proactive intelligence, high business value
## Dependencies: Brief 11 (Intelligence — Trajectory/Scenario engines), Brief 9 (Collectors — Calendar), Brief 5 (Data Foundation — Capacity Lanes)

## Problem Statement

The system detects problems *after* they happen: overdue tasks, missed commitments, capacity breaches. It has the trajectory engine (velocity, acceleration, trend projection) and scenario engine (what-if modeling) but neither is wired into forward-looking scheduling. Capacity lanes exist but aren't used predictively — they show current load, not next week's collision. Calendar data is collected but not analyzed for meeting overload or focus time deficits. The agency needs to see problems *before* they arrive: "Next Tuesday, Lane X will be at 140% capacity" or "Client Y's project will miss deadline at current velocity."

## Success Criteria

- Capacity forecast: 2-week rolling view showing predicted load per lane, per person, per day
- Overcommitment early warning: flag weeks where predicted load > 100% at least 5 days before
- Resource rebalancing suggestions: when lane A is overloaded and lane B has slack, suggest moves
- Project deadline prediction: based on current velocity + remaining scope, predict completion date
- Cash flow projection: based on AR aging + invoice schedule + payment patterns, forecast cash position
- Meeting load analysis: flag people with >60% meeting time, suggest consolidation windows
- Focus time protection: identify available deep-work blocks, suggest calendar holds
- What-if staffing scenarios: simulate adding/removing team members on predicted outcomes

## Scope

### Phase 1: Capacity Forecaster (PS-1.1)
Build a CapacityForecaster that takes current lane assignments, task velocity (from trajectory engine), and known upcoming commitments to project load per lane per day for the next 14 days. Factor in PTO/holidays from calendar. Output: daily load percentage per lane, per person. Flag days exceeding configurable threshold (default 100%).

### Phase 2: Project Deadline Predictor (PS-2.1)
Build a DeadlinePredictor that uses task completion velocity (tasks/week), remaining task count, and scope change rate to project completion dates. Compare against committed deadlines. Output: predicted_completion_date, confidence_interval, days_ahead_or_behind, risk_level. Trigger warnings when predicted date exceeds committed date by configurable buffer.

### Phase 3: Cash Flow Projector (PS-3.1)
Build a CashFlowProjector that combines: AR aging (invoices outstanding by age bucket), scheduled invoice dates (from project milestones), historical payment patterns (days-to-pay per client from Xero data), and known expenses. Output: daily projected cash position for next 30/60/90 days. Flag cash crunch dates where projected balance drops below safety threshold.

### Phase 4: Meeting & Focus Time Analyzer (PS-4.1)
Build a CalendarAnalyzer that processes calendar events to calculate: meeting load per person (hours/week, % of working hours), meeting fragmentation (number of context switches per day), available focus blocks (≥2hr uninterrupted slots), meeting clustering opportunities (back-to-back consolidation). Generate focus time recommendations and calendar hold suggestions.

### Phase 5: Resource Optimizer & Validation (PS-5.1)
Build a ResourceOptimizer that takes capacity forecast, deadline predictions, and team capabilities to suggest rebalancing: "Move 2 tasks from Alice (130% load) to Bob (60% load) in Lane X." Score suggestions by feasibility (skill match, client familiarity, task complexity). Wire what-if scenarios: "What if we hire a junior designer?" → simulate on forecast. Validate all predictions against historical accuracy.

## Architecture

```
Data Sources:
  Capacity Lanes (Brief 5) → current assignments
  Trajectory Engine (Brief 11) → velocity, trends
  Scenario Engine (Brief 11) → what-if simulation
  Calendar Collector (Brief 9) → meetings, PTO
  Xero Collector (Brief 9) → invoices, payments

Predictive Models:
  CapacityForecaster
    ├─ input: lanes, velocity, commitments, PTO
    ├─ method: linear projection + known events
    └─ output: load_per_lane_per_day[14d]

  DeadlinePredictor
    ├─ input: tasks_remaining, velocity, scope_change_rate
    ├─ method: monte carlo (100 runs) with velocity variance
    └─ output: predicted_date, confidence_interval, risk

  CashFlowProjector
    ├─ input: AR_aging, invoice_schedule, payment_history, expenses
    ├─ method: probabilistic (payment timing distribution per client)
    └─ output: daily_projected_balance[90d], crunch_dates

  CalendarAnalyzer
    ├─ input: calendar_events, working_hours config
    ├─ method: time-block analysis, fragmentation scoring
    └─ output: meeting_load, focus_blocks, recommendations

  ResourceOptimizer
    ├─ input: forecasts, team_capabilities, constraints
    ├─ method: greedy assignment with skill-match scoring
    └─ output: rebalancing_suggestions, what_if_results
```

## Task Files
- `tasks/TASK_PS_1_1_CAPACITY_FORECASTER.md`
- `tasks/TASK_PS_2_1_DEADLINE_PREDICTOR.md`
- `tasks/TASK_PS_3_1_CASHFLOW_PROJECTOR.md`
- `tasks/TASK_PS_4_1_MEETING_FOCUS_ANALYZER.md`
- `tasks/TASK_PS_5_1_RESOURCE_OPTIMIZER_VALIDATION.md`

## Estimated Effort
Very Large — 5 independent predictive models (~600 lines each), API endpoints, UI integration. Pure Python math (no ML dependencies). ~3,500 lines total.
