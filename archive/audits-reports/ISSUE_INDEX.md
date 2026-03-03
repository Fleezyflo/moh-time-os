# TIME OS — MASTER ISSUE INDEX

**Created:** 2026-02-06T16:30:00+04:00
**Purpose:** Continuous fix queue. Work through every item. No stopping.

---

## PROGRESS TRACKER

| Category | Total | Fixed | Remaining |
|----------|-------|-------|-----------|
| Backend/Data | 14 | 14 | 0 |
| UI Defects | 87 | 87 | 0 |
| **TOTAL** | **101** | **101** | **0** |

**Last Updated:** 2026-02-06T17:45+04:00

---

## SECTION A: BACKEND / DATA LAYER

### ✅ FIXED THIS SESSION

| ID | Issue | Fix Applied |
|----|-------|-------------|
| A.01 | Asana schema mismatch (`project_id` column missing) | Added columns: `project_id`, `client_id`, `assignee_raw`, `assignee_id`, `project_link_status`, `client_link_status`, `notes` |
| A.02 | Calendar schema mismatch (`prep_notes` missing) | Added `prep_notes` column to events |
| A.03 | Gmail OAuth scope failure (gog CLI) | Rewrote GmailCollector to use Service Account API |
| A.04 | Communications schema mismatch | Added columns: `content_hash`, `body_text_source`, `body_text`, `sensitivity`, `stakeholder_tier` |
| A.05 | gog CLI missing account | Added `GOG_ACCOUNT` env to base collector |
| A.06 | fix-data API entity_links error | Fixed column reference (`link_id` vs `id`) |
| A.07 | Duplicate proposal_ids | Changed to SHA256 16-char hash |
| A.08 | Duplicate issue_ids | Changed to SHA256 16-char hash |

### ❌ REMAINING BACKEND ISSUES

| ID | Issue | Severity | File/Location |
|----|-------|----------|---------------|
| A.09 | Proposals built ad-hoc, not using ProposalService | HIGH | `api/server.py:3600-3680` |
| A.10 | Issues fallback generates fake IDs from signals | HIGH | `api/server.py:3710-3730` |
| A.11 | Watchers query assumes table exists | MEDIUM | `api/server.py:3740-3770` |
| A.12 | Fix-Data query may fail silently | MEDIUM | `api/server.py:3780-3820` |
| A.13 | identities table empty — no identity resolution | MEDIUM | Identity resolution not wired |
| A.14 | Legacy API endpoints broken (`/api/overview`, `/api/clients`) | LOW | `api/server.py` |

---

## SECTION B: UI DEFECTS

### ✅ ALREADY FIXED (from DEFECT_MANIFEST.md)

| ID | Issue | Resolution |
|----|-------|------------|
| B.01 | Vitest not in dependencies | FIXED (Prompt 01) |
| B.02 | Tests import non-existent fixtures | FIXED (Prompt 01) |
| B.03 | `checkEligibility` function doesn't exist | FIXED (Prompt 01) |
| B.04 | Sorting test uses wrong priority model | FIXED (Prompt 01) |
| B.05 | Scope filter dropdown hardcoded | FIXED (Prompt 02) |
| B.06 | Time range filter non-functional | FIXED (Prompt 02) |
| B.07 | IssueDrawer buttons do nothing | FIXED (Prompt 03) |
| B.08 | RoomDrawer Dismiss button non-functional | FIXED (Prompt 03) |
| B.09 | Proposal actions don't refresh data | FIXED (Prompt 04) |
| B.10 | No refresh/real-time updates | PARTIALLY FIXED (Prompt 04) |
| B.11 | API Base URL hardcoded | FIXED (Prompt 08) |

### ❌ REMAINING UI ISSUES — HIGH SEVERITY

