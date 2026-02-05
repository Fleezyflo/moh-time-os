# Page 1 — DELIVERY COMMAND (Portfolio Board + Project Room) — LOCKED SPEC (v1)

> Locked: 2026-02-03
> Status: Build-ready

---

## 0. Purpose

A delivery operating console that answers, in under 60 seconds:

1. Which projects/retainers will slip first (and why)?
2. What are the few interventions that change outcomes today/this week?
3. Where is capacity making delivery impossible?
4. What's blocked, what's breaking next, what changed?

**Hard rule:** This is not a task browser. It surfaces portfolio + critical chain, then drills to one project at a time.

---

## 1. Global Controls (must match Page 0 contract)

### 1.1 Mode Selector (locked)

Modes affect ranking weights, not underlying truth:
- Ops Head
- Co-Founder
- Artist

Mode weights are inherited from Page 0 (Delivery/Money/Clients/Capacity/Comms).

### 1.2 Horizon Selector (locked)

Horizon affects eligibility gates (filter-before-rank), inherited from Page 0:
- NOW (4h)
- TODAY
- THIS WEEK

### 1.3 Scope Chips (locked)

Multi-select filters applied across Page 1:
- Lane(s)
- Owner(s)
- Client(s)
- Toggle: include/exclude internal projects (default per Page 0 rules)

---

## 2. Trust & Gating (inherits Page 0; locked behavior)

### 2.1 Trust Strip (always visible)

Must show:
- `data_integrity`
- collector staleness
- `project_brand_required`, `project_brand_consistency`
- `client_coverage_pct`, `commitment_ready_pct`, `finance_ar_coverage_pct`
- `last_refresh_at`

### 2.2 Hard gating behavior

**If `data_integrity=false`:** Page 1 shows only:
- Integrity Failure panel
- "Open Inspector"
- Trust strip

**If integrity true but project gates fail:**
- Page may render but must show PARTIAL badge
- Confidence for affected projects = LOW
- No "Green/Healthy" language without LOW badge + "why low" bullets

---

## 3. Anti-Overstack Limits (hard caps; locked)

If it doesn't fit, it goes to Inspector — not Delivery Command.

| Element | Max |
|---------|-----|
| Portfolio list | 25 rows (rest behind "Show more" if engineer insists; default hidden) |
| Breaks next | 3 |
| Critical chain | exactly 1 chain surfaced (the top one) |
| Recent change | 3 |
| Comms threads | 5 |

---

## 4. Page Layout (fixed zones; not a table site)

### Zone A — Top Bar (fixed)

- Mode / Horizon / Scope chips
- Trust strip

### Zone B — Portfolio Board (left; primary)

A ranked grid/list of 25 project chips (not a spreadsheet table).

Each chip shows:
- Project name (short)
- Status pill: GREEN/YELLOW/RED or PARTIAL
- Time-to-slip (hours or days; may be "overdue")
- Primary driver label (one word): Deadline | Capacity | Blocked | Scope | Comms | Unknown
- Confidence dot (HIGH/MED/LOW)

**Interaction:**
- Click chip → opens Zone C Project Room
- Pin chip → persists on top (max 3 pinned; pinned does not break 25 cap—pinned occupy slots)

### Zone C — Project Room (right drawer or right panel; exclusive focus)

Opened when a project is selected. Shows exactly these modules, in this order:

#### 1. Project Header
- Name, owner, lane, client/brand (if client-facing), type (project/retainer), internal flag
- Status pill + confidence + "Why low" (max 3 bullets)

#### 2. Slip Risk Panel (deterministic)
- `slip_risk_score` (0..1)
- `time_to_slip_hours`
- The top 2 drivers contributing to slip risk (must be explicit)

#### 3. Breaks Next (max 3)
Each break item is one sentence + one action:
```
"Break: {thing} in {TTC}. Driver: {driver}. Action: {CTA}."
```

#### 4. Critical Chain (exactly 1)
A compact chain of the single most critical dependency path:
- Task/Blocker → Task → Milestone/Deadline
- Must include TTC and the "unlock" action
- If no chain exists, show: "No critical chain detected (confidence: X)."

#### 5. Capacity Reality
- Hours available vs hours needed within horizon
- Capacity gap hours + whether gap is solvable by reassignment
- Top constraint (person or lane)

#### 6. Comms Threads (max 5)
Only threads relevant to this project/client risk:
- SLA breach / VIP / commitment breach
- Each shows: subject, age, expected response by, risk badge

#### 7. Recent Change (max 3)
Exactly up to 3 deltas since last refresh (project-scoped):
- status change, slip risk change, capacity gap change, new blocker

#### 8. Actions Panel
Primary + secondary actions (risk-labeled) using Page 0 action model:
- Auto-Execute / Propose / Explicit Approval
- All actions must include idempotency key if written to `pending_actions`

---

## 5. Eligibility Gates (filter-before-rank; locked)

A project is eligible to appear in the Portfolio Board only if it passes the horizon gates (Page 0) OR is already RED.

**NOW:** `time_to_slip ≤ 12h` OR `dependency_breaker=true` OR `capacity_blocker_today=true` OR status RED

**TODAY:** `time_to_slip ≤ EOD` OR `tomorrow_starts_broken=true` OR status RED

**THIS WEEK:** `critical_path=true` OR `compounding_damage=true` OR status RED

**If project has no deadline and no inferred consequence**, it may appear only if:
- it is blocking eligible work, OR
- it has P1 resolution issues, OR
- it is client-facing and has comms/commitment breach with TTC

---

## 6. Deterministic Delivery Computations (locked)

