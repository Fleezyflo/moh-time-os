# 09_GAPS_FAILURE_MODES_AND_CONFIDENCE.md — Data Gaps, Failure Modes, and Confidence Model

> Phase G Deliverable | Generated: 2026-02-04

---

## 1. Source-Level Gaps

### 1.1 Google Tasks

| Gap | Impact | Mitigation |
|-----|--------|------------|
| No assignee support | Can't track individual workload from this source | Use Asana as primary task source |
| No time estimates | Duration defaults to 60min | Mark confidence as LOW for capacity |
| No dependencies | Can't build critical path | Rely on Asana dependency data |

**Failure Modes:**
- `gog tasks` CLI unavailable → Sync fails, stale data
- Token expiration → Silent failure, no new data

**Detection:** Check `sync_state.error` and `sync_state.last_success`

---

### 1.2 Google Calendar

| Gap | Impact | Mitigation |
|-----|--------|------------|
| No client linkage | Events don't map to clients | Match title patterns |
| No prep extraction | Prep notes are inferred | Show as "suggested" |

**Failure Modes:**
- API quota exceeded → Partial data
- Private events hidden → Missing time blocks

**Detection:** Compare event count vs expected

---

### 1.3 Gmail

| Gap | Impact | Mitigation |
|-----|--------|------------|
| Body fetch rate-limited | Only ~50% have full body | Mark body_text_source |
| 12% client linkage | Most comms unlinked | Show unlinked count prominently |
| No response detection | requires_response unreliable | Don't rely on this flag |

**Failure Modes:**
- OAuth token expired → No new emails
- Rate limiting → Partial body fetch

**Detection:** Check `body_text IS NULL` percentage

---

### 1.4 Asana

| Gap | Impact | Mitigation |
|-----|--------|------------|
| Only 15 projects synced | May miss tasks | Increase limit or prioritize |
| Project→client not automatic | Requires manual enrollment | Show unlinked projects |

**Failure Modes:**
- API rate limit → Incomplete sync
- Personal access token expired → Auth failure

**Detection:** Check project count vs Asana

---

### 1.5 Xero

| Gap | Impact | Mitigation |
|-----|--------|------------|
| No invoice line items | Can't see project-level AR | Show only client-level |
| Client matching by name | May miss matches | Show unmatched invoices |

**Failure Modes:**
- OAuth expired → No AR data
- API changes → Parse failures

**Detection:** `invoice_count = 0` when expected > 0

---

## 2. Domain-Level Gaps

### 2.1 Delivery Domain

| What's Missing | Impact | Workaround |
|----------------|--------|------------|
| Real velocity data | Can't predict slip accurately | Use completion % trends |
| Milestone tracking | No milestone view | Use project.deadline only |
| Time logging | No actual vs estimated | Mark capacity as LOW confidence |

**Unreliable:**
- `slip_risk_score` when no deadline
- `days_to_deadline` when deadline = NULL
- `blocked_tasks` when blockers not populated

**Fake Confidence Risk:**
- Showing "GREEN" when task data is stale
- Showing completion % when tasks not synced

**UI Must:**
- Show "Last synced X ago" timestamp
- Mark projects with no deadline as "No deadline set"

---

### 2.2 Clients Domain

| What's Missing | Impact | Workaround |
|----------------|--------|------------|
| Contact data | No people → client mapping | Show "No contacts" |
| Meeting notes | No context from calls | Link to calendar |
| Manual health overrides | Can't correct bad scores | Add manual override |

**Unreliable:**
- `health_score` when no linked projects
- `relationship_trend` when no history
- Sub-scores when source data missing

**Fake Confidence Risk:**
- High health score when no data (defaults to 100)
- "No issues" when comms not linked

**UI Must:**
- Show "Based on X projects, Y tasks" source info
- Mark "Limited data" when linkage < 50%

---

### 2.3 Cash Domain

| What's Missing | Impact | Workaround |
|----------------|--------|------------|
| Payment promises | No expected payment dates | Use due_date only |
| Partial payments | Can't track partial | Show full amount |
| Credit notes | May overstate AR | Filter by status |

**Unreliable:**
- Nothing (Xero data is authoritative)

**Fake Confidence Risk:**
- None if Xero syncing

**UI Must:**
- Show "Synced from Xero X ago"
- Show invoice count with AR total

---

### 2.4 Capacity Domain

| What's Missing | Impact | Workaround |
|----------------|--------|------------|
| Time tracking | No actual hours | Use estimates only |
| Calendar integration per person | Can't see meeting load | Use team_events if populated |
| PTO/vacation | Overstates capacity | Manual adjustment needed |

**Unreliable:**
- ALL capacity metrics (no time tracking)
- `hours_available` (theoretical only)
- `utilization_pct` (based on estimates)

**Fake Confidence Risk:**
- Showing "20 hours available" when person is in meetings all day
- Showing specific numbers without data

**UI Must:**
- Label all capacity as "Estimated"
- Show "Based on task estimates, not actual time"
- Consider hiding capacity metrics entirely until time tracking exists

