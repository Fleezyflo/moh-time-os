# Time OS UI - Architecture

## Overview

Time OS UI is a React + TypeScript frontend for the Time OS control room. It provides visualization and management of client relationships, team operations, and operational issues.

## Tech Stack

- **Framework**: React 18 + TypeScript
- **Build**: Vite
- **Routing**: TanStack Router (file-based routes)
- **Styling**: Tailwind CSS
- **Testing**: Vitest
- **PWA**: vite-plugin-pwa

## Directory Structure

```
src/
├── components/       # Reusable UI components
│   ├── ErrorBoundary.tsx
│   ├── ErrorState.tsx
│   ├── Skeleton.tsx
│   ├── IssueDrawer.tsx
│   ├── RoomDrawer.tsx
│   └── ...
├── lib/             # Business logic and utilities
│   ├── api.ts       # API client functions
│   ├── hooks.ts     # Data fetching hooks
│   ├── priority.ts  # Priority calculation
│   ├── coupling.ts  # Coupling thresholds
│   ├── teamLoad.ts  # Team load calculation
│   ├── datetime.ts  # Date/time utilities
│   └── format.ts    # Number formatting
├── pages/           # Route components
│   ├── Snapshot.tsx
│   ├── Issues.tsx
│   ├── Clients.tsx
│   ├── Team.tsx
│   └── ...
├── types/           # TypeScript type definitions
│   └── api.ts       # API response types
├── router.tsx       # Route definitions
└── main.tsx         # App entry point
```

## Routing

Routes are defined in `src/router.tsx` using TanStack Router:

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `Snapshot` | Main dashboard with proposals |
| `/issues` | `Issues` | Issues inbox |
| `/clients` | `Clients` | Client list |
| `/clients/:clientId` | `ClientDetail` | Client detail |
| `/team` | `Team` | Team members list |
| `/team/:id` | `TeamDetail` | Team member detail |
| `/intersections` | `Intersections` | Entity coupling view |
| `/fix` | `FixData` | Data quality issues |

## Data Fetching

### API Client (`src/lib/api.ts`)

All API calls go through typed functions:

```typescript
// Fetching data
fetchProposals(limit, status, days, scope) → ApiResponse<ProposalResponse>
fetchIssues(limit, days, scope, memberId) → ApiResponse<IssuesResponse>
fetchClients() → ApiResponse<ClientsResponse>
fetchTeam() → ApiResponse<TeamResponse>

// Mutations
resolveIssue(issueId) → ApiResponse<void>
addNote(issueId, text, actor) → ApiResponse<void>
tagProposal(proposalId, data) → ApiResponse<void>
```

### Hooks (`src/lib/hooks.ts`)

React hooks wrap API calls with loading/error states and refetch:

```typescript
const { data, loading, error, refetch } = useProposals(limit, status, days, scope);
const { data, loading, error, refetch } = useIssues(limit, days, scope, memberId);
```

### Mutation Flow

1. User triggers action (e.g., "Resolve Issue")
2. Component calls API function (e.g., `api.resolveIssue(id)`)
3. On success, component calls `refetch()` to update list
4. UI reflects new state

## State Management

- **No global state library** - React state + hooks pattern
- **Data fetching state** - Managed by custom hooks in `src/lib/hooks.ts`
- **UI state** - Local component state (useState)
- **URL state** - TanStack Router search params for filters

## Key Domain Types

```typescript
// Proposal - Risk or opportunity flagged by the system
interface Proposal {
  proposal_id: string;
  headline: string;
  score: number;
  trend: 'rising' | 'falling' | 'flat';
  proposal_type: 'risk' | 'opportunity' | 'info';
  impact: { severity: string; signal_count: number; entity_type: string };
}

// Issue - Actionable item requiring attention
interface Issue {
  issue_id: string;
  headline: string;
  priority: number;  // 0-100, higher = more urgent
  state: 'open' | 'monitoring' | 'awaiting' | 'blocked' | 'resolved' | 'closed';
}

// Client - External organization
interface Client {
  id: string;
  name: string;
  risk_level: 'low' | 'medium' | 'high';
}

// TeamMember - Internal team member
interface TeamMember {
  id: string;
  name: string;
  role: string;
  load_score: number;
}
```

## Priority System

Priority is computed from multiple signals (see `src/lib/priority.ts`):

| Score Range | Label | Visual |
|-------------|-------|--------|
| 80-100 | Critical | Red |
| 60-79 | High | Orange |
| 40-59 | Medium | Amber |
| 0-39 | Low | Slate |

Thresholds are centralized in `PRIORITY_THRESHOLDS` constant.

## Coupling System

Entity relationships use strength thresholds (see `src/lib/coupling.ts`):

| Strength | Level | Visual |
|----------|-------|--------|
| ≥80% | Strong | Green |
| 60-79% | Medium | Amber |
| 50-59% | Weak | Red |
| <50% | Filtered | N/A |

## Error Handling

1. **ErrorBoundary** - Catches React render errors at app root
2. **ErrorState** - Displays fetch errors with retry button
3. **Per-component** - Loading/error/empty states in each page

## Testing

```bash
npm test              # Run all tests
npm run test:watch    # Watch mode
```

Tests cover:
- API configuration
- Priority calculations
- Format utilities
- Date/time utilities
