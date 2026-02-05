# MOH TIME OS — SURGICAL DESIGN SPECIFICATION

**Date:** 2026-02-01  
**Status:** DRAFT  
**Standard:** Forensic. Every field. Every query. Every pixel.

---

# PART 1: DATA ARCHITECTURE

## 1.1 Database Schema (Complete)

### Table: `tasks`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `asana_{gid}` or `manual_{uuid}` |
| `source` | TEXT NOT NULL | Literal | `asana` \| `manual` |
| `source_id` | TEXT | Asana | Original Asana GID |
| `title` | TEXT NOT NULL | Asana `name` | Task title |
| `status` | TEXT NOT NULL | Mapped | `pending` \| `in_progress` \| `blocked` \| `completed` \| `cancelled` |
| `priority` | INTEGER | Computed | 0-100, computed by PriorityAnalyzer |
| `priority_reasons` | TEXT (JSON) | Computed | `["Overdue by 2 days", "High priority tag"]` |
| `due_date` | TEXT | Asana `due_on` | `YYYY-MM-DD` |
| `due_time` | TEXT | Asana `due_at` | `HH:MM:SS` |
| `assignee_id` | TEXT | FK → people.id | Who owns this task |
| `assignee_name` | TEXT | Asana | Denormalized for display |
| `delegated_by` | TEXT | FK → people.id | Who delegated (null if not delegated) |
| `delegated_at` | TEXT | System | When delegated |
| `project_id` | TEXT | FK → projects.id | Parent project |
| `project_name` | TEXT | Asana | Denormalized for display |
| `lane` | TEXT | Mapped/Manual | `ops` \| `client` \| `finance` \| `music` \| `admin` \| `people` \| `governance` |
| `tags` | TEXT (JSON) | Asana | `["urgent", "client-x"]` |
| `dependencies` | TEXT (JSON) | Asana | `["asana_123", "asana_456"]` |
| `blockers` | TEXT (JSON) | Manual/Parsed | `["Waiting on client approval"]` |
| `notes` | TEXT | Asana `notes` | Task description/notes |
| `is_supervised` | INTEGER | Computed | 1 if assigned to team member (not Moh) |
| `last_activity_at` | TEXT | Asana | Last modification timestamp |
| `stale_days` | INTEGER | Computed | Days since last_activity_at |
| `created_at` | TEXT NOT NULL | Asana/System | ISO timestamp |
| `updated_at` | TEXT NOT NULL | System | ISO timestamp |
| `synced_at` | TEXT | System | Last sync timestamp |

**Indexes:**
```sql
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_due ON tasks(due_date);
CREATE INDEX idx_tasks_priority ON tasks(priority DESC);
CREATE INDEX idx_tasks_lane ON tasks(lane);
CREATE INDEX idx_tasks_delegated ON tasks(delegated_by) WHERE delegated_by IS NOT NULL;
```

---

### Table: `events`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `gcal_{id}` |
| `source` | TEXT NOT NULL | Literal | `google_calendar` |
| `source_id` | TEXT | Google | Original event ID |
| `calendar_id` | TEXT | Google | Which calendar |
| `title` | TEXT NOT NULL | Google `summary` | Event title |
| `start_time` | TEXT NOT NULL | Google | ISO timestamp |
| `end_time` | TEXT | Google | ISO timestamp |
| `duration_minutes` | INTEGER | Computed | End - Start in minutes |
| `all_day` | INTEGER | Google | 1 if all-day event |
| `location` | TEXT | Google | Location string |
| `description` | TEXT | Google | Event description |
| `attendees` | TEXT (JSON) | Google | `[{"email": "x@y.com", "name": "X", "status": "accepted"}]` |
| `attendee_count` | INTEGER | Computed | Number of attendees |
| `organizer_email` | TEXT | Google | Who created it |
| `is_organizer` | INTEGER | Computed | 1 if Moh is organizer |
| `status` | TEXT | Google | `confirmed` \| `tentative` \| `cancelled` |
| `recurrence` | TEXT | Google | RRULE if recurring |
| `conference_url` | TEXT | Google | Meet/Zoom link |
| `has_conflict` | INTEGER | Computed | 1 if overlaps another event |
| `conflict_with` | TEXT (JSON) | Computed | `["gcal_xyz"]` IDs of conflicting events |
| `prep_notes` | TEXT | Manual | Preparation notes |
| `created_at` | TEXT NOT NULL | System | ISO timestamp |
| `updated_at` | TEXT NOT NULL | System | ISO timestamp |
| `synced_at` | TEXT | System | Last sync timestamp |

**Indexes:**
```sql
CREATE INDEX idx_events_start ON events(start_time);
CREATE INDEX idx_events_date ON events(date(start_time));
CREATE INDEX idx_events_calendar ON events(calendar_id);
CREATE INDEX idx_events_conflict ON events(has_conflict) WHERE has_conflict = 1;
```

---

### Table: `communications`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `gmail_{id}` |
| `source` | TEXT NOT NULL | Literal | `gmail` |
| `source_id` | TEXT | Gmail | Original message ID |
| `thread_id` | TEXT | Gmail | Thread ID for grouping |
| `from_email` | TEXT | Gmail | Sender email |
| `from_name` | TEXT | Gmail | Sender display name |
| `from_domain` | TEXT | Computed | Domain part of email |
| `to_emails` | TEXT (JSON) | Gmail | `["moh@hrmny.co"]` |
| `cc_emails` | TEXT (JSON) | Gmail | CC list |
| `subject` | TEXT | Gmail | Email subject |
| `snippet` | TEXT | Gmail | First ~200 chars |
| `body_text` | TEXT | Gmail | Plain text body |
| `labels` | TEXT (JSON) | Gmail | `["INBOX", "IMPORTANT"]` |
| `is_unread` | INTEGER | Gmail | 1 if unread |
| `is_starred` | INTEGER | Gmail | 1 if starred |
| `is_important` | INTEGER | Gmail | 1 if marked important |
| `priority` | INTEGER | Computed | 0-100 |
| `priority_reasons` | TEXT (JSON) | Computed | `["VIP sender", "Contains 'urgent'"]` |
| `sender_tier` | TEXT | Computed | `vip` \| `important` \| `normal` \| `low` |
| `requires_response` | INTEGER | Computed/Manual | 1 if needs reply |
| `response_urgency` | TEXT | Computed | `urgent` \| `normal` \| `low` |
| `expected_response_by` | TEXT | Computed | ISO timestamp |
| `processed` | INTEGER | Manual | 1 if handled |
| `processed_at` | TEXT | System | When marked processed |
| `action_taken` | TEXT | Manual | `replied` \| `delegated` \| `task_created` \| `ignored` |
| `linked_task_id` | TEXT | FK → tasks.id | If task was created from this |
| `received_at` | TEXT NOT NULL | Gmail | Original receive time |
| `age_hours` | REAL | Computed | Hours since received |
| `created_at` | TEXT NOT NULL | System | ISO timestamp |
| `synced_at` | TEXT | System | Last sync timestamp |

**Indexes:**
```sql
CREATE INDEX idx_comms_thread ON communications(thread_id);
CREATE INDEX idx_comms_from ON communications(from_email);
CREATE INDEX idx_comms_domain ON communications(from_domain);
CREATE INDEX idx_comms_unread ON communications(is_unread) WHERE is_unread = 1;
CREATE INDEX idx_comms_response ON communications(requires_response) WHERE requires_response = 1 AND processed = 0;
CREATE INDEX idx_comms_priority ON communications(priority DESC);
CREATE INDEX idx_comms_tier ON communications(sender_tier);
```

---

### Table: `projects`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `asana_{gid}` |
| `source` | TEXT NOT NULL | Literal | `asana` |
| `source_id` | TEXT | Asana | Original GID |
| `name` | TEXT NOT NULL | Asana | Project name |
| `status` | TEXT | Asana/Computed | `active` \| `on_hold` \| `completed` \| `archived` |
| `health` | TEXT | Computed | `green` \| `yellow` \| `red` |
| `health_reasons` | TEXT (JSON) | Computed | `["3 overdue tasks", "No activity 7 days"]` |
| `owner_id` | TEXT | FK → people.id | Project owner |
| `owner_name` | TEXT | Asana | Denormalized |
| `lane` | TEXT | Mapped | Primary lane |
| `client` | TEXT | Parsed/Manual | Client name if client project |
| `deadline` | TEXT | Asana/Manual | `YYYY-MM-DD` |
| `days_to_deadline` | INTEGER | Computed | Can be negative |
| `tasks_total` | INTEGER | Computed | Count of all tasks |
| `tasks_completed` | INTEGER | Computed | Count of done tasks |
| `tasks_overdue` | INTEGER | Computed | Count of overdue tasks |
| `tasks_blocked` | INTEGER | Computed | Count of blocked tasks |
| `completion_pct` | REAL | Computed | tasks_completed / tasks_total * 100 |
| `velocity_trend` | TEXT | Computed | `improving` \| `stable` \| `declining` |
| `blockers` | TEXT (JSON) | Aggregated | `["Waiting on assets", "Budget approval"]` |
| `next_milestone` | TEXT | Manual | Next key deliverable |
| `next_milestone_date` | TEXT | Manual | `YYYY-MM-DD` |
| `notes` | TEXT | Asana | Project description |
| `last_activity_at` | TEXT | Computed | Most recent task activity |
| `created_at` | TEXT NOT NULL | Asana | ISO timestamp |
| `updated_at` | TEXT NOT NULL | System | ISO timestamp |
| `synced_at` | TEXT | System | Last sync timestamp |

