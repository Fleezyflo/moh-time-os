# HRMNY Control Room — Design Specification

## Design Principles

1. **Intelligence over information** — The interface shows A's conclusions, not raw data. Every element on screen has been curated.
2. **Action over analysis** — Every screen answers "what should I do?" not "what is happening?"
3. **Relationships over categories** — Information is connected by meaning, not siloed by type.
4. **Restraint over completeness** — Show less, better. Empty space is a feature.

---

## Visual System

### Palette

```
Background
  base:           #000000
  surface:        #0a0a0a
  elevated:       #141414

Text
  primary:        #ffffff
  secondary:      #8a8a8a
  tertiary:       #4a4a4a

Signal
  critical:       #ff3b30
  warning:        #ff9500
  positive:       #30d158
  info:           #0a84ff

Accent
  brand:          #6366f1
```

### Typography

```
Family:          Inter (400, 500, 600)
Monospace:       JetBrains Mono (metrics, IDs)

Scale:
  headline-1:    40/44  600    (screen titles)
  headline-2:    28/32  600    (section titles)
  headline-3:    20/24  500    (card titles)
  body:          15/22  400    (primary content)
  caption:       13/18  400    (secondary content)
  micro:         11/14  500    (labels, metadata)
```

### Spacing

```
Unit:            8px
Scale:           4, 8, 12, 16, 24, 32, 48, 64, 96
```

### Radius

```
small:           6px   (buttons, inputs)
medium:          12px  (cards)
large:           20px  (panels)
```

---

## Information Architecture

```
CONTROL ROOM
│
├── HOME
│   ├── Status bar (agency health, time, sync)
│   ├── Attention stack (ranked situations)
│   └── Quick nav (Clients, Projects, Cash, Team)
│
├── CLIENTS
│   ├── Portfolio (health-sorted grid)
│   └── Client detail (360 view)
│       ├── Health breakdown
│       ├── Active work
│       ├── Financial position
│       ├── Recent activity
│       └── Actions
│
├── PROJECTS
│   ├── Active work (status-sorted list)
│   └── Project detail
│       ├── Progress + timeline
│       ├── Tasks + blockers
│       ├── Team
│       └── Actions
│
├── CASH
│   ├── Position summary
│   ├── Aging breakdown
│   ├── Collection queue
│   └── Invoice detail
│
└── TEAM
    ├── Utilization overview
    ├── Person detail
    └── Availability
```

---

## Screens

### HOME

The primary interface. Answers: "What needs me right now?"

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ● STABLE                                           9:14 AM     │
│                                                                  │
│                                                                  │
│                                                                  │
│   Needs attention                                                │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                                                          │  │
│   │   GMG Ramadan Campaign                             ● ──→ │  │
│   │   Brief not started. 39 days to deadline.                │  │
│   │   Escalate at today's 11:00 review.                      │  │
│   │                                                          │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                                                          │  │
│   │   Supercare collection                             ● ──→ │  │
│   │   AED 75K at 60+ days. Emails not working.               │  │
│   │   Phone call needed.                                     │  │
│   │                                                          │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                                                          │  │
│   │   Gargash contract meeting                         ● ──→ │  │
│   │   Friday. No prep done.                                  │  │
│   │   Block time tomorrow.                                   │  │
│   │                                                          │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│                                                                  │
│                                                                  │
│   ─────────────────────────────────────────────────────────────  │
│                                                                  │
│   Clients          Projects          Cash            Team        │
│   5 active         10 active         276K AR         94%         │
│   all healthy      1 at risk         3 overdue       nominal     │
│                                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Components:**

**Status indicator**
- Position: top left
- States: STABLE (green), ATTENTION (amber), CRITICAL (red)
- Shows agency-wide health derived from all signals

**Attention card**
- Background: elevated
- Border-left: 3px signal color
- Content:
  - Line 1: Entity name (headline-3)
  - Line 2: Situation (body, secondary)
  - Line 3: Recommendation (body, tertiary, italic)
- Right: signal dot + arrow
- Hover: background lightens, cursor pointer
- Click: opens situation detail

**Quick nav**
- Four columns, equal width
- Each shows: label (micro), primary metric (headline-3), secondary (caption)
- Click: navigates to that section

---

### SITUATION DETAIL

