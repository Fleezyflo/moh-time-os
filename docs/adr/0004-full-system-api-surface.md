# ADR-0004: Full System API Surface Expansion

## Status
Accepted

## Context
MOH Time OS is moving from a prototype with minimal API endpoints to a production-ready system covering all 30 implementation briefs. This requires a substantial expansion of `api/server.py` and addition of new routers (`action_router.py`, `export_router.py`, `governance_router.py`, `sse_router.py`, `intelligence_router.py`, `paginated_router.py`).

Key changes:
- **api/server.py**: Added task lifecycle endpoints (delegate, escalate, snooze, archive), decision management, governance mode controls, control-room proposal endpoints, bulk operations, and bundle rollback support.
- **New routers**: Action framework (propose/approve/execute), data export (GDPR compliance), subject access requests, SSE real-time events, intelligence engine, and paginated query endpoints.
- **Observability**: Structured JSON logging with request ID propagation, health checks with component-level status, and Prometheus metrics export.

## Decision
Expand the API surface in a single coordinated delivery rather than incremental merges, ensuring all endpoints share consistent patterns: change bundles for audit trails, governance checks before destructive operations, and structured error responses.

## Consequences
- Larger PR size but coherent API surface
- All new endpoints follow the existing change-bundle pattern for auditability
- OpenAPI schema regenerated to match new endpoints
- New routers mounted under `/api/v2` prefix for spec compliance
