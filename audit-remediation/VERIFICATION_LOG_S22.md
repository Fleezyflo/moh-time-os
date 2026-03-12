# Verification Log — Session 22 Bug Fixes

**Session:** 22
**Date:** 2026-03-12
**Agent:** Cowork session (wonderful-happy-archimedes)
**Rounds:** 2 (initial fixes + self-critique round)

---

## Pre-Edit Verification

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------
| `lib/state_tracker.py` | `get_store()` | `lib/state_store.py:268` | `get_store(db_path: str = None) -> StateStore` | yes — returns StateStore | yes |
| `lib/state_tracker.py` | `get_sync_states()` | `lib/state_store.py:258` | `get_sync_states(self) -> dict[str, dict]` | returns `{row["source"]: row}` where row is `sqlite3.Row` | yes — caller uses `states.get(source)` (dict.get, not Row.get) |
| `lib/state_tracker.py` | `info["last_sync"]` (bracket access on sqlite3.Row) | stdlib `sqlite3.Row` | bracket access via `__getitem__` | returns column value or raises `IndexError` | yes — `last_sync` is column in sync_state table (state_store.py:251) |
| `lib/backup.py` | `checkpoint_wal()` | `lib/store.py:232` | `checkpoint_wal() -> None` | runs `PRAGMA wal_checkpoint(TRUNCATE)` | yes — read function body: checks `db_exists()`, then checkpoints via `get_connection()` |
| `lib/backup.py` | `sqlite3.sqlite_version` | stdlib | string attribute `"X.Y.Z"` | used with `.split(".")` → tuple comparison | N/A (stdlib) |
| `lib/backup.py` | `shutil.copy2()` | stdlib | `shutil.copy2(src, dst)` | returns dst path | yes — was the original implementation before VACUUM INTO |
| `engine/xero_client.py` | `logger.warning()` | stdlib `logging` | `warning(msg, *args)` | void | N/A — log call, no callers to check |
| `lib/observability/health.py` | `import httpx` (moved inside method) | pypi `httpx` | module import | N/A | yes — only used in `_alert_on_degradation()` except clause |
| `lib/observability/health.py` | `GoogleChatChannel.send_sync()` | `lib/notifier/channels/google_chat.py:50` | `send_sync(self, message: str, title: str \| None = None, **kwargs) -> dict` | returns dict | yes |

## Test Compatibility Verification (Round 2)

| Test file | Import | Compatibility issue | Fix applied |
|-----------|--------|-------------------|-------------|
| `tests/test_backup.py` | `from lib.backup import create_backup` | Tests mock `shutil.copy2` but VACUUM INTO path bypasses it. Tests would fail. | Extracted `_copy_database()` function; updated 5 tests to mock `lib.backup._copy_database` |
| `tests/test_collector_resilience.py` | `from lib.collectors.base import BaseCollector` | `test_sync_with_partial_failure_stores_successful_items` asserts `success: True` on transform failure — my fix makes it return `success: False` | Updated test to expect `success: False`, `assert "transform failed" in error`, `insert_many.assert_not_called()`, `update_sync_state` called with failure |
| No test imports `lib.observability.health` | — | No compatibility issue | — |
| No test imports `lib.state_tracker` | — | No compatibility issue | — |

## Exception Path Verification (Round 2)

