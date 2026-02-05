# Data Access Layer — Time OS Control Room

LOCKED_SPEC

## Overview

This spec defines the data access layer for Time OS UI. All queries map directly to CONTROL_ROOM_QUERIES.md. The layer supports:
- **Fixture mode** — Static contract-shaped data for development/testing
- **Real mode** — SQLite database via API

## Query Functions (per CONTROL_ROOM_QUERIES.md)

### Snapshot Queries (CONTROL_ROOM_QUERIES.md L14-19)

| Function | Route | Query Source | Returns |
|----------|-------|--------------|---------|
| `getSnapshotProposals()` | `/` | L15: proposals WHERE status='open' ORDER BY score DESC LIMIT 7 | `Proposal[]` |
| `getSnapshotIssues()` | `/` | L16: issues WHERE state IN (...) ORDER BY priority DESC LIMIT 5 | `Issue[]` |
| `getSnapshotWatchers()` | `/` | L17: issue_watchers WHERE active=1 AND next_check_at <= now()+24h | `Watcher[]` |
| `getFixDataCount()` | `/` | L18: resolution_queue COUNT WHERE status='pending' | `number` |

### Client/Team Queries (CONTROL_ROOM_QUERIES.md L25-27)

| Function | Route | Query Source | Returns |
|----------|-------|--------------|---------|
| `getClients()` | `/clients` | Derived: clients with proposal/issue counts | `Client[]` |
| `getClientDetail(clientId)` | `/clients/:clientId` | L26: proposals + issues scoped to client | `{ client, proposals, issues }` |
| `getTeamMembers()` | `/team` | Derived: team_members with metrics | `TeamMember[]` |
| `getTeamDetail(memberId)` | `/team/:id` | L26: proposals + issues scoped to member | `{ member, proposals, issues }` |

### Intersections Queries (CONTROL_ROOM_QUERIES.md L29-31)

| Function | Route | Query Source | Returns |
|----------|-------|--------------|---------|
| `getAnchors()` | `/intersections` | Derived: recent proposals + issues for selection | `Anchor[]` |
| `getCouplings(anchorType, anchorId)` | `/intersections` | L30-31: couplings for anchor | `Coupling[]` |

### Issues Query

| Function | Route | Query Source | Returns |
|----------|-------|--------------|---------|
| `getIssues(filters)` | `/issues` | L16 extended: issues with state/priority filters | `Issue[]` |

### Fix Data Query

| Function | Route | Query Source | Returns |
|----------|-------|--------------|---------|
| `getFixDataQueue()` | `/fix-data` | L18-19: resolution_queue OR entity_links with confidence < 0.70 | `FixData[]` |

## Caching Strategy

### Cache Keys
```typescript
const cacheKeys = {
  snapshotProposals: (scope?: string, horizon?: string) => ['proposals', 'snapshot', scope, horizon],
  snapshotIssues: () => ['issues', 'snapshot'],
  snapshotWatchers: () => ['watchers', 'snapshot'],
  fixDataCount: () => ['fixData', 'count'],
  clients: () => ['clients'],
  clientDetail: (id: string) => ['clients', id],
  teamMembers: () => ['team'],
  teamDetail: (id: string) => ['team', id],
  issues: (filters?: object) => ['issues', JSON.stringify(filters)],
  fixDataQueue: () => ['fixData', 'queue'],
  anchors: () => ['anchors'],
  couplings: (type: string, id: string) => ['couplings', type, id],
};
```

### Stale Times
| Data Type | Stale After | Revalidate On |
|-----------|-------------|---------------|
| Proposals | 30s | Focus, mutation |
| Issues | 30s | Focus, mutation |
| Watchers | 60s | Focus |
| Fix Data | 60s | Resolution action |
| Clients | 5m | Focus |
| Team | 5m | Focus |
| Couplings | 5m | Anchor change |

### Invalidation Rules
| Mutation | Invalidates |
|----------|-------------|
| Tag proposal | snapshotProposals, issues, clientDetail, teamDetail |
| Snooze proposal | snapshotProposals |
| Dismiss proposal | snapshotProposals |
| Transition issue | snapshotIssues, issues, clientDetail, teamDetail |
| Resolve fix data | fixDataCount, fixDataQueue, snapshotProposals |

## Offline Behavior

### Cached Routes (Service Worker)
- `/` — Full snapshot data
- `/clients` — Client list
- `/team` — Team list
- `/issues` — Issue list

### Stale Indicator
When data is stale and offline:
- Show banner: "Last synced: X minutes ago"
- Data still renders from cache
- Actions are queued

### Action Queue
Offline mutations are queued in IndexedDB:
```typescript
interface QueuedAction {
  id: string;
  type: 'tag' | 'snooze' | 'dismiss' | 'transition' | 'resolve';
  payload: object;
  timestamp: string;
}
```

On reconnect:
1. Process queue in order
2. Revalidate affected caches
3. Show sync status

## Loading States

### Per-Route Loading
| Route | Skeleton Pattern |
|-------|------------------|
| `/` | 3 ProposalCard skeletons + 3 IssueRow skeletons |
| `/clients` | 6 ClientCard skeletons (grid) |
| `/clients/:id` | Header skeleton + 2 IssueCard + 2 ProposalCard |
| `/team` | 4 TeamCard skeletons (grid) |
| `/team/:id` | Header + LoadBar skeleton + 3 SignalRow |
| `/intersections` | AnchorList skeleton + empty map |
| `/issues` | 5 IssueRow skeletons |
| `/fix-data` | 3 FixDataCard skeletons |

### Error States
| Error Type | UI Behavior |
|------------|-------------|
| Network error | Show last cached data + error banner |
| 404 | Show "Not found" with back link |
| 500 | Show "Unable to load" with retry button |
| Timeout | Show cached data if available, else loading skeleton |

## DataProvider Implementation

```typescript
interface DataProviderProps {
  mode: 'fixture' | 'real';
  apiBaseUrl?: string;
  children: React.ReactNode;
}

// Fixture mode: returns static data from fixtures/index.ts
// Real mode: fetches from API (to be implemented)
```

## Type Contracts (from PROPOSAL_ISSUE_ROOM_CONTRACT.md)

All query functions return types that match the contract exactly:
- `Proposal` — proposal_id, headline, impact, top_hypotheses, proof, missing_confirmations, score, trend, occurrence_count, status
- `Issue` — issue_id, state, priority, primary_ref, resolution_criteria, last_activity_at, next_trigger
- `Watcher` — watcher_id, issue_id, next_check_at, trigger_condition
- `FixData` — fix_data_id, fix_type, description, candidates, impact_summary, affected_proposal_ids

## Sorting Rules (from Page Specs)

| Query | Sort Order | Source |
|-------|------------|--------|
| Snapshot proposals | score DESC | 06_PROPOSALS_BRIEFINGS.md L141 |
| Snapshot issues | priority DESC | CONTROL_ROOM_QUERIES.md L16 |
| Watchers | next_check_at ASC | CONTROL_ROOM_QUERIES.md L17 |
| Fix data | affected_count DESC, created_at ASC | 08_FIX_DATA_CENTER.md |
| Client list | posture priority, then name | 02_CLIENTS_PORTFOLIO.md |
| Team list | load_band priority, then name | 04_TEAM_PORTFOLIO.md |
| Issues | priority DESC, last_activity_at DESC | 07_ISSUES_INBOX.md |
| Couplings | strength DESC | 06_INTERSECTIONS.md |

LOCKED_SPEC
