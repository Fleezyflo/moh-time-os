# Verification Log — write-path query() guard + writer migration

**Session:** write-path-guard (post-#152/#154)
**Date:** 2026-06-04
**Agent:** Claude Opus 4.8 (1M)

This session migrates ~11 write-via-`query()` call sites to `store.execute_write()`,
then adds a read-only guard to `StateStore.query()`. Split into 3 PRs:

- **PR-A** — `lib/autonomous_loop.py` (daemon-critical, isolated)
- **PR-B** — `debt_tracker.py`, `linker.py` (×2), `commitment_manager.py` (×4), `state_tracker.py`, `block_manager.py` (×2)
- **PR-C** — `lib/state_store.py` guard in `query()`

---

## Pre-Edit Verification

Every method call added/modified. All verified by reading the source this session.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| lib/autonomous_loop.py:1310 | `store.execute_write` | lib/state_store.py:266 | yes — `execute_write(self, sql, params=None) -> int` | yes — return value ignored at call site (was `query()` list, now int; unused) | yes — call site reads in `_process_commitment_truth`, return unused; wrapped in `except (sqlite3.Error, ValueError, OSError)` which still catches execute_write errors |
| lib/capacity_truth/debt_tracker.py:69 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `resolve_debt`, return unused |
| lib/client_truth/linker.py:62 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `link_project_to_client` UPDATE branch, return unused |
| lib/client_truth/linker.py:83 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `unlink_project`, return unused |
| lib/commitment_truth/commitment_manager.py:201 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `link_commitment_to_task`, return unused |
| lib/commitment_truth/commitment_manager.py:221 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `unlink_commitment`, return unused |
| lib/commitment_truth/commitment_manager.py:231 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `mark_done`, return unused |
| lib/commitment_truth/commitment_manager.py:240 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `mark_broken`, return unused |
| lib/state_tracker.py:122 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `mark_collected`, return unused |
| lib/time_truth/block_manager.py:171 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `schedule_task`, return unused; `store.update()` called right after (line 176) |
| lib/time_truth/block_manager.py:193 | `store.execute_write` | lib/state_store.py:266 | yes | yes — return unused | yes — `unschedule_task`, return unused; `store.update()` called right after (line 199) |
| lib/state_store.py:254 (query guard) | n/a (new internal logic) | lib/state_store.py:254 | n/a — adds first-keyword parse + RuntimeError | n/a | yes — grepped every `.query(` caller in lib/ api/ cli/ engine/; after migration all remaining are reads |

**Re-grep finding (Pre-Edit Gate caught it):** the task's call-site list named `linker.py:83` only.
A re-grep of multi-line `.query(` calls found a SECOND write in `linker.py` at lines 62–69
(`UPDATE client_projects` in `link_project_to_client`). Both migrate. Total = 11 sites, 6 files.

**Reference pattern:** `lib/task_project_linker.py` (PR #152) — reads via `query()`, writes via
`execute_write()`, module docstring documents the rule. This session mirrors that exactly.

## Pre-Commit Verification (PR-A)

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` (lib/autonomous_loop.py, tests/test_autonomous_loop_write_path.py) |
| `ruff format --check` on changed files | PASS | `2 files already formatted` |
| `bandit -r` on changed files | PASS | autonomous_loop.py: 0 issues. Test file: 8× B101 (asserts) — skipped by `[tool.bandit] skips=["B101"]` + `exclude_dirs=["tests"]` |
| `pytest` (this Mac) | PASS | `tests/test_autonomous_loop_write_path.py ... 3 passed`; regression `test_autonomous_loop.py + test_autonomous_operations.py 42 passed` |
| Every method call in changed files resolves to a real `def` | PASS | `execute_write` → lib/state_store.py:266 |
| Verification log included in `git add` | PENDING (in command block) | |

**TDD evidence (PR-A):** structural test `test_S_mark_processed_uses_execute_write` RED before edit
(`AssertionError: ... must mark emails processed via store.execute_write()`), GREEN after.
Behavioral tests passed before+after (they guard the live write path; go red if a future guard
rejects an unmigrated write).

## Pre-Commit Verification (PR-B)

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` (5 src files + test) |
| `ruff format --check` on changed files | PASS | `6 files already formatted` (linker.py + test file reformatted with ruff 0.15.1 = pre-commit pin) |
| `bandit -r` on changed files | PASS | 0 Low/Medium/High on all 5 src files; tests excluded by `[tool.bandit]` |
| `pytest` (this Mac) | PASS | `tests/test_truth_helpers_write_path.py 15 passed`; regression `test_ws4_freshness_wiring + test_collector_silent_failures 56 passed` |
| Every method call in changed files resolves to a real `def` | PASS | `execute_write` → state_store.py:266; `BlockManager.schedule_task` sig is `(task_id, block_id)` (test arg-order bug found+fixed) |
| Verification log included in `git add` | PENDING (in command block) | |

**TDD evidence (PR-B):** 5 structural `test_S_*_uses_execute_write` RED before edits, GREEN after.
10 behavioral tests passed before+after (real temp-DB StateStore proves each write persists).
`commitments` test table uses the LIVE daemon shape (`commitment_id` PK) — the canonical
fixture/schema_engine schema diverges (has `id`, no `commitment_id`); the commitment_manager
SQL is written for the live shape. See "Schema drift note" below.

## Pre-Commit Verification (PR-C — guard)

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | PASS | `All checks passed!` (state_store.py + guard test) |
| `ruff format --check` on changed files | PASS | `2 files already formatted` |
| `bandit -r` on changed files | PASS | state_store.py: 0 Low/Medium/High |
| `pytest` (this Mac) | PASS | guard edge-cases `11 passed`; the 7 named contract tests `7 passed` |
| TestWritePathRule + TestWritePathBehavioralExtended green | PASS | `test_B_query_rejects_insert/update/delete`, `..._create/drop/alter_table`, `..._allows_select` all PASS |
| Daemon path (autonomous_loop) still works | PASS | smoke: `read before=0 after_write=1 query_write_blocked=True` → DAEMON PATH SMOKE: OK |
| Verification log included in `git add` | PENDING (in command block) | |

**Guard implementation:** `_first_sql_keyword()` strips leading whitespace + `--`/`/* */`
comments (repeatedly), reads first word, uppercases. `query()` raises
`RuntimeError("query() is read-only; use execute_write()")` when that keyword is in
`_WRITE_KEYWORDS` (INSERT/UPDATE/DELETE/REPLACE/CREATE/DROP/ALTER/TRUNCATE/VACUUM/ATTACH/
DETACH/REINDEX). SELECT/WITH/EXPLAIN/PRAGMA/VALUES pass.

**Known limitation (documented, not a bug):** a `WITH cte AS (...) INSERT/UPDATE/DELETE`
data-modifying CTE would pass the guard (first keyword WITH). No such statement exists in the
codebase (static scan: 206 literal `query()` calls are all SELECT; the rest pass `safe_sql.select`
/ `q="SELECT..."` vars). The guard is defense-in-depth behind already-migrated writers, not the
sole barrier.

## FULL-SUITE REGRESSION DELTA (the decisive check)

Ran `pytest tests/` with my changes, then stashed everything (`git stash -u`) and re-ran on
pristine origin/main (`4169434`), diffed the FAILED lists:

- Pristine HEAD: **98 failures**. With my changes: **91 failures**.
- **NEW failures introduced by my changes: 0** (empty diff).
- **Fixed: 7** — the 6 write-path guard tests (this work) + 1 `test_daemon_resilience` (from the
  OTHER agent's uncommitted `lib/daemon.py` `except Exception` fix that happens to be in the tree;
  NOT mine, EXCLUDED from my commits).
- The 91 remaining failures are pre-existing rot (the known "CI gates only 7 subdirs" cluster),
  none touched by this work.

## Out-of-scope items flagged (NOT fixed here)

- **2 pre-existing `tests/test_task_project_linker.py` failures** (`test_correct_client_id`:
  `assert None == 'c1'`; `test_link_all_runs_all_strategies`: `assert 6 > 6`). Fail on pristine
  HEAD. That file is PR #152's (untouched here). Spawned as a separate task.
- **Schema drift:** live `commitments` has `commitment_id` PK; canonical schema_engine/fixture
  has `id` and no `commitment_id`. commitment_manager link/mark SQL is written for the live shape.
  Out of scope for a write-path migration; flagged for follow-up.
- **`lib/daemon.py`** has another agent's uncommitted `except Exception` resilience change in this
  shared checkout. EXCLUDED from all three PRs (explicit `git add` paths only).

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| PR-A daemon writer | lib/autonomous_loop.py + tests/test_autonomous_loop_write_path.py + this log | yes |
| PR-B truth writers | debt_tracker, linker, commitment_manager, state_tracker, block_manager + tests/test_truth_helpers_write_path.py + this log | yes |
| PR-C query guard | lib/state_store.py + tests/test_state_store_query_guard.py + this log | yes |

**Merge order is load-bearing: A → B → C.** The guard (C) rejects `query()` writes; if it merges
before A and B, the daemon + truth writers break. PR-C must merge LAST.
