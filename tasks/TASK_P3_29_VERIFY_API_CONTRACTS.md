# TASK: Verify IA-4.1 through IA-6.1 (API endpoints, contract tests)
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.29 | Status: PENDING

## Instructions
1. Read `tasks/TASK_IA_4_1_SIGNAL_PATTERN_ENDPOINTS.md` — do signal/pattern endpoints exist in `api/intelligence_router.py`?
2. Read `tasks/TASK_IA_5_1_SCENARIO_TRAJECTORY_ENDPOINTS.md` — do scenario/trajectory endpoints exist? (Likely NO until P1-7 is done)
3. Read `tasks/TASK_IA_6_1_API_CONTRACT_TESTS.md` — are there contract tests? `grep -rn 'contract\|schema.*test\|response.*shape' tests/`
4. List all routes in intelligence_router.py and their status

## Acceptance Criteria
- [ ] Route inventory with DONE/MISSING per endpoint
- [ ] Contract test status: exist or GAP
