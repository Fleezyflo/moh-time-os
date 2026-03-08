# Phase B: System Completeness

**Priority:** Ship second — connects things that are built but not wired.
**Estimated PRs:** 2-3

---

## Scope

Every item here is code that exists but isn't connected to its consumer. No new features — just wiring, fixing mismatches, and making existing modules reachable.

## Work Items

### Intelligence Wiring

**Wire ConversationalIntelligence to API (GAP-10-10) — HIGH**
971 lines of fully tested code in `lib/intelligence/conversational_intelligence.py` that nothing can reach. Add `POST /api/v2/intelligence/conversation` accepting `{query, session_id?}`. Wire to `process_query()`. Maintain session state per session_id. Return structured response: answer, entities, suggested_actions, confidence. Optionally wire to Google Chat slash commands.

Files: `api/intelligence_router.py`, optionally `lib/integrations/chat_commands.py`

**Wire ComplianceReporter to real data (GAP-11-06)**
`ComplianceReporter()` at `api/intelligence_router.py:1361` creates empty default instances. Report always shows zeros. Pass real `RetentionEngine` and `SubjectAccessManager` from `lib/governance/`.

Files: `api/intelligence_router.py`, `lib/intelligence/data_governance.py`

**Wire V4 services behind unified facade (GAP-12-02)**
IssueService, SignalService, ProposalService, CouplingService are imported directly in api/. Create `lib/services/entity_service.py` as unified facade. Update API imports.

Files: `lib/services/entity_service.py` (create), `api/server.py`, `api/spec_router.py`

**Add per-entity intelligence endpoint (GAP-12-04)**
No REST endpoint exposes `build_entity_profile()` for a single entity. Add `GET /api/v2/intelligence/entity/{entity_type}/{entity_id}/profile`.

Files: `api/intelligence_router.py`

### Schema & Contract Fixes

**Add engagements tables to schema.py (GAP-07-01)**
`engagements` and `engagement_transitions` are only created by `v29_engagement_lifecycle.py` migration, not in `lib/schema.py`. Add both table definitions, bump SCHEMA_VERSION.

Files: `lib/schema.py`

**Fix intelligence error format (GAP-13-01)**
Intelligence endpoints use FastAPI's `{"detail": "..."}` (HTTPException) instead of the declared `{"error": "...", "error_code": "..."}` (IntelligenceResponse). Replace HTTPException in intelligence_router.py error paths with JSONResponse using the correct schema.

Files: `api/intelligence_router.py`

**Fix /api/v2/search version mismatch (GAP-08-04)**
UI calls `/api/v2/search` but only `/api/search` exists. Add `/search` to spec_router.py.

Files: `api/spec_router.py`

**INSUFFICIENT_DATA_SCORE sentinel (PR-FRESH-03)**
Add sentinel value in `scoring.py` to distinguish "low score" from "not enough data to score." Use in scoring functions, handle in entity profile building.

Files: `lib/intelligence/scoring.py`, `lib/intelligence/entity_profile.py`

### System Map Accuracy

**Scan all sub-routers (GAP-08-02)**
`generate_system_map.py` only scans `server.py` and `spec_router.py`. Misses ~43 routes from intelligence_router, sse_router, paginated_router, export_router, governance_router, action_router. Extend scanner to find all `include_router()` calls and resolve each router file.

Files: `scripts/generate_system_map.py`, `docs/system-map.json`

**Parse fetchJson wrapper (GAP-08-03)**
UI uses `fetchJson(${API_BASE}/...)` not literal `fetch('/api/...')`. Generator always produces empty `ui_api_calls`. Update scanner to parse template literals with API_BASE.

Files: `scripts/generate_system_map.py`, `docs/system-map.json`

## Done When

- `POST /api/v2/intelligence/conversation` endpoint exists, calls ConversationalIntelligence
- ComplianceReporter wired to real PII counts, retention status, deletion requests
- V4 facade wraps all V4 service access — no direct imports in `api/`
- Entity profile endpoint returns all 7 intelligence dimensions
- `engagements` and `engagement_transitions` tables in schema.py
- Intelligence error responses use `{"error", "error_code"}` format
- `/api/v2/search` route exists and resolves
- INSUFFICIENT_DATA_SCORE constant used in scoring and profile building
- System map scanner updated for new routes and API calls