**Indexes:**
```sql
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_health ON projects(health);
CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_projects_lane ON projects(lane);
CREATE INDEX idx_projects_deadline ON projects(deadline);
```

**Health Calculation Logic:**
```python
def calculate_health(project):
    score = 100
    reasons = []
    
    # Overdue tasks penalty
    if project.tasks_overdue > 0:
        penalty = min(40, project.tasks_overdue * 10)
        score -= penalty
        reasons.append(f"{project.tasks_overdue} overdue tasks")
    
    # Blocked tasks penalty
    if project.tasks_blocked > 0:
        penalty = min(20, project.tasks_blocked * 5)
        score -= penalty
        reasons.append(f"{project.tasks_blocked} blocked tasks")
    
    # Deadline pressure
    if project.days_to_deadline is not None:
        if project.days_to_deadline < 0:
            score -= 30
            reasons.append(f"Past deadline by {abs(project.days_to_deadline)} days")
        elif project.days_to_deadline <= 7 and project.completion_pct < 80:
            score -= 20
            reasons.append(f"Deadline in {project.days_to_deadline} days, only {project.completion_pct:.0f}% complete")
    
    # Stale project
    if project.last_activity_days > 7:
        score -= 15
        reasons.append(f"No activity for {project.last_activity_days} days")
    
    # Determine health status
    if score >= 80:
        health = 'green'
    elif score >= 50:
        health = 'yellow'
    else:
        health = 'red'
    
    return health, reasons
```

---

### Table: `people`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `person_{uuid}` or email-based |
| `email` | TEXT UNIQUE | Asana/Config | Primary email |
| `name` | TEXT NOT NULL | Asana/Config | Display name |
| `role` | TEXT | Config | Job title/role |
| `team` | TEXT | Config | `core` \| `extended` \| `external` |
| `is_internal` | INTEGER | Config | 1 if HRMNY team |
| `is_vip` | INTEGER | Config | 1 if VIP contact |
| `tier` | TEXT | Config | `always_urgent` \| `important` \| `normal` |
| `company` | TEXT | Config/Parsed | Company name |
| `lanes_owned` | TEXT (JSON) | Config | `["ops", "finance"]` lanes they handle |
| `can_delegate_to` | INTEGER | Config | 1 if valid delegation target |
| `turnaround_days` | INTEGER | Config | Expected response time |
| `tasks_assigned` | INTEGER | Computed | Current task count |
| `tasks_overdue` | INTEGER | Computed | Overdue task count |
| `tasks_blocked` | INTEGER | Computed | Blocked task count |
| `last_task_completed` | TEXT | Computed | ISO timestamp |
| `last_communication` | TEXT | Computed | Last email interaction |
| `notes` | TEXT | Manual | Personal notes |
| `created_at` | TEXT NOT NULL | System | ISO timestamp |
| `updated_at` | TEXT NOT NULL | System | ISO timestamp |

**Indexes:**
```sql
CREATE INDEX idx_people_email ON people(email);
CREATE INDEX idx_people_team ON people(team);
CREATE INDEX idx_people_vip ON people(is_vip) WHERE is_vip = 1;
CREATE INDEX idx_people_delegate ON people(can_delegate_to) WHERE can_delegate_to = 1;
```

---

### Table: `delegations`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `del_{uuid}` |
| `task_id` | TEXT NOT NULL | FK → tasks.id | Delegated task |
| `delegated_to_id` | TEXT NOT NULL | FK → people.id | Who received |
| `delegated_to_name` | TEXT | Denormalized | Display name |
| `delegated_by_id` | TEXT NOT NULL | FK → people.id | Who delegated (usually Moh) |
| `delegated_at` | TEXT NOT NULL | System | ISO timestamp |
| `due_date` | TEXT | Copied | Expected completion |
| `status` | TEXT | Tracked | `active` \| `completed` \| `recalled` \| `escalated` |
| `days_active` | INTEGER | Computed | Days since delegated |
| `follow_up_needed` | INTEGER | Computed | 1 if stale |
| `follow_up_sent_at` | TEXT | System | Last reminder sent |
| `notes` | TEXT | Manual | Context provided |
| `completed_at` | TEXT | System | When completed |
| `created_at` | TEXT NOT NULL | System | ISO timestamp |
| `updated_at` | TEXT NOT NULL | System | ISO timestamp |

**Follow-up Logic:**
```python
def needs_follow_up(delegation):
    if delegation.status != 'active':
        return False
    
    days_active = delegation.days_active
    delegate = get_person(delegation.delegated_to_id)
    expected_turnaround = delegate.turnaround_days or 3
    
    # Follow up if past expected turnaround
    if days_active > expected_turnaround:
        # But not if we already followed up recently
        if delegation.follow_up_sent_at:
            days_since_followup = days_since(delegation.follow_up_sent_at)
            if days_since_followup < 2:
                return False
        return True
    
    return False
```

---

### Table: `insights`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `insight_{uuid}` |
| `type` | TEXT NOT NULL | System | `anomaly` \| `pattern` \| `recommendation` |
| `category` | TEXT | System | `tasks` \| `calendar` \| `communications` \| `projects` \| `team` |
| `severity` | TEXT | System | `critical` \| `warning` \| `info` |
| `title` | TEXT NOT NULL | System | Short description |
| `description` | TEXT | System | Detailed explanation |
| `data` | TEXT (JSON) | System | Supporting data |
| `affected_items` | TEXT (JSON) | System | `["asana_123", "gmail_456"]` related IDs |
| `suggested_action` | TEXT | System | What to do about it |
| `action_type` | TEXT | System | `complete` \| `delegate` \| `reschedule` \| `review` \| `custom` |
| `confidence` | REAL | System | 0.0 - 1.0 |
| `is_active` | INTEGER | System | 1 if still relevant |
| `is_dismissed` | INTEGER | Manual | 1 if user dismissed |
| `dismissed_at` | TEXT | System | When dismissed |
| `acted_on` | INTEGER | System | 1 if action taken |
| `acted_on_at` | TEXT | System | When acted on |
| `expires_at` | TEXT | System | Auto-dismiss after this |
| `created_at` | TEXT NOT NULL | System | ISO timestamp |

**Indexes:**
```sql
CREATE INDEX idx_insights_active ON insights(is_active, is_dismissed) WHERE is_active = 1 AND is_dismissed = 0;
CREATE INDEX idx_insights_type ON insights(type);
CREATE INDEX idx_insights_severity ON insights(severity);
CREATE INDEX idx_insights_category ON insights(category);
```

---

### Table: `decisions`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `id` | TEXT PK | Generated | `dec_{uuid}` |
| `domain` | TEXT NOT NULL | System | `tasks` \| `calendar` \| `email` \| `delegation` |
| `action_type` | TEXT NOT NULL | System | `create` \| `update` \| `delete` \| `send` \| `delegate` |
| `title` | TEXT NOT NULL | System | What it wants to do |
| `description` | TEXT | System | Detailed explanation |
| `target_id` | TEXT | System | ID of item being acted on |
| `target_type` | TEXT | System | `task` \| `event` \| `email` |
| `payload` | TEXT (JSON) NOT NULL | System | The actual action data |
| `rationale` | TEXT | System | Why system recommends this |
| `confidence` | REAL | System | 0.0 - 1.0 |
| `risk_level` | TEXT | System | `low` \| `medium` \| `high` |
| `status` | TEXT NOT NULL | System | `pending` \| `approved` \| `rejected` \| `executed` \| `failed` |
| `approved_at` | TEXT | System | When approved |
| `rejected_at` | TEXT | System | When rejected |
| `rejection_reason` | TEXT | Manual | Why rejected |
| `executed_at` | TEXT | System | When executed |
| `execution_result` | TEXT (JSON) | System | Result of execution |
| `error` | TEXT | System | Error if failed |
| `created_at` | TEXT NOT NULL | System | ISO timestamp |
| `updated_at` | TEXT NOT NULL | System | ISO timestamp |

**Indexes:**
```sql
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX idx_decisions_pending ON decisions(status) WHERE status = 'pending';
CREATE INDEX idx_decisions_domain ON decisions(domain);
```

---

### Table: `sync_state`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `source` | TEXT PK | System | `asana` \| `gmail` \| `calendar` \| `apollo` |
| `last_sync_at` | TEXT | System | Last successful sync |
| `last_sync_duration_ms` | INTEGER | System | How long it took |
| `last_sync_items` | INTEGER | System | Items processed |
| `last_error` | TEXT | System | Error if failed |
| `last_error_at` | TEXT | System | When error occurred |
| `consecutive_errors` | INTEGER | System | Error streak count |
| `is_healthy` | INTEGER | Computed | 1 if working |
| `next_sync_at` | TEXT | Computed | When next sync due |

---

## 1.2 Computed Views

### View: `priority_queue`

**Purpose:** Pre-computed priority ranking of all actionable items

