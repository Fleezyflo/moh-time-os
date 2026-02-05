# 06_METRICS_AND_SCORES.md — Computed Metrics, Scores, Badges, and Gates

> Phase D Deliverable | Generated: 2026-02-04

---

## 1. Gates (Data Quality Checks)

### 1.1 data_integrity

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/gates.py` |
| **Type** | Boolean (all 6 invariants must pass) |
| **Formula** | `inv1 AND inv2 AND inv3 AND inv4 AND inv5 AND inv6` |
| **Inputs** | tasks, projects, brands, clients |
| **Eligibility** | Always evaluated |
| **Confidence Rule** | BLOCKING if fails |
| **UI Usage** | Trust strip gate indicator |
| **Failure Behavior** | Snapshot blocked, show "Data integrity failed" |

**Invariants:**
1. `project_link_status='linked'` requires valid project→brand→client chain
2. `project_link_status='unlinked'` requires `project_id IS NULL`
3. `project_link_status='partial'` requires `project_id IS NOT NULL`
4. `project_link_status='partial'` must have broken chain (not resolvable)
5. `client_link_status='linked'` requires complete chain
6. `client_link_status='n/a'` requires internal project

---

### 1.2 project_brand_required

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/gates.py` |
| **Type** | Boolean |
| **Formula** | `COUNT(*) = 0 WHERE is_internal=0 AND brand_id IS NULL` |
| **Inputs** | projects.is_internal, projects.brand_id |
| **UI Usage** | Quality indicator |
| **Failure Behavior** | Shows warning, delivery data degraded |

---

### 1.3 client_coverage

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/gates.py` |
| **Type** | Percentage (threshold ≥80%) |
| **Formula** | `100 * SUM(CASE WHEN client_link_status='linked' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN client_link_status != 'n/a' THEN 1 ELSE 0 END), 0)` |
| **Inputs** | tasks.client_link_status |
| **UI Usage** | Coverage badge on trust strip |
| **Failure Behavior** | Shows current % with warning if <80% |

---

### 1.4 commitment_ready

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/gates.py` |
| **Type** | Percentage (threshold ≥50%) |
| **Formula** | `100 * SUM(CASE WHEN body_text IS NOT NULL AND LENGTH(body_text) >= 50 THEN 1 ELSE 0 END) / COUNT(*)` |
| **Inputs** | communications.body_text |
| **UI Usage** | Comms domain confidence |
| **Failure Behavior** | Comms data marked as degraded |

---

### 1.5 finance_ar_coverage

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/gates.py` |
| **Type** | Percentage (threshold ≥95%) |
| **Formula** | `100 * SUM(CASE WHEN client_id IS NOT NULL AND due_date IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*)` for AR invoices |
| **Inputs** | invoices.client_id, invoices.due_date, invoices.status |
| **UI Usage** | Finance domain confidence |
| **Failure Behavior** | AR data marked as incomplete |

---

### 1.6 finance_ar_clean

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/gates.py` |
| **Type** | Boolean |
| **Formula** | `COUNT(*) = 0` for AR invoices missing client_id or due_date |
| **Inputs** | invoices |
| **UI Usage** | AR validity indicator |
| **Failure Behavior** | Cash domain shows warning |

---

### 1.7 capacity_baseline

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/gates.py` |
| **Type** | Boolean |
| **Formula** | `COUNT(*) = 0 WHERE weekly_hours <= 0` |
| **Inputs** | capacity_lanes.weekly_hours |
| **UI Usage** | Capacity domain confidence |
| **Failure Behavior** | Capacity metrics unavailable |

---

## 2. Scores

### 2.1 BaseScore

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/agency_snapshot/scoring.py` |
| **Type** | Float 0.0-1.0 |
| **Formula** | `0.30*Impact + 0.30*Urgency + 0.20*Controllability + 0.20*ConfidenceScalar` |
| **Inputs** | impact, urgency, controllability, confidence |
| **Locked Weights** | Yes (per spec) |
| **UI Usage** | Internal ranking, not displayed directly |

**ConfidenceScalar:**
- HIGH: 1.0
- MED: 0.6
- LOW: 0.3

