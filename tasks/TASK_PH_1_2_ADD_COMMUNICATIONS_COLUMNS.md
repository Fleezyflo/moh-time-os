# TASK: Add Missing Communications Columns
> Brief: PIPELINE_HARDENING | Phase: 1 | Sequence: 1.2 | Status: PENDING

## Context

`lib/normalizer.py` (lines 232-320) queries 3 columns on `communications` that don't exist:
- `from_domain` — derived from `from_email`, used for client identity matching
- `client_id` — linked client, populated by normalizer
- `link_status` — 'linked' / 'unlinked', set after client matching

Current `communications` schema has 21 columns but none of these 3.

## Objective

Add the 3 missing columns to `communications` via ALTER TABLE so the normalizer can run.

## Instructions

1. Verify current schema:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('data/moh_time_os.db')
   c = conn.cursor()
   c.execute('PRAGMA table_info(communications)')
   for r in c.fetchall(): print(r[1], r[2])
   "
   ```

2. Add the missing columns:
   ```sql
   ALTER TABLE communications ADD COLUMN from_domain TEXT;
   ALTER TABLE communications ADD COLUMN client_id TEXT;
   ALTER TABLE communications ADD COLUMN link_status TEXT DEFAULT 'unlinked';
   ```

3. Create a migration script at `lib/migrations/add_communications_columns.py`:
   - Idempotent: check if columns exist before adding
   - Log each addition
   - Return count of columns added

4. Run the migration on live DB.

5. Verify the normalizer can reference the columns:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('data/moh_time_os.db')
   c = conn.cursor()
   c.execute('SELECT from_domain, client_id, link_status FROM communications LIMIT 1')
   print('Columns accessible')
   "
   ```

## Preconditions
- [ ] Brief 6 complete

## Validation
1. All 3 columns exist in `communications` table
2. `from_domain` is TEXT, nullable
3. `client_id` is TEXT, nullable
4. `link_status` is TEXT, default 'unlinked'
5. `pytest tests/ -q` — no regressions

## Acceptance Criteria
- [ ] 3 new columns added to communications
- [ ] Migration script is idempotent
- [ ] Normalizer SQL no longer crashes on missing columns

## Output
- Created: `lib/migrations/add_communications_columns.py`
- Modified: live DB (3 columns added)
