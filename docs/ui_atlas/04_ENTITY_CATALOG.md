# 04_ENTITY_CATALOG.md — Canonical Entity Model

> Phase B Deliverable | Generated: 2026-02-04

---

## Overview

This catalog defines the canonical entity model for UI design. Each entity includes:
- Description and UI meaning
- Primary key and foreign keys
- Lifecycle states
- Freshness expectations
- Relationships

---

## 1. clients

**Description:** Master client/customer records. The top-level entity for external relationships.

**UI Meaning:** Who we work for. Anchor for all financial (AR), delivery (projects), and communication data. Client health drives relationship management.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | None (top-level) |
| **Children** | brands, projects, invoices, communications (via FK) |
| **Row Count** | 190 |
| **Source** | Xero (via collector), manual entry |

### Lifecycle States

| State | Description | Transition |
|-------|-------------|------------|
| `active` | Active client relationship | → churned, dormant |
| `dormant` | No recent activity | → active, churned |
| `churned` | Relationship ended | → active (rare) |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `name` | TEXT | Display name |
| `tier` | TEXT | VIP badge ('A', 'B', 'C') |
| `health_score` | REAL | Health indicator (0-100) |
| `financial_ar_outstanding` | REAL | AR badge |
| `financial_ar_aging` | TEXT | Aging alert |
| `relationship_health` | TEXT | Status color |
| `relationship_trend` | TEXT | Trend arrow |

### Freshness

- **Source Sync:** Xero every 5 minutes
- **Staleness Threshold:** 1 hour
- **Health Recalc:** Every cycle (~5 min)

---

## 2. brands

**Description:** Client sub-brands. Groups projects under a client.

**UI Meaning:** Organizational unit for project grouping. Some clients have multiple brands (e.g., GMG → Monoprix, Geant, Aswaaq).

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `client_id` → clients.id |
| **Children** | projects (via brand_id) |
| **Row Count** | 21 |
| **Source** | Manual setup |

### Lifecycle States

Brands don't have explicit lifecycle. They exist or don't.

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `name` | TEXT | Display name |
| `client_id` | TEXT | Parent client link |

### Freshness

Static reference data. Updated manually.

---

## 3. projects

**Description:** Work projects. Container for tasks. May be linked to client/brand or internal.

**UI Meaning:** Primary delivery unit. Project health drives delivery dashboards. The "what are we working on" entity.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `brand_id` → brands.id, `client_id` → clients.id |
| **Children** | tasks (via project_id) |
| **Row Count** | 100 |
| **Source** | Asana collector, manual |

### Lifecycle States

| State | Description | Transition |
|-------|-------------|------------|
| `active` | In progress | → completed, on_hold |
| `on_hold` | Paused | → active, completed |
| `completed` | Finished | → archived |
| `archived` | Historical | Terminal |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `name` | TEXT | Project title |
| `is_internal` | INTEGER | Internal badge (no client) |
| `type` | TEXT | 'project' vs 'retainer' |
| `status` | TEXT | Status chip |
| `health` | TEXT | Health color (green/yellow/red) |
| `deadline` | TEXT | Due date display |
| `tasks_total` | INTEGER | Task count |
| `tasks_done` | INTEGER | Progress numerator |
| `completion_pct` | REAL | Progress bar |
| `owner` | TEXT | Owner avatar/name |
| `days_to_deadline` | INTEGER | Countdown |

### Freshness

- **Source Sync:** Asana every 5 minutes
- **Staleness Threshold:** 15 minutes
- **Metrics Recalc:** Every cycle

---

## 4. tasks

**Description:** Work items. The atomic unit of work tracked in the system.

**UI Meaning:** What needs to be done. Tasks drive urgency, capacity, and delivery metrics. The core operational entity.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `project_id` → projects.id, `brand_id` → brands.id, `client_id` → clients.id, `assignee_id` → team_members.id |
| **Row Count** | 3,761 |
| **Source** | Google Tasks, Asana |

