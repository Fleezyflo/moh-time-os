# Intelligence Layer Views

## Overview

The Intelligence Layer UI surfaces operational intelligence from the backend:
- Entity scores (client, project, person, portfolio)
- Active signals (threshold, trend, anomaly, compound)
- Detected patterns (concentration, cascade, degradation, drift, correlation)
- Prioritized proposals with actionable recommendations
- Daily briefings

## Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/intel` | `CommandCenter` | Main intelligence dashboard |
| `/intel/briefing` | `Briefing` | Daily briefing view |
| `/intel/signals` | `Signals` | Active signals list |
| `/intel/patterns` | `Patterns` | Detected patterns |
| `/intel/proposals` | `Proposals` | Ranked proposals |
| `/intel/client/:id` | `ClientIntel` | Client intelligence deep dive |
| `/intel/person/:id` | `PersonIntel` | Person intelligence deep dive |

## View Definitions

### 1. Command Center (`/intel`)

The primary intelligence dashboard. Shows the "30-second scan" view.

**Sections:**
1. **Portfolio Health** — Single score (0-100) with trend indicator
2. **Critical Items** — IMMEDIATE urgency proposals (expandable cards)
3. **Attention Items** — THIS_WEEK proposals (top 5)
4. **Signal Summary** — Counts by severity (critical/warning/watch)
5. **Pattern Alerts** — Structural patterns only

**API Endpoints Used:**
- `GET /api/v2/intelligence/critical`
- `GET /api/v2/intelligence/scores/portfolio`
- `GET /api/v2/intelligence/signals/summary`
- `GET /api/v2/intelligence/patterns` (filtered to structural)

**Components:**
- `HealthScore` — Large score display with trend
- `ProposalCard` — Expandable proposal with evidence
- `SignalBadges` — Severity count badges
- `PatternAlert` — Pattern card with affected entities

---

### 2. Briefing (`/intel/briefing`)

Daily briefing in a narrative format.

**Sections:**
1. **Summary** — "X proposals today: Y critical, Z attention, W watching"
2. **Top Priority** — The #1 ranked proposal with full evidence
3. **Critical Items** — IMMEDIATE proposals with implied actions
4. **Attention Items** — THIS_WEEK proposals
5. **Watching** — MONITOR proposals (collapsed by default)
6. **Portfolio Snapshot** — Health score, active patterns, key metrics

**API Endpoints Used:**
- `GET /api/v2/intelligence/briefing`
- `GET /api/v2/intelligence/entity/portfolio`

**Components:**
- `BriefingSummary` — Header with counts
- `ProposalDetail` — Full proposal with evidence list
- `WatchList` — Collapsible monitoring items

---

### 3. Signals (`/intel/signals`)

All active signals with filtering.

**Sections:**
1. **Filters** — By severity, entity type, signal category
2. **Signal List** — Cards showing signal details
3. **Signal Detail** (drawer) — Full evidence and history

**Filters:**
- Severity: critical, warning, watch, all
- Entity Type: client, project, person, portfolio
- Category: threshold, trend, anomaly, compound

**API Endpoints Used:**
- `GET /api/v2/intelligence/signals`
- `GET /api/v2/intelligence/signals/active`
- `GET /api/v2/intelligence/signals/history`

**Components:**
- `SignalFilters` — Filter bar
- `SignalCard` — Signal summary with severity badge
- `SignalDrawer` — Full signal detail with history timeline

---

### 4. Patterns (`/intel/patterns`)

Detected structural patterns.

**Sections:**
1. **Pattern List** — Cards by severity (structural → operational → informational)
2. **Pattern Detail** (drawer) — Detection logic, affected entities, implied action

**API Endpoints Used:**
- `GET /api/v2/intelligence/patterns`
- `GET /api/v2/intelligence/patterns/catalog`

**Components:**
- `PatternCard` — Pattern summary with type badge
- `PatternDrawer` — Full pattern detail
- `AffectedEntities` — List of entities involved

