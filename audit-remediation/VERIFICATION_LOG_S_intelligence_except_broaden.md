# Verification Log — fix/intelligence-except-resilience

**Session:** intelligence-except-broaden (2026-06-03)
**Date:** 2026-06-03
**Agent:** Claude Opus 4.8 (1M)

---

## Root cause (Phase 1 — systematic-debugging)

Commit `641754c` ("fix: phase -1 backend cleanup", 2026-02-26) bulk-narrowed **593**
`except Exception` blocks to `except (sqlite3.Error, ValueError, OSError)`. Three intelligence
modules' **outer method-level resilience boundaries** were among them. The original code
(introduced in `e8b334e`, the SAME commit that added the tests) was `except Exception as e:`
with `logger.error(...); return None` — a compliant log-and-return-typed-null pattern, NOT a
banned silent swallow.

The 6 failing tests assert that an *arbitrary* downstream failure (mock `side_effect =
Exception("DB error")`) is caught, logged, and a typed-null/error returned. Bare `Exception`
is not a subclass of the narrow tuple, so it propagates past the `except` and the test's
`result = ...` assignment raises.

Evidence:
- `git log -L` on all three files shows `e8b334e` introduced `except Exception` + the tests;
  `641754c` narrowed it. (See investigation in session transcript.)
- 12 broad `except Exception as e:` catches still exist in `lib/` (command_center.py,
  action_framework.py, db_adapter.py, …) — broad-catch-with-log is an accepted repo convention.
- No test in the 3 files asserts the narrow contract; the only `pytest.raises` are for
  `FileNotFoundError` in `__init__` (deliberate fail-fast, NOT touched).

**Decision: option (b)** — restore broad `except Exception as e:` (keeping `log + typed-null/error
return`) at the **outer method-level resilience boundaries** in the 3 files. Nested best-effort
sub-fetch handlers (`logger.debug`/`logger.warning`-and-continue) stay narrow — they catch a
*known* concrete query's errors by design. `__init__` `FileNotFoundError` fail-fast stays.

CLAUDE.md compliance: the rule bans `except Exception: pass` (silent) and `return {}`/`return []`
*on failure*. These handlers log with `exc_info` and return `None` / `{"error": str(e)}` / a
degraded typed dataclass — all compliant.

---

## Pre-Edit Verification

These edits change ONLY the exception type in `except (...) as e:` clauses to `except Exception
as e:`. No method calls are added or changed; the `e` variable remains used (logged) in every
handler. Therefore the "method call resolves to a real def" columns are N/A — no new calls.

| File edited | Handler (method) | Line (pre-edit) | Role | Returns on catch | Action |
|-------------|------------------|-----------------|------|------------------|--------|
| scenario_engine.py | model_client_loss | 283 | outer | `None` | broaden |
| scenario_engine.py | model_client_addition | 425 | outer | `None` | broaden |
| scenario_engine.py | model_resource_change | 502 | outer | `None` | broaden |
| scenario_engine.py | model_pricing_change | 873 | outer | `None` | broaden |
| scenario_engine.py | model_capacity_shift | 968 | outer | `None` | broaden |
| scenario_engine.py | model_workload_rebalance | 1079 | outer | `None` | broaden |
| scenario_engine.py | compare_scenarios | 1148 | outer | `None` | broaden |
| cost_to_serve.py | compute_client_cost (inner avg_task_duration) | 230 | nested best-effort | (continues) | KEEP narrow |
| cost_to_serve.py | compute_client_cost | 261 | outer | `None` | broaden |
| cost_to_serve.py | compute_project_cost (inner avg_completion) | 314 | nested best-effort | (continues) | KEEP narrow |
| cost_to_serve.py | compute_project_cost | 333 | outer | `None` | broaden |
| cost_to_serve.py | compute_portfolio_profitability (inner percentiles) | 374 | nested best-effort | (fallback) | KEEP narrow |
| cost_to_serve.py | compute_portfolio_profitability | 443 | outer | `None` | broaden |
| cost_to_serve.py | get_hidden_cost_clients | 511 | outer | `[]` (no-clients path is separate; catch path is error) | broaden |
| cost_to_serve.py | get_profitability_ranking | 549 | outer | `[]` (same) | broaden |
| unified_intelligence.py | _get_correlation_engine | 162 | init log+reraise | re-raises | broaden |
| unified_intelligence.py | _get_cost_engine | 172 | init log+reraise | re-raises | broaden |
| unified_intelligence.py | _get_trajectory_engine | 182 | init log+reraise | re-raises | broaden |
| unified_intelligence.py | _get_scenario_engine | 192 | init log+reraise | re-raises | broaden |
| unified_intelligence.py | run_intelligence_cycle step1 patterns | 227 | outer sub-step | error dict | broaden |
| unified_intelligence.py | run_intelligence_cycle step2 correlation | 251 | outer sub-step | error dict | broaden |
| unified_intelligence.py | run_intelligence_cycle step3 cost | 268 | outer sub-step | error dict | broaden |
| unified_intelligence.py | run_intelligence_cycle step4 trajectory | 279 | outer sub-step | `[]` | broaden |
| unified_intelligence.py | run_intelligence_cycle (cycle-level) | 307 | outer | degraded result (grade F) | broaden |
| unified_intelligence.py | get_client_intelligence (inner trajectory) | 354 | nested best-effort | (continues) | KEEP narrow |
| unified_intelligence.py | get_client_intelligence (inner patterns) | 373 | nested best-effort | (continues) | KEEP narrow |
| unified_intelligence.py | get_client_intelligence | 398 | outer | partial intel | broaden |
| unified_intelligence.py | get_portfolio_dashboard (inner trajectory) | 442 | nested best-effort | (continues) | KEEP narrow |
| unified_intelligence.py | get_portfolio_dashboard | 473 | outer | partial dashboard | broaden |
| unified_intelligence.py | run_scenario | 550 | outer | error dict | broaden |
| unified_intelligence.py | _build_cycle_summary | 582 | outer | fallback summary | broaden |

