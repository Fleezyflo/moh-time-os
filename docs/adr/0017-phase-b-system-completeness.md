# ADR-0017: Phase B System Completeness

**Date:** 2026-03-08
**Status:** Accepted
**Context:** Audit remediation Phase B

## Decision

Wire 10 existing but unconnected modules to their consumers across API endpoints, schema, and system map tooling.

## Changes

### API (api/spec_router.py)
- `GET /api/v2/search` -- unified search endpoint wired to existing search infrastructure

### API (api/intelligence_router.py)
- `POST /conversation` -- wired to ConversationalIntelligence module
- `GET /entity/{type}/{id}/profile` -- entity profile endpoint via EntityServiceFacade
- ComplianceReporter rewired to real governance classes (DataClassifier, RetentionEngine, SubjectAccessManager)
- Intelligence error responses standardized to JSONResponse format

### Schema (lib/schema.py)
- `engagements` and `engagement_transitions` tables added, SCHEMA_VERSION 14 to 15

### System Map (scripts/generate_system_map.py)
- Sub-router discovery via `include_router()` parsing
- Template literal parsing for `fetchJson/postJson(${API_BASE}/...)` patterns

### Services
- `lib/services/entity_service.py` -- EntityServiceFacade wrapping V4 services
- `lib/intelligence/scoring.py` -- INSUFFICIENT_DATA_SCORE sentinel

## Rationale

Phase B connects modules that exist and are tested but have no wiring to their consumers. ADR required because api/spec_router.py and scripts/generate_system_map.py are governance-trigger files.
