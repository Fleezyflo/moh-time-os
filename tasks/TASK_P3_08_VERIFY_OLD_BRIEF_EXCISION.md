# TASK: Verify UR-1.2 old morning brief excision
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.08 | Status: PENDING

## Context

Task spec `TASK_UR_1_2_EXCISE_MORNING_BRIEF.md` describes removing the old morning brief. Phase 15e replaced it with `lib/detectors/morning_brief.py`.

## Instructions

1. Read `tasks/TASK_UR_1_2_EXCISE_MORNING_BRIEF.md`
2. `grep -rn 'morning.*brief\|daily.*brief\|send_brief' lib/ api/ engine/` — find old references
3. Check if old code still exists alongside the new Phase 15e implementation
4. If old code remains: it should be removed

## Acceptance Criteria
- [ ] Report: DONE or GAP (old code still present)