---

### 2.2 ModeWeightedScore

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/agency_snapshot/scoring.py` |
| **Type** | Float 0.0-1.0 |
| **Formula** | `BaseScore * DomainWeight(mode, domain)` |

**Domain Weights by Mode:**

| Domain | Ops Head | Co-Founder | Artist |
|--------|----------|------------|--------|
| Delivery | 0.40 | 0.15 | 0.25 |
| Money | 0.10 | 0.35 | 0.10 |
| Clients | 0.10 | 0.35 | 0.10 |
| Capacity | 0.25 | 0.05 | 0.35 |
| Comms | 0.15 | 0.10 | 0.20 |

---

### 2.3 SlipRiskScore

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/agency_snapshot/delivery.py` |
| **Type** | Float 0.0-1.0 |
| **Formula** | `0.35*DeadlinePressure + 0.25*RemainingWorkRatio + 0.25*CapacityGapRatio + 0.15*BlockingSeverity` |
| **Inputs** | projects.deadline, tasks.status, tasks.duration_min, tasks.blockers |
| **UI Usage** | Project heatstrip color, portfolio sorting |

**DeadlinePressure Calculation:**
```python
if days_to_deadline <= 0: return 1.0  # Overdue
runway = 14  # days
return max(0, 1 - (days_to_deadline / runway))
```

---

### 2.4 ClientHealthScore

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/agency_snapshot/client360_page10.py` |
| **Type** | Float 0-100 |
| **Formula** | Weighted average of 5 sub-scores |
| **Sub-scores** | delivery, finance, responsiveness, commitments, capacity |
| **UI Usage** | Client 360 tiles, client portfolio |

**Sub-score Weights:**
- Delivery: 30%
- Finance: 25%
- Responsiveness: 20%
- Commitments: 15%
- Capacity: 10%

---

### 2.5 UrgencyFromTTC

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/agency_snapshot/scoring.py` |
| **Type** | Float 0.0-1.0 |
| **Formula** | Inverse mapping from time_to_consequence_hours |

```python
if ttc <= 0: return 1.0      # Overdue
if ttc <= 12: return 1.0 - (ttc/12)*0.3   # 1.0 → 0.7
if ttc <= 24: return 0.7 - ((ttc-12)/12)*0.2  # 0.7 → 0.5
if ttc <= 168: return 0.5 - ((ttc-24)/144)*0.4  # 0.5 → 0.1
return max(0, 0.1 - (ttc-168)/1000)
```

---

### 2.6 TaskPriorityScore

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/collectors/tasks.py`, `lib/priority_engine.py` |
| **Type** | Integer 0-100 |
| **Formula** | Base 50 + due_date_modifier + has_notes_modifier |
| **UI Usage** | Task list sorting |

```python
score = 50
if overdue: score += min(40, 40 + abs(days_overdue) * 2)
elif due_today: score += 35
elif due_tomorrow: score += 25
elif due_within_3_days: score += 15
elif due_within_7_days: score += 5
if has_notes: score += 5
return clamp(0, 100, score)
```

---

## 3. Status Colors

### 3.1 ProjectHealth (RED/YELLOW/GREEN)

| Color | Condition |
|-------|-----------|
| GREEN | slip_risk < 0.3 AND no blocked critical tasks |
| YELLOW | slip_risk 0.3-0.6 OR has blocked tasks |
| RED | slip_risk > 0.6 OR blocked critical path OR overdue |

---

### 3.2 ClientHealth (excellent/good/fair/poor/critical)

| Status | Score Range |
|--------|-------------|
| excellent | 80-100 |
| good | 60-79 |
| fair | 40-59 |
| poor | 20-39 |
| critical | 0-19 |

---

### 3.3 InvoiceAgingColor

| Bucket | Color | Days Overdue |
|--------|-------|--------------|
| current | Green | 0 |
| 1-30 | Yellow | 1-30 |
| 31-60 | Orange | 31-60 |
| 61-90 | Red | 61-90 |
| 90+ | Dark Red | >90 |

---

## 4. Coverage Metrics

### 4.1 TaskProjectLinkage

| Attribute | Value |
|-----------|-------|
| **Formula** | `COUNT(project_link_status='linked') / COUNT(*)` |
| **Current Value** | ~98.9% |
| **UI Usage** | Data quality indicator |

### 4.2 TaskClientLinkage

| Attribute | Value |
|-----------|-------|
| **Formula** | `COUNT(client_link_status='linked') / COUNT(client_link_status != 'n/a')` |
| **Current Value** | ~87% |
| **UI Usage** | Client coverage gate |

### 4.3 CommunicationClientLinkage

| Attribute | Value |
|-----------|-------|
| **Formula** | `COUNT(link_status='linked') / COUNT(*)` |
| **Current Value** | ~12.3% |
| **UI Usage** | Comms domain confidence |

---

## 5. Aggregate Metrics

### 5.1 TotalAR

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/agency_snapshot/cash_ar_page12.py` |
| **Formula** | `SUM(amount) WHERE status IN ('sent','overdue') AND paid_date IS NULL` |
| **Current Value** | ~AED 980,642 |
| **UI Usage** | Cash tile, AR waterfall |