Expands from attention card. Answers: "What's the full context and what can I do?"

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ← Back                                                         │
│                                                                  │
│                                                                  │
│   GMG Ramadan Campaign                                           │
│   Monoprix · Campaign                                            │
│                                                                  │
│                                                                  │
│   ┌─────────────────────────────────────┐                        │
│   │                                     │                        │
│   │   15%                               │                        │
│   │   ━━━━━░░░░░░░░░░░░░░░░░░░░░░░░░░░ │                        │
│   │                                     │                        │
│   │   Deadline        Mar 15            │                        │
│   │   Days left       39                │                        │
│   │   Owner           Strategy Team     │                        │
│   │   Client health   72.5              │                        │
│   │                                     │                        │
│   └─────────────────────────────────────┘                        │
│                                                                  │
│                                                                  │
│   Problem                                                        │
│                                                                  │
│   Campaign brief hasn't started. This blocks creative concepts,  │
│   production planning, and media buying. Every day of delay      │
│   compresses the remaining timeline exponentially.               │
│                                                                  │
│                                                                  │
│   Recommendation                                                 │
│                                                                  │
│   You have a GMG Campaign Review at 11:00 today. That's the      │
│   right moment to escalate this directly. I can draft talking    │
│   points for that meeting.                                       │
│                                                                  │
│                                                                  │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│   │ Draft talking  │  │ See all tasks  │  │ View client    │    │
│   │ points         │  │                │  │                │    │
│   └────────────────┘  └────────────────┘  └────────────────┘    │
│                                                                  │
│                                                                  │
│   Related                                                        │
│   ──────                                                         │
│   Today 11:00    GMG Campaign Review (meeting)                   │
│   Feb 2          GMG Campaign Feedback (email from marketing@)   │
│   Jan 30         Feedback on Deliverables (email from team@)     │
│                                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Components:**

**Progress block**
- Background: surface
- Shows: completion %, progress bar, key metrics grid

**Problem statement**
- Plain text, body size
- States the issue and its implications clearly

**Recommendation**
- Plain text, body size
- A's specific recommendation with reasoning

**Action buttons**
- Primary action: brand background, white text
- Secondary actions: surface background, border
- Max 3 visible, overflow to menu

**Related items**
- Chronological list
- Each row: date, description, type indicator
- Click: opens that item

---

### CLIENTS

Portfolio view. Answers: "How are my client relationships?"

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ← Home                                            Clients      │
│                                                                  │
│                                                                  │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│   │             │ │             │ │             │               │
│   │   GMG       │ │   Gargash   │ │  Supercare  │               │
│   │   ●  72     │ │   ●  85     │ │   ●  65     │               │
│   │             │ │             │ │             │               │
│   │   107K AR   │ │   1.2K AR   │ │   75K AR    │               │
│   │   4 projects│ │   1 project │ │   1 project │               │
│   │             │ │             │ │             │               │
│   └─────────────┘ └─────────────┘ └─────────────┘               │
│                                                                  │
│   ┌─────────────┐ ┌─────────────┐                               │
│   │             │ │             │                               │
│   │  Five Guys  │ │   BinSina   │                               │
│   │   ●  78     │ │   ●  70     │                               │
│   │             │ │             │                               │
│   │   1.2K AR   │ │   0 AR      │                               │
│   │   1 project │ │   1 project │                               │
│   │             │ │             │                               │
│   └─────────────┘ └─────────────┘                               │
│                                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Client card**
- Size: fixed width, auto height
- Content: name, health score with indicator, AR amount, project count
- Health indicator color: >70 green, 50-70 amber, <50 red
- Sorted by: health score ascending (worst first)
- Click: opens client detail

---

### CLIENT DETAIL (360)

Full client context. Answers: "What's the complete picture of this relationship?"

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ← Clients                                    GMG Consumer LLC  │
│                                                       Tier A     │
│                                                                  │
│   ┌────────────────────────────────────────────────────────────┐│
│   │                                                            ││
│   │   72.5         Delivery     ━━━━━━━━━━░░  78              ││
│   │   Health       Finance      ━━━━━━░░░░░░  55              ││
│   │                Response     ━━━━━━━━━━░░  80              ││
│   │   ↓ from 78    Commitment   ━━━━━━━━░░░░  72              ││
│   │                Capacity     ━━━━━━━━━░░░  77              ││
│   │                                                            ││
│   └────────────────────────────────────────────────────────────┘│
│                                                                  │
│                                                                  │
│   Work                                                           │
│   ────                                                           │
│   Monoprix Monthly          ●  65%     on track                  │
│   GMG Ramadan Campaign      ●  15%     at risk                   │
│   Geant Monthly             ●  45%     2 tasks overdue           │
│   Aswaaq Monthly            ●  80%     on track                  │
│                                                                  │
│                                                                  │
│   Money                                                          │
│   ─────                                                          │
│   Outstanding    AED 107,586                                     │
│                                                                  │
│   INV-1451       7,350       ●  90+ days     escalate            │
│   INV-1409       100,236     ●  31-60 days   follow-up sent      │
│   INV-1520       45,000      ●  current      due Feb 15          │
│                                                                  │
│                                                                  │
│   Recent                                                         │
│   ──────                                                         │
│   Feb 4    GMG Campaign Review (meeting)                         │
│   Feb 2    GMG Campaign Feedback (email)                         │
│   Jan 30   Feedback on Deliverables (email)                      │
│                                                                  │
│                                                                  │
│   ┌────────────────┐  ┌────────────────┐                        │
│   │ Escalate AR    │  │ Email client   │                        │
│   └────────────────┘  └────────────────┘                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

