# Page 0 — AGENCY CONTROL ROOM (Executive Overview) — LOCKED SPEC (v1)

> Locked: 2026-02-03
> Status: Build-ready

---

## 0) Purpose (what this page must do)

Provide a whole-agency, cross-domain, drillable executive view that answers—at a glance:

1. **What breaks first if I do nothing?** (single narrative line + recommended drilldown)
2. **What's the agency state across Delivery, Cash, Clients, Capacity?** (3 dials + 2 intersection tiles)
3. **Where is risk concentrated?** (project heatstrip + people constraints strip)
4. **What changed since last refresh?** (delta strip)
5. **What are the top exceptions worth intervention?** (max 7, taxonomized)

**Hard rule:** This page is not a task browser. It is a decision console.

---

## 1) Global Controls (must match Page 1 contract)

### 1.1 Mode Selector (locked)

Modes affect ranking weights, not underlying truth.

- Ops Head
- Co-Founder
- Artist

Mode weights (apply only to domain impact channels, not base dimensions):

| Mode | Delivery | Money | Clients | Capacity | Comms |
|------|----------|-------|---------|----------|-------|
| Ops Head | 0.40 | 0.10 | 0.10 | 0.25 | 0.15 |
| Co-Founder | 0.15 | 0.35 | 0.35 | 0.05 | 0.10 |
| Artist | 0.25 | 0.10 | 0.10 | 0.35 | 0.20 |

### 1.2 Horizon Selector (locked)

Horizon affects eligibility gates (filter-before-rank).

- **NOW (4h)** → urgent horizon
- **TODAY** → before end of day
- **THIS WEEK** → compounding / critical path

Horizon gates are defined in §4.2 and are used consistently across modules.

### 1.3 Scope Chips (locked)

Multi-select filters applied across page:

- Lane(s)
- Owner(s)
- Client(s)
- Toggle: include/exclude internal projects (default depends on mode):
  - Ops Head / Co-Founder: internal = off by default
  - Artist: internal = on by default

But internal is always available via one click and never hidden from search.

---

## 2) Trust & Recency Contract (no executive claims without it)

### 2.1 Trust Strip Inputs (locked)

Displayed in top bar, always visible:

- `data_integrity` (boolean)
- `collector_staleness` per source + overall staleness badge
- `project_brand_required` (boolean pass/fail)
- `project_brand_consistency` (boolean pass/fail)
- `client_coverage_pct` (0–100)
- `finance_ar_coverage_pct` (0–100)
- `commitment_ready_pct` (0–100)
- `last_refresh_at` timestamp

### 2.2 Hard Gating Behavior (locked)

**If `data_integrity = false`:**
→ Page shows ONLY:
- "Integrity Failure" panel (single)
- A button: "Open Inspector"
- Trust strip remains visible
- Everything else hidden (no dials, no heatstrip, no exceptions, no narrative)

**If `data_integrity=true` but project gates fail:**
- If `project_brand_required=false` OR `project_brand_consistency=false`
→ Delivery/Clients modules render but must:
  - show "PARTIAL: project chain incomplete" badge
  - reduce confidence of affected objects to LOW (see §3.3)
  - never show "Green / Healthy" language without LOW badge

**If finance validity is low:**
- If `finance_ar_coverage_pct < 95`
→ Cash dial and cash-dependent intersections show "PARTIAL" and must list the top missing causes:
  - count of AR invoices missing due_date
  - count missing client_id

**If commitment readiness is low:**
- If `commitment_ready_pct < 50`
→ Comms module shows "LIMITED: body_text coverage low" and confidence LOW.

---

## 3) Core Scoring + Confidence (single shared contract)

### 3.1 Deterministic time_to_consequence (locked)

Used everywhere that needs urgency.

Fallback order:
1. `task.due_date` (+ `due_time` if present)
2. `commitment.deadline` (if linked)
3. `communication.expected_response_by` OR `response_deadline`
4. inferred from `last_activity_at` using stale thresholds (see §3.2)
5. else `null` → cannot qualify for horizon urgency; must fall into "Unknown triage" only

