# Relationship Gap Analysis — 2026-02-13

## Summary
- HIGH priority gaps: 4
- MEDIUM priority gaps: 3
- RESOLVABLE-NOW: 5
- NEEDS-LOOKUP-TABLE: 0 (entity_links already exists)
- NEEDS-ENRICHMENT: 2
- STRUCTURAL: 0

## Data Model Overview

The system uses a **three-tier relationship model**:

1. **Direct FK** — `table.entity_id = entity.id` (fast, reliable)
2. **Artifact-mediated** — `source → artifacts → entity_links → entity` (requires joins)
3. **Implicit** — email/name matching (unreliable, needs normalization)

**Key Tables:**
- `artifacts` (4,070 rows): Extracted items from Gmail, Asana, Calendar
- `entity_links` (30,129 rows): Junction table linking artifacts to entities

## Direct FK Coverage (Tested)

| Relationship | Join | Matches | Coverage | Status |
|--------------|------|---------|----------|--------|
| Invoice → Client | `invoices.client_id = clients.id` | 1,254 / 1,254 | 100% | ✅ COMPLETE |
| Project → Client | `projects.client_id = clients.id` | 354 / 354 | 100% | ✅ COMPLETE |
| Task → Project | `tasks.project_id = projects.id` | 2,474 / 3,946 | 63% | ⚠️ PARTIAL |
| Task → Client | `tasks.client_id = clients.id` | 202 / 3,946 | 5% | ❌ SPARSE |
| Person → Client | `people.client_id = clients.id` | 1 / 71 | 1.4% | ❌ SPARSE |
| Inbox → Client | `inbox_items_v29.client_id = clients.id` | 0 / 121 | 0% | ❌ MISSING |

## RESOLVABLE-NOW (can implement in Task 2.3)

### 1. Task → Client (via Project)
**Current:** 5% direct FK coverage
**Resolution:** Join through Project

```sql
SELECT t.*, c.id as client_id, c.name as client_name
FROM tasks t
JOIN projects p ON t.project_id = p.id
JOIN clients c ON p.client_id = c.id;
```

**Tested Result:** 2,474 tasks can be linked to clients via project
**Match Rate:** 63% (up from 5%)

### 2. Inbox → Client (via entity_links chain)
**Current:** 0% direct FK coverage
**Resolution:** Join through artifacts → entity_links

```sql
SELECT i.*, c.id as client_id, c.name as client_name
FROM inbox_items_v29 i
JOIN artifacts a ON (
  a.source = 'inbox' AND a.source_id = i.id
  OR i.evidence LIKE '%' || a.artifact_id || '%'
)
JOIN entity_links el ON el.from_artifact_id = a.artifact_id
JOIN clients c ON el.to_entity_id = c.id
WHERE el.to_entity_type = 'client';
```

**Note:** Requires testing — inbox may link through issue → evidence → artifact chain

### 3. Person → Communications (Gmail, Chat, Calendar)
**Current:** Implicit email matching only
**Resolution:** Use `people.email` join

```sql
-- Person → Gmail
SELECT p.*, g.id as gmail_id, g.subject
FROM people p
JOIN gmail_messages g ON g.sender = p.email OR g.recipients LIKE '%' || p.email || '%';

-- Person → Calendar  
SELECT p.*, ce.id as event_id, ce.summary
FROM people p
JOIN calendar_events ce ON ce.attendees LIKE '%' || p.email || '%';
```

**Match Rate:** Depends on email normalization (untested)

### 4. Chat → Client (via entity_links)
**Current:** No direct path
**Resolution:** Join through artifacts

```sql
SELECT cm.*, c.id as client_id
FROM chat_messages cm
JOIN artifacts a ON a.source = 'gchat' AND a.source_id = cm.id
JOIN entity_links el ON el.from_artifact_id = a.artifact_id
JOIN clients c ON el.to_entity_id = c.id
WHERE el.to_entity_type = 'client';
```

**entity_links coverage:** 11,756 message artifacts linked to clients

### 5. Calendar → Client (via entity_links)
**Current:** No direct path
**Resolution:** Join through artifacts

```sql
SELECT ce.*, c.id as client_id
FROM calendar_events ce
JOIN artifacts a ON a.source = 'calendar' AND a.source_id = ce.id
JOIN entity_links el ON el.from_artifact_id = a.artifact_id
JOIN clients c ON el.to_entity_id = c.id
WHERE el.to_entity_type = 'client';
```

**entity_links coverage:** 72 calendar artifacts linked to clients

## NEEDS-ENRICHMENT (future work)

### 1. Task → Client (direct FK backfill)
**Current:** 5% of tasks have `client_id`
**Data Needed:** Populate `tasks.client_id` from `projects.client_id`
**Resolution:**
```sql
UPDATE tasks SET client_id = (
  SELECT p.client_id FROM projects p WHERE p.id = tasks.project_id
) WHERE project_id IS NOT NULL AND client_id IS NULL;
```
**Effort:** LOW — simple SQL update, ~2,200 rows affected

### 2. Person → Client (direct FK backfill)
**Current:** 1.4% of people have `client_id`
**Data Needed:** Link people to clients via organization/domain
**Resolution:** Requires collector enhancement to capture client affiliation
**Effort:** MEDIUM — needs business logic for client-person association

## entity_links Distribution

| to_entity_type | Count | % of Total |
|----------------|-------|------------|
| client | 12,985 | 43% |
| person | 9,722 | 32% |
| task | 4,481 | 15% |
| thread | 2,318 | 8% |
| project | 623 | 2% |

**Key Finding:** entity_links is heavily weighted toward client and person links, making it the primary cross-entity bridge.

## Implementation Order

1. **Create Task → Client view** (via project) — unlocks 63% task-client queries
2. **Create Communication → Client view** (via entity_links) — unlocks message/calendar attribution
3. **Backfill tasks.client_id** — improve direct FK coverage
4. **Create Person → Communication view** — enable people-based queries
5. **Consider Person → Client backfill** — requires business rules

## Key Findings

### What Works Well
- **Invoice-Client and Project-Client** relationships are 100% complete
- **entity_links** provides 30K cross-references, heavily client-focused
- **Artifact model** normalizes heterogeneous sources (Gmail, Chat, Calendar)

### What Needs Work
- **Task-Client** direct FK is only 5% populated (but 63% reachable via project)
- **Person-Client** almost entirely unpopulated (1.4%)
- **Inbox-Client** has no direct FK and unclear artifact chain

### Recommended Views for Task 2.3
1. `v_task_with_client` — Task + Project + Client
2. `v_communication_client_link` — Messages/Events → entity_links → Client
3. `v_person_communications` — Person → Gmail/Chat/Calendar via email
