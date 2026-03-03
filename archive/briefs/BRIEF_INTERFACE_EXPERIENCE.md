# Brief 12: INTERFACE_EXPERIENCE
> **Objective:** Design and build the user interface layer — a live dashboard serving real intelligence data, resolution queue UI, real-time updates, and a command interface for scenario modeling.
>
> **Why now:** After Briefs 9-11, MOH Time OS has comprehensive data, a stable autonomous engine, and powerful intelligence modules. All of that value is locked behind API endpoints and JSON files. This brief makes it accessible through a designed, usable interface.

## Scope

### What This Brief Does
1. **Dashboard design** — UI/UX design for the primary intelligence dashboard
2. **Live data serving** — Dashboard connected to real API endpoints, no hardcoded data
3. **Resolution queue UI** — Interface for reviewing, approving, and acting on resolution items
4. **Scenario modeling UI** — Interactive "what-if" interface for capacity and client decisions
5. **Real-time updates** — WebSocket or polling for live data refresh
6. **Mobile-responsive** — Accessible on tablet/phone for on-the-go decisions

### What This Brief Does NOT Do
- Collect more data (Brief 9)
- Modify the autonomous loop (Brief 10)
- Build new intelligence modules (Brief 11)

## Dependencies
- Brief 11 (INTELLIGENCE_EXPANSION) complete — all intelligence modules feeding unified data

## Phase Structure

| Phase | Focus | Tasks |
|-------|-------|-------|
| 1 | Design | IX-1.1: UI/UX design system and dashboard wireframes |
| 2 | Dashboard | IX-2.1: Build live intelligence dashboard |
| 3 | Resolution UI | IX-3.1: Resolution queue interface |
| 4 | Scenario UI | IX-4.1: Interactive scenario modeling interface |
| 5 | Real-Time | IX-5.1: WebSocket live updates + notification center |
| 6 | Validation | IX-6.1: Full UI/UX validation and user acceptance |

## Task Queue

| Seq | Task ID | Title | Status |
|-----|---------|-------|--------|
| 1 | IX-1.1 | UI/UX Design System & Wireframes | PENDING |
| 2 | IX-2.1 | Live Intelligence Dashboard | PENDING |
| 3 | IX-3.1 | Resolution Queue Interface | PENDING |
| 4 | IX-4.1 | Scenario Modeling Interface | PENDING |
| 5 | IX-5.1 | Real-Time Updates & Notification Center | PENDING |
| 6 | IX-6.1 | UI/UX Validation & User Acceptance | PENDING |

## Success Criteria
- Dashboard loads with live data in <2 seconds
- All 13 agency snapshot pages rendered with real data
- Resolution queue shows pending items with approve/reject actions
- Scenario modeling accepts parameters and displays projected impact
- Real-time updates refresh data without page reload
- Mobile-responsive layout passes on iPad and iPhone
- Molham approves UI/UX in user acceptance testing
