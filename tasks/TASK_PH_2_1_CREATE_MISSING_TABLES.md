# TASK: Create Missing Tables (client_identities, resolution_queue)
> Brief: PIPELINE_HARDENING | Phase: 2 | Sequence: 2.1 | Status: PENDING

## Context

Two tables are referenced by pipeline code but don't exist in the DB:

1. **`client_identities`** — Used by `lib/normalizer.py` line 256 for email/domain → client matching.
   Schema defined in `lib/migrations/spec_schema_migration.py` line 217 but migration was never run.

2. **`resolution_queue`** — Used by `lib/resolution_queue.py` for surfacing items needing manual resolution.
   Schema defined in `lib/migrations/spec_schema_migration.py` line 296 but migration was never run.

## Objective

Create both tables by invoking the existing migration functions.

## Instructions

1. Verify tables don't exist:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('data/moh_time_os.db')
   c = conn.cursor()
   for t in ['client_identities', 'resolution_queue']:
       c.execute(f\"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'\")
       print(f'{t}: {\"exists\" if c.fetchone() else \"MISSING\"}\')
   "
   ```

2. Read the CREATE TABLE definitions in `lib/migrations/spec_schema_migration.py`:
   - `create_client_identities_table()` (line 209)
   - `create_resolution_queue_table()` (line 288)

3. Run the migration functions:
   ```python
   from lib.migrations.spec_schema_migration import (
       create_client_identities_table,
       create_resolution_queue_table,
   )
   import sqlite3
   conn = sqlite3.connect('data/moh_time_os.db')
   cursor = conn.cursor()
   create_client_identities_table(cursor)
   create_resolution_queue_table(cursor)
   conn.commit()
   ```

4. If the migration functions have import issues (they may depend on compat shims from Brief 6), extract and run the CREATE TABLE SQL directly.

5. Verify:
   ```sql
   SELECT name FROM sqlite_master WHERE type='table' AND name IN ('client_identities', 'resolution_queue');
   PRAGMA table_info(client_identities);
   PRAGMA table_info(resolution_queue);
   ```

## Preconditions
- [ ] PH-1.1 complete (lane alignment — no dependency, but phase ordering)
- [ ] PH-1.2 complete (communications columns)

## Validation
1. `client_identities` table exists with columns: id, client_id, identity_type, identity_value, created_at
2. `resolution_queue` table exists with columns matching spec_schema_migration.py definition
3. `python3 -c "from lib.resolution_queue import ResolutionQueue"` succeeds
4. `pytest tests/ -q` — no regressions

## Acceptance Criteria
- [ ] Both tables created in live DB
- [ ] Schemas match spec_schema_migration.py definitions
- [ ] Pipeline modules can reference both tables without crash

## Output
- Modified: live DB (2 tables created)
- No source file changes expected (migration code already exists)
