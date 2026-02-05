# 02_SOURCES_AND_COLLECTORS.md — External Sources & Collectors

> Phase A Deliverable | Generated: 2026-02-04

---

## 1. Collector Registry

| Collector | Source System | Target Table(s) | Sync Interval | Status |
|-----------|---------------|-----------------|---------------|--------|
| `TasksCollector` | Google Tasks | `tasks` | 300s (5m) | ENABLED |
| `CalendarCollector` | Google Calendar | `events` | 60s (1m) | ENABLED |
| `GmailCollector` | Gmail | `communications` | 120s (2m) | ENABLED |
| `AsanaCollector` | Asana | `tasks`, `projects` | 300s (5m) | ENABLED |
| `XeroCollector` | Xero | `invoices`, `clients` | 300s (5m) | ENABLED |
| `TeamCalendarCollector` | Google Calendar (team) | `team_events`, `team_capacity` | 300s | AVAILABLE |

---

## 2. TasksCollector (Google Tasks)

**Source:** Google Tasks via `gog tasks` CLI  
**Target Table:** `tasks`  
**Sync Interval:** 300 seconds (5 minutes)

### Fields Produced

| Field | Type | Source Mapping | Notes |
|-------|------|----------------|-------|
| `id` | TEXT | `gtask_{task_id}` | Prefixed for uniqueness |
| `source` | TEXT | `'google_tasks'` | Literal |
| `source_id` | TEXT | `task.id` | Original Google Tasks ID |
| `title` | TEXT | `task.title` | Task title |
| `status` | TEXT | Mapped from `task.status` | 'completed' → 'done', else 'pending' |
| `priority` | INTEGER | Computed | 0-100 based on due date urgency |
| `due_date` | TEXT | `task.due[:10]` | ISO date only |
| `due_time` | TEXT | NULL | Google Tasks doesn't have times |
| `assignee` | TEXT | NULL | Google Tasks doesn't support assignees |
| `project` | TEXT | `task._list_name` | Task list name |
| `lane` | TEXT | '' | Empty, filled by lane_assigner |
| `sensitivity` | TEXT | '' | Empty |
| `tags` | TEXT | '[]' | JSON array |
| `dependencies` | TEXT | '[]' | JSON array |
| `blockers` | TEXT | '[]' | JSON array |
| `context` | TEXT | JSON(task) | Full raw task object |
| `created_at` | TEXT | `task.updated` | Google Tasks uses updated time |
| `updated_at` | TEXT | NOW | Current timestamp |
| `synced_at` | TEXT | NOW | Sync timestamp |

### Raw Data Shape

```json
{
  "tasks": [
    {
      "id": "MTcxNzg5...",
      "title": "Review contract",
      "status": "needsAction",
      "due": "2026-02-15T00:00:00.000Z",
      "notes": "Client: GMG",
      "_list_id": "MTM0NzYy...",
      "_list_name": "Work"
    }
  ]
}
```

### Priority Computation

```python
score = 50  # Base
if overdue: score += min(40, 40 + days_overdue * 2)
elif due_today: score += 35
elif due_tomorrow: score += 25
elif due_within_3_days: score += 15
elif due_within_7_days: score += 5
if has_notes: score += 5
return clamp(0, 100, score)
```

---

## 3. CalendarCollector (Google Calendar)

**Source:** Google Calendar via `gog calendar` CLI  
**Target Table:** `events`  
**Sync Interval:** 60 seconds (1 minute)  
**Lookback:** 30 days | **Lookahead:** 30 days

### Fields Produced

| Field | Type | Source Mapping | Notes |
|-------|------|----------------|-------|
| `id` | TEXT | `calendar_{event_id}` | Prefixed |
| `source` | TEXT | `'calendar'` | Literal |
| `source_id` | TEXT | `event.id` | Original Calendar event ID |
| `title` | TEXT | `event.summary` | Event title |
| `start_time` | TEXT | Parsed from `event.start` | ISO datetime |
| `end_time` | TEXT | Parsed from `event.end` | ISO datetime |
| `location` | TEXT | `event.location` | Physical or virtual location |
| `attendees` | TEXT | JSON array of emails | Extracted from attendees |
| `status` | TEXT | `event.status` | 'confirmed', 'tentative', 'cancelled' |
| `prep_notes` | TEXT | JSON | Inferred prep requirements |
| `context` | TEXT | JSON(event) | Full raw event object |
| `created_at` | TEXT | `event.created` | Event creation timestamp |
| `updated_at` | TEXT | NOW | Current timestamp |

