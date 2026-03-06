# TASK: Verify CI-2.1, CI-4.1 (cross-domain synthesis, conversational UI)
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.18 | Status: PENDING

## Context

`lib/intelligence/conversational_intelligence.py` (971 lines) exists. Need to verify it's wired.

## Instructions
1. Read `tasks/TASK_CI_2_1_CROSS_DOMAIN_SYNTHESIS.md`
2. `grep -rn 'conversational_intelligence' lib/ api/` — check if wired
3. Read `tasks/TASK_CI_4_1_CONVERSATIONAL_UI_VALIDATION.md` — manual validation task
4. Check if chat commands use conversational_intelligence for cross-domain answers

## Acceptance Criteria
- [ ] Report: DONE or GAP