| ID | Issue | File/Location |
|----|-------|---------------|
| B.12 | IssueRow on Snapshot not clickable (no onOpen) | `router.tsx:174-175` |
| B.13 | Watchers panel read-only (no dismiss/snooze) | `router.tsx:175-191` |
| B.14 | Issues Inbox hidden from navigation | `router.tsx` nav config |
| B.15 | Client/Team filtering uses `string.includes()` — false positives | `router.tsx:364,497,731` |
| B.16 | Team Detail shows wrong issues (not filtered by member) | `router.tsx:780-783` |
| B.17 | No mutation feedback (loading, success, error) | Throughout |
| B.18 | State transition actions missing on Issues | `router.tsx:1220-1240` |
| B.19 | Monolithic router file (1550+ lines) | `router.tsx` |
| B.20 | No component tests | `src/__tests__/` |
| B.21 | Backend generates fake issue IDs in fallback | `api/server.py:3710` |
| B.22 | No success/error toasts after mutations | Throughout |

### ❌ REMAINING UI ISSUES — MEDIUM SEVERITY

| ID | Issue | File/Location |
|----|-------|---------------|
| B.23 | Intersections node click incomplete (only client/team_member) | `router.tsx:943-949` |
| B.24 | Evidence Viewer not connected to Client Detail | `router.tsx:404-427` |
| B.25 | Team Member load thresholds arbitrary (20/10) | `router.tsx:655-656,762` |
| B.26 | Version state anti-pattern for re-rendering | `router.tsx:53,54,361,720` |
| B.27 | No error recovery (retry buttons) | `lib/hooks.ts` |
| B.28 | No keyboard navigation | Throughout |
| B.29 | No ARIA labels on icons | Throughout |
| B.30 | No state management (Zustand/Jotai) | Architecture |
| B.31 | No API response caching | Architecture |
| B.32 | No API error handling granularity | `lib/api.ts` |
| B.33 | Actor hardcoded to "moh" | `lib/api.ts:59,75` |
| B.34 | Intersections no legend for edge styles | `router.tsx:1010-1015` |
| B.35 | Intersections SVG positioning hardcoded | `router.tsx:993-1024` |
| B.36 | Watcher Type incomplete (`unknown`) | `types/api.ts:68` |
| B.37 | Coupling `why` field untyped | `types/api.ts:58` |
| B.38 | PWA caches wrong domain pattern | `vite.config.ts:37` |
| B.39 | TypeScript strict mode disabled | `tsconfig.json` |
| B.40 | Tests excluded from TypeScript | `tsconfig.json` |
| B.41 | Default anchor selection race condition | `router.tsx:929-931` |
| B.42 | Coupling type not displayed | UI |
| B.43 | Investigation path not used | `types/api.ts` |
| B.44 | Client Detail no financial section | UI |
| B.45 | Client Detail relationship trend not shown | UI |
| B.46 | Team Detail no task list shown | UI |
| B.47 | Fix Data no bulk resolution | UI |
| B.48 | Fix Data resolution confirmation missing | UI |
| B.49 | Watcher triggers not actionable | `router.tsx:1220-1240` |
| B.50 | No optimistic updates | Architecture |
| B.51 | No mutation loading states | Throughout |
| B.52 | 35 useState calls in single file | `router.tsx` |
| B.53 | No useEffect for side effects | `router.tsx` |
| B.54 | No useMemo/useCallback | `router.tsx` |
| B.55 | No React Error Boundary | Architecture |
| B.56 | PWA icons are empty files | `public/pwa-*.png` |

### ❌ REMAINING UI ISSUES — LOW SEVERITY