---

### 5. Proposals (`/intel/proposals`)

Ranked proposals with full detail.

**Sections:**
1. **Filters** — By urgency, type
2. **Proposal List** — Ranked cards with priority scores
3. **Proposal Detail** (drawer) — Full evidence, entity links, action buttons

**Filters:**
- Urgency: immediate, this_week, monitor, all
- Type: client_risk, resource_risk, project_risk, portfolio_risk, financial_alert, opportunity

**API Endpoints Used:**
- `GET /api/v2/intelligence/proposals`

**Components:**
- `ProposalFilters` — Filter bar
- `ProposalCard` — Summary with score and urgency
- `ProposalDrawer` — Full detail with evidence

---

### 6. Client Intelligence (`/intel/client/:id`)

Deep dive into a single client.

**Sections:**
1. **Scorecard** — Dimension scores with trend
2. **Active Signals** — Signals for this client
3. **Signal History** — Timeline of past signals
4. **Trajectory** — Score trend over time (chart)
5. **Related Proposals** — Proposals mentioning this client

**API Endpoints Used:**
- `GET /api/v2/intelligence/entity/client/:id`
- `GET /api/v2/intelligence/scores/client/:id`

**Components:**
- `Scorecard` — Dimension breakdown
- `ScoreTrend` — Line chart of score history
- `SignalTimeline` — Chronological signal list

---

### 7. Person Intelligence (`/intel/person/:id`)

Deep dive into a single person.

**Sections:**
1. **Scorecard** — Dimension scores (load, output, spread, availability)
2. **Active Signals** — Signals for this person
3. **Signal History** — Timeline
4. **Blast Radius** — Clients/projects affected if this person is unavailable

**API Endpoints Used:**
- `GET /api/v2/intelligence/entity/person/:id`
- `GET /api/v2/intelligence/scores/person/:id`

**Components:**
- `Scorecard` — Dimension breakdown
- `BlastRadius` — Entity dependency graph

---

## Shared Components

| Component | Usage |
|-----------|-------|
| `HealthScore` | Large score display (0-100) with color and trend |
| `ProposalCard` | Proposal summary card |
| `ProposalDrawer` | Full proposal detail drawer |
| `SignalCard` | Signal summary card |
| `SignalDrawer` | Full signal detail drawer |
| `PatternCard` | Pattern summary card |
| `PatternDrawer` | Full pattern detail drawer |
| `Scorecard` | Entity scorecard with dimensions |
| `SeverityBadge` | Severity indicator (critical/warning/watch) |
| `UrgencyBadge` | Urgency indicator (immediate/this_week/monitor) |
| `EntityLink` | Clickable entity reference |
| `EvidenceList` | List of evidence items |

---

## Color System

Consistent with existing Time OS UI:

| Severity/Urgency | Tailwind Classes |
|------------------|------------------|
| Critical / Immediate | `bg-red-500/10 text-red-400 border-red-500` |
| Warning / This Week | `bg-amber-500/10 text-amber-400 border-amber-500` |
| Watch / Monitor | `bg-slate-500/10 text-slate-400 border-slate-500` |
| Healthy | `bg-green-500/10 text-green-400 border-green-500` |

Score colors (0-100):
- 0-30: Red (critical)
- 31-60: Amber (warning)
- 61-100: Green (healthy)

---

## Mobile Responsiveness

- Cards stack vertically on mobile
- Drawers become full-screen modals
- Filters collapse into dropdown on mobile
- Tables become card lists on mobile

---

## Implementation Order

1. **Shared Components** — Build reusable components first
2. **Command Center** — Primary dashboard
3. **Briefing** — Daily briefing view
4. **Signals** — Signal list and detail
5. **Patterns** — Pattern list and detail
6. **Proposals** — Proposal list and detail
7. **Client/Person Intel** — Entity deep dives
