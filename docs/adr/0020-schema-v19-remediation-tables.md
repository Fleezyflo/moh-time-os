# ADR-0020: Schema V19 -- Remediation Tables and Column Additions

## Status

Accepted

## Context

The closure audit (docs/closure-audit.md) identified 47 validated bugs, 13 of which
are blocked by missing schema elements. Handler code references columns and tables
that do not exist in the current schema (V18), causing silent data loss and incorrect
query results.

Specific gaps:

- notifications table missing: dismissed, dismissed_at, task_id, recipient_id
- insights table missing: severity
- cycle_logs table missing: source, status, completed_at
- saved_filters table does not exist (6 columns needed by spec_router endpoints)
- couplings table does not exist (11 columns needed by detection engine)

## Decision

Evolve schema from V18 to V19 with ALTER TABLE additions for existing tables and
CREATE TABLE for new tables. This is a non-destructive migration -- all changes are
additive (new columns default to NULL, new tables are created fresh).

The V19 migration unblocks 13 bug-fix rows but does not resolve them. Resolution
requires subsequent handler-code PRs (PR3/PR4 in the remediation plan).

## Consequences

- 5 existing tables gain new columns (backward compatible, NULL defaults)
- 2 new tables created (saved_filters, couplings)
- docs/schema.sql regenerated to reflect new schema state
- Deletion count in PR diff is high (~540 lines) because schema table definitions
  are replaced wholesale during migration restructuring, not because functionality
  was removed