```sql
CREATE VIEW priority_queue AS
SELECT 
    'task' as item_type,
    id,
    title,
    priority as score,
    priority_reasons as reasons,
    due_date,
    due_time,
    assignee_name,
    project_name,
    lane,
    status,
    source,
    source_id,
    CASE 
        WHEN due_date < date('now') THEN 'overdue'
        WHEN due_date = date('now') THEN 'due_today'
        WHEN due_date <= date('now', '+7 days') THEN 'due_this_week'
        ELSE 'future'
    END as urgency,
    created_at,
    updated_at
FROM tasks
WHERE status NOT IN ('completed', 'cancelled')

UNION ALL

SELECT
    'email' as item_type,
    id,
    subject as title,
    priority as score,
    priority_reasons as reasons,
    expected_response_by as due_date,
    NULL as due_time,
    from_name as assignee_name,
    NULL as project_name,
    NULL as lane,
    CASE WHEN processed = 1 THEN 'processed' ELSE 'pending' END as status,
    source,
    source_id,
    CASE
        WHEN age_hours > 48 THEN 'overdue'
        WHEN age_hours > 24 THEN 'due_today'
        ELSE 'recent'
    END as urgency,
    created_at,
    received_at as updated_at
FROM communications
WHERE requires_response = 1 AND processed = 0

ORDER BY score DESC, due_date ASC NULLS LAST;
```

### View: `team_workload`

```sql
CREATE VIEW team_workload AS
SELECT
    p.id,
    p.name,
    p.email,
    p.role,
    p.team,
    COUNT(t.id) as total_tasks,
    SUM(CASE WHEN t.status NOT IN ('completed', 'cancelled') THEN 1 ELSE 0 END) as active_tasks,
    SUM(CASE WHEN t.due_date < date('now') AND t.status NOT IN ('completed', 'cancelled') THEN 1 ELSE 0 END) as overdue_tasks,
    SUM(CASE WHEN t.status = 'blocked' THEN 1 ELSE 0 END) as blocked_tasks,
    MAX(CASE WHEN t.status = 'completed' THEN t.updated_at END) as last_completed_at
FROM people p
LEFT JOIN tasks t ON t.assignee_id = p.id
WHERE p.is_internal = 1
GROUP BY p.id, p.name, p.email, p.role, p.team;
```

### View: `daily_calendar`

```sql
CREATE VIEW daily_calendar AS
SELECT
    date(start_time) as event_date,
    COUNT(*) as event_count,
    SUM(duration_minutes) as total_minutes,
    SUM(CASE WHEN has_conflict = 1 THEN 1 ELSE 0 END) as conflict_count,
    GROUP_CONCAT(id) as event_ids
FROM events
WHERE status != 'cancelled'
GROUP BY date(start_time);
```

---

# PART 2: API SPECIFICATION

## 2.1 Base Configuration

```
Base URL: http://localhost:8420/api
Content-Type: application/json
```

## 2.2 Endpoint Specifications

---

### GET `/api/overview`

**Purpose:** Home page data - everything needed for at-a-glance view

**Response:**
```json
{
  "timestamp": "2026-02-01T17:30:00Z",
  "today": {
    "date": "2026-02-01",
    "day_name": "Saturday"
  },
  "alerts": [
    {
      "id": "insight_123",
      "severity": "critical",
      "title": "3 VIP emails awaiting response > 4 hours",
      "action_url": "/inbox?filter=vip"
    }
  ],
  "stats": {
    "tasks_due_today": 5,
    "tasks_overdue": 3,
    "emails_pending_response": 12,
    "team_blocked_items": 2,
    "pending_decisions": 1
  },
  "top_priorities": [
    {
      "item_type": "task",
      "id": "asana_123456",
      "title": "Submit VAT return",
      "score": 95,
      "reasons": ["Overdue by 1 day", "High priority"],
      "due_date": "2026-01-31",
      "project_name": "Finance",
      "source_url": "https://app.asana.com/0/123/456"
    }
    // ... top 5 items
  ],
  "upcoming_events": [
    {
      "id": "gcal_abc",
      "title": "Client call - Gargash",
      "start_time": "2026-02-01T18:00:00+04:00",
      "end_time": "2026-02-01T19:00:00+04:00",
      "duration_minutes": 60,
      "location": "Google Meet",
      "has_conflict": false
    }
    // ... next 3 events
  ],
  "sync_status": {
    "asana": {"healthy": true, "last_sync": "2026-02-01T17:28:00Z"},
    "gmail": {"healthy": true, "last_sync": "2026-02-01T17:29:00Z"},
    "calendar": {"healthy": true, "last_sync": "2026-02-01T17:29:00Z"}
  }
}
```

**Queries Used:**
```sql
-- Stats
SELECT COUNT(*) FROM tasks WHERE due_date = date('now') AND status NOT IN ('completed', 'cancelled');
SELECT COUNT(*) FROM tasks WHERE due_date < date('now') AND status NOT IN ('completed', 'cancelled');
SELECT COUNT(*) FROM communications WHERE requires_response = 1 AND processed = 0;
SELECT COUNT(*) FROM tasks WHERE status = 'blocked' AND assignee_id != '{moh_id}';
SELECT COUNT(*) FROM decisions WHERE status = 'pending';

-- Top priorities
SELECT * FROM priority_queue LIMIT 5;

-- Upcoming events
SELECT * FROM events 
WHERE start_time >= datetime('now') 
AND start_time <= datetime('now', '+24 hours')
AND status != 'cancelled'
ORDER BY start_time LIMIT 3;

-- Active critical alerts
SELECT * FROM insights 
WHERE is_active = 1 AND is_dismissed = 0 AND severity = 'critical'
ORDER BY created_at DESC LIMIT 5;
```

---

### GET `/api/priorities`

**Purpose:** Full priority queue with filters

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | `all` | `all` \| `task` \| `email` |
| `lane` | string | `all` | Filter by lane |
| `status` | string | `all` | `all` \| `overdue` \| `due_today` \| `due_week` |
| `assignee` | string | `all` | `me` \| `delegated` \| `team` \| specific person ID |
| `limit` | int | 50 | Max items |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "items": [
    {
      "item_type": "task",
      "id": "asana_123456",
      "title": "Submit VAT return",
      "score": 95,
      "reasons": ["Overdue by 1 day", "High priority"],
      "due_date": "2026-01-31",
      "due_time": null,
      "assignee": {
        "id": "person_moh",
        "name": "Moh"
      },
      "project": {
        "id": "asana_proj_789",
        "name": "Finance"
      },
      "lane": "finance",
      "status": "pending",
      "urgency": "overdue",
      "source": "asana",
      "source_url": "https://app.asana.com/0/123/456",
      "is_delegated": false,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-30T14:00:00Z"
    },
    {
      "item_type": "email",
      "id": "gmail_abc123",
      "title": "Re: Contract review needed",
      "score": 88,
      "reasons": ["VIP sender", "Awaiting response 26 hours"],
      "due_date": null,
      "due_time": null,
      "assignee": null,
      "project": null,
      "lane": null,
      "status": "pending",
      "urgency": "due_today",
      "source": "gmail",
      "source_url": "https://mail.google.com/mail/u/0/#inbox/abc123",
      "sender": {
        "name": "Ayham Homsi",
        "email": "ay@hrmny.co",
        "tier": "always_urgent"
      },
      "snippet": "Hi Moh, please review the attached contract...",
      "age_hours": 26.5,
      "created_at": "2026-01-31T15:00:00Z"
    }
  ],
  "total": 47,
  "limit": 50,
  "offset": 0,
  "filters_applied": {
    "type": "all",
    "lane": "all",
    "status": "all",
    "assignee": "all"
  }
}
```

---

### POST `/api/priorities/:id/complete`

**Purpose:** Mark item as complete

**URL Params:**
- `id`: Item ID (e.g., `asana_123456` or `gmail_abc123`)

**Request Body:**
```json
{
  "note": "Optional completion note"
}
```

**Response:**
```json
{
  "success": true,
  "item_id": "asana_123456",
  "item_type": "task",
  "action": "completed",
  "synced_to_source": true,
  "timestamp": "2026-02-01T17:35:00Z"
}
```

**Backend Logic:**
```python
def complete_item(item_id: str, note: str = None):
    if item_id.startswith('asana_'):
        # Update local DB
        db.execute("""
            UPDATE tasks SET 
                status = 'completed',
                updated_at = ?
            WHERE id = ?
        """, [now(), item_id])
        
        # Sync to Asana
        asana_gid = item_id.replace('asana_', '')
        asana_client.tasks.update(asana_gid, {'completed': True})
        
        return {'synced_to_source': True}
        
    elif item_id.startswith('gmail_'):
        # Mark as processed
        db.execute("""
            UPDATE communications SET
                processed = 1,
                processed_at = ?,
                action_taken = 'completed'
            WHERE id = ?
        """, [now(), item_id])
        
        return {'synced_to_source': False}  # No Gmail sync needed
```

---

### POST `/api/priorities/:id/snooze`

**Purpose:** Snooze item for later

**Request Body:**
```json
{
  "duration": "4h"  // "1h" | "4h" | "tomorrow" | "next_week" | "2026-02-05"
}
```

**Response:**
```json
{
  "success": true,
  "item_id": "asana_123456",
  "snoozed_until": "2026-02-01T21:35:00Z",
  "timestamp": "2026-02-01T17:35:00Z"
}
```

**Backend Logic:**
```python
def snooze_item(item_id: str, duration: str):
    snoozed_until = calculate_snooze_time(duration)
    
    if item_id.startswith('asana_'):
        # Update due date to snooze time
        db.execute("""
            UPDATE tasks SET
                due_date = ?,
                updated_at = ?,
                status = CASE WHEN status = 'pending' THEN 'snoozed' ELSE status END
            WHERE id = ?
        """, [snoozed_until.date(), now(), item_id])
        
        # Optionally sync to Asana
        asana_gid = item_id.replace('asana_', '')
        asana_client.tasks.update(asana_gid, {'due_on': snoozed_until.date().isoformat()})
        
    elif item_id.startswith('gmail_'):
        # For emails, we just adjust expected response time
        db.execute("""
            UPDATE communications SET
                expected_response_by = ?,
                priority = priority - 20  -- Lower priority temporarily
            WHERE id = ?
        """, [snoozed_until, item_id])
    
    return {'snoozed_until': snoozed_until}

