# TASK: Fix asana_project_map Schema Mismatch in Task Project Linker Tests
> Brief: TEST_REMEDIATION | Phase: 3 | Sequence: 3.1 | Status: PENDING

## Context

4 tests in `tests/test_task_project_linker.py` fail with `sqlite3.OperationalError: no such column: m.asana_name`.

**Root cause:** The test fixture creates `asana_project_map` with the wrong schema:

```sql
-- Test fixture (WRONG):
CREATE TABLE asana_project_map (
    project_name TEXT,
    asana_gid TEXT
);

-- Production schema (CORRECT):
CREATE TABLE asana_project_map (
    asana_gid TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asana_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

The production code in `lib/task_project_linker.py` queries `m.asana_name` and `m.project_id`, but the test fixture only has `project_name` and `asana_gid`.

**Live DB confirms:** The `asana_project_map` table has columns `(asana_gid, project_id, asana_name, created_at)` with 36 rows.

## Objective

Align the test fixture schema with production, and update test data to use correct column names.

## Instructions

1. Read `tests/test_task_project_linker.py` to find the fixture that creates `asana_project_map`.

2. Update the `CREATE TABLE asana_project_map` in the test fixture to match production:
   ```sql
   CREATE TABLE asana_project_map (
       asana_gid TEXT PRIMARY KEY,
       project_id TEXT NOT NULL,
       asana_name TEXT,
       created_at TEXT NOT NULL DEFAULT (datetime('now'))
   );
   ```

3. Update all `INSERT INTO asana_project_map` statements to use the correct columns:
   - `project_name` → `asana_name`
   - Add `project_id` column with appropriate test values

4. Read `lib/task_project_linker.py` to verify the queries reference `m.asana_name` and `m.project_id`. Ensure the test data matches what the queries expect.

5. Verify the test assertions still make sense with the corrected schema. The linking logic matches `LOWER(TRIM(t.project)) = LOWER(TRIM(m.asana_name))` — ensure test data satisfies this.

## Preconditions
- [ ] TR-1.1, TR-1.2, TR-2.1 complete (all import issues resolved)

## Validation
1. `pytest tests/test_task_project_linker.py -v` — all tests pass (was 6 pass / 4 fail, now 10/10)
2. Specifically verify:
   - `test_links_via_map` — PASS
   - `test_link_all_runs_all_strategies` — PASS
   - `test_link_all_dry_run` — PASS
   - `test_unmatched_tasks_stay_unlinked` — PASS

## Acceptance Criteria
- [ ] Test fixture schema matches production `asana_project_map`
- [ ] All 4 previously-failing tests now pass
- [ ] No other tests regressed

## Output
- Modified: `tests/test_task_project_linker.py` (fixture schema + test data)
