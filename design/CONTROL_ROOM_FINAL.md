# HRMNY Control Room — Design Architecture

## Overview

A command interface for agency executives. Full system visibility with intelligent organization. Bold, distinctive visual language reflecting hrmny's creative identity.

---

## Design Principles

1. **Full context visible** — See the entire system state at once. No hiding, no drip-feeding.
2. **Intelligent organization** — Information grouped by meaning, prioritized by urgency.
3. **Action-ready** — Every view enables action. One click to do, not just to see.
4. **Distinctive** — Looks like hrmny, not like generic SaaS.

---

## Visual System

### Typography

```
Primary:     Space Grotesk (400, 500, 700)
Monospace:   JetBrains Mono (400, 500)

Scale:
  hero:      36-64px / 700    (key metrics, health scores)
  title:     15-20px / 600    (page titles, section headers)
  body:      14px / 400       (content)
  label:     11px / 500       (labels, metadata, mono)
  micro:     10px / 500       (tags, status badges, mono)
```

### Color

```
Base:
  black:     #000000          (background)
  white:     #ffffff          (primary text)
  
Grey scale:
  grey-1:    #111111          (elevated surfaces)
  grey-2:    #222222          (borders, dividers)
  grey-3:    #444444          (secondary borders)
  grey-4:    #666666          (tertiary text, labels)
  grey-5:    #888888          (secondary text)

Signal:
  accent:    #ff3d00          (critical, at-risk, primary action)
  yellow:    #ffcc00          (warning, attention)
  green:     #00ff88          (healthy, on-track, live status)
```

### Spacing

```
Base unit: 4px

Scale: 4, 8, 12, 16, 20, 24, 32, 48, 64

Page padding:    32px
Section gap:     32-48px
Card padding:    20-24px
Row padding:     12-16px
```

### Components

**Status Indicators**
- 8x8px square (not circle)
- Colors: accent (critical), yellow (warning), green (good)
- Pulsing animation for live status

**Labels**
- JetBrains Mono, 10-11px
- Uppercase, letter-spacing 0.1-0.15em
- Color: grey-4

**Buttons**
- Primary: accent background, black text
- Secondary: transparent, grey-3 border, white text
- Uppercase, letter-spacing 0.05em
- Padding: 12-16px vertical, 24-32px horizontal

**Data rows**
- Full-width, border-bottom grey-1
- Hover: background grey-1, slight indent
- Grid layout with consistent column widths

**Cards (attention items)**
- Background grey-1
- Left border 3px for status color
- Hover: background grey-2

---

## Information Architecture

```
CONTROL ROOM
├── Command (home)
│   ├── Agency status bar (5 key metrics)
│   ├── Attention items (flagged issues, ranked)
│   ├── Active projects (status list)
│   ├── Clients (health + AR)
│   ├── Today (calendar)
│   ├── AR aging (mini chart)
│   └── Team utilization (grid)
│
├── Clients
│   ├── Client list (health-sorted)
│   └── Client 360 (detail)
│       ├── Health breakdown
│       ├── Active work by brand
│       ├── Financials
│       ├── Activity timeline
│       └── Key contacts
│
├── Projects
│   ├── Project list (status-sorted)
│   └── Project detail
│       ├── Progress + stats
│       ├── Blocker alert
│       ├── Task list
│       ├── Team
│       └── Activity timeline
│
├── Cash
│   ├── Summary stats
│   ├── Aging chart
│   ├── Collection queue (prioritized)
│   └── All invoices (sortable)
│
└── Team
    ├── Utilization overview
    ├── Person list
    └── Person detail
```

---

## Screen Specifications

### Command (Home)