Net: broaden 24 outer/init handlers; KEEP 6 nested best-effort + 2 `__init__` FileNotFoundError narrow.

NOTE on `get_hidden_cost_clients` / `get_profitability_ranking` returning `[]`: this is the
**error-path** catch, where the original `e8b334e` code returned `[]` after logging the error.
The CLAUDE.md "no `return []` on failure" rule targets *masking errors as no-data*; here the
return is logged with `exc_info=True` and the function's no-data path (empty portfolio) is a
*separate* explicit `return []` with a `logger.warning`. The pre-641754c code already did this;
broadening the catch type does not change the `[]` return. Not expanding scope to refactor those
returns (out of scope; would be a different PR).

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` (after removing now-dead `import sqlite3` from scenario_engine.py — F401) |
| `ruff format --check` on changed files | PASS | `3 files already formatted` |
| `bandit` on changed files | PASS | exit 0, no findings |
| `pytest` 6 target tests | PASS | `6 passed in 0.15s` |
| `pytest` full intelligence scope (test_unified_intelligence + test_cost_to_serve + test_scenario_engine + test_scenario_ui) | PASS | `140 passed in 0.29s` |
| Regression isolation (stash my edits → run the 21 other-module failures on pristine main) | PRE-EXISTING | `21 failed, 34 passed` WITH and WITHOUT my changes — identical; my edit caused 0 regressions. Failing files (test_correlation_confidence/intelligence_engine/intelligence_api) do NOT import my 3 modules. |
| No-bypass check (no `noqa`/`nosec`/`type: ignore` added) | PASS | grep → none |
| Every method call in changed files resolves to a real `def` | N/A | no calls added; only `except` type changed + 1 import removed |
| Verification log included in `git add` | YES | in commit block below |

### Pre-existing failures (out of scope — flagged, NOT fixed here)
21 tests fail on pristine `main` HEAD, unrelated to this PR (they test `lib/intelligence/engine.py`,
correlation-confidence scoring, intelligence_api — none import the 3 files changed here). They are
NOT in CI's Python Tests gate (CI runs only tests/contract, test_safety, auth, negative, golden,
ui_spec_v21, property — not these top-level intelligence tests), which is why `main` is green.
Recommend a separate task. Files: test_correlation_confidence.py, test_intelligence_engine.py,
test_intelligence_api.py.

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Restore intelligence resilience contract (641754c regression) | scenario_engine.py, cost_to_serve.py, unified_intelligence.py, this log | yes — one purpose |

This commit does NOT touch the trajectory perf work (PR #140, already merged) or any other concern.
