# Verification Log — fix/action-framework-test-isolation

**Session:** action-framework-test-repair
**Date:** 2026-06-02
**Agent:** Claude Opus 4.8 (1M context)

---

## Problem (verified by reproduction)

`python -m pytest tests/test_action_framework.py -q` in isolation → **10 passed, 21 errors**.

All 21 errors share one root cause:
- `framework` fixture (tests/test_action_framework.py:109-112) builds
  `ActionFramework(store=mock_store, policy_engine=policy_engine, dry_run=False)`.
- `ActionFramework.__init__` (lib/actions/action_framework.py:122-149) calls
  `get_outbox()` at line 143.
- `get_outbox()` (lib/outbox.py:412-419) is a lazy singleton; when `_outbox is None`
  it constructs `SideEffectOutbox(db_path)` → `sqlite3.connect(live_db)` (lib/outbox.py:72).
- conftest `_guarded_sqlite_connect` (tests/conftest.py:215-236) raises
  DETERMINISM VIOLATION on the live DB path.

In the FULL suite an earlier test warms `_outbox`, so `get_outbox()` short-circuits and
these tests pass. In isolation `_outbox` is cold → live DB hit → 21 errors.

Confirmed the sibling A-U1 test
`tests/test_action_schema_fixes.py::TestRejectAction::test_reject_stores_in_error_and_result`
fails identically in isolation — proving this is a shared latent isolation bug, not unique
to the target test.

Secondary issue (the originally-reported symptom): test_action_framework.py:506 asserts
`action["rejection_reason"] == "Not needed"`, but reject_action (action_framework.py:285-296,
"Bug fix A-U1") no longer writes a `rejection_reason` column. It writes
`error = reason` and `result = json.dumps({"rejected_by": ..., "reason": ...})`.

## Pre-Edit Verification

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| tests/test_action_framework.py | `SideEffectOutbox(db_path=...)` | lib/outbox.py:62 (`__init__`, `db_path` param) | yes — `db_path` kwarg used at test_auth_and_side_effects.py:149,377 | yes — returns outbox instance | n/a (test fixture) |
| tests/test_action_framework.py | `patch("lib.outbox.get_outbox", return_value=outbox)` | lib/outbox.py:412 (`def get_outbox`) | yes — proven pattern at test_auth_and_side_effects.py:409 | yes — `__init__` assigns to `self._outbox` (action_framework.py:143) | yes — only caller in __init__ that matters here |
| tests/test_action_framework.py | `create_fixture_db(db_path)` | tests/fixtures/fixture_db.py (imported test_auth_and_side_effects.py:21, test_action_schema_fixes.py:13) | yes — returns conn, used at conftest.py:355, schema_fixes:97 | yes | n/a |
| tests/test_action_framework.py | `reject_action(action_id, rejected_by, reason)` | lib/actions/action_framework.py:274 | yes — writes error+result, no rejection_reason | yes — returns bool | n/a (assertion change only) |
| tests/test_action_framework.py | `_get_proposal(action_id)` | lib/actions/action_framework.py (existing usage at test:484,504) | yes — returns row dict | yes — dict with status/error/result keys | n/a |

## Decision: scope

Fix BOTH at the shared `framework` fixture level:
1. Inject a fixture-DB-backed outbox via `patch` so `get_outbox()` never hits the live DB →
   repairs all 21 isolation errors.
2. Correct the stale `rejection_reason` assertion → read `error` and parse `result` JSON.

Rationale: the task's own verify command runs the WHOLE file. A one-line fix would leave
20/21 tests erroring and the command red — dishonest "green." Both changes are test-only,
one file, one PR.

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check tests/test_action_framework.py` | PASS | "All checks passed!" |
| `ruff format --check tests/test_action_framework.py` | PASS | "1 file already formatted" |
| `bandit -r tests/test_action_framework.py --skip B101,B608` | PASS | zero issues (B101/B608 skipped per pyproject.toml; tests also in exclude_dirs) |
| `pytest tests/test_action_framework.py -q` (isolation) | PASS | "31 passed in 0.21s" (was 10 passed / 21 errors) |
| `pytest tests/test_action_framework.py::...::test_reject_pending_action` | PASS | "1 passed" |
| `python scripts/check_mypy_baseline.py --strict-only` | PASS | "0 errors, baseline stable" (file not in strict islands) |
| Every method call in changed files resolves to a real `def` | PASS | SideEffectOutbox.__init__ outbox.py:66; get_outbox outbox.py:413; reject_action af.py:274; _get_proposal af.py:569 |
| Verification log included in `git add` | YES | (in commit block below) |

### Regression note (out of scope, pre-existing)

`tests/test_action_schema_fixes.py` fails 7 tests in isolation (reproduces on clean main;
those files are byte-identical to main per `git diff main`). Confirmed NOT caused by this
change: that file fails identically with this change stashed. Two root causes there — the
same outbox-singleton live-DB guard issue, plus a separate `get_action_history` issue.
Flagged for a separate task (spawn_task chip raised). NOT fixed here per One-PR-One-Purpose.

Full-suite delta (this branch is a dirty in-flight branch with unrelated failures):
- Baseline (edits stashed): 228 failed, 3383 passed, 189 errors
- With this change:          228 failed, 3404 passed, 168 errors
- Delta: +21 passed, -21 errors, 0 new failures. This change strictly improves the suite.

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Test-only: action_framework test isolation + stale assertion | tests/test_action_framework.py + this log | yes |
