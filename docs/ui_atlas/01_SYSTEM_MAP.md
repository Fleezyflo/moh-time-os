# 01_SYSTEM_MAP.md — MOH Time OS Data Atlas

> Phase A Deliverable | Generated: 2026-02-04

---

## 1. Repository Location

```
REPO_ROOT: /Users/molhamhomsi/clawd/moh_time_os
```

---

## 2. Runtime Database

```
DB_PATH: /Users/molhamhomsi/clawd/moh_time_os/data/state.db
DB_SIZE: ~11 MB
DB_MODE: WAL (Write-Ahead Logging)
```

The canonical runtime database is `data/state.db`. All collectors, normalizers, gates, and snapshot generators read/write to this single database.

### Database Connection Pattern

All modules use the pattern:
```python
DB_PATH = Path(__file__).parent.parent / "data" / "state.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys=ON")
```

---

## 3. Table Inventory (36 tables + 1 view)

| Table | Row Count | Description |
|-------|-----------|-------------|
| `actions` | 0 | Pending/executed system actions |
| `asana_project_map` | varies | Asana GID → project_id mapping |
| `asana_user_map` | varies | Asana GID → team_member_id mapping |
| `brands` | 21 | Client brands (child of clients) |
| `capacity_lanes` | varies | Work lanes (ops, finance, creative, etc.) |
| `client_health_log` | varies | Time-series client health scores |
| `client_identities` | 25 | Email/domain → client mapping for linking |
| `client_projects` | varies | M:N link table (legacy, mostly unused) |
| `clients` | 190 | Client entities (master data) |
| `commitments` | 3 | Extracted promises/requests from comms |
| `communications` | 488 | Emails from Gmail |
| `cycle_logs` | 425 | Autonomous loop execution logs |
| `decisions` | 2 | Logged system decisions |
| `dismissed_moves` | varies | User-dismissed move suggestions |
| `events` | 173 | Calendar events (Google Calendar) |
| `feedback` | 0 | User feedback on decisions/insights |
| `insights` | 0 | System-generated insights |
| `invoices` | 34 | AR invoices (from Xero) |
| `item_history` | 0 | Audit trail for items |
| `items` | (VIEW) | Unified view over tasks |
| `lanes` | varies | Alternative lane storage |
| `meet_attendance` | 0 | Google Meet attendance data |
| `notifications` | 2,529 | System notifications sent |
| `patterns` | 0 | Detected behavior patterns |
| `pending_actions` | 0 | Actions awaiting approval |
| `people` | varies | Contact/person records |
| `projects` | 100 | Projects (Asana + manual) |
| `resolution_queue` | 3,950 | Items needing human resolution |
| `resolved_queue_items` | varies | Resolved queue items (audit) |
| `snoozed_moves` | varies | User-snoozed move suggestions |
| `sync_state` | 5 | Collector sync timestamps |
| `tasks` | 3,761 | Tasks (Google Tasks + Asana) |
| `team_capacity` | varies | Computed team capacity per person |
| `team_events` | varies | Team calendar events |
| `team_members` | 31 | Team member registry |
| `time_blocks` | 0 | Scheduled time blocks |
| `time_debt` | 0 | Accumulated time debt per lane |

---

## 4. Entrypoint Modules

### 4.1 Autonomous Loop (Primary Runtime)

```
lib/autonomous_loop.py
```

The autonomous loop is the main runtime. It executes in cycles:

```
PHASE ORDER:
1. COLLECT → collectors/orchestrator.py (sync all sources)
2. NORMALIZE → lib/normalizer.py (derive link statuses)
3. GATES → lib/gates.py (check data integrity)
4. RESOLUTION → lib/resolution_queue.py (queue issues)
5. SNAPSHOT → lib/agency_snapshot/generator.py (build UI data)
6. MOVES → lib/moves.py (generate action suggestions)
7. NOTIFY → (send notifications if configured)
```

### 4.2 Collectors (Data Ingestion)

```
lib/collectors/orchestrator.py    # Orchestrates all collectors
lib/collectors/tasks.py           # Google Tasks
lib/collectors/calendar.py        # Google Calendar
lib/collectors/gmail.py           # Gmail (via gog CLI)
lib/collectors/asana.py           # Asana projects/tasks
lib/collectors/asana_sync.py      # Detailed Asana sync
lib/collectors/xero.py            # Xero invoices
lib/collectors/team_calendar.py   # Team calendar aggregation
```

### 4.3 Normalizer (Derived Fields)

```
lib/normalizer.py
```

Derives:
- `projects.client_id` from brand chain
- `tasks.brand_id`, `client_id`, `project_link_status`, `client_link_status`
- `communications.from_domain`, `client_id`, `link_status`
- `invoices.aging_bucket`

### 4.4 Gates (Data Quality)

```
lib/gates.py
```

