# Verification Log — StateStore write-path primitives (Phase 1c, PR A)

**Session:** phase1c (2026-06-04)
**Base:** origin/main @ be391c0
**Branch:** feat/statestore-write-path

Per-PR log (not the shared phase-1 log). Phase 1c was scoped as "task_project_linker debt" but the
real contract is an unbuilt StateStore write-path (≈18 tests across v3/v3_behavioral/v4). Decision
(mine, no longer asking): BUILD it — `lib/state_store.py` is unprotected, not ADR-gated, and the
codebase clearly intends this (tests written, query() already funnels through `_get_conn()`).

## Decomposition (One-PR-One-Purpose)
- **PR A (this one): additive primitives** — `execute_write`, `transaction`, `_write_lock`, and the
  WRITE-PATH RULE class docstring. Breaks nothing (purely new methods + docs + a delegating `query`).
- **PR B (next): migrate task_project_linker** onto execute_write/query + `store=` kwarg.
- **DEFERRED to its own track: the `query()` read-only guard.** `query()` cannot start rejecting
  non-SELECT until ~11 live write-via-query() call sites migrate to execute_write first, or the daemon
  breaks. Sites: autonomous_loop.py:1310 (UPDATE communications — LIVE daemon path), debt_tracker.py:69,
  client_truth/linker.py:83 (DELETE), commitment_manager.py:202/222/232/241, state_tracker.py:123,
  block_manager.py:172/194. Shipping the guard before migrating these would raise RuntimeError in
  production. So `test_B_query_rejects_create/drop/alter/insert` stay RED until that track lands —
  intentional, flagged via spawn-task.

## Implementation
- `__init__`: `self._write_lock = threading.RLock()` (test_B_transaction_holds_write_lock requires a
  reentrant `_write_lock`; reentrancy lets a transaction() callback call execute_write without deadlock).
- `query()` → delegates to new `_raw_query()` (identical SELECT behavior; docstring marks it read-only).
- `execute_write(sql, params)` → `with self._write_lock, self._get_conn()`: execute, return rowcount.
- `transaction(fn)` → `with self._write_lock`: open conn (WAL+FK), `fn(conn)`, commit + return result;
  on `BaseException` rollback + re-raise; always close.

## Pre-Edit Verification
| File edited | Symbol | Defined/used at | Confirmed | Callers checked |
|-------------|--------|-----------------|-----------|-----------------|
| state_store.py `__init__` | `threading.RLock()` | threading imported (line 9) | yes | n/a (new attr) |
| state_store.py `query` | delegates to `_raw_query` | new internal | yes — SELECT behavior unchanged | ALL `.query(` SELECT callers regression-tested (93 passed); the ~11 write-via-query callers are NOT broken because the guard is DEFERRED |
| state_store.py `execute_write`/`transaction` | `self._get_conn()` / raw connect | _get_conn (line ~65) | yes | new methods — callers added in PR B + the migration track |

## Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | TestStateStoreTransaction 5 failed (`no attribute 'execute_write'`) |
| TDD green (after) | PASS | TestStateStoreTransaction 5 passed; TestWritePathRule doc test passed; v3 execute_write/query_allows/write_lock 4 passed |
| query() guard tests stay red (DEFERRED, intentional) | EXPECTED | `query_rejects_create/drop/alter/insert` still fail — guard needs the 11-site migration first |
| broad regression (query consumers) | PASS | `93 passed` (state_store/command_center/autonomous/commitment/capacity/client_truth/time_truth/ws4) |
| ruff / ruff format / bandit | PASS | clean (transaction's `except BaseException: raise` re-raises — not a silent swallow) |

Files in this commit: `lib/state_store.py`, this log. One purpose (PR A: additive write-path primitives).
