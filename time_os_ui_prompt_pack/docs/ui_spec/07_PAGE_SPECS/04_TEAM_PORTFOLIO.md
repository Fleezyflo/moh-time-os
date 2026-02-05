# Page Spec: Team Portfolio

LOCKED_SPEC

## 1. Purpose
Portfolio view showing team members with load bands and responsiveness signals. Quick navigation to member detail.

## 2. Primary decisions enabled (max 3)
1. **Identify capacity issues** — See which members are at high load
2. **Drill into member** — Navigate to detail for investigation
3. **Compare workloads** — Quickly scan team health

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR: Search | Sort [Load ▼]                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   TEAM CARDS (grid)                                         │
│                                                             │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  │
│   │ Sarah Chen    │  │ Mike Johnson  │  │ Alex Kim      │  │
│   │ Designer      │  │ Developer     │  │ PM            │  │
│   │ Load: High    │  │ Load: Medium  │  │ Load: Low     │  │
│   │ ████████░░    │  │ █████░░░░░    │  │ ██░░░░░░░░    │  │
│   │ Resp: Normal  │  │ Resp: Fast    │  │ Resp: Fast    │  │
│   └───────────────┘  └───────────────┘  └───────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:** Single column, full-width cards.

## 4. Primary surfaces

### 4.1 Team Cards

**Query:**
```sql
SELECT 
  tm.member_id,
  tm.name,
  tm.role,
  tmm.load_band,
  tmm.load_confidence,
  tmm.responsiveness_band
FROM team_members tm
LEFT JOIN team_member_metrics tmm ON tm.member_id = tmm.member_id;
```

**Fields used (canonical IDs):**
- `member_id` — unique identifier
- `name` — display name
- `role` — job title/role
- `load_band` — 'high'|'medium'|'low'|'unknown' (from team_member_metrics)
- `load_confidence` — 0-1 confidence score for load estimate
- `responsiveness_band` — 'fast'|'normal'|'slow' (aggregated from responsiveness_signals)

**Load band derivation:**
Load band is derived from `team_member_metrics.load_band` field (computed by backend).
UI does not compute thresholds — it displays the backend-provided band.

**Confidence threshold (from contract):**
If `load_confidence` is below backend-defined threshold, show "⚠️ Limited data" instead of load bar.

**Responsiveness band derivation:**
Aggregated from `responsiveness_signals` table by backend. UI displays the computed band.

**States:**
- Loading: skeleton cards
- Empty: "No team members"
- Error: "Unable to load team — retry"

**Interactions:**
- Tap card → navigate to `/team/:id`

## 5. Ranking/Sorting rules (deterministic)

Default sort: Load band priority (High → Medium → Low → Unknown), then alphabetical.

Sort options:
- By load (default)
- Alphabetical (A-Z)
- By responsiveness

## 6. Filters & scope

- Search: filter by name/role

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| Team card | Tap | `/team/:id` |

## 8. Telemetry

Events:
- `team_portfolio_loaded` — time_to_load, member_count
- `team_card_clicked` — member_id

## 9. Acceptance tests

1. [ ] Portfolio shows all team members with load bands
2. [ ] Load band displayed as visual bar
3. [ ] Responsiveness badge shown
4. [ ] Low confidence shows "Limited data" indicator
5. [ ] Clicking card navigates to team detail
6. [ ] Search filters by name/role

LOCKED_SPEC