def calculate_snooze_time(duration: str) -> datetime:
    now = datetime.now()
    if duration == '1h':
        return now + timedelta(hours=1)
    elif duration == '4h':
        return now + timedelta(hours=4)
    elif duration == 'tomorrow':
        return (now + timedelta(days=1)).replace(hour=9, minute=0)
    elif duration == 'next_week':
        days_until_monday = (7 - now.weekday()) % 7 or 7
        return (now + timedelta(days=days_until_monday)).replace(hour=9, minute=0)
    else:
        # Assume ISO date
        return datetime.fromisoformat(duration)
```

---

### POST `/api/priorities/:id/delegate`

**Purpose:** Delegate item to team member

**Request Body:**
```json
{
  "delegate_to": "person_krystie",  // Person ID
  "note": "Please handle the follow-up",
  "due_date": "2026-02-03"  // Optional override
}
```

**Response:**
```json
{
  "success": true,
  "item_id": "asana_123456",
  "delegation": {
    "id": "del_xyz789",
    "delegated_to": {
      "id": "person_krystie",
      "name": "Krystie Marie Beldad",
      "email": "krystie@hrmny.co"
    },
    "due_date": "2026-02-03",
    "status": "active"
  },
  "synced_to_source": true,
  "timestamp": "2026-02-01T17:35:00Z"
}
```

**Backend Logic:**
```python
def delegate_item(item_id: str, delegate_to: str, note: str = None, due_date: str = None):
    # Get delegate info
    delegate = db.query("SELECT * FROM people WHERE id = ?", [delegate_to])
    if not delegate:
        raise ValueError("Invalid delegate")
    
    # Get task
    task = db.query("SELECT * FROM tasks WHERE id = ?", [item_id])
    if not task:
        raise ValueError("Task not found")
    
    # Create delegation record
    delegation_id = f"del_{uuid4()}"
    db.execute("""
        INSERT INTO delegations (id, task_id, delegated_to_id, delegated_to_name, 
                                  delegated_by_id, delegated_at, due_date, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
    """, [delegation_id, item_id, delegate_to, delegate['name'], 
          'person_moh', now(), due_date or task['due_date'], note])
    
    # Update task
    db.execute("""
        UPDATE tasks SET
            assignee_id = ?,
            assignee_name = ?,
            delegated_by = 'person_moh',
            delegated_at = ?,
            is_supervised = 1,
            updated_at = ?
        WHERE id = ?
    """, [delegate_to, delegate['name'], now(), now(), item_id])
    
    # Sync to Asana
    if item_id.startswith('asana_'):
        asana_gid = item_id.replace('asana_', '')
        # Get Asana user ID for delegate
        asana_user = get_asana_user_by_email(delegate['email'])
        if asana_user:
            asana_client.tasks.update(asana_gid, {'assignee': asana_user['gid']})
    
    return {'delegation_id': delegation_id, 'synced_to_source': True}
```

---

### GET `/api/calendar`

**Purpose:** Calendar data with analysis

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `start` | date | today | Start date |
| `end` | date | +14 days | End date |
| `view` | string | `week` | `day` \| `week` \| `month` |

**Response:**
```json
{
  "range": {
    "start": "2026-02-01",
    "end": "2026-02-14"
  },
  "events": [
    {
      "id": "gcal_abc",
      "title": "Client call - Gargash",
      "start_time": "2026-02-01T18:00:00+04:00",
      "end_time": "2026-02-01T19:00:00+04:00",
      "duration_minutes": 60,
      "location": "Google Meet",
      "conference_url": "https://meet.google.com/xxx",
      "attendees": [
        {"name": "Ahmed Hassan", "email": "ahmed@gargash.ae", "status": "accepted"}
      ],
      "attendee_count": 2,
      "is_organizer": true,
      "has_conflict": false,
      "calendar_id": "primary"
    }
  ],
  "analysis": {
    "today": {
      "date": "2026-02-01",
      "events_count": 4,
      "total_scheduled_minutes": 180,
      "available_minutes": 420,  // 10h work day - 3h scheduled
      "utilization_pct": 30,
      "conflicts": [],
      "deep_work_slots": [
        {"start": "10:00", "end": "14:00", "minutes": 240},
        {"start": "19:30", "end": "22:00", "minutes": 150}
      ]
    },
    "week": {
      "total_events": 18,
      "total_meeting_hours": 12.5,
      "busiest_day": {"date": "2026-02-03", "hours": 4.5},
      "lightest_day": {"date": "2026-02-07", "hours": 0.5}
    }
  },
  "conflicts": [
    {
      "date": "2026-02-03",
      "events": [
        {"id": "gcal_123", "title": "Team standup", "time": "10:00-10:30"},
        {"id": "gcal_456", "title": "Client call", "time": "10:15-11:00"}
      ],
      "overlap_minutes": 15
    }
  ]
}
```

---

### GET `/api/tasks`

**Purpose:** Full task list with filters

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `project` | string | `all` | Project ID or `all` |
| `assignee` | string | `all` | Person ID, `me`, or `all` |
| `status` | string | `active` | `active` \| `completed` \| `blocked` \| `all` |
| `lane` | string | `all` | Lane filter |
| `overdue` | bool | `false` | Only overdue |
| `sort` | string | `priority` | `priority` \| `due_date` \| `updated` \| `project` |
| `limit` | int | 100 | Max items |
| `offset` | int | 0 | Pagination |

**Response:**
```json
{
  "items": [
    {
      "id": "asana_123456",
      "title": "Submit VAT return",
      "status": "pending",
      "priority": 95,
      "priority_reasons": ["Overdue by 1 day", "High priority"],
      "due_date": "2026-01-31",
      "assignee": {
        "id": "person_moh",
        "name": "Moh"
      },
      "project": {
        "id": "asana_proj_789",
        "name": "Finance",
        "health": "yellow"
      },
      "lane": "finance",
      "tags": ["urgent", "tax"],
      "blockers": [],
      "is_delegated": false,
      "is_supervised": false,
      "stale_days": 0,
      "source_url": "https://app.asana.com/0/123/456",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-30T14:00:00Z"
    }
  ],
  "total": 156,
  "by_status": {
    "pending": 89,
    "in_progress": 34,
    "blocked": 12,
    "completed": 21
  },
  "by_assignee": {
    "person_moh": 45,
    "person_krystie": 23,
    "person_rene": 18,
    "unassigned": 5
  }
}
```

---

### GET `/api/team`

**Purpose:** Team overview and workload

**Response:**
```json
{
  "members": [
    {
      "id": "person_krystie",
      "name": "Krystie Marie Beldad",
      "email": "krystie@hrmny.co",
      "role": "Operations",
      "team": "core",
      "avatar_url": null,
      "workload": {
        "active_tasks": 23,
        "overdue_tasks": 2,
        "blocked_tasks": 1,
        "due_today": 3,
        "due_this_week": 8
      },
      "lanes": ["admin", "finance", "ops"],
      "last_activity": "2026-02-01T16:45:00Z",
      "status": "active"  // based on recent activity
    }
  ],
  "summary": {
    "total_members": 6,
    "total_active_tasks": 89,
    "total_overdue": 7,
    "total_blocked": 4
  }
}
```

---

### GET `/api/delegations`

**Purpose:** Track delegated items

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `active` | `active` \| `completed` \| `all` |
| `delegate` | string | `all` | Person ID or `all` |
| `needs_followup` | bool | `false` | Only items needing follow-up |

**Response:**
```json
{
  "delegations": [
    {
      "id": "del_xyz789",
      "task": {
        "id": "asana_123456",
        "title": "Follow up with client on proposal",
        "status": "pending",
        "due_date": "2026-02-03"
      },
      "delegated_to": {
        "id": "person_krystie",
        "name": "Krystie Marie Beldad"
      },
      "delegated_at": "2026-01-28T10:00:00Z",
      "days_active": 4,
      "expected_turnaround": 2,
      "status": "active",
      "needs_followup": true,
      "last_followup": null,
      "notes": "Client prefers email communication"
    }
  ],
  "summary": {
    "total_active": 12,
    "needs_followup": 3,
    "overdue": 2,
    "by_delegate": {
      "person_krystie": 5,
      "person_rene": 4,
      "person_aubrey": 3
    }
  }
}
```

---

### GET `/api/inbox`

**Purpose:** Communications requiring attention

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `filter` | string | `needs_response` | `all` \| `needs_response` \| `vip` \| `unread` |
| `sender_tier` | string | `all` | `vip` \| `important` \| `normal` |
| `limit` | int | 50 | Max items |

**Response:**
```json
{
  "items": [
    {
      "id": "gmail_abc123",
      "subject": "Re: Contract review needed",
      "sender": {
        "name": "Ayham Homsi",
        "email": "ay@hrmny.co",
        "tier": "always_urgent",
        "is_vip": true
      },
      "snippet": "Hi Moh, please review the attached contract and let me know...",
      "received_at": "2026-01-31T15:00:00Z",
      "age_hours": 26.5,
      "is_unread": true,
      "is_starred": false,
      "labels": ["INBOX", "IMPORTANT"],
      "requires_response": true,
      "response_urgency": "urgent",
      "thread_id": "thread_xyz",
      "thread_count": 3,
      "source_url": "https://mail.google.com/mail/u/0/#inbox/abc123"
    }
  ],
  "counts": {
    "total_unread": 23,
    "needs_response": 12,
    "vip_pending": 3,
    "by_tier": {
      "always_urgent": 2,
      "important": 4,
      "normal": 6
    }
  }
}
```

---

### GET `/api/projects`

**Purpose:** Project health overview

**Response:**
```json
{
  "projects": [
    {
      "id": "asana_proj_789",
      "name": "Client X - Website Redesign",
      "status": "active",
      "health": "yellow",
      "health_reasons": ["3 overdue tasks", "Deadline in 5 days, 60% complete"],
      "owner": {
        "id": "person_rene",
        "name": "Rene"
      },
      "client": "Client X",
      "lane": "client",
      "deadline": "2026-02-06",
      "days_to_deadline": 5,
      "progress": {
        "total_tasks": 24,
        "completed": 14,
        "overdue": 3,
        "blocked": 1,
        "completion_pct": 58.3
      },
      "blockers": ["Waiting on brand assets"],
      "next_milestone": "Design review",
      "next_milestone_date": "2026-02-03",
      "last_activity": "2026-02-01T14:30:00Z",
      "source_url": "https://app.asana.com/0/proj_789"
    }
  ],
  "summary": {
    "total": 8,
    "by_health": {
      "green": 4,
      "yellow": 3,
      "red": 1
    },
    "by_lane": {
      "client": 5,
      "ops": 2,
      "music": 1
    }
  }
}
```

---

### GET `/api/insights`

**Purpose:** Active insights and recommendations

**Response:**
```json
{
  "insights": [
    {
      "id": "insight_123",
      "type": "anomaly",
      "category": "communications",
      "severity": "critical",
      "title": "VIP emails awaiting response > 4 hours",
      "description": "3 emails from always_urgent contacts have been waiting for response",
      "affected_items": [
        {"type": "email", "id": "gmail_abc", "title": "Re: Contract review"},
        {"type": "email", "id": "gmail_def", "title": "Urgent: Budget approval"}
      ],
      "suggested_action": "Review and respond to VIP emails",
      "action_type": "review",
      "confidence": 0.95,
      "created_at": "2026-02-01T17:00:00Z"
    },
    {
      "id": "insight_456",
      "type": "pattern",
      "category": "tasks",
      "severity": "warning",
      "title": "Finance tasks frequently overdue",
      "description": "70% of finance lane tasks have been completed late in the past 30 days",
      "data": {
        "lane": "finance",
        "total_tasks": 20,
        "late_tasks": 14,
        "late_pct": 70
      },
      "suggested_action": "Consider delegating more finance tasks or adjusting deadlines",
      "action_type": "review",
      "confidence": 0.82,
      "created_at": "2026-02-01T09:00:00Z"
    }
  ],
  "counts": {
    "total_active": 7,
    "by_severity": {
      "critical": 1,
      "warning": 4,
      "info": 2
    },
    "by_type": {
      "anomaly": 3,
      "pattern": 2,
      "recommendation": 2
    }
  }
}
```

---

### GET `/api/decisions`

**Purpose:** Pending decisions requiring approval

**Response:**
```json
{
  "decisions": [
    {
      "id": "dec_789",
      "domain": "tasks",
      "action_type": "delegate",
      "title": "Auto-delegate admin task to Krystie",
      "description": "Task 'Update employee records' matches delegation rules for admin lane",
      "target": {
        "type": "task",
        "id": "asana_999",
        "title": "Update employee records"
      },
      "payload": {
        "action": "delegate",
        "delegate_to": "person_krystie",
        "reason": "Admin lane auto-delegation rule"
      },
      "rationale": "This task is in the admin lane and Krystie is the primary delegate for admin tasks",
      "confidence": 0.88,
      "risk_level": "low",
      "status": "pending",
      "created_at": "2026-02-01T16:00:00Z"
    }
  ],
  "count": 1
}
```

---

### POST `/api/decisions/:id`

**Purpose:** Approve or reject a decision

**Request Body:**
```json
{
  "action": "approve",  // "approve" | "reject"
  "modification": null,  // Optional: modified payload
  "reason": null  // Required if rejecting
}
```

**Response:**
```json
{
  "success": true,
  "decision_id": "dec_789",
  "action": "approve",
  "executed": true,
  "execution_result": {
    "task_id": "asana_999",
    "delegated_to": "person_krystie",
    "synced_to_asana": true
  },
  "timestamp": "2026-02-01T17:40:00Z"
}
```

---

# PART 3: DASHBOARD SPECIFICATIONS

## 3.1 Technical Stack

```
Framework: Single HTML file with vanilla JS (for now)
            OR React/Next.js (for production)
