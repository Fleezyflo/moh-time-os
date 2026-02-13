# MOH TIME OS — Design Document v3

**Date:** 2026-02-01  
**Status:** DRAFT - Awaiting Approval  
**Objective:** A personal operating system that lets Moh see and control his entire world from one place.

---

## 1. THE PROBLEM

Moh runs an agency (HRMNY), manages a team, handles clients, and works on music. Information lives in:
- Asana (tasks, projects)
- Gmail (communications)
- Google Calendar (events)
- Apollo (leads/outreach)

**Current pain:**
- No single view of everything
- Mental overhead tracking what matters
- Things slip through cracks
- No visibility into team's work
- No early warning when things go wrong

---

## 2. THE SOLUTION

**MOH TIME OS** — A command center that:

1. **Aggregates** all data into one place
2. **Analyzes** and prioritizes intelligently  
3. **Surfaces** what needs attention
4. **Enables** direct action without friction
5. **Tracks** team and delegations
6. **Alerts** proactively when things go wrong

---

## 3. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                        MOH TIME OS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │  COLLECTORS │────▶│   STATE     │────▶│  DASHBOARD  │       │
│  │             │     │   STORE     │     │    (UI)     │       │
│  │ Asana       │     │             │     │             │       │
│  │ Gmail       │     │ - Tasks     │     │ - Overview  │       │
│  │ Calendar    │     │ - Events    │     │ - Priorities│       │
│  │ Apollo      │     │ - Comms     │     │ - Calendar  │       │
│  └─────────────┘     │ - Projects  │     │ - Tasks     │       │
│        │             │ - People    │     │ - Team      │       │
│        │             │ - Insights  │     │ - Inbox     │       │
│        ▼             └─────────────┘     │ - Projects  │       │
│  ┌─────────────┐           │            │ - Insights  │       │
│  │  ANALYZERS  │◀──────────┘            └─────────────┘       │
│  │             │                              │                │
│  │ Priority    │                              │                │
│  │ Time        │                              ▼                │
│  │ Patterns    │                        ┌─────────────┐       │
│  │ Anomalies   │                        │     API     │       │
│  └─────────────┘                        │   SERVER    │       │
│        │                                └─────────────┘       │
│        ▼                                                       │
│  ┌─────────────┐                                              │
│  │  REASONER   │──▶ Decisions requiring approval              │
│  └─────────────┘                                              │
│        │                                                       │
│        ▼                                                       │
│  ┌─────────────┐                                              │
│  │  EXECUTOR   │──▶ Approved actions executed                 │
│  └─────────────┘                                              │
│                                                                │
├─────────────────────────────────────────────────────────────────┤
│  SUPPLEMENTARY: AI Assistant (Clawdbot)                        │
│  - Complex delegation                                          │
│  - Judgment calls                                              │
│  - Proactive critical alerts                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. THE DASHBOARD (Primary Interface)

The dashboard is where Moh goes to see and control everything.

### 4.1 Overview Page (Home)

**Purpose:** At-a-glance state of everything

**Shows:**
- Today's date and time
- Top 5 priorities with one-click actions
- Next 3 upcoming events
- Alert banner if critical issues exist
- Quick stats:
  - Tasks due today: X
  - Overdue items: X
  - Pending responses: X
  - Team blocked items: X

**Actions:**
- Click any item to drill down
- Quick complete/snooze on priorities

---

### 4.2 Priorities Page

**Purpose:** Full prioritized queue of everything needing attention

**Shows:**
- All actionable items ranked by score
- Each item shows:
  - Type icon (task/email/event)
  - Title
  - Source (Asana project, Gmail label)
  - Due date
  - Priority score + reason
  - Assignee (if delegated)

**Filters:**
- Type: Tasks / Emails / All
- Lane: Ops / Client / Finance / Music / etc.
- Status: All / Overdue / Due Today / Due This Week
- Assignee: Me / Delegated / Team

**Actions per item:**
- ✓ Complete
- ⏰ Snooze (1h, 4h, tomorrow, next week)
- → Delegate (select person)
- 📌 Pin to top
- ↗ Open in source system

---

### 4.3 Calendar Page

**Purpose:** Visual view of time allocation and availability

**Shows:**
- Week view (default) / Day view / Month view
- Events from all calendars color-coded
- Task due dates shown as markers
- Available time slots highlighted
- Conflicts shown in red

**Analysis panel:**
- Today's utilization: X%
- Deep work available: Xh
- Meeting load: Xh
- Conflicts: X

**Actions:**
- Click slot to create event
- Drag to reschedule (if system-owned)
- Click event for details

---

### 4.4 Tasks Page

**Purpose:** Full task management view

**Shows:**
- All tasks from Asana + manual
- Grouped by: Project / Lane / Assignee / Status

**Columns:**
- Task title
- Project
- Assignee
- Due date
- Priority
- Status
- Blockers (if any)

