# V4/V5 Architecture Reconciliation Audit

**Date:** 2026-02-21
**Brief:** 29 (VR), Task VR-1.1
**Author:** Claude (engineering partner)

---

## Executive Summary

The codebase has three parallel intelligence implementations:

| Layer | Files | Lines | Status |
|-------|-------|-------|--------|
| lib/intelligence/ | 26 | ~16,800 | **ACTIVE** — production, daemon-wired |
| lib/v4/ | 22 | ~10,700 | **PRODUCTION** — Control Room API depends on it |
| lib/v5/ | 40 | ~10,600 | **SKELETON** — mostly stubs, experimental |

**Decision:** Archive V5 (skeleton code with no production consumers). V4 remains until Control Room API migration (future brief). lib/intelligence/ is canonical.

---

## V4 Module Disposition

| Module | Lines | Decision | Reason |
|--------|-------|----------|--------|
| proposal_service.py | ~900 | KEEP (V4) | Control Room API depends on 5 endpoints |
| issue_service.py | ~850 | KEEP (V4) | Control Room API depends on 4 endpoints |
| signal_service.py | ~1,050 | KEEP (V4) | Control Room proposals/issues depend on signals |
| coupling_service.py | ~340 | KEEP (V4) | 1 API endpoint, low priority |
| report_service.py | ~500 | KEEP (V4) | Internal report generation |
| policy_service.py | ~680 | KEEP (V4) | Governance layer (inactive) |
| artifact_service.py | ~530 | KEEP (V4) | Legacy data layer |
| entity_link_service.py | ~620 | KEEP (V4) | Fix Data queue endpoint |
| identity_service.py | ~620 | KEEP (V4) | Identity resolution |
| seed_identities.py | ~200 | KEEP (V4) | API endpoint |
| collector_hooks.py | ~1,500 | KEEP (V4) | Pipeline orchestration |
| ingest_pipeline.py | ~600 | KEEP (V4) | Pipeline orchestration |
| orchestrator.py | ~300 | KEEP (V4) | CLI orchestration |
| detectors/ (4 files) | ~1,200 | KEEP (V4) | Signal detection |
| proposal_aggregator.py | ~300 | KEEP (V4) | Proposal bundling |
| proposal_scoring.py | ~200 | KEEP (V4) | Proposal scoring |

**V4 Rationale:** api/server.py Control Room endpoints (lines 4202-5365) are deeply integrated. Removing V4 requires implementing equivalent V5/intelligence endpoints — a separate brief.

---

## V5 Module Disposition

| Module | Lines | Decision | Reason |
|--------|-------|----------|--------|
| orchestrator.py | ~200 | ARCHIVE | Replaced by lib/intelligence/engine.py |
| database.py | ~150 | ARCHIVE | Replaced by lib/query_engine.py |
| data_loader.py | ~100 | ARCHIVE | Replaced by collectors/ |
| models/ (8 files) | ~1,800 | ARCHIVE | Replaced by lib/intelligence/ dataclasses |
| detectors/ (7 files) | ~2,400 | ARCHIVE | Replaced by lib/intelligence/signals.py |
| services/ (2 files) | ~800 | ARCHIVE | Replaced by lib/intelligence/engine.py |
| issues/ (2 files) | ~600 | ARCHIVE | Replaced by lib/intelligence/proposals.py |
| resolution/ (3 files) | ~900 | ARCHIVE | Replaced by lib/intelligence/auto_resolution.py |
| api/ (4 files) | ~1,200 | ARCHIVE | Replaced by api/spec_router.py |
| repositories/ (1 file) | ~400 | ARCHIVE | Replaced by lib/intelligence/persistence.py |
| migrations/ (1 file) | ~100 | ARCHIVE | Replaced by lib/migrations/ |

**V5 Rationale:** Entire V5 is skeleton code. Every module has a more complete equivalent in lib/intelligence/. Only consumer is `collectors/scheduled_collect.py` (1 reference, lines 378-384).

---

## Consumer Impact

### V4 Consumers (CANNOT remove without migration)
- **api/server.py** — 6+ V4 service imports, ~15 endpoints
- **cli_v4.py** — entire file is V4 CLI

### V5 Consumers (CAN remove with minor edits)
- **collectors/scheduled_collect.py** — 1 import block (lines 378-384)
  - Action: Remove V5 orchestrator call, rely on lib/intelligence pipeline

---

## Migration Plan Executed

### Phase 1: V5 Cleanup (This Brief)
1. Remove V5 import from scheduled_collect.py
2. Archive lib/v5/ to docs/archive/v5/
3. Remove time_os_v5.db references
4. Validate: no remaining V5 imports

### Phase 2: V4 Migration (Future Brief — Control Room API)
1. Implement V4 proposal/issue/coupling equivalents in lib/intelligence/
2. Create API endpoints in api/spec_router.py
3. Migrate api/server.py endpoints one by one
4. Archive lib/v4/ once all endpoints migrated
5. Retire cli_v4.py

---

## Metrics

| Metric | Before | After |
|--------|--------|-------|
| V5 files in lib/ | 40 | 0 (archived) |
| V5 lines in lib/ | ~10,600 | 0 (archived) |
| V4 files in lib/ | 22 | 22 (unchanged, future brief) |
| V5 import references | 1 | 0 |
| V4 import references | ~20 | ~20 (unchanged, future brief) |
