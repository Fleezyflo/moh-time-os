markdown

# UNIFIED RUN: UI ARCHITECTURE + FEEDBACK LOOPS — 35 Tasks
> Completes Brief 5 (Phase 2–4) + Brief 6 (Phase 0–5)
> **Depends on:** Run 1 COMPLETE ✅ (Foundation + Portfolio Pulse — 10 tasks done)
> **Agent reads:** This file, GUARDRAILS.md, DIRECTIVE.md
> **Sequential execution. One task at a time. Zero patchwork. Zero non-compliant work.**

---

## What Run 1 Already Built (DO NOT REBUILD)

- `tokens.css` — 80+ CSS custom properties (--intel-* namespace)
- 10 atomic components: ScoreBadge, SeverityBadge, TrendIndicator, MetricCell, EntityLink, StatusDot, TimeAgo, LoadingSkeleton, EmptyState, ErrorState
- 4 layout components: PageShell, DenseGrid, Section, CollapsiblePanel
- Navigation: IntelligenceNav, IntelligenceLayout
- API layer: client.js (fetch with cache + mock fallback), hooks.js (useIntelligenceQuery + 9 convenience hooks), types.js, mocks.js
- Signal components: SignalCard, SignalCardCompact, SignalCardList
- Portfolio components: PortfolioVitals, TrajectoryStrip, TrajectoryChip, RecentChanges
- PulsePage wired at /intelligence (index route)
- Placeholder pages at: /intelligence/clients/:id, /intelligence/persons/:id, /intelligence/projects/:id

## Architecture Decisions (Apply to ALL 35 Tasks)

- All new UI code: `time-os-ui/src/intelligence/` — NEVER modify existing dashboard components
- Entity views: `time-os-ui/src/intelligence/views/` — one file per entity type plus section sub-components
- All components share ProfileShell (header, section, connected entities)
- Charts: SVG inline — Sparkline, DimensionBar, BreakdownChart, ActivityHeatmap, DistributionChart, CommunicationChart. NO chart library unless already in deps.
- Entity detail hooks: useClientDetail, usePersonDetail, useProjectDetail with `enabled` guard
- Mock data: cross-consistent (Client Alpha ↔ Sarah Chen ↔ Website Redesign)
- Cross-entity links: EntityLink component, breadcrumb trail via URL search params
- Design tokens exclusively — zero hardcoded color/spacing/font values
- 375px mobile support — no horizontal overflow, 44px min touch targets
- spec_router.py is PROTECTED — do NOT touch
- New backend: `api/feedback_router.py` (Brief 6 only) — separate from intelligence_router.py
- New backend module: `lib/feedback_engine.py` (Brief 6 only)
- Feedback tables: SAME SQLite database (moh_time_os.db)
- Event tracking: fire-and-forget, batched client-side (flush every 30s or on page unload)
- All test suites must pass before AND after every task

---

## MASTER TASK TABLE

| # | Task | Brief | Phase | Depends On |
|---|------|-------|-------|------------|
| **ENTITY VIEWS (Brief 5 Phase 2)** ||||
| 1 | Entity Detail API Hooks & Mock Data | B5 | 2.0 | Run 1 API layer |
| 2 | Profile Shell Component System | B5 | 2.0 | Run 1 components |
| 3 | Chart Primitives (6 SVG components) | B5 | 2.0 | Run 1 tokens |
| 4 | Client Profile — Header + Health Breakdown | B5 | 2.1 | Tasks 1-3 |
| 5 | Client Profile — Communication + Financial + Trajectory | B5 | 2.1 | Task 4 |
| 6 | Person Profile — Full View | B5 | 2.1 | Tasks 2, 3 |
| 7 | Project Profile — Full View | B5 | 2.1 | Tasks 2, 3 |
| 8 | Cross-Entity Navigation & Breadcrumbs | B5 | 2.2 | Tasks 4-7 |
| 9 | Entity View Integration & Polish | B5 | 2.2 | Task 8 |
| 10 | Entity Views Validation | B5 | 2.2 | Task 9 |
| **EVIDENCE & COMPARISON (Brief 5 Phase 3)** ||||
| 11 | Signal Evidence Drawer | B5 | 3.0 | Task 10 |
| 12 | Period Comparison — API Layer + Data Shape | B5 | 3.0 | Task 10 |
| 13 | Period Comparison View | B5 | 3.1 | Task 12 |
| 14 | Cross-Entity Comparison View | B5 | 3.1 | Task 12 |
| 15 | Topology View | B5 | 3.1 | Task 8 |
| **REFINEMENT (Brief 5 Phase 4)** ||||
| 16 | Keyboard Navigation System | B5 | 4.0 | Task 15 |
| 17 | Search & Quick Navigation | B5 | 4.0 | Task 10 |
| 18 | Print/Export View | B5 | 4.0 | Task 10 |
| 19 | Performance Optimization | B5 | 4.1 | Tasks 16-18 |
| 20 | Brief 5 Final Validation | B5 | 4.1 | Task 19 |
| **FEEDBACK FOUNDATION (Brief 6 Phase 0)** ||||
| 21 | Event Schema & Storage Design (APPROVAL GATE) | B6 | 0.0 | Task 20 |
| 22 | Computation Pipeline Design | B6 | 0.0 | Task 21 |
| 23 | Create Feedback Tables | B6 | 0.1 | Task 21 |
| **EVENT COLLECTION (Brief 6 Phase 1)** ||||
| 24 | Event Emitter Module (UI) | B6 | 1.0 | Task 23 |
| 25 | Event Collection API Endpoint | B6 | 1.0 | Task 23 |
| 26 | UI Instrumentation — Portfolio Pulse | B6 | 1.1 | Tasks 24-25 |
| 27 | UI Instrumentation — Entity Views + Session | B6 | 1.1 | Tasks 24-25 |
| **SIGNAL FEEDBACK ANALYSIS (Brief 6 Phase 2)** ||||
| 28 | Signal Utility Computation — Implementation | B6 | 2.0 | Task 27 |
| 29 | Signal Type Report + Per-Entity Relevance | B6 | 2.0 | Task 28 |
| 30 | Feedback Foundation Validation | B6 | 2.1 | Task 29 |
| **THRESHOLD ADAPTATION (Brief 6 Phase 3)** ||||
| 31 | Threshold Adaptation Algorithm + Confidence | B6 | 3.0 | Task 30 |
| 32 | Safety Rails + Threshold Application | B6 | 3.0 | Task 31 |
| **ATTENTION MODEL (Brief 6 Phase 4)** ||||
| 33 | Entity Attention Scoring + Attention-Based Ranking | B6 | 4.0 | Task 30 |
| 34 | Blind Spot Detection + Navigation Patterns | B6 | 4.0 | Task 33 |
| **FEEDBACK TRANSPARENCY (Brief 6 Phase 5)** ||||
| 35 | Calibration Dashboard + Override Controls + Health Indicators + Final Validation | B6 | 5.0 | Tasks 32, 34 |

---

## IMPORTANT: Tasks 1–5 Already Have Detailed Files

The agent should read these FIRST before starting:
- `/home/claude/tasks/TASK_UI_2_1_ENTITY_API_MOCKS.md` → Task 1
- `/home/claude/tasks/TASK_UI_2_2_PROFILE_SHELL.md` → Task 2
- `/home/claude/tasks/TASK_UI_2_3_CHART_PRIMITIVES.md` → Task 3
- `/home/claude/tasks/TASK_UI_2_4_CLIENT_HEADER_HEALTH.md` → Task 4
- `/home/claude/tasks/TASK_UI_2_5_CLIENT_COMM_FIN_TRAJECTORY.md` → Task 5

Those files contain exhaustive step-by-step instructions, code examples, CSS specs, test requirements, and acceptance criteria. Follow them exactly.

**Tasks 6–35 are specified below in this file. Same level of detail.**

---
---
---

# ═══════════════════════════════════════════════════════════════
# TASK 6 of 35: Person Profile — Full View
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 2.1 | Depends On: Tasks 2, 3 | Status: PENDING

## Context
Person profiles show load distribution, blast radius, communication concentration, and trajectory. This is the second entity type, following the pattern established by the client profile. Sarah Chen is the mock person — she has 50 tasks across 5 projects, load_score of 78, and a blast_radius_score of 74.

**Input:**
- ProfileShell, ProfileSection, ConnectedEntities from Task 2
- DistributionChart, Sparkline, CommunicationChart from Task 3
- usePersonDetail hook + MOCK_PERSON_DETAIL from Task 1
- Formatters from Task 4 (formatPercentage, classifyLoad, formatCurrency)
- SeverityBadge, MetricCell, EntityLink, DenseGrid from Run 1

