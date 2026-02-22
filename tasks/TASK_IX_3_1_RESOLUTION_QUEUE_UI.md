# IX-3.1: Resolution Queue Interface

## Objective
Build an interactive UI for the resolution queue — view pending items, approve/reject automated actions, review history, and monitor automation performance.

## Context
IE-6.1 builds the resolution queue automation backend. This task provides the human interface for oversight and decision-making. The queue should make Molham's decision workflow efficient: see what needs attention, act on it, move on.

## Implementation

### Views

**Pending Queue**:
- List of unresolved items sorted by severity (critical → warning → info)
- Each item shows: type, entity, age, severity badge, recommended action
- Action buttons: Approve (execute recommendation), Dismiss, Escalate, Snooze
- Bulk actions: approve all info-level, dismiss all older than X days

**Item Detail**:
- Full context: pattern signals that triggered this item
- History: when created, who/what acted on it, status changes
- Related items: other queue items for same entity
- Raw data: links to underlying signals and insights

**History**:
- Resolved items with outcome (approved, dismissed, auto-resolved)
- Time to resolution metrics
- Automation success rate per type

**Automation Dashboard**:
- Per-automation stats: triggered count, success rate, average resolution time
- Recent automation executions with pass/fail
- Circuit breaker status per automation

### API Endpoints Needed
```
GET  /api/v1/resolution/pending         — list pending items
GET  /api/v1/resolution/{id}            — item detail
POST /api/v1/resolution/{id}/approve    — approve recommended action
POST /api/v1/resolution/{id}/dismiss    — dismiss item
POST /api/v1/resolution/{id}/escalate   — escalate to higher priority
GET  /api/v1/resolution/history         — resolved items
GET  /api/v1/resolution/stats           — automation performance
```

## Validation
- [ ] Pending queue displays all unresolved items
- [ ] Approve action triggers the recommended automation
- [ ] Dismiss removes from pending without executing
- [ ] History shows resolved items with timestamps
- [ ] Automation stats are accurate
- [ ] Responsive on tablet

## Files Created/Modified
- `frontend/resolution.js` — resolution queue UI
- `api/server.py` — add resolution endpoints

## Estimated Effort
Medium — ~300 lines frontend + ~150 lines API endpoints
