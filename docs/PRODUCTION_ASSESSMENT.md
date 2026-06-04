# Production Readiness Assessment — MOH Time OS

**Date:** 2026-03-17
**Assessor:** Pilot system (automated + manual verification)
**Baseline:** Ground zero (2026-03-16), 294 source files, 132,011 lines

---

## Executive Summary

MOH Time OS has solid foundations — no f-string SQL injection, all HTTP calls have timeouts, health checks are comprehensive, and UI-API contracts are aligned. The critical blocker is **35+ runtime DDL statements creating tables outside the migration system**, including two inside HTTP endpoint handlers. The codebase also carries 36 silent failures, ~40 dead modules, and 33 lint suppressions from organic growth.

**Verdict:** NOT PRODUCTION READY — 1 critical blocker, 3 high-severity findings

---

## Tier 1 — Launch Blockers

### CRITICAL

#### [C-002] 35+ runtime DDL statements outside migration system
- **Location:** 13+ production modules including `api/server.py:4775,4823`, `lib/store.py:20–150`, `lib/collectors/all_users_runner.py:78,88`, `lib/governance/audit_log.py:63`, `lib/intelligence/entity_memory.py:110`, plus files in lib/intelligence/, lib/integrations/, lib/v4/, lib/governance/, lib/safety/
- **What's wrong:** CREATE TABLE IF NOT EXISTS statements are scattered across production code. Two are inside HTTP endpoint handlers (server.py), executing DDL on every request. 47 tables are invisible to the schema engine. Table definitions conflict between schema.py and inline DDL.
- **Impact:** Schema drift is undetectable. Migrations can't track or rollback these tables. DDL in request handlers risks write contention under load.
- **Fix:** Consolidate all table definitions into lib/schema.py and the migration system. Remove inline DDL. Add a CI check that greps for CREATE TABLE outside allowed locations.
- **Effort:** 8–13 hours across 5 PRs

### HIGH

#### [H-001] 36 silent failure paths (return {} / return [])
- **Location:** Distributed across lib/ — 6 CRITICAL (governance/security: key_manager.py:402, subject_access.py, retention_engine.py, data_classification.py), 3 HIGH (intelligence profitability), 20 MEDIUM, 7 LOW
- **What's wrong:** Exception handlers return empty dicts/lists instead of raising or logging errors. Callers see "no data" instead of "something failed." 6 of these are in GDPR subject access, data retention, and key management — worst places to silently fail.
- **Impact:** Failures are invisible. GDPR SAR requests return incomplete data. Key management errors are completely silent (zero logging).
- **Fix:** Extend existing `lib/collectors/result.py` Result type pattern. Replace silent returns with logged errors + typed results. Phase 1 targets the 6 CRITICAL locations.
- **Effort:** 15–20 hours across 12–15 PRs (phased by severity)

#### [H-002] 10 orphaned v4 modules — 3 dead, 7 internal
- **Location:** `lib/v4/` — 3 dead (ingest_pipeline.py, orchestrator.py, collector_hooks.py), 7 active internal (artifact_service, entity_link_service, identity_service, policy_service, report_service, proposal_aggregator, proposal_scoring)
- **What's wrong:** 3 modules are never imported anywhere. 7 are active internal infrastructure but not API-exposed. Only 4 of 14 v4 services are wired to the API layer.
- **Impact:** Dead code inflates codebase. Unclear which v4 services are authoritative vs deprecated.
- **Fix:** Delete 3 dead modules. Document 7 active internal modules with docstrings.
- **Effort:** 2 hours across 2 PRs

#### [H-003] 33 lint/security suppressions — 11 bogus
- **Location:** lib/intelligence/signals.py (6 bogus E402), plus scattered across lib/. 22 are legitimate (B904 in server.py, S608 in safe_sql.py, etc.)
- **What's wrong:** 11 suppressions label standard library imports (logging, datetime, statistics, Path) as "conditional imports" when they're just mid-file imports. The noqa comments hide the real issue: imports should be at the top of the file.
- **Impact:** Suppression count inflated. Real linter value diluted by false justifications.
- **Fix:** Move deferred imports to top of file, remove 11 bogus noqa comments. Document remaining 22 with justification.
- **Effort:** 3 hours across 2 PRs

---

## Tier 2 — Product Value

### MEDIUM

