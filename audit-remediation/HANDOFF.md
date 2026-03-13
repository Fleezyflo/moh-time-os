# HANDOFF -- Audit Remediation

**Generated:** 2026-03-12
**Current Phase:** post-audit (hostile review complete, gap closure complete)
**Current Session:** 23
**Track:** Post-audit structural repair

---

## What Just Happened

### Session 023 -- Gap Closure: Schema-Code Mismatches + Persistence Unification

Branch: fix/data-loss-write-safety (continues from Session 022).

**Three gaps from Session 022 hostile review closed:**

1. **Gap A: Mock-based muting/analytics tests → real SQLite** -- Rewrote TestNotificationMuting (6 tests) and TestNotificationAnalytics (4 tests) in test_action_integration.py. Added _FixtureStore class and fixture_store/notif_engine fixtures using create_fixture_db() for full production schema.

2. **Gap B: Split persistence in DigestEngine** -- Refactored generate_digest(), mark_as_processed() SELECT, and get_pending_count() to use safe_sql.select() instead of raw SQL string construction. Added `from lib import safe_sql` import.

3. **Gap C: Blast-radius analysis** -- Completed. See below.

**Critical production bugs found by Gap A (hidden by Mocks):**

- `mute_entity()` inserted `muted_at` (column doesn't exist) and omitted `entity_type` (NOT NULL). Fixed: entity_type extracted from "type:id" format, muted_at removed.
- `get_active_mutes()` queried `muted_at` (doesn't exist). Fixed: changed to `created_at`.
- `track_delivery()` inserted `metadata` and `recorded_at` (neither exists). Fixed: outcomes map to schema timestamp columns (delivered_at, opened_at, acted_on_at), metadata stored in failed_reason for failures.
- `get_analytics_summary()` queried `recorded_at` (doesn't exist). Fixed: changed to `created_at`.

**Verification:** 36 tests pass (17 in test_action_integration.py, 19 in test_digest_engine.py). ruff clean, bandit clean (only B101 assert in tests, B608 in test fixtures with noqa).

**Files changed (this session):**
- `lib/notifier/engine.py` -- 4 schema-code mismatch fixes in muting/analytics methods
- `lib/notifier/digest.py` -- safe_sql import + 3 query refactors
- `tests/test_action_integration.py` -- _FixtureStore, fixtures, 10 real SQLite tests replacing Mock tests
- `tests/test_digest_engine.py` -- count() and delete() added to _FixtureStore

### Blast-Radius Analysis

| Fix | Files touched | API surface | Runtime callers | Test coverage |
|-----|---------------|-------------|-----------------|---------------|
| mute_entity schema fix | engine.py | POST /api/v2/notifications/mute | spec_router.mute_entity_notifications() | test_mute_and_check, test_mute_stores_entity_type |
| get_active_mutes column fix | engine.py | GET /api/v2/notifications/mutes | spec_router.get_active_mutes() | test_get_active_mutes, test_expired_mute_not_active |
| track_delivery schema fix | engine.py | (internal -- called by process_pending) | NotificationEngine.process_pending() | test_track_delivery, test_track_delivery_outcome_timestamps, test_track_delivery_failed_with_metadata |
| get_analytics_summary column fix | engine.py | GET /api/v2/notifications/analytics | spec_router.get_notification_analytics() | test_analytics_summary |
| DigestEngine safe_sql refactor | digest.py | (internal -- called by engine.py) | DigestEngine.generate_digest, mark_as_processed, get_pending_count | All 19 test_digest_engine.py tests |

**Regression risk:** LOW. All fixes align production code with the actual database schema. The old code would have crashed on real SQLite -- Mocks masked the failures. No behavioral change for callers; only the column names in SQL now match reality.

### Leftover Sweep

HANDOFF.md line 50 previously referenced: "Replace remaining `store.query(raw SQL)` in DigestEngine with store CRUD. Convert NotificationEngine muting/analytics tests from Mock to fixture DB." The second item is now done. The first item (raw SQL in NotificationEngine methods like get_pending_count, get_sent_today, unmute_entity, get_active_mutes, get_analytics_summary) remains as a true follow-up -- these are read-only queries via store.query() which is correct for reads. Converting them to safe_sql.select() is a polish task, not a defect.

---

## What's Next

All audit remediation phases (A-D) complete. Hostile review complete. Gap closure complete.

Remaining work:
1. **Merge PR** -- fix/data-loss-write-safety branch (includes Session 022 + 023 changes)
2. **PR #3 (backup VACUUM INTO)** -- `lib/backup.py`, `tests/test_backup.py`
3. **PR #4 (schema + alerting + API handler)** -- `lib/schema_engine.py`, `lib/observability/health.py`, `api/server.py`
4. **Polish follow-up:** Convert remaining raw SQL in NotificationEngine read methods to safe_sql.select().

---

## Key Rules

1. You write code. You never run anything.
2. Commit subject under 72 chars, valid types only
3. "HANDOFF.md removed and rewritten" required in commit body
4. If 20+ deletions, include "Deletion rationale:" in body
5. Match existing patterns obsessively
6. No comments in command blocks
7. `store.query()` is for reads ONLY -- all writes must go through `store.insert()`, `store.update()`, `store.delete()` to acquire `_write_lock`
8. Schema (tables + indexes) lives in `lib/schema.py` only -- no runtime class may create or manage schema
9. Deferred imports are justified only for circular dependency breaking or graceful degradation (try/except). Lazy stdlib imports are not acceptable.
10. Test fixture stores must match production semantics exactly (INSERT OR REPLACE, not INSERT INTO)
11. Test DB fixtures should be function-scoped (`tmp_path`) for per-test isolation, not session-scoped shared files
12. `lib/governance/` has REAL production classes -- `lib/intelligence/data_governance.py` has toy in-memory versions. Always use the real ones.
13. NotificationEngine has TWO methods returning the same dict comprehension pattern (`get_pending_count` and `get_sent_today`) -- use enough context to disambiguate when editing.
14. Mock tests MUST NOT be used when testing persistence boundaries -- they hide schema-code mismatches that crash on real SQLite. (Session 23: 4 production bugs hidden by Mocks)
15. Production code columns must match lib/schema.py exactly -- no invented columns (muted_at, recorded_at, metadata). (Session 23: caught by fixture DB conversion)

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- This brief
2. `audit-remediation/state.json` -- Current project state
3. `CLAUDE.md` -- Repo-level engineering rules
