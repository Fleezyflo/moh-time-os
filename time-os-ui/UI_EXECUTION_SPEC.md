# UI Consistency — Execution Spec

Companion to `UI_CONSISTENCY_PLAN.md`. This document has the exact changes, token values, component specs, and verification steps needed to execute every phase.

---

## Errata: Corrections to the Plan Document

The plan document has three inaccuracies that must be noted before execution:

1. **`--grey-mid` does not exist.** The plan references `--grey-mid` as an existing token. The actual `tokens.css` defines only: `--black`, `--white`, `--grey`, `--grey-light`, `--grey-dim`. A new `--grey-mid` token must be created.

2. **Incorrect hex values.** The plan states `--grey-dim: #111111` and `--grey-light: #888888`. The actual values are `--grey-dim: #1a1a1a` and `--grey-light: #555555`.

3. **`--accent` conflict not documented.** `tokens.css` defines `--accent: #ff3d00` (red). `index.css` `:root` block redefines `--accent: #3b82f6` (blue). The `:root` override wins at runtime, meaning the blue accent is what users currently see. The plan's recommendation to remove the `:root` block would change the accent from blue to red — this needs a deliberate decision.

---

## Section 1: Token Mapping Table

### Current tokens.css neutral values → Proposed slate equivalents

| Token | Current Value | Proposed Value | Tailwind Equivalent | Used By |
|---|---|---|---|---|
| `--black` | `#000000` | `#0f172a` | slate-900 | Body bg, page bg |
| `--grey-dim` | `#1a1a1a` | `#1e293b` | slate-800 | Card bg, raised surfaces |
| `--grey` | `#333333` | `#334155` | slate-700 | Borders, dividers |
| `--grey-mid` | *(new token)* | `#475569` | slate-600 | Secondary borders, hover |
| `--grey-light` | `#555555` | `#94a3b8` | slate-400 | Secondary text |
| `--white` | `#ffffff` | `#f1f5f9` | slate-100 | Primary text |

### Additional neutrals needed (new tokens)

| Token | Value | Tailwind Equivalent | Purpose |
|---|---|---|---|
| `--grey-muted` | `#64748b` | slate-500 | Tertiary/muted text, timestamps |
| `--grey-subtle` | `#cbd5e1` | slate-300 | Emphasized secondary text |

### Slate class → token replacement map (the actual find/replace pairs)

This is the complete mapping for Phase 2 mechanical replacements:

| Slate Class | Token Replacement | Occurrences |
|---|---|---|
| `bg-slate-900` | `bg-[var(--black)]` | 7 |
| `bg-slate-800` | `bg-[var(--grey-dim)]` | 48 |
| `bg-slate-700` | `bg-[var(--grey)]` | ~20 (mostly borders, some bg) |
| `bg-slate-600` | `bg-[var(--grey-mid)]` | ~5 |
| `bg-slate-500` | `bg-[var(--grey-muted)]` | ~10 |
| `text-slate-100` | `text-[var(--white)]` | 7 |
| `text-slate-200` | `text-[var(--white)]` | 19 |
| `text-slate-300` | `text-[var(--grey-subtle)]` | 23 |
| `text-slate-400` | `text-[var(--grey-light)]` | 116 |
| `text-slate-500` | `text-[var(--grey-muted)]` | 150 |
| `text-slate-600` | `text-[var(--grey-mid)]` | ~10 |
| `border-slate-700` | `border-[var(--grey)]` | 115 |
| `border-slate-600` | `border-[var(--grey-mid)]` | ~13 |
| `slate-750` | `[var(--grey)]` | 1 (Inbox hover) |

### Compound patterns requiring careful replacement

These contain slate within opacity/modifier expressions:

| Pattern | Replacement |
|---|---|
| `bg-slate-800/50` | `bg-[var(--grey-dim)]/50` |
| `bg-slate-800/90` | `bg-[var(--grey-dim)]/90` |
| `bg-slate-800/95` | `bg-[var(--grey-dim)]/95` |
| `bg-slate-700/50` | `bg-[var(--grey)]/50` |
| `bg-slate-700/30` | `bg-[var(--grey)]/30` |
| `border-slate-700/50` | `border-[var(--grey)]/50` |
| `ring-slate-700` | `ring-[var(--grey)]` |
| `divide-slate-700` | `divide-[var(--grey)]` |

### Signal color tokens — unchanged

These are NOT being remapped. They stay as-is in tokens.css:

| Token | Value | Purpose |
|---|---|---|
| `--danger` | `#ff3d00` | Error/critical |
| `--warning` | `#ffcc00` | Warning/caution |
| `--success` | `#00ff88` | Success/healthy |
| `--info` | `#0a84ff` | Informational |

### Accent color decision needed

| Source | Value | Visual |
|---|---|---|
| `tokens.css` | `--accent: #ff3d00` | Red-orange (matches `--danger`) |
| `index.css :root` | `--accent: #3b82f6` | Blue (Tailwind blue-500) |

**Current behavior:** The `:root` override wins, so the app renders with blue accent. Most hardcoded accent references in intelligence pages use `blue-500`/`blue-600`, confirming blue is the de facto accent color.

**Recommendation:** Change `tokens.css` to `--accent: #3b82f6` and `--accent-dim: #3b82f666`. Then remove the `:root` block from `index.css`. This makes tokens.css the single source of truth while preserving the visual users currently see.

---

## Section 2: Per-File Change Specifications

### Phase 1A — Token values (2 files)

**`design/system/tokens.css`** — Update neutral values:
```
Line 18: --black: #000000;        → --black: #0f172a;
Line 19: --white: #ffffff;        → --white: #f1f5f9;
Line 20: --grey: #333333;         → --grey: #334155;
Line 21: --grey-light: #555555;   → --grey-light: #94a3b8;
Line 22: --grey-dim: #1a1a1a;     → --grey-dim: #1e293b;
```
Add after line 22:
```css
--grey-mid: #475569;
--grey-muted: #64748b;
--grey-subtle: #cbd5e1;
```
Update accent:
```
Line 25: --accent: #ff3d00;       → --accent: #3b82f6;
Line 26: --accent-dim: #ff3d0066; → --accent-dim: #3b82f666;
```
Update border values (line 96-98):
```
--border: 1px solid #333333;   → --border: 1px solid #334155;
--border-hover: 1px solid #555555; → --border-hover: 1px solid #475569;
--border-active: 1px solid #ff3d00; → --border-active: 1px solid #3b82f6;
```

**`time-os-ui/src/index.css`** — Delete `:root` block (lines 46-52):
```css
/* DELETE THIS ENTIRE BLOCK */
:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --accent: #3b82f6;
}
```
Add new tokens to `@theme` block (after line 18):
```css
--color-text-muted: var(--grey-muted);
--color-text-subtle: var(--grey-subtle);
--color-border-mid: var(--grey-mid);
```

### Phase 1B — Layout components (3 new files)

See Section 3 for full implementation specs.

### Phase 1C — Delete inline duplicates (3 files)

**`intelligence/pages/Signals.tsx`** — Delete inline `SeverityBadge` and `SignalCard` definitions. Add imports:
```tsx
import { SeverityBadge } from '../components/Badges';
import { SignalCard } from '../components/SignalCard';
```

**`intelligence/pages/Patterns.tsx`** — Delete inline `SeverityBadge`, `TypeBadge`, `PatternCard`. Add imports:
```tsx
import { PatternSeverityBadge, PatternTypeBadge } from '../components/Badges';
import { PatternCard } from '../components/PatternCard';
```

**`intelligence/pages/Proposals.tsx`** — Delete inline `UrgencyBadge` and `ProposalCard`. Add imports:
```tsx
import { UrgencyBadge } from '../components/Badges';
import { ProposalCard } from '../components/ProposalCard';
```

### Phase 1D — Extract shared issue styles (1 new file, 2 edits)