## Objective
Build the PersonProfile view at `/intelligence/persons/:id` with 4 sections: Load Distribution, Blast Radius, Communication, Trajectory. Replace the placeholder route.

## Instructions

### Step 1: Create PersonProfile view

Create `time-os-ui/src/intelligence/views/PersonProfile.jsx`:

```jsx
import React from 'react';
import { useParams } from 'react-router-dom';
import { usePersonDetail } from '../api';
import ProfileShell from '../components/ProfileShell';
import PersonLoadDistribution from './sections/PersonLoadDistribution';
import PersonBlastRadius from './sections/PersonBlastRadius';
import PersonCommunication from './sections/PersonCommunication';
import PersonTrajectory from './sections/PersonTrajectory';
import { formatPercentage, classifyLoad } from '../utils/formatters';

export default function PersonProfile() {
  const { id } = useParams();
  const { data: person, loading, error, refresh } = usePersonDetail(id);
  
  return (
    <ProfileShell
      entityType="person"
      data={person}
      loading={loading}
      error={error}
      onRefresh={refresh}
      mapToHeader={mapPersonToHeader}
      mapToConnected={mapPersonToConnected}
      renderSections={(data) => (
        <>
          
          
          
          
        </>
      )}
    />
  );
}

function mapPersonToHeader(person) {
  const loadClass = classifyLoad(person.load_score);
  return {
    name: person.person_name,
    score: person.load_score,
    classification: loadClass,
    primarySignal: person.active_signals?.[0] || null,
    quickStats: {
      'Role': person.role || '—',
      'Projects': person.load_distribution?.projects?.length || 0,
      'Tasks': person.load_distribution?.total_tasks || 0,
      'Clients': person.connected_clients?.length || 0,
      'Blast Radius': person.blast_radius?.total_blast_radius_score || 0,
    },
    trend: determineTrend(person),
  };
}

function mapPersonToConnected(person) {
  return {
    clients: person.connected_clients || [],
    projects: person.connected_projects || [],
    persons: [],
    invoices: [],
  };
}

function determineTrend(person) {
  const periods = person.trajectory?.periods;
  if (!periods || periods.length < 2) return null;
  const current = periods[periods.length - 1].load_score;
  const previous = periods[periods.length - 2].load_score;
  const delta = current - previous;
  // For load, increasing is BAD (polarity negative)
  if (delta > 2) return { direction: 'increasing', magnitude: Math.abs(delta), polarity: 'negative' };
  if (delta < -2) return { direction: 'declining', magnitude: Math.abs(delta), polarity: 'negative' };
  return { direction: 'stable', magnitude: 0, polarity: 'negative' };
}
```

### Step 2: Build PersonLoadDistribution section

Create `time-os-ui/src/intelligence/views/sections/PersonLoadDistribution.jsx`:

```jsx
/**
 * PersonLoadDistribution — work allocation across projects.
 *
 * Shows:
 * 1. DistributionChart — proportional bar of task share by project
 * 2. Concentration warning — if one project > 60% of load
 * 3. Project breakdown — rows with EntityLink + client name + task count + share %
 *
 * Layout: Distribution bar on top, table below.
 */
```

The distribution chart segments come from `person.load_distribution.projects[]`:
- Each project maps to a segment: `{ label: "${name} (${client_name})", value: task_count }`
- Concentration warning triggers when `load_distribution.concentration_pct > 60`
- Project table rows: EntityLink (project) | client name (text) | task count | share percentage
- Sort projects by task_share_pct descending (highest share first)

### Step 3: Build PersonBlastRadius section

Create `time-os-ui/src/intelligence/views/sections/PersonBlastRadius.jsx`:

```jsx
/**
 * PersonBlastRadius — impact analysis if person becomes unavailable.
 *
 * Shows:
 * 1. Blast radius score (ScoreBadge, inverted — high = risky)
 * 2. Exposed clients grid — EntityLink cards with dependency_score bars
 * 3. Exposed projects grid — EntityLink cards with task_share bars
 *
 * Visual: Two-column grid (clients | projects) on desktop, stacked on mobile.
 */
```

From `person.blast_radius`:
- Hero metric: `total_blast_radius_score` displayed as ScoreBadge (lg)
- Exposed clients: each rendered as a card with EntityLink + DimensionBar showing `dependency_score` (0-100)
- Exposed projects: each rendered as a card with EntityLink + DimensionBar showing `task_share` (0-100)
- Sort both lists by score descending (most exposed first)
- If `total_blast_radius_score > 70`, show SeverityBadge warning

### Step 4: Build PersonCommunication section

Create `time-os-ui/src/intelligence/views/sections/PersonCommunication.jsx`:

Reuse `CommunicationChart` but with person-specific data:
- Channel distribution from `person.communication.by_channel`
- Client distribution: who this person communicates with most (horizontal bars from `person.communication.by_client[]`)
- Concentration score: `person.communication.concentration_score` — warn if > 0.6

### Step 5: Build PersonTrajectory section

Create `time-os-ui/src/intelligence/views/sections/PersonTrajectory.jsx`:

- Main sparkline: `person.trajectory.periods[]` mapped to `{ date, value: load_score }`
- **Polarity is NEGATIVE** — increasing load is bad, so Sparkline gets `polarity="negative"`
- Show direction label: "Load Increasing (+3)" in red, or "Load Decreasing (-5)" in green
- Secondary metric: task count over time as a smaller sparkline below

### Step 6: Wire route — replace placeholder

Replace the person placeholder route with PersonProfile:
```diff
- { path: 'persons/:id', element:  }
+ { path: 'persons/:id', element:  }
```

### Step 7: Add CSS to sections.css

```css
/* ── Person Load Distribution ──────────────────── */
.intel-person-load-warning { /* same pattern as client cost warning */ }
.intel-person-load-table { display: flex; flex-direction: column; gap: var(--intel-space-2); }
.intel-person-load-row {
  display: grid;
  grid-template-columns: 1fr 120px 60px 60px;
  gap: var(--intel-space-2);
  align-items: center;
  padding: var(--intel-space-2) 0;
  border-bottom: 1px solid var(--intel-surface-divider-subtle);
}

/* ── Person Blast Radius ──────────────────── */
.intel-person-blast { display: grid; grid-template-columns: 1fr 1fr; gap: var(--intel-space-6); }
.intel-person-blast__group { }
.intel-person-blast__group-title {
  font-size: var(--intel-font-size-sm);
  font-weight: var(--intel-font-weight-semibold);
  color: var(--intel-text-secondary);
  margin: 0 0 var(--intel-space-3) 0;
}
.intel-person-blast__card {
  padding: var(--intel-space-3);
  background: var(--intel-surface-card);
  border: var(--intel-border-width) solid var(--intel-border-color);
  border-radius: var(--intel-radius-md);
  margin-bottom: var(--intel-space-2);
}

@media (max-width: 768px) {
  .intel-person-blast { grid-template-columns: 1fr; }
  .intel-person-load-row { grid-template-columns: 1fr 80px 50px 50px; }
}
```

### Step 8: Write tests

- PersonProfile renders at `/intelligence/persons/:id` without crash
- Header shows person name, load score, classification (AT_RISK for load_score 78)
- Quick stats show correct values (Role: "Account Lead", Projects: 5, Tasks: 50, etc.)
- PersonLoadDistribution renders DistributionChart with 5 segments
- Concentration warning shows when concentration_pct > 60
- PersonBlastRadius renders exposed clients and projects grids
- Blast radius warning shows when total_blast_radius_score > 70
- PersonCommunication renders channel distribution and client breakdown
- PersonTrajectory uses polarity="negative" for load sparkline
- Route wired: placeholder replaced
- Loading, error, empty states all work

### Step 9: Verify build

```bash
cd ~/clawd/moh-time-os && python3 -m pytest tests/ -q --tb=short
cd time-os-ui && npm run build 2>&1
```

## Acceptance Criteria
- [ ] PersonProfile view at `/intelligence/persons/:id` — fully rendered
- [ ] 4 sections: Load Distribution, Blast Radius, Communication, Trajectory
- [ ] Load polarity inverted (increasing = bad, red)
- [ ] Blast radius warns when score > 70
- [ ] Concentration warnings for both load and communication
- [ ] ConnectedEntities shows clients and projects (not persons)
- [ ] Route replaces placeholder
- [ ] All design tokens, responsive, tests pass

## Output
- `PersonProfile.jsx`, `PersonLoadDistribution.jsx`, `PersonBlastRadius.jsx`, `PersonCommunication.jsx`, `PersonTrajectory.jsx`
- CSS additions to sections.css
- Route update, test additions

