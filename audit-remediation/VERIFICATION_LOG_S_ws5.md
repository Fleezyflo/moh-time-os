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
- **Pre-verified:** `signal_suppressions`=schema.py:1879, `signal_dismiss_log`=:1893 (canonical TABLES defs); `create_fresh(conn: sqlite3.Connection) -> dict`=schema_engine.py:629 builds all TABLES; `SignalSuppression(db_path: Path)`=signal_suppression.py:85, `dismiss_signal`=:107; `import sqlite3` already at test file line 7.
- **[DECISION] honored:** fix in the FIXTURE (apply canonical schema via create_fresh), NOT self-provisioning in the constructor (would diverge from centralized-schema convention; live tables exist).
- **Step 1 FAIL (observed):** `sqlite3.OperationalError: no such table: signal_dismiss_log` at signal_suppression.py:124. Full file = **20 failed** (entire suite red — bare tmp_path DB has no schema).
- **Step 3 PASS:** after fixture applies create_fresh → **20 passed**. RED is the mutation proof (revert fixture → 20 fail on missing table). This FIXES 20 pre-existing failures (baseline 005956b: 20 failed → WS5: 20 passed).
- Files: tests/test_signal_suppression.py. ruff clean.

---

## Per-task summary

| Task | Files | Tests | Net effect vs baseline 005956b |
|------|-------|-------|--------------------------------|
| 1+2 (commit 2c9a76f) | trajectory.py, errors.py(new), test_trajectory_bulk.py(new), test_trajectory.py | test_trajectory_bulk 4 pass; test_trajectory 70 pass/1 pre-existing-fail | +4 new tests; test_trajectory unchanged (70/1) |
| 3 (commit b31d811) | daemon.py, test_daemon_intelligence_mode.py(new) | 3 pass | +3 new tests; daemon surface 0 net-new failures |
| 4 (commit 44fe704) | signals.py, test_intelligence_signals.py | 30 pass | +1 new test (29→30); 0 regressions |
| 5 (commit 9b48015) | docs/adr/0028-dual-findings-stores.md(new) | n/a | doc only |
| 6 (commit c81810d) | test_signal_suppression.py | 20 pass | FIXES 20 pre-existing failures (20 fail → 20 pass) |

---

## Adversarial verify Workflow round 1 (workflow wvvvscyk2, 20 read-only agents) — ALL 5 tasks PASS, 0/15 refutes

Independent verify (re-run suite + mutation-proof on /tmp copies) + 3 skeptics (correctness-regression / data-safety / spec-completeness) per committed task, read-only against the ws5 worktree using the existing main `.venv` by absolute path. NO `isolation:'worktree'` (would leak — .venv gitignored).

| Task | verify | mutation_proved | skeptic refutes | passed |
|------|--------|-----------------|-----------------|--------|
| T1-bulk-trajectory | pass | True | 0/3 | ✅ |
| T2-typed-error | pass | True | 0/3 | ✅ |
| T3-full-mode-switch | pass | True | 0/3 | ✅ |
| T4-dead-code | pass | True | 0/3 | ✅ |
| T6-suppression-fixture | pass | True | 0/3 | ✅ |

