# Page Spec: Fix Data Center

LOCKED_SPEC

## 1. Purpose
Data quality resolution workspace for identity conflicts, ambiguous links, and missing mappings. Improving linkage confidence unblocks proposal eligibility.

## 2. Primary decisions enabled (max 3)
1. **Resolve identity** — Merge or split conflicting entities
2. **Confirm/deny link** — Disambiguate entity relationships
3. **Create alias** — Add missing mappings

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR: Filter [Type ▼] [Impact ▼] | Search                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ FIX DATA QUEUE                                              │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🔀 IDENTITY CONFLICT                                    │ │
│ │                                                         │ │
│ │ "[name]" appears in multiple sources                    │ │
│ │ Candidates: [list with match scores]                    │ │
│ │                                                         │ │
│ │ Impact: Blocks [N] proposals (weak linkage)             │ │
│ │                                                         │ │
│ │ [Merge all] [Keep separate] [Review →]                  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🔗 AMBIGUOUS LINK                                       │ │
│ │                                                         │ │
│ │ "[item]" could belong to multiple entities              │ │
│ │ Candidates: [list with match scores]                    │ │
│ │                                                         │ │
│ │ Impact: Blocks [N] proposals (scope uncertainty)        │ │
│ │                                                         │ │
│ │ [Assign to: option] [Review →]                          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ➕ MISSING MAPPING                                       │ │
│ │                                                         │ │
│ │ "[identifier]" has no entity mapping                    │ │
│ │                                                         │ │
│ │ Suggested: [suggestion]                                 │ │
│ │ Impact: [N] items unlinked                              │ │
│ │                                                         │ │
│ │ [Create alias] [Ignore] [Review →]                      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:** Full-width cards, action buttons at bottom of each card.

## 4. Primary surfaces

### 4.1 Fix Data Queue

**Query (from CONTROL_ROOM_QUERIES.md L18-19):**
```sql
SELECT 
  fd.fix_data_id,
  fd.fix_type,
  fd.description,
  fd.candidates_json,
  fd.impact_summary,
  fd.affected_proposal_ids,
  fd.status,
  fd.created_at
FROM fix_data_queue fd
WHERE fd.status = 'pending'
ORDER BY 
  json_array_length(fd.affected_proposal_ids) DESC,
  fd.created_at ASC;
```

**Fallback (if fix_data_queue not implemented):**
```sql
SELECT 
  el.link_id as fix_data_id,
  'ambiguous_link' as fix_type,
  el.description,
  el.candidates_json,
  COUNT(DISTINCT p.proposal_id) as affected_count
FROM entity_links el
LEFT JOIN proposals p ON json_extract(p.scope_refs_json, '$') LIKE '%' || el.link_id || '%'
WHERE el.confidence < 0.70
GROUP BY el.link_id
ORDER BY affected_count DESC;
```

Note: The 0.70 threshold matches the scope coverage gate from 06_PROPOSALS_BRIEFINGS.md L86.

**Fields used (canonical IDs):**
- `fix_data_id` — unique identifier
- `fix_type` — 'identity_conflict'|'ambiguous_link'|'missing_mapping'
- `description` — human-readable summary
- `candidates_json` — array of `{label, match_score}` (scores computed by backend)
- `impact_summary` — e.g., "Blocks N proposals"
- `affected_proposal_ids` — JSON array of proposal_ids
- `status` — 'pending'|'resolved'|'ignored'

**Fix type display:**
| Type | Icon | Description |
|------|------|-------------|
| identity_conflict | 🔀 | Same person/entity appears with different identifiers |
| ambiguous_link | 🔗 | Entity could belong to multiple parents |
| missing_mapping | ➕ | No mapping exists for identifier |

**Impact display:**
- Show count of affected proposals
- Show "Blocks X proposals" if any proposal's eligibility gate fails due to this item

**States:**
- Loading: skeleton cards
- Empty: "All data clean ✓" (celebration state)
- Error: "Unable to load fix data — retry"

**Interactions:**
- Tap card → open FixDataDrawer for detailed review
- Tap quick action → execute resolution

### 4.2 FixDataDrawer (detail view)

**Sections:**
1. **Conflict detail** — full description of the data quality issue
2. **Candidates** — all options with match scores (from backend)
3. **Evidence** — signals/excerpts that created the conflict
4. **Affected items** — proposals and issues impacted
5. **Resolution options** — actions with preview of impact

**Interactions:**
- Select candidate → preview impact
- Confirm resolution → execute and close
- Ignore → mark as ignored (can be undone)

## 5. Ranking/Sorting rules (deterministic)

Default: Impact-first
1. `affected_proposal_count DESC` (highest impact first)
2. `created_at ASC` (older items first among same impact)

Sort options:
- By impact (default)
- By type
- By age

## 6. Filters & scope

**Filter controls:**
- Type: All | Identity conflicts | Ambiguous links | Missing mappings
- Impact: All | Has affected proposals | No affected proposals
- Scope (optional): Client filter

**Search:** Filter by description text

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| FixDataCard | Tap | FixDataDrawer |
| Affected proposal chip | Tap | RoomDrawer for proposal |
| Entity candidate | Tap | Entity detail (if exists) |

## 8. Drawer/Detail contract

**FixDataDrawer:**
- Header: fix_type icon + description
- Sections: as listed in 4.2
- Actions: resolution buttons contextual to fix_type

**Resolution actions by type:**
| Type | Actions |
|------|---------|
| identity_conflict | Merge all, Keep separate, Merge selected |
| ambiguous_link | Assign to [candidate], Create new, Ignore |
| missing_mapping | Create alias, Link to existing, Ignore |

## 9. Actions available (safe-by-default)

| Action | Behavior | Idempotent | Audit |
|--------|----------|------------|-------|
| Merge identities | Consolidate entity records | No | Yes |
| Keep separate | Mark as distinct entities | Yes | Yes |
| Assign link | Set parent entity | Yes | Yes |
| Create alias | Add identifier mapping | No | Yes |
| Ignore | Mark fix_data as ignored | Yes | Yes |

**All actions create audit log entry:**
```sql
INSERT INTO fix_data_audit (
  fix_data_id, action, actor, timestamp, before_state, after_state
) VALUES (...);
```

## 10. Telemetry

Events:
- `fix_data_loaded` — time_to_load, pending_count
- `fix_data_viewed` — fix_data_id, fix_type
- `fix_data_resolved` — fix_data_id, action, affected_proposals
- `fix_data_ignored` — fix_data_id

## 11. Acceptance tests

1. [ ] Fix data queue shows pending items sorted by impact
2. [ ] Each card shows fix_type, description, impact
3. [ ] Quick actions available on card
4. [ ] FixDataDrawer shows full detail and candidates
5. [ ] Resolution updates linkage confidence
6. [ ] Affected proposals rechecked for eligibility after resolution
7. [ ] Audit log created for every resolution
8. [ ] "All data clean" state shown when queue empty
9. [ ] Ignored items can be un-ignored

LOCKED_SPEC
