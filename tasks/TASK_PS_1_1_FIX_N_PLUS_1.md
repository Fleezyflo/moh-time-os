# PS-1.1: Fix N+1 Queries + Add Indexes

## Objective
Eliminate all N+1 query patterns in API endpoints and add indexes for every frequently queried column.

## Context
Investigation found N+1 patterns in `api/spec_router.py`:
- Lines 697-700: 4 subqueries per row counting tasks by assignee, status, overdue, completion
- Pattern: `for row in cursor.fetchall()` followed by per-row queries (lines 453, 585, 605, 664, 709, 787)
- No join optimization in team/person endpoint aggregations

The DB has 80+ tables and 556MB of data. Missing indexes on frequently filtered/joined columns cause full table scans.

## Implementation

### N+1 Fixes
Replace per-row subqueries with JOINs or window functions:
```sql
-- BEFORE (N+1): for each person, query tasks
SELECT * FROM team_members;
-- then for EACH row:
SELECT COUNT(*) FROM tasks WHERE assignee_id = ?;
SELECT COUNT(*) FROM tasks WHERE assignee_id = ? AND completed = 1;
SELECT COUNT(*) FROM tasks WHERE assignee_id = ? AND due_on < date('now') AND completed = 0;

-- AFTER (single query with aggregation):
SELECT
    tm.*,
    COUNT(t.id) AS task_count,
    SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed_count,
    SUM(CASE WHEN t.due_on < date('now') AND t.completed = 0 THEN 1 ELSE 0 END) AS overdue_count
FROM team_members tm
LEFT JOIN tasks t ON t.assignee_id = tm.id
GROUP BY tm.id;
```

### Index Additions
```sql
-- Foreign keys (should already exist, verify)
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_communications_client ON communications(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_contact ON invoices(contact_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_calendar ON calendar_events(calendar_id);
CREATE INDEX IF NOT EXISTS idx_signals_entity ON signals_unified(entity_type, entity_id);

-- Frequently filtered columns
CREATE INDEX IF NOT EXISTS idx_tasks_due_completed ON tasks(due_on, completed);
CREATE INDEX IF NOT EXISTS idx_tasks_section ON tasks(section_id);
CREATE INDEX IF NOT EXISTS idx_communications_date ON communications(date);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_patterns_severity ON patterns(severity);
CREATE INDEX IF NOT EXISTS idx_resolution_queue_status ON resolution_queue(status);
```

### Query Audit
Run `EXPLAIN QUERY PLAN` on every API endpoint query. Flag any that show `SCAN TABLE` instead of `SEARCH TABLE USING INDEX`.

## Validation
- [ ] Zero N+1 patterns remaining (grep for per-row query patterns)
- [ ] All foreign key columns indexed
- [ ] EXPLAIN QUERY PLAN shows index usage for all hot queries
- [ ] API response times improve (measure before/after)
- [ ] No regressions in existing tests

## Files Modified
- `api/spec_router.py` — rewrite N+1 queries as JOINs
- `api/intelligence_router.py` — audit and fix
- `lib/db/migrations/` — add index migration

## Estimated Effort
Medium-Large — ~200 lines of query rewrites + index creation
