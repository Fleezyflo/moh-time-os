# TASK: Replace f-string SQL with Parameterized Queries
> Brief: PIPELINE_HARDENING | Phase: 4 | Sequence: 4.1 | Status: PENDING

## Context

11 files in `lib/` use f-string interpolation in SQL queries, violating the CLAUDE.md rule: "No f-string SQL — use parameterized queries or lib/query_engine.py."

**Files with f-string SQL:**
- `lib/store.py`
- `lib/state_store.py`
- `lib/entities.py`
- `lib/items.py`
- `lib/v5/database.py`
- `lib/v5/api/routes/issues.py`
- `lib/v5/api/routes/signals.py`
- `lib/v5/issues/formation_service.py`
- `lib/v5/services/signal_service.py`
- `lib/ui_spec_v21/time_utils.py`
- `lib/migrations/v4_milestone1_truth_proof.py`

**Note:** Some f-string SQL interpolates **table names or column names** (identifiers), not user input. SQLite parameterized queries (`?` placeholders) only work for values, not identifiers. For identifier interpolation:
- Use allowlists (validate identifier against known table/column names)
- Or use string formatting but with explicit validation

## Objective

Eliminate f-string SQL for value interpolation. For identifier interpolation, add validation.

## Instructions

1. For each file, categorize each f-string SQL as:
   - **Value interpolation** (e.g., `f"WHERE id = '{some_var}'"`) → convert to `"WHERE id = ?"` with params
   - **Identifier interpolation** (e.g., `f"SELECT * FROM {table_name}"`) → add allowlist validation

2. Value interpolation fix pattern:
   ```python
   # BEFORE (bad):
   cursor.execute(f"SELECT * FROM tasks WHERE id = '{task_id}'")

   # AFTER (good):
   cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
   ```

3. Identifier interpolation fix pattern:
   ```python
   # BEFORE (risky):
   cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,))

   # AFTER (safe):
   VALID_TABLES = {"tasks", "projects", "clients", "signals", ...}
   if table_name not in VALID_TABLES:
       raise ValueError(f"Invalid table: {table_name}")
   cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,))
   ```

4. Skip migration files (`lib/migrations/`) if they only run once and don't accept user input. Document the skip with a comment.

5. Verify by re-running grep:
   ```bash
   grep -rn "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE\|f\".*DELETE\|f'.*SELECT\|f'.*INSERT\|f'.*UPDATE\|f'.*DELETE" lib/ --include="*.py" -l
   ```
   Target: only migration files remain (documented exception).

## Preconditions
- [ ] PH-3.1 and PH-3.2 complete (data population done, no schema changes during this task)

## Validation
1. `grep` for f-string SQL in `lib/` (excluding `lib/migrations/`) returns empty
2. `pytest tests/ -q` — all tests pass (no regressions from query changes)
3. Manual spot-check: run 2-3 key functions that were modified to verify data still returns correctly

## Acceptance Criteria
- [ ] Zero f-string value interpolation in lib/ (excluding migrations)
- [ ] All identifier interpolation validated against allowlists
- [ ] No test regressions
- [ ] Migration files documented as exceptions

## Output
- Modified: 8-10 source files in lib/
- Skipped: lib/migrations/ files (documented)
