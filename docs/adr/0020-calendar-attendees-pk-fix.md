# ADR-0020: Calendar Attendees PK Type Fix

## Status
Accepted

## Context
The `calendar_attendees` table was declared with `id INTEGER PRIMARY KEY AUTOINCREMENT` but the calendar collector generates text IDs (`"{event_id}_attendee_{idx}"`). This caused 96 "datatype mismatch" warnings per sync cycle. Every INSERT succeeded due to SQLite type affinity but logged warnings that obscured real errors.

## Decision
Change the `id` column from `INTEGER PRIMARY KEY AUTOINCREMENT` to `TEXT PRIMARY KEY` in `lib/schema.py`. The schema engine's Phase 0 auto-detects the PK type mismatch and drops/recreates the table on next sync. No data migration needed since attendees are re-fetched every sync cycle.

## Consequences
- Eliminates 96 warnings per sync
- Table is dropped and recreated on first sync after deploy (acceptable -- attendees are ephemeral)
- `docs/schema.sql` updated to match
