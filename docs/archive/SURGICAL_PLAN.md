# MOH TIME OS — Surgical Enhancement Plan

## Overview

This plan addresses gaps where **backend capability exists** but is **not exposed in the dashboard**, and where **data exists** but is **not utilized**. Each item includes the exact files to modify, API endpoints to add/update, and UI components needed.

---

## PHASE 1: Governance & Control Panel
**Priority: CRITICAL** — Enables user control over automation

### 1.1 Governance Controls in Dashboard

**Backend exists:**
- `lib/governance.py` — `DomainMode` enum (observe/propose/auto_low/auto_high)
- `lib/governance.py:64` — `set_mode(domain, mode)`
- `lib/governance.py:223` — `get_status()`

**API exists but incomplete:**
- `GET /api/governance` — returns status ✅
- `PUT /api/governance/{domain}` — sets mode ✅
- `POST /api/governance/emergency-brake` — activates brake ✅
- `DELETE /api/governance/emergency-brake` — releases brake ✅

**UI needed:**
```
Location: Sidebar or Settings modal
Components:
├── Domain cards (tasks, calendar, email, notifications)
│   ├── Current mode indicator (color-coded)
│   ├── Mode dropdown (observe → propose → auto_low → auto_high)
│   └── Last action count
├── Emergency brake button (prominent red)
├── Rate limit display (actions remaining today)
└── Confidence threshold sliders (advanced)
```

**Files to modify:**
| File | Change |
|------|--------|
| `ui/index.html` | Add governance panel in sidebar |
| `api/server.py` | Add `GET /api/governance/rate-limits` endpoint |

**Effort:** 1-2 hours

---

### 1.2 Change Bundles & Rollback Panel

**Backend exists:**
- `lib/change_bundles.py:38` — `create_bundle()`
- `lib/change_bundles.py:170` — `rollback_bundle(bundle_id)`
- `lib/change_bundles.py:233` — `list_rollbackable_bundles()`

**API exists:**
- `GET /api/bundles` — list bundles ✅
- `GET /api/bundles/rollbackable` — list rollbackable ✅
- `POST /api/bundles/{id}/rollback` — execute rollback ✅

**UI needed:**
```
Location: New "History" tab or sidebar section
Components:
├── Recent changes list (last 20)
│   ├── Timestamp
│   ├── Description (e.g., "Complete task: Send proposal")
│   ├── Status badge (applied/pending/rolled_back)
│   └── Rollback button (if applicable)
├── Filter by domain (tasks/calendar/email)
└── Bulk undo (last N changes)
```

**Files to modify:**
| File | Change |
|------|--------|
| `ui/index.html` | Add "History" tab with bundle list |
| — | Wire rollback buttons to existing API |

**Effort:** 1 hour

---

## PHASE 2: Task Management Enhancements
**Priority: HIGH** — Core workflow improvements

### 2.1 Task Creation

**Backend exists:**
- `lib/executor/handlers/task.py` — `_create_task()` handler
- Supports: title, due_date, assignee, project, priority, tags

**API needed:**
```python
# Add to api/server.py
@app.post("/api/tasks")
async def create_task(body: TaskCreate):
    """Create a new task."""
    handler = TaskHandler(store)
    result = handler.execute({
        'action_type': 'create',
        'data': body.dict()
    })
    return result
```

**UI needed:**
```
Location: Floating action button + modal
Components:
├── Quick add bar (title only, enter to submit)
└── Full form modal
    ├── Title (required)
    ├── Due date picker
    ├── Assignee dropdown (from people table)
    ├── Project dropdown (from projects table)
    ├── Priority slider (or quick buttons: low/med/high)
    ├── Tags input
    └── Notes textarea
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add `POST /api/tasks` endpoint |
| `ui/index.html` | Add quick-add bar and create modal |

**Effort:** 2 hours

---

### 2.2 Task Editing & Notes

**Backend exists:**
- `lib/executor/handlers/task.py` — `_update_task()` handler
- Tasks table has `notes` field

**API needed:**
```python
@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    """Update task fields."""
    
@app.post("/api/tasks/{task_id}/notes")
async def add_task_note(task_id: str, body: NoteAdd):
    """Append note to task."""
