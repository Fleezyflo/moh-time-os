# Verification Log — test_change_bundles fixture rot (Phase 1b)

**Session:** phase1b (2026-06-04)
**Base:** origin/main @ 8d5d83f
**Branch:** fix/test-rot-fixture-targets

Per-PR log. Diagnosed via the parallel rot-diagnosis workflow (audit-remediation/rot_diagnoses_2026-06-04.json).

## Root cause (pure fixture rot, high confidence, verified green)
`tests/test_change_bundles.py:45` fixture patched `lib.change_bundles.BUNDLES_DIR`, a module-level
constant removed in the paths refactor and replaced by the `_bundles_dir()` resolver
(`paths.data_dir()/"bundles"`, change_bundles.py:26-29). All 46 errors were fixture-setup
AttributeErrors.

## Fix
`monkeypatch.setattr("lib.change_bundles.BUNDLES_DIR", bundles_dir)` →
`monkeypatch.setattr("lib.change_bundles._bundles_dir", lambda: bundles_dir)`. Test-only, one line.

## Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | 46 errors (`lib.change_bundles` has no `BUNDLES_DIR`) |
| TDD green (after) | PASS | `52 passed` test_change_bundles |
| ruff / ruff format | PASS | clean |

Files in this commit: `tests/test_change_bundles.py`, `audit-remediation/rot_diagnoses_2026-06-04.json`
(the workflow's diagnosis reference for the remaining rot files), this log.

## Scope note — why ONLY change_bundles in this PR
The rot-diagnosis workflow flagged 17 files. Applying the fixes serially + running each (only the main
checkout has a venv) revealed that MOST "rot" files are multi-layered — fixing the outer fixture
exposes deeper stale patches or real bugs:
- `test_daemon_resilience`: STATE_FILE fix works, but ~15 tests patch a removed `lib.daemon.collect_all`
  (now `_handle_collect`/`_run_job` instance methods) — own task spawned.
- `test_runtime_payload`: singleton reset needed but insufficient; deeper payload-shape failures — own task.
- `test_cross_cutting_correctness`: one trivial `check_system_invariants.py` DB_PATH fix + a LARGE
  `api/server.py` 55-bare-`datetime.now()` cleanup (ADR-gated file) — own task.
- `test_backup`: 11 `@patch` decorators with `.value` setup need `return_value` rewrites — own task.
- Real-bug cluster (gmail/calendar/asana/chat writers, background_tasks, entity_profile): fixture fix
  exposes 641754c-class except-narrowing bugs (API errors propagate) — own tasks.
`change_bundles` is the only file that goes 100% green with the pure mechanical fix, so it ships alone.
The diagnoses JSON is committed so the spawned tasks start from the analysis instead of re-diagnosing.
