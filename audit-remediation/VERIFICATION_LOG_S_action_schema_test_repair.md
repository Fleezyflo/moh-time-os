# Verification Log — fix/test-action-schema-outbox-isolation

**Session:** action_schema_test_repair (spawned)
**Date:** 2026-06-02
**Agent:** Claude (Opus 4.8, 1M)

---

## Root Cause (investigated before any edit)

All 7 failures in `tests/test_action_schema_fixes.py` (in isolation) terminate at the
SAME traceback:

```
test body line N: fw = ActionFramework(store=fixture_store, dry_run=True)
lib/actions/action_framework.py:143: self._outbox = get_outbox()
lib/outbox.py:419: _outbox = SideEffectOutbox(db_path)   # db_path=None → live DB path
lib/outbox.py:79 -> :72: conn = sqlite3.connect(self.db_path)
tests/conftest.py:230: RuntimeError DETERMINISM VIOLATION (live DB)
```

`get_outbox()` (lib/outbox.py:413-420) is a module-level lazy singleton. When `_outbox`
is cold (None), it constructs `SideEffectOutbox(None)`, which resolves to the LIVE DB
path and opens it via `sqlite3.connect` — tripping the conftest guard
(tests/conftest.py:215-236). In the full suite, an earlier test
(tests/test_auth_and_side_effects.py) warms `_outbox` to a temp DB, so the singleton is
already non-None by the time these tests run → they pass. In isolation it is cold → fail.

**Proof of single cause:**
- `pytest tests/test_action_schema_fixes.py -p no:randomly` → 7 failed, 5 passed (cold)
- `pytest tests/test_auth_and_side_effects.py tests/test_action_schema_fixes.py` → 61 passed (warm)

**Second hypothesis (real get_action_history column bug) — DISPROVEN.**
`get_action_history` (action_framework.py:509-535) selects on columns
`status`, `target_system`, `type`, `created_at`. The `actions` table (lib/schema.py:795-811)
defines all four. The A-S1 fix already replaced the phantom `target_id` with `target_system`.
The 3 TestGetActionHistory failures never reach the query — they fail at construction
(`ActionFramework(...)`), same as the other 4. No code bug; test-isolation only.

## Fix

Inject a temp-DB-backed `SideEffectOutbox` via `patch("lib.outbox.get_outbox", ...)` during
`ActionFramework` construction. Convert the 7 inline `ActionFramework(store=fixture_store,
dry_run=True)` call sites to a single `framework` fixture that depends on `fixture_store`,
mirroring tests/test_action_framework.py:112-136 and tests/test_auth_and_side_effects.py:409.
Test-only change. No production code touched.

---

## Pre-Edit Verification

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| tests/test_action_schema_fixes.py | SideEffectOutbox(db_path=...) | lib/outbox.py:60 (`__init__`) | yes — `__init__(self, db_path: str \| None = None)` | yes — returns instance | reference: test_action_framework.py:126, test_auth_and_side_effects.py |
| tests/test_action_schema_fixes.py | patch("lib.outbox.get_outbox", return_value=outbox) | lib/outbox.py:413 (`get_outbox`) | yes — patched symbol exists; ActionFramework calls `get_outbox()` at action_framework.py:141-143 | yes — returns SideEffectOutbox | only caller of get_outbox in ctor is action_framework.py:143 |
| tests/test_action_schema_fixes.py | ActionFramework(store=..., dry_run=True) | lib/actions/action_framework.py:122 (`__init__`) | yes — `__init__(self, store, policy_engine=None, approval_policies=None, dry_run: bool=False)` | yes — returns instance | reference fixture: test_action_framework.py:128 |
| tests/conftest.py (PR #2 root fix) | `lib.outbox._outbox` reset + `MOH_TIME_OS_DB` setenv | outbox singleton lib/outbox.py:409; env override lib/paths.py:7,49-50 + lib/db.py:57 | yes — `db_path()` reads `MOH_TIME_OS_DB` first; `SideEffectOutbox.__init__` defaults `db_path` to `get_db_path_str()` (outbox.py:66-67) | yes — points cold-singleton construction at session `fixture_db_path` (guard-permitted; tmp file named `fixture_test.db`, never matches `_FORBIDDEN_DB_PATTERNS`) | callers: ActionFramework ctor (action_framework.py:143). Composes with existing `patch("lib.outbox.get_outbox")` in test_action_framework.py / test_action_schema_fixes.py and explicit `SideEffectOutbox(db_path=...)` in test_auth_and_side_effects.py — patches/explicit paths override; env only used on cold construction. No test asserts `MOH_TIME_OS_DB` absent (grep: only setters + override-test). |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` |
| `ruff format --check` on changed files | PASS | `1 file already formatted` |
| `bandit` on changed file | PASS (no new findings) | HEAD baseline 40L/4M/0H == edited 40L/4M/0H; all B608/B101 are pre-existing fixture/assert lines, none added |
| `pytest tests/test_action_schema_fixes.py -q` (isolation) | PASS | was `7 failed, 5 passed` → now `12 passed` |
| Regression: action_framework + action_schema_fixes + auth_and_side_effects | PASS | `92 passed` (fixed-order, `-p no:randomly`) |
| Every method call in changed files resolves to a real `def` | yes | SideEffectOutbox@outbox.py:60, get_outbox@outbox.py:413, ActionFramework@action_framework.py:122 |
| Verification log included in `git add` | yes | this file |

**Out-of-scope pre-existing failures (NOT caused by this change):**
- `tests/test_missed_surface_closure.py:188` has an unresolved git merge-conflict marker
  (`<<<<<<< Updated upstream`) on disk — matches the `UU` unmerged state in git status at
  session start. Blocks full-suite collection. Not this file; not touched.
- `tests/test_trajectory.py` and others fail/error IN ISOLATION (48 errors run alone) from
  the same repo-wide cold-singleton determinism debt this audit is remediating. Verified
  independent of this change. The full `tests/` suite does not pass on clean main for these
  unrelated reasons; this PR fixes only `test_action_schema_fixes.py`.

## PR Scope Check (TWO PRs, sequenced)

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| PR #1: per-fixture repair for test_action_schema_fixes.py | tests/test_action_schema_fixes.py + this log | yes — single purpose, the chip task |
| PR #2: conftest-root outbox-singleton reset | tests/conftest.py + this log | yes — generalizes the fix; also fixes test_action_integration.py (no patch was there) |

## PR #2 (conftest) verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check tests/conftest.py` | PASS | `All checks passed!` |
| `ruff format --check tests/conftest.py` | PASS | `1 file already formatted` |
| `test_action_integration.py` isolation | PASS | was `10 passed, 7 errors` → `17 passed` (NO per-fixture patch — autouse fixture did it) |
| Four action files together | PASS | `109 passed` |
| Full suite delta vs baseline (excl conflict file, fixed order) | NET POSITIVE | baseline 3311p/218f/168e → **3364p/220f/113e** = +53 passed, −55 errors |
| Suspicious `test_key_manager.py` — regression check | NOT MINE | 3 passed/47 errors IN ISOLATION both WITH and WITHOUT the conftest hunk → pre-existing; +2 full-suite "failed" is pytest-randomly order-shuffle noise, not a new break |
| No test asserts `MOH_TIME_OS_DB` absent | yes | grep tests/: only `monkeypatch.setenv` setters + one override-test (test_cross_cutting_correctness.py:181); zero `delenv`/`not in` assertions |
