# 07_VIEWS_AND_QUERY_RECIPES.md — UI-Ready Query Recipes

> Phase E Deliverable | Generated: 2026-02-04

---

## 1. Executive Overview

### 1.1 Dashboard Tiles Query

**Purpose:** Populate the 4 status tiles on the control room

```sql
-- Delivery Tile
SELECT 
    COUNT(*) FILTER (WHERE status = 'active') as active_projects,
    COUNT(*) FILTER (WHERE health = 'red') as red_projects,
    COUNT(*) FILTER (WHERE health = 'yellow') as yellow_projects,
    (SELECT COUNT(*) FROM tasks WHERE status NOT IN ('done','completed') 
     AND due_date < date('now')) as overdue_tasks
FROM projects WHERE status = 'active';

-- Cash Tile
SELECT 
    COALESCE(SUM(amount), 0) as total_ar,
    COALESCE(SUM(amount) FILTER (WHERE aging_bucket IN ('61-90','90+')), 0) as severe_ar,
    COUNT(*) as invoice_count
FROM invoices 
WHERE status IN ('sent','overdue') AND paid_date IS NULL;

-- Clients Tile
SELECT 
    COUNT(*) as total_clients,
    COUNT(*) FILTER (WHERE relationship_health = 'critical') as critical_clients,
    AVG(health_score) as avg_health
FROM clients WHERE tier IN ('A','B');

-- Capacity Tile (placeholder - requires time tracking)
SELECT 
    COUNT(DISTINCT assignee_id) as active_team,
    SUM(duration_min) / 60.0 as total_hours_needed
FROM tasks 
WHERE status NOT IN ('done','completed');
```

**Output Shape:**
```json
{
  "delivery": {"active_projects": 25, "red_projects": 3, "overdue_tasks": 45},
  "cash": {"total_ar": 980642, "severe_ar": 125000, "invoice_count": 34},
  "clients": {"total_clients": 190, "critical_clients": 2, "avg_health": 65.5},
  "capacity": {"active_team": 21, "total_hours_needed": 3668}
}
```

---

## 2. Per-Client Rollup

### 2.1 Client Portfolio Query

**Purpose:** List all clients with key metrics for portfolio view

```sql
SELECT 
    c.id,
    c.name,
    c.tier,
    c.health_score,
    c.relationship_health,
    c.relationship_trend,
    c.financial_ar_outstanding,
    c.financial_ar_aging,
    COUNT(DISTINCT p.id) as project_count,
    COUNT(DISTINCT t.id) as task_count,
    SUM(CASE WHEN t.status NOT IN ('done','completed') 
        AND t.due_date < date('now') THEN 1 ELSE 0 END) as overdue_tasks
FROM clients c
LEFT JOIN projects p ON p.client_id = c.id AND p.status = 'active'
LEFT JOIN tasks t ON t.client_id = c.id
GROUP BY c.id
ORDER BY c.tier, c.health_score DESC;
```

**Performance:** Uses `idx_projects_client`, `idx_tasks_client`

---

### 2.2 Client Detail Query

**Purpose:** Full client profile for drilldown

```sql
-- Basic info
SELECT * FROM clients WHERE id = ?;

-- Projects
SELECT id, name, status, health, deadline, completion_pct 
FROM projects WHERE client_id = ? ORDER BY status, deadline;

-- Recent communications
SELECT id, subject, from_email, received_at, link_status
FROM communications 
WHERE client_id = ? 
ORDER BY received_at DESC LIMIT 20;

-- AR invoices
SELECT id, external_id, amount, due_date, status, aging_bucket
FROM invoices 
WHERE client_id = ? 
ORDER BY due_date;

-- Commitments
SELECT id, text, type, status, deadline
FROM commitments 
WHERE client_id = ? 
ORDER BY deadline;
```

---

## 3. Per-Project Rollup

### 3.1 Project Portfolio Query

**Purpose:** List projects for delivery command heatstrip

```sql
SELECT 
    p.id,
    p.name,
    p.status,
    p.health,
    p.deadline,
    p.is_internal,
    p.completion_pct,
    p.tasks_total,
    p.tasks_done,
    p.owner,
    c.name as client_name,
    c.tier as client_tier,
    b.name as brand_name,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status NOT IN ('done','completed') 
        AND t.due_date < date('now')) as overdue_tasks,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'blocked') as blocked_tasks
FROM projects p
LEFT JOIN clients c ON p.client_id = c.id
LEFT JOIN brands b ON p.brand_id = b.id
LEFT JOIN tasks t ON t.project_id = p.id
WHERE p.status = 'active'
GROUP BY p.id
ORDER BY 
    CASE p.health WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END,
    p.deadline NULLS LAST;
```