**Watch-items each independently cleared with live PoCs / /tmp mutations / git-diff proofs:**
- **num_windows=12 mismatch (T1):** verifier mutated /tmp copy (dropped `traj=`) → `client_trajectory.assert_not_called()` FAILED (called 2×) — test genuinely guards the fix. Literal `12` confirmed in BOTH source (trajectory.py:721,727) and test assertion; bulk default `6` (query_engine.py:934) is overridden → 12 is load-bearing. Absent-client fallback (bulk_map.get→None→per-entity traj=None path) proven intact. Skeptics: bulk_client_trajectories ALWAYS builds each value with the `windows` key (query_engine.py:1018-1034) → malformed-slice case unreachable.
- **typed error raises vs swallowed (T2):** /tmp mutation (revert raise→return []) → `pytest.raises(TrajectoryComputationError)` FAILS on mutant. MRO `TrajectoryComputationError→IntelligenceError→OSError` confirmed; caught at ALL caller sites (autonomous_loop.py:721, unified_intelligence.py:279,442) AND the daemon `_run_job` wrapper (daemon.py:476) → neither crashes the daemon nor silently logs as 0. client_full_trajectory still returns None on its own errors (unchanged).
- **default OFF + call-time env (T3):** two /tmp mutants (hardcode quick=True → full-mode test fails; hardcode quick=False → default test fails) — both wirings load-bearing. Single-process PoC: unset→True, =1→False, =0→True proves call-time read (not import-frozen). Class is `TimeOSDaemon` (daemon.py:142).
- **full-mode N×M safety (T3):** full-mode detect_all_signals primes the cache (signals.py:1800-1818); per-entity engine fallback gated behind `cache is None` → never hit on the daemon path; portfolio TREND returns None immediately. T1 is sufficient to make full mode safe.
- **T4 dead-code:** /tmp mutation (re-add the call) → `portfolio_trajectory.assert_not_called()` FAILS (called 1×). engine.portfolio_trajectory still exists at query_engine.py:1129 (only the call removed). Branch still returns None; client/person branches byte-identical.
- **T6 fixture-not-constructor:** `git diff main HEAD -- lib/intelligence/signal_suppression.py` EMPTY (source unchanged); fix is +13 lines in the fixture only. /tmp mutation (revert fixture) → `no such table: signal_dismiss_log`. 20/20 pass.

**No in-scope defect reproduced by any of the 15 skeptics.** All pre-existing failures the agents encountered (`test_portfolio_health_trajectory_error_handling` bare-Exception; 4 `test_unified_intelligence.py` engine errors; `test_audit_remediation_v4` orchestrator AttributeError) were independently re-proven pre-existing on main (byte-identical test files / identical failure on base) and correctly excluded as non-refutation grounds.

**One completeness nit (NOT a refute) → driven to a fix:** the correctness-regression skeptic for T1/T2 flagged that `test_portfolio_health_trajectory_error_handling` still asserted `result == []` (the OLD contract T2 removed) rather than `pytest.raises(TrajectoryComputationError)`. It was a pre-existing failure (bare `Exception` never in the catch tuple — fails on main too), but post-T2 the assertion documents a removed contract. **FIX-R1:** updated the test to use a realistic `sqlite3.OperationalError` and assert `pytest.raises(TrajectoryComputationError)` — aligning it with T2's contract AND turning the last pre-existing failure green. Mutation proof: revert T2's raise→return [] makes this test fail (function returns [] instead of raising). Folded into the T1+T2 commit (it is the T2 contract). After FIX-R1: `test_trajectory.py` = 71 passed / 0 failed; full WS5 surface = **128 passed / 0 failed**.

**Decision on rounds:** Round 1 returned 0/15 refutes with full skeptic coverage (subagent_tokens 1.58M, all 20 agents returned StructuredOutput — no harness starvation) and every watch-item cleared by an independent PoC. WS5 is far smaller/simpler than WS4 (no data-loss surfaces, no Xero/concurrency, no destructive SQL). The single nit was a stale-test alignment, not a code defect. Running a Round 2 after FIX-R1 to confirm the test change is itself sound and re-confirm 0 refutes on the now-zero-failure surface.

## Adversarial verify Workflow round 2 (workflow wc1im2q92, 20 read-only agents) — all 5 PASS 0/15 refutes; T1 lens caught a REAL in-scope PERF defect (PoC)

All 5 tasks `verify=pass`, `mutation_proved=True`, 0/15 refutes (FIX-R1 test alignment held; verifier mutated /tmp copy reverting raise→[] and confirmed it fails). Round 2's T1 mutation also proved num_windows=12 is load-bearing (mutated 12→6 → assertion FAILS). BUT the T1 correctness-regression skeptic, measuring on the LIVE DB, surfaced a **real in-scope defect with a measured PoC** (engineering correctness is not a majority vote — a lens with a working PoC wins, per the process):