**Filters:**
- Project
- Assignee (Me / Team member / Unassigned)
- Status (Pending / In Progress / Blocked / Done)
- Lane
- Overdue only

**Actions:**
- Complete
- Change assignee
- Change due date
- Add blocker note
- Open in Asana

---

### 4.5 Team Page

**Purpose:** See what the team is working on, track delegations

**Shows:**
- List of team members
- Each person shows:
  - Name, role
  - Current tasks assigned
  - Overdue items
  - Blocked items
  - Last activity

**Delegation Tracker:**
- Items I delegated
- Status of each
- Days since delegated
- Follow-up needed indicator

**Actions:**
- View person's full task list
- Send reminder
- Recall delegation
- Escalate

---

### 4.6 Inbox Page

**Purpose:** Communications requiring attention

**Shows:**
- Emails requiring response
- Grouped by:
  - VIP (priority senders)
  - Needs Response
  - FYI / Low Priority

**Each email shows:**
- From (with VIP badge if applicable)
- Subject
- Snippet
- Age
- Thread indicator

**Actions:**
- Mark processed
- Create task from email
- Open in Gmail
- Quick reply (draft)

---

### 4.7 Projects Page

**Purpose:** Health and status of all projects

**Shows:**
- All projects from Asana
- Each project shows:
  - Name
  - Health (Green/Yellow/Red)
  - Progress (tasks done / total)
  - Owner
  - Deadline
  - Blockers
  - Next milestone

**Health calculated from:**
- % tasks overdue
- Days to deadline vs work remaining
- Blocked items count

**Actions:**
- Drill into project tasks
- Open in Asana

---

### 4.8 Insights Page

**Purpose:** Patterns, anomalies, recommendations

**Shows:**
- Active insights grouped by type:
  - Anomalies (things wrong)
  - Patterns (things detected)
  - Recommendations (suggested actions)

**Each insight shows:**
- Type icon
- Description
- Confidence score
- Suggested action (if any)

**Actions:**
- Dismiss
- Act on recommendation
- Snooze for X days

---

### 4.9 Decisions Page

**Purpose:** Items requiring approval

**Shows:**
- Pending decisions the system wants to make
- Each shows:
  - What it wants to do
  - Why (rationale)
  - Confidence score
  - Options available

**Actions:**
- Approve
- Reject
- Modify and approve

---

### 4.10 Settings Page

**Purpose:** Configure system behavior

**Sections:**
- **Governance:** Set mode per domain (Observe/Propose/Auto)
- **Lanes:** Configure work lanes and capacity
- **VIP:** Manage priority contacts
- **Delegation:** Configure delegates and routing
- **Notifications:** Alert preferences
- **Sync:** Source connection status and manual sync

---

## 5. BACKEND REQUIREMENTS

### 5.1 Data Collection

| Source | Data | Sync Interval |
|--------|------|---------------|
| Asana | Tasks, Projects | 5 min |
| Gmail | Emails (Inbox, Important) | 2 min |
| Calendar | Events (14 days ahead) | 2 min |
| Apollo | Leads, Sequences | 10 min |

### 5.2 State Store (SQLite)

**Tables needed:**
- `tasks` - All tasks with priority scores
- `events` - Calendar events
- `communications` - Emails
- `projects` - Project health data
- `people` - Team and contacts with VIP flags
- `insights` - Detected patterns/anomalies
- `decisions` - Pending approvals
- `notifications` - Alert queue
- `actions` - Execution log
- `delegation_log` - Track delegations

### 5.3 Analysis Pipeline

Runs after each sync:

1. **Priority Scoring**
   - Score all tasks and emails 0-100
   - Factors: due date, explicit priority, sender importance, project criticality
   
2. **Time Analysis**
   - Calculate daily/weekly utilization
   - Find conflicts
   - Identify available slots
   
3. **Anomaly Detection**
   - Overdue items
   - Scheduling conflicts
   - Stale tasks (no update in X days)
   - VIP emails aging
   - Team blockers
   
4. **Pattern Recognition**
   - Recurring delays
   - Productivity patterns
   - Communication patterns

### 5.4 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/overview` | GET | Dashboard home data |
| `/api/priorities` | GET | Priority queue |
| `/api/priorities/:id/complete` | POST | Mark complete |
| `/api/priorities/:id/snooze` | POST | Snooze item |
| `/api/priorities/:id/delegate` | POST | Delegate item |
| `/api/calendar` | GET | Events + analysis |
| `/api/calendar/:date` | GET | Specific day |
| `/api/tasks` | GET | All tasks |
| `/api/tasks/:id` | GET/PATCH | Single task |
| `/api/team` | GET | Team overview |
| `/api/team/:id` | GET | Person details |
| `/api/delegations` | GET | Delegation tracker |
| `/api/inbox` | GET | Communications |
| `/api/inbox/:id/process` | POST | Mark processed |
| `/api/projects` | GET | All projects |
| `/api/projects/:id` | GET | Project details |
| `/api/insights` | GET | Active insights |
| `/api/insights/:id/dismiss` | POST | Dismiss insight |
| `/api/decisions` | GET | Pending decisions |
| `/api/decisions/:id` | POST | Approve/reject |
| `/api/settings/governance` | GET/PUT | Governance config |
| `/api/sync` | POST | Force sync |
| `/api/health` | GET | System health |