### 6.1 time_to_slip_hours (locked)

Computed as:
- If deadline exists: `deadline_datetime - now`
- Else if inferred consequence exists (Page 0 stale thresholds): use inferred TTC
- Else `null`

### 6.2 Project Status Pill (locked, same as Page 0 delivery logic)

**RED** if any:
- deadline exists and `days_to_deadline < 0`
- `slip_risk_score ≥ 0.75`
- `blocked_critical_path=true`

**YELLOW** if any:
- deadline exists and `days_to_deadline ≤ 7`
- `slip_risk_score ∈ [0.45, 0.75)`
- `dependency_breaker=true` (within horizon)
- velocity trend negative (if available)

**GREEN** otherwise

If project gates fail → status renders but must be PARTIAL + LOW confidence.

### 6.3 Slip Risk Formula (locked)

Normalize each input to 0..1:

```
slip_risk =
  0.35*deadline_pressure +
  0.25*remaining_work_ratio +
  0.25*capacity_gap_ratio +
  0.15*blocking_severity
```

**Definitions (locked):**

- **deadline_pressure:**
  - if no deadline → 0
  - else `clamp01(1 - (days_to_deadline / 14))`

- **remaining_work_ratio:**
  - if `planned_effort_hours` exists: `open_effort_hours / max(1, planned_effort_hours)`
  - else fallback: `open_tasks / max(1, total_tasks)`

- **capacity_gap_ratio:**
  - `clamp01((hours_needed - hours_available) / max(1, hours_needed))`

- **blocking_severity:**
  - `clamp01(blocked_critical_tasks / max(1, critical_tasks))`

---

## 7. Ranking Contracts (locked)

### 7.1 Portfolio ordering (locked)

Order eligible projects by:
1. Status severity: RED > YELLOW > GREEN
2. `slip_risk_score` desc
3. shortest `time_to_slip_hours`
4. highest `value_at_risk` (if exists else 0)
5. confidence preference: HIGH > MED > LOW

### 7.2 "Breaks Next" ordering (locked)

Within selected project, breaks are ordered by:
1. shortest `time_to_consequence`
2. highest controllability
3. highest confidence

Cap at 3.

### 7.3 Critical chain selection (locked)

Pick exactly one chain:
- the chain with the earliest end consequence (deadline/milestone),
- tie-breaker: chain with most blocked nodes,
- then highest controllability.

---

## 8. Data Sources (locked; engineer must use these)

Minimum inputs:
- `projects` (deadline, lane, owner, is_internal, type, client/brand fields, status)
- `tasks` filtered by project_id and link statuses
- `communications` filtered by client_id and/or project association (if available)
- gates + computed coverage metrics
- capacity/time blocks + calendar events (for hours_available)
- commitments (if used for TTC fallback)

---

## 9. Snapshot Contract (single payload the UI consumes; locked)

Page 1 renders from `agency_snapshot.json` or a dedicated `delivery_snapshot.json`.
If dedicated, it must include the same meta + trust block as Page 0.

### 9.1 Required structure (Page 1 section)

Add this under `agency_snapshot.delivery_command`:

```json
"delivery_command": {
  "portfolio": [
    {
      "project_id": "string",
      "name": "string",
      "status": "GREEN|YELLOW|RED|PARTIAL",
      "slip_risk_score": 0.0,
      "time_to_slip_hours": 0,
      "top_driver": "Deadline|Capacity|Blocked|Scope|Comms|Unknown",
      "confidence": "HIGH|MED|LOW",
      "why_low": ["string"]
    }
  ],
  "selected_project": {
    "project_id": "string",
    "header": { "owner": "string", "lane": "string", "client": "string", "type": "project|retainer", "is_internal": false },
    "slip": { "slip_risk_score": 0.0, "time_to_slip_hours": 0, "top_drivers": ["string","string"] },
    "breaks_next": [ { "text": "string", "ttc_hours": 0, "driver": "string", "primary_action": {} } ],
    "critical_chain": { "nodes": [ { "type": "task|blocker|milestone", "id": "string", "label": "string", "ttc_hours": 0 } ] },
    "capacity": { "hours_needed": 0, "hours_available": 0, "gap_hours": 0, "top_constraint": { "type": "person|lane", "name": "string" } },
    "comms_threads": [ { "thread_id": "string", "subject": "string", "age_hours": 0, "expected_response_by": "ISO8601", "risk": "LOW|MED|HIGH" } ],
    "recent_change": [ { "text": "string", "impact": 0.0 } ],
    "actions": [ { "risk": "auto|propose|approval", "label": "string", "payload": {} } ]
  }
}
```

### 9.2 Hard caps enforced in payload (locked)

| Element | Max |
|---------|-----|
| portfolio | 25 |
| breaks_next | 3 |
| critical_chain | exactly 1 |
| recent_change | 3 |
| comms_threads | 5 |

---

## 10. Acceptance Tests (must pass)

1. If `data_integrity=false`: only Integrity panel renders (no portfolio, no project room).
2. Portfolio never exceeds 25; project room modules obey caps (3/1/3/5).
3. Portfolio ordering matches §7.1 exactly (test with synthetic data).
4. Slip risk formula exactly matches §6.3 and is unit-tested.
5. Every project chip has confidence + (if LOW) `why_low` ≤3 bullets.
6. Clicking a project shows Project Room with all required modules; no "task list browsing" surfaces by default.
7. Actions obey risk model: Auto executes immediately; Propose writes `pending_actions` with idempotency key; Approval is gated.

---

*End of Page 1 LOCKED SPEC (v1)*
