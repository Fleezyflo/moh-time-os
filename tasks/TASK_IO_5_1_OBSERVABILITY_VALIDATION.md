# IO-5.1: Observability Validation

## Objective

End-to-end validation of intelligence observability pipeline: audit trail captures correctly, explainer produces meaningful output, drift detection identifies real drift, debug mode works.

## Test Files

### `tests/test_intelligence_audit.py` (~120 lines)
- trace() records inputs and outputs correctly
- trace() captures duration within 10% accuracy
- trace() records errors on exception
- get_entity_audit returns filtered results
- get_cycle_audit aggregates correctly
- cleanup removes old entries, keeps recent
- Large inputs/outputs truncated to size limit

### `tests/test_explainer.py` (~130 lines)
- Score change with clear driver produces correct explanation
- Score change with multiple drivers lists them by impact
- Signal explanation includes threshold vs actual
- Pattern explanation lists contributing signals
- Proposal explanation traces to triggers
- Entity with no changes produces "stable" explanation
- Entity with missing data produces quality warning
- Explanation text is human-readable (no raw IDs or technical jargon)

### `tests/test_drift_detector.py` (~100 lines)
- Score clustering detected when scores converge (stdev < 10)
- Score clustering NOT detected when distribution is healthy
- Signal noise detected when >60% firing rate
- Signal noise NOT detected at normal firing rate
- Pattern staleness detected for N consecutive unchanged cycles
- Full drift scan produces actionable recommendations

### `tests/test_debug_mode.py` (~100 lines)
- trace_entity returns all steps
- Each step includes metrics and duration
- Failed step doesn't block subsequent steps
- trace_signal shows evaluation detail
- trace_pattern shows component analysis
- Nonexistent entity returns informative error

### Integration: `tests/test_observability_pipeline.py` (~80 lines)
- Seed DB with entity that has declining score
- Run intelligence phase with auditor
- Verify audit trail captures all computations
- Run explainer on entity — verify explanation matches audit data
- Run drift scan — verify no false drift on single cycle
- Run debug trace — verify all steps match audit

## Validation

- All tests pass
- No test uses live DB
- Audit → Explain → Drift → Debug chain is coherent
- Edge cases: empty DB, entity with no history, entity with perfect data

## Estimated Effort

~530 lines across 5 test files
