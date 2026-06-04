# Verification Log — test_key_manager rot + double-tz bug (Phase 1b)

**Session:** phase1b (2026-06-04)
**Base:** origin/main @ 3308317
**Branch:** fix/test-rot-key-manager

Per-PR log. First Phase-1b file.

## Two coupled issues in test_key_manager (one purpose: make the file correct)

### Issue 1 — stale fixture patch target (TEST ROT, 47 errors)
The `key_manager` fixture patched `lib.security.key_manager.store.DB_PATH`, but `lib.store` has no
`DB_PATH` (removed in the paths refactor) AND `KeyManager` doesn't read it — it uses
`lib.store.get_connection()` → `lib.store._db_path()` → `lib.paths.db_path()` (respects MOH_TIME_OS_DB).
Fix: patch `lib.paths.db_path` to return the temp DB (verified: `store._db_path()` then resolves to
temp). `KeyManager.__init__` runs `db.ensure_migrations()` which converges the schema onto it.

### Issue 2 — `+00:00Z` double-timezone bug (REAL PRODUCTION BUG, 3 fails after Issue 1 fixed)
`key_manager.py` built timestamps as `datetime.now(timezone.utc).isoformat() + "Z"` (lines 177, 181,
263). An AWARE `.isoformat()` already ends in `+00:00`, so appending `"Z"` yields `...+00:00Z`. Then
`is_expired()` does `.replace("Z", "+00:00")` → `...+00:00+00:00` → `ValueError: Invalid isoformat
string`. This crashes `is_expired()` for ANY key with an expiry — a live auth-key bug, not just a test
artifact. Fix: drop the `+ "Z"` (3 sites); the aware isoformat is already offset-qualified. Left the
defensive `.replace("Z","+00:00")` in `is_expired` (harmless; tolerates a Z-suffixed external value).

## Pre-Edit Verification
| File edited | Symbol | Defined at | Confirmed | Notes |
|-------------|--------|-----------|-----------|-------|
| test_key_manager.py `key_manager` fixture | `lib.paths.db_path` | lib/store.py:14 `_db_path()`→paths.db_path() | yes — probe showed store._db_path()==temp | replaces removed `store.DB_PATH` |
| key_manager.py:177,181,263 | `datetime.isoformat()` (aware) | stdlib | yes — aware isoformat ends in +00:00, not Z | dropping `+ "Z"` removes the double offset |

## Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | 47 errors (`store` has no `DB_PATH`) |
| After fixture fix | PARTIAL | 47 passed, 3 failed (`+00:00+00:00` ValueError exposed) |
| After tz-bug fix | PASS | `50 passed` test_key_manager |
| regression (security hardening + auth integration) | PASS | `71 passed` |
| ruff / ruff format / bandit | PASS | clean |

Files in this commit: `tests/test_key_manager.py`, `lib/security/key_manager.py`, this log. One purpose
(test_key_manager correctness: fixture rot + the double-tz bug it exposed).
