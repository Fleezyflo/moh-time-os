# Phase 3 Remaining Work — Implementation Plan

## Status Check

**PR #35 (Phase 3.1 Portfolio):** Pushed with regenerated system-map.json. Awaiting CI green + merge.
**New rule learned:** Regenerate `docs/system-map.json` after adding UI routes to `router.tsx`.

---

## Scope Assessment — What Already Exists vs What BUILD_PLAN Specifies

### 3.2 Inbox Enhancement — LOW delta
The existing `Inbox.tsx` (831 lines) is already feature-rich:
- PageLayout + SummaryGrid + 4 MetricCards ✅
- 3-tab system (needs_attention / snoozed / recently_actioned) ✅
- Type filters (issue / flagged_signal / orphan / ambiguous) ✅
- Severity filters ✅
- Client search ✅
- Sort options (severity / age / client) ✅
- InboxCard with unread indicator (`!item.read_at`) ✅
- InboxDrawer with evidence, snooze picker, action buttons ✅

**BUILD_PLAN wants:** `InboxCategoryTabs` (risk/opportunity/anomaly/maintenance), `useInbox()`, `useInboxCounts()` hooks.

**What actually needs doing:**
1. Extract inline `fetchItems()` / `fetchCounts()` into `useInbox()` and `useInboxCounts()` hooks in `lib/hooks.ts` (+ matching fetch functions in `lib/api.ts`) — refactor, not new functionality
2. Add `InboxCategoryTabs` component — BUT: the API categorizes by type (issue/flagged_signal/orphan/ambiguous), not by risk/opportunity/anomaly/maintenance. Need to check if `/api/v2/inbox` supports a `category` filter. If not, this is a frontend grouping over the existing type field.

**Estimated changes:** ~2 new fetch functions, ~2 new hooks, ~1 new component (InboxCategoryTabs), refactor Inbox.tsx internals.

### 3.3 Client Detail Enhancement — MEDIUM delta
The existing `ClientDetailSpec.tsx` (791 lines) already has all 5 tabs:
- Overview ✅ (key metrics, top issues, recent positive signals)
- Engagements ✅ (brand → engagement hierarchy, health bars)
- Financials ✅ (issued/paid, AR aging buckets, invoices table)
- Signals ✅ (filter by sentiment, signal list with evidence)
- Team ✅ (member cards with task counts)
- PageLayout + SummaryGrid + 4 MetricCards ✅

**BUILD_PLAN wants:** TrajectorySparkline in header, TabContainer component, hooks for sub-endpoints.

**What actually needs doing:**
1. Refactor: Extract inline `useEffect/fetch` into named hooks (`useClientDetail(id)`) in `lib/hooks.ts` + `lib/api.ts`
2. Create `TabContainer` component (reusable tab UI, extracted from existing inline tabs) — used by both ClientDetail and Operations
3. No TrajectorySparkline yet exists — consider creating as part of this phase (BUILD_PLAN specifies it for Portfolio 3.1 but it wasn't built; it's also needed in 3.4)
4. Wire additional sub-endpoints IF they exist: `/api/v2/clients/{id}/invoices`, `/api/v2/clients/{id}/ar-aging`, `/api/v2/clients/{id}/team`

**Estimated changes:** ~4 new fetch functions, ~4 new hooks, ~2 new components (TabContainer, TrajectorySparkline), refactor ClientDetailSpec.tsx.

### 3.4 Team Detail Enhancement — LOW delta
The existing `TeamDetail.tsx` already has:
- PageLayout + SummaryGrid + MetricCards ✅
- Workload visualization ✅
- Proposals + Issues inline ✅

**BUILD_PLAN wants:** TrajectorySparkline in header, wire `/api/team/workload`.

**What actually needs doing:**
1. Add TrajectorySparkline in header (reuse from 3.3)
2. Add `useTeamWorkload()` hook + `fetchTeamWorkload()` fetch function (endpoint exists at `/api/team/workload`)
3. Show workload distribution data in the page

**Estimated changes:** ~1 fetch function, ~1 hook, ~10-20 lines in TeamDetail.tsx.

### 3.5 Operations Page — NEW page
No Operations page exists yet. `FixData.tsx` exists standalone.

