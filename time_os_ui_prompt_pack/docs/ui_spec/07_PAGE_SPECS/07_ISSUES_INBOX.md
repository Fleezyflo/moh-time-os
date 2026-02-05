# Page Spec: Issues Inbox

LOCKED_SPEC

## 1. Purpose
Central inbox for all issues with filtering by state, priority, and watcher visibility. Primary issue management interface.

## 2. Primary decisions enabled (max 3)
1. **Triage issues** — Review and prioritize open issues
2. **Update state** — Transition issues through workflow
3. **Monitor watchers** — Track upcoming triggers

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR: Filter [State ▼] [Priority ▼] | Search             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ISSUES LIST                                                 │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ● Issue #1 — Open | Critical                           │ │
│ │   Last activity: [relative] | Next trigger: [relative] │ │
│ │   Resolution: [criteria]                                │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ◐ Issue #2 — Monitoring | High                         │ │
│ │   Last activity: [relative]                            │ │
│ │   Resolution: [criteria]                                │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:** Full-width cards, filters as bottom sheet.

## 4. Primary surfaces

### 4.1 Issues List

**Query (from CONTROL_ROOM_QUERIES.md L16, extended for all states):**
```sql
SELECT i.*, 
  (SELECT MIN(next_check_at) FROM issue_watchers iw 
   WHERE iw.issue_id = i.issue_id AND iw.active = 1) as next_trigger
FROM issues i
WHERE (:stateFilter IS NULL OR i.state = :stateFilter)
  AND (:priorityFilter IS NULL OR i.priority = :priorityFilter)
ORDER BY 
  CASE i.priority 
    WHEN 'critical' THEN 1 
    WHEN 'high' THEN 2 
    WHEN 'medium' THEN 3 
    ELSE 4 
  END,
  i.last_activity_at DESC;
```

**Fields used (canonical IDs from PROPOSAL_ISSUE_ROOM_CONTRACT.md):**
- `issue_id` — unique identifier
- `state` — 'open'|'monitoring'|'awaiting'|'blocked'|'resolved'|'closed'
- `priority` — 'critical'|'high'|'medium'|'low'
- `headline` — from primary_ref or linked proposal
- `primary_ref` — reference identifier
- `resolution_criteria` — short form completion definition
- `last_activity_at` — ISO timestamp
- `next_trigger` — from watchers, ISO timestamp (computed in query)

**State icons:**
| State | Icon | Color |
|-------|------|-------|
| open | ● | red |
| monitoring | ◐ | amber |
| awaiting | ◑ | blue |
| blocked | ■ | slate |
| resolved | ✓ | green |
| closed | ○ | gray |

**Priority rendering:**
| Priority | Badge color |
|----------|-------------|
| critical | red |
| high | orange |
| medium | amber |
| low | gray |

**Watcher indicator:**
- If `next_trigger` exists and is within 24h window: show badge "Trigger: [relative time]"
- 24h window matches CONTROL_ROOM_QUERIES.md L17

**States:**
- Loading: skeleton rows
- Empty: "No issues"
- Filtered empty: "No issues match filters"
- Error: "Unable to load issues — retry"

**Interactions:**
- Tap row → open IssueDrawer
- Swipe right → Quick transition menu (state change)

## 5. Ranking/Sorting rules (deterministic)

Default sort: Priority DESC (critical → high → medium → low), then `last_activity_at DESC`.

Sort options:
- By priority (default)
- By last activity
- By state
- By next trigger

## 6. Filters & scope

**Filter controls:**
- State: All | Open | Monitoring | Awaiting | Blocked | Resolved | Closed
- Priority: All | Critical | High | Medium | Low

**Search:** Filter by headline text

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| IssueRow | Tap | IssueDrawer |
| Client chip | Tap | `/clients/:clientId` |
| Team chip | Tap | `/team/:id` |
| Proposal chip | Tap | RoomDrawer |

## 8. Drawer/Detail contract

**IssueDrawer:**
- Header: Issue headline + state badge
- Sections:
  1. State + priority + resolution criteria
  2. Originating proposal (if linked)
  3. Handoffs + commitments timeline
  4. Active watchers + next trigger
- Actions: Transition state, Add commitment, Add/edit watcher

## 9. Actions available (safe-by-default)

| Action | Behavior | Idempotent |
|--------|----------|------------|
| Transition state | Update issue.state | Yes |
| Add commitment | Create handoff entry | No |
| Edit watcher | Update watcher config | Yes |
| Resolve issue | Set state=resolved | Yes |

## 10. Telemetry

Events:
- `issues_inbox_loaded` — time_to_load, issue_count
- `issue_filtered` — filter_type, filter_value
- `issue_opened` — issue_id
- `issue_transitioned` — issue_id, from_state, to_state

## 11. Acceptance tests

1. [ ] Issues list shows all issues by default
2. [ ] State filter works correctly
3. [ ] Priority filter works correctly
4. [ ] Issues sorted by priority then activity
5. [ ] Watcher indicator shown for upcoming triggers
6. [ ] Clicking row opens IssueDrawer
7. [ ] State icons render correctly per state
8. [ ] Search filters by headline

LOCKED_SPEC
