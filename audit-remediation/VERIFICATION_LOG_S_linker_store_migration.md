# Verification Log — task_project_linker → StateStore migration (Phase 1c, PR B)

**Session:** phase1c (2026-06-04)
**Base:** feat/statestore-write-path (PR A #152) → rebased onto main after #152 merges
**Branch:** refactor/task-project-linker-store

Per-PR log. PR B of Phase 1c; depends on PR A (StateStore.execute_write/query).

## Root cause / contract
`TestTaskProjectLinkerMigration` (v3) requires `lib/task_project_linker.py` to drop raw `sqlite3`,
take a `store=` kwarg on all 5 functions, use `store.query()` for reads and `store.execute_write()`
for the writes. Previously every function opened `sqlite3.connect(db_path)` directly (the anti-pattern
the codebase moved away from) and did set-based UPDATEs.

## Fix
Rewrote all 5 functions:
- Signatures: `(db_path: str | None = None, dry_run: bool = False, store: StateStore | None = None)`.
  `_resolve_store(db_path, store)` returns the passed store, else `StateStore(db_path)` / `StateStore()`.
- Reads (COUNT) → `s.query("SELECT COUNT(*) AS c ...")[0]["c"]`.
- Writes (set-based UPDATE with subqueries) → `s.execute_write(sql, [now])`. These cannot use the
  per-row `store.update(id, data)` helper (they update many rows via subquery), so execute_write is
  the correct primitive.
- `link_all` resolves `s` once and passes `store=s` to the 4 strategy functions; uses `s.query(...)`
  for before/after counts (satisfies `test_S_uses_store_query_for_reads`'s literal `s.query(` check).
- Dropped `import sqlite3`.

No production caller of `task_project_linker` exists (grep: zero importers in lib/api/cli/engine/
scripts; the only `link_*` call elsewhere is `client_truth/linker.auto_link_by_name`, a different
module), so the signature change is safe. Behavioral tests call `link_by_name(store=store)` /
`link_by_name(dry_run=True, store=store)` — both supported.

## Pre-Edit Verification
| File edited | Symbol | Defined at | Confirmed | Callers checked |
|-------------|--------|-----------|-----------|-----------------|
| task_project_linker.py (all 5 fns) | `StateStore.query` / `StateStore.execute_write` | state_store.py (PR A) | yes — execute_write returns rowcount; query returns list[dict] | yes — zero production importers; behavioral tests pass `store=` |
| task_project_linker.py | `StateStore(db_path)` | state_store.py:39 (singleton) | yes — `db_path` optional ctor | n/a |

## Pre-Commit Verification
| Check | Result | Output |
|-------|--------|--------|
| TDD red (before) | CONFIRMED | TestTaskProjectLinkerMigration 4 failed (sqlite3 import/connect, store kwarg, s.query) |
| TDD green (after) | PASS | TestTaskProjectLinkerMigration 5 passed |
| Behavioral (real-DB UPDATEs + dry-run) | PASS | TestTaskProjectLinkerBehavioral 5 passed |
| v3 file overall | IMPROVED | 21 failed → 11 failed (remaining = deferred query()-guard `query_rejects_*` + unrelated TestSchemaOwnershipDefects bucket) |
| ruff / ruff format / bandit | PASS | clean |

Files in this commit: `lib/task_project_linker.py`, this log. One purpose (PR B: linker → StateStore).

## Still deferred (own track, NOT this PR)
`query()` read-only guard + the ~11 live write-via-query() call-site migrations (see PR A log).
Those keep `TestWritePathRule::test_B_query_rejects_*` and `TestWritePathBehavioralExtended::
query_rejects_*` red until that track lands. `TestSchemaOwnershipDefects` (issue_notes/watchers/
identities missing-from-schema) is a separate schema-defect bucket.
