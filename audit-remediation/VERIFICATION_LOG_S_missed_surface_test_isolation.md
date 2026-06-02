# Verification Log — fix/test-isolation-missed-surface-closure

**Session:** test-isolation-fix
**Date:** 2026-06-02
**Agent:** Claude (Opus 4.8)

---

## Problem

`tests/test_missed_surface_closure.py::TestServerAuthClosure::test_mutation_rejects_no_auth[POST-/api/sync/xero]`
(and every test using the `test_client` fixture) raises in isolation:

    RuntimeError: DETERMINISM VIOLATION: live DB path probed via Path.exists:
    /Users/molhamhomsi/.moh_time_os/data/moh_time_os.db

### Root cause (verified, not assumed)

1. `tests/test_missed_surface_closure.py:104-114` — the `test_client` fixture sets
   `MOH_TIME_OS_API_KEY` and `MOH_TIME_OS_ENV` but never points the DB at a fixture
   and never resets the `StateStore` singleton.
2. `from api.server import app` (line 112) executes `api/server.py:93` `store = get_store()`
   at module level.
3. `lib/state_store.py:53` `StateStore.__init__` calls `db_module.ensure_migrations()`.
4. `lib/db.py:245-247` `ensure_migrations()` → `run_startup_migrations()` (first run only).
5. `lib/db.py:173,180` `run_startup_migrations()` calls `get_db_path()` →
   `lib/paths.py:41-51 db_path()`, which honors ONLY `MOH_TIME_OS_DB`; with no override
   it returns the live default `~/.moh_time_os/data/moh_time_os.db`, then
   `db_path.exists()` trips the guard at `tests/conftest.py:179-185 _guarded_path_exists`.

Order-dependent: `_migrations_run` (db.py:160) and `StateStore._instance` (state_store.py:27)
are process-global. In the full suite an earlier test points `lib.paths`/`MOH_TIME_OS_DB`
at a fixture (or builds the singleton against one) before `api.server` is first imported,
so the probe is short-circuited. Run alone, nothing sets it first → live-path probe.

This is a fixture-level test-isolation leak, NOT a guard or production-code defect.
The guard is left intact per instructions. Fix mirrors the two existing working fixtures
(`tests/test_auth_and_side_effects.py:28-61`, `tests/test_auth_middleware.py:11-50`) and the
module-scoped pattern in `tests/test_mounted_app_route_ownership.py:40-69`.

---

## Pre-Edit Verification

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| tests/test_missed_surface_closure.py | `create_fixture_db(db_path)` | tests/fixtures/fixture_db.py:56 | yes — `(db_path: str\|Path=":memory:") -> sqlite3.Connection` | yes — returns Connection, `.close()` called | n/a (fixture-local) |
| tests/test_missed_surface_closure.py | `lib.paths.db_path` (patch target) | lib/paths.py:41-51 | yes — `() -> Path`, reads MOH_TIME_OS_DB live | yes — patched with `lambda: db_path` (Path) | called by lib/db.py:60 get_db_path → state_store.py:44 |
| tests/test_missed_surface_closure.py | `lib.paths.data_dir` (patch target) | lib/paths.py:35-38 | yes — `() -> Path` (mkdir side effect) | yes — patched with `lambda: db_path.parent` (Path) | called by state_store.py:45 |
| tests/test_missed_surface_closure.py | `StateStore._instance` (reset target) | lib/state_store.py:27 (`_instance = None`) | yes — class attr, singleton flag at __new__ line 32 | yes — set to `None` forces rebuild | __new__ state_store.py:30-37 |
| tests/test_missed_surface_closure.py | `api.auth` reload (rebinds `_API_KEY`) | api/auth.py:33 `_API_KEY = os.environ.get(...)` | yes — captured at import time | yes — reload re-reads env var | get_api_key auth.py:44, require_auth:80 |
| tests/test_missed_surface_closure.py | `MonkeyPatch()` + `.undo()` | _pytest.monkeypatch (stdlib pytest) | yes — verified usage at test_mounted_app_route_ownership.py:43-47 | yes — context-manager-free, manual undo | n/a |
| tests/test_missed_surface_closure.py | `importlib.reload(module)` | stdlib importlib | yes — standard | yes — returns reloaded module | n/a |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check tests/test_missed_surface_closure.py` | PASS | `All checks passed!` |
| `ruff format --check` (NOT run from sandbox per rules; check only) | PASS | `1 file already formatted` |
| `bandit -r -ll --skip B101,B608` (exact pre-commit invocation) | PASS | `0 issues reported at threshold` (only B101 assert_used below threshold; CI skips B101) |
| `pytest tests/test_missed_surface_closure.py` (full file, isolated) | PASS | `103 passed, 1 xfailed in 1.01s` (was: 69 errors, all DETERMINISM VIOLATION on live path) |
| `pytest …::test_mutation_rejects_no_auth[POST-/api/sync/xero]` (the exact reported case, isolated) | PASS | `1 passed in 0.58s` |
| Contamination check, BOTH orders | PASS | `196 passed, 1 xfailed` × 2 (test_missed_surface_closure + test_auth_and_side_effects + test_auth_middleware + test_mounted_app_route_ownership + test_stub_endpoints) |
| Full-suite no-regression (baseline vs fix) | PASS | with fix: 228 failed / 3381 passed / 189 err / 95 violations; baseline (file stashed): 244 failed / 3368 passed / 189 err / 95 violations → delta −16 fail, +13 pass, **0 new errors, 0 new violations**. Pre-existing failures are unrelated branch WIP. |
| Every method call in changed file resolves to a real `def` | yes | `create_fixture_db` (tests/fixtures/fixture_db.py:56), `db_path` (lib/paths.py:41), `data_dir` (lib/paths.py:35), `StateStore._instance` (lib/state_store.py:27) |
| Verification log included in `git add` | yes | included in commit block below |

**Note on workspace:** the checkout drifted to `main` mid-session (started on `fix/tasks-collector-propagation-test`). The fix is currently on the `main` working tree as the ONLY tracked change. The commit block below branches off main first (never commits to main). A duplicate copy of these edits also sits in `git stash@{0}` ("WIP on main") as a safety copy — not dropped.

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Fix test-isolation leak in test_missed_surface_closure.py | tests/test_missed_surface_closure.py + this log | yes — one file, one purpose |