**New: `lib/issueStyles.ts`** — Extract from IssueCard.tsx:
- `stateStyles` map (currently duplicated in IssueCard.tsx and IssueDrawer.tsx)
- `getTitle`, `getType`, `getPriority`, `getLastActivity`, `getPriorityInfo` helpers

**`components/IssueCard.tsx`** — Delete `stateStyles` definition, import from `lib/issueStyles`
**`components/IssueDrawer.tsx`** — Delete `stateStyles` definition, import from `lib/issueStyles`

---

### Phase 2 — Color migration (53 files, 400 slate references)

Files ordered by reference count (highest first = highest risk):

| # | File | Slate Refs | Key Patterns |
|---|---|---|---|
| 1 | `components/RoomDrawer.tsx` | 48 | bg-slate-800, text-slate-400/500, border-slate-700 |
| 2 | `components/IssueDrawer.tsx` | 22 | bg-slate-800, text-slate-400/500, border-slate-700 |
| 3 | `intelligence/pages/Proposals.tsx` | 21 | bg-slate-800, text-slate-500/400, border-slate-700 |
| 4 | `intelligence/components/ProposalCard.tsx` | 21 | bg-slate-800, text-slate-500/400/300, border-slate-700 |
| 5 | `components/ProposalCard.tsx` | 19 | bg-slate-800, text-slate-500/400/100 |
| 6 | `intelligence/components/ConnectedEntities.tsx` | 17 | text-slate-500/400, border-slate-700 |
| 7 | `intelligence/pages/Briefing.tsx` | 16 | bg-slate-800, text-slate-400/500/300 |
| 8 | `intelligence/pages/Signals.tsx` | 14 | *(after Phase 1C dedup, ~5 remain)* |
| 9 | `intelligence/components/Skeletons.tsx` | 12 | bg-slate-700/50, bg-slate-800, border-slate-700 |
| 10 | `intelligence/components/SignalCard.tsx` | 12 | bg-slate-800, text-slate-500/400, border-slate-700 |
| 11 | `intelligence/pages/Patterns.tsx` | 11 | *(after Phase 1C dedup, ~3 remain)* |
| 12 | `intelligence/pages/CommandCenter.tsx` | 11 | text-slate-500/400, bg-slate-800 |
| 13 | `intelligence/components/PatternCard.tsx` | 11 | bg-slate-800, text-slate-500/400/300 |
| 14 | `intelligence/components/EvidenceList.tsx` | 10 | bg-slate-800/700, text-slate-500/400/300 |
| 15 | `components/FixDataCard.tsx` | 10 | bg-slate-800, text-slate-500/400, border-slate-700 |
| 16 | `intelligence/components/ProfileShell.tsx` | 9 | bg-slate-900/800, border-slate-700 |
| 17 | `components/EvidenceViewer.tsx` | 9 | bg-slate-800, text-slate-400/500/200/100 |
| 18 | `intelligence/components/ProfileHeader.tsx` | 8 | text-slate-400/500, bg-slate-700 |
| 19 | `components/IssueCard.tsx` | 8 | text-slate-500/400 (stateStyles remain) |
| 20 | `intelligence/components/Scorecard.tsx` | 7 | bg-slate-800, text-slate-500/400 |
| 21 | `intelligence/components/ActivityHeatmap.tsx` | 7 | text-slate-500/400, bg-slate-700 |
| 22 | `components/ErrorBoundary.tsx` | 7 | bg-slate-800, text-slate-400/500 |
| 23 | `router.tsx` | 6 | bg-slate-900, bg-slate-800/95, border-slate-700 |
| 24 | `pages/Inbox.tsx` | 6 | text-slate-500/400/600, bg-slate-750 |
| 25 | `intelligence/components/CommunicationChart.tsx` | 6 | text-slate-500/400, bg-slate-700 |
| 26 | `intelligence/components/Badges.tsx` | 6 | text-slate-500/400 |
| 27 | `constants/labels.ts` | 6 | slate color strings in label config |
| 28 | `intelligence/views/sections/PersonLoadDistribution.tsx` | 5 | text-slate-500/400/300, border-slate-700 |
| 29 | `intelligence/components/ProfileSection.tsx` | 5 | border-slate-700, text-slate-400 |
| 30 | `intelligence/components/DistributionChart.tsx` | 5 | text-slate-500/400 |
| 31 | `intelligence/components/DimensionBar.tsx` | 5 | text-slate-400, bg-slate-700/500 |
| 32 | `intelligence/views/sections/ProjectOperationalState.tsx` | 3 | bg-slate-800, text-slate-500/400 |
| 33 | `intelligence/components/Sparkline.tsx` | 3 | rgb(148 163 184), rgb(30 41 59) |
| 34 | `intelligence/components/EntityLink.tsx` | 3 | text-slate-500, bg-slate-700 |
| 35 | `components/notifications/Toast.tsx` | 3 | bg-slate-800/90 |
| 36 | `components/Toast.tsx` | 3 | bg-slate-800/90 |
| 37 | `components/Skeleton.tsx` | 3 | bg-slate-700/50, bg-slate-800 |
| 38 | `components/EmptyState.tsx` | 3 | text-slate-300/500 |
| 39 | `intelligence/views/sections/ProjectHealthSignals.tsx` | 2 | text-slate-500 |
| 40 | `intelligence/views/sections/ClientHealthBreakdown.tsx` | 2 | text-slate-400/500 |
| 41 | `intelligence/components/HealthScore.tsx` | 2 | text-slate-500/400 |
| 42 | `__tests__/priority.test.ts` | 2 | slate in test assertions |
| 43 | `types/generated.ts` | 1 | slate in type comment |
| 44 | `pages/Issues.tsx` | 1 | text-slate-500 |
| 45 | `pages/ClientDetailSpec.tsx` | 1 | text-slate-500 |
| 46 | `lib/priority.ts` | 1 | slate color string |
| 47 | `intelligence/components/BreakdownChart.tsx` | 1 | text-slate-500 |
| 48 | `components/ui/Badge.tsx` | 1 | single slate ref |
| 49 | `components/pickers/TeamMemberPicker.tsx` | 1 | slate ref |
| 50 | `components/SuspenseWrapper.tsx` | 1 | text-slate-400 |
| 51 | `components/PostureStrip.tsx` | 1 | bg-slate-700 |
| 52 | `components/ErrorState.tsx` | 1 | text-slate-400 |
| 53 | `components/ConfidenceBadge.tsx` | 1 | bg-slate-700 |