---

## 6. AI ASSISTANT ROLE (Supplementary)

The AI (me) is NOT the primary interface. The dashboard is.

**AI is used for:**

1. **Complex Delegation**
   - "Handle routine admin emails"
   - Requires judgment, not just rules

2. **Proactive Critical Alerts**
   - VIP email aging > 4 hours
   - Critical deadline at risk
   - NOT routine updates

3. **Analysis & Advice**
   - "What should I prioritize today?"
   - "Is this project at risk?"

4. **Bulk Operations**
   - "Clear all notifications older than a week"
   - "Reassign all Jana's tasks to Rene"

**AI is NOT used for:**
- Routine status checks (use dashboard)
- Simple actions (use dashboard)
- Regular briefings (use dashboard overview)

---

## 7. IMPLEMENTATION CHECKLIST

### Phase 1: Data Foundation
- [ ] 1.1 Verify all collectors working (Asana, Gmail, Calendar)
- [ ] 1.2 Verify data flowing to state store
- [ ] 1.3 Add missing tables (delegation_log)
- [ ] 1.4 Populate people table from Asana assignees + VIP config
- [ ] 1.5 Populate projects table from Asana
- [ ] 1.6 Test: Run sync, verify data in all tables

### Phase 2: Analysis Pipeline
- [ ] 2.1 Priority scoring working and accurate
- [ ] 2.2 Time analysis producing utilization + conflicts
- [ ] 2.3 Anomaly detection finding real issues
- [ ] 2.4 Cache analysis results for fast API access
- [ ] 2.5 Test: Verify priority queue makes sense

### Phase 3: API Server
- [ ] 3.1 All endpoints from 5.4 implemented
- [ ] 3.2 Endpoints return real data from state store
- [ ] 3.3 Action endpoints actually work (complete, snooze, delegate)
- [ ] 3.4 API server starts reliably
- [ ] 3.5 Test: curl each endpoint, verify responses

### Phase 4: Dashboard - Structure
- [ ] 4.1 Navigation between all pages
- [ ] 4.2 Overview page layout
- [ ] 4.3 Priorities page layout
- [ ] 4.4 Calendar page layout
- [ ] 4.5 Tasks page layout
- [ ] 4.6 Team page layout
- [ ] 4.7 Inbox page layout
- [ ] 4.8 Projects page layout
- [ ] 4.9 Insights page layout
- [ ] 4.10 Decisions page layout
- [ ] 4.11 Settings page layout

### Phase 5: Dashboard - Functionality
- [ ] 5.1 Overview fetches and displays data
- [ ] 5.2 Priorities with working filters and actions
- [ ] 5.3 Calendar with visual timeline
- [ ] 5.4 Tasks with grouping and filters
- [ ] 5.5 Team with delegation tracker
- [ ] 5.6 Inbox with VIP grouping
- [ ] 5.7 Projects with health indicators
- [ ] 5.8 Insights with dismiss/act
- [ ] 5.9 Decisions with approve/reject
- [ ] 5.10 Settings with governance controls

### Phase 6: Background Operations
- [ ] 6.1 Sync runs automatically (cron or daemon)
- [ ] 6.2 Analysis runs after each sync
- [ ] 6.3 System recovers from errors
- [ ] 6.4 Logs accessible for debugging

### Phase 7: Integration Test
- [ ] 7.1 Full flow: Data syncs → Analysis runs → Dashboard shows correct data
- [ ] 7.2 Actions work: Complete task in dashboard → Reflected in Asana
- [ ] 7.3 Delegation works: Delegate → Shows in team page → Tracked
- [ ] 7.4 Run for 24 hours, verify stability

---

## 8. SUCCESS CRITERIA

The system is successful when Moh can:

1. Open dashboard and immediately see what needs attention
2. See his entire team's workload and blockers
3. Track delegated items without manual follow-up
4. Get early warning when things are going wrong
5. Take action directly without switching to Asana/Gmail
6. Trust the priority scoring to surface what matters

---

## 9. OPEN QUESTIONS

1. **Sync frequency** - Is 5 min for Asana, 2 min for email right?
2. **Priority weights** - What factors matter most?
3. **Alert thresholds** - When should proactive alerts fire?
4. **Team scope** - Which team members to track?
5. **Mobile** - Is desktop dashboard enough or need mobile too?

---

**AWAITING APPROVAL BEFORE ANY IMPLEMENTATION**
