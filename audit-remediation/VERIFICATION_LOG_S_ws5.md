# Verification Log — fix/ws5-detection-intelligence

**Session:** WS5 (Detection / Intelligence Correctness; WS1–WS4 merged, WS4 = PR #136)
**Date:** 2026-06-02
**Agent:** Claude Opus 4.8 (1M) — implementer (I implement with TDD; a separate read-only Workflow verifies)
**Branch base:** `origin/main` `0852199` (Merge PR #138 phantom-db-path-connect-guard)

---

## Working model

- **Isolation:** WS5 is implemented in a DEDICATED git worktree at `/Users/molhamhomsi/clawd/ws5-worktree` on branch `fix/ws5-detection-intelligence`, branched off `origin/main` (`0852199`). The MAIN checkout (`/Users/molhamhomsi/clawd/moh_time_os`) is on another chip's branch (`feat/collector-status-entry-recovery`, `95ff75e`) with that chip's WIP and the LIVE daemon's WorkingDirectory — left UNTOUCHED. Forbidden files (tests/conftest.py, tests/test_determinism_guards.py, tests/test_xero_collector_expansion.py) are NOT edited.
- **Interpreter:** tests run with the main checkout's venv by absolute path: `/Users/molhamhomsi/clawd/moh_time_os/.venv/bin/python3 -m pytest`. First-party source resolves from the worktree, deps from the main `.venv` (ruff 0.15.1 == pinned).
- **HARD OVERRIDES applied:** (1) ADR number is **0028** (0026=WS3, 0027=WS2 taken on disk — verified `ls docs/adr/`). (2) `MOH_INTELLIGENCE_FULL_MODE` defaults **OFF** (daemon default unchanged quick=True); test proves default OFF. (3) bulk call uses `num_windows=12` (matches `portfolio_health_trajectory`'s windows=12, NOT the method default 6).

---

## Baseline (origin/main 0852199) — captured BEFORE any edit

| Suite | Result | Notes |
|-------|--------|-------|
| `tests/test_trajectory.py` | **70 passed, 1 failed** | `test_portfolio_health_trajectory_error_handling` FAILS pre-existing: it raises bare `Exception("DB error")` from `client_portfolio_overview`, which `except (sqlite3.Error, ValueError, OSError)` does NOT catch → propagates. This is a pre-existing failure on origin/main, NOT a WS5 regression. (Full-suite baseline captured at PHASE 4.) |

---

## Pre-Edit Verification

For EVERY method call added or modified, one row. Filled BEFORE each edit.

### Task 1 — Bulk-migrate portfolio_health_trajectory

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/intelligence/trajectory.py (`client_full_trajectory` +`traj` param) | `self.engine.client_deep_profile` | query_engine.py:304 | yes — `(self, client_id) -> dict\|None` | yes (`.get("client_name")`) | only intra-method; `traj=None` path identical to before |
| lib/intelligence/trajectory.py (`client_full_trajectory`) | `self.engine.client_trajectory` | query_engine.py:842 | yes — `(self, client_id, window_size_days=30, num_windows=6) -> dict` shape `{...,windows,trends}` | yes (`traj["windows"]` :603,:663) | called only when `traj is None` (fallback) |
| lib/intelligence/trajectory.py (`portfolio_health_trajectory`) | `self.engine.client_portfolio_overview` | query_engine.py:177 | yes — `(self, order_by="total_tasks", desc=True) -> list[dict]` w/ `client_id` | yes (`client["client_id"]`) | unchanged usage |
| lib/intelligence/trajectory.py (`portfolio_health_trajectory`) | `self.engine.bulk_client_trajectories` | query_engine.py:933 | yes — `(self, window_size_days=30, num_windows=6) -> dict[str,dict]`; each value `{client_id,window_size_days,num_windows,windows,trends}` | yes — `bulk_map.get(client_id)` → dict w/ `windows` consumed by client_full_trajectory; **MUST pass num_windows=12** to match windows=12 | sole new caller; bulk_client_trajectories signature NOT changed |
| lib/intelligence/trajectory.py (`portfolio_health_trajectory`) | `self.client_full_trajectory` | trajectory.py:564 (this PR adds `traj=`) | yes — `(self, client_id, windows=12, traj=None) -> FullTrajectory\|None` | yes (`if traj: results.append`) | sole caller is portfolio_health_trajectory + 3 external callers that pass only `client_id` (autonomous_loop:714, unified_intelligence:276,435) — all use `traj=None` default, unaffected |

**Regression risk identified (TDD pre-analysis):** existing `tests/test_trajectory.py::test_portfolio_health_trajectory` (:625) mocks `client_trajectory` but NOT `bulk_client_trajectories`. After Task 1, `portfolio_health_trajectory` calls `bulk_client_trajectories` (auto-Mock) → `bulk_map.get(cid)` returns a truthy Mock → `client_full_trajectory` hits `traj["windows"]` → `TypeError` (uncaught by the sqlite3/ValueError/OSError except) → net-new test ERROR. MUST update that test to mock `bulk_client_trajectories`. This is a necessary regression fix (keeps test_trajectory.py green), not scope creep — documented per WS4 precedent of correcting plan-test bugs TDD surfaces.

### Task 2 — Typed TrajectoryComputationError

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/intelligence/errors.py (Create) | `class IntelligenceError(OSError)` / `class TrajectoryComputationError(IntelligenceError)` | errors.py (new) | yes — MRO: TrajectoryComputationError → IntelligenceError → OSError | n/a (exception classes) | n/a |
| lib/intelligence/trajectory.py (`portfolio_health_trajectory` except) | `raise TrajectoryComputationError(...) from e` | errors.py | yes | raised, not returned | **all 3 external callers catch OSError** → `autonomous_loop.py:721` `except (sqlite3.Error, ValueError, OSError)`; `unified_intelligence.py:279` same tuple; `unified_intelligence.py:442` same tuple. TrajectoryComputationError(OSError) is caught by all three (PROVEN: live `try/except (sqlite3.Error, ValueError, OSError)` catches it). The raise is in the `except` block, so it propagates out (not re-caught by the same except). |

**Caller-catch proof (run live):** `raise TrajectoryComputationError('boom')` → `except (sqlite3.Error, ValueError, OSError) as e:` → CAUGHT (`type=TrajectoryComputationError`); `issubclass(TrajectoryComputationError, OSError) → True`. So no caller breaks — failures now log+surface there instead of being recorded as `trajectory_analyses=0`.

---

## Per-task evidence (fail→pass observed)

### Task 1 — Bulk-migrate portfolio_health_trajectory
- **Pre-edit baseline:** `test_trajectory.py` = 70 passed, 1 failed (pre-existing error_handling).
- **Step 2 FAIL (observed):** `test_client_full_trajectory_uses_prebuilt_traj` → `TypeError: client_full_trajectory() got an unexpected keyword argument 'traj'`; `test_portfolio_health_trajectory_calls_bulk_once` → `AssertionError: Expected 'bulk_client_trajectories' to be called once. Called 0 times.`
- **Step 4-5 PASS:** after adding `traj=` param + bulk migration (num_windows=12), both pass (2 passed). The RED step IS the mutation proof — without the bulk call, bulk_client_trajectories is called 0× and `traj=` raises TypeError.
- **Regression caught + fixed (as predicted):** full `test_trajectory.py` after edit = 2 failed (`test_portfolio_health_trajectory` NEW `TypeError: 'Mock' object is not subscriptable` + pre-existing error_handling). Updated `test_portfolio_health_trajectory` to mock `bulk_client_trajectories` (+ `client_trajectory.assert_not_called()`). Re-run = **70 passed, 1 failed** = EXACTLY the origin/main baseline. Net-new failures = 0.
- Files: lib/intelligence/trajectory.py, tests/test_trajectory_bulk.py, tests/test_trajectory.py. ruff clean.

### Task 2 — Typed TrajectoryComputationError
- **Step 2 FAIL (observed):** both Task-2 tests → `ModuleNotFoundError: No module named 'lib.intelligence.errors'`.
- **Step 4-5 PASS:** after creating errors.py + import + raise, all 4 tests in test_trajectory_bulk.py pass.
- **Caller-catch proof:** see Pre-Edit table above — TrajectoryComputationError(OSError) caught by all 3 callers' exact tuple.
- **Regression PROVEN pre-existing (not mine):** `test_trajectory.py` + `test_unified_intelligence.py` after edit = 5 failed, 99 passed. The 4 `test_unified_intelligence.py` failures (`test_run_scenario_error_handling`, `test_run_intelligence_cycle_pattern_detection_error`, `test_run_intelligence_cycle_correlation_error`, `test_get_client_intelligence_error_handling`) DO NOT touch trajectory (grep-confirmed) and raise bare `Exception("Scenario engine failed")`. Ran all 4 on a pristine baseline worktree (`/Users/molhamhomsi/clawd/ws5-baseline` @ origin/main `005956b`) → **4 failed identically**. PROVEN pre-existing. The 5th (`test_portfolio_health_trajectory_error_handling`) is the pre-existing bare-Exception failure (also unaffected — bare Exception isn't in the catch tuple, so the typed-raise never fires for it).
- Files: lib/intelligence/errors.py (new), lib/intelligence/trajectory.py, tests/test_trajectory_bulk.py. ruff clean.

**Note on origin/main movement:** baseline advanced `0852199` → `005956b` (PR #139 `feat/collector-status-entry-recovery` merged mid-session). The PHASE-4 regression comparison uses `005956b` (current origin/main). Will rebase onto current origin/main before pushing.

### Task 3 evidence (fail→pass observed)
- **PLAN-TEST BUG caught by TDD:** plan's test imported `from lib.daemon import Daemon` → `ImportError: cannot import name 'Daemon'`. The class is **`TimeOSDaemon`** (daemon.py:142), not `Daemon`. Fixed the test helper. (Same class of plan-test bug WS4 hit with `CapacityCommandPage7Engine`.)
- **Step 2 FAIL (observed, post-fix):** `test_full_mode_env_runs_quick_false` → `AssertionError: assert True is False` (daemon hardcodes `quick=True`). `test_default_mode_is_quick` + `test_explicit_zero_is_quick` PASS pre-change (today's default IS quick=True) — proving the change preserves default-OFF.
- **Step 4 PASS:** after `quick=not full_mode` (env read at call time), all 3 pass. RED step is the mutation proof (revert → full-mode test fails).
- **CALL-TIME read proven:** same daemon process, two test invocations with different env (unset vs "1") yield different `quick` → env is NOT import-frozen.
- **Regression PROVEN pre-existing (vs baseline 005956b, identical per-file):** test_daemon_intelligence.py 11 failed/1 passed (BOTH — root cause `AttributeError: 'AutonomousLoop' object has no attribute 'cycle_count'`, unrelated to mode switch); test_daemon_resilience.py 1 failed/19 errors (BOTH); test_daemon_state_atomic.py 2 passed; test_daemon_status.py 4 passed. Net-new daemon failures = 0.
- Files: lib/daemon.py, tests/test_daemon_intelligence_mode.py. ruff clean; bandit clean.

### Task 3 — MOH_INTELLIGENCE_FULL_MODE switch (DEFAULT OFF)

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/daemon.py (`_handle_intelligence`) | `detect_all_signals(db_path_obj, quick=not full_mode)` | signals.py:1779 | yes — `(db_path=None, quick=False, categories=None) -> dict` | yes (`.get("signals", [])`) | sole scheduled caller is daemon `_handle_intelligence:582`; `quick` passed as keyword (test asserts `kwargs["quick"]`) |
| lib/daemon.py (`_handle_intelligence`) | `os.environ.get("MOH_INTELLIGENCE_FULL_MODE", "0")` | stdlib; `import os` ALREADY at daemon.py:24 (module-level) | yes | read AT CALL TIME inside the method (NOT import-time frozen) — matches existing idiom `os.environ.get("MOH_GCHAT_WEBHOOK_URL","")` at daemon.py:619 | n/a |
| lib/daemon.py (`_handle_intelligence`) | `self.logger.info(...)` | module-level `from lib import paths` daemon.py:33; logger set in __init__ | yes | mode logged before detection | n/a |

**Override applied:** default OFF. `full_mode = os.environ.get("MOH_INTELLIGENCE_FULL_MODE","0").strip().lower() in ("1","true","yes")`; unset/"0"/anything-else → False → `quick=not False = True` (today's exact behavior). **PLAN DEVIATION (idiomatic):** plan's Step 3 added a redundant local `import os` inside the method — DROPPED because `import os` is already module-level at daemon.py:24 (verified) and the existing env-switch idiom at :619 uses module-level `os` with no local import. Env read is still at call time (inside the method body), satisfying the no-import-time-freeze requirement.
**Test patch targets verified:** `detect_all_signals`/`update_signal_state` imported INSIDE `_handle_intelligence` (`from lib.intelligence.signals import ...`) → `monkeypatch.setattr("lib.intelligence.signals.detect_all_signals", ...)` is seen at call time. `ProposalService` defined at lib/v4/proposal_service.py:22, imported inside method → patch at definition module is seen. `TimeOSDaemon.__new__(TimeOSDaemon)` + `daemon.logger=MagicMock()` skips __init__ side effects; `paths.db_path()` runs for real (harmless, detect mocked).

### Task 4 — Delete portfolio-TREND dead code

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/intelligence/signals.py (`_evaluate_trend` portfolio branch) | DELETED `engine.portfolio_trajectory(window_size_days=, num_windows=)` | query_engine.py:1129 (still exists, just no longer called from this branch) | yes — the call removed; branch now `return None` immediately | n/a (return None unchanged) | `_evaluate_trend` (signals.py:1292); portfolio branch only reachable when entity_type=="portfolio"; the sole signal that hits it (`sig_portfolio_quality_declining`, signals.py:429) stays inert (returned None before too) |

**Task 4 evidence (fail→pass observed):**
- `engine.portfolio_trajectory` confirmed real method at query_engine.py:1129 (so `assert_not_called()` is meaningful, not a phantom); `_get_engine` at signals.py:899 (test patches it); `sig_portfolio_quality_declining` at signals.py:429 (stays inert).
- **Step 2 FAIL (observed):** `AssertionError: Expected 'portfolio_trajectory' to not have been called. Called 1 times. Calls: [call(window_size_days=30, num_windows=4), call().__bool__()]` — proves the dead call + the emptiness `if not trajectories` ran.
- **Step 4 PASS:** after deleting the call (branch → immediate `return None`), test passes. RED is the mutation proof.
- **Regression:** full `test_intelligence_signals.py` WS5 = **30 passed** vs baseline 005956b = **29 passed** (+1 = my new test, 0 regressions). The branch already returned None; only the wasted query was removed (zero output change).
- Files: lib/intelligence/signals.py, tests/test_intelligence_signals.py. ruff clean; bandit clean.

### Task 5 — ADR-0028 dual findings stores (OVERRIDE: 0028, not 0026)
- **Override applied:** ADR number **0028** (`ls docs/adr/` → highest on disk is 0027; 0026=WS3, 0027=WS2 taken). Created `docs/adr/0028-dual-findings-stores.md` (NOT the plan's `0026`). No `dual-findings` collision (grep = 1 file).
- **All factual claims verified before writing:** `TABLES["signal_state"]`=schema.py:1598; `TABLES["detection_findings"]`=:1649, preview=:1678. `lib/detectors/__init__.py:53` writes detection_findings; `lib/detectors/morning_brief.py:67,77,87` read it; api/server.py has 7 detection_findings refs. **Separation proven:** `grep -rn signal_state lib/detectors/` = EMPTY; `grep -rn detection_findings lib/intelligence/` = EMPTY → the two lineages never cross-write. Decision: keep separate; signal_state is canonical for active findings.
- Files: docs/adr/0028-dual-findings-stores.md (Create). Markdown only.

### Task 6 — signal_suppression fixture schema
- **Pre-verified:** `signal_suppressions`=schema.py:1879, `signal_dismiss_log`=:1893 (canonical TABLES defs); `create_fresh(conn)` builds all TABLES.

---

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | | |
| `ruff format --check` on changed files | | |
| `bandit -ll --skip B101,B608` on changed source files | | |
| `pytest` (WS5 + regression surface) | | |
| `check_mypy_baseline.py --strict-only` | | |
| Every method call in changed files resolves to a real `def` | | |
| Verification log included in `git add` | | |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| WS5 (one PR per plan, 6 tasks) | | |