---

# ═══════════════════════════════════════════════════════════════
# TASK 7 of 35: Project Profile — Full View
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 2.1 | Depends On: Tasks 2, 3 | Status: PENDING

## Context
Project profiles show operational state, health signals, activity timeline, and dependencies. Website Redesign is the mock project — 45 tasks, 53% complete, health_score 58, 5 overdue, 12 weeks of activity data.

## Objective
Build ProjectProfile view at `/intelligence/projects/:id` with 4 sections: Operational State, Health Signals, Activity Timeline, Dependencies. Replace placeholder route.

## Instructions

### Step 1: Create ProjectProfile view

Create `time-os-ui/src/intelligence/views/ProjectProfile.jsx` following the same pattern as ClientProfile and PersonProfile:
- `useProjectDetail(id)` hook
- `mapToHeader`: name, health_score, classification (classifyScore), status pill, quickStats (Client, Tasks, Completed, Overdue, Completion %, Staleness)
- `mapToConnected`: client (as single-item clients array), persons from team, invoices from dependencies.invoices

### Step 2: Build ProjectOperationalState section

Create `time-os-ui/src/intelligence/views/sections/ProjectOperationalState.jsx`:

**Metrics grid (DenseGrid, 3 columns):**
- Total Tasks / Completed / Overdue / In Progress / Completion % / Avg Task Age / Staleness Days
- Each rendered as MetricCell
- Overdue gets trend indicator with negative polarity if > 0
- Staleness gets warning if > 7 days

**Team list below metrics:**
- Each team member: EntityLink (person) + task count + role badge
- Sort by task_count descending

### Step 3: Build ProjectHealthSignals section

Create `time-os-ui/src/intelligence/views/sections/ProjectHealthSignals.jsx`:

- SignalCardList in compact mode showing `project.active_signals`
- If no signals: EmptyState "No active signals for this project"

### Step 4: Build ProjectActivityTimeline section

Create `time-os-ui/src/intelligence/views/sections/ProjectActivityTimeline.jsx`:

Uses ActivityHeatmap from Task 3:
- Map `project.activity_timeline.weeks[]` to `{ week_start, activity_level: task_created + task_completed + communications }`
- Show 12 weeks of data
- Below heatmap: two mini sparklines:
  - Tasks created per week (Sparkline, polarity="neutral")
  - Tasks completed per week (Sparkline, polarity="positive")

### Step 5: Build ProjectDependencies section

Create `time-os-ui/src/intelligence/views/sections/ProjectDependencies.jsx`:

- Client link: single EntityLink card for `project.dependencies.client`
- Team members: list from `project.dependencies.persons[]` with EntityLink + task count
- Invoices: list from `project.dependencies.invoices[]` with amount, status badge, date

### Step 6: Wire route, CSS, tests

Same pattern as Person profile. Replace placeholder. Add CSS to sections.css. Write tests for all 4 sections.

## Acceptance Criteria
- [ ] ProjectProfile view at `/intelligence/projects/:id`
- [ ] 4 sections: Operational State, Health Signals, Activity Timeline, Dependencies
- [ ] Metrics grid with 7 operational metrics
- [ ] Team list sorted by task count
- [ ] Activity heatmap with 12 weeks + mini sparklines
- [ ] Route replaces placeholder, tests pass, responsive

---

# ═══════════════════════════════════════════════════════════════
# TASK 8 of 35: Cross-Entity Navigation & Breadcrumbs
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 2.2 | Depends On: Tasks 4-7 | Status: PENDING

## Context
Entity views must cross-link bidirectionally. Clicking Sarah Chen in Client Alpha's profile navigates to Sarah Chen's Person profile. Clicking Client Alpha in Sarah Chen's profile navigates back. A breadcrumb trail tracks the drill-down path.

## Objective
Build BreadcrumbTrail component, NavigationContext for tracking drill-down paths, and integrate breadcrumbs into all entity profile views.

## Instructions

### Step 1: Build BreadcrumbTrail component

Create `time-os-ui/src/intelligence/components/BreadcrumbTrail.jsx`:

```jsx
/**
 * BreadcrumbTrail — shows navigation path: Portfolio Pulse > Client Alpha > Sarah Chen
 *
 * Reads breadcrumb state from URL search params: ?from=client:12,person:5
 * Each crumb is clickable (navigates back to that entity).
 * Home crumb always present: "Portfolio Pulse" → /intelligence
 *
 * VISUAL: Horizontal row, separated by " › ", truncated on mobile.
 * STYLING: --intel-font-size-xs, --intel-text-tertiary, current item --intel-text-primary
 */
```

URL param format: `?from=client:12:Client+Alpha,person:5:Sarah+Chen`
- Parse on mount: split by comma, each segment is `type:id:name`
- Each crumb renders as a link to `/intelligence/${type}s/${id}?from=...` (preserving the path UP TO that crumb)
- Current page is the last crumb (not clickable, bold)

### Step 2: Build useBreadcrumbs hook

Create `time-os-ui/src/intelligence/hooks/useBreadcrumbs.js`:

```javascript
/**
 * useBreadcrumbs — manages breadcrumb state via URL search params.
 *
 * Returns:
 * - crumbs: Array
 * - pushCrumb(type, id, name): adds current entity to breadcrumb trail
 * - buildEntityPath(type, id, name): returns path with updated breadcrumbs
 *
 * Used by EntityLink to build navigation URLs with breadcrumb context.
 */
```

### Step 3: Integrate into EntityLink

Modify the EntityLink component from Run 1:
- When EntityLink generates its `<a href>`, include the current breadcrumb trail as `?from=...`
- This ensures every cross-entity navigation preserves and extends the trail

### Step 4: Integrate BreadcrumbTrail into ProfileShell

Add BreadcrumbTrail to the top of ProfileShell, above the ProfileHeader:
```jsx


```

### Step 5: Add back navigation

- Browser back button works naturally (URL-based breadcrumbs)
- Add a "← Back" button in ProfileHeader actions that navigates to the previous crumb
- Keyboard: Escape key navigates back one level

### Step 6: CSS, tests

```css
.intel-breadcrumb-trail {
  display: flex;
  align-items: center;
  gap: var(--intel-space-1);
  padding: var(--intel-space-2) 0;
  font-size: var(--intel-font-size-xs);
  overflow-x: auto;
  white-space: nowrap;
}
.intel-breadcrumb-trail__crumb { color: var(--intel-text-tertiary); }
.intel-breadcrumb-trail__crumb:hover { color: var(--intel-text-link); }
.intel-breadcrumb-trail__separator { color: var(--intel-text-tertiary); }
.intel-breadcrumb-trail__current { color: var(--intel-text-primary); font-weight: var(--intel-font-weight-medium); }
```

Tests:
- BreadcrumbTrail parses URL params correctly
- Home crumb always present
- Clicking a crumb navigates to correct path
- EntityLink builds URLs with breadcrumb params
- Back button navigates to previous crumb

## Acceptance Criteria
- [ ] BreadcrumbTrail renders: Portfolio Pulse › Client Alpha › Sarah Chen
- [ ] URL-param backed (bookmarkable, browser back works)
- [ ] EntityLink preserves and extends breadcrumb trail
- [ ] Back button + Escape key navigate up one level
- [ ] Integrated into all 3 entity profile views via ProfileShell
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 9 of 35: Entity View Integration & Polish
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 2.2 | Depends On: Task 8 | Status: PENDING

## Objective
End-to-end verification and polish of all entity views. Fix edge cases, ensure consistency.

## Instructions

### Step 1: Route verification
- Navigate to `/intelligence/clients/12` → ClientProfile renders
- Navigate to `/intelligence/persons/5` → PersonProfile renders
- Navigate to `/intelligence/projects/101` → ProjectProfile renders
- Navigate to `/intelligence/clients/999` → Error state (entity not found)

### Step 2: Cross-link testing
- From Client Alpha → click Sarah Chen → PersonProfile loads with breadcrumb "Portfolio Pulse › Client Alpha › Sarah Chen"
- From Sarah Chen → click Website Redesign → ProjectProfile loads with full breadcrumb trail
- From Website Redesign → click Client Alpha → navigates back with breadcrumb

