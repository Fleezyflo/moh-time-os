# TASK: Calibrate Signal Thresholds to Reduce Noise
> Brief: DATA_FOUNDATION | Phase: 3 | Sequence: 3.1 | Status: PENDING

## Context

The signal system has 809 signals with 728 active. The severity distribution is badly skewed:
- critical: 536 (66%)
- low: 149 (18%)
- medium: 103 (13%)
- high: 21 (3%)

The dominant signal type is `deadline_overdue` (532 signals, all critical). When 66% of signals are critical, the severity system provides no differentiation. This is partly a data problem (task due dates are stale — see DF-1.1) and partly a threshold calibration problem.

Threshold config exists at `lib/intelligence/thresholds.yaml`.

Signal definitions have `priority_weight = 0.6` uniformly across all 15 types — no differentiation.

## Objective

Recalibrate signal thresholds and priority weights so severity distribution is actionable: critical should be <10% of active signals, representing genuine emergencies.

## Instructions

1. Read `lib/intelligence/thresholds.yaml` — understand current threshold config.
2. Read `lib/intelligence/signals.py` — understand how signals are scored and severity is assigned.
3. Read `lib/intelligence/scoring.py` — understand the scoring pipeline.
4. Modify `thresholds.yaml`:
   - `deadline_overdue`: severity=critical only if overdue > 14 days AND priority >= 80. Else high (7-14d), medium (1-7d).
   - `ar_aging_risk`: critical if overdue > 90 days, high if 60-90, medium if 30-60.
   - `data_quality_issue`: max severity = medium (these are housekeeping, not operational emergencies).
   - `hierarchy_violation`: max severity = low.
5. Update `signal_definitions` table: differentiate `priority_weight`:
   - Deadline/commitment signals: weight=0.8
   - Client health signals: weight=1.0
   - Anomaly signals: weight=0.6
   - Protocol/data quality: weight=0.3
6. Create `lib/intelligence/recalibrate.py`:
   - `recalibrate_active_signals(db_path)`: Re-score all active signals with new thresholds
   - `signal_distribution_report(db_path)`: Print severity distribution before/after
7. Write tests covering threshold logic
8. Run: `pytest tests/ -q`

## Preconditions
- [ ] Phase 2 complete (task data is more accurate post-linking)
- [ ] Test suite passing

## Validation
1. After recalibration: critical signals < 20% of active total
2. `signal_distribution_report` shows a more balanced distribution
3. No signal type has uniform severity (spread across at least 2 levels)
4. All tests pass

## Acceptance Criteria
- [ ] `thresholds.yaml` updated with graduated severity rules
- [ ] `signal_definitions` priority_weight differentiated by category
- [ ] Recalibration function re-scores existing signals
- [ ] Post-calibration: critical < 20% of active signals
- [ ] All tests pass
- [ ] No guardrail violations

## Output
- Modified: `lib/intelligence/thresholds.yaml`
- New: `lib/intelligence/recalibrate.py`
- New: `tests/test_recalibrate.py`
- Modified: `signal_definitions` table data

## On Completion
- Update HEARTBEAT: Task DF-3.1 complete — Signal severity rebalanced, critical reduced from 66% to N%
- Record: signal distribution before/after

## On Failure
- If signal scoring is deeply embedded and can't be changed without cascading breaks, document the dependency chain in Blocked