### CASH

Financial position. Answers: "Where's my money and what needs collection?"

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ← Home                                                  Cash   │
│                                                                  │
│                                                                  │
│   AED 276,466                                                    │
│   Outstanding                                                    │
│                                                                  │
│                                                                  │
│   Aging                                                          │
│   ─────                                                          │
│                                                                  │
│   Current    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━           63.5K   │
│   1-30       ━━━━━━━━━━━━━━                             26.7K   │
│   31-60      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  132.5K   │
│   61-90      ━━━━━━━━━━━━━━━━━━━━━━                     46.4K   │
│   90+        ━━━━━                                       7.4K   │
│                                                                  │
│                                                                  │
│   Collection queue                                               │
│   ────────────────                                               │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  Supercare              AED 75,245          ● 61-90 days │  │
│   │  3 invoices · no response to emails · call needed        │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  GMG                    AED 107,586         ● 31-60 days │  │
│   │  2 invoices · 1 at 90+ days · escalate oldest            │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  ASICS                  AED 26,675          ● 1-30 days  │  │
│   │  1 invoice · first reminder                              │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### Attention Card

```
Properties:
  entity:         string    (e.g., "GMG Ramadan Campaign")
  situation:      string    (what's wrong)
  recommendation: string    (what A suggests)
  signal:         critical | warning | info

States:
  default:        bg elevated
  hover:          bg elevated + 8% white
  active:         border left brand

Behavior:
  click:          opens situation detail
  keyboard:       enter/space activates
```

### Health Indicator

```
Properties:
  score:          number (0-100)
  trend:          up | down | stable

Rendering:
  >70:            green dot
  50-70:          amber dot
  <50:            red dot

  trend up:       ↑ suffix
  trend down:     ↓ suffix
```

### Progress Bar

```
Properties:
  value:          number (0-100)
  status:         on-track | at-risk | blocked

Rendering:
  height:         4px
  track:          tertiary @ 20%
  fill:           status color
  radius:         2px
```

### Action Button

```
Variants:
  primary:        brand bg, white text
  secondary:      transparent bg, border, secondary text
  ghost:          transparent, no border, secondary text

States:
  default
  hover:          darken/lighten 10%
  active:         darken/lighten 20%
  disabled:       50% opacity

Sizes:
  default:        12px vertical, 16px horizontal padding
  small:          8px vertical, 12px horizontal padding
```

---

## Interaction Patterns

### Navigation

- Back button always returns to previous context
- Quick nav on home provides lateral movement
- Clicking any entity opens its detail view
- No deep nesting—max 2 levels from home

### Actions

- Primary action is always visible
- Secondary actions in row, max 3 visible
- Confirmation required for external actions (send email, make call)
- Success/failure feedback inline

### Transitions

- Screen transitions: 200ms ease-out slide
- Card expansions: 150ms ease-out
- Hover states: 100ms
- No decorative animation

---

## Data Mapping

### Attention Stack

Source: `resolution_queue` joined with entities
Ranking: `priority` (1 = highest), then `created_at`
Limit: 5 items max on home
Content generation: A synthesizes entity state into situation + recommendation

### Client Health

Source: `clients.health_score` with breakdown from `client360_page10.py`
Sub-scores: delivery, finance, responsiveness, commitment, capacity
Trend: compare to `client_health_log` 7 days ago

### Project Status

Source: `projects` joined with `tasks`
Health: derived from `slip_risk_score` thresholds
Progress: `completion_pct` from task counts

### Cash Position

Source: `invoices` where status in (sent, overdue)
Aging: `aging_bucket` from normalizer
Collection queue: sorted by aging severity then amount

---

## Confidence Display

When data confidence is degraded:
- Show indicator next to affected metrics
- Tooltip explains what's missing
- Never hide the data—show it with caveat

```
72.5 ●◐  ← half-filled circle indicates degraded confidence
```

---

## Responsive Behavior

### Desktop (≥1200px)
- Full layout as specified
- Quick nav in single row

### Tablet (768-1199px)
- Quick nav wraps to 2x2
- Cards stack vertically

### Mobile (<768px)
- Single column
- Bottom tab navigation replaces quick nav
- Details as full-screen overlays

---

*End of specification*
