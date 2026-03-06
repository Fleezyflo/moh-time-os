# TASK: Verify AT workstream (adaptive thresholds)
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.14 | Status: PENDING

## Context

`lib/calibration.py` (196 lines) exists and is wired. But AT-2.1 through AT-5.1 describe a much more elaborate system: threshold adjustment engine, seasonal modifiers, calibration reporting.

## Instructions
1. Read ALL AT task specs: `TASK_AT_2_1_THRESHOLD_ADJUSTMENT_ENGINE.md`, `TASK_AT_3_1_SEASONAL_CONTEXTUAL_MODIFIERS.md`, `TASK_AT_4_1_CALIBRATION_REPORTING.md`, `TASK_AT_5_1_ADAPTIVE_THRESHOLD_VALIDATION.md`
2. Compare requirements against `lib/calibration.py` capabilities
3. Identify what calibration.py covers vs. what's missing
4. Create follow-up tasks for gaps (likely: threshold adjustment engine, seasonal modifiers, calibration dashboard)

## Acceptance Criteria
- [ ] Gap analysis: what AT specs require vs. what calibration.py provides
- [ ] Follow-up tasks for each gap