### Lifecycle States

| State | Description | Transition |
|-------|-------------|------------|
| `active` | To be done | → done, blocked, overdue |
| `pending` | Not started | → active, blocked |
| `blocked` | Can't proceed | → active, done |
| `overdue` | Past due date | → done |
| `done` | Completed | Terminal |

### Link Statuses

| Field | Values | Meaning |
|-------|--------|---------|
| `project_link_status` | linked, partial, unlinked | Project chain completeness |
| `client_link_status` | linked, unlinked, n/a | Client chain completeness |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `title` | TEXT | Task name |
| `status` | TEXT | Status chip |
| `priority` | INTEGER | Priority indicator (0-100) |
| `due_date` | TEXT | Due date/countdown |
| `assignee` | TEXT | Assignee avatar/name |
| `lane` | TEXT | Lane tag |
| `urgency` | TEXT | Urgency indicator |
| `duration_min` | INTEGER | Effort estimate |

### Freshness

- **Source Sync:** Every 5 minutes (both sources)
- **Staleness Threshold:** 15 minutes
- **Derived Fields:** Updated by normalizer every cycle

---

## 5. communications

**Description:** Emails from Gmail. External communication records.

**UI Meaning:** Client/stakeholder interactions. Drives response urgency, commitment tracking, and relationship health.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `client_id` → clients.id |
| **Children** | commitments (via source_id) |
| **Row Count** | 488 |
| **Source** | Gmail collector |

### Link Statuses

| Field | Values | Meaning |
|-------|--------|---------|
| `link_status` | linked, unlinked | Whether matched to a client |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `subject` | TEXT | Email subject |
| `from_email` | TEXT | Sender |
| `from_name` | TEXT | Sender display name |
| `snippet` | TEXT | Preview |
| `received_at` | TEXT | Timestamp |
| `is_unread` | INTEGER | Unread badge |
| `is_starred` | INTEGER | Star indicator |
| `requires_response` | INTEGER | Action needed badge |
| `age_hours` | REAL | "2h ago" display |

### Freshness

- **Source Sync:** Every 2 minutes
- **Staleness Threshold:** 10 minutes
- **Body Fetch:** Rate-limited, may lag

---

## 6. commitments

**Description:** Promises and requests extracted from communications.

**UI Meaning:** Tracked obligations. "We said we'd do X" or "They asked for Y". Drives relationship trust.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `source_id` → communications.id, `client_id` → clients.id, `task_id` → tasks.id |
| **Row Count** | 3 |
| **Source** | commitment_extractor.py |

### Lifecycle States

| State | Description | Transition |
|-------|-------------|------------|
| `open` | Not yet fulfilled | → fulfilled, broken, cancelled |
| `fulfilled` | Completed successfully | Terminal |
| `broken` | Failed to deliver | Terminal |
| `cancelled` | No longer relevant | Terminal |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `text` | TEXT | Commitment text |
| `type` | TEXT | 'promise' (we made) vs 'request' (they made) |
| `deadline` | TEXT | Due date |
| `status` | TEXT | Status chip |
| `confidence` | REAL | Extraction confidence |

### Freshness

- **Extraction:** After Gmail sync
- **Staleness Threshold:** 1 hour
- **Note:** Currently only 3 commitments extracted

---

## 7. invoices

**Description:** AR invoices from Xero.

**UI Meaning:** Money owed. Drives cash flow dashboards, collection actions, and financial health.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `client_id` → clients.id, `brand_id` → brands.id, `project_id` → projects.id |
| **Row Count** | 34 |
| **Source** | Xero collector |

### Lifecycle States

| State | Description | Transition |
|-------|-------------|------------|
| `draft` | Not sent | → sent, void |
| `sent` | Awaiting payment | → paid, overdue, void |
| `overdue` | Past due | → paid, void |
| `paid` | Payment received | Terminal |
| `void` | Cancelled | Terminal |

### Aging Buckets