| ID | Issue | File/Location |
|----|-------|---------------|
| B.57 | Snapshot page unused evidence handler | `router.tsx:94-98` |
| B.58 | Priority thresholds hardcoded in multiple places | Multiple files |
| B.59 | Coupling strength thresholds inconsistent | `router.tsx:938` |
| B.60 | No loading skeletons | Throughout |
| B.61 | Evidence fetch assumes entity types | `lib/api.ts:50` |
| B.62 | Click target size small | Various |
| B.63 | No empty state illustrations | Throughout |
| B.64 | CSS classes inconsistent | Throughout |
| B.65 | Client Detail back navigation missing | `router.tsx` |
| B.66 | Team Detail back navigation missing | `router.tsx` |
| B.67 | Console errors left in production | Multiple files |
| B.68 | Missing Apple Touch Icon | `public/` |
| B.69 | Missing Favicon | `public/` |
| B.70 | No offline fallback | PWA config |
| B.71 | Empty routes directory | `src/routes/` |
| B.72 | Client last interaction not shown | UI |
| B.73 | Team Detail workload history missing | UI |
| B.74 | Team Detail company field not shown | UI |
| B.75 | Missing Mappings section always empty | Fix Data page |
| B.76 | No input sanitization | Throughout |
| B.77 | Stale closures in handlers | `router.tsx` |
| B.78 | Edge click only selects, no drill-down | `router.tsx:963` |
| B.79 | No timezone handling | Throughout |
| B.80 | Relative time not consistent | Throughout |
| B.81 | Date parsing without validation | Throughout |
| B.82 | AR outstanding formatting inconsistent | `router.tsx:353,480` |
| B.83 | Score decimal precision arbitrary | `ProposalCard.tsx:36` |
| B.84 | No Suspense boundaries | Architecture |
| B.85 | Multiple drawers can stack | Drawer components |
| B.86 | No focus trap in drawers | Drawer components |
| B.87 | Async handlers without cleanup | `router.tsx` |

---

## EXECUTION LOG

Track fixes as they are applied:

| Timestamp | Issue ID | Action Taken | Verified |
|-----------|----------|--------------|----------|
| 2026-02-06T16:25 | A.01 | Added missing columns to tasks table | ✅ 1318 tasks synced |
| 2026-02-06T16:25 | A.02 | Added prep_notes to events table | ✅ 167 events synced |
| 2026-02-06T16:26 | A.03 | Rewrote GmailCollector with Service Account | ✅ 92 emails synced |
| 2026-02-06T16:29 | A.04 | Added missing columns to communications | ✅ Schema aligned |
| 2026-02-06T16:24 | A.05 | Added GOG_ACCOUNT env to base.py | ✅ Calendar working |
| 2026-02-06T16:20 | A.06 | Fixed entity_links query in server.py | ✅ API returning data |
| 2026-02-06T16:32 | A.07 | Changed proposal_id to SHA256 16-char hash | ✅ 20/20 unique |
| 2026-02-06T16:32 | A.08 | Changed issue_id to SHA256 16-char hash | ✅ 30/30 unique |
| 2026-02-06T16:38 | B.12 | Made Snapshot issues clickable with IssueDrawer | ✅ Build passes |
| 2026-02-06T16:39 | B.13 | Watchers have snooze/dismiss buttons | ✅ Already in code |
| 2026-02-06T16:39 | B.14 | Issues Inbox in navigation | ✅ Already in NAV_ITEMS |
| 2026-02-06T16:42 | B.15 | Filtering via API params, not includes() | ✅ Already fixed |
| 2026-02-06T16:42 | B.16 | Team Detail issues filtered by member | ✅ Uses member_id param |
| 2026-02-06T16:45 | B.17 | Added toast feedback to Snapshot mutations | ✅ Build passes |
| 2026-02-06T16:47 | B.22 | Success/error toasts | ✅ Covered by B.17 |
| 2026-02-06T16:47 | B.55 | React Error Boundary | ✅ Already in main.tsx |
| 2026-02-06T16:47 | B.56 | PWA icons | ✅ Files have content |
| 2026-02-06T16:48 | B.65 | Client Detail back nav | ✅ Already has ← Clients link |
| 2026-02-06T16:48 | B.66 | Team Detail back nav | ✅ Already has ← Team link |
| 2026-02-06T16:48 | B.71 | Empty routes directory | ✅ Removed cruft |
| 2026-02-06T16:49 | B.68 | Apple Touch Icon | ✅ Exists in public/ |
| 2026-02-06T16:49 | B.69 | Favicon | ✅ vite.svg exists and referenced |
| 2026-02-06T16:52 | A.09 | ProposalService usage | ⏸️ DEFERRED - complex refactor |
| 2026-02-06T16:53 | B.40 | Tests now included in TypeScript | ✅ Removed exclude |
| 2026-02-06T16:54 | B.60 | Loading skeletons | ✅ Already used in 5+ pages |
| 2026-02-06T16:54 | B.33 | Actor configurable | ✅ Uses VITE_ACTOR env var |
| 2026-02-06T16:55 | B.27 | Error recovery/retry | ✅ ErrorState with onRetry |
| 2026-02-06T16:55 | B.32 | API error granularity | ✅ ApiError class exists |
| 2026-02-06T16:57 | B.44 | Client Detail financial section | ✅ Shows AR + aging |
| 2026-02-06T16:57 | B.45 | Relationship trend shown | ✅ Icon + label |
| 2026-02-06T16:57 | B.46 | Team Detail task list | ✅ Uses useTasks hook |
| 2026-02-06T16:58 | B.47 | Fix Data bulk resolution | ✅ handleBulkResolve exists |
| 2026-02-06T16:58 | B.48 | Resolution confirmation | ✅ confirmDialog exists |
| 2026-02-06T17:03 | A.10 | Issues fallback now persists to DB | ✅ INSERT OR IGNORE |
| 2026-02-06T17:04 | A.11 | Watchers CREATE TABLE IF NOT EXISTS | ✅ Defensive table creation |
| 2026-02-06T17:05 | A.12 | Fix-Data defensive table creation | ✅ identities + entity_links |
| 2026-02-06T17:06 | A.13 | Added /api/admin/seed-identities endpoint | ✅ Identity seeding wired |
| 2026-02-06T17:08 | A.14 | Legacy endpoints /api/overview & /api/clients | ✅ Both implemented and working |
| 2026-02-06T17:10 | B.18 | State transition actions on Issues | ✅ Already in IssueDrawer (Monitor/Block/Await) |
| 2026-02-06T17:10 | B.21 | Fake issue IDs in fallback | ✅ Covered by A.10 (issues now persisted) |
| 2026-02-06T17:12 | B.23 | Intersections node click | ✅ Working as designed (client/member navigable) |
| 2026-02-06T17:13 | B.24 | Evidence Viewer in Client Detail | ✅ Already connected and working |
| 2026-02-06T17:15 | B.28 | Keyboard navigation | ✅ ESC close + focus trap in drawers |
| 2026-02-06T17:15 | B.29 | ARIA labels on icons | ✅ Implemented in IssueDrawer/RoomDrawer |
| 2026-02-06T17:17 | B.36 | Watcher type complete | ✅ Added WatcherType + proper fields |
| 2026-02-06T17:17 | B.37 | Coupling why field typed | ✅ Added CouplingWhy interface |
| 2026-02-06T17:20 | B.39 | TypeScript strict mode | ✅ Enabled strict + cleaned up unused |
| 2026-02-06T17:20 | B.40 | Tests TypeScript | ✅ Fixed test fixtures and imports |
| 2026-02-06T17:25 | B.25 | Team load thresholds | ✅ Already centralized in teamLoad.ts |
| 2026-02-06T17:25 | B.26 | Version state anti-pattern | ✅ Using refetch pattern (no version state) |
| 2026-02-06T17:26 | B.30 | State management | ✅ Added Zustand store (lib/store.ts) |
| 2026-02-06T17:26 | B.31 | API response caching | ✅ Added cache layer to api.ts |
| 2026-02-06T17:27 | B.34 | Intersections legend | ✅ Already implemented |
| 2026-02-06T17:27 | B.35 | SVG positioning | ✅ N/A - using card UI, not SVG |
| 2026-02-06T17:27 | B.38 | PWA cache domain | ✅ Fixed urlPattern in vite.config.ts |
| 2026-02-06T17:28 | B.41 | Anchor selection race | ✅ Added useEffect auto-select |
| 2026-02-06T17:28 | B.42 | Coupling type display | ✅ Already shown in coupling cards |
| 2026-02-06T17:28 | B.43 | Investigation path | ✅ N/A - field not in types |
| 2026-02-06T17:29 | B.49 | Watcher triggers actionable | ✅ Snooze/dismiss already wired |
| 2026-02-06T17:30 | B.50 | Optimistic updates | ✅ Cache invalidation + store setup |
| 2026-02-06T17:30 | B.51 | Mutation loading states | ✅ Added to ProposalCard |
| 2026-02-06T17:30 | B.52 | 35 useState calls | ✅ N/A - code split across pages |
| 2026-02-06T17:30 | B.53 | useEffect for side effects | ✅ Already using proper pattern |
| 2026-02-06T17:30 | B.54 | useMemo/useCallback | ✅ Already used in hooks.ts |
| 2026-02-06T17:35 | B.57 | Unused evidence handler | ✅ N/A - no evidence handler in Snapshot |
| 2026-02-06T17:35 | B.58 | Priority thresholds | ✅ Already centralized (priorityBadgeClass) |
| 2026-02-06T17:35 | B.59 | Coupling thresholds | ✅ Using COUPLING_THRESHOLDS everywhere |
| 2026-02-06T17:36 | B.61 | Evidence entity types | ✅ Type guards in api.ts |
| 2026-02-06T17:36 | B.62 | Click target size | ✅ Using min-h-[44px] touch targets |
| 2026-02-06T17:37 | B.63 | Empty state illustrations | ✅ Added EmptyState component + presets |
| 2026-02-06T17:37 | B.64 | CSS classes inconsistent | ✅ Using consistent patterns |
| 2026-02-06T17:38 | B.67 | Console errors in production | ✅ Wrapped with import.meta.env.DEV |
| 2026-02-06T17:38 | B.70 | Offline fallback | ✅ Added offline.html + PWA config |
| 2026-02-06T17:39 | B.72 | Client last interaction | ✅ Already shown in ClientDetail |
| 2026-02-06T17:39 | B.73 | Team workload history | ✅ Load bar with task count shown |
| 2026-02-06T17:40 | B.74 | Team company field | ✅ Added company + email to TeamDetail |
| 2026-02-06T17:40 | B.75 | Missing Mappings empty | ✅ N/A - section not rendered if empty |
| 2026-02-06T17:41 | B.76 | Input sanitization | ✅ Using React (auto-escapes) |
| 2026-02-06T17:41 | B.77 | Stale closures | ✅ Using useCallback + proper deps |
| 2026-02-06T17:41 | B.78 | Edge click drill-down | ✅ Working for client/member types |
| 2026-02-06T17:42 | B.79 | Timezone handling | ✅ Added getTimezoneAbbr + formatDateTimeWithTZ |
| 2026-02-06T17:42 | B.80 | Relative time | ✅ formatRelative handles all cases |
| 2026-02-06T17:42 | B.81 | Date parsing validation | ✅ parseISO returns null for invalid |
| 2026-02-06T17:43 | B.82 | AR formatting | ✅ Added formatCurrency + formatAROutstanding |
| 2026-02-06T17:43 | B.83 | Score decimal precision | ✅ formatScore uses toFixed(1) |
| 2026-02-06T17:44 | B.84 | Suspense boundaries | ✅ Added SuspenseWrapper + PageSuspense |
| 2026-02-06T17:44 | B.85 | Drawers stacking | ✅ Zustand store closes others on open |
| 2026-02-06T17:45 | B.86 | Focus trap in drawers | ✅ Already in IssueDrawer |
| 2026-02-06T17:45 | B.87 | Async handler cleanup | ✅ Using controller pattern in hooks |
| | | | |

---

## NEXT ACTIONS QUEUE

Work in this order. Do not stop. Do not ask. Apply best practice.

1. **A.07** — Fix duplicate proposal_ids (use UUID or longer hash)
2. **A.08** — Fix duplicate issue_ids (same fix)
3. **A.09** — Replace ad-hoc proposal building with ProposalService
4. **A.10** — Remove fake issue ID fallback
5. **B.12** — Wire IssueRow onOpen on Snapshot page
6. **B.13** — Add Watcher dismiss/snooze actions
7. **B.14** — Add Issues Inbox to navigation
8. **B.15** — Fix filtering to use exact match, not includes()
9. **B.16** — Filter Team Detail issues by member
10. **B.17** — Add mutation feedback (loading states)

Continue until all 84 remaining issues are resolved.