### Step 3: Edge cases
- Missing entity (ID doesn't match any mock): ErrorState with "Entity not found" and retry button
- Empty sections (client with no signals, person with no blast radius data): EmptyState per section, NOT full-page empty
- Null/undefined data fields: all formatters handle null gracefully (return "—")

### Step 4: Mobile responsiveness (375px)
- All 3 profiles render without horizontal overflow at 375px
- Touch targets: all clickable elements ≥ 44px
- Stacked layouts on mobile (grids → single column)

### Step 5: Loading state consistency
- Every section shows its own skeleton while loading
- Profile header skeleton matches the real header layout
- No layout shift when data arrives

### Step 6: Verify design token compliance
```bash
# Check for any hardcoded colors, font sizes, or spacing
grep -rn "px\|#[0-9a-fA-F]\{3,6\}\|rgb\|rgba" time-os-ui/src/intelligence/views/ --include="*.css" | grep -v "var(--"
grep -rn "px\|#[0-9a-fA-F]\{3,6\}\|rgb\|rgba" time-os-ui/src/intelligence/components/profile.css | grep -v "var(--"
```
Any hardcoded values found must be replaced with design tokens.

## Acceptance Criteria
- [ ] All 3 entity routes render correctly
- [ ] Cross-entity navigation works bidirectionally with breadcrumbs
- [ ] Error, empty, loading states work per-section
- [ ] 375px mobile: no overflow, touch-friendly
- [ ] Zero hardcoded style values
- [ ] All tests pass, frontend builds

---

# ═══════════════════════════════════════════════════════════════
# TASK 10 of 35: Entity Views Validation
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 2.2 | Depends On: Task 9 | Status: PENDING

## Objective
Final validation checkpoint for Brief 5 Phase 2. Full inventory, test suite, heartbeat update.

## Instructions

### Step 1: Component inventory
List every new component created in Tasks 1-9:
- API layer additions (types, mocks, hooks)
- Profile components (ProfileHeader, ProfileSection, ConnectedEntities, ProfileShell)
- Chart components (Sparkline, DimensionBar, BreakdownChart, ActivityHeatmap, DistributionChart, CommunicationChart)
- View components (ClientProfile, PersonProfile, ProjectProfile + all section sub-components)
- Navigation components (BreadcrumbTrail, useBreadcrumbs)
- Utilities (formatters.js)

### Step 2: Run full test suite
```bash
cd ~/clawd/moh-time-os && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30
cd time-os-ui && npm run build 2>&1
cd time-os-ui && npm test 2>&1 || npx vitest run 2>&1 || echo "Frontend tests complete"
```

### Step 3: Verify Brief 5 Phase 2 success criteria
- [ ] All 3 entity profiles complete with all data sections
- [ ] Cross-entity navigation with breadcrumbs
- [ ] All routes replace placeholders
- [ ] 375px responsive
- [ ] Loading/error/empty states everywhere
- [ ] No regressions

### Step 4: Update HEARTBEAT
Record Phase 2 completion status, component count, any blocked items.

## Acceptance Criteria
- [ ] Complete component inventory documented
- [ ] All tests pass (backend + frontend)
- [ ] Brief 5 Phase 2 success criteria verified
- [ ] HEARTBEAT updated

---

# ═══════════════════════════════════════════════════════════════
# TASK 11 of 35: Signal Evidence Drawer
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 3.0 | Depends On: Task 10 | Status: PENDING

## Context
When Moh clicks "View Details →" on a signal card, an evidence drawer slides in from the right showing: raw data points, timeline of signal evolution, related signals on the same entity, and action context.

## Objective
Build EvidenceDrawer component, add SignalEvidence type + mock data + useSignalEvidence hook, integrate into PulsePage.

## Instructions

### Step 1: Define evidence data shape

Add to `api/types.js`:
```javascript
/**
 * @typedef {Object} SignalEvidence
 * @property {string} signal_id
 * @property {string} signal_type
 * @property {string} entity_type
 * @property {number} entity_id
 * @property {string} entity_name
 * @property {Array} data_points — raw evidence
 * @property {Array} timeline — signal evolution history
 * @property {Array} related_signals — other signals on same entity
 * @property {string} context_summary — human-readable analysis of what happened
 */
```

### Step 2: Add mock evidence data

Add to `api/mocks.js`:
```javascript
const MOCK_SIGNAL_EVIDENCE = {
  signal_id: 'sig_001',
  signal_type: 'communication_declining',
  entity_type: 'client', entity_id: 12, entity_name: 'Client Alpha',
  data_points: [
    { label: 'Emails sent (weekly avg)', value: '23 → 12', date: '2025-02-01', direction: 'declining' },
    { label: 'Chat messages', value: '0 in 14 days', date: '2025-02-08', direction: 'declining' },
    { label: 'Last meeting', value: 'Jan 20 (25 days ago)', date: '2025-01-20', direction: 'stale' },
    { label: 'Response time (avg)', value: '4h → 18h', date: '2025-02-01', direction: 'declining' },
  ],
  timeline: [
    { date: '2025-01-15', event: 'Signal detected', detail: 'Communication volume dropped below 60% of 90-day average' },
    { date: '2025-01-22', event: 'Escalated to critical', detail: 'No chat messages for 7 days + email volume at 40% of average' },
    { date: '2025-02-03', event: 'Gap detected', detail: '14-day communication gap identified' },
  ],
  related_signals: [
    { id: 'sig_015', signal_type: 'task_staleness', severity: 'warning', entity_type: 'client', entity_id: 12, entity_name: 'Client Alpha', headline: '3 tasks stale for over 14 days', trend: { direction: 'increasing', magnitude: 15, polarity: 'negative' }, first_detected: '2025-01-28T10:30:00Z' },
  ],
  context_summary: 'Client Alpha outbound communication has declined 45% over 8 weeks while active task count remains unchanged. This pattern typically precedes client disengagement. The last meeting was 25 days ago despite a normal weekly cadence. Combined with 3 stale tasks, this suggests the relationship needs immediate attention.',
};
```

### Step 3: Add useSignalEvidence hook + mock lookup

```javascript
export function useSignalEvidence(signalId) {
  return useIntelligenceQuery(`/signals/${signalId}/evidence`, {}, { enabled: signalId != null });
}
```

Add to getMockData: `/signals/${id}/evidence` → returns MOCK_SIGNAL_EVIDENCE (with signal_id override).

### Step 4: Build EvidenceDrawer component

Create `time-os-ui/src/intelligence/components/EvidenceDrawer.jsx`:

**Visual structure:**
```
┌──────────────────────────────── Right panel, 400px wide ──┐
│ ✕ Close                            Signal Type Badge       │
│ ─────────────────────────────────────────────────────────  │
│ Entity Name (EntityLink)                                   │
│ Signal headline                                            │
│                                                            │
│ ── Data Points ──────────────────────────────────────────  │
│ Label: value                                    [direction] │
│ Label: value                                    [direction] │
│ Label: value                                    [direction] │
│                                                            │
│ ── Timeline ─────────────────────────────────────────────  │
│ ● Jan 15  Signal detected                                  │
│ ● Jan 22  Escalated to critical                            │
│ ● Feb 03  Gap detected                                     │
│                                                            │
│ ── Context ──────────────────────────────────────────────  │
│ Analysis paragraph...                                      │
│                                                            │
│ ── Related Signals ──────────────────────────────────────  │
│ [SignalCardCompact] task_staleness                          │
│                                                            │
│ [Navigate to Entity →]                                     │
└────────────────────────────────────────────────────────────┘
```

- Slides in from right with transition (transform: translateX)
- Backdrop: semi-transparent overlay
- Close: ✕ button + Escape key + clicking backdrop
- Loading: skeleton while evidence loads
- Error: ErrorState with retry
- CSS: All design tokens. `position: fixed; right: 0; top: 0; height: 100vh; width: 400px; max-width: 90vw;`

### Step 5: Integrate into PulsePage

When `onSignalDrilldown` is called on PulsePage:
1. Set `evidenceSignalId` state
2. Render `<EvidenceDrawer signalId={evidenceSignalId} onClose={() => setEvidenceSignalId(null)} />`
3. Also integrate into entity profile views (signal cards in ClientHealthBreakdown, etc.)

### Step 6: CSS, tests

Evidence drawer CSS: overlay, panel, slide animation, data points list, timeline, responsive (full-width on mobile).

Tests: renders with mock data, close button works, Escape closes, shows loading state, shows data points and timeline, handles error, related signals render as compact cards.

## Acceptance Criteria
- [ ] EvidenceDrawer slides from right, shows data points + timeline + context + related signals
- [ ] Integrated into PulsePage and entity profile views
- [ ] Close: ✕ button, Escape, backdrop click
- [ ] Loading/error states
- [ ] Mobile: full-width panel
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 12 of 35: Period Comparison — API Layer + Data Shape
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 3.0 | Depends On: Task 10 | Status: PENDING

## Objective
Define PeriodComparison and CrossEntityComparison types, add mock data, create hooks. This is the data layer for Tasks 13-14.

## Instructions

### Step 1: Define types

```javascript
/**
 * @typedef {Object} PeriodComparison
 * @property {string} entity_type
 * @property {number} entity_id
 * @property {string} entity_name
 * @property {{start: string, end: string}} period_a
 * @property {{start: string, end: string}} period_b
 * @property {Array} metrics
 */

/**
 * @typedef {Object} ComparisonMetric
 * @property {string} category — 'communication'|'financial'|'operational'|'health'
 * @property {string} label — 'Total emails sent'
 * @property {number} value_a — value in period A
 * @property {number} value_b — value in period B
 * @property {number} delta — value_b - value_a
 * @property {number} delta_pct — percentage change
 * @property {'increasing'|'declining'|'stable'} direction
 * @property {'positive'|'negative'|'neutral'} polarity — is this change good or bad?
 */

/**
 * @typedef {Object} CrossEntityComparison
 * @property {string} entity_type
 * @property {Array}>} entities
 * @property {Array} metric_keys — ordered list of metric names
 */
```

### Step 2: Build comprehensive mock data

PeriodComparison mock: Client Alpha, Jan vs Feb, 12+ metrics across 4 categories.
CrossEntityComparison mock: 4 clients compared on 8 metrics.

### Step 3: Add hooks

```javascript
export function usePeriodComparison(entityType, entityId, periodA, periodB) { ... }
export function useCrossEntityComparison(entityType, entityIds) { ... }
```

### Step 4: Tests, verify build

## Acceptance Criteria
- [ ] Types defined for PeriodComparison and CrossEntityComparison
- [ ] Mock data: 12+ metrics for period comparison, 4 entities × 8 metrics for cross-entity
- [ ] Hooks with enabled guard
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 13 of 35: Period Comparison View
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 3.1 | Depends On: Task 12 | Status: PENDING

## Objective
Build PeriodComparisonView at `/intelligence/compare/periods/:type/:id`. Shows metrics from two time periods side-by-side with colored deltas.

## Instructions

### Step 1: Build PeriodSelector component
- Preset buttons: "This Month vs Last", "This Quarter vs Last", "Custom"
- Custom: two date inputs
- Renders above the comparison table

### Step 2: Build ComparisonMetricRow
- Label | Period A value | Period B value | Delta (colored: green=improvement, red=degradation) | Delta % | Arrow icon
- Grouped by category with section headers

### Step 3: Build PeriodComparisonView page
- Uses PeriodSelector + ComparisonMetricRow rows
- Route: `/intelligence/compare/periods/:type/:id`
- Accessible via "Compare Periods" button in ProfileHeader actions

### Step 4: CSS, tests, route

## Acceptance Criteria
- [ ] Period selector with presets + custom dates
- [ ] Metrics table with colored deltas
- [ ] Grouped by category
- [ ] Route wired, responsive, tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 14 of 35: Cross-Entity Comparison View
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 3.1 | Depends On: Task 12 | Status: PENDING

## Objective
Build CrossEntityComparisonView at `/intelligence/compare/entities`. Multi-entity comparison table: entities as columns, metrics as rows. Sortable, outlier highlighting.

## Instructions

### Step 1: Build EntityMultiSelector — checkbox list of entities (2-8 selection), search filter
### Step 2: Build ComparisonTable — entities as columns, metrics as rows, sortable by any column, outlier cells highlighted (>1.5 std dev from mean)
### Step 3: Wire route, CSS, tests

## Acceptance Criteria
- [ ] Entity selector for 2-8 entities of same type
- [ ] Table with sortable columns, outlier highlighting
- [ ] Route wired, responsive, tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 15 of 35: Topology View
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 3.1 | Depends On: Task 8 | Status: PENDING

## Objective
Build TopologyView — visual relationship map for any entity. Center node = selected entity, connected nodes = related entities, edge thickness = relationship strength, node color = health state.

## Instructions

### Step 1: Define TopologyData type and mock
```javascript
/**
 * @typedef {Object} TopologyData
 * @property {{type: string, id: number, name: string, score: number}} center
 * @property {Array} nodes
 * @property {Array} edges
 */
```

### Step 2: Build TopologyView component
**Implementation decision tree:**
- If D3 is already in project deps → use D3 force layout
- If not → SVG radial layout (center node in middle, connected nodes in a circle)
- Nodes: colored circles (health-based color from design tokens), labeled
- Edges: lines with thickness proportional to weight
- Nodes are clickable → navigate to that entity's profile
- Pan/zoom: CSS transform (no extra deps)

### Step 3: Integrate into entity profiles
Add "View Topology" button to ProfileHeader actions. Opens TopologyView as a full-screen overlay or navigates to `/intelligence/topology/:type/:id`.

### Step 4: CSS, tests

## Acceptance Criteria
- [ ] Center node + connected nodes rendered as SVG
- [ ] Node colors reflect health state
- [ ] Edge thickness reflects relationship strength
- [ ] Nodes clickable → navigate to entity
- [ ] Integrated into entity profile actions
- [ ] Responsive, tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 16 of 35: Keyboard Navigation System
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 4.0 | Depends On: Task 15 | Status: PENDING

## Objective
Global keyboard shortcuts for power-user navigation.

## Instructions

### Step 1: Build KeyboardShortcuts provider
Wrap the intelligence layout with a context provider that listens for global keydown events.

Shortcuts:
- `j` / `k`: Move focus between signal cards (next/previous)
- `Enter`: Expand focused signal or navigate to focused entity
- `Escape`: Close drawer/modal, or navigate back one breadcrumb level
- `d`: Dismiss focused signal
- `e`: Open evidence drawer for focused signal
- `c`: Open comparison view for current entity
- `t`: Open topology view for current entity
- `/` or `Ctrl+K`: Open search palette
- `?`: Toggle shortcut help overlay

### Step 2: Build ShortcutHelp overlay
Simple modal listing all shortcuts with descriptions. Toggled by `?` key.

### Step 3: Focus management
- SignalCardList: track focused index, apply `.intel-signal-card--focused` class
- j/k increment/decrement focused index
- Ensure focus ring is visible (design token border)

### Step 4: CSS, tests

## Acceptance Criteria
- [ ] All shortcuts functional
- [ ] Help overlay shows on `?`
- [ ] Focus management on signal card list
- [ ] No conflicts with browser shortcuts
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 17 of 35: Search & Quick Navigation
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 4.0 | Depends On: Task 10 | Status: PENDING

## Objective
Global search palette (command palette pattern) — Ctrl/Cmd+K or `/`. Search clients, persons, projects by name. Jump to any entity.

## Instructions

### Step 1: Build SearchPalette component
- Activated by Ctrl/Cmd+K, `/`, or clicking search icon
- Input field with auto-focus
- Fuzzy search across all entity names (from client/person scores data)
- Results grouped by type (Clients, People, Projects)
- Arrow key navigation through results
- Enter navigates to selected entity
- Escape closes
- Debounced 200ms

### Step 2: Build search data source
Use existing hooks (useClientScores, usePersonScores) to build a search index.
```javascript
function useSearchIndex() {
  const clients = useClientScores();
  const persons = usePersonScores();
  // Combine into searchable array: [{type, id, name, score}]
}
```

### Step 3: Recent searches
Store last 5 searches in React state (in-memory only, resets on page refresh).

### Step 4: Integrate into IntelligenceNav
Add search icon button to the nav bar. Render SearchPalette as a portal overlay.

### Step 5: CSS, tests

## Acceptance Criteria
- [ ] Search palette opens on Ctrl/Cmd+K or /
- [ ] Fuzzy search across all entity types
- [ ] Arrow key navigation, Enter to select
- [ ] Results grouped by type
- [ ] Recent searches shown when input is empty
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 18 of 35: Print/Export View
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 4.0 | Depends On: Task 10 | Status: PENDING

## Objective
Print stylesheet + export button for entity profiles.

## Instructions

### Step 1: Print stylesheet
Add `@media print` rules:
- Hide: nav bar, action buttons, keyboard shortcut help, breadcrumb trail links, dismiss buttons
- Show: all sections expanded (no collapsed panels)
- Colors: preserve severity colors (use `color-adjust: exact`)
- Page breaks: between sections
- Font: use system font stack for print

### Step 2: ExportButton component
Button in ProfileHeader actions: "Export" → triggers `window.print()`
Include "Generated on {date}" footer in print view.

### Step 3: Integrate, test

## Acceptance Criteria
- [ ] Print stylesheet hides interactive elements, preserves data
- [ ] ExportButton triggers browser print dialog
- [ ] Page breaks between sections
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 19 of 35: Performance Optimization
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 4.1 | Depends On: Tasks 16-18 | Status: PENDING

## Objective
Optimize load times, bundle size, and rendering performance.

## Instructions

### Step 1: Lazy-load entity views
```javascript
const ClientProfile = React.lazy(() => import('./views/ClientProfile'));
const PersonProfile = React.lazy(() => import('./views/PersonProfile'));
const ProjectProfile = React.lazy(() => import('./views/ProjectProfile'));
// Wrap routes in }>
```

### Step 2: Virtualize long lists
If signal list has >50 items, use windowing (implement simple virtual scroll or use existing dep if available).

### Step 3: API cache tuning
- Entity details: 5-minute TTL
- Evidence/comparison: 10-minute TTL
- Briefing/signals: 2-minute TTL
- Add `cache-bust` option to refresh button

### Step 4: EntityLink prefetch on hover
On mouseenter of EntityLink, prefetch entity detail data (fire useIntelligenceQuery with the entity path — populates cache).

### Step 5: Performance logging
Add `console.time` / `console.timeEnd` for:
- Page mount → first meaningful paint
- API response times
- Route transition times
Log in development only (`if (import.meta.env.DEV)`).

### Step 6: Bundle size check
```bash
cd time-os-ui && npm run build 2>&1 | grep -i "size\|chunk\|bundle"
```
Document total bundle size. Flag if intelligence chunk > 200KB.

## Acceptance Criteria
- [ ] Entity views lazy-loaded
- [ ] Long lists virtualized
- [ ] Cache TTLs configured
- [ ] Hover prefetch on EntityLink
- [ ] Performance logging in dev mode
- [ ] Bundle size documented

---

# ═══════════════════════════════════════════════════════════════
# TASK 20 of 35: Brief 5 Final Validation
# ═══════════════════════════════════════════════════════════════
> Brief: B5 | Phase: 4.1 | Depends On: Task 19 | Status: PENDING

## Objective
Complete validation of Brief 5 — UI Architecture. Every feature verified against the brief's success criteria.

## Instructions

### Step 1: Verify Brief 5 success criteria

- [ ] Portfolio Pulse landing page shows signals, vitals, and trajectories
- [ ] All three entity types have profile views with full data
- [ ] Cross-entity navigation works (client → person → project → back)
- [ ] Signal evidence is viewable for any active signal
- [ ] Period comparison works for any entity
- [ ] Cross-entity comparison works
- [ ] Topology view renders for any entity
- [ ] Keyboard navigation works on portfolio view
- [ ] Search works across all entity types
- [ ] All views load in <2 seconds with mock data
- [ ] No regressions to existing UI functionality
- [ ] Full test suite passes

### Step 2: Full test suite
```bash
cd ~/clawd/moh-time-os && python3 -m pytest tests/ -v --tb=short 2>&1
cd time-os-ui && npm run build 2>&1
```

### Step 3: Update HEARTBEAT — Brief 5 COMPLETE

## Acceptance Criteria
- [ ] All Brief 5 success criteria verified
- [ ] All tests pass
- [ ] HEARTBEAT updated: Brief 5 COMPLETE

---
---
---

# ═══════════════════════════════════════════════════════════════
# BRIEF 6 — FEEDBACK LOOPS
# ═══════════════════════════════════════════════════════════════

---

# ═══════════════════════════════════════════════════════════════
# TASK 21 of 35: Event Schema & Storage Design (APPROVAL GATE)
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 0.0 | Depends On: Task 20 | Status: PENDING

## Context
This is an APPROVAL GATE task. The agent designs the schema, documents it, and presents it for approval. No tables are created until approval.

## Objective
Design the complete feedback data model: interaction_events table, 5 derived metric tables, indexes, retention policy, storage estimates.

## Instructions

### Step 1: Audit existing database
```bash
cd ~/clawd/moh-time-os
python3 -c "
import sqlite3
conn = sqlite3.connect('moh_time_os.db')
tables = [t[0] for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print(f'Total tables: {len(tables)}')
for t in sorted(tables):
    count = conn.execute(f'SELECT COUNT(*) FROM [{t}]').fetchone()[0]
    print(f'  {t}: {count} rows')
" 2>&1 | head -50
```

Verify no existing tables conflict with proposed names: interaction_events, signal_utility_scores, entity_attention_scores, threshold_calibration_log, session_summaries, interaction_events_weekly.

### Step 2: Design interaction_events table

```sql
CREATE TABLE IF NOT EXISTS interaction_events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'moh',
    event_type TEXT NOT NULL CHECK(event_type IN (
        'page_view', 'signal_seen', 'signal_dismissed', 'signal_drilldown',
        'entity_drilldown', 'entity_frequent', 'comparison_viewed',
        'topology_viewed', 'search_performed', 'session_start',
        'session_end', 'export_performed', 'heartbeat'
    )),
    entity_type TEXT,
    entity_id INTEGER,
    signal_id TEXT,
    signal_type TEXT,
    context TEXT, -- JSON blob
    session_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON interaction_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON interaction_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_entity ON interaction_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_events_signal ON interaction_events(signal_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON interaction_events(session_id);
```

### Step 3: Design derived metric tables

```sql
CREATE TABLE IF NOT EXISTS signal_utility_scores (
    signal_type TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    lookback_days INTEGER NOT NULL DEFAULT 30,
    total_seen INTEGER NOT NULL DEFAULT 0,
    total_dismissed INTEGER NOT NULL DEFAULT 0,
    total_investigated INTEGER NOT NULL DEFAULT 0,
    total_ignored INTEGER NOT NULL DEFAULT 0,
    action_rate REAL,
    dismiss_rate REAL,
    ignore_rate REAL,
    avg_time_to_action_seconds REAL,
    utility_classification TEXT CHECK(utility_classification IN ('HIGH_UTILITY', 'MODERATE', 'LOW_UTILITY', 'NOISE')),
    PRIMARY KEY (signal_type, computed_at)
);

CREATE TABLE IF NOT EXISTS entity_attention_scores (
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    computed_at TEXT NOT NULL,
    lookback_days INTEGER NOT NULL DEFAULT 14,
    visit_frequency REAL,
    visit_depth REAL,
    unprompted_ratio REAL,
    recency_weight REAL,
    attention_score REAL,
    PRIMARY KEY (entity_type, entity_id, computed_at)
);

CREATE TABLE IF NOT EXISTS threshold_calibration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    old_threshold REAL,
    new_threshold REAL,
    direction TEXT CHECK(direction IN ('tightened', 'loosened', 'reset')),
    confidence TEXT CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    reason TEXT,
    source TEXT CHECK(source IN ('auto_calibration', 'manual_override')),
    data_points INTEGER
);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'moh',
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_seconds INTEGER,
    event_count INTEGER,
    pages_viewed INTEGER,
    signals_seen INTEGER,
    signals_dismissed INTEGER,
    signals_investigated INTEGER,
    entities_drilled INTEGER,
    first_action TEXT,
    navigation_sequence TEXT -- JSON array
);

CREATE TABLE IF NOT EXISTS interaction_events_weekly (
    week_start TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    event_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (week_start, event_type, entity_type, entity_id)
);
```

### Step 4: Design retention policy
- Raw events: keep 6 months
- Weekly aggregates: keep indefinitely
- Archive job: monthly, aggregates events older than 6 months into interaction_events_weekly, then deletes raw events

### Step 5: Storage estimate
~800 events/day × 180 days × ~500 bytes = ~72MB raw events. With indexes: ~145MB total. Trivial for SQLite.

### Step 6: Write design document
Create `data/feedback_schema_design_YYYYMMDD.md` with all CREATE TABLE statements, indexes, retention logic, storage estimates, event type descriptions.

### Step 7: Verify no GUARDRAILS violations
- No modifications to existing tables
- No changes to spec_router.py
- New tables only

## Acceptance Criteria
- [ ] Design document created with full schema
- [ ] No conflicts with existing tables verified
- [ ] 6 new tables designed with appropriate indexes
- [ ] Retention policy documented
- [ ] Storage estimate calculated
- [ ] GUARDRAILS compliance verified

---

# ═══════════════════════════════════════════════════════════════
# TASK 22 of 35: Computation Pipeline Design
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 0.0 | Depends On: Task 21 | Status: PENDING

## Objective
Create `lib/feedback_engine.py` skeleton with function signatures, docstrings, computation schedule, and test cases — NO implementation yet.

## Instructions

### Step 1: Create lib/feedback_engine.py skeleton

All functions with complete docstrings, type hints, parameter documentation, return type documentation. Function bodies are `pass` or raise `NotImplementedError`.

Functions:
- `compute_signal_utility(lookback_days=30) -> list[dict]`
- `classify_signal_utility(action_rate, dismiss_rate, ignore_rate) -> str`
- `store_signal_utility(results: list[dict]) -> None`
- `compute_entity_attention(lookback_days=14) -> list[dict]`
- `store_entity_attention(results: list[dict]) -> None`
- `summarize_sessions() -> list[dict]`
- `compute_entity_signal_relevance(entity_type, entity_id) -> dict`
- `generate_signal_utility_report() -> dict`
- `propose_threshold_adjustments(min_data_points=20) -> list[dict]`
- `apply_threshold_adjustment(signal_type, new_threshold, source='auto_calibration') -> bool`
- `detect_blind_spots(lookback_days=30) -> list[dict]`
- `compute_navigation_patterns(lookback_days=30) -> dict`
- `run_daily_feedback_computation() -> dict`
- `archive_old_events(retention_days=180) -> int`

### Step 2: Document computation schedule
- Daily 3:00 AM: compute_signal_utility, compute_entity_attention, summarize_sessions, propose_threshold_adjustments
- Monthly 1st 4:00 AM: archive_old_events, generate_signal_utility_report

### Step 3: Write test stubs
Create `tests/test_feedback_engine.py` with test function stubs (no implementation, just names and docstrings).

## Acceptance Criteria
- [ ] feedback_engine.py created with 14 function signatures + docstrings
- [ ] Computation schedule documented
- [ ] Test stubs created
- [ ] Imports work, file loads without errors

---

# ═══════════════════════════════════════════════════════════════
# TASK 23 of 35: Create Feedback Tables
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 0.1 | Depends On: Task 21 | Status: PENDING

## Objective
Execute all CREATE TABLE and CREATE INDEX statements from Task 21's design. Verify tables exist. Run existing test suite to confirm no regressions.

## Instructions

### Step 1: Create migration script
Create `data/migrations/create_feedback_tables.py`:
- Connect to moh_time_os.db
- Execute all 6 CREATE TABLE IF NOT EXISTS statements
- Execute all CREATE INDEX IF NOT EXISTS statements
- Verify each table exists after creation
- Print summary

### Step 2: Run migration
```bash
cd ~/clawd/moh-time-os && python3 data/migrations/create_feedback_tables.py
```

### Step 3: Verify tables
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('moh_time_os.db')
for table in ['interaction_events', 'signal_utility_scores', 'entity_attention_scores', 'threshold_calibration_log', 'session_summaries', 'interaction_events_weekly']:
    exists = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name=?\", (table,)).fetchone()
    print(f'{table}: {\"EXISTS\" if exists else \"MISSING\"}')"
```

### Step 4: Run existing test suite
```bash
cd ~/clawd/moh-time-os && python3 -m pytest tests/ -q --tb=short
```
All 297+ existing tests must still pass.

## Acceptance Criteria
- [ ] All 6 tables created successfully
- [ ] All indexes created
- [ ] Existing test suite passes (no regressions)

---

# ═══════════════════════════════════════════════════════════════
# TASK 24 of 35: Event Emitter Module (UI)
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 1.0 | Depends On: Task 23 | Status: PENDING

## Objective
Create lightweight event emitter in the UI: `time-os-ui/src/intelligence/lib/events.js`. Fire-and-forget, batched, never blocks UI.

## Instructions

### Step 1: Build events.js

```javascript
/**
 * Feedback event emitter — tracks UI interactions for system calibration.
 * Fire-and-forget. Never blocks UI. Silent on error.
 *
 * Usage:
 *   import { trackSignalSeen, trackSignalDismissed, startEventCollection } from '../lib/events';
 *   startEventCollection(); // call once on app mount
 *   trackSignalSeen('sig_001', 'communication_declining', 'client', 12);
 */

const FLUSH_INTERVAL = 30000; // 30 seconds
const MAX_BUFFER_SIZE = 100;
const API_ENDPOINT = '/api/v2/feedback/events';

let buffer = [];
let sessionId = null;
let flushTimer = null;

function generateSessionId() { return 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8); }
function generateEventId() { return 'evt_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8); }

function emitEvent(eventType, { entityType, entityId, signalId, signalType, context } = {}) {
  buffer.push({
    event_id: generateEventId(),
    timestamp: new Date().toISOString(),
    user_id: 'moh',
    event_type: eventType,
    entity_type: entityType || null,
    entity_id: entityId || null,
    signal_id: signalId || null,
    signal_type: signalType || null,
    context: context ? JSON.stringify(context) : null,
    session_id: sessionId,
  });
  if (buffer.length >= MAX_BUFFER_SIZE) flush();
}

async function flush() {
  if (buffer.length === 0) return;
  const batch = [...buffer];
  buffer = [];
  try {
    await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events: batch }),
      keepalive: true, // survive page unload
    });
  } catch (e) { /* silent — events are valuable but not critical */ }
}