Styling: Tailwind CSS
State: Local state + API polling (30s interval)
Charts: Chart.js or similar for calendar visualization
```

## 3.2 Page Layouts

### Overview Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADER                                                                   │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ MOH TIME OS                          [Sync] [Settings] [Profile]    │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│ ALERTS BAR (if any critical alerts)                                     │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ⚠️ 3 VIP emails awaiting response > 4 hours          [View] [Dismiss]│ │
│ └─────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │ STATS ROW                   │  │                                 │  │
│  │ ┌─────┐ ┌─────┐ ┌─────┐    │  │                                 │  │
│  │ │  5  │ │  3  │ │ 12  │    │  │                                 │  │
│  │ │ Due │ │Over │ │Email│    │  │                                 │  │
│  │ │Today│ │ due │ │Pend │    │  │                                 │  │
│  │ └─────┘ └─────┘ └─────┘    │  │                                 │  │
│  │ ┌─────┐ ┌─────┐            │  │  UPCOMING EVENTS               │  │
│  │ │  2  │ │  1  │            │  │  ┌─────────────────────────┐   │  │
│  │ │Team │ │Pend │            │  │  │ 18:00 Client call       │   │  │
│  │ │Block│ │Decis│            │  │  │ 19:30 Team sync         │   │  │
│  │ └─────┘ └─────┘            │  │  │ Tomorrow 10:00 Review   │   │  │
│  └─────────────────────────────┘  │  └─────────────────────────┘   │  │
│                                    │                                 │  │
│  ┌─────────────────────────────┐  └─────────────────────────────────┘  │
│  │ TOP PRIORITIES              │                                       │
│  │ ┌─────────────────────────┐ │  ┌─────────────────────────────────┐  │
│  │ │ 1. Submit VAT return    │ │  │ SYNC STATUS                     │  │
│  │ │    ⚠️ Overdue 1 day     │ │  │ Asana    ✓ 2m ago               │  │
│  │ │    [✓] [⏰] [→]         │ │  │ Gmail    ✓ 1m ago               │  │
│  │ ├─────────────────────────┤ │  │ Calendar ✓ 1m ago               │  │
│  │ │ 2. Review contract      │ │  └─────────────────────────────────┘  │
│  │ │    📧 VIP - 26h old     │ │                                       │
│  │ │    [✓] [⏰] [→]         │ │                                       │
│  │ ├─────────────────────────┤ │                                       │
│  │ │ 3. Client deliverable   │ │                                       │
│  │ │    Due today            │ │                                       │
│  │ │    [✓] [⏰] [→]         │ │                                       │
│  │ └─────────────────────────┘ │                                       │
│  │ [View all priorities →]     │                                       │
│  └─────────────────────────────┘                                       │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ NAVIGATION                                                               │
│ [Overview] [Priorities] [Calendar] [Tasks] [Team] [Inbox] [Projects]    │
│ [Insights] [Decisions] [Settings]                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component: Priority Item Card

```
┌────────────────────────────────────────────────────────────────┐
│ ┌────┐                                                          │
│ │ 95 │  Submit VAT return                              [Asana↗]│
│ │ 🔴 │  Finance • Due: Jan 31 (1 day overdue)                  │
│ └────┘  Reasons: Overdue, High priority tag                    │
│         Assignee: Moh                                           │
│         ┌─────┐ ┌─────────┐ ┌──────────┐                       │
│         │ ✓   │ │ ⏰ Snooze│ │ → Delegate│                      │
│         │Done │ │ ▼       │ │ ▼        │                       │
│         └─────┘ └─────────┘ └──────────┘                       │
└────────────────────────────────────────────────────────────────┘