### 5.2 ARByBucket

| Attribute | Value |
|-----------|-------|
| **Formula** | `SUM(amount) GROUP BY aging_bucket` |
| **UI Usage** | Aging waterfall chart |

### 5.3 OverdueTaskCount

| Attribute | Value |
|-----------|-------|
| **Formula** | `COUNT(*) WHERE due_date < date('now') AND status NOT IN ('done','completed')` |
| **UI Usage** | Delivery tile, alerts |

### 5.4 QueueSize

| Attribute | Value |
|-----------|-------|
| **Formula** | `COUNT(*) FROM resolution_queue WHERE resolved_at IS NULL` |
| **Current Value** | ~3,950 |
| **UI Usage** | Governance indicators |

---

## 6. Eligibility Gates (for Ranking)

### 6.1 NOW Horizon Eligibility

Item eligible if:
- `time_to_consequence <= 12h`, OR
- `dependency_breaker = true`, OR
- `capacity_blocker_today = true`, OR
- `impact >= 0.5 AND time_to_consequence <= 24h`

### 6.2 TODAY Horizon Eligibility

Item eligible if:
- `time_to_consequence <= 16h`, OR
- `tomorrow_starts_broken = true`, OR
- `impact >= 0.5`, OR
- `time_to_consequence <= 48h`, OR
- `time_to_consequence < 0` (overdue)

### 6.3 THIS_WEEK Horizon Eligibility

Item eligible if:
- `critical_path = true`, OR
- `compounding_damage = true`, OR
- `ar_severe = true`, OR
- `time_to_consequence <= 168h`, OR
- `impact > 0.3`

---

## 7. Confidence Model

### 7.1 Trust State

| Attribute | Value |
|-----------|-------|
| **Owner Module** | `lib/agency_snapshot/confidence.py` |
| **Components** | gates_status, coverage_metrics, sync_freshness |
| **UI Usage** | Trust strip display |

### 7.2 Domain Confidence

| Domain | Blocking Gates | Quality Gates |
|--------|----------------|---------------|
| Delivery | data_integrity | project_brand_required, project_client_populated |
| Clients | data_integrity | client_coverage |
| Cash | data_integrity, finance_ar_clean | finance_ar_coverage |
| Comms | data_integrity | commitment_ready |
| Capacity | data_integrity, capacity_baseline | — |

**Confidence Levels:**
- `reliable`: All gates pass
- `degraded`: Quality gates fail
- `blocked`: Blocking gates fail

---

## 8. Move Types

| Move Type | Domain | Trigger |
|-----------|--------|---------|
| `collection_call` | Cash | AR > threshold, aging > 30d |
| `follow_up_email` | Comms | Thread silence > N days |
| `escalate_blocker` | Delivery | Blocked task > N days |
| `reassign_overload` | Capacity | Person utilization > 100% |
| `schedule_meeting` | Clients | No contact > N days |
| `resolve_link` | Governance | Unlinked entity |

---

*End of 06_METRICS_AND_SCORES.md*