**Output Shape:**
```json
{
  "id": "proj_001",
  "name": "GMG Ramadan Campaign",
  "health": "yellow",
  "deadline": "2026-03-15",
  "completion_pct": 45.0,
  "client_name": "GMG Consumer LLC",
  "overdue_tasks": 3,
  "blocked_tasks": 1
}
```

---

### 3.2 Project Detail Query

**Purpose:** Full project profile for room view

```sql
-- Project info
SELECT p.*, c.name as client_name, b.name as brand_name
FROM projects p
LEFT JOIN clients c ON p.client_id = c.id
LEFT JOIN brands b ON p.brand_id = b.id
WHERE p.id = ?;

-- Tasks by status
SELECT 
    status,
    COUNT(*) as count,
    json_group_array(json_object(
        'id', id, 'title', title, 'due_date', due_date, 
        'assignee', assignee_raw, 'priority', priority
    )) as tasks
FROM tasks 
WHERE project_id = ?
GROUP BY status;

-- Critical path (blocked tasks with dependencies)
SELECT id, title, blockers, dependencies
FROM tasks 
WHERE project_id = ? AND (blockers IS NOT NULL OR dependencies IS NOT NULL);
```

---

## 4. AR Rollup

### 4.1 AR Summary Query

**Purpose:** Cash/AR command overview

```sql
SELECT 
    COALESCE(SUM(amount), 0) as total_ar,
    COALESCE(SUM(amount) FILTER (WHERE aging_bucket = 'current'), 0) as current_ar,
    COALESCE(SUM(amount) FILTER (WHERE aging_bucket = '1-30'), 0) as ar_1_30,
    COALESCE(SUM(amount) FILTER (WHERE aging_bucket = '31-60'), 0) as ar_31_60,
    COALESCE(SUM(amount) FILTER (WHERE aging_bucket = '61-90'), 0) as ar_61_90,
    COALESCE(SUM(amount) FILTER (WHERE aging_bucket = '90+'), 0) as ar_90_plus,
    COUNT(*) as invoice_count,
    COUNT(DISTINCT client_id) as debtor_count
FROM invoices 
WHERE status IN ('sent','overdue') AND paid_date IS NULL;
```

---

### 4.2 Debtors Board Query

**Purpose:** List clients with outstanding AR

```sql
SELECT 
    c.id as client_id,
    c.name as client_name,
    c.tier,
    SUM(i.amount) as total_owed,
    MAX(CASE 
        WHEN i.aging_bucket = '90+' THEN 4
        WHEN i.aging_bucket = '61-90' THEN 3
        WHEN i.aging_bucket = '31-60' THEN 2
        WHEN i.aging_bucket = '1-30' THEN 1
        ELSE 0
    END) as worst_bucket,
    COUNT(*) as invoice_count,
    MAX(julianday('now') - julianday(i.due_date)) as max_days_overdue
FROM invoices i
JOIN clients c ON i.client_id = c.id
WHERE i.status IN ('sent','overdue') AND i.paid_date IS NULL
GROUP BY c.id
ORDER BY worst_bucket DESC, total_owed DESC
LIMIT 25;
```

---

## 5. Communications Rollup

### 5.1 Inbox Summary Query

**Purpose:** Comms command thread console

```sql
SELECT 
    id,
    subject,
    from_email,
    from_name,
    received_at,
    snippet,
    client_id,
    link_status,
    is_unread,
    is_starred,
    requires_response,
    ROUND((julianday('now') - julianday(received_at)) * 24, 1) as age_hours
FROM communications
WHERE received_at > datetime('now', '-30 days')
ORDER BY 
    is_unread DESC,
    requires_response DESC,
    received_at DESC
LIMIT 50;
```

---

### 5.2 Thread by Client Query

**Purpose:** Client-filtered communications

```sql
SELECT 
    id, subject, from_email, received_at, snippet, is_unread
FROM communications
WHERE client_id = ?
ORDER BY received_at DESC
LIMIT 30;
```

---

## 6. Capacity Rollup

### 6.1 Lane Capacity Query

**Purpose:** Capacity command lane summary