**No consequence → no urgency claim.**

### 3.2 Stale Thresholds (locked)

If `last_activity_at` exists, inferred consequence is:
- **NOW:** stale if `stale_hours >= 24`
- **TODAY:** stale if `stale_hours >= 48`
- **THIS WEEK:** stale if `stale_days >= 7`

### 3.3 Confidence Model (locked)

Every surfaced item must carry confidence: `HIGH | MED | LOW`.

**HIGH** when all true:
- `data_integrity=true`
- required chain valid for that domain (e.g., delivery requires linked project; client modules require client chain)
- required fields coverage ≥ threshold (defined per module)

**MED** when:
- integrity OK but some missing/partial mappings or missing secondary fields

**LOW** when any true:
- chain invalid/partial for required domain
- required fields missing below threshold
- dependent gate coverage below threshold

**If confidence is LOW, UI must show "Why low" bullets (max 3)**, generated from explicit reasons:
- "Project brand/client chain incomplete"
- "Due dates missing on >20% linked tasks"
- "AR invoices missing due_date/client_id"
- "Comms body_text coverage below threshold"
- "Collector stale: gmail > X hours"

---

## 4) Page Layout (fixed zones, hard caps)

### Zone A — Top Bar (always visible)

- Mode selector
- Horizon selector
- Scope chips
- Trust strip (compact: integrity, project gates, coverage, staleness, last refresh)

### Zone B — Row 1: Executive Narrative + Delta Strip

#### B1: "First to break" narrative (single line)

Format:
```
"First to break: {OBJECT} in {TTC}. Driver: {TOP_DRIVER}. Next action: {CTA}."
```

- OBJECT is one of: Project / Client / Lane / Person / AR cluster / Comms thread
- TTC = time_to_consequence (e.g., "in 6h", "EOD", "2d", "overdue")
- TOP_DRIVER is one of the defined drivers per module (§6)
- CTA is deterministic (execute/propose) per action risk model

#### B2: "Since last refresh" delta strip (max 5)

Show exactly 5 or fewer deltas, ordered by impact score descending:

Examples:
- "+2 projects turned Red"
- "AED 45k moved into 31–60"
- "Capacity gap increased by 6h (Ops lane)"
- "Client X health drifted −12"
- "3 new commitment breaches detected"

### Zone C — Row 2: Executive State (3 dials + 2 intersections)

**Hard rule: exactly 5 tiles.**

- C1 Delivery Dial
- C2 Cash Dial
- C3 Clients Dial
- C4 Intersection Tile: Churn × Money
- C5 Intersection Tile: Delivery × Capacity

Each tile shows:
- One sentence state
- One risk badge (Green/Yellow/Red or Partial)
- One CTA ("Open Delivery Command", etc.)

### Zone D — Row 3: Project Heatstrip (max 25)

A horizontal/compact ranked list of the 25 most intervention-worthy projects/retainers.

Each chip shows:
- Project name (short)
- Status color (derived, §6.1)
- Time-to-slip
- Confidence dot

Click → drawer; Pin → opens Delivery Command (Page 2).

### Zone E — Row 4: Constraints Strip (People/Lanes) (max 12)

Shows the 12 biggest constraints, not "busy people".

Each item is either:
- a Person constraint OR
- a Lane constraint

Each chip shows:
- Name (person/lane)
- Capacity gap (hours)
- Next deadline pressure (soonest TTC)
- Confidence dot

Click → drawer; Pin → opens Capacity/Calendar page (future Page: Capacity Command).

### Zone F — Row 5: Exceptions Feed (max 7, taxonomized)

Exactly 7 exception cards max, always.

Each card must map to a fixed taxonomy:

**Exception Types (locked):**
1. Delivery slip risk
2. AR/money risk
3. Client churn risk
4. Capacity bottleneck
5. Commitment breach
6. Blocked waiting
7. Unknown triage

If it doesn't map → it does not appear here (goes to Inspector).

Click → drawer; Primary CTA execute/propose per risk model.

