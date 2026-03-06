# TASK: Verify PH-3.1 brand ID population
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.01 | Status: PENDING

## Context

Task spec `TASK_PH_3_1_POPULATE_BRAND_IDS.md` describes populating `brand_id` in the clients table. Need to verify this was done.

## Objective

Confirm `brand_id` gets populated in the clients table during collection/sync.

## Instructions

1. Read `tasks/TASK_PH_3_1_POPULATE_BRAND_IDS.md` for full requirements
2. `grep -rn 'brand_id' lib/ api/` — find where brand_id is set
3. Check schema.py for `brand_id` column definition
4. Check collectors for brand_id population logic
5. If NOT done: create a follow-up task brief with the gap

## Acceptance Criteria
- [ ] Report: DONE (with evidence) or GAP (with follow-up task)
