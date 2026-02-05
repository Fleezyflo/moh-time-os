# Navigation & Routing — Time OS Control Room

LOCKED_SPEC

## Route-to-Query Mapping (Contract-Bound)

All queries referenced below are sourced from:
- **CONTROL_ROOM_QUERIES.md** (lines 9-31)
- **06_PROPOSALS_BRIEFINGS.md** (lines 180-193 for detailed SQL)

| Route | Routing Doc Section | Query Block | Query Doc Line |
|-------|---------------------|-------------|----------------|
| `/` | CONTROL_ROOM_QUERIES.md §Snapshot | `proposals` status='open' + `issues` active states + `issue_watchers` next 24h | L14-19 |
| `/clients` | CONTROL_ROOM_QUERIES.md §Client/Team | `proposals` + `issues` scoped by entity + `report_snapshots` | L25-27 |
| `/clients/:clientId` | CONTROL_ROOM_QUERIES.md §Client/Team | `proposals` + `issues` scoped to client_id | L25-27 |
| `/team` | CONTROL_ROOM_QUERIES.md §Client/Team | `team_member_metrics` with load bands | L25-27 |
| `/team/:id` | CONTROL_ROOM_QUERIES.md §Client/Team | `proposals` + `issues` scoped to member + responsiveness_signals | L25-27 |
| `/intersections` | CONTROL_ROOM_QUERIES.md §Intersections | `couplings` for anchor + compute endpoint | L29-31 |
| `/issues` | Derived from §Snapshot issues query | `issues` all states with filters | L16 |
| `/fix-data` | CONTROL_ROOM_QUERIES.md §Snapshot | `resolution_queue` / `entity_links` low confidence | L18-19 |

## Exact Query Blocks (from CONTROL_ROOM_QUERIES.md L14-19)

### Snapshot `/`
```
L15: proposals where status='open' ordered by score DESC, limit 7
L16: issues where state IN ('open','monitoring','awaiting','blocked') ordered by priority DESC, limit 5
L17: issue_watchers where active=1 and next_check_at <= now()+24h
L18: resolution_queue (if implemented) / entity_links with low confidence
```

### Client/Team `/clients/*`, `/team/*` (L25-27)
```
L26: Open Issues + Top Proposals scoped to entity
L27: report_snapshots when present; otherwise live Issues/Proposals
```

### Intersections `/intersections` (L29-31)
```
L30: Anchor is Proposal or Issue
L31: Render couplings for anchor; if absent, UI calls compute endpoint
```

## Route table

| Route | Page | Drawer Support | Deep Link Pattern |
|-------|------|----------------|-------------------|
| `/` | Snapshot (Control Room) | Yes | `/?drawer=proposal:{id}` |
| `/clients` | Client Portfolio | No | — |
| `/clients/:clientId` | Client Detail | Yes | `/clients/123?drawer=issue:{id}` |
| `/team` | Team Portfolio | No | — |
| `/team/:id` | Team Detail | Yes | `/team/456?drawer=proposal:{id}` |
| `/intersections` | Intersections | Yes | `/intersections?anchor=proposal:{id}` |
| `/issues` | Issues Inbox | Yes | `/issues?drawer=issue:{id}` |
| `/fix-data` | Fix Data Center | Yes | `/fix-data?drawer=fix:{id}` |

## Router implementation (TanStack Router)

```typescript
// src/router.tsx
import { createRouter, createRoute, createRootRoute } from '@tanstack/react-router'

const rootRoute = createRootRoute({ component: RootLayout })

const routes = [
  createRoute({ getParentRoute: () => rootRoute, path: '/', component: Snapshot }),
  createRoute({ getParentRoute: () => rootRoute, path: '/clients', component: ClientsPortfolio }),
  createRoute({ getParentRoute: () => rootRoute, path: '/clients/$clientId', component: ClientDetail }),
  createRoute({ getParentRoute: () => rootRoute, path: '/team', component: TeamPortfolio }),
  createRoute({ getParentRoute: () => rootRoute, path: '/team/$id', component: TeamDetail }),
  createRoute({ getParentRoute: () => rootRoute, path: '/intersections', component: Intersections }),
  createRoute({ getParentRoute: () => rootRoute, path: '/issues', component: IssuesInbox }),
  createRoute({ getParentRoute: () => rootRoute, path: '/fix-data', component: FixDataCenter }),
]

export const router = createRouter({ routeTree: rootRoute.addChildren(routes) })
```

