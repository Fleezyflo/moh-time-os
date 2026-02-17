# Cross-Entity Views — 2026-02-13

## Summary
- Views created: 6
- Bridging tables created: 0 (entity_links already provides junction)
- New tests: 25
- Test count: 297 → 322

## Views Created

| View | Purpose | Entities Joined | Row Count | Key Computed Fields |
|------|---------|----------------|-----------|-------------------|
| `v_task_with_client` | Task with client via project | Task → Project → Client | 3,946 | client_id, client_name |
| `v_client_operational_profile` | Client with operational metrics | Client + subqueries | 160 | project_count, total_tasks, total_invoiced |
| `v_project_operational_state` | Project with task metrics | Project → Client + Tasks | 354 | completion_rate_pct, overdue_tasks |
| `v_person_load_profile` | Person with workload metrics | Person + Tasks | 71 | assigned_tasks, active_tasks, project_count |
| `v_communication_client_link` | Communications linked to clients | Artifacts → entity_links → Client | 12,961 | artifact_type, confidence |
| `v_invoice_client_project` | Invoices with client context | Invoice → Client + subqueries | 1,254 | client_active_tasks |

## View Definitions

### v_task_with_client
Joins tasks to clients via projects, using COALESCE to prefer direct client_id when available.

```sql
CREATE VIEW v_task_with_client AS
SELECT
    t.id as task_id,
    t.title as task_title,
    t.status as task_status,
    t.priority as task_priority,
    t.due_date,
    t.assignee,
    t.project_id,
    p.name as project_name,
    COALESCE(t.client_id, p.client_id) as client_id,
    c.name as client_name
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
LEFT JOIN clients c ON COALESCE(t.client_id, p.client_id) = c.id;
```

### v_client_operational_profile
Aggregates operational metrics for each client using subqueries.

```sql
CREATE VIEW v_client_operational_profile AS
SELECT
    c.id as client_id,
    c.name as client_name,
    c.tier as client_tier,
    c.relationship_health,
    (SELECT COUNT(*) FROM projects p WHERE p.client_id = c.id) as project_count,
    (SELECT COUNT(*) FROM tasks t JOIN projects p ON t.project_id = p.id
     WHERE p.client_id = c.id) as total_tasks,
    (SELECT COUNT(*) FROM tasks t JOIN projects p ON t.project_id = p.id
     WHERE p.client_id = c.id AND t.status NOT IN ('done', 'complete', 'completed')) as active_tasks,
    (SELECT COUNT(*) FROM invoices i WHERE i.client_id = c.id) as invoice_count,
    (SELECT COALESCE(SUM(i.amount), 0) FROM invoices i WHERE i.client_id = c.id) as total_invoiced,
    (SELECT COALESCE(SUM(i.amount), 0) FROM invoices i WHERE i.client_id = c.id AND i.status = 'paid') as total_paid,
    (SELECT COALESCE(SUM(i.amount), 0) FROM invoices i WHERE i.client_id = c.id AND i.status != 'paid') as total_outstanding,
    c.financial_ar_total,
    c.financial_ar_overdue,
    c.ytd_revenue,
    (SELECT COUNT(*) FROM entity_links el WHERE el.to_entity_type = 'client' AND el.to_entity_id = c.id) as entity_links_count
FROM clients c;
```

### v_project_operational_state
Project with task metrics and computed completion rate.

```sql
CREATE VIEW v_project_operational_state AS
SELECT
    p.id as project_id,
    p.name as project_name,
    p.status as project_status,
    p.client_id,
    c.name as client_name,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) as total_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
     AND t.status NOT IN ('done', 'complete', 'completed')) as open_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
     AND t.status IN ('done', 'complete', 'completed')) as completed_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
     AND t.due_date IS NOT NULL AND t.due_date < date('now')
     AND t.status NOT IN ('done', 'complete', 'completed')) as overdue_tasks,
    (SELECT COUNT(DISTINCT t.assignee) FROM tasks t
     WHERE t.project_id = p.id AND t.assignee IS NOT NULL) as assigned_people_count,
    CASE
        WHEN (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) = 0 THEN 0
        ELSE ROUND(100.0 * (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
             AND t.status IN ('done', 'complete', 'completed')) /
             (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id), 1)
    END as completion_rate_pct
FROM projects p
LEFT JOIN clients c ON p.client_id = c.id;
```