```

**UI needed:**
```
Location: Task detail panel (slide-out or modal)
Components:
├── Editable title
├── Due date picker
├── Assignee selector
├── Project selector
├── Priority adjuster
├── Notes section
│   ├── Existing notes (timestamped)
│   └── Add note input
├── Activity log (changes history)
└── Action buttons (complete/archive/delete)
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add `PUT /api/tasks/{id}`, `POST /api/tasks/{id}/notes` |
| `ui/index.html` | Add task detail slide-out panel |

**Effort:** 2-3 hours

---

### 2.3 Full Delegation Workflow

**Backend exists:**
- `lib/executor/handlers/delegation.py` — Full workflow:
  - `delegate` — assign to team member
  - `escalate` — bump to higher priority/person
  - `handoff` — transfer with context
  - `recall` — take back delegated task

**API needed:**
```python
@app.post("/api/tasks/{task_id}/delegate")
async def delegate_task(task_id: str, body: DelegateRequest):
    """Delegate task with optional message."""

@app.post("/api/tasks/{task_id}/escalate")
async def escalate_task(task_id: str, body: EscalateRequest):
    """Escalate task priority/ownership."""

@app.post("/api/tasks/{task_id}/recall")
async def recall_task(task_id: str):
    """Recall a delegated task."""

@app.get("/api/delegations")
async def get_delegations():
    """Get all delegated tasks with status."""
```

**UI needed:**
```
Location: Task actions + dedicated "Delegated" view
Components:
├── Delegate button on each task
│   ├── Person selector
│   ├── Message input
│   └── Due date (optional override)
├── "Delegated by me" filter/tab
│   ├── Task list with delegate name
│   ├── Days since delegated
│   ├── Follow-up button
│   └── Recall button
└── "Delegated to me" filter/tab
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add delegation endpoints |
| `ui/index.html` | Add delegation UI in task actions + delegated view |

**Effort:** 3 hours

---

## PHASE 3: Calendar Integration
**Priority: HIGH** — Conflict resolution from dashboard

### 3.1 Calendar Actions

**Backend exists:**
- `lib/executor/handlers/calendar.py` — `_reschedule_event()` handler
- Events table has conflict detection fields

**API needed:**
```python
@app.post("/api/events/{event_id}/reschedule")
async def reschedule_event(event_id: str, body: RescheduleRequest):
    """Reschedule event to new time."""

@app.post("/api/events/{event_id}/decline")
async def decline_event(event_id: str, body: DeclineRequest):
    """Decline/cancel event."""

@app.get("/api/events/conflicts")
async def get_conflicts():
    """Get all conflicting events."""
```

**UI needed:**
```
Location: Today panel + Conflicts view
Components:
├── Today's events (already partial)
│   ├── Click to expand details
│   ├── Reschedule button → time picker
│   ├── Decline button → reason input
│   └── Prep notes display
├── Conflicts section
│   ├── Conflicting event pairs
│   ├── One-click resolution options
│   └── "Resolve all" with suggestions
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add calendar action endpoints |
| `ui/index.html` | Enhance today panel, add conflicts view |

**Effort:** 2-3 hours

---

## PHASE 4: Email Actions
**Priority: MEDIUM** — Beyond dismiss

### 4.1 Email Actions

**Backend exists:**
- `lib/executor/handlers/email.py` — Actions available:
  - `create` — draft new email
  - `send_immediate` — send now
  - `batch` — queue for batch send

**API needed:**
```python
@app.post("/api/emails/{email_id}/reply")
async def reply_to_email(email_id: str, body: ReplyRequest):
    """Create reply draft."""

@app.post("/api/emails/{email_id}/forward")
async def forward_email(email_id: str, body: ForwardRequest):
    """Forward email."""

@app.post("/api/emails/{email_id}/create-task")
async def create_task_from_email(email_id: str):
    """Convert email to task."""

@app.post("/api/emails/{email_id}/snooze")
async def snooze_email(email_id: str, hours: int = 4):
    """Snooze email for later."""
```