| Bucket | Meaning | UI Color |
|--------|---------|----------|
| `current` | Not overdue | Green |
| `1-30` | 1-30 days overdue | Yellow |
| `31-60` | 31-60 days overdue | Orange |
| `61-90` | 61-90 days overdue | Red |
| `90+` | >90 days overdue | Dark Red |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `external_id` | TEXT | Invoice number |
| `client_name` | TEXT | Client display |
| `amount` | REAL | Amount due |
| `currency` | TEXT | Currency code |
| `due_date` | TEXT | Due date |
| `status` | TEXT | Status chip |
| `aging_bucket` | TEXT | Aging badge |

### Freshness

- **Source Sync:** Every 5 minutes
- **Staleness Threshold:** 1 hour
- **Aging Recalc:** Every cycle by normalizer

---

## 8. team_members

**Description:** Internal team members who do work.

**UI Meaning:** Who does the work. Assignees for tasks. Capacity calculation targets.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | None |
| **Referenced By** | tasks.assignee_id, asana_user_map.team_member_id |
| **Row Count** | 31 |
| **Source** | build_team_registry.py (from task assignees) |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `name` | TEXT | Display name |
| `email` | TEXT | Contact |
| `default_lane` | TEXT | Default work category |

### Freshness

- Built from task assignees
- Updated when new assignees appear

---

## 9. events

**Description:** Calendar events from Google Calendar.

**UI Meaning:** Time commitments. What's on the schedule. Drives prep and capacity.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `linked_task_id` → tasks.id |
| **Row Count** | 173 |
| **Source** | Calendar collector |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `title` | TEXT | Event name |
| `start_time` | TEXT | Start timestamp |
| `end_time` | TEXT | End timestamp |
| `location` | TEXT | Location display |
| `attendees` | TEXT | Attendee list (JSON) |
| `status` | TEXT | confirmed/tentative/cancelled |
| `has_conflict` | INTEGER | Conflict warning |

### Freshness

- **Source Sync:** Every 1 minute
- **Staleness Threshold:** 5 minutes

---

## 10. capacity_lanes

**Description:** Work lane definitions with capacity limits.

**UI Meaning:** Categories of work. How capacity is organized and tracked.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Referenced By** | tasks.lane, time_debt.lane |
| **Row Count** | Varies |
| **Source** | Manual setup |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `name` | TEXT | Lane name |
| `display_name` | TEXT | Friendly name |
| `weekly_hours` | INTEGER | Capacity |
| `buffer_pct` | REAL | Buffer percentage |
| `color` | TEXT | Lane color |

### Freshness

Static reference data.

---

## 11. time_blocks

**Description:** Scheduled time blocks for tasks.

**UI Meaning:** Calendar-view of allocated work time.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `task_id` → tasks.id |
| **Row Count** | 0 (not actively used) |
| **Source** | scheduling_engine.py |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `date` | TEXT | Block date |
| `start_time` | TEXT | Start time |
| `end_time` | TEXT | End time |
| `lane` | TEXT | Lane |
| `is_protected` | INTEGER | Lock indicator |

---

## 12. resolution_queue

**Description:** Items needing human resolution.

**UI Meaning:** The "inbox" of issues. What needs attention that the system can't auto-resolve.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **References** | `entity_type` + `entity_id` polymorphic |
| **Row Count** | 3,950 |
| **Source** | resolution_queue.py |

### Issue Types

| Type | Description |
|------|-------------|
| `missing_project` | Task without project |
| `missing_client` | Project without client |
| `overdue` | Overdue task |
| `blocked` | Blocked task |
| `stale` | No activity for N days |
| `unlinked_comm` | Communication not matched |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `entity_type` | TEXT | Type badge |
| `entity_id` | TEXT | Link to entity |
| `issue_type` | TEXT | Issue description |
| `priority` | INTEGER | Priority (1=highest) |
| `context` | TEXT | Additional context |
| `resolved_at` | TEXT | Resolution timestamp |

### Freshness