### Additional Schema Columns (not from collector)

| Field | Type | Description |
|-------|------|-------------|
| `sensitivity` | TEXT | Manual: 'public', 'private', 'confidential' |
| `is_system_owned` | INTEGER | 1 if created by system |
| `linked_task_id` | TEXT | FK to tasks.id if linked |
| `all_day` | INTEGER | 1 if all-day event |
| `has_conflict` | INTEGER | 1 if conflicts detected |
| `conflict_with` | TEXT | ID of conflicting event |
| `prep_required` | TEXT | Legacy field |

### Prep Inference Rules

```python
prep = {'time_minutes': 15, 'items': []}
if 'interview' or 'presentation' or 'pitch' or 'demo' in title:
    prep['time_minutes'] = 30
    prep['items'].append('Review materials')
if '1:1' or '1-1' or 'one on one' in title:
    prep['items'].append('Check notes from last meeting')
if 'call' or 'meeting' in title:
    prep['items'].append('Join link ready')
if location and not virtual:
    prep['time_minutes'] += 15  # Travel
    prep['items'].append('Travel to location')
```

---

## 4. GmailCollector (Gmail)

**Source:** Gmail via `gog gmail` CLI  
**Target Table:** `communications`  
**Sync Interval:** 120 seconds (2 minutes)  
**Lookback:** 90 days  
**Max Results:** 500

### Fields Produced

| Field | Type | Source Mapping | Notes |
|-------|------|----------------|-------|
| `id` | TEXT | `gmail_{thread_id}` | Prefixed |
| `source` | TEXT | `'gmail'` | Literal |
| `source_id` | TEXT | `thread.id` | Original thread ID |
| `thread_id` | TEXT | `thread.id` | For conversation threading |
| `from_email` | TEXT | Extracted from `thread.from` | Sender email |
| `from_name` | TEXT | Extracted from `thread.from` | Sender display name |
| `to_emails` | TEXT | Extracted from `thread.to` | Recipients |
| `subject` | TEXT | `thread.subject` | Email subject |
| `snippet` | TEXT | `thread.snippet` | Preview snippet |
| `body_text` | TEXT | Fetched via `gog gmail get` | Full message body |
| `body_text_source` | TEXT | 'html_stripped', 'plain', 'snippet_fallback' | Body extraction method |
| `content_hash` | TEXT | SHA256 of subject+snippet | For deduplication |
| `received_at` | TEXT | `thread.date` | Email timestamp |
| `is_unread` | INTEGER | From labels | 1 if UNREAD label |
| `is_starred` | INTEGER | From labels | 1 if STARRED label |
| `is_important` | INTEGER | From labels | 1 if IMPORTANT label |
| `labels` | TEXT | JSON array | Gmail labels |
| `created_at` | TEXT | NOW | Insert timestamp |
| `updated_at` | TEXT | NOW | Update timestamp |

### Derived Fields (from normalizer)

| Field | Type | Derivation |
|-------|------|------------|
| `from_domain` | TEXT | Extracted from from_email |
| `client_id` | TEXT | Matched via client_identities |
| `link_status` | TEXT | 'linked' or 'unlinked' |

### Query Filters

```
"newer_than:90d -category:promotions -category:updates -category:social"
```

### Body Fetching

For each thread, collector attempts to fetch full body via:
```bash
gog gmail get {thread_id} --json
```

Body processing:
1. If HTML: Strip tags, decode entities, normalize whitespace
2. If plain: Use as-is
3. On failure: Use snippet as fallback

---

## 5. AsanaCollector (Asana)

