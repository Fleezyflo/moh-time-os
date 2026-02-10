# Safety + Provenance + Parity Foundation

This document describes the safety mechanisms that ensure every DB write is attributable, valid state transitions are enforced, and root cause is always answerable.

## Overview

The safety system provides:

1. **DB-Level Invariants**: Triggers that ABORT invalid state transitions
2. **Write Context**: Every write must have actor/request_id/source attribution
3. **Audit Logging**: Append-only log of all DB writes with before/after state
4. **Schema Assertions**: CI gates that catch drift in schema, triggers, and indexes
5. **Ripgrep Guardrails**: Static analysis to prevent writes to legacy tables

## Write Context

### How It Works

Every DB write must go through a `WriteContext` that sets attribution metadata:

```python
from lib.safety import WriteContext

with WriteContext(conn, actor="user123", source="api", request_id="req-abc"):
    conn.execute("UPDATE inbox_items_v29 SET ...")
    conn.commit()
```

The context sets a row in `write_context_v1` that triggers use to:
1. **Validate** that context exists (ABORT if not)
2. **Log** the write to `db_write_audit_v1` with full attribution

### Context Fields

| Field | Description | Example |
|-------|-------------|---------|
| `actor` | Who performed the write | `"moh"`, `"system"`, `"detector-xyz"` |
| `source` | Where the write originated | `"api"`, `"migration"`, `"tooling"` |
| `request_id` | Unique ID for this request/job | `"req-abc123"` |
| `git_sha` | Git commit SHA (auto-detected) | `"5dedbd4"` |

### API Integration

The API automatically sets write context for mutation endpoints:

```python
@spec_router.post("/inbox/{item_id}/action")
async def execute_inbox_action(
    item_id: str,
    request: InboxActionRequest,
    actor: str = Query(...),
    request_id: str = Depends(get_request_id),
):
    with get_db_with_context(actor=actor, request_id=request_id, source="api") as conn:
        # All writes are attributed
        ...
```

The `X-Request-Id` header is propagated if provided, otherwise auto-generated.

## Manual Database Operations

### Using db_exec

For manual database operations, use the `tools/db_exec.py` wrapper:

```bash
# Read query (context logged but not enforced for reads)
python tools/db_exec.py --actor moh --source tooling "SELECT * FROM inbox_items_v29 LIMIT 5"

# Write query (context required)
python tools/db_exec.py --actor moh --source tooling \
  "UPDATE inbox_items_v29 SET note = 'fixed' WHERE id = 'xxx'"

# Maintenance mode (for bulk operations)
python tools/db_exec.py --actor moh --source maintenance --maintenance \
  "UPDATE inbox_items_v29 SET severity = 'low' WHERE type = 'orphan'"
```

The wrapper:
- Requires `--actor` and `--source` flags
- Auto-generates `request_id` and detects `git_sha`
- Sets write context before executing SQL
- Shows audit trail after writes

### Maintenance Mode

For bulk operations that would affect many rows:

```python
from lib.safety.migrations import enable_maintenance_mode, disable_maintenance_mode

# Enable maintenance mode
enable_maintenance_mode(conn, reason="bulk fix for issue #123", set_by="moh")

# Perform bulk operations (triggers allow writes without context)
conn.execute("UPDATE inbox_items_v29 SET ...")
conn.commit()

# Disable maintenance mode
disable_maintenance_mode(conn)
```

**Warning**: Maintenance mode bypasses context checks but still logs to audit.

## Querying the Audit Log

### Who Changed This Row?

```python
from lib.safety.audit import query_who_changed

trail = query_who_changed(conn, "inbox_items_v29", "item-id-123")
print(trail)
```

Output:
```
Audit trail for inbox_items_v29.item-id-123:
  2024-02-10T15:30:00Z | UPDATE by moh (source=api, request=req-abc123...)
  2024-02-10T14:00:00Z | INSERT by detector-expiring-engagement (source=detector, request=req-def456...)
```

### Using SQL

```sql
-- All changes to a specific row
SELECT at, actor, source, request_id, op, before_json, after_json
FROM db_write_audit_v1
WHERE table_name = 'inbox_items_v29' AND row_id = 'item-id-123'
ORDER BY at DESC;

-- All changes by a specific actor
SELECT at, table_name, op, row_id
FROM db_write_audit_v1
WHERE actor = 'moh'
ORDER BY at DESC
LIMIT 50;

-- All changes in a specific request
SELECT *
FROM db_write_audit_v1
WHERE request_id = 'req-abc123'
ORDER BY at;

-- Detect bulk writes (mystery writes)
SELECT request_id, actor, source, COUNT(*) as row_count
FROM db_write_audit_v1
WHERE table_name = 'inbox_items_v29'
GROUP BY request_id
HAVING COUNT(*) > 10
ORDER BY row_count DESC;
```

### Using AuditLogger

```python
from lib.safety.audit import AuditLogger

logger = AuditLogger(conn)

# Get changes for a row
entries = logger.get_changes_for_row("inbox_items_v29", "item-id-123")

# Get changes by actor
entries = logger.get_changes_by_actor("moh", limit=50)

# Get changes in a request
entries = logger.get_changes_by_request("req-abc123")

# Detect mystery writes (bulk updates)
mystery = logger.get_mystery_writes("inbox_items_v29", threshold=10)
```

## DB-Level Invariants

These triggers ABORT invalid writes at the database level:

### Terminal State Requires resolved_at

```sql
-- ABORT if state IN ('dismissed', 'linked_to_issue') AND resolved_at IS NULL
```

### Dismissed Requires Audit Fields

```sql
-- ABORT if state = 'dismissed' AND (
--   dismissed_at IS NULL OR
--   dismissed_by IS NULL OR
--   suppression_key IS NULL
-- )
```

### Linked_to_issue Requires Issue Pointer

```sql
-- ABORT if state = 'linked_to_issue' AND resolved_issue_id IS NULL
```

### Write Context Required

```sql
-- ABORT if write_context_v1 is empty (no actor/request_id)
-- Unless maintenance_mode.flag = 1
```

## Schema Assertions

Run schema checks:

```bash
make schema-check
```

Or in Python:

```python
from lib.safety import assert_schema

violations = assert_schema(conn, raise_on_violation=True)
```

This verifies:
- Required tables exist
- Required triggers exist
- Required columns exist
- Required indexes exist
- Legacy `inbox_items` is VIEW (not writable table)

## Running Checks

```bash
# Run all checks (CI gate)
make check

# Individual checks
make lint
make test
make schema-check
make ripgrep-check

# Run migrations
make migrate

# Start dev server
make dev
```

## Troubleshooting

### "SAFETY: write context required"

Your code is trying to write without setting `WriteContext`. Wrap your writes:

```python
with WriteContext(conn, actor="...", source="..."):
    conn.execute("UPDATE ...")
```

### "SAFETY: terminal state requires resolved_at"

You're setting `state='dismissed'` without also setting `resolved_at`. Fix:

```python
conn.execute("""
    UPDATE inbox_items_v29
    SET state = 'dismissed',
        resolved_at = datetime('now'),  -- Required!
        dismissed_at = datetime('now'),
        dismissed_by = 'actor',
        suppression_key = 'key'
    WHERE id = ?
""", (item_id,))
```

### Schema violations in CI

Run `make migrate` to apply safety migrations, then commit the changes.
