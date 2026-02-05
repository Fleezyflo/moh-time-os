# Page Spec: Client Detail Report

LOCKED_SPEC

## 1. Purpose
Deep dive into a specific client showing open issues, top proposals, and evidence tabs for investigation. Report view, not dashboard.

## 2. Primary decisions enabled (max 3)
1. **Resolve issue** — Transition issue state or add commitment
2. **Tag proposal** — Convert proposal to monitored issue
3. **Investigate evidence** — Drill into specific evidence domain

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: Client Name | Posture badge | Linkage confidence   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ OPEN ISSUES (section)                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ IssueCard #1 — state | priority                        │ │
│ │ Last activity: relative | Next trigger: relative       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ TOP PROPOSALS (section, gate-aware)                         │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ProposalCard #1 — score | trend                        │ │
│ │ Eligible: status | [Tag & Monitor]                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ EVIDENCE TABS (drill-down only)                             │
│ [Work] [Comms] [Meetings] [Finance]                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:** Stacked sections, tabs as horizontal scroll.

## 4. Primary surfaces

### 4.1 Open Issues

**Query (from CONTROL_ROOM_QUERIES.md L25-27):**
```sql
SELECT * FROM issues
WHERE primary_entity_type = 'client' 
  AND primary_entity_id = :clientId
  AND state IN ('open','monitoring','awaiting','blocked')
ORDER BY priority DESC, last_activity_at DESC;
```

**Fields used (canonical IDs from PROPOSAL_ISSUE_ROOM_CONTRACT.md):**
- `issue_id` — unique identifier
- `state` — 'open'|'monitoring'|'awaiting'|'blocked'|'resolved'|'closed'
- `priority` — 'critical'|'high'|'medium'|'low'
- `headline` — from primary_ref or linked proposal
- `last_activity_at` — ISO timestamp
- `next_trigger` — from watchers, ISO timestamp
- `resolution_criteria` — short form completion definition

**States:**
- Loading: skeleton cards
- Empty: "No open issues for this client"
- Error: inline retry

**Interactions:**
- Tap card → open IssueDrawer

### 4.2 Top Proposals (gate-aware)

**Query (from 06_PROPOSALS_BRIEFINGS.md L185-190):**
```sql
SELECT * FROM proposals
WHERE status = 'open'
  AND json_extract(scope_refs_json, '$') LIKE '%"type":"client","id":"' || :clientId || '"%'
ORDER BY score DESC
LIMIT 5;
```

**Fields used (canonical IDs from PROPOSAL_ISSUE_ROOM_CONTRACT.md):**
- `proposal_id` — unique identifier
- `headline` — card title
- `impact` → `impact_json` parsed
- `score` — ranking sort key
- `trend` — 'worsening'|'improving'|'flat'
- `linkage_confidence` — derived from min(entity_links.confidence)
- `interpretation_confidence` — from top hypothesis confidence

**Eligibility gate enforcement:**
Same as Snapshot (see 01_SNAPSHOT_CONTROL_ROOM.md §4.1). Gates from 06_PROPOSALS_BRIEFINGS.md L82-89.

**Ineligible rendering:**
- Show card in muted style
- Display gate violation reason
- Show Fix Data CTA
- Tag button disabled

**States:**
- Loading: skeleton cards
- Empty: "No proposals for this client"

**Interactions:**
- Tap card → open RoomDrawer
- Tap "Tag & Monitor" → create Issue (if eligible)
- Tap "Fix Data" → navigate to `/fix-data?scope=client:{clientId}`

### 4.3 Evidence Tabs (drill-down)

**Tabs:** Work | Comms | Meetings | Finance

Each tab loads relevant evidence on demand:

**Work tab query:**
```sql
SELECT ae.* FROM artifact_excerpts ae
JOIN signals s ON ae.excerpt_id = s.evidence_anchor_id
WHERE s.entity_type = 'client' AND s.entity_id = :clientId
  AND ae.source_type IN ('asana_task', 'asana_comment', 'github_issue')
ORDER BY ae.extracted_at DESC
LIMIT 20;
```

**Fields used (canonical IDs):**
- `excerpt_id` — anchored snippet ID
- `text` — excerpt content
- `source_type` — artifact origin (email, asana_task, etc.)
- `source_ref` — link to original
- `extracted_at` — ISO timestamp

**Interactions:**
- Tap excerpt → open EvidenceViewer in drawer (anchored navigation)

## 5. Ranking/Sorting rules (deterministic)

- Issues: `priority DESC`, then `last_activity_at DESC`
- Proposals: `score DESC`
- Evidence: `extracted_at DESC` (most recent first)

## 6. Filters & scope

- Time horizon (inherited from global or overridden): Today | 7d | 30d
- Evidence tab filters by source type implicitly

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| IssueCard | Tap | IssueDrawer |
| ProposalCard | Tap | RoomDrawer |
| Engagement chip | Tap | Engagement detail (if exists) |
| Team member chip | Tap | `/team/:id` |
| Evidence excerpt | Tap | EvidenceViewer in drawer |

## 8. Drawer/Detail contract

**RoomDrawer (from ProposalCard):** Same as Snapshot.

**IssueDrawer (from IssueCard):**
- Header: Issue headline + state badge
- Sections:
  1. Originating proposal snapshot
  2. Handoffs + commitments
  3. Watcher list + next trigger
- Actions: Transition state, Add commitment, Add watcher

**EvidenceViewer (from excerpt):**
- Anchored excerpt highlighted
- Context (surrounding text if available)
- Source link (open in external app)
- Navigation: prev/next evidence in timeline

## 9. Actions available (safe-by-default)

| Action | Behavior | Idempotent |
|--------|----------|------------|
| Tag & Monitor (proposal) | Creates Issue | Yes |
| Transition state (issue) | Updates issue state | Yes |
| Add commitment (issue) | Adds handoff/commitment | Yes |
| Fix Data (proposal) | Navigate to fix data | N/A |

## 10. Telemetry

Events:
- `client_detail_loaded` — client_id, time_to_load
- `issue_opened` — issue_id, client_id
- `proposal_opened` — proposal_id, client_id
- `evidence_tab_viewed` — tab_name, client_id
- `evidence_excerpt_viewed` — excerpt_id

## 11. Acceptance tests

1. [ ] Client header shows name + posture + linkage confidence
2. [ ] Open issues section shows active issues scoped to client
3. [ ] Top proposals section enforces eligibility gates
4. [ ] Ineligible proposals show gate violation + Fix Data CTA
5. [ ] Evidence tabs load on demand (not preloaded)
6. [ ] Evidence excerpts open in EvidenceViewer
7. [ ] Both confidence badges visible on proposal cards
8. [ ] No raw tables in default view (evidence tabs are drill-down)

LOCKED_SPEC
