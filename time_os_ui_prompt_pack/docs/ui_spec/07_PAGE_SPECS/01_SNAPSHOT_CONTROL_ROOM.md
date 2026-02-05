# Page Spec: Snapshot (Control Room)

LOCKED_SPEC

## 1. Purpose
The executive entry point for 90-second decision sessions. Surfaces the top proposals requiring attention, active issues, upcoming watchers, and data quality items.

## 2. Primary decisions enabled (max 3)
1. **Tag & Monitor** — Convert a proposal to a tracked Issue
2. **Snooze/Dismiss** — Defer or remove a proposal from attention
3. **Fix Data** — Resolve linkage/identity conflicts blocking proposals

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR: Scope selector | Time horizon (today/7d/30d) | Search │
├───────────────────────────────────────┬─────────────────────┤
│                                       │                     │
│   PROPOSAL STACK                      │   RIGHT RAIL        │
│   (limit from contract)               │                     │
│                                       │   Issues (limit 5)  │
│   ┌─────────────────────────────┐     │   ─────────────     │
│   │ ProposalCard #1             │     │   IssueCard         │
│   │ - headline                  │     │   IssueCard         │
│   │ - impact strip              │     │   ...               │
│   │ - hypotheses (top 3)        │     │                     │
│   │ - proof bullets             │     │   Watchers          │
│   │ - missing confirmations     │     │   ─────────────     │
│   │ - confidence badges         │     │   WatcherRow        │
│   │ - actions: Tag | Snooze     │     │   WatcherRow        │
│   └─────────────────────────────┘     │                     │
│                                       │   Fix Data (count)  │
│   ┌─────────────────────────────┐     │   ─────────────     │
│   │ ProposalCard #2             │     │   FixDataSummary    │
│   │ ...                         │     │                     │
│   └─────────────────────────────┘     │                     │
│                                       │                     │
└───────────────────────────────────────┴─────────────────────┘
```

**Mobile:** Single column, Right Rail collapsed to bottom sheet tabs.

## 4. Primary surfaces

### 4.1 Proposal Stack

**Query (from CONTROL_ROOM_QUERIES.md L15):**
```sql
SELECT * FROM proposals
WHERE status='open'
ORDER BY score DESC
LIMIT 7;
```

**Fields used (canonical IDs from PROPOSAL_ISSUE_ROOM_CONTRACT.md):**
- `proposal_id` — unique identifier
- `headline` — card title
- `impact` → `impact_json` parsed as `{dimensions: {time, cash, reputation}, deadline_at}`
- `top_hypotheses` → `hypotheses_json` parsed (max 3) as `[{label, confidence, supporting_signal_ids}]`
- `proof` → `proof_excerpt_ids_json` resolved to `[{excerpt_id, text, source_type, source_ref}]`
- `missing_confirmations` → `missing_confirmations_json` (max 2)
- `score` — ranking sort key
- `trend` — 'worsening'|'improving'|'flat'
- `occurrence_count` — recurrence indicator
- `linkage_confidence` — derived from min(entity_links.confidence) for scope_refs
- `interpretation_confidence` — from top hypothesis confidence

**Confidence display (two badges always shown):**
- **Linkage confidence** (from entity_links coverage)
- **Interpretation confidence** (from hypotheses_json[0].confidence)

Badge thresholds reference the eligibility gate thresholds only (see below).

**Eligibility gate enforcement (from 06_PROPOSALS_BRIEFINGS.md L82-89):**
| Gate | Requirement (source: 06_PROPOSALS_BRIEFINGS.md) | UI Behavior if FAIL |
|------|------------------------------------------------|---------------------|
| Proof density | ≥3 excerpts (L82) | Card shows "Insufficient proof" + Fix Data CTA |
| Scope coverage | min link_confidence ≥ 0.70 (L86) | Card shows "Weak linkage" + Fix Data CTA |
| Reasoning | ≥1 hypothesis with confidence ≥ 0.55, ≥2 signals (L88) | Card shows "Needs review" + disabled Tag |
| Source validity | All excerpts resolve (L89) | Card shows "Missing sources" + Fix Data CTA |

**Ineligible state:**
```
┌─────────────────────────────────────┐
│ ⚠️ INELIGIBLE PROPOSAL              │
│                                     │
│ headline                            │
│ [Gate violations listed]            │
│                                     │
│ [Fix Data →]                        │
│                                     │
│ Tag button: DISABLED                │
└─────────────────────────────────────┘
```

**States:**
- Loading: skeleton cards
- Empty: "No proposals require attention right now"
- Error: "Unable to load proposals — retry"
- Partial: some cards loaded, others skeleton

**Interactions:**
- Tap card → open RoomDrawer
- Tap "Tag & Monitor" → create Issue (idempotent)
- Tap "Snooze" → snooze modal (duration picker)
- Swipe left → Dismiss (with confirmation)
- Long press → Quick actions menu

### 4.2 Right Rail — Issues

**Query (from CONTROL_ROOM_QUERIES.md L16):**
```sql
SELECT * FROM issues
WHERE state IN ('open','monitoring','awaiting','blocked')
ORDER BY priority DESC
LIMIT 5;
```

**Fields used (canonical IDs from PROPOSAL_ISSUE_ROOM_CONTRACT.md):**
- `issue_id` — unique identifier
- `state` — 'open'|'monitoring'|'awaiting'|'blocked'|'resolved'|'closed'
- `priority` — 'critical'|'high'|'medium'|'low'
- `headline` — derived from `primary_ref` or linked proposal
- `last_activity_at` — ISO timestamp
- `next_trigger` — from watchers, ISO timestamp

**States:**
- Loading: skeleton rows
- Empty: "No active issues"
- Error: inline error message

**Interactions:**
- Tap row → open IssueDrawer

### 4.3 Right Rail — Watchers

**Query (from CONTROL_ROOM_QUERIES.md L17):**
```sql
SELECT * FROM issue_watchers
WHERE active=1 AND next_check_at <= datetime('now', '+24 hours')
ORDER BY next_check_at ASC
LIMIT 5;
```

**Fields used:**
- `watcher_id` — unique identifier
- `issue_id` — linked issue
- `next_check_at` — ISO timestamp
- `trigger_condition` — summary text

**Interactions:**
- Tap row → open IssueDrawer for linked issue

### 4.4 Right Rail — Fix Data Summary

**Query (from CONTROL_ROOM_QUERIES.md L18):**
```sql
SELECT COUNT(*) as fix_data_count FROM resolution_queue
WHERE status='pending';
```

**Fields used:**
- `fix_data_count` — integer count

**Interactions:**
- Tap → navigate to `/fix-data`

## 5. Ranking/Sorting rules (deterministic)

Proposals sorted by `score DESC` (from 06_PROPOSALS_BRIEFINGS.md L141-167).

Tie-breakers (in order, from 06_PROPOSALS_BRIEFINGS.md L160-163):
1. Higher urgency (deadline sooner)
2. Higher `min_link_confidence`
3. More recent `last_seen_at`
4. Higher `occurrence_count`

## 6. Filters & scope

**Top bar controls (from CONTROL_ROOM_QUERIES.md L10-12):**
- **Scope:** All | Client | Brand | Engagement (optional filter)
- **Time horizon:** Today | 7 days | 30 days

Filters apply to all surfaces (Proposals, Issues, Watchers).

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| ProposalCard | Tap | RoomDrawer with evidence tabs |
| Client chip | Tap | `/clients/:clientId` |
| Team chip | Tap | `/team/:id` |
| IssueCard | Tap | IssueDrawer |
| WatcherRow | Tap | IssueDrawer for linked issue |
| FixDataSummary | Tap | `/fix-data` |

## 8. Drawer/Detail contract

**RoomDrawer (opened from ProposalCard):**
- Header: Entity name + coverage summary
- Sections:
  1. What changed (delta summary)
  2. Why likely (hypotheses with confidence)
  3. Proof (excerpts with anchors)
  4. Missing confirmations
- Actions: Tag & Monitor, Snooze, Dismiss
- Evidence tabs: Work, Comms, Meetings, Finance (per entity type)

## 9. Actions available (safe-by-default)

| Action | Behavior | Idempotent |
|--------|----------|------------|
| Tag & Monitor | Creates Issue, sets proposal status='accepted' | Yes |
| Snooze | Sets snooze_until, hides from stack | Yes |
| Dismiss | Sets status='dismissed', logs feedback | Yes |
| Copy Draft | Copies communication draft to clipboard | Yes |

**Disabled when ineligible:** Tag & Monitor (gate violations block this action).

## 10. Telemetry

Events:
- `snapshot_loaded` — time to first proposal
- `proposal_viewed` — proposal_id, time_in_view
- `proposal_tagged` — proposal_id, time_to_tag
- `proposal_snoozed` — proposal_id, snooze_duration
- `proposal_dismissed` — proposal_id

## 11. Acceptance tests

1. [ ] Snapshot loads proposals ordered by score DESC
2. [ ] Ineligible proposals show gate violation + Fix Data CTA
3. [ ] Tag button disabled for ineligible proposals
4. [ ] Tag action creates Issue and updates proposal status
5. [ ] Snooze hides proposal until snooze_until
6. [ ] Both confidence badges always visible on ProposalCard
7. [ ] Clicking proposal opens RoomDrawer with evidence
8. [ ] Right rail shows Issues, Watchers, Fix Data count
9. [ ] Scope filter applies to all surfaces
10. [ ] Time horizon filter updates query window

LOCKED_SPEC