---

### 2.5 Comms Domain

| What's Missing | Impact | Workaround |
|----------------|--------|------------|
| 88% comms unlinked | Can't attribute to clients | Show unlinked prominently |
| Response detection | Can't track SLAs | Don't show SLA metrics |
| Commitment extraction sparse | Only 3 commitments | Mark as "Experimental" |

**Unreliable:**
- `requires_response` (not detected reliably)
- `expected_response_by` (not populated)
- Commitment counts (too sparse)

**Fake Confidence Risk:**
- "No pending responses" when detection is broken
- "All commitments fulfilled" when extraction isn't running

**UI Must:**
- Show "X of Y emails linked to clients"
- Mark commitment features as "Beta"
- Don't show SLA metrics

---

## 3. Confidence Model

### 3.1 Gate-Based Confidence

| Gate | Pass Effect | Fail Effect |
|------|-------------|-------------|
| data_integrity | Domain enabled | Domain BLOCKED |
| client_coverage | Full confidence | Degraded (show %) |
| commitment_ready | Comms enabled | Comms degraded |
| finance_ar_coverage | Cash enabled | Cash degraded |
| capacity_baseline | Capacity enabled | Capacity BLOCKED |

### 3.2 Confidence Levels

| Level | Meaning | UI Treatment |
|-------|---------|--------------|
| HIGH | All gates pass, >80% coverage | Normal display |
| MED | Quality gates fail, 50-80% coverage | Yellow indicator, show % |
| LOW | <50% coverage or key data missing | Red indicator, prominent warning |
| BLOCKED | Blocking gate fails | Hide domain, show error |

### 3.3 Per-Domain Confidence

```
DELIVERY:
  blocking: [data_integrity]
  quality: [project_brand_required, project_client_populated]

CLIENTS:
  blocking: [data_integrity]
  quality: [client_coverage]

CASH:
  blocking: [data_integrity, finance_ar_clean]
  quality: [finance_ar_coverage]

COMMS:
  blocking: [data_integrity]
  quality: [commitment_ready]

CAPACITY:
  blocking: [data_integrity, capacity_baseline]
  quality: []
```

---

## 4. Drift/Corruption Detection

### 4.1 Invariant Checks

Run on every cycle:
1. No `linked` tasks with NULL project_id
2. No `unlinked` tasks with non-NULL project_id
3. Internal projects have NULL client_id
4. Non-internal projects have brand_id

### 4.2 Count Anomaly Detection

| Check | Threshold | Action |
|-------|-----------|--------|
| Task count drops >50% | Alert | Check collector |
| Comm count drops >50% | Alert | Check Gmail |
| Invoice count = 0 | Alert | Check Xero |
| Client count drops | Alert | Investigate |

### 4.3 Freshness Checks

| Source | Stale Threshold | Action |
|--------|-----------------|--------|
| tasks | >15 min | Yellow warning |
| calendar | >5 min | Yellow warning |
| gmail | >10 min | Yellow warning |
| xero | >1 hour | Yellow warning |
| Any | >1 hour | Red warning |

---

## 5. UI Guidance When Confidence Low

### 5.1 Never Hide Data

- Always show what we have
- Add confidence indicators
- Explain limitations

### 5.2 Label Patterns

| Situation | Label |
|-----------|-------|
| Low linkage | "Based on X% of data" |
| No history | "No trend data available" |
| Stale data | "Last updated X ago" |
| Missing source | "Source unavailable" |
| Estimated value | "Estimated" badge |

### 5.3 Color Coding

| Confidence | Background | Text |
|------------|------------|------|
| HIGH | None | Normal |
| MED | Yellow/10% | Normal |
| LOW | Red/10% | Normal |
| BLOCKED | Gray | "Unavailable" |

### 5.4 Specific Warnings

```
Capacity: "⚠️ Capacity estimates are theoretical. No time tracking data available."

Comms: "⚠️ 88% of emails not linked to clients. Showing all communications."

Commitments: "⚠️ Commitment extraction is experimental. Only 3 commitments found."

Client Health: "ℹ️ Health score based on 2 projects and 0 linked communications."
```

---

## 6. Data Quality Roadmap

### 6.1 Critical Fixes (Unlocks Value)

| Fix | Impact | Effort |
|-----|--------|--------|
| More client_identities | Improves comm linkage | Low |
| Full Asana project sync | Complete task data | Low |
| Commitment extraction tuning | Better comms insights | Medium |

### 6.2 Medium Priority

| Fix | Impact | Effort |
|-----|--------|--------|
| Time tracking integration | Enables capacity | High |
| Contact sync | Enables people → client | Medium |
| Response detection | Enables SLA tracking | High |

### 6.3 Nice to Have

| Fix | Impact | Effort |
|-----|--------|--------|
| Slack integration | More comms | Medium |
| Meeting notes extraction | Context | High |
| Payment prediction | Cash forecasting | High |

---

*End of 09_GAPS_FAILURE_MODES_AND_CONFIDENCE.md*