- **FIX-R2 (PERF — the plan's HEADLINE goal only partially met; PoC reproduced):** `portfolio_health_trajectory()` measured **110.28s** on the live DB (134 clients), NOT the claimed ~0.1s. Decomposition: `bulk_client_trajectories` ALONE = 0.10s (the bulk fix works), but `client_full_trajectory` STILL called `client_deep_profile(client_id)` PER CLIENT (trajectory.py:590) = 108.36s for 134 clients — the SAME fresh-connection N-blowup (`QueryEngine._execute` opens a new read-only connection per call, query_engine.py:77; deep_profile fires 4 queries/client) the bulk fix's docstring claims to eliminate. The deep profile was fetched ONLY for `profile["client_name"]` (verified: `profile` used at trajectory.py:590,591,594 and NOWHERE else in the method). Since full mode (Task 3) re-hits this path, the plan's premise ("full mode safe now that portfolio_health_trajectory uses the bulk path") was NOT actually satisfied.
  - **Fix:** added `client_name: str | None = None` to `client_full_trajectory`; when supplied, the per-entity `client_deep_profile` lookup is SKIPPED (the existence check is unnecessary on the bulk path — the client came from `client_portfolio_overview()`, so it exists). `portfolio_health_trajectory` threads `client.get("client_name", client_id)` from the overview rows (which already carry `client_name`, query_engine.py:177-188). Direct callers (client_name=None) keep the per-entity deep-profile lookup + existence check unchanged.
  - **TDD:** Step-2 FAIL observed: `test_portfolio_health_trajectory_calls_bulk_once` → `client_deep_profile ... Called 2 times. Calls: [call('c1'), call('c2')]`; `test_client_full_trajectory_uses_supplied_client_name` → `TypeError: ... unexpected keyword argument 'client_name'`. Step-4 PASS after the fix. **Mutation proof = the RED step** (without client_name threading, deep_profile fires per client).
  - **Perf PROVEN on live DB (read-only timed run, signal.alarm guard):** `clients=134 trajectories=134 elapsed=0.15s` — down from 110.28s. The plan's ~0.1s headline goal is now actually met. Full mode is genuinely safe.
  - Files: lib/intelligence/trajectory.py, tests/test_trajectory_bulk.py. ruff clean. Full WS5 surface after FIX-R2 = **129 passed / 0 failed**.
  - Direct-caller regression: `test_client_full_trajectory_found` and the other TestFullTrajectory tests (client_name=None) still pass → the deep-profile + existence-check path is intact.

A Round 3 is required (a real in-scope defect was fixed) to confirm FIX-R2 introduces no regression and re-verify on the now-faster path.

## Adversarial verify Workflow round 3 (workflow wq21htivc, 20 read-only agents) — all 5 PASS, 0/15 refutes, FIX-R2 confirmed

All 5 tasks `verify=pass`, `mutation_proved=True`, **0/15 refutes** with full skeptic coverage (subagent_tokens 1.62M, all 20 agents returned StructuredOutput). FIX-R2 introduced no regression:
- **T1 now mutation-proves BOTH the bulk-traj AND the deep-profile-skip:** verifier's Mutation A (drop `traj=` AND `client_name=`) → BOTH `client_trajectory.assert_not_called()` AND `client_deep_profile.assert_not_called()` FAIL (call_count=2 each — the N×M blowup returns). Mutation B (num_windows 12→6) → exact-kwargs assertion FAILS. The literal 12 is pinned in source (trajectory.py:734) + test (test_trajectory_bulk.py:82-84). Skeptics ran byte-identical-equivalence PoCs on the real fixture DB (bulk-12 == per-entity-12, 0 shape/value mismatches) and confirmed the absent-client fallback fires per-entity with num_windows=12 and the name still threaded.
- **T2/T3/T4/T6** re-confirmed sound (typed-error OSError chain caught at all caller sites incl. the daemon `_run_job`/`except` wrapper; default-OFF + call-time env proven by single-process multi-env PoC; dead-call removal mutation-proved; fixture-not-constructor proven by empty `git diff` on source).
- **No skeptic reproduced any in-scope defect.** The FIX-R2 perf concern from Round 2 no longer appears (resolved). All encountered failures (`test_unified_intelligence.py` bare-Exception ×4, `test_daemon_intelligence.py` cycle_count, `test_daemon_resilience.py` STATE_FILE/PID_FILE module-constant refactor, `test_canonical_pipeline.py` docstring-grep flake) independently re-proven pre-existing on main (byte-identical test files / identical failures on base) and correctly excluded as non-refutation grounds.

**Convergence:** Round 1 (0/15, drove FIX-R1 stale-test alignment) → Round 2 (0/15 refutes but the T1 lens reproduced a REAL in-scope perf defect with a 110s live-DB PoC → FIX-R2) → Round 3 (0/15, FIX-R2 confirmed regression-free, perf 110s→0.15s). Matches the WS4 pattern: the adversarial process caught a real defect (the residual deep-profile N×M blowup) that solo verification + the original plan both missed. **WS5 verified sound. Proceeding to PHASE 4 pre-merge.**

## Per-task FINAL commit map (7 commits on fix/ws5-detection-intelligence)

| Commit | Scope |
|--------|-------|
| 2c9a76f | T1 bulk migration + T2 typed error (cohesive: same method's error path) |
| b31d811 | T3 MOH_INTELLIGENCE_FULL_MODE switch (default OFF) |
| 44fe704 | T4 delete dead portfolio_trajectory call |
| 9b48015 | T5 ADR-0028 dual findings stores |
| c81810d | T6 signal_suppression fixture schema |
| 48fb05d | FIX-R1 (round 1): align portfolio error test to typed-error contract |
| 7d8b459 | FIX-R2 (round 2): skip per-client deep-profile in bulk path (110s→0.15s) |

---

## Pre-Commit / Pre-Merge Verification (PHASE 4, after rebase onto origin/main 005956b)

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on all changed files | PASS | "All checks passed!" (trajectory.py, errors.py, signals.py, daemon.py + 5 test files) |
| `ruff format` on changed files | PASS | formatted on Mac via pinned .venv (0.15.1), re-staged each commit |
| `bandit -ll --skip B101,B608` on changed source | PASS | "No issues identified." (trajectory.py, errors.py, signals.py, daemon.py) |
| WS5 test surface | PASS | **129 passed / 0 failed** (test_trajectory_bulk, test_trajectory, test_daemon_intelligence_mode, test_intelligence_signals, test_signal_suppression) |
| **Full-suite regression (vs fresh baseline 005956b)** | **PASS — NET-NEW = 0** | branch **300** failures vs baseline **321**; `comm -13 baseline branch` = EMPTY (zero net-new); WS5 FIXES 21 pre-existing (20 test_signal_suppression + 1 test_trajectory error_handling). Regression-free + net-positive. |
| `check_mypy_baseline.py --strict-only` | PASS (exit 0) | "Strict island errors: 0 ... Mypy check passed (strict islands clean, baseline stable)". Legacy 159 < baseline 813. WS5 files not in strict islands; 0 new mypy errors. No .mypy-baseline.txt resync needed (check passed clean). |
| Every method call in changed files resolves to a real `def` | PASS | all interfaces read + cited in the Pre-Edit tables above (client_full_trajectory, bulk_client_trajectories, client_portfolio_overview, client_deep_profile, detect_all_signals, create_fresh, portfolio_trajectory) |
| Verification log included in `git add` | PASS | this file staged with every commit |
| Adversarial verify (3 rounds, read-only) | PASS | R1 0/15 (→FIX-R1), R2 0/15 + 1 real perf PoC (→FIX-R2), R3 0/15 confirmed. See rounds above. |

## PR Scope Check

| Planned PR | Files in this branch | Matches plan? |
|-----------|---------------------|--------------|
| WS5 (ONE PR, 6 tasks) | lib/intelligence/trajectory.py, lib/intelligence/errors.py (new), lib/intelligence/signals.py, lib/daemon.py, docs/adr/0028-dual-findings-stores.md (new), tests/test_trajectory_bulk.py (new), tests/test_daemon_intelligence_mode.py (new), tests/test_intelligence_signals.py, tests/test_signal_suppression.py, tests/test_trajectory.py, audit-remediation/VERIFICATION_LOG_S_ws5.md | YES — every file maps to a WS5 task (T1-T6) or an adversarial-round fix (FIX-R1/R2) or the verification log. No unrelated concerns bundled. |

**Net-new failure proof (the regression-free gate):** `comm -13 /tmp/ws5_baseline_failures.txt /tmp/ws5_branch_failures.txt` returned EMPTY — there is NO test that fails on the WS5 branch but passes on origin/main 005956b. 21 baseline failures are FIXED by WS5 (all under test_signal_suppression.py + test_portfolio_health_trajectory_error_handling).
