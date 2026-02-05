# Step 4 — IA + ROUTING LOCK (No Code)

## Objective
Lock navigation, routes, and deep-link patterns.

## Deliverables
Write:
- docs/ui_spec/02_INFORMATION_ARCHITECTURE.md
- docs/ui_spec/06_NAVIGATION_AND_ROUTING.md

Routes must include:
- / (Snapshot)
- /clients, /clients/:clientId
- /team, /team/:id
- /intersections
- /issues
- /fix-data

## Acceptance checks
- Every route maps to one or more queries in CONTROL_ROOM_QUERIES.md.
- Each route specifies primary drill paths and drawer usage.

## Stop condition
Unmappable route → remove or revise.
