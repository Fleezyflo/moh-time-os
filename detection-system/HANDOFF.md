# HANDOFF -- MOH Time OS Detection System

**Generated:** 2026-03-03 19:16 UTC
**Session:** 0
**Current Phase:** phase-15a (pending)

---

## What Just Happened

No previous session recorded. This is the first session.

## Phase Status

| Phase | Status | Tasks | PRs |
|-------|--------|-------|-----|
| phase-15a | READY | 0/3 |  |
| phase-15b | BLOCKED | 0/7 |  |
| phase-15c | BLOCKED | 0/4 |  |
| phase-15d | BLOCKED | 0/3 |  |
| phase-15e | BLOCKED | 0/3 |  |
| phase-15f | BLOCKED | 0/2 |  |

## What's Next

**Phase:** phase-15a -- CalendarSync Horizon + Schema Formalization

**Progress:** 0/3 tasks complete

**Next tasks:**

### task-01: Extend block generation to 10 business days

In lib/time_truth/calendar_sync.py at line 235, change
ensure_blocks_for_week() from timedelta(days=6) to timedelta(days=13)
to cover 10 business days across 2 calendar weeks. Add weekend-skip
logic in sync_events() to skip Saturday/Sunday dates.

**Files:**
- MODIFY `lib/time_truth/calendar_sync.py`

**Verification:**
- After truth cycle run, time_blocks has rows for the next 10 business days
- Weekends are skipped — no rows for Saturday or Sunday dates
- Idempotent: running twice doesn't create duplicate blocks (existing check at line 127-130)
- ruff check lib/time_truth/calendar_sync.py — zero errors

### task-02: Formalize time_blocks in schema.py

Add TABLES["time_blocks"] to lib/schema.py with columns from
SCHEMA_ATLAS: id, date, start_time, end_time, lane, task_id,
is_protected, is_buffer, created_at, updated_at. This formalizes
a table that already exists at runtime (created by BlockManager).
Migration is safe because CREATE TABLE IF NOT EXISTS is idempotent.

**Files:**
- MODIFY `lib/schema.py`

**Verification:**
- time_blocks appears in TABLES dict in schema.py
- Columns match SCHEMA_ATLAS exactly
- CREATE TABLE IF NOT EXISTS — safe for existing DBs
- ruff check lib/schema.py — zero errors

### task-03: Revenue column verification at startup

Add startup verification for revenue columns (prior_year_revenue,
ytd_revenue, lifetime_revenue) on the clients table. Use ALTER TABLE
ADD COLUMN IF NOT EXISTS pattern. The drift detector queries these
columns with COALESCE fallback, but they must exist in the table for
the query to parse at all.

**Files:**
- MODIFY `lib/schema.py`

**Verification:**
- Revenue columns either exist or are added at startup
- If columns already exist, no error (idempotent)
- Drift detector can query COALESCE(clients.ytd_revenue, 0) without error
- ruff check lib/schema.py — zero errors
- bandit -r lib/schema.py — zero findings

## Key Rules

- All calendar queries use `events JOIN calendar_attendees`, NEVER `calendar_events`
- Revenue queries use COALESCE with try/except for missing columns
- `collect_calendar_for_user()` fetches but does NOT persist -- use `CalendarCollector.sync()`
- Sandbox cannot run git, format, install, or dev servers
- Commit subjects max 72 chars, first letter after prefix lowercase
- Stage ALL files before committing
- ADR required when modifying api/server.py (Phase 15c)
- System map regeneration required for new fetch('/api/...') calls

## Documents to Read

1. `detection-system/plan/phase-15a.yaml` -- Current phase spec
2. `detection-system/AGENT.md` -- Engineering rules and verification gates
3. `detection-system/commit-workflow.md` -- Error recovery protocol
4. `docs/design/DETECTION_SYSTEM_DESIGN.md` -- Full design document
5. `CLAUDE.md` -- Repo-level rules