### Zone G — Right Drawer (context on demand)

Drawer contract is identical to Page 1, plus "Reason".

Drawer must contain:
1. **Summary** (2–3 sentences)
2. **Evidence** (linked objects + gate states relevant)
3. **Action panel** (primary/secondary + propose option + risk label)
4. **Reason** (one line): `{horizon_gate} | {domain} | {top_driver}`

---

## 5) Eligibility Gates (filter-before-rank, locked)

### 5.1 Horizon Eligibility

An item is eligible for surfacing (tiles/heatstrip/exceptions) only if:

**NOW**
- `time_to_consequence ≤ 12h` OR `dependency_breaker=true` OR `capacity_blocker_today=true`
- Unknown triage only allowed if it blocks other work today (`dependency_breaker=true`)

**TODAY**
- `time_to_consequence ≤ EOD` OR `tomorrow_starts_broken=true`

**THIS WEEK**
- `critical_path=true` OR `compounding_damage=true` OR `AR_severe=true`

If no eligibility and no unknown gate → item cannot surface.

### 5.2 Unknown triage gate (locked)

Unknown triage can surface only if:
- it blocks an eligible item (`dependency_breaker=true`), OR
- it is in a resolution queue issue type P1, OR
- it is a finance AR invoice missing due_date/client_id (P2 but money-impact above threshold)

---

## 6) Deterministic Domain Definitions (what each tile means)

### 6.1 Delivery: Project Status + Slip Risk (locked)

#### Project Status Pill Logic

**RED** if any:
- deadline exists and `days_to_deadline < 0`
- `slip_risk_score ≥ 0.75`
- `blocked_critical_path=true`

**YELLOW** if any:
- deadline exists and `days_to_deadline ≤ 7`
- `slip_risk_score ∈ [0.45, 0.75)`
- `dependency_breaker=true` (within horizon)
- velocity trend negative (if available)

**GREEN** otherwise.

If no deadline: can be Yellow/Red only via risk/blocking; else Green.

#### Slip Risk Formula (locked)

Normalize each subscore to 0..1.

```
slip_risk = 0.35*deadline_pressure
          + 0.25*remaining_work_ratio
          + 0.25*capacity_gap_ratio
          + 0.15*blocking_severity
```

Definitions:
- **deadline_pressure:**
  - if no deadline → 0
  - else `clamp01(1 - (days_to_deadline / 14))` (14d runway)
- **remaining_work_ratio:**
  - `open_effort_hours / max(1, planned_effort_hours)` if planned exists
  - else `open_tasks / max(1, total_tasks)` as fallback
- **capacity_gap_ratio:**
  - `clamp01((hours_needed - hours_available) / max(1, hours_needed))`
- **blocking_severity:**
  - `clamp01(blocked_critical_tasks / max(1, critical_tasks))`

#### Delivery Dial (locked output)

- "{X} Red, {Y} Yellow, {Z} Green (top 25 in scope)"
- plus one sentence: "Highest risk: {project} ({time_to_slip})"
- Confidence: LOW if project gates failing or linked-task coverage < 80%

### 6.2 Cash: AR Health (locked)

**AR definition:**
- AR = `status IN ('sent','overdue') AND paid_date IS NULL`

**Valid AR for scoring:**
- AR AND `due_date IS NOT NULL` AND `client_id IS NOT NULL`

Buckets use spec: current, 1–30, 31–60, 61–90, 90+

#### Cash Dial (locked output)

- "Valid AR: {total_amt}. Severe: {61–90 + 90+}."
- Badge Red if `severe_pct ≥ 0.25` OR any 90+ > threshold
- Badge Yellow if `moderate_pct ≥ 0.30`
- Else Green
- If validity coverage <95% → PARTIAL

### 6.3 Clients: Health / Churn Risk (locked)

Client health score is computed by your Client Truth (per spec). On Page 0:
- Show drift and tier-aware thresholds.

#### Churn Risk (locked)

