# ADR-0015: Detection System API Endpoints

**Date:** 2026-03-03
**Status:** Accepted
**Context:** Phase 15c

## Decision

Add 8 detection system API endpoints to api/server.py and micro-sync helpers to lib/collectors/all_users_runner.py, enabling the UI to display findings, week strip, staleness, and weight review data.

## Changes

### API (api/server.py)
- `GET /api/command/week-strip` -- 10-day array with available minutes, tasks due, weighted ratio, collision flag
- `GET /api/command/findings` -- active findings grouped by correlation, with acknowledged/suppressed/team sections
- `GET /api/command/findings/{id}?refresh=true` -- single finding detail with optional calendar+email micro-sync
- `POST /api/command/findings/{id}/acknowledge` -- mark finding as acknowledged
- `POST /api/command/findings/{id}/suppress` -- suppress finding for 30 days
- `GET /api/command/staleness` -- detection freshness status
- `GET /api/command/weight-review` -- pending weight confirmations
- `POST /api/command/weight-review/{task_id}` -- confirm or correct task weight

### Micro-Sync (lib/collectors/all_users_runner.py)
- `micro_sync_calendar()` -- scoped calendar sync via CalendarCollector for one user
- `micro_sync_gmail()` -- scoped gmail sync via GmailCollector for one user
- Both persist data through the full collect-transform-store pipeline
- Asana is explicitly excluded from micro-sync (task data from last scheduled collection)

## Rationale

The detection system (collision, drift, bottleneck detectors from Phase 15b) needs API endpoints to serve findings to the Command Center UI. Micro-sync enables on-demand data refresh when viewing finding details, providing fresher calendar/email data without running a full collection cycle. ADR required because api/server.py is a governance-trigger file.