### Special cases in Phase 2

**`constants/labels.ts`** (6 refs) — Contains slate color strings as data values, not className strings. These define the colors for label badges. Must be changed to token var references or to the equivalent hex values.

**`lib/priority.ts`** (1 ref) — Contains a slate color as a return value. Change to equivalent hex or token reference.

**`__tests__/priority.test.ts`** (2 refs) — Test assertions that check for slate color strings. Must update to match whatever `lib/priority.ts` changes to.

**`types/generated.ts`** (1 ref) — Comment only. Cosmetic change, low priority.

**`components/ui/Badge.tsx`** (1 ref) — This component is otherwise fully tokenized. The single slate ref should be migrated to maintain its clean token-only status.

**`intelligence/components/Sparkline.tsx`** — Uses raw RGB strings (not Tailwind classes). These become `var(--chart-*)` token references per Problem 8.

### Phase 2 also adds new tokens to `tokens.css`

**Semantic severity tokens** (Problem 5):
```css
/* Severity Colors (with alpha for backgrounds) */
--severity-critical-bg: rgba(239, 68, 68, 0.1);
--severity-critical-text: #f87171;
--severity-critical-border: rgba(239, 68, 68, 0.3);
--severity-warning-bg: rgba(245, 158, 11, 0.1);
--severity-warning-text: #fbbf24;
--severity-warning-border: rgba(245, 158, 11, 0.3);
--severity-success-bg: rgba(34, 197, 94, 0.1);
--severity-success-text: #4ade80;
--severity-success-border: rgba(34, 197, 94, 0.3);
--severity-info-bg: rgba(59, 130, 246, 0.1);
--severity-info-text: #60a5fa;
--severity-info-border: rgba(59, 130, 246, 0.3);
```