Churn risk is 0..1 derived from:
- health_score band (worse = higher)
- recent negative drift magnitude
- unresolved commitments to that client
- comms responsiveness issues (SLA breaches)

Locked formula:

```
churn_risk = clamp01(
  0.50*(1 - health_score/100)
+ 0.20*drift_severity
+ 0.20*comms_risk
+ 0.10*commitment_risk
)
```

#### Client Dial shows:

- "At-risk clients: {count} (Top: {client})"
- Badge Red if any tier A/B client `churn_risk ≥ 0.75` else Yellow if `≥0.55` else Green

### 6.4 Capacity (locked)

Capacity is expressed as gap, not "utilization %".

For each lane/person within horizon:
- `hours_available` from time blocks/calendar minus fixed constraints
- `hours_needed` from eligible tasks/projects effort within horizon
- `capacity_gap = hours_needed - hours_available`

#### Capacity Dial shows:

- "Biggest gap: {lane/person} (−{hours}h)"
- Badge Red if any gap ≥ 6h TODAY or ≥ 10h THIS WEEK, else Yellow if ≥ 3h / 6h.

### 6.5 Comms (locked)

Comms risk = response deadlines + VIP sensitivity + extracted commitments.

This page does not browse inbox; it surfaces only delivery/client relevant signals.

---

## 7) Intersection Tiles (the "hours-to-assemble manually" value)

### 7.1 Churn × Money (locked)

List (in drawer) top 5 clients where:
- `churn_risk ≥ 0.60` AND
- `valid_AR_total > 0` AND
- (`overdue_amt > 0` OR `severe_bucket_amt > 0`)

**Tile sentence:**
- "{N} clients: churn risk + overdue AR. Largest exposure: {client}."

Primary CTA: "Open Client 360" pinned to that client (future page).

### 7.2 Delivery × Capacity (locked)

List top 5 projects where:
- project status is Red/Yellow AND
- `capacity_gap_ratio ≥ 0.30` within horizon OR `blocked_critical_path=true`

**Tile sentence:**
- "{N} projects impossible under current capacity. Worst: {project}."

Primary CTA: "Open Delivery Command" (Page 2) scoped to those projects.

---

## 8) Ranking Contracts (no vibes, locked ordering)

### 8.1 "First to break" selection (locked)

Compute candidate set from eligible items across domains:
- top 10 risky projects (delivery)
- top 10 risky clients (clients)
- top 10 constraints (capacity)
- top 10 AR clusters (cash)
- top 10 comms breaches (comms)

For each candidate, compute:

**BaseScore (locked dimensions, 0..1 each):**

```
BaseScore = 0.30*Impact + 0.30*Urgency + 0.20*Controllability + 0.20*ConfidenceScalar
```

- **Impact:** domain-specific (normalized)
- **Urgency:** derived from time_to_consequence (inverse mapping)
- **Controllability:** 1 if Moh can act now (no hard blockers), else scaled
- **ConfidenceScalar:** HIGH=1.0, MED=0.6, LOW=0.3

Then compute ModeWeightedScore:

```
ModeWeightedScore = BaseScore * DomainWeight(mode, domain)
```

Pick the max. Tie-breakers:
1. shortest time_to_consequence
2. highest controllability
3. highest confidence

### 8.2 Heatstrip project ordering (locked)

Order by:
1. Status severity (Red > Yellow > Green)
2. slip_risk_score desc
3. shortest time_to_slip
4. highest value_at_risk (if available else 0)
5. lowest confidence last (i.e., prefer higher confidence)

### 8.3 Constraints strip ordering (locked)

Order by:
1. capacity_gap hours desc
2. soonest time_to_consequence among work they own
3. dependency_breaker count desc
4. confidence desc

### 8.4 Exceptions feed ordering (locked)

Order by ModeWeightedScore (same model) with horizon eligibility enforced.

---

## 9) Action Mutation Model (inherits Page 1, locked)

Risk levels:
- **Auto-Execute (immediate):** link task, assign owner, set lane/priority/due, create queue item
- **Propose (pending_actions):** email draft, invoice reminder, move project status, bulk reassignment
- **Explicit Approval:** invoice amount/date edits, VIP comms

