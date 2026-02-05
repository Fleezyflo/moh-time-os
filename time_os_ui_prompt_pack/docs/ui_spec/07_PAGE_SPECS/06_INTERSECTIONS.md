# Page Spec: Intersections

LOCKED_SPEC

## 1. Purpose
Coupling explorer showing relationships between proposals, issues, clients, and team members. Evidence-based investigation workspace.

## 2. Primary decisions enabled (max 3)
1. **Identify root cause** — Trace couplings to understand why issues cluster
2. **Spot dependencies** — See which entities are interconnected
3. **Investigate propagation** — Understand how one issue affects others

## 3. Default view anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR: Anchor selector [Proposal ▼] | Search              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ANCHOR SELECTION (left)          COUPLING MAP (center)      │
│ ┌─────────────────────┐          ┌─────────────────────────┐│
│ │ Select anchor:      │          │                         ││
│ │                     │          │    ┌───┐                ││
│ │ ○ Proposal: P-123   │          │    │ C │←────┐          ││
│ │ ○ Proposal: P-456   │          │    └───┘     │          ││
│ │ ○ Issue: I-789      │          │      ↓       │          ││
│ │                     │          │  ┌───┐   ┌───┐          ││
│ │ [Selected: P-123]   │          │  │ P │───│ T │          ││
│ │                     │          │  └───┘   └───┘          ││
│ │                     │          │    ↑                    ││
│ │                     │          │  ┌───┐                  ││
│ │                     │          │  │ I │                  ││
│ │                     │          │  └───┘                  ││
│ │                     │          │                         ││
│ └─────────────────────┘          └─────────────────────────┘│
│                                                             │
│ WHY-DRIVERS (bottom)                                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Coupling: P-123 ↔ Client C                              │ │
│ │ Strength: [level] | Confidence: [value]                 │ │
│ │                                                         │ │
│ │ Why:                                                    │ │
│ │ • Signal: [type] → [description]                        │ │
│ │                                                         │ │
│ │ Proof excerpts:                                         │ │
│ │ [excerpt 1] [excerpt 2] [excerpt 3]                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Mobile:** Anchor selector as top sheet, coupling map as zoomable canvas, why-drivers as bottom sheet.

## 4. Primary surfaces

### 4.1 Anchor Selector

**Query:**
```sql
SELECT 'proposal' as type, proposal_id as id, headline as label, score
FROM proposals WHERE status = 'open'
UNION ALL
SELECT 'issue' as type, issue_id as id, headline as label, priority as score
FROM issues WHERE state IN ('open','monitoring','awaiting','blocked')
ORDER BY score DESC
LIMIT 20;
```

**Fields used (canonical IDs):**
- `type` — 'proposal'|'issue'
- `id` — entity identifier
- `label` — headline for display
- `score` / `priority` — for ranking

**Interactions:**
- Tap item → set as anchor, load coupling map

### 4.2 Coupling Map

**Query (from CONTROL_ROOM_QUERIES.md L29-31):**
```sql
SELECT * FROM couplings
WHERE anchor_type = :anchorType AND anchor_id = :anchorId
ORDER BY strength DESC;
```

If no couplings exist, UI calls compute endpoint:
```
POST /api/couplings/compute
{ anchor_type, anchor_id }
```

**Fields used (canonical IDs):**
- `coupling_id` — unique identifier
- `anchor_type`, `anchor_id` — source entity
- `coupled_type`, `coupled_id` — target entity
- `coupled_label` — display name for coupled entity
- `strength` — 0-1 coupling strength (backend-computed)
- `confidence` — 0-1 confidence (backend-computed)
- `why_signal_ids` — JSON array of signal IDs
- `why_excerpt_ids` — JSON array of excerpt IDs

**Rendering:**
- Nodes: entities (Proposal, Issue, Client, Team, Engagement)
- Edges: couplings with strength as line weight
- Color: confidence level (solid/dashed/dotted per backend-defined bands)

**Node types:**
| Type | Icon | Color |
|------|------|-------|
| Proposal | P | blue |
| Issue | I | red |
| Client | C | green |
| Team | T | purple |
| Engagement | E | orange |

**Interactions:**
- Tap node → show entity summary, option to drill
- Tap edge → show coupling details in why-drivers
- Pinch/zoom → navigate map
- Pan → scroll map

### 4.3 Why-Drivers

**Display (when edge selected):**
- Coupling strength + confidence (values from backend)
- Why: list of signals that established the coupling
- Proof: excerpts anchoring the signals

**Fields used (canonical IDs):**
- `strength` — 0-1 displayed as Strong/Medium/Weak (bands from backend)
- `confidence` — 0-1 with badge
- `why_signals[]` → each with `signal_type`, `description`
- `proof_excerpts[]` → each with `excerpt_id`, `text`, `source_ref`

**Rendering rules:**
- **NO coupling without why** — if why_signal_ids empty, do not show edge
- Each signal links to its evidence
- Excerpts are clickable → open EvidenceViewer

**Interactions:**
- Tap signal → expand detail inline
- Tap excerpt → open EvidenceViewer in drawer
- Tap "Investigate" → open RoomDrawer for coupled entity

## 5. Ranking/Sorting rules (deterministic)

- Anchor list: `score DESC`
- Couplings: `strength DESC`
- Why-signals: order preserved from coupling computation

## 6. Filters & scope

- Anchor type filter: All | Proposals | Issues
- Strength threshold filter: Show all | Strong only (uses backend-defined threshold)
- Entity type filter (on map): show/hide Clients, Team, Engagements

## 7. Drill-down paths

| Element | Action | Target |
|---------|--------|--------|
| Proposal node | Tap → Drill | RoomDrawer |
| Issue node | Tap → Drill | IssueDrawer |
| Client node | Tap → Drill | `/clients/:clientId` |
| Team node | Tap → Drill | `/team/:id` |
| Coupling edge | Tap | Why-drivers panel |
| Proof excerpt | Tap | EvidenceViewer |

## 8. Drawer/Detail contract

**RoomDrawer / IssueDrawer:** Same as Snapshot.

**EvidenceViewer:** Anchored excerpt with context and source link.

## 9. Actions available (safe-by-default)

| Action | Behavior | Idempotent |
|--------|----------|------------|
| Refresh couplings | Re-compute for anchor | Yes |
| Open entity | Navigate or open drawer | N/A |

## 10. Telemetry

Events:
- `intersections_loaded` — time_to_load
- `anchor_selected` — anchor_type, anchor_id
- `coupling_viewed` — coupling_id, strength
- `entity_drilled` — entity_type, entity_id

## 11. Acceptance tests

1. [ ] Anchor selector shows recent proposals and issues
2. [ ] Selecting anchor loads/computes coupling map
3. [ ] Coupling edges show strength + confidence
4. [ ] No edge displayed without why-drivers (signals)
5. [ ] Tapping edge shows why-drivers panel
6. [ ] Why-drivers include signals and proof excerpts
7. [ ] Tapping node opens entity detail
8. [ ] Couplings without evidence do not appear

LOCKED_SPEC
