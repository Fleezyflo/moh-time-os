# Verification Log — fix/test-daemon-resilience-rot

**Session:** S (2026-06-04)
**Date:** 2026-06-04
**Agent:** daemon-resilience-repair

---

## Context

`tests/test_daemon_resilience.py` had two layers of stale-patch rot plus exposed one real
daemon resilience regression:

1. **Rot — fixture paths:** `daemon` fixture + `test_consecutive_failures_persist_across_restarts`
   patched removed module constants `lib.daemon.STATE_FILE/PID_FILE/LOG_FILE`. `monkeypatch.setattr`
   on a nonexistent attribute raises `AttributeError` → 19 fixture errors. These are now resolver
   functions `_state_file()/_pid_file()/_log_file()` (lib/daemon.py:74-83), all reading
   `paths.data_dir()`. Fixed by the sibling idiom (test_daemon_status.py): set `MOH_TIME_OS_HOME`
   + `importlib.reload(lib.paths)`.
2. **Rot — collect seam:** ~13 tests patched `lib.daemon.collect_all`, a module global removed at
   commit 4a7f78a ("kill legacy collectors/"). Collect is now `TimeOSDaemon._handle_collect`
   (lib/daemon.py:487) → `_get_orchestrator().sync_all()`, dispatched by `_run_job` (line 448-449).
   Fixed by patching `patch.object(daemon, "_handle_collect")`.
3. **Real regression — narrow except:** `_run_job`'s outer catch is
   `except (sqlite3.Error, ValueError, OSError)` (lib/daemon.py:476), narrowed by commit 641754c
   (`git blame` confirmed; was `except Exception` at baseline e8b334e). `run()` has no try/except
   around `_run_job` (lib/daemon.py:773-778), so any other exception type kills the self-healing
   loop. Probe proved bare `Exception` propagates uncaught. The failure-path tests raise bare
   `Exception` asserting "any job error → recorded failure"; that contract is correct. **Molham
   approved fixing the daemon (broaden `_run_job` to `except Exception`, logged + typed return).**

4. **Inner `_handle_*` handlers (Molham approved "broaden them too"):** classified by ROLE
   (per the 641754c lesson — broaden outer boundaries, keep nested best-effort narrow):
   - **Role A, re-raise boundary → BROADENED:** `_handle_collect` (503) and
     `_handle_lane_assignment` (~525). These `log + raise`; broadening to `except Exception`
     (after the existing `except ImportError` swallow) means unexpected types get a stage-specific
     log AND propagate to `_run_job` to be recorded. `ImportError` swallow preserved (probe-verified).
   - **Role B, swallow/recover → LEFT NARROW (deliberate, evidence-backed):** `_handle_intelligence`
     (619, 633), `_handle_morning_brief` (667), `_handle_snapshot` (687). These `log + continue/
     recover` (do NOT re-raise). Broadening them would SWALLOW unexpected errors at the sub-step
     and return success to `_run_job`, HIDING real failures — the opposite of the resilience goal.
     Left narrow so unexpected types propagate to `_run_job` and ARE recorded (probe-verified:
     snapshot+RuntimeError → `_run_job`=False, failure recorded).
   - **Role C, not job handlers → UNTOUCHED:** `_load_state` (271), `_save_state` (298),
     `is_running` (830), `status` (892).
   New `TestRunJobExceptionBreadth` class pins the contract (parametrized RuntimeError/KeyError/
   TypeError/AttributeError); proven to FAIL 5/6 against the narrow catch, pass after the fix.

---

## Pre-Edit Verification

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/daemon.py | `_run_job` outer `except Exception` (broaden) | lib/daemon.py:424 (def), except at :476 | yes — returns bool; logs+records state+returns False | yes — `run()` (773-778) and `run_once()` (737-742) use bool result; broadening only widens catch | yes — `run()` no try/except (needs this), `run_once()` counts True/False; no test asserts `_run_job` re-raises (grep: only test_daemon_resilience uses `_run_job`) |
| tests/test_daemon_resilience.py | `paths.data_dir()` (via reload idiom) | lib/paths.py `data_dir()` | yes — `_state_file/_pid_file/_log_file` (lib/daemon.py:74-83) all call `paths.data_dir()` | yes — returns Path | yes — sibling test_daemon_status.py uses identical reload idiom (passes today) |
| tests/test_daemon_resilience.py | `patch.object(daemon, "_handle_collect")` | lib/daemon.py:495 (def _handle_collect) | yes — no args, returns None; raised inside `_run_job` try at line 456 | yes — None on success; side_effect Exception on failure path | yes — `_run_job` dispatches collect → `_handle_collect()` |
| lib/daemon.py | `_handle_collect` inner `except Exception` (broaden re-raise boundary) | lib/daemon.py:503 | yes — re-raises; `except ImportError` (501) still swallows first | n/a (raises) | yes — only caller is `_run_job` (line 456), which now catches Exception |
| lib/daemon.py | `_handle_lane_assignment` inner `except Exception` (broaden re-raise boundary) | lib/daemon.py:~525 | yes — re-raises; `except ImportError` (519) still swallows first | n/a (raises) | yes — only caller is `_run_job` (line 458), which now catches Exception |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` |
| `ruff format --check` on changed files | PASS | `2 files already formatted` |
| `bandit -r` on changed files | PASS | lib/daemon.py: 0 results; test file: only B101 (assert_used, LOW — skipped for tests/) |
| `pytest tests/test_daemon_resilience.py` | PASS | `26 passed in 0.19s` (20 original + 6 new breadth guards) |
| `pytest tests/ -k daemon` (regression) | PASS | `49 passed, 3843 deselected` |
| `check_mypy_baseline.py --strict-only` | PASS | `Strict island errors: 0`, baseline stable |
| Every method call in changed files resolves to a real `def` | PASS | `_run_job`@424, `_handle_collect`@495, `_handle_lane_assignment`@511, `paths.data_dir`@35 |
| New tests proven to guard the fix | PASS | `TestRunJobExceptionBreadth` → 5/6 FAIL against narrow catch, 6/6 pass after (TDD proof, residue reverted) |
| Verification log included in `git add` | PASS | included in commit block below |

**Note:** line numbers shifted as comments were added inside `_run_job`/`_handle_collect`; the
post-edit `def` resolution above is authoritative. `sqlite3` import retained — still used at 6
sites (Role-B/C narrow handlers).

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| fix daemon resilience tests + the regression they exposed | lib/daemon.py, tests/test_daemon_resilience.py, audit-remediation/VERIFICATION_LOG_S_daemon_resilience_test_repair.md | yes — single purpose |
