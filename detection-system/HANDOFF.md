# HANDOFF -- MOH Time OS Detection System

**Generated:** 2026-03-06 13:14 UTC
**Session:** 3
**Current Phase:** phase-15d (pending)

---

## What Just Happened

No previous session recorded. This is the first session.

## Phase Status

| Phase | Status | Tasks | PRs |
|-------|--------|-------|-----|
| phase-15a | DONE | 3/3 | #57 |
| phase-15b | DONE | 7/7 | #58 |
| phase-15c | DONE | 4/4 | #59 |
| phase-15d | READY | 0/3 |  |
| phase-15e | READY | 0/3 |  |
| phase-15f | BLOCKED | 0/2 |  |

## What's Next

**Phase:** phase-15d -- Command Center UI Redesign

**Progress:** 0/3 tasks complete

**Next tasks:**

### task-01: Add fetch functions and hooks for detection endpoints

Add fetch functions to time-os-ui/src/lib/api.ts for all new endpoints:
fetchWeekStrip, fetchFindings, fetchFinding, acknowledgeFinding,
suppressFinding, fetchStaleness, fetchWeightReview, submitWeightReview.
Add corresponding hooks to time-os-ui/src/lib/hooks.ts:
useWeekStrip, useFindings, useFinding, useStaleness, useWeightReview.
Replace the inline useFetchCommand() hook (lines 17-30 of current
CommandCenter.tsx) with the shared hooks.

**Files:**
- MODIFY `time-os-ui/src/lib/api.ts`
- MODIFY `time-os-ui/src/lib/hooks.ts`

**Verification:**
- All fetch functions typed with correct request/response shapes
- All hooks use correct endpoints
- No inline hooks remain in CommandCenter.tsx
- npx tsc --noEmit -- zero type errors (run on Mac)

### task-02: Rewrite CommandCenter.tsx with new layout

Full rewrite of time-os-ui/src/pages/CommandCenter.tsx to single-view
layout. New components (all in CommandCenter.tsx):
- StalenessBar: yellow warning when detection is stale
- WeekStrip: 10-day horizontal cards with ratio coloring, clickable days
- FindingCard: single finding with expandable adjacent data, "Got it"
  and "Expected" buttons. On expand, calls ?refresh=true and shows
  "Refreshing calendar & email..." state before rendering.
- CorrelatedGroup: groups related findings, primary + subordinates
- TeamCollisions: collapsible section for team member collisions

Empty state: "Nothing requires attention" (only when not stale).
Stale state: yellow warning, no "nothing requires attention".
No scored lists or color-coded labels anywhere.

**Files:**
- MODIFY `time-os-ui/src/pages/CommandCenter.tsx`

**Verification:**
- Renders with staleness bar, week strip, findings, decision queue
- Empty state shows 'Nothing requires attention' only when not stale
- Stale state shows yellow warning
- Finding cards expand on click with adjacent data
- 'Got it' / 'Expected' buttons call correct API endpoints
- Correlated findings render as grouped cards
- Team collisions in collapsible section
- Week strip days are clickable
- No scored lists or color-coded labels anywhere
- npx tsc --noEmit -- zero type errors (run on Mac)
- prettier --check passes (run on Mac)

### task-03: Update system map for UI route changes

If CommandCenter.tsx adds new fetch() calls with literal /api/ URLs,
regenerate docs/system-map.json. If only using fetchJson wrapper or
hooks, system map may not need updating -- verify first.

**Files:**
- MODIFY `docs/system-map.json`

**Verification:**
- system-map.json reflects any new fetch('/api/...') calls
- Drift Detection CI passes

## Key Rules

- All calendar queries use `events JOIN calendar_attendees`, NEVER `calendar_events`
- Revenue queries use COALESCE with try/except for missing columns
- `collect_calendar_for_user()` fetches but does NOT persist -- use `CalendarCollector.sync()`
- Sandbox cannot run git, format, install, or dev servers
- Commit subjects max 72 chars, first letter after prefix lowercase
- Stage ALL files before committing
- ADR required when modifying api/server.py (Phase 15c)
- System map regeneration required for new fetch('/api/...') calls

## Documents to Read

1. `detection-system/plan/phase-15d.yaml` -- Current phase spec
2. `detection-system/AGENT.md` -- Engineering rules and verification gates
3. `detection-system/commit-workflow.md` -- Error recovery protocol
4. `docs/design/DETECTION_SYSTEM_DESIGN.md` -- Full design document
5. `CLAUDE.md` -- Repo-level rules
