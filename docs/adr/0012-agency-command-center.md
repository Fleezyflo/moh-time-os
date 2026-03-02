# ADR-0012: Agency Command Center

**Date:** 2026-03-02
**Status:** Accepted
**Context:** Session 21

## Decision

Add an Agency Command Center with three executive views (Client Health, Team Load, Decision Queue) to give the agency executive a single surface for answering: which clients need attention, who on the team is overloaded, and what decisions are waiting on me.

## Changes

### Backend
- `lib/command_center.py` (new, ~655 lines): Three view classes — ClientHealthView, TeamLoadView, DecisionQueueView. Each queries the existing database (tasks, projects, events, team_members, commitments, signals) and computes health/load status with clear thresholds.
- `api/server.py` (modified): 5 new endpoints under `/api/command/*` — client-health, client-health/{id}, team-load, team-load/{name}, decisions.

### Frontend
- `time-os-ui/src/pages/CommandCenter.tsx` (new, ~528 lines): Three-tab page using existing layout components (PageLayout, SummaryGrid, MetricCard). Self-contained fetch hook to avoid modifying shared hooks.ts.
- `time-os-ui/src/router.tsx` (modified): Added /command route and nav item.

### Data fixes
- `scripts/fix_project_lanes.py` (new): Sets is_internal flag on projects matching internal patterns, then runs lane_assigner.run_assignment() to categorize all tasks out of the default "ops" lane.

### Pipeline
- `lib/autonomous_loop.py` (modified): Wired CalendarSync.ensure_blocks_for_week() into Phase 1a1 between COLLECT and DATA NORMALIZATION.

## Rationale

Previous Time & Capacity pages were designed for an individual contributor. Database investigation revealed the actual use case: an agency executive managing 31 team members across 20+ clients. The Command Center provides the executive-level views needed for that workflow.