Score badge colors:
- 90-100: Red (critical)
- 70-89: Orange (high)  
- 50-69: Yellow (medium)
- 0-49: Gray (low)
```

### Component: Snooze Dropdown

```
┌─────────────┐
│ ⏰ Snooze   │
├─────────────┤
│ 1 hour      │
│ 4 hours     │
│ Tomorrow    │
│ Next week   │
│ Pick date...│
└─────────────┘
```

### Component: Delegate Dropdown

```
┌──────────────────────┐
│ → Delegate           │
├──────────────────────┤
│ 👤 Krystie (Admin)   │
│ 👤 Rene (Creative)   │
│ 👤 Aubrey (People)   │
│ 👤 Amar (Creative)   │
│ 👤 Jana (Creative)   │
├──────────────────────┤
│ [Add note...]        │
└──────────────────────┘
```

---

### Priorities Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADER + NAV (same as overview)                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ FILTERS BAR                                                              │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Type: [All ▼] Lane: [All ▼] Status: [All ▼] Assignee: [All ▼]      │ │
│ │                                                    [Clear filters]  │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│ RESULTS INFO                                                             │
│ │ Showing 47 items                                                     │ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│ PRIORITY LIST                                                            │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ [Priority Item Card 1]                                              │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ [Priority Item Card 2]                                              │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ [Priority Item Card 3]                                              │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ ...                                                                 │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ PAGINATION                                                               │
│ │ [← Prev] Page 1 of 3 [Next →]                                       │ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Calendar Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADER + NAV                                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ CALENDAR HEADER                                                          │
│ │ [< Prev] February 2026 [Next >]      [Day] [Week] [Month]           │ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────┐ ┌────────────────────────┐ │
│  │ CALENDAR GRID (Week View)               │ │ ANALYSIS PANEL         │ │
│  │                                         │ │                        │ │
│  │      Mon   Tue   Wed   Thu   Fri        │ │ Today                  │ │
│  │ 09:00 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ │ ├ Events: 4           │ │
│  │ 10:00 ████░░░░░████░░░░░░░░░░░░░░░░░░  │ │ ├ Scheduled: 3h       │ │
│  │ 11:00 ████░░░░░████░░░░░░░░░░░░░░░░░░  │ │ ├ Available: 7h       │ │
│  │ 12:00 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ │ └ Utilization: 30%    │ │
│  │ 13:00 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ │                        │ │
│  │ 14:00 ░░░░████████░░░░░░░░████░░░░░░░  │ │ This Week              │ │
│  │ 15:00 ░░░░████████░░░░░░░░████░░░░░░░  │ │ ├ Total meetings: 12h │ │
│  │ 16:00 ░░░░░░░░░░░░░░░░░░░░████░░░░░░░  │ │ ├ Busiest: Wed (4h)   │ │
│  │ 17:00 ░░░░░░░░░░████░░░░░░░░░░░░░░░░░  │ │ └ Conflicts: 1        │ │
│  │ 18:00 ████░░░░░░████░░░░░░░░░░░░░░░░░  │ │                        │ │
│  │ 19:00 ████░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ │ ⚠️ Conflicts           │ │
│  │                                         │ │ Wed 10:00-10:30       │ │
│  │ Legend: ████ = Event  🔴 = Conflict     │ │ Team sync vs Client   │ │
│  └─────────────────────────────────────────┘ │ [Resolve]             │ │
│                                              └────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Tasks Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADER + NAV                                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ FILTERS BAR                                                              │
│ │ Project: [All ▼] Assignee: [All ▼] Status: [Active ▼] Lane: [All ▼] │ │
│ │ [x] Overdue only                           Sort: [Priority ▼]       │ │
├─────────────────────────────────────────────────────────────────────────┤
│ SUMMARY BAR                                                              │
│ │ 156 tasks │ Pending: 89 │ In Progress: 34 │ Blocked: 12 │ Done: 21  │ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│ TASK TABLE                                                               │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ☐ │ Task                    │ Project    │ Assignee │ Due    │ Pri │ │
│ ├───┼─────────────────────────┼────────────┼──────────┼────────┼─────┤ │
│ │ ☐ │ Submit VAT return       │ Finance    │ Moh      │ Jan 31 │ 🔴  │ │
│ │ ☐ │ Review contract         │ Client X   │ Moh      │ Feb 2  │ 🟠  │ │
│ │ ☐ │ Update website copy     │ Client X   │ Rene     │ Feb 3  │ 🟡  │ │
│ │ ☐ │ Send invoice            │ Finance    │ Krystie  │ Feb 1  │ 🟡  │ │
│ │ 🚫│ Finalize designs        │ Client Y   │ Amar     │ Feb 4  │ 🟠  │ │
│ │   │ └ Blocked: Waiting on assets                                    │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ BULK ACTIONS (when items selected)                                       │
│ │ [Complete] [Delegate to...] [Change due date] [Add to project]      │ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Team Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADER + NAV                                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ TEAM SUMMARY                                                             │
│ │ 6 team members │ 89 active tasks │ 7 overdue │ 4 blocked            │ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────────────────────┐  ┌─────────────────────────────┐ │
│  │ TEAM MEMBERS                      │  │ DELEGATION TRACKER          │ │
│  │                                   │  │                             │ │
│  │ ┌─────────────────────────────┐   │  │ Active delegations: 12     │ │
│  │ │ 👤 Krystie Marie Beldad     │   │  │ Needs follow-up: 3         │ │
│  │ │    Operations               │   │  │                             │ │
│  │ │    Tasks: 23 │ ⚠️ 2 overdue │   │  │ ┌─────────────────────────┐ │ │
│  │ │    Blocked: 1               │   │  │ │ Follow up client       │ │ │
│  │ │    [View tasks]             │   │  │ │ → Krystie • 4 days     │ │ │
│  │ └─────────────────────────────┘   │  │ │ ⚠️ Past turnaround      │ │ │
│  │                                   │  │ │ [Remind] [Recall]      │ │ │
│  │ ┌─────────────────────────────┐   │  │ └─────────────────────────┘ │ │
│  │ │ 👤 Rene                     │   │  │                             │ │
│  │ │    Creative Lead            │   │  │ ┌─────────────────────────┐ │ │
│  │ │    Tasks: 18 │ ✓ On track   │   │  │ │ Update records         │ │ │
│  │ │    [View tasks]             │   │  │ │ → Aubrey • 2 days      │ │ │
│  │ └─────────────────────────────┘   │  │ │ ✓ On track             │ │ │
│  │                                   │  │ └─────────────────────────┘ │ │
│  │ [+ More team members...]          │  │                             │ │
│  └───────────────────────────────────┘  └─────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Inbox Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ HEADER + NAV                                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ INBOX FILTERS                                                            │
│ │ [All] [Needs Response (12)] [VIP (3)] [Unread (23)]                 │ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│ VIP SECTION (if any)                                                     │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ 👑 VIP - Requires Attention                                         │ │
│ │ ┌─────────────────────────────────────────────────────────────────┐ │ │
│ │ │ ⭐ Ayham Homsi <ay@hrmny.co>                          26h ago   │ │ │
│ │ │    Re: Contract review needed                                   │ │ │
│ │ │    Hi Moh, please review the attached contract and let me...    │ │ │
│ │ │    [Mark Done] [Create Task] [Open in Gmail]                    │ │ │
│ │ └─────────────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ NEEDS RESPONSE                                                           │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ┌─────────────────────────────────────────────────────────────────┐ │ │
│ │ │ Client X <contact@clientx.com>                        18h ago   │ │ │
│ │ │    Re: Project timeline                                         │ │ │
│ │ │    Thanks for the update. Can we discuss the revised...         │ │ │
│ │ │    [Mark Done] [Create Task] [Open in Gmail]                    │ │ │
│ │ └─────────────────────────────────────────────────────────────────┘ │ │
│ │ ...                                                                 │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3.3 Interaction Specifications

### Complete Item Flow

```
User clicks [✓ Complete]
    │
    ▼
Show confirmation toast: "Completing..."
    │
    ▼
POST /api/priorities/{id}/complete
    │
    ├── Success
    │       │
    │       ▼
    │   Remove item from list (animate out)
    │   Show toast: "Completed ✓"
    │   Update stats counters
    │
    └── Error
            │
            ▼
        Show error toast: "Failed to complete. Retry?"
        Keep item in list
        [Retry] button
```

### Snooze Item Flow

```
User clicks [⏰ Snooze]
    │
    ▼
Show dropdown:
  - 1 hour
  - 4 hours  
  - Tomorrow
  - Next week
  - Pick date...
    │
    ▼
User selects option
    │
    ▼
POST /api/priorities/{id}/snooze {duration: "4h"}
    │
    ├── Success
    │       │
    │       ▼
    │   Remove item from list (animate out)
    │   Show toast: "Snoozed until 21:35"
    │
    └── Error
            │
            ▼
        Show error toast
        Close dropdown
```

### Delegate Item Flow

```
User clicks [→ Delegate]
    │
    ▼
Show delegate dropdown:
  - Team members with lanes
  - Optional note field
    │
    ▼
User selects person + optional note
    │
    ▼
POST /api/priorities/{id}/delegate {delegate_to, note}
    │
    ├── Success
    │       │
    │       ▼
    │   Update item in list (show delegated badge)
    │   Show toast: "Delegated to Krystie"
    │   Add to delegation tracker
    │
    └── Error
            │
            ▼
        Show error toast
        Close dropdown
```

### Filter Change Flow

```
User changes filter dropdown
    │
    ▼
Update URL query params (for shareable links)
    │
    ▼
Show loading state on list
    │
    ▼
GET /api/priorities?type=task&lane=finance&...
    │
    ▼