**Source:** Asana API via `engine/asana_client.py`  
**Target Tables:** `tasks`, `projects`  
**Sync Interval:** 300 seconds (5 minutes)  
**Workspace:** hrmny (GID: 1148006162435561)

### Fields Produced (tasks)

| Field | Type | Source Mapping | Notes |
|-------|------|----------------|-------|
| `id` | TEXT | `asana_{gid}` | Prefixed |
| `source` | TEXT | `'asana'` | Literal |
| `source_id` | TEXT | `task.gid` | Asana GID |
| `title` | TEXT | `task.name` | Task name |
| `status` | TEXT | Computed | 'completed', 'overdue', 'active' |
| `priority` | TEXT | 'high' if overdue else 'normal' | Priority string |
| `due_date` | TEXT | `task.due_at` or `task.due_on + T23:59:59` | ISO datetime |
| `assignee` | TEXT | `task.assignee.name` | Assignee display name |
| `project` | TEXT | `task._project_name` | Project name (injected) |
| `project_id` | TEXT | NULL initially | Linked by normalizer |
| `notes` | TEXT | `task.notes[:500]` | Task description (truncated) |
| `tags` | TEXT | JSON array of tag names | From `task.tags[].name` |
| `created_at` | TEXT | `task.created_at` | Task creation |
| `updated_at` | TEXT | `task.modified_at` | Last modification |

### Asana API Fields Available (but not all collected)

```
gid, name, notes, completed, completed_at, due_on, due_at,
start_on, start_at, assignee, assignee_status, followers,
parent, projects, memberships, tags, workspace, custom_fields,
html_notes, num_hearts, num_likes, resource_type, resource_subtype
```

### Projects Sync (via AsanaSyncCollector)

The `asana_sync.py` collector also syncs:

| Field | Type | Source |
|-------|------|--------|
| `projects.id` | TEXT | `proj_{gid}` |
| `projects.name` | TEXT | `project.name` |
| `projects.source` | TEXT | 'asana' |
| `projects.status` | TEXT | 'active' or 'completed' |
| `asana_project_map.asana_gid` | TEXT | Asana GID |
| `asana_project_map.project_id` | TEXT | Internal project ID |
| `asana_user_map.asana_gid` | TEXT | Asana user GID |
| `asana_user_map.team_member_id` | TEXT | Internal team_member ID |

---

## 6. XeroCollector (Xero)

**Source:** Xero API via `collectors/xero_ops.py`  
**Target Tables:** `invoices`, `clients`  
**Sync Interval:** 300 seconds (5 minutes)

### Fields Produced (invoices)

| Field | Type | Source Mapping | Notes |
|-------|------|----------------|-------|
| `id` | TEXT | `xero_{invoice_number}` | Prefixed, sanitized |
| `source` | TEXT | `'xero'` | Literal |
| `external_id` | TEXT | `inv.number` | Invoice number |
| `client_id` | TEXT | Matched from clients by name | FK to clients |
| `client_name` | TEXT | `inv.contact` | Contact name from Xero |
| `amount` | REAL | `inv.amount_due` | Outstanding amount |
| `currency` | TEXT | `inv.currency` or 'AED' | Currency code |
| `issue_date` | TEXT | `inv.due_date` (proxy) | Issue date |
| `due_date` | TEXT | `inv.due_date` | Due date |
| `status` | TEXT | 'overdue' if overdue else 'sent' | Computed |
| `aging_bucket` | TEXT | Computed from days_overdue | 'current', '1-30', '31-60', '61-90', '90+' |
| `created_at` | TEXT | NOW | Insert timestamp |
| `updated_at` | TEXT | NOW | Update timestamp |

### Fields Updated (clients)

| Field | Type | Description |
|-------|------|-------------|
| `financial_ar_outstanding` | REAL | Sum of AR for client |
| `financial_ar_aging` | TEXT | Worst aging bucket |
| `updated_at` | TEXT | Update timestamp |

### Aging Bucket Calculation

```python
days_over = days_overdue if overdue else 0
if days_over >= 90: return '90+'
elif days_over >= 61: return '61-90'
elif days_over >= 31: return '31-60'
elif days_over >= 1: return '1-30'
else: return 'current'
```