### v_person_load_profile
Person with task load metrics, joining on name (since assignee_id is unpopulated).

```sql
CREATE VIEW v_person_load_profile AS
SELECT
    ppl.id as person_id,
    ppl.name as person_name,
    ppl.email as person_email,
    ppl.role,
    (SELECT COUNT(*) FROM tasks t WHERE LOWER(t.assignee) = LOWER(ppl.name)) as assigned_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE LOWER(t.assignee) = LOWER(ppl.name)
     AND t.status NOT IN ('done', 'complete', 'completed')) as active_tasks,
    (SELECT COUNT(DISTINCT t.project_id) FROM tasks t
     WHERE LOWER(t.assignee) = LOWER(ppl.name)) as project_count,
    (SELECT COUNT(*) FROM entity_links el
     WHERE el.to_entity_type = 'person' AND el.to_entity_id = ppl.id) as communication_links
FROM people ppl;
```

### v_communication_client_link
Links artifacts (messages, calendar events) to clients via entity_links.

```sql
CREATE VIEW v_communication_client_link AS
SELECT
    a.artifact_id,
    a.type as artifact_type,
    a.source as source_system,
    a.occurred_at,
    el.to_entity_id as client_id,
    c.name as client_name,
    el.confidence,
    el.method as link_method
FROM artifacts a
JOIN entity_links el ON el.from_artifact_id = a.artifact_id
JOIN clients c ON el.to_entity_id = c.id
WHERE el.to_entity_type = 'client';
```

### v_invoice_client_project
Invoice with client context and project/task counts.

```sql
CREATE VIEW v_invoice_client_project AS
SELECT
    i.id as invoice_id,
    i.external_id,
    i.client_id,
    c.name as client_name,
    i.amount,
    i.currency,
    i.status as invoice_status,
    i.issue_date,
    i.due_date,
    i.aging_bucket,
    (SELECT COUNT(*) FROM projects p WHERE p.client_id = i.client_id) as client_project_count,
    (SELECT COUNT(*) FROM tasks t JOIN projects p ON t.project_id = p.id
     WHERE p.client_id = i.client_id
     AND t.status NOT IN ('done', 'complete', 'completed')) as client_active_tasks
FROM invoices i
LEFT JOIN clients c ON i.client_id = c.id;
```

## Test Coverage

| View | Tests | Status |
|------|-------|--------|
| v_task_with_client | 3 | ✅ |
| v_client_operational_profile | 3 | ✅ |
| v_project_operational_state | 3 | ✅ |
| v_person_load_profile | 2 | ✅ |
| v_communication_client_link | 3 | ✅ |
| v_invoice_client_project | 3 | ✅ |
| Views exist | 7 | ✅ |
| Cross-view integration | 1 | ✅ |
| **Total** | **25** | ✅ |

## Usage Examples

### Get client operational overview
```sql
SELECT
    client_name,
    project_count,
    total_tasks,
    active_tasks,
    total_invoiced,
    total_outstanding
FROM v_client_operational_profile
WHERE project_count > 0
ORDER BY total_tasks DESC
LIMIT 10;
```

### Find overloaded team members
```sql
SELECT
    person_name,
    assigned_tasks,
    active_tasks,
    project_count
FROM v_person_load_profile
WHERE active_tasks > 10
ORDER BY active_tasks DESC;
```

### Client communication intensity
```sql
SELECT
    client_name,
    artifact_type,
    COUNT(*) as message_count
FROM v_communication_client_link
GROUP BY client_id, artifact_type
ORDER BY message_count DESC
LIMIT 20;
```

### Projects at risk (high overdue ratio)
```sql
SELECT
    project_name,
    client_name,
    total_tasks,
    overdue_tasks,
    completion_rate_pct
FROM v_project_operational_state
WHERE overdue_tasks > 0
ORDER BY overdue_tasks DESC;
```