#### [M-001] 13 confirmed dead lib/ top-level modules (3,990 lines)
- **Location:** lib/ root — build_client_identities.py, build_team_registry.py, conflicts.py, cron_tasks.py, delegation_engine.py, heartbeat_processor.py, link_projects.py, priority_engine.py, promise_tracker.py, protocol.py, scheduling_engine.py, sync_ar.py, task_parser.py. Plus 3 test-only orphans (459 lines).
- **What's wrong:** Zero imports anywhere in the codebase. Original estimate of ~40 was wrong — investigation confirmed 24 of 40 are actively imported by production code.
- **Impact:** 3,990 lines of dead code inflating codebase surface area.
- **Fix:** Delete 13 dead modules, relocate 3 test-only orphans.
- **Effort:** 1.5 hours across 2 PRs

#### [M-002] 3 test files mock persistence layer
- **Location:** tests/test_backup.py, tests/test_maintenance.py, tests/test_data_lifecycle.py
- **What's wrong:** Mock database connections instead of testing against real SQLite.
- **Impact:** False confidence in backup, maintenance, and data lifecycle.
- **Fix:** Add integration tests using temporary databases alongside mock tests.
- **Effort:** 4–6 hours

#### [M-003] 136 source files have zero test coverage (46.3%)
- **Location:** Systematic absence across governance (5 files), security middleware, v4 services (12 files), all detectors (5 files), all analyzers (6 files), collectors/all_users_runner (1,144 lines). Plus 14 dead migration files.
- **What's wrong:** 46.3% of source files have no test imports — worse than initial 73.8% estimate. The gap is structural: entire subsystems (governance, v4, detectors, analyzers) have zero tests.
- **Impact:** Compliance violations undetectable (governance), RBAC untested (security), core product logic unverified (v4, detectors).
- **Fix:** 4-phase plan over 12 weeks. Phase 1: governance + security (9 files, ~40 tests).
- **Effort:** Ongoing — Phase 1 is ~2 weeks

---

## Tier 3 — Ongoing Improvements

### LOW

#### [L-001] 1 broad except in CLI entry point
- **Location:** `lib/collectors/orchestrator.py:359`
- **What's wrong:** `except Exception:` in CLI main().
- **Fix:** Narrow to expected exceptions.
- **Effort:** 30 minutes

#### [L-002] Schema version 23 with only 2 tables in schema.py
- **Location:** `lib/schema.py`
- **What's wrong:** 47 tables are created inline, only 2 tracked in schema.py.
- **Fix:** Part of C-002 remediation.

---

## What's Clean

| Check | Status |
|-------|--------|
| f-string SQL injection | CLEAN — zero unsafe instances |
| shell=True in subprocess | CLEAN — zero in production |
| hashlib.md5 usage | CLEAN — zero instances |
| Hardcoded /tmp paths | CLEAN — tempfile.gettempdir() used |
| HTTP timeouts | CLEAN — all httpx calls have explicit timeout= |
| Health endpoint | GOOD — 6 substantive checks (DB, schema, disk, collectors, daemon, bundles) |
| UI-API contract alignment | GOOD — all UI fetch calls have corresponding API routes |
| Bare except patterns | CLEAN — zero bare except: in production |
| Path hardcoding in v4/ | CLEAN — proper use of paths module |
| Backup implementation | OK — shutil.copy2 with WAL checkpoint |

---

## Priority Order for Remediation

1. **C-002** (DDL consolidation) — Only critical. Start with PR 1: remove DDL from server.py endpoint handlers.
2. **H-001** (silent failures) — Phase 1 targets 6 CRITICAL locations in governance/security.
3. **H-003** (suppressions) — Quick win, 3 hours for 2 PRs.
4. **H-002** (v4 cleanup) — Quick win, 2 hours for 2 PRs.
5. **M-001** (dead code) — 13 modules, 1.5h, quick cleanup.
6. **M-002** (mock tests) — 3 integration test files, 6h.
7. **M-003** (coverage) — 136 files, 4 phases over 12 weeks. Phase 1: governance + security.

---

## Metrics Summary

| Metric | Ground Zero | Current | Target |
|--------|-------------|---------|--------|
| Critical findings | 1 | 1 | 0 |
| High findings | 3 | 3 | 0 |
| Medium findings | 3 | 3 | ≤2 |
| Silent failures | 36 | 36 | <10 |
| Test coverage (import) | 53.7% (136/294 uncovered) | 53.7% | >75% |
| Dead modules | 13 (3,990 lines) | 13 | 0 |
| Suppressions | 33 | 33 | <5 (justified) |
| Schema centralization | ~4% (2/49) | ~4% | 100% |