**BUILD_PLAN wants:**
```
Operations.tsx
├── PageLayout title="Operations"
├── SummaryGrid (4 MetricCards)
├── TabContainer
│   ├── Tab "Data Quality" → FixDataCard[] (existing)
│   ├── Tab "Watchers" → WatcherList
│   └── Tab "Couplings" → CouplingList
```

**What needs doing:**
1. Create `Operations.tsx` using TabContainer (from 3.3)
2. Reuse existing hooks: `useFixData()`, `useWatchers()`, `useAllCouplings()`, `checkHealth()`
3. Create inline WatcherList and CouplingList sections (or extract from existing pages if patterns exist elsewhere)
4. Add route `/ops` in `router.tsx`, lazy import, add to NAV_ITEMS
5. Regenerate `docs/system-map.json` (learned in 3.1)

**Estimated changes:** ~1 new page (~150-200 lines), route + nav update, system-map regen.

---

## Execution Sequence

Each sub-phase = 1 PR. All on separate branches from main.

### PR 1: Phase 3.2 — Inbox hooks extraction + InboxCategoryTabs
**Branch:** `feat/phase-3-inbox-hooks`
**Files changed:**
- `time-os-ui/src/lib/api.ts` — add `fetchInbox()`, `fetchInboxCounts()`, `fetchInboxRecent()`
- `time-os-ui/src/lib/hooks.ts` — add `useInbox()`, `useInboxCounts()`
- `time-os-ui/src/components/inbox/InboxCategoryTabs.tsx` — new component
- `time-os-ui/src/components/inbox/index.ts` — barrel export
- `time-os-ui/src/pages/Inbox.tsx` — refactor to use hooks, add category tabs
- Docs: SESSION_LOG.md, HANDOFF.md

**No new routes → no system-map regen needed.**

### PR 2: Phase 3.3 + 3.4 — TabContainer, TrajectorySparkline, Client/Team enhancements
**Branch:** `feat/phase-3-client-team-enhance`
**Files changed:**
- `time-os-ui/src/components/shared/TabContainer.tsx` — new reusable tab component
- `time-os-ui/src/components/shared/TrajectorySparkline.tsx` — new sparkline component
- `time-os-ui/src/components/shared/index.ts` — barrel export
- `time-os-ui/src/lib/api.ts` — add `fetchClientDetail()`, `fetchTeamWorkload()`
- `time-os-ui/src/lib/hooks.ts` — add `useClientDetail()`, `useTeamWorkload()`
- `time-os-ui/src/pages/ClientDetailSpec.tsx` — refactor to use hook, add TabContainer + sparkline
- `time-os-ui/src/pages/TeamDetail.tsx` — add sparkline + workload section
- Docs: SESSION_LOG.md, HANDOFF.md

**No new routes → no system-map regen needed.**

### PR 3: Phase 3.5 — Operations page
**Branch:** `feat/phase-3-operations`
**Files changed:**
- `time-os-ui/src/pages/Operations.tsx` — new page
- `time-os-ui/src/pages/index.ts` — add export
- `time-os-ui/src/router.tsx` — add route + nav item
- `docs/system-map.json` — **must regenerate** (new `/ops` route)
- Docs: SESSION_LOG.md, HANDOFF.md, CLAUDE.md (new rule about system-map regen)

---

## Verification per PR

Each PR must pass before merge:
1. `ruff check` + `ruff format --check` — zero issues on changed `.py` files (none expected for UI-only PRs)
2. `npx tsc --noEmit` — zero TypeScript errors (Mac only)
3. `pnpm exec prettier --write <files>` — format new/changed TS/TSX files (Mac only)
4. Pre-push 7-gate verification
5. CI green (including drift detection — only PR 3 needs system-map regen)
6. Governance check: commit message has deletion rationale if >20 deletions, large-change if >50 files

## Commit Message Templates

- PR 1: `feat: extract inbox hooks and add category tabs`
- PR 2: `feat: add TabContainer, TrajectorySparkline, enhance client and team pages`
- PR 3: `feat: add operations page with data quality, watchers, and couplings tabs`

All under 72 chars, lowercase after prefix.
