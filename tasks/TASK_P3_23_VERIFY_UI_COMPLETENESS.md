# TASK: Verify IX-3.1 through IX-6.1 (UI completeness)
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.23 | Status: PENDING

## Context

21 UI pages exist. DataQuality.tsx (72 lines), Notifications.tsx (82 lines), Approvals.tsx (92 lines) are FUNCTIONAL (not stubs — they use real hooks, components, API calls). But some expected pages may be missing.

## Instructions
1. Read `tasks/TASK_IX_3_1_RESOLUTION_QUEUE_UI.md` — no dedicated ResolutionQueue page exists. Check if it's embedded in CommandCenter or Priorities.
2. Read `tasks/TASK_IX_4_1_SCENARIO_MODELING_UI.md` — no dedicated scenario page exists. May need new page after P1-7 wires the backend.
3. Read `tasks/TASK_IX_5_1_REALTIME_UPDATES.md` — check for WebSocket/SSE in the UI codebase: `grep -rn 'WebSocket\|EventSource\|SSE\|useWebSocket' time-os-ui/src/`
4. Read `tasks/TASK_IX_6_1_UI_VALIDATION.md` — manual validation task

## Acceptance Criteria
- [ ] Report per sub-task: DONE, EMBEDDED (in another page), or MISSING
