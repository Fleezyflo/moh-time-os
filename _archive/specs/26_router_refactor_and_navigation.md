# 026 — Router refactor + navigation surface area

## Objective
Address the “router.tsx is 1550+ lines” architectural failure and the “Issues page hidden / built but not in navigation” class of defects by:
1) decomposing routing and page logic into focused modules, and
2) ensuring **every built page is reachable via navigation** (unless explicitly deprecated).

## Manifest anchors
## 1.3 Sorting Test Uses Old Priority Model
- **File:** `src/__tests__/sorting.test.ts`
- **Issue:** Test uses `priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 }` but API returns `priority: number` (0-100 scale)
- **Impact:** Test logic doesn't match actual data model
- **Severity:** HIGH

---

## 2. STUB / PLACEHOLDER DATA

### 2.1 Scope Filter Dropdown — Hardcoded Options
- **File:** `router.tsx` line ~142
- **Code:** `<option>All Scope</option><option>Client: Acme</option><option>Client: Beta</option>`
- **Issue:** Dropdown shows fake "Acme" and "Beta" clients instead of fetching real client list
- **Impact:** Filter is purely decorative, does nothing
- **Severity:** HIGH

### 2.2 Time Range Filter — Non-Functional
- **File:** `router.tsx` line ~146
- **Code:** `<option>7 days</option><option>Today</option><option>30 days</option>`
- **Issue:** Dropdown exists but value is never used — `useProposals(7, 'open')` hardcodes 7 days
- **Impact:** User can change dropdown but nothing happens
- **Severity:** HIGH

---

## 3. INCOMPLETE FUNCTIONALITY

### 3.1 IssueDrawer — Non-Functional Action Buttons
- **File:** `components/IssueDrawer.tsx` lines 78-82
- **Code:**
  ```tsx
  <button className="...">Resolve</button>
  <button className="...">Add Note</button>
  ```
- **Issue:** Buttons have no `onClick` handlers — clicking does nothing
- **Impact:** User expects "Resolve" to resolve the issue, but it's purely visual
- **Severity:** HIGH

### 3.2 RoomDrawer — Dismiss Button Non-Functional
- **File:** `components/RoomDrawer.tsx` line 85
- **Code:** `<button className="

## Scope (must-do)
- Split `time-os-ui/src/router.tsx` into:
  - `src/router/routes.tsx` (route definitions only)
  - `src/router/nav.ts` (navigation model + labels + icons if any)
  - `src/router/loaders.ts` (route loaders / data fetch hooks if applicable)
  - `src/router/actions.ts` (mutation handlers if applicable)
  - `src/pages/*` (move page components out of router)
- Replace “hidden page” behavior:
  - Add nav entry for Issues (and any other built-but-hidden pages identified during refactor).
  - Ensure route is registered and linked in UI.

## Constraints
- Keep behavior identical except for:
  - navigation exposes previously-hidden pages
  - code organization improves
- No new libraries.
- No large design changes.

## Acceptance criteria
- `router.tsx` shrinks to **< 250 LOC** (or is removed entirely).
- Navigation contains links for: Snapshot, Clients, Team, Intersections, Fix, Issues (and any existing pages you find).
- App builds and runs: `pnpm dev` with no runtime route errors.
- Basic smoke: can navigate between all pages without blank screens.

## Implementation steps
1. Create new files under `src/router/` and `src/pages/`.
2. Move page components out of router; keep exports stable.
3. Centralize nav items in `src/router/nav.ts` and render nav from that model (no duplicated strings).
4. Add Issues route + nav entry (and any other hidden routes you identify).
5. Fix imports and ensure types compile.

## Verification
- `pnpm -C time-os-ui typecheck` (or `pnpm dev` if no typecheck script exists)
- Manual: click every nav item; confirm URL changes and page renders.

## Output required
- A short diff summary (files created/removed, net change).
- Update `logs/WORKLOG.md` and `logs/TEST_NOTES.md`.