Evaluates:
- `data_integrity` (6 invariants)
- `project_brand_required`
- `project_brand_consistency`
- `project_client_populated`
- `internal_project_client_null`
- `client_coverage` (≥80%)
- `commitment_ready` (≥50%)
- `capacity_baseline`
- `finance_ar_coverage` (≥95%)
- `finance_ar_clean`

### 4.5 Snapshot Generator (UI Data)

```
lib/agency_snapshot/generator.py
lib/agency_snapshot/scoring.py      # BaseScore, ModeWeights, Eligibility
lib/agency_snapshot/delivery.py     # Slip risk, project status
lib/agency_snapshot/client360.py    # Client health, relationship
lib/agency_snapshot/cash_ar.py      # AR analysis
lib/agency_snapshot/comms_commitments.py  # Thread/commitment analysis
lib/agency_snapshot/capacity_command_page7.py
lib/agency_snapshot/client360_page10.py
lib/agency_snapshot/comms_commitments_page11.py
lib/agency_snapshot/cash_ar_page12.py
lib/agency_snapshot/confidence.py   # Trust state model
lib/agency_snapshot/deltas.py       # Change detection
```

### 4.6 Moves Engine (Action Suggestions)

```
lib/moves.py
lib/move_executor.py
```

### 4.7 Status Engine (Lifecycle Management)

```
lib/status_engine.py
```

Manages task status transitions with validation.

### 4.8 Additional Modules

```
lib/health.py                 # System health checks
lib/governance.py             # Domain mode (observe/propose/execute)
lib/priority_engine.py        # Priority scoring
lib/resolution_queue.py       # Issue queue management
lib/commitment_extractor.py   # Extract promises from comms
lib/build_client_identities.py  # Populate identity registry
lib/build_team_registry.py    # Populate team members
lib/lane_assigner.py          # Assign lanes to tasks
lib/link_projects.py          # Link projects to clients
```

---

## 5. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                              │
├─────────────────────────────────────────────────────────────────┤
│  Google Tasks │ Google Calendar │ Gmail │ Asana │ Xero          │
└───────┬───────────────┬─────────────┬───────┬───────┬───────────┘
        │               │             │       │       │
        ▼               ▼             ▼       ▼       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    COLLECTORS (lib/collectors/)                  │
│  TasksCollector │ CalendarCollector │ GmailCollector │          │
│  AsanaCollector │ XeroCollector │ TeamCalendarCollector         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STATE STORE (data/state.db)                   │
│  tasks │ events │ communications │ projects │ invoices          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NORMALIZER (lib/normalizer.py)                │
│  Derives: client_id, brand_id, link_status, aging_bucket        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GATES (lib/gates.py)                          │
│  data_integrity │ client_coverage │ finance_ar_coverage │ ...   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SNAPSHOT GENERATOR                            │
│  (lib/agency_snapshot/generator.py)                              │
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ DeliveryEng │ │ Client360   │ │ CashAR      │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ CommsCommit │ │ CapacityCmd │ │ ScoringEng  │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    agency_snapshot.json                          │
│  (output/agency_snapshot.json → dashboard/agency_snapshot.json) │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DASHBOARD (dashboard/app.py)                  │
│  Flask app serving Jinja2 templates                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Configuration Files

```
config/sources.yaml        # Collector enable/disable and intervals
config/domains.yaml        # Domain governance modes
config/vip.yaml            # VIP registry
config/lanes.yaml          # Lane definitions
```

---

## 7. Output Artifacts

```
output/agency_snapshot.json          # Current snapshot
output/previous_snapshot.json        # Previous snapshot (for deltas)
output/snapshot_history/             # Historical snapshots
dashboard/agency_snapshot.json       # Symlink/copy for dashboard
```

---

## 8. Database Relationships (Key FKs)

```
brands.client_id → clients.id
projects.brand_id → brands.id
projects.client_id → clients.id (derived via brand)
tasks.project_id → projects.id
tasks.brand_id → brands.id (derived)
tasks.client_id → clients.id (derived)
tasks.assignee_id → team_members.id
communications.client_id → clients.id (derived via identity match)
invoices.client_id → clients.id
invoices.brand_id → brands.id
invoices.project_id → projects.id
commitments.source_id → communications.id
commitments.client_id → clients.id
commitments.task_id → tasks.id
client_identities.client_id → clients.id
client_health_log.client_id → clients.id
resolution_queue → (entity_type, entity_id) polymorphic
```

---

## 9. Freshness Expectations

| Data Type | Source | Sync Interval | Staleness Threshold |
|-----------|--------|---------------|---------------------|
| Tasks | Google Tasks | 5 min | 15 min |
| Tasks | Asana | 5 min | 15 min |
| Calendar | Google Calendar | 1 min | 5 min |
| Emails | Gmail | 2 min | 10 min |
| Invoices | Xero | 5 min | 1 hour |
| Derived fields | Normalizer | Per cycle | 5 min |
| Gates | Per cycle | Per cycle | 5 min |
| Snapshot | Per cycle | Per cycle | 5 min |

---

*End of 01_SYSTEM_MAP.md*
