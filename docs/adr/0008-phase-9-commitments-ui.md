# ADR-0008: Phase 9 Commitments UI Page

## Status
Accepted

## Context
Phase 9 adds a Commitments page that wires 6 existing backend endpoints to the frontend. The backend endpoints (`/api/commitments`, `/api/commitments/untracked`, `/api/commitments/due`, `/api/commitments/summary`, `/api/commitments/{id}/link`, `/api/commitments/{id}/done`) already exist in `api/server.py` and are production-ready. No backend changes are made in this phase.

## Decision
Wire the existing commitment endpoints to a new frontend page following the established Phase 6-8 patterns:

1. Add 4 fetch functions, 2 mutation functions, and 3 TypeScript interfaces to `lib/api.ts`
2. Add 4 data-fetching hooks to `lib/hooks.ts`
3. Create Commitments page with three tabs (All, Untracked, Due Soon), summary cards, status filter, and untracked alert banner
4. Create 2 new components: CommitmentList, LinkToTaskDialog
5. Add `/commitments` route to the nav between Capacity and Clients

## Consequences
- One new nav item increases navigation width -- acceptable for the commitment tracking capability it provides
- System map grows from 23 to 24 UI routes
- No backend changes, no migration impact, no API surface changes
