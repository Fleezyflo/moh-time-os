# ADR-0010: Phase 14 Cleanup, Bug Fixes & Hardening

## Status
Accepted

## Context
Phase 14 is the final buildout phase. It closes gaps accumulated across Phases 0-13: dead page files, one remaining legacy API call (`/api/control-room/proposals/{id}`), one legacy endpoint (`/api/tasks`), stale Tailwind `slate-*` classes in governance components, hardcoded chart colors, a redundant `/fix-data` route, and missing export functionality on list pages.

## Decision
1. Add `GET /api/v2/proposals/{proposal_id}` to `spec_router.py` — port enrichment logic from `server.py` with 4 bug fixes (fallback descriptions, title truncation, configurable signal limit, JSON parsing safety)
2. Migrate `fetchProposalDetail` from `/api/control-room/proposals/{id}` to `/api/v2/proposals/{id}`
3. Migrate `fetchTasks` from `/api/tasks` to `/api/v2/priorities` — removes response shape translation
4. Delete 4 dead page files (~800 lines): CommandCenter, Briefing, Proposals (replaced by Portfolio/Inbox in Phase 3), FixData (replaced by Operations tab)
5. Fix 6 stale `slate-*` Tailwind classes in 4 governance components
6. Add client-side CSV export (`ExportButton`) to 4 list pages (no backend export endpoints exist)
7. Migrate chart colors to CSS custom properties (12 new `--chart-*` vars in tokens.css)
8. Replace `/fix-data` standalone route with redirect to `/ops`

## Consequences
- Zero legacy API calls remain in `lib/api.ts`
- Zero `slate-*` Tailwind classes remain in `.tsx/.ts` files
- 4 dead files removed (~800 lines)
- Chart colors now participate in the design token system
- 1 new spec_router endpoint (proposal detail v2)
- ExportButton uses client-side CSV serialization (no server round-trip)