## URL state encoding

### Query params (preserved across navigation)
- `scope` — client|brand|engagement filter (e.g., `?scope=client:123`)
- `horizon` — today|7d|30d (from CONTROL_ROOM_QUERIES.md L11)
- `drawer` — active drawer (e.g., `?drawer=proposal:456`)

### Path params
- `:clientId` — client entity ID
- `:id` — generic entity ID (team member, etc.)

### Drawer deep links
```
/?drawer=proposal:123           → Snapshot with ProposalDrawer open
/clients/456?drawer=issue:789   → Client Detail with IssueDrawer open
/intersections?anchor=proposal:123&drawer=coupling:456 → Intersections anchored
```

## Navigation behavior

### Hard refresh safety
- All routes return HTTP 200 (SPA fallback configured in Vite)
- State rehydrates from URL params
- Drawer opens if `?drawer=` present

### Back/forward
- Drawer close → updates URL (removes `?drawer=`)
- Back button → closes drawer or navigates to previous route

### Prefetching
- Portfolio pages prefetch first 3 detail routes on hover
- Drawer content loaded on demand

## Drill paths (interactive)

### From Snapshot
| Element | Click action |
|---------|--------------|
| ProposalCard | Open RoomDrawer with proposal evidence |
| IssueCard | Open IssueDrawer with state + watchers |
| FixDataCard | Open FixDataDrawer with resolution options |
| Client chip (in ProposalCard) | Navigate to `/clients/:clientId` |
| Team chip (in ProposalCard) | Navigate to `/team/:id` |

### From Client Detail
| Element | Click action |
|---------|--------------|
| ProposalCard | Open RoomDrawer |
| IssueCard | Open IssueDrawer |
| Evidence tab item | Open anchored excerpt in EvidenceViewer |

### From Team Detail
| Element | Click action |
|---------|--------------|
| ProposalCard | Open RoomDrawer |
| IssueCard | Open IssueDrawer |
| Responsiveness signal | Expand detail inline |

### From Intersections
| Element | Click action |
|---------|--------------|
| Node (entity) | Open RoomDrawer for that entity |
| Edge (coupling) | Open CouplingDrawer with strength + evidence |

### From Issues Inbox
| Element | Click action |
|---------|--------------|
| IssueRow | Open IssueDrawer |
| Filter chip | Apply filter (updates URL) |

### From Fix Data Center
| Element | Click action |
|---------|--------------|
| FixDataRow | Open FixDataDrawer |
| Resolve action | Confirm → update + close drawer |

## Error states (per route)

| Route | Empty state | Error state |
|-------|-------------|-------------|
| `/` | "No proposals require attention" | "Unable to load Control Room" |
| `/clients` | "No clients found" | "Unable to load clients" |
| `/clients/:clientId` | "Client not found" (404) | "Unable to load client" |
| `/team` | "No team members" | "Unable to load team" |
| `/team/:id` | "Team member not found" (404) | "Unable to load team member" |
| `/intersections` | "Select a Proposal or Issue to explore" | "Unable to compute couplings" |
| `/issues` | "No issues" | "Unable to load issues" |
| `/fix-data` | "All data clean ✓" | "Unable to load fix data" |

## Offline behavior

- **Cached routes**: `/`, `/clients`, `/team`, `/issues` (via service worker)
- **Stale indicator**: "Last synced: X minutes ago"
- **Action queue**: Tag/resolve actions queued if offline, sync on reconnect

LOCKED_SPEC
