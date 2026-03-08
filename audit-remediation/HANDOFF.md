# HANDOFF -- Audit Remediation

**Generated:** 2026-03-08
**Current Phase:** phase-c (pending) -- Intelligence Expansion
**Current Session:** 17
**Track:** Gap remediation (phases A-D)

---

## What Just Happened

### Session 016 -- Phase B: System Completeness

All 10 work items completed. PR #TBD (branch: phase-b/system-completeness).

**Intelligence Wiring:**
- GAP-10-10 (HIGH): Added `POST /api/v2/intelligence/conversation` endpoint calling ConversationalIntelligence.process_query(). Session state keyed by session_id with UUID generation for new sessions.
- GAP-11-06: Rewired ComplianceReporter to use real `DataClassifier.classify_database()`, `RetentionEngine.get_policies()`, and `SubjectAccessManager.list_requests()` from `lib/governance/`. Previous implementation used toy in-memory classes that always returned zeros.
- GAP-12-02: Created `lib/services/entity_service.py` -- EntityServiceFacade with lazy-singleton properties for IssueService, SignalService, ProposalService, CouplingService.
- GAP-12-04: Added `GET /api/v2/intelligence/entity/{entity_type}/{entity_id}/profile` endpoint calling `build_entity_profile()`.

**Schema & Contract Fixes:**
- GAP-07-01: Added `engagements` and `engagement_transitions` tables to `lib/schema.py`, bumped SCHEMA_VERSION 14->15. Columns match v29_engagement_lifecycle.py migration exactly.
- GAP-13-01: Replaced all 500-level HTTPException raises in intelligence_router.py with JSONResponse + `_error_response()` for consistent `{"error", "error_code"}` format. Left 400/404 HTTPException for input validation.
- GAP-08-04: Added `GET /search` to spec_router.py resolving the /api/v2/search version mismatch.
- PR-FRESH-03: Added `INSUFFICIENT_DATA_SCORE = -1.0` sentinel in scoring.py, used in entity_profile.py's `_compute_overall_health()`.

**System Map Accuracy:**
- GAP-08-02: Updated `scripts/generate_system_map.py` to discover all sub-routers by parsing `from api.\w+ import` in server.py.
- GAP-08-03: Updated UI API call scanner to parse `fetchJson/postJson(\`${API_BASE}/...\`)` template literals.

**Files changed:** `api/intelligence_router.py`, `api/spec_router.py`, `lib/schema.py`, `lib/services/__init__.py` (new), `lib/services/entity_service.py` (new), `lib/intelligence/scoring.py`, `lib/intelligence/entity_profile.py`, `scripts/generate_system_map.py`

**Key fix during verification:** Sub-agent initially used `DataCatalog(db_path)` but the real `lib.governance.DataCatalog` takes `tables: dict[str, TableClassification]`. Fixed to use `DataClassifier(db_path).classify_database()` which returns a properly initialized DataCatalog.

---

## What's Next

### Phase C: Intelligence Expansion
- 13 work items across 4 groups: adaptive thresholds (4), notifications (3), bidirectional integration (4), manual validation (2)
- See `audit-remediation/tasks/PHASE-C-INTELLIGENCE-EXPANSION.md`
- This is the largest phase -- new feature work building modules that don't exist yet
- Split into 3-4 PRs: thresholds, notifications, bidirectional, (optional) validation docs
- Read at least 3 existing modules in each directory before writing new ones
- Every new class needs tests

---

## Key Rules

1. You write code. You never run anything.
2. Commit subject under 72 chars, valid types only
3. "HANDOFF.md removed and rewritten" required in commit body
4. If 20+ deletions, include "Deletion rationale:" in body
5. Match existing patterns obsessively
6. No comments in command blocks
7. `lib/governance/` has REAL production classes -- `lib/intelligence/data_governance.py` has toy in-memory versions. Always use the real ones.
8. `DataCatalog` takes `tables: dict[str, TableClassification]`, NOT `db_path`. Use `DataClassifier(db_path).classify_database()` to get a DataCatalog.
9. Intelligence error responses must use `JSONResponse(content=_error_response(...))`, NOT `raise HTTPException(detail=...)` for 500 errors.
10. Inline `from fastapi.responses import JSONResponse` is redundant -- it's imported at module level (line 22 of intelligence_router.py).

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- This brief
2. `audit-remediation/tasks/PHASE-C-INTELLIGENCE-EXPANSION.md` -- Next phase task file
3. `audit-remediation/state.json` -- Current project state
4. `CLAUDE.md` -- Repo-level engineering rules
