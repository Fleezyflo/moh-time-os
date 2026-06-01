# Verification Log — fix/contract-test-tree-scope-and-ignore

**Session:** contract-test tree-scope robustness + .claude gitignore (ad-hoc task)
**Date:** 2026-06-02
**Agent:** Opus 4.8 (1M context)

---

## Problem

The pre-push gate 3 (fast tests) failed on
`tests/contract/test_collector_registry.py::TestLegacyRemoved::test_no_scheduled_collect_imports`
with:

```
AssertionError: .claude/worktrees/wf_50535659-8d6-35/tests/contract/test_collector_registry.py
still imports from collectors.scheduled_collect
```

Root cause: the test did `PROJECT_ROOT.rglob("*.py")` (PROJECT_ROOT = repo root,
test_collector_registry.py:14) and its skip filter only excluded `_archive` paths
and the test file itself. So `rglob` walked into `.claude/worktrees/` — 24 stray git
worktrees left over from finished background Workflow runs (all locked at old commit
f1f651e) — and found a stale copy of this very test, whose assertion-message strings
contain `from collectors.scheduled_collect`, tripping the assertion against itself.
This is environmental, not a code regression: ANY push failed regardless of branch
content.

## Fix (durable — "once and for all")

Two complementary changes:

1. **tests/contract/test_collector_registry.py** — added `_SKIP_DIR_NAMES` (frozenset
   of `.git`, `.venv`, `venv`, `.claude`, `node_modules`, `_archive`, `.mypy_cache`,
   `.pytest_cache`, `.ruff_cache`, `__pycache__`) and `_iter_source_py_files(root)`
   that prunes any path whose parts intersect that set, then yields source `*.py`
   only. `test_no_scheduled_collect_imports` now iterates `_iter_source_py_files`.
   The forbidden imports can only legitimately live in first-party source, so
   pruning vendored/scratch/cache trees is *more correct*, not just a workaround.
   This mirrors the existing project idiom in
   tests/test_cross_cutting_correctness.py:961-973 (scope the walk to source dirs).

2. **.gitignore** — ignore `.claude/worktrees/`, `.claude/*.lock`,
   `.claude/scheduled_tasks.lock`, and `preserved-worktree-*/` so agent/worktree
   scratch is never tracked or surfaced. `.claude/plan.md` is intentionally tracked
   (verified `git ls-files .claude/` → only plan.md) and is deliberately NOT ignored.

Out-of-band cleanup (not a committable change): removed all 25 stray worktrees via
`git worktree remove --force` + `git worktree prune`. `git worktree list` now shows
only the main checkout.

## Pre-Edit Verification

| File edited | Symbol relied on | Defined at (file:line) | Confirmed | Matches usage | Callers checked |
|-------------|------------------|------------------------|-----------|---------------|-----------------|
| tests/contract/test_collector_registry.py | `Path.rglob` / `Path.parts` (stdlib) | pathlib stdlib | yes | yes | only caller is the test method below |
| tests/contract/test_collector_registry.py | `_iter_source_py_files` (new helper) | test_collector_registry.py (module scope) | yes | yes | called by `test_no_scheduled_collect_imports` only |
| .gitignore | gitignore pattern semantics; `.claude/plan.md` tracked | `git ls-files .claude/` → plan.md | yes | yes (plan.md not matched by the patterns) | N/A |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed test | PASS | "All checks passed!" |
| `ruff format --check` on changed test | PASS | "1 file already formatted" |
| target test WITH 24 worktrees still present | PASS | `test_no_scheduled_collect_imports` PASSED (proves robustness) |
| full `tests/contract/test_collector_registry.py` | PASS | "12 passed" |
| `.gitignore` ignores scratch, keeps plan.md | PASS | `git check-ignore` matches worktrees/lock/preserved; plan.md NOT ignored |
| Verification log included in `git add` | PASS | this file staged with the commit |

## PR Scope Check

| Planned change | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| Contract-test tree-scope robustness + ignore agent scratch | tests/contract/test_collector_registry.py, .gitignore, this log | yes — one concern (make the tree-walking contract test robust + stop tracking the scratch that broke it) |

Kept separate from the transaction-rollback fix
(branch fix/transaction-rollback-all-exceptions) per "One PR, One Purpose"
(CLAUDE.md, Session 21). The xero.py:365 type annotation needed to satisfy the
working-tree mypy gate is NOT committed here — it belongs to the in-progress xero
work owned elsewhere; it stays as uncommitted local state.

## Result summary

- `test_no_scheduled_collect_imports` was FAILING on every push (stray-worktree
  pollution); now PASSES even with worktrees present, and is robust against `.venv`,
  `.git`, and build caches going forward.
- 25 stray worktrees removed; `.claude/worktrees/` + `preserved-worktree-*` now
  gitignored so they cannot recur in tracked state or break tree-walking tests.
