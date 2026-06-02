# Verification Log — test/repair-tasks-collector-propagation-seam

**Session:** standalone test-repair (separate from WS2)
**Date:** 2026-06-02
**Agent:** Claude Opus 4.8 (1M context)

---

## Context

`tests/test_stub_endpoints.py::TestErrorPropagation::test_tasks_collector_propagates_errors`
fails on clean `main` (HEAD bf60dc1) with `Failed: DID NOT RAISE <class 'Exception'>`.
Confirmed pre-existing — NOT caused by WS2.

Root cause: the test patches `collector._run_command` to raise, then expects
`collect()` to propagate. But `TasksCollector.collect()` (lib/collectors/tasks.py:59-127)
was rewritten to fetch via the Google Tasks **API** (`_get_service()` →
`service.tasklists().list()`); it **never calls `_run_command`**. The patch targets a
real but unused method (`_run_command` is defined on `BaseCollector` at
lib/collectors/base.py:230), so the side-effect never fires. With the dead patch in
place, `collect()` makes a **live API call** — empirically probed on this machine it
returned 112 real tasks across 11 lists and did not raise, hence "DID NOT RAISE".

The contract under test (`TestErrorPropagation`, plus base.py:69 "MUST raise on
failure — never return empty data to fake success") is correct and still upheld by
the source: tasks.py:125-127 catches `COLLECTOR_ERRORS` and re-`raise`s. The test
was patching the wrong seam. Fix: patch `_get_service` — the seam `collect()`
actually uses — so the test exercises real propagation with no network call.

This is a test-only repair. NO production code changes.

---

## Pre-Edit Verification

For EVERY method call you add or modify, fill in one row.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| tests/test_stub_endpoints.py | `TasksCollector.collect()` | lib/collectors/tasks.py:59 | yes — no-arg method, returns `dict[str, Any]` | yes — `try: service = self._get_service()` at :62, fetch loop, `except COLLECTOR_ERRORS: ... raise` at :125-127 | yes — only this test calls `collect()` directly on a patched instance; `sync()` (base.py:122) is the production caller and is untouched |
| tests/test_stub_endpoints.py | `TasksCollector._get_service()` (patch target) | lib/collectors/tasks.py:40 | yes — `_get_service(self, user=DEFAULT_USER)`, returns the Tasks API service; raises `COLLECTOR_ERRORS` on cred/build failure (:55-57) | yes — called once at tasks.py:62 inside `collect()`'s try; any exception is caught at :125 and re-raised at :127 | yes — sole caller is `collect()` at :62 (grep `_get_service` → defs at :40, call at :62) |

### Evidence — empirically probed (all via `.venv/bin/python`, MagicMock store, config={})

- **Dead patch (old test):** `patch.object(collector, "_run_command", side_effect=...)`
  then `collect()` → **RETURNED** `dict` with `n_tasks=112, n_lists=11` (live Google
  Tasks API call). No exception. This is the "DID NOT RAISE" failure.
- **Correct seam (new test):** `patch.object(collector, "_get_service", side_effect=Exception("Service failed"))`
  then `collect()` → **RAISED** `Exception - Service failed`. No network call.
- `_run_command` is defined at base.py:230 and `grep -rn _run_command lib/collectors/`
  shows it is referenced nowhere in any collector's `collect()` — only the test
  referenced it. The Tasks collector is fully API-based (tasks.py:1-3, 40-57).

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` |
| `ruff format --check` on changed files | PASS | `1 file already formatted` |
| `bandit -r --skip B101,B608` (CI invocation) on changed file | PASS | `No issues identified.` (4 raw B101 asserts are in pre-existing untouched lines 83/85/86/130; B101 is skipped per pyproject.toml:104 and .pre-commit-config.yaml:27) |
| `pre-commit run ruff / ruff-format / bandit --files tests/test_stub_endpoints.py` | PASS | all three `Passed` |
| `pytest tests/test_stub_endpoints.py` | PASS | `4 passed in 0.69s` (was 3 passed / 1 failed, ~6s) |
| Every method call in changed files resolves to a real `def` | yes | `collect` (tasks.py:59), `_get_service` (tasks.py:40) verified above |
| Verification log included in `git add` | yes | included in commit block below |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| test: repair Tasks collector propagation seam (patch `_get_service`, not unused `_run_command`) | tests/test_stub_endpoints.py + this log | yes — one file, one purpose, separate from WS2 |

If this commit contains files from more than one planned PR: **STOP. Split the commit.**