**UI needed:**
```
Location: Email tab items
Components:
├── Email item actions
│   ├── Reply (opens composer)
│   ├── Forward
│   ├── → Task (converts to task)
│   ├── Snooze (time picker)
│   └── Archive
├── Quick reply composer
│   ├── To (pre-filled)
│   ├── Subject (pre-filled with Re:)
│   ├── Body textarea
│   └── Send / Save draft
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add email action endpoints |
| `ui/index.html` | Add email actions and reply composer |

**Effort:** 3 hours

---

## PHASE 5: Analytics & Insights
**Priority: MEDIUM** — Visibility into patterns

### 5.1 Pattern Detection Display

**Backend exists:**
- `lib/analyzers/patterns.py:31` — `analyze_task_patterns()`
- `lib/analyzers/patterns.py:140` — `analyze_communication_patterns()`
- `lib/analyzers/patterns.py:212` — `analyze_meeting_patterns()`
- `lib/analyzers/patterns.py:267` — `detect_anomalies()`

**API needed:**
```python
@app.get("/api/analytics/patterns")
async def get_patterns():
    """Get detected patterns."""
    analyzer = PatternAnalyzer(store)
    return {
        'tasks': analyzer.analyze_task_patterns(),
        'communications': analyzer.analyze_communication_patterns(),
        'meetings': analyzer.analyze_meeting_patterns()
    }

@app.get("/api/analytics/anomalies")
async def get_anomalies():
    """Get current anomalies."""
    analyzer = PatternAnalyzer(store)
    return {'anomalies': analyzer.detect_anomalies()}
```

**UI needed:**
```
Location: New "Insights" tab or dashboard section
Components:
├── Task patterns
│   ├── Avg completion time by project
│   ├── Overdue rate by assignee
│   └── Peak creation days/times
├── Communication patterns
│   ├── Response time trends
│   ├── High-volume senders
│   └── Unresponded threads
├── Meeting patterns
│   ├── Hours per week trend
│   ├── Back-to-back frequency
│   └── Recurring vs one-off ratio
├── Anomalies list
│   ├── Current issues
│   └── Suggested actions
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add analytics endpoints |
| `ui/index.html` | Add Insights tab with pattern displays |

**Effort:** 3-4 hours

---

### 5.2 Calibration & Feedback Loop

**Backend exists:**
- `lib/calibration.py:25` — `run_weekly_calibration()`
- `lib/calibration.py:48` — `_analyze_feedback()`
- `lib/calibration.py:160` — `get_last_calibration()`
- Feedback table exists

**API exists partially:**
- `GET /api/calibration` — get last calibration ✅
- `POST /api/calibration/run` — trigger calibration ✅

**API needed:**
```python
@app.post("/api/feedback")
async def submit_feedback(body: FeedbackRequest):
    """Submit priority/action feedback."""
    # Store in feedback table
    
@app.get("/api/calibration/recommendations")
async def get_recommendations():
    """Get calibration recommendations."""
```

**UI needed:**
```
Location: Each task + settings panel
Components:
├── Per-task feedback
│   ├── "Priority wrong?" quick button
│   ├── Thumbs up/down on suggestions
│   └── "This shouldn't be here" flag
├── Calibration panel (settings)
│   ├── Last calibration date
│   ├── Recommendations list
│   ├── "Run calibration" button
│   └── Accuracy metrics
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add feedback endpoint, recommendations endpoint |
| `ui/index.html` | Add feedback buttons, calibration panel |

**Effort:** 2 hours

---

## PHASE 6: Data Utilization
**Priority: MEDIUM** — Use existing data

### 6.1 Client View

**Data exists:**
- `clients` table — 166 clients
- Tasks have client associations (via project or direct)

**API needed:**
```python
@app.get("/api/clients")
async def get_clients(limit: int = 50):
    """Get clients with task counts."""

@app.get("/api/clients/{client_id}")
async def get_client(client_id: str):
    """Get client details with all tasks."""

@app.get("/api/clients/{client_id}/tasks")
async def get_client_tasks(client_id: str):
    """Get all tasks for client."""
```

**UI needed:**
```
Location: New "Clients" tab
Components:
├── Client list
│   ├── Name
│   ├── Tier (A/B/C)
│   ├── Health indicator
│   ├── Open task count
│   └── Overdue count
├── Client detail view
│   ├── All tasks for client
│   ├── Recent communications
│   ├── Upcoming events
│   └── Health history
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add client endpoints |
| `ui/index.html` | Add Clients tab |

**Effort:** 2-3 hours

---

### 6.2 Enhanced Task Fields Display

**Data exists but not shown:**
- `effort_min`, `effort_max` — time estimates
- `sensitivity` — confidential flags
- `tags` — categorization
- `deadline_type` — soft/hard
- `waiting_for` — blocked reason