**Purpose:** Full agency state at a glance. Entry point for all actions.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: Logo | Nav | Status | Time                          │
├─────────────────────────────────────────────────────────────┤
│ AGENCY BAR: Projects | Clients | AR | Capacity | Comms      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LEFT (2/3)                    │  RIGHT (1/3)               │
│                                │                            │
│  Attention Items               │  Today                     │
│  ├─ Item 1 (critical)         │  ├─ 09:00 Standup          │
│  ├─ Item 2 (warning)          │  ├─ 11:00 GMG Review       │
│  └─ Item 3 (warning)          │  └─ 14:00 Supercare Call   │
│                                │                            │
│  Active Projects               │  AR Aging                  │
│  ├─ Project row               │  [Mini bar chart]          │
│  ├─ Project row               │                            │
│  └─ ...                       │  Team Utilization          │
│                                │  [Grid: initials + %]      │
│  Clients                       │                            │
│  ├─ Client row                │                            │
│  └─ ...                       │                            │
│                                │                            │
└─────────────────────────────────────────────────────────────┘
```

**Agency Bar Metrics:**
| Metric | Source | Alert Condition |
|--------|--------|-----------------|
| Projects | projects.status counts | Any at-risk |
| Clients | clients.health_score | Any < 50 |
| Outstanding AR | invoices.amount sum | Any overdue |
| Team Capacity | utilization % | Any > 100% |
| Comms | communications.requires_response | Any pending |

**Attention Items:**
- Source: resolution_queue, priority-sorted
- Max: 5 items
- Click → appropriate detail view
- Shows: title, context, domain tag

### Client 360

**Purpose:** Complete view of a client relationship.

**Sections:**
1. **Health Score** — Large number + breakdown bars
2. **Active Work** — Projects grouped by brand
3. **Financials** — AR summary + invoice list
4. **Activity** — Recent emails, meetings, milestones
5. **Actions** — Escalate AR, Email client

**Data Binding:**
- Health: `clients.health_score`, breakdown from `client360_page10.py`
- Work: `projects WHERE client_id = X`, grouped by `brand_id`
- Financials: `invoices WHERE client_id = X`
- Activity: `communications WHERE client_id = X` + `events`

### Project Detail

**Purpose:** Status and control for a specific project.

**Sections:**
1. **Stats Bar** — Progress, deadline, client, owner
2. **Progress Bar** — Visual completion
3. **Blocker Alert** — If blocked, prominent warning
4. **Tasks** — List with status, assignee, due date
5. **Team** — Assigned team members
6. **Activity** — Timeline of events

**Data Binding:**
- Stats: `projects.*`
- Tasks: `tasks WHERE project_id = X`
- Blocker: derived from blocked tasks, `slip_risk_score`

### Cash View

**Purpose:** AR position and collection priorities.

**Sections:**
1. **Summary Bar** — Total, overdue, current, avg days
2. **Aging Chart** — Bar chart by bucket
3. **Collection Queue** — Prioritized list with recommended actions
4. **Invoice List** — All invoices, sortable

**Data Binding:**
- Summary: aggregates from `invoices`
- Aging: `invoices` grouped by `aging_bucket`
- Collection: derived from aging + follow-up history

---

## Navigation

**Header Nav:**
- Persistent across all views
- Items: Command, Clients, Projects, Cash, Team
- Active state: white text
- Inactive: grey-4 text

**Drill-down:**
- Click entity row → detail view
- Back button → previous view
- Breadcrumb shows: Section → Entity name

**Deep Links:**
- All views URL-addressable
- Pattern: `/clients/{id}`, `/projects/{id}`, etc.

---

## Interactions

### Hover States
- Rows: background grey-1, slight left indent
- Cards: background grey-2
- Buttons: color shift (primary → white, secondary → border white)
- Transition: 150ms ease

### Click Actions
| Element | Action |
|---------|--------|
| Agency stat | Navigate to that domain |
| Attention item | Navigate to related entity |
| Project row | Open project detail |
| Client row | Open client 360 |
| Invoice row | Open invoice detail / action |
| Action button | Execute action (confirm if needed) |

### Keyboard
- Tab: Navigate focusable elements
- Enter: Activate focused element
- Escape: Close modals, go back

---

## Data Freshness

**Sync Indicator:**
- Position: header right
- Shows: "SYNCED" + green dot (pulsing)
- If stale (>5 min): "STALE" + yellow dot
- If error: "ERROR" + red dot

**Per-section freshness:**
- Show "Updated X min ago" in section footers if needed
- Confidence indicators for derived metrics

---

## Responsive Behavior

### Desktop (≥1280px)
- Full two-column layout
- All sections visible

### Tablet (768-1279px)
- Single column
- Agency bar: 3+2 or 2+2+1
- Sections stack vertically

### Mobile (<768px)
- Single column
- Bottom tab navigation
- Simplified data density
- Detail views as full-screen overlays

---

## File Structure

```
/prototype/v5/
├── index.html        (Command view)
├── client.html       (Client 360)
├── project.html      (Project detail)
├── cash.html         (Cash view)
├── team.html         (Team view - TBD)
└── styles/
    └── main.css      (shared styles - can extract)
```

---

## Implementation Notes

### Tech Stack
- HTML/CSS (prototype)
- Production: React/Next.js recommended
- Data: agency_snapshot.json from existing backend

### CSS Approach
- CSS custom properties for tokens
- Grid for layout
- No external UI library needed (custom components)

### Data Integration
- Fetch `agency_snapshot.json` on load
- Poll every 60s for updates
- Use existing scoring/ranking from backend

---

## Next Steps

1. **Review prototype** — Validate direction with these views
2. **Complete Team view** — Utilization detail
3. **Add interactions** — Modal confirmations, action flows
4. **Build production version** — React components, real data binding
5. **Mobile optimization** — Responsive breakpoints, touch interactions

---

*Version: 5.0*
*Last updated: 2025-02-05*
