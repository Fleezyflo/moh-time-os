# MOH Time OS v2 — Build Audit

**Last Updated:** 2026-01-31 (heartbeat build complete)

---

## Legend

- ✅ Complete and working
- ⚠️ Partial / needs more work
- ❌ Not implemented
- 🔧 Schema exists but not populated

---

## Entity Model

### Clients

| Field | Status | Notes |
|-------|--------|-------|
| id, name, tier, type | ✅ | Working, tiers inferred from AR |
| ar_outstanding, ar_aging | ✅ | 24 clients have real AR data |
| health, payment_pattern | ✅ | Inferred from AR |
| annual_value | ❌ | Not populated |
| trend | 🔧 | All default to 'stable' |
| last_interaction | ✅ | Updated on item capture |
| relationship_notes | ❌ | Empty for all |
| contacts (person links) | ✅ | Populated when contacts created |
| active_projects | ✅ | Populated from sync |

### People

| Field | Status | Notes |
|-------|--------|-------|
| id, name, email, phone | ✅ | Working |
| type (internal/external) | ✅ | 68 internal, external created properly |
| company, client_id | ✅ | External contacts linked to clients |
| role, department | ✅ | Working |
| trust, style, responsiveness | 🔧 | Schema exists, not used |
| reliability_rate | 🔧 | Schema exists, not used |
| last_interaction | ✅ | Updated on item capture |

### Projects

| Field | Status | Notes |
|-------|--------|-------|
| id, name, client_id | ⚠️ | 23% linked + 64% internal |
| status, health | ✅ | From Asana (archived/completed/due/status) |
| dates, value, stakes | ❌ | Not populated |
| milestones, blockers, team | ❌ | Schema only |

### Items

| Field | Status | Notes |
|-------|--------|-------|
| id, what, status | ✅ | Working |
| owner, counterparty | ✅ | Working, warns on internal counterparty |
| owner_id, counterparty_id | ✅ | Both link to Person |
| due, waiting_since | ✅ | Working |
| client_id, project_id | ⚠️ | client works, project rarely linked |
| context_snapshot_json | ✅ | Populated correctly |
| source_type, source_ref | ⚠️ | Basic tracking |
| resolution fields | ✅ | Working |
| item_history | ✅ | Working |

---

## A Protocol

### Creating Items

| Feature | Status | Notes |
|---------|--------|-------|
| Entity resolution | ✅ | Distinguishes internal/external |
| Context snapshot | ✅ | Captures correct context |
| Warn on internal counterparty | ✅ | Shows warning |
| require_context option | ✅ | Can reject without context |
| Link owner_id | ✅ | Links to internal Person |
| Update last_interaction | ✅ | Updates client & person |

### Surfacing Items

| Feature | Status | Notes |
|---------|--------|-------|
| synthesize() method | ✅ | Correct natural language |
| Refresh entity state | ✅ | refresh_context=True |

### Daily Brief

| Feature | Status | Notes |
|---------|--------|-------|
| Overdue items | ✅ | Working |
| Due today | ✅ | Working |
| Due this week | ✅ | Included |
| Waiting items | ✅ | Checked |
| Clients at risk | ✅ | Shows poor/critical |
| Clients to watch | ✅ | Shows fair |
| Projects at risk | ✅ | Shows late/at_risk (6 late found) |

### Queries

| Query | Status | Notes |
|-------|--------|-------|
| status | ✅ | System health |
| stats | ✅ | Summary numbers |
| brief | ✅ | Full daily brief |
| what's overdue | ✅ | Overdue items |
| what's open | ✅ | All open items |
| due today | ✅ | Today's items |
| what about [client] | ✅ | Client summary |
| relationship with [client] | ✅ | Full relationship details |

---

## Contacts

| Feature | Status | Notes |
|---------|--------|-------|
| Create external contact | ✅ | CLI and lib |
| Link to client | ✅ | Updates client.contacts |
| List client contacts | ✅ | Working |
| Find external contact | ✅ | By name or email |
| Contact summary | ✅ | Shows counts |

---

## Data Quality

| Issue | Status | Notes |
|-------|--------|-------|
| Client tiers | ✅ | 2 A, 2 B, rest C |
| AR data | ✅ | 24 clients |
| Project linking | ⚠️ | 87% accounted |
| Project health | ✅ | 6 late projects detected |
| External contacts | ✅ | Model fixed |

---

## Still Missing

### Should Build
1. ❌ annual_value population (needs Xero invoice history)

### Nice to Have
1. Memory mode for DB failure
2. Project milestones/blockers
3. Learning from usage

---

## Current Assessment

**Foundation:** ~95% complete
**Data Quality:** ~80% complete  
**Intelligence:** ~90% complete
**Operations:** ~85% complete

**Overall:** ~85% of designed functionality

The system is now operationally complete for the core use cases. It can:
- Capture items with full context
- Resolve entities (clients, people, projects)
- Generate useful daily briefs
- Track client relationships
- Surface late projects
- Manage external contacts

Main remaining gap is annual_value which would require Xero invoice history integration.