**UI changes needed:**
```
Location: Task list items + detail panel
Components:
├── Task item badges
│   ├── ⏱️ Effort estimate (e.g., "2-4h")
│   ├── 🔒 Sensitivity flag
│   ├── 🏷️ Tags (clickable to filter)
│   ├── ⚠️ Hard deadline indicator
│   └── ⏳ Waiting for (blocker text)
├── Filter additions
│   ├── Filter by tag
│   ├── Filter by effort range
│   └── Filter by deadline type
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Extend filtered endpoint with new params |
| `ui/index.html` | Add badges and filters |

**Effort:** 1-2 hours

---

### 6.3 People/Team View

**Data exists:**
- `people` table with team members
- Workload already calculated

**API exists partially:**
- `GET /api/team/workload` ✅

**API needed:**
```python
@app.get("/api/people")
async def get_people():
    """Get all people with details."""

@app.get("/api/people/{person_id}/tasks")
async def get_person_tasks(person_id: str):
    """Get all tasks for person."""

@app.get("/api/people/{person_id}/capacity")
async def get_person_capacity(person_id: str):
    """Get capacity analysis for person."""
```

**UI needed:**
```
Location: Enhanced Team panel + Team tab
Components:
├── Team panel (sidebar) — exists, enhance:
│   ├── Capacity bar (visual)
│   ├── Trend indicator (↑↓)
│   └── Click to see all tasks
├── Team tab (full view)
│   ├── All team members
│   ├── Workload comparison chart
│   ├── Delegation suggestions
│   └── Capacity planning
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add people endpoints |
| `ui/index.html` | Enhance team panel, add team tab |

**Effort:** 2 hours

---

## PHASE 7: Notifications
**Priority: HIGH** — Complete the loop

### 7.1 Notification Management

**Backend exists:**
- `lib/notifier/engine.py` — Full notification engine
- `notifications` table — 50+ queued notifications
- Channels: clawdbot (needs WhatsApp link)

**API exists:**
- `GET /api/notifications` ✅

**API needed:**
```python
@app.post("/api/notifications/{notif_id}/send")
async def send_notification(notif_id: str):
    """Manually send a notification."""

@app.post("/api/notifications/{notif_id}/dismiss")
async def dismiss_notification(notif_id: str):
    """Dismiss without sending."""

@app.post("/api/notifications/send-all")
async def send_all_pending():
    """Send all pending notifications."""

@app.get("/api/notifications/settings")
async def get_notification_settings():
    """Get notification preferences."""
```

**UI needed:**
```
Location: Notifications panel + settings
Components:
├── Notification queue
│   ├── Pending notifications list
│   ├── Send now button (per item)
│   ├── Dismiss button
│   └── Send all button
├── Notification settings
│   ├── Channel status (WhatsApp linked?)
│   ├── Quiet hours config
│   ├── Priority thresholds
│   └── Batch vs immediate toggle
```

**Prerequisite:** Run `clawdbot channels login --channel whatsapp`

**Files to modify:**
| File | Change |
|------|--------|
| `api/server.py` | Add notification action endpoints |
| `ui/index.html` | Add notification panel and settings |

**Effort:** 2 hours

---

## Implementation Order

| Phase | Items | Effort | Cumulative |
|-------|-------|--------|------------|
| 1 | Governance + Rollback | 3h | 3h |
| 2 | Task create + edit + delegation | 7h | 10h |
| 3 | Calendar actions | 3h | 13h |
| 4 | Email actions | 3h | 16h |
| 5 | Analytics + calibration | 5h | 21h |
| 6 | Client + fields + team | 6h | 27h |
| 7 | Notifications | 2h | 29h |

**Total estimated effort: ~29 hours**

---

## Quick Wins (< 30 min each)

1. **Show effort estimates** — Add badge to task items
2. **Show tags** — Add tag badges, click to filter
3. **Show deadline type** — Hard deadline warning icon
4. **Enhanced today events** — Show prep notes
5. **Rollback panel** — Wire existing API to UI
6. **Governance dropdowns** — Wire existing API to UI

---

## File Summary

| File | Changes |
|------|---------|
| `api/server.py` | ~15 new endpoints |
| `ui/index.html` | Major restructure + new tabs |
| `lib/executor/handlers/*.py` | No changes (already complete) |
| `lib/governance.py` | No changes (already complete) |
| `lib/change_bundles.py` | No changes (already complete) |

---

## Next Action

Start with **Phase 1** (Governance + Rollback) — gives immediate control over the system and visibility into changes. Then proceed through phases in order.

Confirm to begin implementation.
