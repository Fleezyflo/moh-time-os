# Page Spec: Team Detail Report

LOCKED_SPEC

## 1. Purpose
Deep dive into a specific team member showing load/throughput bands, responsiveness signals, and scoped issues/proposals. Responsible telemetry — no surveillance.

## 2. Primary decisions enabled (max 3)
1. **Assess capacity** — Understand current load and bandwidth
2. **Reassign work** — Identify items that could be redistributed
3. **Investigate blockers** — Drill into issues affecting the member

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: Member Name | Role | Load band | Confidence         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ LOAD & THROUGHPUT (responsible metrics)                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Current Load: [band]                                    │ │
│ │ ████████░░░░░░░░░░░░ (Confidence: [value])              │ │
│ │                                                         │ │
│ │ Throughput (window): [count] tasks completed            │ │
│ │ Avg completion time: ~[value] (Confidence: [value])     │ │
│ │                                                         │ │
│ │ ⚠️ Caveat: Based on task tracking data. May not reflect │ │
│ │ meetings, ad-hoc work, or untracked activities.         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ RESPONSIVENESS SIGNALS                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Email: [band] (confidence)                              │ │
│ │ Slack: [band] (confidence)                              │ │
│ │ Task updates: [band] (confidence)                       │ │
│ │ (Based on configured time window)                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ SCOPED ISSUES                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ IssueCard — assigned to this member                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ SCOPED PROPOSALS                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ProposalCard — mentions this member                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:** Stacked sections, scroll vertical.

## 4. Primary surfaces

### 4.1 Load & Throughput

**Query:**
```sql
SELECT 
  load_band,
  load_confidence,
  throughput_count,
  throughput_window,
  avg_completion_time,
  throughput_confidence
FROM team_member_metrics
WHERE member_id = :memberId;
```

**Fields used (canonical IDs):**
- `load_band` — 'high'|'medium'|'low'|'unknown' (backend-computed)
- `load_confidence` — 0-1 confidence value (backend-computed)
- `throughput_count` — tasks completed in window (integer)
- `throughput_window` — time window label (e.g., "7d")
- `avg_completion_time` — approximate completion time (backend-computed)
- `throughput_confidence` — 0-1 confidence value (backend-computed)

**Display rules (responsible telemetry):**
- Show bands, not precise numbers where possible
- Always show confidence alongside each metric
- Include caveat about data limitations
- **NO**: "hours worked", "activity score", "idle time", "keystrokes"
- **YES**: task completion bands, response patterns, deadline adherence

**Confidence handling:**
If `confidence` is below backend-defined threshold, show "Insufficient data" instead of metric.
UI does not define confidence thresholds — they come from the backend.

### 4.2 Responsiveness Signals

**Query:**
```sql
SELECT 
  channel,
  response_band,
  confidence,
  computed_window
FROM responsiveness_signals
WHERE member_id = :memberId;
```

**Fields used (canonical IDs):**
- `channel` — 'email'|'slack'|'task_updates'
- `response_band` — 'fast'|'normal'|'slow'|'unknown' (backend-computed)
- `confidence` — 0-1 confidence value
- `computed_window` — time window used for computation

**Display rules:**
- Show signal per channel, not aggregate
- Include time window label (from `computed_window`)
- Allow user to expand for detail (drill-down)

**Interactions:**
- Tap signal → expand inline detail (not full page)

### 4.3 Scoped Issues

**Query:**
```sql
SELECT * FROM issues
WHERE assignee_id = :memberId
  AND state IN ('open','monitoring','awaiting','blocked')
ORDER BY priority DESC;
```

**Fields used (canonical IDs from PROPOSAL_ISSUE_ROOM_CONTRACT.md):**
- `issue_id`, `state`, `priority`, `headline`, `last_activity_at`, `next_trigger`

**Interactions:**
- Tap card → open IssueDrawer

### 4.4 Scoped Proposals

**Query:**
```sql
SELECT * FROM proposals
WHERE status = 'open'
  AND (
    json_extract(scope_refs_json, '$') LIKE '%"type":"team_member","id":"' || :memberId || '"%'
    OR proposal_id IN (
      SELECT DISTINCT s.proposal_id FROM signals s
      WHERE s.entity_type = 'team_member' AND s.entity_id = :memberId
    )
  )
ORDER BY score DESC
LIMIT 5;
```

**Fields used (canonical IDs from PROPOSAL_ISSUE_ROOM_CONTRACT.md):**
- `proposal_id`, `headline`, `impact`, `score`, `trend`, `linkage_confidence`, `interpretation_confidence`

**Eligibility gates:** Enforced same as Snapshot (from 06_PROPOSALS_BRIEFINGS.md L82-89).

**Interactions:**
- Tap card → open RoomDrawer

## 5. Ranking/Sorting rules (deterministic)

- Issues: `priority DESC`
- Proposals: `score DESC`

## 6. Filters & scope

- Time horizon (inherited): Today | 7d | 30d (affects responsiveness signals window display)

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| IssueCard | Tap | IssueDrawer |
| ProposalCard | Tap | RoomDrawer |
| Client chip | Tap | `/clients/:clientId` |
| Responsiveness signal | Tap | Expand inline |

## 8. Drawer/Detail contract

**IssueDrawer:** Same as Client Detail.
**RoomDrawer:** Same as Snapshot.

## 9. Actions available (safe-by-default)

| Action | Behavior | Idempotent |
|--------|----------|------------|
| Reassign issue | Update assignee (opens modal) | Yes |
| Tag proposal | Creates Issue | Yes |

## 10. Telemetry

Events:
- `team_detail_loaded` — member_id, time_to_load
- `responsiveness_expanded` — member_id, channel
- `issue_opened` — issue_id, member_id
- `proposal_opened` — proposal_id, member_id

## 11. Acceptance tests

1. [ ] Load shown as band with confidence (not precise hours)
2. [ ] Throughput shown as approximate completion metrics
3. [ ] Responsiveness shown per channel with confidence
4. [ ] Caveat visible about data limitations
5. [ ] No surveillance metrics (no activity score, idle time, etc.)
6. [ ] Low confidence metrics show "Insufficient data"
7. [ ] Scoped issues and proposals display correctly
8. [ ] Both confidence badges visible on proposal cards

LOCKED_SPEC
