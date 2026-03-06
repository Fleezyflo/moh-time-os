# TASK: Verify IW-4.1, IW-5.1 (event hooks, integration validation)
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.28 | Status: PENDING

## Instructions
1. Read `tasks/TASK_IW_4_1_EVENT_HOOKS.md` — are intelligence event hooks wired?
2. `grep -rn 'on_signal\|on_pattern\|event_hook\|hook' lib/intelligence/` — check for hook system
3. Read `tasks/TASK_IW_5_1_INTEGRATION_VALIDATION.md` — full wiring integration test
4. Check if `IntelligenceEventStore` (in persistence.py) connects events to downstream consumers

## Acceptance Criteria
- [ ] Report: event hooks exist or GAP; integration validated or GAP
