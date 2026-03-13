# HANDOFF -- Audit Remediation

**Generated:** 2026-03-13
**Current Phase:** post-audit (all structural repair complete)
**Current Session:** 24
**Track:** Post-audit structural repair

---

## What Just Happened

### Session 024 -- Entity Links Alignment, PatternDetectionResponse Wiring, Couplings Fix

Branch: fix/data-loss-write-safety (continues from Session 023).

**Four fixes applied:**

1. **server.py entity_links alignment** -- Removed runtime `CREATE TABLE IF NOT EXISTS entity_links` DDL (schema.py owns the table). Fixed `WHERE id = ?` to `WHERE link_id = ?` in resolve_fix_data_item(). Fixed `el.entity_id`/`el.entity_type`/`el.linked_id` to `el.to_entity_id`/`el.to_entity_type`/`el.from_artifact_id` in get_evidence().

2. **spec_router.py /couplings** -- Added `investigation_path, created_at, updated_at` to the SELECT to match the UI Coupling type contract.

3. **PatternDetectionResponse wiring** -- Added `PatternDetectionData` and `PatternDetectionResponse` to response_models.py. Changed `/intelligence/patterns` from `IntelligenceResponse` to `PatternDetectionResponse`. Endpoint now propagates detection_success, detection_errors, and detection_error_details from detect_all_patterns().

4. **Test fixes** -- Fixed `RECOMMENDED_INDEXES` -> `PERFORMANCE_INDEXES` import (actual export name). Tightened spec_router typed response test to assert both `PatternDetectionResponse` and `PatternDetectionData` appear in endpoint source.

**Files changed:**
- `api/server.py` -- 3 entity_links fixes, runtime DDL removed
- `api/spec_router.py` -- /couplings columns, PatternDetectionResponse wiring
- `api/response_models.py` -- PatternDetectionData, PatternDetectionResponse added, stray import sqlite3 removed
- `lib/schema.py` -- entity_links corrected (prior session, unstaged)
- `lib/db_opt/indexes.py` -- entity_links index columns corrected (prior session, unstaged)
- `tests/test_audit_remediation_v4_implementations.py` -- import fix, assertion fix
- `docs/adr/0021-entity-links-schema-alignment.md` -- ADR for server.py + spec_router.py changes

**Verification:** py_compile, ruff check, bandit -- all clean on changed files.

### Remaining work

All audit remediation phases (A-D) complete. Hostile review complete. Gap closure complete.

1. **Merge PR** -- fix/data-loss-write-safety branch
2. **PR #3 (backup VACUUM INTO)** -- `lib/backup.py`, `tests/test_backup.py`
3. **PR #4 (schema + alerting + API handler)** -- `lib/schema_engine.py`, `lib/observability/health.py`, `api/server.py`
4. **Polish follow-up:** Convert remaining raw SQL in NotificationEngine read methods to safe_sql.select().

---

## What's Next

Merge the current PR. Then proceed to PR #3 and PR #4 from the original remediation plan.

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
13. Mock tests MUST NOT be used when testing persistence boundaries -- they hide schema-code mismatches that crash on real SQLite.
14. Production code columns must match lib/schema.py exactly -- no invented columns.
15. ADR required when modifying api/server.py or api/spec_router.py (CI enforces via scripts/check_adr_required.sh).
16. Deletion rationale required in commit body when >20 lines deleted (CI enforces via scripts/check_change_size.sh).

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- This brief
2. `audit-remediation/state.json` -- Current project state
3. `CLAUDE.md` -- Repo-level engineering rules
