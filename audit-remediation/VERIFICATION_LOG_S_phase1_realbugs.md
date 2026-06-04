# Verification Log — Phase 1a real-bug fixes (one PR each)

**Session:** phase1-realbugs (2026-06-04)
**Base:** origin/main @ 8ea24b8
**Driver:** triage report audit-remediation/TEST_SUITE_TRIAGE_2026-06-04.md

Each bug is its own branch + PR (One-PR-One-Purpose). This log accumulates per-bug Pre-Edit/Pre-Commit rows.

---

## BUG-3 — threshold_adjuster calls nonexistent `day_context()`  [branch: fix/threshold-adjuster-day-context]

### Root cause
`lib/intelligence/threshold_adjuster.py:198,249` call `self._calendar.day_context(ref_date)`.
`self._calendar` is a `BusinessCalendar` (threshold_adjuster.py:162). `BusinessCalendar` defines
`get_day_context(d)` (temporal.py:161) returning `DayContext` with `.is_ramadan` (temporal.py:193) —
there is NO `day_context` method anywhere (grep: 0 `def day_context`; the only 2 `.day_context(`
call sites are these two bugs). Production-reachable: `ThresholdAdjuster` is used by
`calibration_reporter.py`. Crashes `run_adjustment_cycle` + `get_seasonal_modifiers` whenever
Ramadan-modifier logic runs.

### Fix
`day_context` → `get_day_context` at both production call sites (threshold_adjuster.py:198, 249).
The `.is_ramadan` access on the returned `DayContext` is already correct. ALSO: the 5 test patch
sites in `tests/test_adaptive_thresholds.py` (lines 248,264,278,291,431) used `patch.object(...,
"day_context", return_value=Mock(is_ramadan=...))` — they mocked the same wrongly-named method.
Updated all 5 to `"get_day_context"` so the mock intercepts the now-correct call. This is part of
the same single defect (production + tests both encoded the wrong method name).

### Pre-Edit Verification
| File edited | Method called | Defined at | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|-----------|--------------------|--------------------------|-----------------|
| threshold_adjuster.py:198,249 | `BusinessCalendar.get_day_context(d: date\|None)` | temporal.py:161 | yes — takes a `date`; `ref_date` is a `date` | yes — returns `DayContext` with `.is_ramadan` (temporal.py:193) | yes — only callers of these adjuster methods are calibration_reporter.py + tests; `.day_context(` appears nowhere else |

### Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before fix, on main) | CONFIRMED | `13 failed, 11 passed` test_adaptive_thresholds |
| TDD green (after fix) | PASS | `24 passed` test_adaptive_thresholds |
| ruff check (threshold_adjuster.py) | PASS | `All checks passed!` |
| ruff format --check | PASS | `1 file already formatted` |
| bandit | PASS | exit 0 |
| no regressions (temporal + calendar + recency + lifecycle scope) | PASS | `126 passed` across 6 files |

Files in this commit: `lib/intelligence/threshold_adjuster.py`, `tests/test_adaptive_thresholds.py`, this log. One purpose (BUG-3). Does NOT touch other bugs.