- Updated every cycle
- Items created when issues detected

---

## 13. pending_actions

**Description:** System-proposed actions awaiting approval.

**UI Meaning:** Actions the system wants to take but needs human approval for.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Row Count** | 0 |
| **Source** | governance.py, move_executor.py |

### Lifecycle States

| State | Description |
|-------|-------------|
| `pending` | Awaiting decision |
| `approved` | Approved, awaiting execution |
| `rejected` | Rejected by human |
| `executed` | Successfully executed |
| `expired` | Timed out |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `action_type` | TEXT | Action description |
| `payload` | TEXT | Action details |
| `risk_level` | TEXT | Risk indicator |
| `status` | TEXT | Status chip |
| `proposed_at` | TEXT | Timestamp |

---

## 14. decisions

**Description:** Logged system decisions.

**UI Meaning:** Audit trail. What the system decided and why.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Row Count** | 2 |
| **Source** | governance.py |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `decision_type` | TEXT | Decision category |
| `description` | TEXT | What was decided |
| `rationale` | TEXT | Why |
| `confidence` | REAL | Confidence level |
| `outcome` | TEXT | Result |

---

## 15. notifications

**Description:** System notifications sent to user.

**UI Meaning:** Alert history. What the system communicated.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Row Count** | 2,529 |
| **Source** | Various |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `type` | TEXT | Notification type |
| `priority` | TEXT | Priority level |
| `title` | TEXT | Notification title |
| `body` | TEXT | Content |
| `read_at` | TEXT | Read status |
| `acted_on_at` | TEXT | Action taken |

---

## 16. cycle_logs

**Description:** Autonomous loop execution logs.

**UI Meaning:** System health. Performance and timing of data cycles.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Row Count** | 425 |
| **Source** | autonomous_loop.py |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `cycle_number` | INTEGER | Cycle counter |
| `phase` | TEXT | Phase name |
| `duration_ms` | REAL | Performance metric |
| `created_at` | TEXT | Timestamp |

---

## 17. client_identities

**Description:** Email/domain → client mapping for linking communications.

**UI Meaning:** How the system knows which emails belong to which clients.

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `client_id` → clients.id |
| **Row Count** | 25 |
| **Source** | build_client_identities.py |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `identity_type` | TEXT | 'email' or 'domain' |
| `identity_value` | TEXT | The email/domain |
| `client_id` | TEXT | Matched client |

---

## 18. client_health_log

**Description:** Historical client health scores.

**UI Meaning:** Health trend data for charts. "How has this client's health changed?"

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `id` (TEXT) |
| **Foreign Keys** | `client_id` → clients.id |
| **Row Count** | Varies |
| **Source** | Health scoring engine |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `health_score` | INTEGER | Score at time |
| `factors` | TEXT | Factor breakdown |
| `computed_at` | TEXT | Timestamp |

---

## 19. sync_state

**Description:** Collector sync timestamps.

**UI Meaning:** Data freshness indicators. "When was this data last updated?"

| Attribute | Value |
|-----------|-------|
| **Primary Key** | `source` (TEXT) |
| **Row Count** | 5 |
| **Source** | Collectors |

### Key Fields for UI

| Field | Type | UI Usage |
|-------|------|----------|
| `source` | TEXT | Collector name |
| `last_sync` | TEXT | Last attempt |
| `last_success` | TEXT | Last success |
| `items_synced` | INTEGER | Count |
| `error` | TEXT | Error message |

---

## Entity Relationship Summary

```
clients
├── brands
│   └── projects
│       └── tasks
├── projects (direct)
│   └── tasks
├── invoices
├── communications
│   └── commitments
└── client_identities

team_members
├── tasks (assignee_id)
└── asana_user_map

events
└── tasks (linked_task_id)

capacity_lanes
├── time_blocks
└── time_debt

resolution_queue → (polymorphic entity references)
pending_actions → (polymorphic entity references)
```

---

*End of 04_ENTITY_CATALOG.md*
