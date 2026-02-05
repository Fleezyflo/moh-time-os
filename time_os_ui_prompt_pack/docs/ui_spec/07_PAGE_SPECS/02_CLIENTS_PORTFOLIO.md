# Page Spec: Clients Portfolio

LOCKED_SPEC

## 1. Purpose
Portfolio view showing all clients with posture summaries derived from scoped proposals and issues. Quick navigation to client detail.

## 2. Primary decisions enabled (max 3)
1. **Identify attention-needed clients** — See which clients have open proposals/issues
2. **Drill into client** — Navigate to detail for investigation
3. **Compare postures** — Quickly scan client health across portfolio

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR: Search | Sort [Posture ▼]                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   CLIENT CARDS (grid)                                       │
│                                                             │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  │
│   │ Client A      │  │ Client B      │  │ Client C      │  │
│   │ 🔴 Critical   │  │ ⚠️ Attention  │  │ ✓ Healthy     │  │
│   │ 3 proposals   │  │ 1 proposal    │  │ 0 proposals   │  │
│   │ 2 issues      │  │ 1 issue       │  │ 0 issues      │  │
│   │ Link: ●High   │  │ Link: ●Med    │  │ Link: ●High   │  │
│   └───────────────┘  └───────────────┘  └───────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:** Single column, full-width cards.

## 4. Primary surfaces

### 4.1 Client Cards

**Query (from CONTROL_ROOM_QUERIES.md L25-27):**
```sql
SELECT 
  c.client_id,
  c.name,
  COUNT(DISTINCT p.proposal_id) as proposal_count,
  COUNT(DISTINCT i.issue_id) as issue_count,
  MIN(el.confidence) as min_linkage_confidence
FROM clients c
LEFT JOIN proposals p ON json_extract(p.scope_refs_json,'$') LIKE '%"type":"client","id":"' || c.client_id || '"%'
  AND p.status='open'
LEFT JOIN issues i ON i.primary_entity_type='client' AND i.primary_entity_id=c.client_id
  AND i.state IN ('open','monitoring','awaiting','blocked')
LEFT JOIN entity_links el ON el.target_type='client' AND el.target_id=c.client_id
GROUP BY c.client_id;
```

**Fields used (canonical IDs):**
- `client_id` — unique identifier
- `name` — display name
- `proposal_count` — count of open proposals scoped to client
- `issue_count` — count of active issues scoped to client
- `min_linkage_confidence` — derived from min(entity_links.confidence)

**Posture derivation (computed from proposal_count and issue_count):**
Posture is derived from the presence of proposals/issues, not from invented score thresholds.

| Posture | Condition |
|---------|-----------|
| 🔴 Critical | issue_count > 0 AND any issue.priority = 'critical' |
| ⚠️ Attention | proposal_count > 0 OR issue_count > 0 |
| ✓ Healthy | proposal_count = 0 AND issue_count = 0 |
| ◯ Inactive | No recent activity (last_activity_at older than time_horizon) |

**States:**
- Loading: skeleton cards
- Empty: "No clients found"
- Error: "Unable to load clients — retry"

**Interactions:**
- Tap card → navigate to `/clients/:clientId`

## 5. Ranking/Sorting rules (deterministic)

Default sort: Posture priority (Critical → Attention → Healthy → Inactive), then alphabetical by name.

Sort options:
- By posture (default)
- Alphabetical (A-Z)
- By proposal count (DESC)
- By issue count (DESC)

## 6. Filters & scope

- Search: filter by client name (client-side filtering)
- Posture filter: All | Critical | Attention | Healthy

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| Client card | Tap | `/clients/:clientId` |

## 8. Telemetry

Events:
- `clients_portfolio_loaded` — time_to_load, client_count
- `client_card_clicked` — client_id

## 9. Acceptance tests

1. [ ] Portfolio shows all clients with posture badges
2. [ ] Posture derived from proposal/issue presence (no invented thresholds)
3. [ ] Linkage confidence badge shown per card
4. [ ] Clicking card navigates to client detail
5. [ ] Search filters clients by name
6. [ ] Sort options work correctly

LOCKED_SPEC