All surfaced cards must show:
- Primary CTA = Execute/Propose (by risk)
- Secondary = Open context
- If Propose → must write `pending_actions` with idempotency key

---

## 10) Snapshot Contract (single payload the UI consumes)

UI must render from a single `agency_snapshot.json` produced per cycle.

Minimum required structure (locked fields; you may add fields, but may not remove/rename):

```json
{
  "meta": {
    "generated_at": "ISO8601",
    "mode": "Ops Head|Co-Founder|Artist",
    "horizon": "NOW|TODAY|THIS_WEEK",
    "scope": { "lanes": [], "owners": [], "clients": [], "include_internal": false }
  },
  "trust": {
    "data_integrity": true,
    "project_brand_required": true,
    "project_brand_consistency": true,
    "client_coverage_pct": 0,
    "finance_ar_coverage_pct": 0,
    "commitment_ready_pct": 0,
    "collector_staleness": { "gmail_hours": 0, "calendar_hours": 0, "tasks_hours": 0, "xero_hours": 0 },
    "last_refresh_at": "ISO8601"
  },
  "narrative": {
    "first_to_break": {
      "entity_type": "project|client|lane|person|ar|thread",
      "entity_id": "string",
      "time_to_consequence_hours": 0,
      "top_driver": "string",
      "primary_action": { "risk": "auto|propose|approval", "label": "string", "payload": {} },
      "reason": "string",
      "confidence": "HIGH|MED|LOW",
      "why_low": ["string"]
    },
    "deltas": [ { "text": "string", "impact": 0.0, "entity_refs": [] } ]
  },
  "tiles": {
    "delivery": { "badge": "GREEN|YELLOW|RED|PARTIAL", "summary": "string", "cta": "string" },
    "cash": { "badge": "GREEN|YELLOW|RED|PARTIAL", "summary": "string", "cta": "string" },
    "clients": { "badge": "GREEN|YELLOW|RED|PARTIAL", "summary": "string", "cta": "string" },
    "churn_x_money": { "badge": "GREEN|YELLOW|RED|PARTIAL", "summary": "string", "cta": "string", "top": [] },
    "delivery_x_capacity": { "badge": "GREEN|YELLOW|RED|PARTIAL", "summary": "string", "cta": "string", "top": [] }
  },
  "heatstrip_projects": [ { "project_id": "string", "name": "string", "status": "GREEN|YELLOW|RED", "time_to_slip_hours": 0, "confidence": "HIGH|MED|LOW" } ],
  "constraints": [ { "type": "person|lane", "id": "string", "name": "string", "capacity_gap_hours": 0, "time_to_consequence_hours": 0, "confidence": "HIGH|MED|LOW" } ],
  "exceptions": [ { "type": "delivery|money|churn|capacity|commitment|blocked|unknown", "id": "string", "title": "string", "score": 0.0, "confidence": "HIGH|MED|LOW", "primary_action": {}, "drawer_ref": "string" } ],
  "drawers": { "drawer_ref": { "summary": "string", "evidence": [], "actions": [], "reason": "string", "why_low": [] } }
}
```

**Hard caps enforced in payload:**
- deltas max 5
- heatstrip_projects max 25
- constraints max 12
- exceptions exactly 7 (or fewer if not enough eligible; never more)

---

## 11) Acceptance Tests (must pass)

1. If `data_integrity=false` → only Integrity panel renders; no other module visible.
2. Exceptions list is ≤7 and each has a type in the locked taxonomy.
3. Heatstrip never exceeds 25; constraints never exceed 12.
4. Narrative "first to break" always includes: entity, TTC, driver, action, reason, confidence.
5. If any module is PARTIAL, drawer must state why (missing due_date/client_id, coverage low, stale collector).
6. Clicking any surfaced item opens a drawer with: summary, evidence, actions, reason.
7. No module contains a freeform "all tasks" list or inbox browsing.

---

*End of Page 0 LOCKED SPEC (v1)*