Replace list with new results
Update results count
```

---

## 3.4 State Management

### Global State

```javascript
const state = {
  // User
  user: {
    id: "person_moh",
    name: "Moh"
  },
  
  // Cache
  cache: {
    priorities: { data: [], fetchedAt: null, stale: false },
    calendar: { data: {}, fetchedAt: null, stale: false },
    tasks: { data: [], fetchedAt: null, stale: false },
    team: { data: [], fetchedAt: null, stale: false },
    inbox: { data: [], fetchedAt: null, stale: false },
    projects: { data: [], fetchedAt: null, stale: false },
    insights: { data: [], fetchedAt: null, stale: false },
    decisions: { data: [], fetchedAt: null, stale: false }
  },
  
  // UI State
  ui: {
    currentPage: "overview",
    filters: {
      priorities: { type: "all", lane: "all", status: "all", assignee: "all" },
      tasks: { project: "all", assignee: "all", status: "active", lane: "all" },
      inbox: { filter: "needs_response" }
    },
    modals: {
      snooze: { open: false, itemId: null },
      delegate: { open: false, itemId: null },
      settings: { open: false }
    },
    toasts: []
  },
  
  // Sync status
  sync: {
    lastUpdate: null,
    isPolling: true,
    sources: {
      asana: { healthy: true, lastSync: null },
      gmail: { healthy: true, lastSync: null },
      calendar: { healthy: true, lastSync: null }
    }
  }
};
```

### Polling Strategy

```javascript
// Poll overview data every 30 seconds
setInterval(async () => {
  if (state.ui.currentPage === 'overview') {
    const data = await fetch('/api/overview');
    updateOverview(data);
  }
}, 30000);

// Poll current page data when switching
async function navigateTo(page) {
  state.ui.currentPage = page;
  await refreshCurrentPage();
}

