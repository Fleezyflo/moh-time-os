# Information Architecture — Time OS Control Room

LOCKED_SPEC

## Core hierarchy

```
Time OS
├── Snapshot (/)                    ← Executive entry point, 90-second session
│   ├── Proposal Stack              ← Primary attention
│   ├── Right Rail                  ← Issues / Watchers / Fix Data
│   └── RoomDrawer                  ← Evidence + actions
│
├── Clients (/clients)              ← Client portfolio
│   └── Client Detail (/clients/:clientId)
│       ├── Open Issues
│       ├── Top Proposals
│       └── Evidence tabs (drill-down)
│
├── Team (/team)                    ← Team portfolio
│   └── Team Detail (/team/:id)
│       ├── Load/Throughput bands
│       ├── Responsiveness signals
│       └── Scoped Issues/Proposals
│
├── Intersections (/intersections)  ← Coupling explorer
│   └── Node/Edge → RoomDrawer
│
├── Issues (/issues)                ← Issue lifecycle inbox
│   └── Issue Detail (drawer)
│
└── Fix Data (/fix-data)            ← Data quality resolution
    └── Fix Detail (drawer)
```

## Navigation model

### Primary navigation (persistent)
- **Snapshot** — always-visible home anchor
- **Clients** — client portfolio
- **Team** — team portfolio
- **Intersections** — coupling workspace
- **Issues** — lifecycle inbox
- **Fix Data** — data quality center

### Mobile: bottom nav bar (5 slots + overflow)
- Snapshot, Clients, Team, Issues, More (→ Intersections, Fix Data)

### Desktop: left rail + top bar
- Left rail: navigation items
- Top bar: scope selector, time horizon, search

## Depth model

| Level | Surface | Interaction |
|-------|---------|-------------|
| L0 | Portfolio/List | Scan, filter, sort |
| L1 | Card | Tap → RoomDrawer (inline) |
| L2 | RoomDrawer | Evidence, actions, drill |
| L3 | Evidence detail | Anchored excerpts, source link |

**Rule:** No tables at L0/L1. Tables appear only at L2/L3 (audit/drill views).

## Entity relationships

```
Client ←→ Engagements ←→ Brands
   ↓           ↓           ↓
Proposals ←→ Issues ←→ Team Members
   ↓           ↓
Evidence   Watchers
   ↓
Fix Data (unresolved links)
```

## Drill paths (from Snapshot)

| Starting surface | Primary drill | Secondary drill |
|------------------|---------------|-----------------|
| ProposalCard | RoomDrawer (evidence + hypotheses) | Client Detail, Team Detail |
| IssueCard | Issue Detail drawer | Originating Proposal, Client |
| FixDataCard | Fix Data drawer | Affected Proposals/Issues |
| WatcherRow | Issue Detail drawer | — |

## Scope inheritance

- **Global scope** (top bar): All, Client filter, Brand filter, Engagement filter
- **Time horizon**: Today, 7d, 30d
- **Scope flows down**: Snapshot → all child views respect scope
- **Override**: Detail pages can expand scope to show cross-entity couplings

## Search model

- Global search → Proposals, Issues, Clients, Team
- Results grouped by entity type
- Click → Detail drawer with context preserved

## Drawer behavior

- **Always slide-in from right** (mobile: full-screen bottom sheet)
- **Stacking**: max 2 drawers (root + child)
- **Close**: swipe right or tap outside (desktop)
- **Deep link**: drawer state encoded in URL (`?drawer=proposal:123`)

## Mobile-first considerations

- Touch targets: 44px minimum
- Swipe gestures: left/right for card actions, down to dismiss drawer
- Offline: show cached data + sync indicator
- PWA: installable, service worker caches critical routes