```sql
SELECT 
    l.id as lane_id,
    l.name as lane_name,
    l.weekly_hours,
    COUNT(t.id) as task_count,
    SUM(t.duration_min) / 60.0 as hours_needed,
    l.weekly_hours - (SUM(t.duration_min) / 60.0) as hours_gap
FROM capacity_lanes l
LEFT JOIN tasks t ON t.lane = l.name 
    AND t.status NOT IN ('done','completed')
GROUP BY l.id
ORDER BY hours_gap;
```

---

### 6.2 Person Load Query

**Purpose:** Team member workload

```sql
SELECT 
    tm.id,
    tm.name,
    tm.default_lane,
    COUNT(t.id) as task_count,
    SUM(t.duration_min) / 60.0 as hours_assigned,
    SUM(CASE WHEN t.due_date < date('now') THEN 1 ELSE 0 END) as overdue_count
FROM team_members tm
LEFT JOIN tasks t ON t.assignee_id = tm.id 
    AND t.status NOT IN ('done','completed')
GROUP BY tm.id
ORDER BY hours_assigned DESC;
```

---

## 7. Resolution Queue Rollup

### 7.1 Queue Summary Query

**Purpose:** Resolution queue overview

```sql
SELECT 
    entity_type,
    issue_type,
    priority,
    COUNT(*) as count
FROM resolution_queue
WHERE resolved_at IS NULL
GROUP BY entity_type, issue_type, priority
ORDER BY priority, count DESC;
```

---

### 7.2 Queue Items Query

**Purpose:** List queue items for triage

```sql
SELECT 
    rq.id,
    rq.entity_type,
    rq.entity_id,
    rq.issue_type,
    rq.priority,
    rq.context,
    rq.created_at,
    CASE rq.entity_type
        WHEN 'task' THEN (SELECT title FROM tasks WHERE id = rq.entity_id)
        WHEN 'project' THEN (SELECT name FROM projects WHERE id = rq.entity_id)
        WHEN 'client' THEN (SELECT name FROM clients WHERE id = rq.entity_id)
        ELSE NULL
    END as entity_name
FROM resolution_queue rq
WHERE rq.resolved_at IS NULL
ORDER BY rq.priority, rq.created_at
LIMIT 50;
```

---

## 8. Pending Actions Rollup

### 8.1 Pending Actions Query

**Purpose:** List actions awaiting approval

```sql
SELECT 
    id,
    action_type,
    entity_type,
    entity_id,
    payload,
    risk_level,
    approval_mode,
    status,
    proposed_at,
    expires_at
FROM pending_actions
WHERE status = 'pending'
ORDER BY 
    CASE risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
    proposed_at;
```

---

## 9. Timeline / Time Series

### 9.1 Calendar Events Query

**Purpose:** Calendar view

```sql
SELECT 
    id,
    title,
    start_time,
    end_time,
    location,
    status,
    has_conflict,
    prep_notes
FROM events
WHERE date(start_time) BETWEEN date('now', '-7 days') AND date('now', '+30 days')
ORDER BY start_time;
```

---

### 9.2 Task Timeline Query

**Purpose:** Task due date timeline

```sql
SELECT 
    date(due_date) as due_day,
    COUNT(*) as task_count,
    SUM(duration_min) as total_minutes,
    json_group_array(json_object('id', id, 'title', title, 'priority', priority)) as tasks
FROM tasks
WHERE status NOT IN ('done','completed')
    AND due_date IS NOT NULL
    AND date(due_date) BETWEEN date('now') AND date('now', '+14 days')
GROUP BY date(due_date)
ORDER BY due_day;
```

---

### 9.3 Client Health History Query

**Purpose:** Health trend chart

```sql
SELECT 
    date(computed_at) as day,
    AVG(health_score) as avg_health,
    COUNT(DISTINCT client_id) as clients_tracked
FROM client_health_log
WHERE computed_at > datetime('now', '-30 days')
GROUP BY date(computed_at)
ORDER BY day;
```

---

## 10. Sync State Query

**Purpose:** Data freshness indicators

```sql
SELECT 
    source,
    last_sync,
    last_success,
    items_synced,
    error,
    ROUND((julianday('now') - julianday(last_sync)) * 24 * 60, 1) as minutes_ago
FROM sync_state
ORDER BY last_sync DESC;
```

---

*End of 07_VIEWS_AND_QUERY_RECIPES.md*