// Mark cache stale when action taken
async function completeItem(id) {
  await post(`/api/priorities/${id}/complete`);
  state.cache.priorities.stale = true;
  state.cache.tasks.stale = true;
  await refreshCurrentPage();
}
```

---

## 3.5 Error Handling

### API Error States

```javascript
// Wrapper for all API calls
async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(`/api${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new ApiError(response.status, error.message);
    }
    
    return await response.json();
    
  } catch (error) {
    if (error instanceof ApiError) {
      showToast({ type: 'error', message: error.message });
    } else {
      showToast({ type: 'error', message: 'Network error. Check connection.' });
    }
    throw error;
  }
}
```

### Empty States

```
┌─────────────────────────────────────────┐
│                                         │
│           📭 No items                   │
│                                         │
│   No priorities match your filters.     │
│   Try adjusting filters or check back   │
│   after the next sync.                  │
│                                         │
│   [Clear filters]                       │
│                                         │
└─────────────────────────────────────────┘
```

### Loading States

```
┌─────────────────────────────────────────┐
│                                         │
│         ⏳ Loading priorities...        │
│                                         │
│   [Skeleton item 1                    ] │
│   [Skeleton item 2                    ] │
│   [Skeleton item 3                    ] │
│                                         │
└─────────────────────────────────────────┘
```

---

# PART 4: BACKGROUND OPERATIONS

## 4.1 Sync Daemon

### Process Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     SYNC DAEMON                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐     │
│  │ Asana   │    │ Gmail   │    │Calendar │    │ Apollo  │     │
│  │ 5 min   │    │ 2 min   │    │ 2 min   │    │ 10 min  │     │
│  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘     │
│       │              │              │              │           │
│       └──────────────┴──────────────┴──────────────┘           │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                         │
│                    │  STATE STORE    │                         │
│                    └────────┬────────┘                         │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                         │
│                    │ ANALYSIS RUN    │                         │
│                    │ (after sync)    │                         │
│                    └────────┬────────┘                         │
│                              │                                  │
│                    ┌────────┴────────┐                         │
│                    │                 │                          │
│                    ▼                 ▼                          │
│            ┌───────────┐    ┌───────────────┐                  │
│            │ Update    │    │ Generate      │                  │
│            │ priority  │    │ insights      │                  │
│            │ scores    │    │ & anomalies   │                  │
│            └───────────┘    └───────────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Cron Schedule

```bash
# Sync jobs
*/2 * * * * cd ~/clawd/moh_time_os && .venv/bin/python -m lib.collectors.gmail_sync
*/2 * * * * cd ~/clawd/moh_time_os && .venv/bin/python -m lib.collectors.calendar_sync
*/5 * * * * cd ~/clawd/moh_time_os && .venv/bin/python -m lib.collectors.asana_sync
*/10 * * * * cd ~/clawd/moh_time_os && .venv/bin/python -m lib.collectors.apollo_sync

# Analysis (runs 1 min after syncs complete)
*/5 * * * * sleep 60 && cd ~/clawd/moh_time_os && .venv/bin/python -m lib.analyzers.run_all

# Health check
*/15 * * * * cd ~/clawd/moh_time_os && .venv/bin/python -m lib.health_check
```

---

## 4.2 Analysis Pipeline

### Priority Scoring Algorithm

```python
def compute_priority_score(item: dict, item_type: str) -> tuple[int, list[str]]:
    """
    Compute priority score 0-100 with reasons.
    
    Returns: (score, reasons)
    """
    score = 50  # Base score
    reasons = []
    
    # === DUE DATE FACTOR (0-40 points) ===
    due_date = item.get('due_date')
    if due_date:
        days_until = days_until_date(due_date)
        
        if days_until < 0:
            # Overdue
            overdue_days = abs(days_until)
            score += min(40, 25 + overdue_days * 3)
            reasons.append(f"Overdue by {overdue_days} day{'s' if overdue_days > 1 else ''}")
        elif days_until == 0:
            score += 25
            reasons.append("Due today")
        elif days_until == 1:
            score += 20
            reasons.append("Due tomorrow")
        elif days_until <= 3:
            score += 15
            reasons.append(f"Due in {days_until} days")
        elif days_until <= 7:
            score += 10
            reasons.append("Due this week")
    
    # === EXPLICIT PRIORITY FACTOR (0-25 points) ===
    if item_type == 'task':
        tags = item.get('tags', [])
        if 'urgent' in tags or 'critical' in tags:
            score += 25
            reasons.append("Marked urgent")
        elif 'high' in tags or 'important' in tags:
            score += 15
            reasons.append("High priority")
        
        # Asana priority custom field
        asana_priority = item.get('asana_priority')
        if asana_priority == 'High':
            score += 20
            reasons.append("High priority in Asana")
        elif asana_priority == 'Medium':
            score += 10
    
    # === SENDER/VIP FACTOR (0-25 points) ===
    if item_type == 'email':
        sender_tier = item.get('sender_tier')
        if sender_tier == 'always_urgent':
            score += 25
            reasons.append("VIP sender")
        elif sender_tier == 'important':
            score += 15
            reasons.append("Important sender")
        
        # Age factor for emails
        age_hours = item.get('age_hours', 0)
        if age_hours > 48:
            score += 15
            reasons.append(f"Awaiting response {int(age_hours)}h")
        elif age_hours > 24:
            score += 10
            reasons.append(f"Awaiting response {int(age_hours)}h")
    
    # === PROJECT CRITICALITY (0-10 points) ===
    if item_type == 'task':
        project_health = item.get('project_health')
        if project_health == 'red':
            score += 10
            reasons.append("Project at risk")
        elif project_health == 'yellow':
            score += 5
    
    # === BLOCKERS (affects others) ===
    if item.get('blocks_others'):
        score += 10
        reasons.append("Blocking other work")
    
    # === CAP AT 100 ===
    score = min(100, score)
    
    return score, reasons
```

### Anomaly Detection Rules

```python
ANOMALY_RULES = [
    {
        'id': 'vip_email_aging',
        'name': 'VIP emails awaiting response',
        'severity': 'critical',
        'check': lambda: """
            SELECT * FROM communications 
            WHERE sender_tier = 'always_urgent' 
            AND requires_response = 1 
            AND processed = 0 
            AND age_hours > 4
        """,
        'message': lambda count: f"{count} VIP emails awaiting response > 4 hours",
        'action': 'review'
    },
    {
        'id': 'overdue_high_priority',
        'name': 'Overdue high-priority tasks',
        'severity': 'critical',
        'check': lambda: """
            SELECT * FROM tasks 
            WHERE due_date < date('now') 
            AND priority >= 80 
            AND status NOT IN ('completed', 'cancelled')
        """,
        'message': lambda count: f"{count} high-priority tasks are overdue",
        'action': 'review'
    },
    {
        'id': 'calendar_conflict',
        'name': 'Calendar conflicts',
        'severity': 'warning',
        'check': lambda: """
            SELECT * FROM events 
            WHERE has_conflict = 1 
            AND date(start_time) >= date('now')
        """,
        'message': lambda count: f"{count} scheduling conflicts detected",
        'action': 'resolve'
    },
    {
        'id': 'stale_tasks',
        'name': 'Stale tasks',
        'severity': 'warning',
        'check': lambda: """
            SELECT * FROM tasks 
            WHERE stale_days > 7 
            AND status NOT IN ('completed', 'cancelled')
        """,
        'message': lambda count: f"{count} tasks with no activity for 7+ days",
        'action': 'review'
    },
    {
        'id': 'team_blocked',
        'name': 'Team members blocked',
        'severity': 'warning',
        'check': lambda: """
            SELECT DISTINCT assignee_id, assignee_name 
            FROM tasks 
            WHERE status = 'blocked' 
            AND assignee_id != 'person_moh'
        """,
        'message': lambda count: f"{count} team members have blocked tasks",
        'action': 'review'
    },
    {
        'id': 'delegation_stale',
        'name': 'Delegations needing follow-up',
        'severity': 'info',
        'check': lambda: """
            SELECT * FROM delegations 
            WHERE status = 'active' 
            AND days_active > turnaround_days 
            AND (follow_up_sent_at IS NULL OR julianday('now') - julianday(follow_up_sent_at) > 2)
        """,
        'message': lambda count: f"{count} delegations past expected turnaround",
        'action': 'follow_up'
    }
]
```

---

# PART 5: IMPLEMENTATION CHECKLIST

## Phase 1: Data Foundation (Days 1-2)

### 1.1 Database Schema
- [ ] Create migration script with all tables from Part 1
- [ ] Run migration on existing state.db
- [ ] Verify all columns exist with correct types
- [ ] Create all indexes
- [ ] Create computed views (priority_queue, team_workload, daily_calendar)
- [ ] Test: Run `.schema` and verify against spec

### 1.2 Collectors Verification
- [ ] Test Asana collector: `python -m lib.collectors.asana_sync`
  - [ ] Verify tasks populated with all fields
  - [ ] Verify projects populated
  - [ ] Verify assignee mapping to people table
- [ ] Test Gmail collector: `python -m lib.collectors.gmail_sync`
  - [ ] Verify communications populated
  - [ ] Verify sender_tier computed
  - [ ] Verify requires_response detection
- [ ] Test Calendar collector: `python -m lib.collectors.calendar_sync`
  - [ ] Verify events populated
  - [ ] Verify conflict detection
- [ ] Test: Query each table, verify data makes sense

### 1.3 People Table Population
- [ ] Extract unique assignees from Asana tasks
- [ ] Load VIP config from config/vip.yaml
- [ ] Merge into people table with correct tiers
- [ ] Add HRMNY team members with roles and lanes
- [ ] Test: `SELECT * FROM people` shows complete team

### 1.4 Projects Table Population
- [ ] Extract projects from Asana
- [ ] Compute health scores
- [ ] Compute task counts and completion %
- [ ] Test: `SELECT * FROM projects` shows all projects with health

---

## Phase 2: Analysis Pipeline (Days 3-4)

### 2.1 Priority Scoring
- [ ] Implement compute_priority_score() per spec
- [ ] Run on all tasks after sync
- [ ] Run on all communications after sync
- [ ] Store score + reasons in respective tables
- [ ] Test: Top 10 priorities make intuitive sense

### 2.2 Anomaly Detection
- [ ] Implement all anomaly rules from spec
- [ ] Run detection after each sync
- [ ] Store active anomalies in insights table
- [ ] Auto-expire resolved anomalies
- [ ] Test: Create overdue task, verify anomaly detected

### 2.3 Time Analysis
- [ ] Compute daily utilization
- [ ] Detect conflicts (overlapping events)
- [ ] Identify available slots
- [ ] Cache results for API
- [ ] Test: Calendar shows correct analysis

### 2.4 Project Health
- [ ] Implement health calculation per spec
- [ ] Update after each Asana sync
- [ ] Test: Artificially create overdue tasks, verify health turns yellow/red

---

## Phase 3: API Server (Days 5-7)

### 3.1 Endpoint Implementation
- [ ] GET /api/overview - implement per spec
- [ ] GET /api/priorities - implement with filters
- [ ] POST /api/priorities/:id/complete - implement + Asana sync
- [ ] POST /api/priorities/:id/snooze - implement
- [ ] POST /api/priorities/:id/delegate - implement + Asana sync
- [ ] GET /api/calendar - implement with analysis
- [ ] GET /api/tasks - implement with filters
- [ ] GET /api/team - implement
- [ ] GET /api/delegations - implement
- [ ] GET /api/inbox - implement with VIP grouping
- [ ] GET /api/projects - implement with health
- [ ] GET /api/insights - implement
- [ ] GET /api/decisions - implement
- [ ] POST /api/decisions/:id - implement approve/reject
- [ ] GET /api/health - implement

### 3.2 API Testing
- [ ] Test each endpoint with curl
- [ ] Verify response shapes match spec
- [ ] Test error cases (404, 400, etc.)
- [ ] Test filters work correctly
- [ ] Load test: 100 requests in 10 seconds

---

## Phase 4: Dashboard Structure (Days 8-10)

### 4.1 Navigation & Layout
- [ ] Create base HTML structure
- [ ] Implement navigation between pages
- [ ] Create header with sync status
- [ ] Create responsive layout grid
- [ ] Style with Tailwind

### 4.2 Page Shells
- [ ] Overview page layout
- [ ] Priorities page layout
- [ ] Calendar page layout
- [ ] Tasks page layout
- [ ] Team page layout
- [ ] Inbox page layout
- [ ] Projects page layout
- [ ] Insights page layout
- [ ] Decisions page layout
- [ ] Settings page layout

### 4.3 Components
- [ ] Priority item card (with score badge, actions)
- [ ] Snooze dropdown
- [ ] Delegate dropdown
- [ ] Filter bar
- [ ] Stats cards
- [ ] Event card
- [ ] Team member card
- [ ] Email card
- [ ] Project card
- [ ] Insight card
- [ ] Decision card
- [ ] Toast notifications
- [ ] Loading skeletons
- [ ] Empty states

---

## Phase 5: Dashboard Functionality (Days 11-14)

### 5.1 Overview Page
- [ ] Fetch /api/overview on load
- [ ] Render stats counters
- [ ] Render top 5 priorities with actions
- [ ] Render upcoming events
- [ ] Render critical alerts banner
- [ ] Show sync status
- [ ] Auto-refresh every 30s

### 5.2 Priorities Page
- [ ] Fetch /api/priorities with filters
- [ ] Render full priority list
- [ ] Implement filter dropdowns
- [ ] Complete action works
- [ ] Snooze action works
- [ ] Delegate action works
- [ ] Pagination works
- [ ] URL reflects filters (shareable)

### 5.3 Calendar Page
- [ ] Fetch /api/calendar
- [ ] Render week view grid
- [ ] Show events in time slots
- [ ] Highlight conflicts
- [ ] Show analysis panel
- [ ] Day/week/month toggle
- [ ] Navigation (prev/next)

### 5.4 Tasks Page
- [ ] Fetch /api/tasks with filters
- [ ] Render task table
- [ ] Filter by project, assignee, status, lane
- [ ] Sort by priority, due date, etc.
- [ ] Bulk selection works
- [ ] Actions work (complete, delegate, etc.)

### 5.5 Team Page
- [ ] Fetch /api/team
- [ ] Render team member cards
- [ ] Show workload stats per person
- [ ] Fetch /api/delegations
- [ ] Render delegation tracker
- [ ] Follow-up indicators
- [ ] Remind/recall actions

### 5.6 Inbox Page
- [ ] Fetch /api/inbox
- [ ] Render VIP section
- [ ] Render needs response section
- [ ] Mark done action
- [ ] Create task from email
- [ ] Open in Gmail link

### 5.7 Projects Page
- [ ] Fetch /api/projects
- [ ] Render project cards with health
- [ ] Show progress bars
- [ ] Show blockers
- [ ] Drill into project tasks

### 5.8 Insights Page
- [ ] Fetch /api/insights
- [ ] Group by type (anomaly, pattern, recommendation)
- [ ] Dismiss action
- [ ] Act on recommendation

### 5.9 Decisions Page
- [ ] Fetch /api/decisions
- [ ] Render pending decisions
- [ ] Approve action
- [ ] Reject action
- [ ] Show execution result

### 5.10 Settings Page
- [ ] Governance mode toggles per domain
- [ ] Sync status and manual sync buttons
- [ ] Show last sync times

---

## Phase 6: Background Operations (Days 15-16)

### 6.1 Sync Automation
- [ ] Create cron script for all syncs
- [ ] Install cron jobs
- [ ] Verify syncs run on schedule
- [ ] Verify analysis runs after sync

### 6.2 Error Handling
- [ ] Sync errors logged to sync_state
- [ ] Consecutive error tracking
- [ ] Alert if source unhealthy
- [ ] Auto-retry with backoff

### 6.3 Logging
- [ ] All operations logged with timestamps
- [ ] Log rotation configured
- [ ] Easy to tail logs for debugging

---

## Phase 7: Integration Testing (Days 17-18)

### 7.1 End-to-End Tests
- [ ] Create task in Asana → appears in dashboard priorities
- [ ] Complete task in dashboard → reflected in Asana
- [ ] Delegate task → appears in team page delegation tracker
- [ ] VIP email arrives → appears in inbox with correct tier
- [ ] Calendar conflict → shows in calendar page conflicts

### 7.2 Stability Test
- [ ] Run system for 24 hours
- [ ] Verify no memory leaks
- [ ] Verify no sync failures
- [ ] Verify dashboard responsive throughout

### 7.3 User Acceptance
- [ ] Moh uses dashboard for real work
- [ ] Gather feedback
- [ ] Fix critical issues

---

# PART 6: SUCCESS CRITERIA

The system is complete when:

1. **Data Complete**: All tasks, events, emails, projects visible in dashboard
2. **Priority Accurate**: Top 10 priorities match Moh's intuition
3. **Actions Work**: Complete/snooze/delegate reflected in source systems
4. **Team Visible**: Can see everyone's workload and delegations
5. **Alerts Working**: Critical issues surfaced automatically
6. **Reliable**: Runs 24/7 without intervention
7. **Fast**: Dashboard loads in < 2 seconds

---

**AWAITING APPROVAL BEFORE IMPLEMENTATION**