| File | Exception scenario | Caught by | Verified |
|------|-------------------|-----------|----------|
| `health.py` | `import httpx` raises `ImportError` | Explicit `except ImportError` — returns early | yes |
| `health.py` | `from lib.notifier...GoogleChatChannel` raises `ImportError` | **Round 1 bug: NOT caught.** Round 2 fix: added `except ImportError` clause before httpx error clause | yes |
| `health.py` | `channel.send_sync()` raises `httpx.HTTPStatusError` | `except (httpx.HTTPStatusError, httpx.RequestError, OSError)` | yes |
| `health.py` | `_alert_on_degradation()` called from `run_all()` — any uncaught error | NOT in `run_all()`'s try/except — could crash health check. But all exception paths are now handled within the method itself | yes — all 3 exception scenarios have handlers |
| `backup.py` | `_copy_database()` raises `PermissionError` | `create_backup()` catches `PermissionError` at line 64 | yes |
| `backup.py` | `_copy_database()` raises `OSError` | `create_backup()` catches `OSError` at line 68 | yes |
| `backup.py` | `_copy_database()` — VACUUM INTO raises `sqlite3.OperationalError` | `create_backup()` catches `sqlite3.Error` at line 79. `sqlite3.OperationalError -> sqlite3.DatabaseError -> sqlite3.Error` — **COVERED**. Initially flagged as gap but re-verified: Session 21 code already had this handler. |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on all changed files (6 files) | PASS | "All checks passed!" |
| `ruff format --check` | 1 file needs formatting | `engine/xero_client.py` — must format on Mac |
| `bandit -r` on changed source files | PASS | "No issues identified" — 943 lines scanned, 0 issues |
| `pytest` (Molham's Mac) | PENDING | Must run before commit |
| Every method call resolves to a real `def` | YES | All verified above |
| Verification log included in `git add` | YES | This file |

## PR Scope Check

| Fix | Files | Target PR |
|-----|-------|-----------|
| Env var credential loading, remove token prefix | `engine/asana_client.py`, `engine/xero_client.py` | PR 1 |
| Write lock, transform failure, sqlite3.Row fix | `lib/collectors/base.py`, `lib/state_store.py`, `lib/state_tracker.py`, `tests/test_collector_resilience.py` | PR 2 |
| VACUUM INTO with version guard, extracted _copy_database | `lib/backup.py`, `tests/test_backup.py` | PR 3 |
| Schema savepoints, health alerting, global error handler | `lib/schema_engine.py`, `lib/observability/health.py`, `api/server.py` | PR 4 |

**These go into separate PRs. No bundling.**

---

## Detailed Fix Descriptions

### Fix 1: state_tracker.py — sqlite3.Row has no .get()

**Bug:** Line 79 `info.get("last_sync")` crashes at runtime because `get_sync_states()` returns `{source: sqlite3.Row}` and `sqlite3.Row` does not support `.get()`.

**Verification:** Confirmed `_get_conn()` sets `conn.row_factory = sqlite3.Row` at state_store.py:68. Confirmed with Python test in Session 21.

**Fix:** Changed to `info["last_sync"]` (bracket access) with explicit `None` guard on `info`.

### Fix 2: backup.py — SQLite version guard + extracted _copy_database

**Risk:** `VACUUM INTO` requires SQLite 3.27.0+. Also, existing tests mock `shutil.copy2` which VACUUM INTO bypasses.

**Fix:** Runtime version check with fallback. Extracted `_copy_database(source, dest)` as a module-level function so tests can mock the entire copy operation regardless of which strategy is used.

**Test updates:** 5 tests in test_backup.py updated to mock `lib.backup._copy_database` instead of `shutil.copy2`.

### Fix 3: xero_client.py — Remove token prefix from log

**Best practice:** Never log any part of a secret.

### Fix 4: health.py — Deferred httpx import + ImportError handling

**Round 1 fix:** Moved `import httpx` inside method with `ImportError` guard.

**Round 2 fix:** Added `except ImportError` for `GoogleChatChannel` import. Without this, a missing `google_chat` module would propagate `ImportError` up to `run_all()` which doesn't catch it.

### Fix 5: test_collector_resilience.py — Updated transform failure expectation

**Old behavior (bug):** Transform failure stored 0 items, marked `success: True`, called `mark_collected()` — caused permanent data loss on next sync.

**New behavior:** Transform failure returns `success: False` immediately, records failure in sync state, does NOT call `insert_many`.

**Test updated:** `test_sync_with_partial_failure_stores_successful_items` renamed to `test_sync_with_transform_failure_returns_failure`. Asserts `success: False`, error contains "transform failed", `insert_many` not called, `update_sync_state` called with failure.

### No open gaps

All exception paths verified. `create_backup()` catches `PermissionError`, `OSError`, and `sqlite3.Error` — covers all `_copy_database()` failure modes.
