# 00_INDEX.md — MOH Time OS Data Atlas Index

> Master Index | Generated: 2026-02-04

---

## Purpose

This Data Atlas provides everything a UI designer or agent needs to build interfaces for MOH Time OS. It documents:

- All data sources and how they're collected
- Complete database schema with relationships
- Every field with semantic meaning and constraints
- All computed metrics, scores, and gates
- Query recipes for common UI patterns
- Known gaps and confidence constraints
- Sample data for testing

---

## File Manifest

| # | File | Purpose | Size |
|---|------|---------|------|
| 00 | `00_INDEX.md` | This index + glossary + pitfalls | ~5KB |
| 01 | `01_SYSTEM_MAP.md` | Architecture, paths, data flow | ~14KB |
| 02 | `02_SOURCES_AND_COLLECTORS.md` | External sources, collector details | ~14KB |
| 03 | `03_SCHEMA_ATLAS.sql` | Complete database schema with comments | ~45KB |
| 04 | `04_ENTITY_CATALOG.md` | Entity definitions for UI design | ~18KB |
| 05 | `05_FIELD_CATALOG.json` | Machine-readable field metadata | ~42KB |
| 06 | `06_METRICS_AND_SCORES.md` | Gates, scores, badges, formulas | ~11KB |
| 07 | `07_VIEWS_AND_QUERY_RECIPES.md` | SQL recipes for UI queries | ~11KB |
| 08 | `08_UI_SURFACE_OPPORTUNITIES.md` | What can be shown per domain | ~14KB |
| 09 | `09_GAPS_FAILURE_MODES_AND_CONFIDENCE.md` | Data quality issues and handling | ~10KB |
| 10 | `10_SAMPLE_DATA_PACK.json` | Test data with relationships | ~19KB |
| 11 | `11_CHANGELOG_AND_NEXT_STEPS.md` | Version history and roadmap | ~5KB |

---

## How to Use This Atlas

### For UI Designers

1. Start with **04_ENTITY_CATALOG.md** to understand the data model
2. Review **08_UI_SURFACE_OPPORTUNITIES.md** for what's possible per domain
3. Check **09_GAPS_FAILURE_MODES_AND_CONFIDENCE.md** for limitations
4. Use **10_SAMPLE_DATA_PACK.json** to prototype with real data shapes

### For Developers

1. Start with **01_SYSTEM_MAP.md** for architecture overview
2. Reference **03_SCHEMA_ATLAS.sql** for exact schema
3. Use **07_VIEWS_AND_QUERY_RECIPES.md** for query patterns
4. Check **06_METRICS_AND_SCORES.md** for computation details

### For Agents

1. Parse **05_FIELD_CATALOG.json** for field metadata
2. Reference **06_METRICS_AND_SCORES.md** for metric definitions
3. Check confidence rules before displaying data

---

## Glossary of Canonical Names

### Entities

| Name | Description |
|------|-------------|
| `client` | External customer/company |
| `brand` | Sub-brand of a client |
| `project` | Work container (has tasks) |
| `task` | Work item (atomic unit) |
| `communication` | Email/message record |
| `commitment` | Promise or request extracted from comms |
| `invoice` | AR invoice from Xero |
| `team_member` | Internal person who does work |
| `event` | Calendar event |
| `resolution_queue_item` | Issue needing human resolution |
| `pending_action` | Action awaiting approval |

### Statuses

| Status | Entities | Meaning |
|--------|----------|---------|
| `active` | project, task | In progress |
| `completed` | project, task | Finished |
| `blocked` | task | Can't proceed |
| `overdue` | task, invoice | Past due date |
| `linked` | task, comm | Matched to client |
| `unlinked` | task, comm | Not matched |
| `n/a` | task | Internal (no client) |

### Scores

| Score | Range | Higher = |
|-------|-------|----------|
| `health_score` | 0-100 | Better |
| `priority` | 0-100 | More urgent |
| `slip_risk_score` | 0-1 | More likely to slip |
| `base_score` | 0-1 | Higher priority for ranking |

### Gates

| Gate | Pass Condition |
|------|----------------|
| `data_integrity` | All 6 invariants pass |
| `client_coverage` | ≥80% tasks linked |
| `commitment_ready` | ≥50% comms have body |
| `finance_ar_coverage` | ≥95% AR invoices valid |
| `capacity_baseline` | All lanes have hours |

---

## DO NOT MISREAD — Critical Pitfalls

### 1. Link Status vs Foreign Key

- `project_link_status='linked'` does NOT mean `project_id IS NOT NULL`
- `linked` means the FULL CHAIN is valid (project→brand→client)
- A task can have `project_id` but status `partial` if chain is broken

### 2. Client ID Derivation

- `tasks.client_id` is DERIVED, not set directly
- Chain: task → project → brand → client
- If project is internal, `client_id` will be NULL and `client_link_status='n/a'`

### 3. Capacity Is Theoretical

- ALL capacity metrics are estimates
- No time tracking integration exists
- `duration_min` defaults to 60 for all tasks
- DO NOT show capacity metrics as fact

### 4. Communication Linkage Is Low

- Only 12% of communications link to clients
- 88% show as "unlinked"
- Don't assume comms belong to clients without checking

### 5. Commitment Data Is Sparse

- Only 3 commitments extracted total
- Don't build features assuming rich commitment data
- Mark commitment features as "Beta"

### 6. Aging Bucket Calculation

- `aging_bucket` is only valid for AR invoices (sent/overdue, unpaid)
- Calculated by normalizer, not Xero
- Based on current date vs due_date

### 7. Project Health vs Slip Risk

- `project.health` is categorical (green/yellow/red)
- `slip_risk_score` is continuous (0-1)
- They correlate but are computed differently

### 8. Multiple Priority Fields

- `tasks.priority` (0-100 integer, used for sorting)
- `resolution_queue.priority` (1-5, 1=highest)
- `pending_actions.risk_level` (text: low/medium/high)
- Don't confuse them

### 9. Sync State vs Data Freshness

- `sync_state.last_sync` = when sync was attempted
- `sync_state.last_success` = when it succeeded
- Check both; a sync can fail

### 10. Internal Projects Have No Client

- `is_internal=1` means NO client relationship
- `client_id` MUST be NULL for internal projects
- Gates enforce this invariant

---

## Quick Reference: Data Counts

| Entity | Current Count |
|--------|---------------|
| clients | 190 |
| brands | 21 |
| projects | 100 |
| tasks | 3,761 |
| communications | 488 |
| invoices | 34 |
| commitments | 3 |
| team_members | 31 |
| events | 173 |
| resolution_queue | 3,950 |

---

*End of 00_INDEX.md*
