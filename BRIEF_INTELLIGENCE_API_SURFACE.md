# Brief 26: Intelligence API Surface
> **Status:** DESIGNED | **Priority:** P1 | **Prefix:** IA

## Problem

The intelligence layer computes rich data — entity scores, signals, patterns, proposals, cost profiles, trajectories, entity profiles. But `api/spec_router.py` (v2.9 spec) was built before these modules matured. The UI has no reliable contract to consume intelligence. Without this brief, Brief 12 (Interface Experience) can't display intelligence, and Brief 25 (Conversational Interface) has no backend to query.

## Dependencies

- **Requires:** Brief 18 (Intelligence Depth) — entity profiles, correlation confidence, outcome tracking must exist
- **Requires:** Brief 17 (Intelligence Wiring) — persistence layer must be wired
- **Blocks:** Brief 12 (IX), Brief 25 (CI), Brief 24 (PI)

## Scope

Design and implement a typed REST API surface that exposes every intelligence module to external consumers (UI, chat, future mobile). Every endpoint returns typed JSON with consistent error handling, pagination where needed, and appropriate caching headers.

**Not in scope:** Authentication (Brief 13), rate limiting (Brief 13), WebSocket/SSE (Brief 12), GraphQL.

## Architecture Principles

1. **Read-only intelligence endpoints** — intelligence is computed by the daemon, API only reads persisted results
2. **Consistent response envelope** — every response wraps data in `{ "data": ..., "meta": { "computed_at": ..., "freshness": ... } }`
3. **Entity-centric routing** — `/api/v3/intelligence/{entity_type}/{entity_id}/...`
4. **Portfolio-level aggregation** — `/api/v3/intelligence/portfolio/...`
5. **Freshness metadata** — every response includes when the data was last computed and how stale it is
6. **No computation in request path** — API reads from persisted tables, never triggers live computation

## Tasks

| Task | Title | Est. Lines |
|------|-------|------------|
| IA-1.1 | Intelligence Router & Response Envelope | ~250 |
| IA-2.1 | Entity Intelligence Endpoints | ~400 |
| IA-3.1 | Portfolio & Aggregate Endpoints | ~300 |
| IA-4.1 | Signal & Pattern Query Endpoints | ~350 |
| IA-5.1 | Scenario & Trajectory Endpoints | ~300 |
| IA-6.1 | API Contract Tests & Validation | ~500 |

## Estimated Effort

~2,100 lines. 6 tasks. Medium-large.

## Success Criteria

- Every intelligence module has at least one API endpoint
- All endpoints return consistent envelope with freshness metadata
- Contract tests verify response shapes
- UI can render entity profiles, portfolio dashboards, signal lists, and proposals from API data alone
- No endpoint triggers live intelligence computation (read-only)
- OpenAPI spec generated and up to date