export function startEventCollection() {
  sessionId = generateSessionId();
  emitEvent('session_start');
  flushTimer = setInterval(flush, FLUSH_INTERVAL);
  window.addEventListener('beforeunload', () => { emitEvent('session_end'); flush(); });
}

// Convenience functions
export function trackPageView(page, entityType, entityId) { emitEvent('page_view', { entityType, entityId, context: { page } }); }
export function trackSignalSeen(signalId, signalType, entityType, entityId) { emitEvent('signal_seen', { signalId, signalType, entityType, entityId }); }
export function trackSignalDismissed(signalId, signalType, entityType, entityId) { emitEvent('signal_dismissed', { signalId, signalType, entityType, entityId }); }
export function trackSignalDrilldown(signalId, signalType, entityType, entityId) { emitEvent('signal_drilldown', { signalId, signalType, entityType, entityId }); }
export function trackEntityDrilldown(entityType, entityId, source) { emitEvent('entity_drilldown', { entityType, entityId, context: { source } }); }
export function trackSearchPerformed(query, resultCount) { emitEvent('search_performed', { context: { query, result_count: resultCount } }); }
export function trackComparisonViewed(entityType, entityId, comparisonType) { emitEvent('comparison_viewed', { entityType, entityId, context: { comparison_type: comparisonType } }); }
export function trackTopologyViewed(entityType, entityId) { emitEvent('topology_viewed', { entityType, entityId }); }
export function trackExportPerformed(entityType, entityId, format) { emitEvent('export_performed', { entityType, entityId, context: { format } }); }
```

### Step 2: Tests
- emitEvent adds to buffer
- flush sends batch and clears buffer
- startEventCollection creates session ID and starts timer
- Buffer auto-flushes at MAX_BUFFER_SIZE
- Silent on fetch error

## Acceptance Criteria
- [ ] Event emitter created with 9 convenience functions
- [ ] Batched (30s interval + max 100 buffer)
- [ ] Fire-and-forget (silent on error)
- [ ] Session ID management
- [ ] keepalive on page unload
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 25 of 35: Event Collection API Endpoint
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 1.0 | Depends On: Task 23 | Status: PENDING

## Objective
Create `api/feedback_router.py` with POST /api/v2/feedback/events endpoint. Accepts batches, validates, writes to interaction_events table.

## Instructions

### Step 1: Create api/feedback_router.py
```python
from flask import Blueprint, request, jsonify
import sqlite3, json
from datetime import datetime

