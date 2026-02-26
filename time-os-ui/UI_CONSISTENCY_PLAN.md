# UI Consistency Plan — MOH Time OS

## Diagnosis

The UI has two independent color systems, no shared layout primitives, and every page reinvents its own structure. The result is a codebase where half the app looks one way and half looks another, with inconsistencies in spacing, typography weight, grid columns, card padding, and semantic color usage across every single page.

---

## Problem 1: Two Conflicting Color Systems

**What exists:**

The design system defines a pure-black palette in `design/system/tokens.css`:
```
--black: #000000
--grey-dim: #111111
--grey: #222222
--grey-mid: #333333
--grey-light: #888888
--white: #f5f5f5
```

The Tailwind slate palette lives in `index.css` `:root`:
```
--bg-primary: #0f172a    (slate-900)
--bg-secondary: #1e293b  (slate-800)
--bg-tertiary: #334155    (slate-700)
```

These are fundamentally different visual languages. Pure black (#000000) vs. dark blue-grey (#0f172a).

**Where each is used:**

| Color System | Files |
|---|---|
| CSS tokens (mostly) | Inbox, Issues, ClientIndex, Team, Snapshot, FixData, TeamDetail, ColdClients, ClientDetailSpec, RecentlyActiveDrilldown |
| Hardcoded slate | CommandCenter, Briefing, Signals, Patterns, Proposals, ClientIntel, PersonIntel, ProjectIntel, RoomDrawer, IssueDrawer, ProfileShell, ProfileHeader, ProfileSection, ConnectedEntities, SignalCard, Scorecard, Badges, PatternCard, ProposalCard (intel), EntityLink, EvidenceList, DistributionChart, DimensionBar, Sparkline, HealthScore, ErrorState, Skeleton, Toast, IssueCard, ProposalCard (shared), FixDataCard, ConfidenceBadge, PostureStrip, EvidenceViewer, EmptyState, SuspenseWrapper |
| CSS tokens (fully) | Card.tsx, Badge.tsx, DataGrid.tsx, ConfirmationDialog.tsx |

**Even the tokenized pages leak:** Inbox uses `bg-orange-500`, `ring-red-500/50`, `bg-blue-600`, `hover:bg-slate-750`. ClientDetailSpec uses `bg-purple-500`, `bg-orange-700`, `bg-blue-600`, `bg-slate-500`. TeamDetail uses `bg-amber-500/20`, `bg-purple-500/20`.

**The root layout itself** (`router.tsx`) uses `bg-slate-900 text-slate-200`, which means the shell contradicts the design tokens.

### Fix

**Decision required:** Which palette wins? The options:

1. **Pure black tokens win** — Migrate all slate to token equivalents. The design system documentation (`DESIGN_SYSTEM.md`) was written for this. Every `bg-slate-800` becomes `bg-[var(--grey-dim)]`, every `text-slate-400` becomes `text-[var(--grey-light)]`, etc. The UI becomes the intended pure-black aesthetic.

2. **Slate palette wins** — Abandon the pure-black tokens, keep the Tailwind slate palette that the intelligence system already uses. Simpler migration (fewer files to change since intelligence + components = majority of files). Less distinctive visually.

3. **Reconcile both** — Redefine the CSS custom properties to map to slate values. `--grey-dim: #1e293b` instead of `#111111`. Keeps CSS var architecture but with the softer blue-grey palette. Every file using `var(--grey-dim)` automatically updates.

**Recommended: Option 3.** It preserves the CSS variable architecture (good for future theming) while unifying on the palette that most of the codebase already uses. Migration is mechanical: update `tokens.css` values, then replace all hardcoded slate classes with their token equivalents across the intelligence system.

### Migration inventory (if Option 3)

**Phase A — Update token values** (1 file):
- `design/system/tokens.css`: Change `--black` to `#0f172a`, `--grey-dim` to `#1e293b`, `--grey` to `#334155`, `--grey-mid` to `#475569`, `--grey-light` to `#94a3b8`, `--white` to `#f1f5f9`
- `index.css`: Remove duplicate `:root` definitions that conflict

**Phase B — Replace hardcoded slate in intelligence system** (~25 files):
- Every `bg-slate-800` → `bg-[var(--grey-dim)]`
- Every `bg-slate-900` → `bg-[var(--black)]`
- Every `bg-slate-700` → `bg-[var(--grey)]`
- Every `text-slate-400` → `text-[var(--grey-light)]`
- Every `text-slate-500` → `text-[var(--grey-mid)]`
- Every `text-slate-200`/`text-slate-100` → `text-[var(--white)]`
- Every `border-slate-700` → `border-[var(--grey)]`
- Every `border-slate-600` → `border-[var(--grey-mid)]`

Files requiring migration:
1. `router.tsx` — nav, layout shell
2. `intelligence/pages/CommandCenter.tsx`
3. `intelligence/pages/Briefing.tsx`
4. `intelligence/pages/Signals.tsx`
5. `intelligence/pages/Patterns.tsx`
6. `intelligence/pages/Proposals.tsx`
7. `intelligence/components/ProfileShell.tsx`
8. `intelligence/components/ProfileHeader.tsx`
9. `intelligence/components/ProfileSection.tsx`
10. `intelligence/components/ConnectedEntities.tsx`
11. `intelligence/components/SignalCard.tsx`
12. `intelligence/components/Scorecard.tsx`
13. `intelligence/components/Badges.tsx`
14. `intelligence/components/PatternCard.tsx`
15. `intelligence/components/ProposalCard.tsx` (intel version)
16. `intelligence/components/EntityLink.tsx`
17. `intelligence/components/EvidenceList.tsx`
18. `intelligence/components/DistributionChart.tsx`
19. `intelligence/components/DimensionBar.tsx`
20. `intelligence/components/Sparkline.tsx`
21. `intelligence/components/Skeletons.tsx`
22. `components/RoomDrawer.tsx`
23. `components/IssueDrawer.tsx`
24. `components/ErrorState.tsx`
25. `components/Skeleton.tsx`
26. `components/Toast.tsx`
27. `components/IssueCard.tsx`
28. `components/ProposalCard.tsx` (shared version)
29. `components/FixDataCard.tsx`
30. `components/ConfidenceBadge.tsx`
31. `components/PostureStrip.tsx`
32. `components/EvidenceViewer.tsx`
33. `components/EmptyState.tsx`
34. `components/SuspenseWrapper.tsx`

**Phase C — Fix hardcoded color leaks in core pages** (~8 files):
- Inbox: `bg-orange-500` → `bg-[var(--warning)]`, `ring-red-500/50` → `ring-[var(--danger)]/50`, `bg-blue-600` → `bg-[var(--accent)]`, `hover:bg-slate-750` → `hover:bg-[var(--grey)]`
- ClientDetailSpec: `bg-purple-500` → define `--tier-platinum` token, `bg-orange-700` → `--tier-bronze`, `bg-blue-600` → `var(--accent)`, `bg-slate-500` → `var(--grey-mid)`
- TeamDetail: `bg-amber-500/20` → `bg-[var(--warning)]/20`, `bg-purple-500/20` → `bg-[var(--info)]/20`
- RecentlyActiveDrilldown: `bg-blue-600` → `var(--accent)`, `bg-yellow-600` → `var(--warning)`
- ClientIndex: Verify all `bg-[var(--black)]` references still work after token value change
- Issues: Fix any remaining hardcoded colors
- ColdClients: Fix any remaining hardcoded colors

---

## Problem 2: No Shared Layout Primitives

**What exists:** Every page builds its own layout from scratch. There is no `PageLayout`, `PageHeader`, `PageContainer`, `MetricCard`, or `SummaryGrid` component.

**Consequence:** Each page chooses its own:
- Container spacing (`space-y-4` vs `space-y-6` vs bare `<div>`)
- Header font weight (`font-bold` vs `font-semibold`)
- Summary grid columns (2→4, 2→5, 3, 6)
- Metric card padding (`p-3` vs `p-4`)
- Back navigation pattern (ad-hoc links)

### Fix — Create shared layout components

**New file: `components/layout/PageLayout.tsx`**
```
Props: title, subtitle?, action?, backTo?, backLabel?, children
```
Renders: optional back link → header row (title + action) → `space-y-6` children container.

Standardizes:
- `space-y-6` as the page-level vertical rhythm (most pages already use this)
- `text-2xl font-semibold` as the page title style (intelligence pages already use this, and `font-semibold` is more refined)
- Back link pattern with `← {label}` using `var(--grey-light)` color

**New file: `components/layout/SummaryGrid.tsx`**
```
Props: children, columns?: 2 | 3 | 4 | 5 | 6
```
Renders: `grid grid-cols-2 md:grid-cols-{n} gap-4` with responsive breakpoint.

Standardizes: `gap-4` everywhere (Snapshot's `gap-3` is the outlier).

**New file: `components/layout/MetricCard.tsx`**
```
Props: label, value, subtext?, warning?, trend?: 'up' | 'down' | 'flat'
```
Renders: A `p-4` card with label on top, large value, optional subtext and trend indicator.

Standardizes: `p-4` padding (Snapshot's `p-3` is the outlier), consistent label/value typography.

### Migration per page

| Page | Current | Migration |
|---|---|---|
| Inbox | `space-y-4`, `font-bold`, no back link | Wrap in `PageLayout title="Inbox"`, inline metric cards → `SummaryGrid columns={4}` + `MetricCard` |
| Issues | bare div, `font-semibold`, summary `grid-cols-2 md:grid-cols-5` | Wrap in `PageLayout title="Issues"`, summary → `SummaryGrid columns={5}` + `MetricCard` |
| ClientIndex | `space-y-6`, `font-bold` | Wrap in `PageLayout title="Clients"` |
| Team | bare div, `font-semibold`, inline `grid-cols-2 md:grid-cols-4` | Wrap in `PageLayout title="Team"`, summary → `SummaryGrid columns={4}` + `MetricCard` |
| Snapshot | bare div, `font-semibold`, `gap-3`, `p-3` cards | Wrap in `PageLayout title="Snapshot"`, fix to `gap-4`/`p-4` via `SummaryGrid` + `MetricCard` |
| FixData | bare div, `font-semibold`, `grid-cols-3` | Wrap in `PageLayout title="Fix Data"`, summary → `SummaryGrid columns={3}` + `MetricCard` |
| TeamDetail | bare div, `font-semibold`, `← Team` back link | Wrap in `PageLayout title={name} backTo="/team" backLabel="Team"` |
| ColdClients | `space-y-6`, `font-bold`, `← Clients` back link | Wrap in `PageLayout title="Cold Clients" backTo="/clients" backLabel="Clients"` |
| ClientDetailSpec | `space-y-4`, `font-bold`, `← Clients` back link, tabs | Wrap in `PageLayout title={name} backTo="/clients" backLabel="Clients"` |
| RecentlyActiveDrilldown | `space-y-6`, `font-bold`, back link | Wrap in `PageLayout backTo="/clients" backLabel="Clients"` |
| CommandCenter | `space-y-6`, `font-semibold` | Wrap in `PageLayout title="Command Center"` |
| Briefing | `space-y-6 max-w-3xl`, `font-semibold` | Wrap in `PageLayout title="Daily Briefing"`, add `max-w-3xl` prop or className pass-through |
| Signals | `space-y-6`, `font-semibold` | Wrap in `PageLayout title="Active Signals"` |
| Patterns | `space-y-6`, `font-semibold` | Wrap in `PageLayout title="Detected Patterns"` |
| Proposals | `space-y-6`, `font-semibold` | Wrap in `PageLayout title="Proposals"` |

---

## Problem 3: Duplicate Component Definitions

**Three intelligence pages define inline components that already exist as shared components:**

| Page | Inline Component | Shared Equivalent |
|---|---|---|
| `Signals.tsx` | Inline `SeverityBadge` (lines ~30-45) | `intelligence/components/Badges.tsx` → `SeverityBadge` |
| `Signals.tsx` | Inline `SignalCard` (lines ~47-85) | `intelligence/components/SignalCard.tsx` |
| `Patterns.tsx` | Inline `SeverityBadge`, `TypeBadge` | `intelligence/components/Badges.tsx` → `PatternSeverityBadge`, `PatternTypeBadge` |
| `Patterns.tsx` | Inline `PatternCard` (lines ~55-100) | `intelligence/components/PatternCard.tsx` |
| `Proposals.tsx` | Inline `UrgencyBadge` (lines ~14-28) | `intelligence/components/Badges.tsx` → `UrgencyBadge` |
| `Proposals.tsx` | Inline `ProposalCard` (lines ~30-96) | `intelligence/components/ProposalCard.tsx` |

**Also duplicated across shared vs. intelligence:**
- `components/ProposalCard.tsx` (275 lines, core inbox version with Tag/Snooze/Dismiss actions)
- `intelligence/components/ProposalCard.tsx` (161 lines, intelligence version with rank/evidence/priority breakdown)

These serve different purposes (inbox interaction vs. intelligence detail) so both are valid, but the naming collision is confusing.

### Fix

1. **Delete inline duplicates from Signals.tsx, Patterns.tsx, Proposals.tsx** — Import from shared components instead. The shared versions are more complete (they have expandable detail, entity links, evidence).

2. **Rename for clarity:**
   - `components/ProposalCard.tsx` → `components/InboxProposalCard.tsx` (or keep as-is since it's already in a different directory, but update the export name in `components/index.ts` to be explicit)

---

## Problem 4: Unused Design System Primitives

**`design/system/tokens.css` defines component classes that no page uses:**

| Token Class | Purpose | Lines |
|---|---|---|
| `.card` | Standard card with `var(--grey-dim)` bg | ~line 200 |
| `.card-raised` | Elevated card variant | ~line 210 |
| `.metric-card` | Metric display card | ~line 220 |
| `.badge` | Badge component | ~line 240 |
| `.data-table` | Table styling | ~line 260 |
| `.btn` | Button variants | ~line 280 |
| `.alert` | Alert component | ~line 300 |
| 12-column grid system | `.grid-container`, `.col-*` | ~lines 350-400 |

**`components/ui/Card.tsx`, `Badge.tsx`, `DataGrid.tsx` are properly tokenized but never imported by any page.**

### Fix

Two options:

**A) Use the existing token classes.** Every page's inline card styling (`bg-slate-800 rounded-lg border border-slate-700 p-4`) gets replaced with the CSS class `.card` or the React `<Card>` component. This requires the color system fix (Problem 1) to land first so token values match the intended visual.

**B) Delete unused token classes.** If we're using React components (Card.tsx, etc.) instead of CSS classes, the CSS component classes in tokens.css are dead code. Keep the design tokens (colors, spacing, typography) but remove the component classes.

**Recommended: Use Card.tsx/Badge.tsx/DataGrid.tsx React components** (Option A but via React, not CSS classes). Delete the CSS component classes from tokens.css (they duplicate what the React components do). After the color migration (Problem 1), the React components will render with the correct palette.

### Where Card.tsx should replace inline styling

Every card-like element in these files:
- Inbox metric cards (4x inline `bg-[var(--grey-dim)] rounded-lg p-4`)
- Issues summary cards (5x inline metric cards)
- Team summary cards (4x inline metric cards)
- Snapshot metric cards (12x inline `p-3 bg-[var(--grey-dim)]`)
- FixData summary cards (3x inline cards)
- TeamDetail summary cards (4x inline cards)
- ColdClients summary cards (4x inline cards)
- All intelligence page cards where `bg-slate-800 border border-slate-700 rounded-lg` appears

---

## Problem 5: Inconsistent Signal/Severity/Status Color Mappings

**The same semantic concept has different color implementations across files:**

| Concept | IssueCard.tsx | IssueDrawer.tsx | Badges.tsx (intel) | ProposalCard (shared) | ProposalCard (intel) |
|---|---|---|---|---|---|
| Critical/Urgent | `text-red-400` | `text-red-400` | `bg-red-500/20 text-red-400` | `bg-red-500/20 text-red-400` | `bg-red-500/5 border-red-500/30` |
| Warning | `text-orange-400` | — | `bg-amber-500/20 text-amber-400` | `bg-amber-500/20 text-amber-400` | `bg-amber-500/5 border-amber-500/30` |
| Blocked | `bg-red-900/30 text-red-400` | `bg-red-900/30 text-red-400` | — | `bg-red-500/20 text-red-400` | — |

**IssueCard and IssueDrawer duplicate the entire `stateStyles` map** (30+ lines each, identical content).

### Fix

1. **Extract `stateStyles` to a shared constant** — New file `lib/issueStyles.ts` exporting `stateStyles`, `priorityColors`, `severityToPriority`, `getTitle`, `getType`, `getPriority`, `getLastActivity`, `getPriorityInfo`. Both IssueCard and IssueDrawer import from it.

2. **Create semantic color tokens** — Add to `tokens.css`:
   ```
   --severity-critical-bg: rgba(239, 68, 68, 0.1);
   --severity-critical-text: #f87171;
   --severity-critical-border: rgba(239, 68, 68, 0.3);
   --severity-warning-bg: rgba(245, 158, 11, 0.1);
   --severity-warning-text: #fbbf24;
   --severity-warning-border: rgba(245, 158, 11, 0.3);
   --severity-success-bg: rgba(34, 197, 94, 0.1);
   --severity-success-text: #4ade80;
   --severity-success-border: rgba(34, 197, 94, 0.3);
   ```
   All severity/status color usage across all components references these tokens instead of hardcoded `red-500/20`, `amber-500/20`, etc.

---

## Problem 6: Inconsistent Empty/Error/Loading States

**Empty states:** `EmptyState.tsx` is well-designed with presets (NoProposals, NoIssues, etc.) and uses `text-slate-300`/`text-slate-500` hardcoded. `SuccessState` uses `bg-green-500/10 border border-green-500/30`. These should use tokens.

**Error states:** `ErrorState.tsx` uses hardcoded `bg-amber-900/20`, `bg-red-900/20`, `text-slate-400`. Should use semantic severity tokens (Problem 5).

**Loading states:** Two separate skeleton systems:
- `components/Skeleton.tsx` — Generic skeletons (SkeletonRow, SkeletonCard, SkeletonPanel, SkeletonCardList, SkeletonCardGrid) using `bg-slate-700/50`, `bg-slate-800`, `border-slate-700`
- `intelligence/components/Skeletons.tsx` — Precise match skeletons for intelligence components (SkeletonSignalCard, SkeletonProposalCard, etc.) using same slate palette

Both systems are valid (generic + precise), but both use hardcoded slate instead of tokens.

### Fix

After Problem 1 (color system unification) lands, all these files get their hardcoded colors replaced with token references as part of Phase B.

No structural changes needed — the component architecture is sound. Just color token migration.

---

## Problem 7: Accessibility Gaps

**Keyboard navigation:**
- IssueDrawer has proper focus trap and ESC handling ✓
- RoomDrawer has ESC handling but no focus trap ✗
- ProposalCard (shared) has no keyboard interaction — click-only cards ✗
- All expandable cards (PatternCard, ProposalCard intel, SignalCard) use `onClick` on divs without `role="button"`, `tabIndex`, or `onKeyDown` ✗
- EmptyState action buttons are accessible ✓
- ConfirmationDialog is accessible ✓

**Color contrast:**
- `text-slate-500` on `bg-slate-800` = ~3.7:1 contrast — fails WCAG AA for normal text ✗
- `text-slate-400` on `bg-slate-800` = ~5.1:1 — passes ✓
- All red/amber/green signal colors on dark backgrounds pass ✓

**Screen reader:**
- IssueDrawer uses `role="dialog"`, `aria-modal`, `aria-labelledby` ✓
- RoomDrawer uses `role="dialog"`, `aria-modal`, `aria-label` ✓
- No other component uses ARIA roles for interactive patterns ✗
- Expandable cards don't announce expanded/collapsed state ✗

### Fix

1. **Add focus trap to RoomDrawer** — Port the pattern from IssueDrawer.

2. **Make interactive cards keyboard-accessible:**
   - Add `role="button" tabIndex={0} onKeyDown={handleKeyDown}` to every clickable card div
   - For expandable cards, add `aria-expanded={expanded}`
   - Files: PatternCard.tsx, ProposalCard.tsx (both), SignalCard.tsx, IssueCard.tsx, all page-level clickable cards

3. **Fix contrast:** Replace `text-slate-500` secondary text with `text-[var(--grey-light)]` (which maps to slate-400 after reconciliation = ~5.1:1).

---

## Problem 8: Chart Components Use Hardcoded RGB Values

**Sparkline.tsx** uses raw RGB strings:
```
'rgb(74 222 128)'   // green-400
'rgb(248 113 113)'  // red-400
'rgb(148 163 184)'  // slate-400
'rgb(30 41 59)'     // slate-800
```

**DistributionChart.tsx** uses raw RGB for default colors:
```
'rgb(59 130 246)'   // blue-500
'rgb(16 185 129)'   // emerald-500
'rgb(168 85 247)'   // purple-500
```

**ProjectOperationalState.tsx** uses raw RGB for task segments:
```
'rgb(34 197 94)'    // green for completed
'rgb(59 130 246)'   // blue for open
'rgb(239 68 68)'    // red for overdue
```

SVG elements can't use Tailwind classes, so these need CSS custom properties or computed values.

### Fix

Add chart-specific tokens to `tokens.css`:
```
--chart-green: rgb(74, 222, 128);
--chart-red: rgb(248, 113, 113);
--chart-amber: rgb(251, 191, 36);
--chart-blue: rgb(59, 130, 246);
--chart-purple: rgb(168, 85, 247);
--chart-emerald: rgb(16, 185, 129);
--chart-pink: rgb(236, 72, 153);
--chart-slate: rgb(148, 163, 184);
--chart-bg: rgb(30, 41, 59);
```

Then Sparkline, DistributionChart, ProjectOperationalState reference `var(--chart-green)` etc.

---

## Execution Order

The problems have dependencies:

```
Problem 1 (color system)  ← MUST BE FIRST
    ↓
Problem 2 (layout primitives) — can start in parallel with 1-B
    ↓
Problem 3 (dedup components) — independent
    ↓
Problem 4 (use shared components) — depends on 1 + 2
    ↓
Problem 5 (semantic color tokens) — depends on 1
    ↓
Problem 6 (empty/error/loading tokens) — depends on 1
    ↓
Problem 7 (accessibility) — independent, can run anytime
    ↓
Problem 8 (chart tokens) — depends on 1
```

### Proposed phases

**Phase 1: Foundation** (Problems 1A, 2, 3)
- Update token values in tokens.css + clean index.css
- Create PageLayout, SummaryGrid, MetricCard components
- Delete inline duplicates from Signals/Patterns/Proposals pages
- Extract shared issue styles

**Phase 2: Color Migration** (Problems 1B, 1C, 5, 6, 8)
- Replace hardcoded slate in all 34 intelligence/component files
- Fix hardcoded color leaks in 8 core pages
- Add semantic severity tokens
- Add chart color tokens
- Migrate all components to token references

**Phase 3: Layout Adoption** (Problems 2 migration, 4)
- Wrap all 15 pages in PageLayout
- Replace inline metric cards with MetricCard
- Replace inline card styling with Card component
- Delete unused CSS component classes from tokens.css

**Phase 4: Polish** (Problem 7)
- Add focus trap to RoomDrawer
- Add keyboard handlers to all interactive cards
- Fix contrast issues
- Add ARIA attributes to expandable components

---

## File Change Summary

| Category | Files | Estimated Changes |
|---|---|---|
| New files | 3 (PageLayout, SummaryGrid, MetricCard) | ~200 lines total |
| Token/style files | 2 (tokens.css, index.css) | ~80 lines changed |
| Shared utility | 1 (lib/issueStyles.ts) | ~50 lines new |
| Intelligence pages | 5 (CommandCenter, Briefing, Signals, Patterns, Proposals) | ~300 lines changed |
| Intelligence components | 12 (all in intelligence/components/) | ~400 lines changed |
| Intelligence view sections | 4 (ClientHealthBreakdown, PersonLoad, ProjectHealth, ProjectOps) | ~50 lines changed |
| Core pages | 10 (Inbox, Issues, ClientIndex, Team, Snapshot, FixData, TeamDetail, ColdClients, ClientDetailSpec, RecentlyActiveDrilldown) | ~500 lines changed |
| Shared components | 14 (RoomDrawer, IssueDrawer, ErrorState, Skeleton, Toast, IssueCard, ProposalCard, FixDataCard, ConfidenceBadge, PostureStrip, EvidenceViewer, EmptyState, SuspenseWrapper, ConfirmationDialog) | ~350 lines changed |
| Router | 1 (router.tsx) | ~20 lines changed |
| **Total** | **~52 files** | **~1,950 lines changed** |

No files are deleted (except inline component code within files). No new dependencies. No API changes. Pure UI-layer refactor.
