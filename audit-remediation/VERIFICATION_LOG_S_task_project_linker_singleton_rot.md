# Verification Log — fix/test-task-project-linker-singleton-rot

**Session:** task_project_linker singleton test-isolation rot (ad-hoc task)
**Date:** 2026-06-04
**Agent:** systematic-debugging session (isolated worktree, branched fresh from origin/main @ef9cc69)

---

## Root cause (Phase 1, verified by evidence)

`tests/test_task_project_linker.py` had 2 failures on origin/main
(`TestCascadeClientIds::test_correct_client_id` → `assert None == 'c1'`;
`TestLinkAll::test_link_all_runs_all_strategies` → `assert 6 > 6`).

NOT seed rot, NOT linker-behavior rot. Both tests PASS in isolation, FAIL in the
full-file run → singleton run-order pollution. The tests passed a `db_path` STRING
positionally to linker functions that route through `StateStore` (singleton). After
the first `StateStore(path)` in the file, `__init__` early-returns on
`self._initialized` (lib/state_store.py:104-105) and the path is frozen. The
function-scoped fixture created a fresh temp DB per test, but the linker kept writing
to the FIRST test's DB; the failing tests then read their own fresh DB (raw
`sqlite3.connect(test_db)`) where nothing was linked.

Proof of order-dependence:
`pytest test_links_asana_tasks_by_name test_correct_client_id` → 1 failed, 1 passed;
each test alone → passed.

origin/main advanced 4169434 → ef9cc69 (PR #156, an unrelated daemon-resilience-rot
fix) mid-task; `git diff 4169434 ef9cc69 -- tests/test_task_project_linker.py
lib/task_project_linker.py lib/state_store.py` is EMPTY → bug identical on current
main. Rebased onto ef9cc69.

Fix = adopt the WORKING repo pattern from
`tests/test_audit_remediation_v3_behavioral.py::_fresh_store` (lines 30-34): reset
`StateStore._instance = None`, construct `StateStore(db_path)` bound to the test DB,
pass `store=` to the linker, inspect via that SAME store, reset `_instance = None`
in teardown. conftest has `reset_outbox_singleton` (autouse, 403-429) but NO
StateStore equivalent — same class of hole. Test-file-only change; production code
(lib/task_project_linker.py) UNTOUCHED (the linker was correct; the tests were wrong).

## Non-vacuous proof (mutation testing, in isolated worktree, reverted after)

| Mutation | Test exercised | Result | Reverted |
|----------|---------------|--------|----------|
| `cascade_client_ids` UPDATE writes `'MUTANT_WRONG'` instead of project.client_id | `test_correct_client_id` | FAILED `assert 'MUTANT_WRONG' == 'c1'` ✓ catches | yes |
| `link_all` forces all 3 link strategies to `dry_run=True` (links nothing) | `test_link_all_runs_all_strategies` | FAILED `assert 2 > 2` ✓ catches | yes |

`git diff HEAD -- lib/task_project_linker.py` → EMPTY after reverts (production pristine).

## Pre-Edit Verification

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| tests/test_task_project_linker.py | `StateStore.__new__` (singleton) | lib/state_store.py:94-101 | yes — `(cls, db_path=None)`, returns cached `_instance` | yes — returns StateStore | n/a (constructor) |
| tests/test_task_project_linker.py | `StateStore.__init__` | lib/state_store.py:103-127 | yes — `_initialized` guard freezes `db_path` after first ctor | yes | n/a |
| tests/test_task_project_linker.py | `StateStore._instance` (class attr reset) | lib/state_store.py:91 | yes — class attribute `_instance = None` | yes (assignment) | reference: test_audit_remediation_v3_behavioral.py:32,521,557,590 |
| tests/test_task_project_linker.py | `StateStore.query(sql, params=None)` | lib/state_store.py:298 | yes — `(self, sql, params=None) -> list[dict]` | yes — returns list[dict], indexed `[0]["c"]`/`["client_id"]`/`["project_id"]` | n/a (read) |
| tests/test_task_project_linker.py | `link_by_asana_gid(db_path=None, dry_run=False, store=None)` | lib/task_project_linker.py:29-31 | yes — `store` kwarg accepted | yes — returns int | n/a |
| tests/test_task_project_linker.py | `link_by_map(db_path=None, dry_run=False, store=None)` | lib/task_project_linker.py:68-70 | yes — `store` kwarg accepted | yes — returns int | n/a |
| tests/test_task_project_linker.py | `link_by_name(db_path=None, dry_run=False, store=None)` | lib/task_project_linker.py:107-109 | yes — `store` kwarg accepted | yes — returns int | n/a |
| tests/test_task_project_linker.py | `cascade_client_ids(db_path=None, dry_run=False, store=None)` | lib/task_project_linker.py:140-142 | yes — `store` kwarg accepted | yes — returns int | n/a |
| tests/test_task_project_linker.py | `link_all(db_path=None, dry_run=False, store=None)` | lib/task_project_linker.py:175-177 | yes — `store` kwarg accepted | yes — returns dict | n/a |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed file | PASS | `All checks passed!` (exit 0) |
| `ruff format --check` on changed file | PASS | `1 file already formatted` (exit 0; check-only, not formatted from sandbox) |
| `bandit` on changed file | PASS | exit 0; 10× B101 (assert in tests — excluded by pre-commit), 0 Medium/High |
| mypy `check_mypy_baseline.py --strict-only` | PASS | strict islands 0 errors, baseline stable |
| `pytest` (sandbox via venv) | PASS | 9 passed; 3× stable; order-independent; passes after StateStore-heavy files run first |
| Every method call in changed file resolves to a real `def` | PASS | all 9 traced above |
| Verification log included in `git add` | YES | this file |

## Isolation / regression scope

- v3 / v3_behavioral pre-existing failures (11 in v3, 3 in v3_behavioral) confirmed
  pre-existing: identical counts with my file ABSENT. My fixture's setup-time
  `StateStore._instance = None` reset means my 9 tests pass regardless of run order
  (verified: all 9 pass with v3 + v3_behavioral run first).

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Fix test_task_project_linker singleton rot | tests/test_task_project_linker.py + this log | yes — single purpose, test-only |

If this commit contains files from more than one planned PR: **STOP. Split the commit.**