feedback_bp = Blueprint('feedback', __name__, url_prefix='/api/v2/feedback')

VALID_EVENT_TYPES = {'page_view', 'signal_seen', 'signal_dismissed', 'signal_drilldown',
    'entity_drilldown', 'entity_frequent', 'comparison_viewed', 'topology_viewed',
    'search_performed', 'session_start', 'session_end', 'export_performed', 'heartbeat'}

@feedback_bp.route('/events', methods=['POST'])
def collect_events():
    """Accept batch of interaction events. Max 100 per request."""
    data = request.get_json(silent=True)
    if not data or 'events' not in data: return jsonify({'error': 'Missing events array'}), 400
    events = data['events']
    if len(events) > 100: return jsonify({'error': 'Max 100 events per batch'}), 400
    # Validate and insert...
    return jsonify({'accepted': len(valid_events)}), 202

@feedback_bp.route('/events/count', methods=['GET'])
def event_count():
    """Monitoring endpoint: total event count."""
    # Query count from interaction_events
    return jsonify({'total': count})
```

### Step 2: Mount router in app
Find the main Flask app and register `feedback_bp`. Do NOT touch spec_router.py.

### Step 3: Rate limiting
Simple in-memory rate limiter: max 10 requests per minute per IP. Return 429 if exceeded.

### Step 4: Tests
- POST /api/v2/feedback/events with valid batch → 202 Accepted
- POST with >100 events → 400
- POST with invalid event_type → skipped (still 202 for valid ones)
- POST with missing events → 400
- GET /events/count → returns total

## Acceptance Criteria
- [ ] feedback_router.py created and mounted
- [ ] POST /events accepts batches up to 100
- [ ] Validates event types
- [ ] Writes to interaction_events table
- [ ] GET /events/count works
- [ ] Rate limiting (10 req/min)
- [ ] Tests pass, existing tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 26 of 35: UI Instrumentation — Portfolio Pulse
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 1.1 | Depends On: Tasks 24-25 | Status: PENDING

## Objective
Add invisible event tracking to PulsePage and signal card components.

## Instructions

### Step 1: Track page_view on PulsePage mount
```javascript
useEffect(() => { trackPageView('portfolio_pulse'); }, []);
```

### Step 2: Track signal_seen via IntersectionObserver
In SignalCard: when card is 50% visible in viewport for the first time, fire `trackSignalSeen`. Use a ref + IntersectionObserver. Track each signal only once per session.

### Step 3: Track signal_dismissed
In SignalCardList: when onDismiss is called, fire `trackSignalDismissed`.

### Step 4: Track signal_drilldown
When evidence drawer opens (onSignalDrilldown), fire `trackSignalDrilldown`.

### Step 5: Verify zero visual impact
These additions must NOT change any rendered UI. No loading indicators, no badges, no text. Pure instrumentation.

## Acceptance Criteria
- [ ] page_view tracked on PulsePage mount
- [ ] signal_seen tracked via IntersectionObserver (once per signal per session)
- [ ] signal_dismissed tracked on dismiss
- [ ] signal_drilldown tracked on evidence open
- [ ] Zero visual impact
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 27 of 35: UI Instrumentation — Entity Views + Session
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 1.1 | Depends On: Tasks 24-25 | Status: PENDING

## Objective
Instrument all entity profile views, comparison views, topology, search, and session lifecycle.

## Instructions

Track: page_view + entity_drilldown in all entity profiles, comparison_viewed in comparison views, topology_viewed, search_performed (with query + result count), export_performed. Session: startEventCollection() on app mount, heartbeat every 60s, session_end on unmount or 15min inactivity. Zero visual impact.

## Acceptance Criteria
- [ ] All entity views instrumented
- [ ] Session lifecycle tracked
- [ ] 60s heartbeat
- [ ] 15min inactivity timeout
- [ ] Zero visual impact
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 28 of 35: Signal Utility Computation — Implementation
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 2.0 | Depends On: Task 27 | Status: PENDING

## Objective
Implement compute_signal_utility, classify_signal_utility, and store_signal_utility in feedback_engine.py.

## Instructions

### Step 1: Implement compute_signal_utility
- Query interaction_events for signal_seen events in lookback window
- For each signal_type: count seen, check for drilldown within 48h (investigated), check for dismissed, remaining = ignored
- Compute action_rate, dismiss_rate, ignore_rate, avg_time_to_action
- Classify: HIGH_UTILITY (action_rate > 0.5), MODERATE (0.2-0.5), LOW_UTILITY (0.1-0.2), NOISE (action_rate < 0.1 AND dismiss_rate > 0.5)

### Step 2: Implement store_signal_utility
Insert/update rows in signal_utility_scores table.

### Step 3: Comprehensive tests
- Test with synthetic events: insert 50 events, compute, verify classifications
- Test edge cases: no events, all dismissed, all investigated, mixed

## Acceptance Criteria
- [ ] compute_signal_utility produces correct classifications
- [ ] store_signal_utility writes to table
- [ ] All edge cases tested
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 29 of 35: Signal Type Report + Per-Entity Relevance
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 2.0 | Depends On: Task 28 | Status: PENDING

## Objective
Implement generate_signal_utility_report, compute_entity_signal_relevance, and summarize_sessions.

## Instructions

- generate_signal_utility_report: ranking with trend analysis (compare to 30 days ago), identify noisiest/most useful types
- compute_entity_signal_relevance: entity-specific utility scores, enables personalized thresholds
- summarize_sessions: aggregate session data into session_summaries table

## Acceptance Criteria
- [ ] Report generates ranking of signal types by utility
- [ ] Per-entity relevance computed
- [ ] Sessions summarized
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 30 of 35: Feedback Foundation Validation
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 2.1 | Depends On: Task 29 | Status: PENDING

## Objective
End-to-end validation: insert 50 synthetic events → compute utility → store → generate report → verify. Full test suite.

## Acceptance Criteria
- [ ] E2E pipeline works
- [ ] All feedback tables populated correctly
- [ ] UI instrumentation verified
- [ ] All tests pass (backend + frontend)

---

# ═══════════════════════════════════════════════════════════════
# TASK 31 of 35: Threshold Adaptation + Confidence Scoring
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 3.0 | Depends On: Task 30 | Status: PENDING

## Objective
Implement propose_threshold_adjustments with confidence scoring.

## Instructions

Logic:
- dismiss_rate > 0.6 AND data_points > min → PROPOSE tighten by 10%
- action_rate > 0.7 AND threshold catches < 50% entities → PROPOSE loosen by 10%
- ignore_rate > 0.8 AND dismiss_rate < 0.2 → flag as INVISIBLE (UI placement issue)

Confidence: HIGH (>50 data points, 30+ days), MEDIUM (20-50), LOW (<20).

## Acceptance Criteria
- [ ] Threshold proposals generated with confidence levels
- [ ] Evidence summaries included
- [ ] Tests with synthetic data verify all logic branches

---

# ═══════════════════════════════════════════════════════════════
# TASK 32 of 35: Safety Rails + Threshold Application
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 3.0 | Depends On: Task 31 | Status: PENDING

## Objective
Implement apply_threshold_adjustment with safety rails.

## Instructions

Safety rails:
- Max adjustment: 15% per cycle
- Min data points: 20
- Auto-revert if action_rate drops within 2 weeks
- Floor/ceiling: no threshold below 20 or above 95
- Cooldown: 14 days between adjustments per signal type

Log every adjustment in threshold_calibration_log.

## Acceptance Criteria
- [ ] Adjustments applied with safety constraints
- [ ] All adjustments logged
- [ ] Auto-revert mechanism
- [ ] Cooldown enforced
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 33 of 35: Entity Attention Scoring + Ranking
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 4.0 | Depends On: Task 30 | Status: PENDING

## Objective
Implement compute_entity_attention and attention-based signal ranking.

## Instructions

Attention score = weighted combination of:
- visit_frequency (visits / days, normalized 0-1)
- visit_depth (avg: page_view=0.2, drilldown=0.5, evidence=0.8, comparison=1.0)
- unprompted_ratio (visits NOT preceded by signal / total)
- recency_weight (exponential decay)

Store in entity_attention_scores. Modify signal ranking: signals on high-attention entities rank higher.

## Acceptance Criteria
- [ ] Attention scores computed correctly
- [ ] Stored in entity_attention_scores
- [ ] Signal ranking modified (sort order, not visibility)
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 34 of 35: Blind Spot Detection + Navigation Patterns
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 4.0 | Depends On: Task 33 | Status: PENDING

## Objective
Implement detect_blind_spots and compute_navigation_patterns.

## Instructions

Blind spots: entities with active signals but zero visits in lookback period. Classifications: BLIND_SPOT, DRIFT, LOW_PRIORITY.

Navigation patterns: common sequences, first_action distribution, avg_session_depth, unused_views, frequently_accessed_entities.

## Acceptance Criteria
- [ ] Blind spots detected and classified
- [ ] Navigation patterns computed
- [ ] Tests pass

---

# ═══════════════════════════════════════════════════════════════
# TASK 35 of 35: Calibration Dashboard + Overrides + Health + Final Validation
# ═══════════════════════════════════════════════════════════════
> Brief: B6 | Phase: 5.0 | Depends On: Tasks 32, 34 | Status: PENDING

## Objective
Build the calibration dashboard UI at `/intelligence/calibration`, override controls, feedback health indicators, and final validation of Brief 6.

## Instructions

### Step 1: Build CalibrationDashboard view

Route: `/intelligence/calibration`

Sections:
1. **Signal Utility Rankings** — table of signal types ranked by utility (most useful → noisiest), with action_rate, dismiss_rate, utility_classification
2. **Threshold History** — per signal type: current threshold, last 3 adjustments with dates/reasons, Sparkline of threshold over time
3. **Pending Proposals** — list of proposed adjustments with approve/reject buttons (if approval mode)
4. **Attention Model** — top 10 most-watched entities, blind spot list with "View Entity →" links
5. **Feedback Health** — meta-metrics: events/day, signals evaluated/month, calibration activity, signal
Done
Continue

12:44 PM
Compacting our conversation so we can keep chatting...
