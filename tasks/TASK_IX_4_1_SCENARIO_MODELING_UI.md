# IX-4.1: Scenario Modeling Interface

## Objective
Build an interactive UI for the scenario modeling engine — select a scenario type, input parameters, and visualize projected impact on capacity, revenue, and team.

## Context
IE-3.1 builds the scenario engine backend. This task provides the interface for Molham to run "what-if" analyses before making business decisions.

## Implementation

### Scenario Selection
- Dropdown or card selection: Add Client, Remove Client, Lose Member, Add Member, Change Scope
- Each scenario type shows required input fields

### Input Forms

**Add Client**:
- Client name (text)
- Estimated weekly hours (slider: 5-40)
- Estimated monthly revenue (number)
- Communication volume estimate (low/medium/high)
- Meeting frequency (weekly/biweekly/monthly)

**Remove Client / Lose Member**:
- Select from existing clients/members (autocomplete dropdown)
- Optional: effective date

**Change Scope**:
- Select project
- Hours delta (positive or negative)

### Results Visualization

**Before/After Comparison**:
- Side-by-side capacity utilization bars
- Revenue impact (delta + new total)
- Cost impact (delta + new total)
- Affected projects/members list

**Risk Indicators**:
- Capacity warnings (anyone goes >90% utilization)
- Revenue concentration risk
- Single-point-of-failure warnings

**Confidence Meter**:
- Visual indicator of projection confidence
- Note on data quality factors

### API Endpoints
```
POST /api/v1/scenarios/simulate    — run scenario, return projections
GET  /api/v1/scenarios/history     — previous scenario runs
```

## Validation
- [ ] All 5 scenario types have working input forms
- [ ] Results display before/after comparison
- [ ] Capacity warnings trigger when utilization exceeds threshold
- [ ] Confidence indicator reflects actual data quality
- [ ] Previous scenarios accessible in history

## Files Created/Modified
- `frontend/scenarios.js` — scenario modeling UI
- `api/server.py` — add scenario endpoints

## Estimated Effort
Medium — ~250 lines frontend + ~100 lines API endpoints
