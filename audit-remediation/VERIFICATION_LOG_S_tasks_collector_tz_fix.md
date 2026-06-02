# Verification Log — fix/tasks-collector-tz-priority

**Session:** 25 (post-audit, standalone bugfix)
**Date:** 2026-06-02
**Agent:** Opus 4.8 (1M context)

---

## Pre-Edit Verification

For EVERY method call you add or modify, fill in one row. If any cell is "no" or blank, you cannot commit.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/collectors/tasks.py | `datetime.strptime(due, "%Y-%m-%d")` | stdlib `datetime` (imported tasks.py:9) | yes — returns naive `datetime` | yes — chained `.replace()` returns `datetime` | yes — only caller of `_compute_priority` is `transform` at tasks.py:150 |
| lib/collectors/tasks.py | `.replace(tzinfo=timezone.utc)` | stdlib `datetime.replace` | yes — `timezone` imported tasks.py:9 | yes — returns aware `datetime`, makes `due_date - datetime.now(timezone.utc)` valid (both aware) | yes — result only used in `(due_date - now).days` at tasks.py:193 |

Notes:
- `_compute_priority` (tasks.py:184) is called only by `transform` (tasks.py:150). Grepped `_compute_priority` — 1 definition, 1 call site, plus test calls in tests/test_tasks_collector.py.
- `timezone` and `datetime` already imported at tasks.py:9 — no new imports added.

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` (ruff 0.15.1) |
| `ruff format --check` on changed files | PASS | `1 file already formatted` |
| `bandit -r` on changed files | PASS | no findings (silent) |
| `pytest` (this Mac) | PASS | `tests/test_tasks_collector.py`: 21 passed, 0 failed |
| Every method call in changed files resolves to a real `def` | PASS | only stdlib `datetime.strptime`/`.replace` touched |
| Verification log included in `git add` | PASS | included in command block below |

### Regression evidence (16 unrelated collector failures are pre-existing)

Stashed `lib/collectors/tasks.py` (clean tree) and re-ran the failing files:
`13 failed, 76 passed` — gmail/chat/xero collector-expansion + v4 SyncHealthSurfacing tests
fail identically WITHOUT my change. They do not import `tasks.py`. Not caused or fixed by
this PR. (xero one owned by a separate spawned session per project memory.)

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Tasks collector tz priority fix | lib/collectors/tasks.py + this log | yes |

Working tree also has STAGED changes from unrelated work (`api/chat_webhook_router.py`,
`lib/integrations/chat_commands.py`, `tests/test_auth_and_side_effects.py`) — these are
EXCLUDED. The command block resets the index and adds only the two files above so this PR
stays "separate from everything else" per the task.

---

## Change summary

`lib/collectors/tasks.py:192` — `_compute_priority`:

```python
# before
due_date = datetime.strptime(due, "%Y-%m-%d")          # offset-naive
days_until = (due_date - datetime.now(timezone.utc)).days  # subtracts offset-aware → TypeError

# after
due_date = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc)  # offset-aware
days_until = (due_date - datetime.now(timezone.utc)).days  # both aware → OK
```

Root cause: `strptime` of a date-only string yields a naive datetime; subtracting the
aware `datetime.now(timezone.utc)` raises `TypeError: can't subtract offset-naive and
offset-aware datetimes`. The 7 `TestTasksTransform` failures were transitive — `transform`
(tasks.py:150) calls `_compute_priority` for every active task. Fix interprets the
date-only due date as UTC midnight, which matches the test data (`...T00:00:00.000Z`) and
the existing `datetime.now(timezone.utc)` reference frame. Tests assert correct priority
math and were not modified.