### Xero API Fields Available

From `get_outstanding_invoices()`:
```
contact, number, amount_due, due_date, is_overdue, days_overdue, currency
```

---

## 7. TeamCalendarCollector

**Source:** Google Calendar (multiple team accounts)  
**Target Tables:** `team_events`, `team_capacity`  
**Status:** AVAILABLE (not always enabled)

### Fields Produced (team_events)

| Field | Type | Source Mapping |
|-------|------|----------------|
| `id` | TEXT | `team_cal_{event_id}` |
| `source` | TEXT | 'team_calendar' |
| `source_id` | TEXT | Event ID |
| `owner_email` | TEXT | Calendar owner email |
| `owner_name` | TEXT | Calendar owner name |
| `title` | TEXT | Event summary |
| `start_time` | TEXT | Event start |
| `end_time` | TEXT | Event end |
| `attendees` | TEXT | JSON array |
| `is_external` | INTEGER | 1 if has external attendees |
| `status` | TEXT | Event status |
| `organizer` | TEXT | Organizer email |
| `raw` | TEXT | JSON of full event |
| `client_id` | TEXT | Matched from event |
| `client_match_source` | TEXT | How client was matched |
| `project_id` | TEXT | Matched from event |
| `project_match_source` | TEXT | How project was matched |
| `meet_code` | TEXT | Google Meet code if present |

### Fields Produced (team_capacity)

| Field | Type | Description |
|-------|------|-------------|
| `email` | TEXT | Team member email (PK) |
| `name` | TEXT | Display name |
| `event_count` | INTEGER | Total events in period |
| `meeting_hours` | REAL | Total meeting hours |
| `external_hours` | REAL | Hours with external attendees |
| `available_hours` | REAL | Remaining capacity |
| `utilization_pct` | REAL | Percentage utilized |
| `computed_at` | TEXT | Computation timestamp |

---

## 8. Sync State Tracking

**Table:** `sync_state`

| Field | Type | Description |
|-------|------|-------------|
| `source` | TEXT | Collector name (PK) |
| `last_sync` | TEXT | Last sync attempt timestamp |
| `last_success` | TEXT | Last successful sync timestamp |
| `items_synced` | INTEGER | Items synced in last run |
| `error` | TEXT | Error message if failed |

Current sync state query:
```sql
SELECT source, last_sync, last_success, items_synced, error 
FROM sync_state ORDER BY last_sync DESC;
```

---

## 9. Data Not Yet Collected (Opportunities)

### Available but Not Wired

| Source | Data Type | Potential Table | Effort |
|--------|-----------|-----------------|--------|
| Google Contacts | Contacts | `people` | Low |
| Google Drive | Documents | `documents` | Medium |
| Slack | Messages | `communications` | Medium |
| Notion | Pages | `documents` | Medium |
| HubSpot | CRM | `clients`, `communications` | High |
| Jira | Issues | `tasks` | Medium |
| Linear | Issues | `tasks` | Medium |
| Google Meet | Recordings | `recordings` | High |
| Zoom | Meetings | `events`, `recordings` | High |

### Data Quality Gaps

| Collector | Gap | Impact |
|-----------|-----|--------|
| Gmail | Body fetching rate-limited | 12% comm→client link rate |
| Asana | Only 15 projects synced | May miss tasks |
| Xero | No invoice line items | Can't see project-level AR |
| Calendar | No attachment extraction | Miss meeting docs |

---

## 10. CLI Tool References

All collectors use `gog` CLI for Google Workspace:

```bash
gog tasks lists --json           # List task lists
gog tasks list {list_id} --json  # List tasks in list
gog calendar list --from X --to Y --max N --json
gog gmail search "{query}" --max N --json
gog gmail get {thread_id} --json # Get full message
```

Asana uses Python client:
```python
from engine.asana_client import list_projects, list_tasks_in_project
```

Xero uses internal wrapper:
```python
from collectors.xero_ops import get_outstanding_invoices
```

---

*End of 02_SOURCES_AND_COLLECTORS.md*