**Chart tokens** (Problem 8):
```css
/* Chart Colors (for SVG/inline styles) */
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

---

## Section 3: Component Implementation Specs

### PageLayout

**File:** `src/components/layout/PageLayout.tsx`

```tsx
interface PageLayoutProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  backTo?: string;
  backLabel?: string;
  maxWidth?: 'default' | 'narrow';  // narrow = max-w-3xl (Briefing)
  className?: string;
  children: ReactNode;
}
```

**DOM structure:**
```
<div className="space-y-6 {maxWidth === 'narrow' ? 'max-w-3xl' : ''} {className}">
  {backTo && (
    <Link to={backTo} className="text-sm text-[var(--grey-light)] hover:text-[var(--white)] transition-colors">
      ← {backLabel || 'Back'}
    </Link>
  )}
  {title && (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--white)]">{title}</h1>
        {subtitle && <p className="text-sm text-[var(--grey-light)] mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  )}
  {children}
</div>
```

**Interaction with router.tsx:** The router's `<main>` already provides `max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6`. PageLayout sits inside that — it does NOT duplicate the container. It only adds the vertical rhythm and header pattern.

**Responsive:** No breakpoint-specific behavior. The `space-y-6` and font sizes work at all screen sizes. `max-w-3xl` for Briefing constrains content width on desktop.

### SummaryGrid

**File:** `src/components/layout/SummaryGrid.tsx`

```tsx
interface SummaryGridProps {
  columns?: 2 | 3 | 4 | 5 | 6;
  children: ReactNode;
  className?: string;
}
```

**DOM structure:**
```
<div className={`grid grid-cols-2 gap-4 ${colsClass} ${className}`}>
  {children}
</div>
```

Where `colsClass` maps:
- 2 → (no additional class, grid-cols-2 is the base)
- 3 → `md:grid-cols-3`
- 4 → `md:grid-cols-4`
- 5 → `md:grid-cols-5`
- 6 → `md:grid-cols-3 lg:grid-cols-6`

**Why `gap-4`:** 14 of 15 pages use `gap-4`. Snapshot uses `gap-3` — that's the outlier being standardized.

### MetricCard

**File:** `src/components/layout/MetricCard.tsx`

```tsx
interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  warning?: boolean;
  trend?: 'up' | 'down' | 'flat';
  onClick?: () => void;
  className?: string;
}
```

**DOM structure:**
```
<div className={`bg-[var(--grey-dim)] rounded-lg p-4 ${onClick ? 'cursor-pointer hover:border-[var(--grey-mid)] transition-colors' : ''} ${className}`}>
  <div className="text-xs text-[var(--grey-muted)] uppercase tracking-wide">{label}</div>
  <div className={`text-2xl font-semibold mt-1 ${warning ? 'text-[var(--warning)]' : 'text-[var(--white)]'}`}>
    {value}
  </div>
  {subtext && (
    <div className="text-xs text-[var(--grey-light)] mt-1 flex items-center gap-1">
      {trend === 'up' && <span className="text-[var(--success)]">↑</span>}
      {trend === 'down' && <span className="text-[var(--danger)]">↓</span>}
      {subtext}
    </div>
  )}
</div>
```

**Why `p-4`:** 13 of 15 pages use `p-4`. Snapshot uses `p-3` — outlier being standardized.

### Index file

**File:** `src/components/layout/index.ts`
```tsx
export { PageLayout } from './PageLayout';
export { SummaryGrid } from './SummaryGrid';
export { MetricCard } from './MetricCard';
```

---

## Section 4: Verification Strategy

### Phase 1 Verification

After Phase 1A (token value update):
1. **Visual smoke test** — Run `pnpm dev` on Mac, open every page. The pages that use CSS tokens (Inbox, Issues, ClientIndex, Team, Snapshot, FixData, TeamDetail, ColdClients, ClientDetailSpec, RecentlyActiveDrilldown) should now render with slate-equivalent colors. The pages that use hardcoded slate (intelligence system) should look identical (no change yet).
2. **Specific check:** Does `body` still render correctly? `index.css` applies `bg-[var(--black)]` which now resolves to `#0f172a` (slate-900). Should match the existing `bg-slate-900` on router.tsx's root div.
3. **TypeScript compile:** `pnpm tsc --noEmit` — should have zero new errors.

After Phase 1B (layout components):
1. **TypeScript compile** — New components must compile.
2. **No visual change yet** — Components are created but not imported by any page.

After Phase 1C (dedup):
1. **Visual smoke test** — Signals, Patterns, Proposals pages should render identically after switching to shared component imports. The shared components are more feature-complete so there may be minor visual improvements (expandable detail on cards, entity links).
2. **Functional test** — Click expand on signal cards, pattern cards, proposal cards. Verify they work.

After Phase 1D (issue styles extraction):
1. **Visual smoke test** — IssueCard and IssueDrawer render identically.
2. **Functional test** — Open an issue drawer, verify all state badges and priority labels display correctly.

### Phase 2 Verification

This is the highest-risk phase (400 replacements across 53 files).

**Strategy: File-by-file verification with TypeScript as gate.**

1. After each batch of files (5-10 at a time):
   - `pnpm tsc --noEmit` — catches any broken className strings
   - Visual spot-check the affected pages

2. **Full page verification after all replacements:**

   | Page | URL | What to check |
   |---|---|---|
   | Inbox | `/` | Metric cards, proposal list, empty states |
   | Issues | `/issues` | Summary cards, issue list, state badges |
   | Clients | `/clients` | Client cards, search bar, empty state |
   | Team | `/team` | Team grid, metric cards |
   | Snapshot | `/snapshot` | 12 metric cards, responsive grid |
   | Fix Data | `/fix-data` | Summary cards, fix data cards |
   | Command Center | `/intel` | Briefing card, signal/pattern/proposal summaries |
   | Briefing | `/intel/briefing` | Narrow layout, briefing sections |
   | Signals | `/intel/signals` | Signal cards, severity badges, expand/collapse |
   | Patterns | `/intel/patterns` | Pattern cards, type badges, entity links |
   | Proposals | `/intel/proposals` | Proposal cards, urgency badges, evidence lists |
   | Client Intel | `/intel/client/:id` | Profile shell, health breakdown, connected entities |
   | Person Intel | `/intel/person/:id` | Profile shell, load distribution, communication chart |
   | Project Intel | `/intel/project/:id` | Profile shell, operational state, health signals |
   | Client Detail | `/clients/:id` | Tabs, detail sections, back navigation |
   | Team Detail | `/team/:id` | Member details, back navigation |
   | Cold Clients | `/clients/cold` | Client list, back navigation |
   | Recently Active | `/clients/recently-active` | Client list, back navigation |

3. **Component-level checks:**
   - Open RoomDrawer (click a room entity) — verify all text, backgrounds, borders
   - Open IssueDrawer (click an issue) — verify state badges, priority, actions
   - Trigger error state (disconnect API) — verify ErrorBoundary, ErrorState
   - Load with slow connection — verify all skeleton animations

4. **Contrast verification:** After migration, `text-[var(--grey-muted)]` (slate-500 = `#64748b`) on `bg-[var(--grey-dim)]` (slate-800 = `#1e293b`) = contrast ratio ~3.7:1. This FAILS WCAG AA for normal text.

   **Decision needed:** Accept 3.7:1 for tertiary text (timestamps, labels) or bump `--grey-muted` to `#94a3b8` (slate-400) for 5.1:1. The plan doc already recommends promoting slate-500 usages to `--grey-light` (slate-400) where the text is meaningful. Apply this judgment per-file: timestamps and decorative labels can stay at `--grey-muted`, but any text the user needs to read should use `--grey-light`.

### Phase 3 Verification

After wrapping pages in PageLayout:
1. **Visual diff per page** — Each page should look nearly identical. The only visible change is standardized vertical rhythm (`space-y-6`) and standardized header typography (`text-2xl font-semibold`).
2. **Check: Back navigation** — TeamDetail, ColdClients, ClientDetailSpec, RecentlyActiveDrilldown all have back links. Verify they render and navigate correctly via PageLayout's `backTo` prop.
3. **Check: Briefing** — Uses `maxWidth="narrow"`. Verify content is constrained to `max-w-3xl`.

After replacing inline metric cards with MetricCard:
1. **Per-page metric check** — Count visible metric cards on each page. Verify values still display. Verify warning states (orange text) still trigger.

### Phase 4 Verification

Accessibility changes — test with keyboard:
1. **Tab through pages** — Every interactive card should receive focus ring
2. **Enter/Space on cards** — Should trigger the same action as click
3. **ESC in drawers** — Both RoomDrawer and IssueDrawer should close
4. **Focus trap in RoomDrawer** — Tab should cycle within drawer, not escape to page behind
5. **Screen reader** — VoiceOver on Mac: expandable cards should announce expanded/collapsed

---

## Section 5: Branch and PR Strategy

### Approach: One branch per phase, sequential PRs

| Phase | Branch | PR Title | Files Changed | Risk |
|---|---|---|---|---|
| 1A | `ui/token-reconciliation` | "Reconcile design tokens to slate palette" | 2 | Medium — changes every tokenized page's appearance |
| 1B | `ui/layout-components` | "Add PageLayout, SummaryGrid, MetricCard components" | 3 new | Low — no existing code changes |
| 1C+1D | `ui/dedup-components` | "Dedup inline components, extract issue styles" | 6 | Medium — refactor with functional impact |
| 2 | `ui/color-migration` | "Migrate all hardcoded slate to design tokens" | 53 | **High** — 400 replacements, every page affected |
| 3 | `ui/layout-adoption` | "Adopt PageLayout and MetricCard across all pages" | 15 | Medium — structural wrapping |
| 4 | `ui/accessibility` | "Add keyboard nav, focus traps, ARIA attributes" | ~10 | Low — additive changes |

**Phase 2 is the dangerous one.** Consider splitting it:
- 2a: Intelligence components (12 files) — these are isolated, easy to verify
- 2b: Intelligence pages (5 files) — depends on 2a
- 2c: Shared components (14 files) — cross-cutting
- 2d: Core pages + router + special cases (10 files) — highest visibility

### Protected file assessment

| File | Protected? | Notes |
|---|---|---|
| `router.tsx` | **Unknown** — protected-files.txt is in the enforcement repo, not locally accessible | Phase 2 changes 6 slate refs. If protected, requires blessing. |
| `tokens.css` | Likely not — it's in `design/` not in any CI-checked path | Phase 1A changes this file |
| `index.css` | Likely not — it's in `time-os-ui/src/` | Phase 1A changes this file |

**Action:** Before starting Phase 2, Molham checks `protected-files.txt` in the enforcement repo for `router.tsx`, `tokens.css`, and `index.css`. If any are protected, we prepare edits and Molham blesses.

### Commit hygiene

- Each phase gets its own PR with `large-change` in the body
- Phase 2 commit message includes "Mechanical replacement: 400 slate → token refs across 53 files"
- Phase 1A commit includes the token value table as context in the body
- All PRs reference this execution spec and `UI_CONSISTENCY_PLAN.md`

---

## Appendix: Files NOT touched by this plan

These files have zero slate references and are already correct:

- `components/ui/Card.tsx` — fully tokenized
- `components/ui/DataGrid.tsx` — fully tokenized
- `components/ui/EmptyState.tsx` — fully tokenized (different from `components/EmptyState.tsx`)
- `components/ConfirmationDialog.tsx` — fully tokenized
- `components/auth/*` — no visual styling
- `components/DegradedModeBanner.tsx` — no slate
- `components/EventStreamSetup.tsx` — no slate
- All test files except `priority.test.ts`
