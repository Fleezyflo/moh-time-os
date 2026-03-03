# Time OS Master Engineering Specification

**Version:** 4.11 LOCKED
**Date:** 2026-02-03
**Status:** 🔒 LOCKED — NO SPEC CHANGES WITHOUT EXPLICIT APPROVAL
**Author:** A (for Moh)

---

## Table of Contents

1. [Canonical Data Model](#1-canonical-data-model)
2. [ID Strategy & Dedupe Rules](#2-id-strategy--dedupe-rules)
3. [Link Status & Chain Validity](#3-link-status--chain-validity)
4. [Derivation Authority](#4-derivation-authority)
5. [Resolution Queue](#5-resolution-queue)
6. [Gates & Blocking](#6-gates--blocking)
7. [Governance & Risk Model](#7-governance--risk-model)
8. [Collectors](#8-collectors)
9. [Truth Modules](#9-truth-modules)
10. [Finance Truth & AR](#10-finance-truth--ar)
11. [Orchestration](#11-orchestration)
12. [Schema Definitions](#12-schema-definitions)
13. [Implementation Sequence](#13-implementation-sequence)
14. [Validation & Acceptance](#14-validation--acceptance)

---

## 1. Canonical Data Model

### 1.1 Entity Hierarchy (Authoritative)

```
Client (required root)
    └── Brand (required for all client work)
          └── Project/Retainer (required, belongs to exactly one brand)
                └── Task (belongs to a project when linked)
```

**Hierarchy Rules:**

| Level | Cardinality | Nullability | Notes |
|-------|-------------|-------------|-------|
| Client | 1 | Root entity | Every linked entity traces to a client |
| Brand | 1..N per client | **Required** for non-internal projects | Manual assignment only |
| Project | 1..N per brand | Required for linking | Internal projects may optionally have brand |
| Task | N per project | Project optional | Unlinked tasks have no project |

**Key Constraints:**

- **Brand is REQUIRED** for all non-internal projects. `projects.brand_id NOT NULL` when `projects.is_internal = 0`.
- **Internal projects** (`projects.is_internal = 1`) may optionally have `brand_id` (e.g., internal initiative sponsored by a brand).
- **Brand assignment is manual-only.** No inference from project names or other heuristics.
- **projects.client_id is DERIVED** from `brands.client_id` via `projects.brand_id`. Internal projects have `client_id = NULL` regardless of brand_id.
- **tasks.is_internal does not exist.** Internal status is determined solely by `projects.is_internal`.

**Retainer Clarification:** Retainers are `projects.type = 'retainer'`. No separate entity. All project logic applies equally.

### 1.2 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│    ┌──────────────┐                                                         │
│    │   clients    │                                                         │
│    │──────────────│                                                         │
│    │ id (slug) PK │◄──────────────────────────────────────────────┐        │
│    │ name         │                                                │        │
│    │ tier         │                                                │        │
│    │ health_score │                                                │        │
│    └──────┬───────┘                                                │        │
│           │                                                        │        │
│           │ 1:N (required)                                         │        │
│           ▼                                                        │        │
│    ┌──────────────┐         ┌──────────────────┐                  │        │
│    │   brands     │         │ client_identities │                  │        │
│    │──────────────│         │──────────────────│                  │        │
│    │ id PK        │         │ id PK            │                  │        │
│    │ client_id FK─┼────┬───►│ client_id FK     │──────────────────┤        │
│    │ name         │    │    │ identity_type    │ ('email'|'domain')        │
│    └──────┬───────┘    │    │ identity_value   │                  │        │
│           │            │    └──────────────────┘                  │        │
│           │ 1:N        │                                          │        │
│           ▼            │                                          │        │
│    ┌──────────────┐    │                                          │        │
│    │  projects    │    │                                          │        │
│    │──────────────│    │                                          │        │
│    │ id (slug) PK │◄───┼─────────────────────┐                    │        │
│    │ brand_id FK──┼────┘ (NOT NULL if !internal)                  │        │
│    │ client_id    │ (DERIVED, NULL if internal)                   │        │
│    │ is_internal  │ (0=client, 1=internal)   │                    │        │
│    │ name         │                          │                    │        │
│    │ type         │ ('project'|'retainer')   │                    │        │
│    └──────┬───────┘                          │                    │        │
│           │                                  │                    │        │
│           │ 1:N                              │                    │        │
│           ▼                                  │                    │        │
│    ┌─────────────────────────────────────────┼─────────────────────────────┤
│    │                    tasks                │                             │
│    │─────────────────────────────────────────┼─────────────────────────────│
│    │ id PK (source_gid)                      │                             │
│    │ project_id FK ──────────────────────────┘                             │
│    │ client_id (DERIVED from project→brand→client)                         │
│    │ brand_id (DERIVED from project→brand)                                 │
│    │ assignee_id FK ──────────────────────────────────► team_members.id    │
│    │ project_link_status ('linked'|'partial'|'unlinked')                   │
│    │ client_link_status ('linked'|'unlinked'|'n/a')                        │
│    │ (NO is_internal column - derived from project)                        │
│    └───────────────────────────────────────────────────────────────────────┘
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Derivation Rules

**Project Derivation:**

```
IF project.is_internal = 1:
    project.client_id := NULL  -- always, regardless of brand_id
    -- brand_id is UNCHANGED (may be NULL or set to a sponsoring brand)
ELSE:
    project.client_id := brands.client_id WHERE brands.id = project.brand_id
```

**Task Derivation (strict order):**

```
-- Two separate status fields:
-- project_link_status: is the task linked to a valid, work-ready project?
-- client_link_status: is the full client chain valid?

IF task.project_id IS NULL:
    task.brand_id := NULL
    task.client_id := NULL
    task.project_link_status := 'unlinked'
    task.client_link_status := 'unlinked'
ELSE:
    project = lookup(projects, task.project_id)
    IF project NOT EXISTS:
        task.brand_id := NULL
        task.client_id := NULL
        task.project_link_status := 'partial'  -- project_id set but project missing
        task.client_link_status := 'unlinked'
    ELSE IF project.is_internal = 1:
        -- Internal project: fully linked for project purposes, no client chain
        task.brand_id := project.brand_id  -- may be NULL
        task.client_id := NULL
        task.project_link_status := 'linked'
        task.client_link_status := 'n/a'  -- not applicable for internal
    ELSE:
        -- Non-internal project: need full chain for linked status
        task.brand_id := project.brand_id
        IF project.brand_id IS NULL:
            task.client_id := NULL
            task.project_link_status := 'partial'
            task.client_link_status := 'unlinked'
        ELSE:
            brand = lookup(brands, project.brand_id)
            IF brand NOT EXISTS:
                task.client_id := NULL
                task.project_link_status := 'partial'
                task.client_link_status := 'unlinked'
            ELSE IF brand.client_id IS NULL:
                task.client_id := NULL
                task.project_link_status := 'partial'
                task.client_link_status := 'unlinked'
            ELSE:
                client = lookup(clients, brand.client_id)
                IF client NOT EXISTS:
                    task.client_id := brand.client_id  -- stale reference
                    task.project_link_status := 'partial'
                    task.client_link_status := 'unlinked'
                ELSE:
                    -- Full chain valid
                    task.client_id := brand.client_id
                    task.project_link_status := 'linked'
                    task.client_link_status := 'linked'
```

**Communication Derivation:** [unchanged from v4.2]

---

## 2. ID Strategy & Dedupe Rules

[Unchanged from v4.2]

### 2.4 Store Contract

**`store.query(sql, params)` behavior:**
- Returns list of dict-like rows (sqlite3.Row or dict)
- Access columns by name: `row['column_name']`
- All COUNT queries use `AS c` alias for consistency

**`store.insert(table, data)` behavior:**
- Inserts only the columns provided in `data` dict
- DB defaults apply for unspecified columns (e.g., `id`, `created_at`)
- Does NOT insert NULL for missing keys

**Date normalization:**
- All date columns (due_date, issue_date, etc.) stored as ISO format: `YYYY-MM-DD`
- Timestamps stored as ISO 8601: `YYYY-MM-DDTHH:MM:SS`
- Empty strings are invalid; use NULL for missing dates
- Collectors must normalize dates at ingestion

---

## 3. Link Status & Chain Validity

### 3.1 Two-Dimensional Link Status

Tasks have **two separate status fields** to avoid semantic overloading:

| Field | Values | Meaning |
|-------|--------|---------|
| `project_link_status` | `linked`, `partial`, `unlinked` | Is the task linked to a valid, work-ready project? |
| `client_link_status` | `linked`, `unlinked`, `n/a` | Is the full client chain valid? |

### 3.2 Status Definitions (Authoritative)

**project_link_status:**

| Status | Definition | Conditions |
|--------|------------|------------|
| `linked` | Project exists AND is work-ready | `project_id NOT NULL` AND project exists AND (internal OR non-internal with full brand→client chain) |
| `partial` | Project mapping attempted but broken | `project_id NOT NULL` AND (project missing OR non-internal project with broken brand/client chain) |
| `unlinked` | No project mapping | `project_id IS NULL` |

**Key insight:** `linked` means "this task can be used for truth calculations for its project type." For internal projects, that's just having a valid project. For non-internal, the full chain must resolve.

**client_link_status:**

| Status | Definition | Conditions |
|--------|------------|------------|
| `linked` | Full client chain valid | Non-internal project AND brand exists AND client exists AND all FKs valid |
| `unlinked` | No client chain | `project_id IS NULL` OR chain is broken |
| `n/a` | Not applicable | Internal project (client chain not expected) |

### 3.3 Coverage Queries

**Canonical pattern:** Use `100.0 * SUM(...) / NULLIF(SUM(...), 0)` to:
- Force float division (100.0)
- Make numerator/denominator explicit
- Guard against division by zero

**Client coverage** (for client truth):
```sql
SELECT COALESCE(
    100.0 * SUM(CASE WHEN client_link_status = 'linked' THEN 1 ELSE 0 END) /
    NULLIF(SUM(CASE WHEN client_link_status != 'n/a' THEN 1 ELSE 0 END), 0),
    100.0
) AS pct
FROM tasks;
```

**Project coverage** (for project-level reporting):
```sql
SELECT COALESCE(
    100.0 * SUM(CASE WHEN project_link_status = 'linked' THEN 1 ELSE 0 END) /
    NULLIF(COUNT(*), 0),
    100.0
) AS pct
FROM tasks;
```

### 3.4 Invariants (All Enforced by data_integrity Gate)

The `data_integrity` gate checks ALL of the following. If any fail (c > 0), the gate fails.

**All queries use `COUNT(*) AS c` pattern for consistency with `_query_zero()`.**

```sql
-- Invariant 1: linked requires project exists AND work-ready
-- For non-internal: full chain must be resolvable
-- For internal: just project must exist
-- Pass condition: c = 0
SELECT COUNT(*) AS c FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
LEFT JOIN brands b ON p.brand_id = b.id
LEFT JOIN clients c ON b.client_id = c.id
WHERE t.project_link_status = 'linked'
AND (
    t.project_id IS NULL
    OR p.id IS NULL
    OR (COALESCE(p.is_internal, 0) = 0 AND (
        p.brand_id IS NULL OR b.id IS NULL OR b.client_id IS NULL OR c.id IS NULL
    ))
);

-- Invariant 2: unlinked requires project_id NULL
-- Pass condition: c = 0
SELECT COUNT(*) AS c FROM tasks
WHERE project_link_status = 'unlinked' AND project_id IS NOT NULL;

-- Invariant 3: partial requires project_id NOT NULL
-- Pass condition: c = 0
SELECT COUNT(*) AS c FROM tasks
WHERE project_link_status = 'partial' AND project_id IS NULL;

-- Invariant 4: partial must actually be broken (not accidentally resolvable)
-- If chain is fully resolvable for non-internal, it should be linked, not partial
-- Pass condition: c = 0
SELECT COUNT(*) AS c FROM tasks t
JOIN projects p ON t.project_id = p.id
JOIN brands b ON p.brand_id = b.id
JOIN clients c ON b.client_id = c.id
WHERE t.project_link_status = 'partial'
AND p.is_internal = 0
AND p.brand_id IS NOT NULL
AND b.client_id IS NOT NULL
AND c.id IS NOT NULL;

-- Invariant 5: client_link_status='linked' requires complete resolvable chain
-- Pass condition: c = 0
SELECT COUNT(*) AS c FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
LEFT JOIN brands b ON t.brand_id = b.id
LEFT JOIN clients c ON t.client_id = c.id
WHERE t.client_link_status = 'linked'
AND (
    t.client_id IS NULL OR c.id IS NULL OR
    t.brand_id IS NULL OR b.id IS NULL OR
    COALESCE(p.is_internal, 0) = 1
);

-- Invariant 6: client_link_status='n/a' requires internal project
-- Pass condition: c = 0
SELECT COUNT(*) AS c FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
WHERE t.client_link_status = 'n/a'
AND (p.id IS NULL OR COALESCE(p.is_internal, 0) = 0);
```

### 3.5 Communication Link Status

| Status | Definition | Conditions |
|--------|------------|------------|
| `linked` | Client resolved | `client_id IS NOT NULL` AND client exists |
| `unlinked` | No client match | `client_id IS NULL` |

### 3.6 Project Integrity Gates

```sql
-- Gate: project_brand_required
SELECT COUNT(*) AS c FROM projects WHERE is_internal = 0 AND brand_id IS NULL;
-- Pass: c = 0

-- Gate: project_brand_client_consistency
SELECT COUNT(*) AS c FROM projects p
JOIN brands b ON p.brand_id = b.id
WHERE p.is_internal = 0 AND p.client_id != b.client_id;
-- Pass: c = 0

-- Gate: project_client_populated
SELECT COUNT(*) AS c FROM projects WHERE is_internal = 0 AND client_id IS NULL;
-- Pass: c = 0

-- Gate: internal_project_client_null
SELECT COUNT(*) AS c FROM projects WHERE is_internal = 1 AND client_id IS NOT NULL;
-- Pass: c = 0
```

---

## 4. Derivation Authority

### 4.1 Single Source of Truth: Normalizer

```
┌─────────────────────────────────────────────────────────────────┐
│                    DERIVATION AUTHORITY                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Normalizer (lib/normalizer.py):                               │
│    ✓ Writes: projects.client_id (from brand, NULL if internal) │
│    ✓ Writes: tasks.brand_id, client_id                         │
│    ✓ Writes: tasks.project_link_status, client_link_status     │
│    ✓ Writes: communications.from_domain, client_id, link_status│
│    ✓ Writes: invoices.aging_bucket (only for valid AR)         │
│    ✓ Runs: AFTER collect, BEFORE truth modules                 │
│                                                                 │
│  Store Contract:                                                │
│    ✓ store.insert() only inserts provided columns              │
│    ✓ DB defaults apply for unspecified columns                 │
│                                                                 │
│  Note: tasks table has NO is_internal column.                  │
│  Internal status determined solely by projects.is_internal.    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Normalizer Implementation

```python
class Normalizer:
    """Single source of truth for derived columns."""

    def _normalize_tasks(self) -> int:
        """Derive brand_id, client_id, project_link_status, client_link_status."""
        updated = 0

        tasks = self.store.query("""
            SELECT t.id, t.project_id, t.brand_id, t.client_id,
                   t.project_link_status, t.client_link_status,
                   p.id as proj_exists, p.brand_id as proj_brand_id, p.is_internal as proj_internal,
                   b.id as brand_exists, b.client_id as brand_client_id,
                   c.id as client_exists
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN brands b ON p.brand_id = b.id
            LEFT JOIN clients c ON b.client_id = c.id
        """)

        for task in tasks:
            new_brand_id = None
            new_client_id = None
            new_project_link = 'unlinked'
            new_client_link = 'unlinked'

            if task['project_id'] is None:
                new_project_link = 'unlinked'
                new_client_link = 'unlinked'
            elif not task['proj_exists']:
                new_project_link = 'partial'
                new_client_link = 'unlinked'
            elif task['proj_internal']:
                new_brand_id = task['proj_brand_id']
                new_project_link = 'linked'
                new_client_link = 'n/a'
            elif not task['proj_brand_id']:
                new_project_link = 'partial'
                new_client_link = 'unlinked'
            elif not task['brand_exists']:
                new_brand_id = task['proj_brand_id']
                new_project_link = 'partial'
                new_client_link = 'unlinked'
            elif not task['brand_client_id']:
                new_brand_id = task['proj_brand_id']
                new_project_link = 'partial'
                new_client_link = 'unlinked'
            elif not task['client_exists']:
                new_brand_id = task['proj_brand_id']
                new_client_id = task['brand_client_id']
                new_project_link = 'partial'
                new_client_link = 'unlinked'
            else:
                new_brand_id = task['proj_brand_id']
                new_client_id = task['brand_client_id']
                new_project_link = 'linked'
                new_client_link = 'linked'

            if (task['brand_id'] != new_brand_id or
                task['client_id'] != new_client_id or
                task['project_link_status'] != new_project_link or
                task['client_link_status'] != new_client_link):

                self.store.query("""
                    UPDATE tasks
                    SET brand_id = ?, client_id = ?,
                        project_link_status = ?, client_link_status = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                """, [new_brand_id, new_client_id, new_project_link, new_client_link, task['id']])
                updated += 1

        return updated
```

---

## 5. Resolution Queue

### 5.1 Purpose

The Resolution Queue surfaces entities that cannot be automatically linked, enabling manual resolution.

### 5.2 Queue Sources (Precise Conditions)

| Entity | Condition | Priority | Notes |
|--------|-----------|----------|-------|
| Task | `project_link_status = 'unlinked'` | P1 if due < 7d, else P2 | Missing project |
| Task | `project_link_status = 'partial'` | P1 | Broken chain |
| Task | `project_link_status = 'linked' AND client_link_status = 'unlinked'` | P1 | **Sanity alarm** - indicates corruption (should be impossible by construction) |
| Communication | `link_status = 'unlinked'` AND has commitments | P2 | Missing client identity |
| Project | `is_internal = 0 AND brand_id IS NULL` | P1 | Missing brand |
| Invoice | `status IN ('sent','overdue') AND paid_date IS NULL AND due_date IS NULL` | P2 | Missing due date |
| Invoice | `status IN ('sent','overdue') AND paid_date IS NULL AND client_id IS NULL` | P2 | Unlinked finance |

**Note:** The third row (client_link_status unlinked + project_link_status linked) is mutually exclusive with the first two rows, so no double-queuing.

### 5.3 Resolution Actions

| Action | Writes To | Effect |
|--------|-----------|--------|
| Assign Project | `tasks.project_id` | Normalizer derives chain |
| Create Project | `projects`, `tasks.project_id` | Creates + links |
| Fix Brand Link | `projects.brand_id` | Repairs project→brand |
| Create Identity | `client_identities` | Enables future matching |
| Set Due Date | `invoices.due_date` | Enables AR calculation |

### 5.4 Queue Population SQL

```sql
-- Task: project unlinked
-- due_date must be ISO format (YYYY-MM-DD) per Store Contract
INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
SELECT 'task', id, 'project_unlinked',
    CASE
        WHEN due_date IS NOT NULL
         AND date(due_date) IS NOT NULL
         AND date(due_date) < date('now', '+7 days')
        THEN 1 ELSE 2
    END
FROM tasks
WHERE project_link_status = 'unlinked'
AND NOT EXISTS (SELECT 1 FROM resolution_queue
    WHERE entity_type = 'task' AND entity_id = tasks.id
    AND issue_type = 'project_unlinked' AND resolved_at IS NULL);

-- Task: project partial (broken chain)
INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
SELECT 'task', id, 'chain_broken', 1
FROM tasks
WHERE project_link_status = 'partial'
AND NOT EXISTS (SELECT 1 FROM resolution_queue
    WHERE entity_type = 'task' AND entity_id = tasks.id
    AND issue_type = 'chain_broken' AND resolved_at IS NULL);

-- Task: project linked but client unlinked (sanity alarm - should be rare/impossible)
-- For non-internal: project_link_status='linked' implies full chain, so client_link_status='linked'
-- For internal: client_link_status='n/a'
-- If this fires, it indicates drift/corruption in the normalizer
INSERT INTO resolution_queue (entity_type, entity_id, issue_type, priority)
SELECT 'task', id, 'client_unlinked_unexpected', 1  -- P1 because it's corruption
FROM tasks
WHERE project_link_status = 'linked'
AND client_link_status = 'unlinked'
AND NOT EXISTS (SELECT 1 FROM resolution_queue
    WHERE entity_type = 'task' AND entity_id = tasks.id
    AND issue_type = 'client_unlinked_unexpected' AND resolved_at IS NULL);
```

---

## 6. Gates & Blocking

### 6.1 Gate Definitions

| Gate | Query | Pass Condition |
|------|-------|----------------|
| `data_integrity` | All §3.4 invariants | All 6 queries return 0 |
| `project_brand_required` | §3.6 | Returns 0 |
| `project_brand_consistency` | §3.6 | Returns 0 |
| `project_client_populated` | §3.6 | Returns 0 |
| `internal_project_client_null` | §3.6 | Returns 0 |
| `client_coverage` | §6.2 | ≥80% |
| `commitment_ready` | §6.2 | ≥50% |
| `capacity_baseline` | §6.2 | Returns 0 |
| `finance_ar_coverage` | §6.2 | ≥95% |
| `finance_ar_clean` | §6.2 | Returns 0 |

### 6.2 Gate Implementations

```python
def _evaluate_gates(self) -> Dict[str, bool]:
    gates = {}

    # data_integrity: ALL invariants from §3.4 must pass
    gates['data_integrity'] = self._check_data_integrity()

    # project gates (all use AS c for consistent dict access)
    gates['project_brand_required'] = self._query_zero("""
        SELECT COUNT(*) AS c FROM projects WHERE is_internal = 0 AND brand_id IS NULL
    """)
    gates['project_brand_consistency'] = self._query_zero("""
        SELECT COUNT(*) AS c FROM projects p JOIN brands b ON p.brand_id = b.id
        WHERE p.is_internal = 0 AND p.client_id != b.client_id
    """)
    gates['project_client_populated'] = self._query_zero("""
        SELECT COUNT(*) AS c FROM projects WHERE is_internal = 0 AND client_id IS NULL
    """)
    gates['internal_project_client_null'] = self._query_zero("""
        SELECT COUNT(*) AS c FROM projects WHERE is_internal = 1 AND client_id IS NOT NULL
    """)

    # client_coverage: ≥80% of applicable tasks (canonical SUM/CASE pattern)
    coverage = self.store.query("""
        SELECT COALESCE(
            100.0 * SUM(CASE WHEN client_link_status = 'linked' THEN 1 ELSE 0 END) /
            NULLIF(SUM(CASE WHEN client_link_status != 'n/a' THEN 1 ELSE 0 END), 0),
            100.0
        ) AS pct FROM tasks
    """)[0]['pct']
    gates['client_coverage'] = coverage >= 80

    # commitment_ready (canonical SUM/CASE pattern)
    ready = self.store.query("""
        SELECT COALESCE(
            100.0 * SUM(CASE WHEN body_text IS NOT NULL AND LENGTH(body_text) >= 50 THEN 1 ELSE 0 END) /
            NULLIF(COUNT(*), 0),
            100.0
        ) AS pct FROM communications
    """)[0]['pct']
    gates['commitment_ready'] = ready >= 50

    # capacity_baseline
    gates['capacity_baseline'] = self._query_zero("""
        SELECT COUNT(*) AS c FROM capacity_lanes WHERE weekly_hours <= 0
    """)

    # finance_ar_coverage: ≥95% of AR invoices are valid (canonical SUM/CASE pattern)
    ar_coverage = self.store.query("""
        SELECT COALESCE(
            100.0 * SUM(CASE WHEN client_id IS NOT NULL AND due_date IS NOT NULL THEN 1 ELSE 0 END) /
            NULLIF(COUNT(*), 0),
            100.0
        ) AS pct
        FROM invoices
        WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
    """)[0]['pct']
    gates['finance_ar_coverage'] = ar_coverage >= 95

    # finance_ar_clean: ALL AR invoices valid
    gates['finance_ar_clean'] = self._query_zero("""
        SELECT COUNT(*) AS c FROM invoices
        WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
        AND (client_id IS NULL OR due_date IS NULL)
    """)

    return gates

def _check_data_integrity(self) -> bool:
    """Check ALL link status invariants from §3.4."""

    # Invariant 1: linked is valid
    inv1 = self._query_zero("""
        SELECT COUNT(*) AS c FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        LEFT JOIN brands b ON p.brand_id = b.id
        LEFT JOIN clients c ON b.client_id = c.id
        WHERE t.project_link_status = 'linked'
        AND (
            t.project_id IS NULL OR p.id IS NULL OR
            (COALESCE(p.is_internal, 0) = 0 AND (
                p.brand_id IS NULL OR b.id IS NULL OR b.client_id IS NULL OR c.id IS NULL
            ))
        )
    """)

    # Invariant 2: unlinked has NULL project_id
    inv2 = self._query_zero("""
        SELECT COUNT(*) AS c FROM tasks WHERE project_link_status = 'unlinked' AND project_id IS NOT NULL
    """)

    # Invariant 3: partial has NOT NULL project_id
    inv3 = self._query_zero("""
        SELECT COUNT(*) AS c FROM tasks WHERE project_link_status = 'partial' AND project_id IS NULL
    """)

    # Invariant 4: partial is actually broken (not resolvable)
    # If project exists and non-internal chain is complete, should be linked not partial
    # Make all conditions explicit for clarity (some implied by joins, but explicit is safer)
    inv4 = self._query_zero("""
        SELECT COUNT(*) AS c FROM tasks t
        JOIN projects p ON t.project_id = p.id
        JOIN brands b ON p.brand_id = b.id
        JOIN clients c ON b.client_id = c.id
        WHERE t.project_link_status = 'partial'
        AND p.is_internal = 0
        AND p.brand_id IS NOT NULL
        AND b.client_id IS NOT NULL
        AND c.id IS NOT NULL
    """)

    # Invariant 5: client_link_status='linked' has complete chain
    inv5 = self._query_zero("""
        SELECT COUNT(*) AS c FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        LEFT JOIN brands b ON t.brand_id = b.id
        LEFT JOIN clients c ON t.client_id = c.id
        WHERE t.client_link_status = 'linked'
        AND (t.client_id IS NULL OR c.id IS NULL OR t.brand_id IS NULL OR b.id IS NULL
             OR COALESCE(p.is_internal, 0) = 1)
    """)

    # Invariant 6: client_link_status='n/a' requires internal project
    inv6 = self._query_zero("""
        SELECT COUNT(*) AS c FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.client_link_status = 'n/a'
        AND (p.id IS NULL OR COALESCE(p.is_internal, 0) = 0)
    """)

    return inv1 and inv2 and inv3 and inv4 and inv5 and inv6

def _query_zero(self, sql: str) -> bool:
    """Check if query returns zero. Uses aliased column 'c' for consistency."""
    row = self.store.query(sql)[0]
    try:
        return row['c'] == 0
    except (TypeError, KeyError, IndexError):
        # Fallback for tuple rows (shouldn't happen per Store Contract)
        return row[0] == 0
```

### 6.3 Gate-to-Capability Blocking

| Gate | On Failure | Behavior |
|------|------------|----------|
| `data_integrity` | **BLOCK** | Skip analyze/surface/reason/execute |
| `project_brand_required` | **BLOCK** | Skip all truth modules |
| `project_brand_consistency` | **BLOCK** | Skip all truth modules |
| `project_client_populated` | **BLOCK** | Skip client truth |
| `internal_project_client_null` | WARN | Log, continue |
| `client_coverage` | DEGRADE | Runs flagged, no external actions |
| `commitment_ready` | DEGRADE | Runs, results flagged |
| `capacity_baseline` | SKIP | Skip capacity truth |
| `finance_ar_coverage` | DEGRADE | Include finance, exclude invalid |
| `finance_ar_clean` | INFO | Log count, continue |

---

## 7. Governance & Risk Model

[Unchanged from v4.2]

---

## 8. Collectors

### 8.1 Asana Collector

```python
class AsanaCollector(BaseCollector):

    def transform(self, raw: Dict) -> List[Dict]:
        results = []

        for task in raw.get('data', []):
            results.append({
                'id': f"asana_{task['gid']}",
                'source': 'asana',
                'project_id': project_id,
                'assignee_id': assignee_id,
                'assignee_raw': assignee_name,
                'project_link_status': 'unlinked',  # Normalizer updates
                'client_link_status': 'unlinked',   # Normalizer updates
                # NO is_internal field - determined by project
                ...
            })

        return results
```

### 8.2 Gmail Collector

[Unchanged from v4.2]

---

## 9. Truth Modules

### 9.1 Commitment Truth

[Unchanged from v4.2]

### 9.2 Client Truth

```python
class HealthCalculator:

    def compute_health(self, client_id: str, include_finance: bool = False) -> Dict:
        # Query tasks WHERE client_link_status = 'linked' AND client_id = ?
        # This automatically excludes:
        # - Internal tasks (client_link_status='n/a')
        # - Unlinked tasks (client_link_status='unlinked')
        ...

    def _get_ar_health(self, client_id: str) -> float:
        """
        Calculate AR health. Only count VALID AR invoices:
        - status IN ('sent', 'overdue')
        - paid_date IS NULL
        - due_date IS NOT NULL (not just aging_bucket IS NOT NULL)
        - client_id matches
        """
        result = self.store.query("""
            SELECT
                SUM(CASE WHEN aging_bucket = 'current' THEN amount ELSE 0 END) as current_amt,
                SUM(CASE WHEN aging_bucket IN ('1-30', '31-60') THEN amount ELSE 0 END) as moderate_amt,
                SUM(CASE WHEN aging_bucket IN ('61-90', '90+') THEN amount ELSE 0 END) as severe_amt,
                SUM(amount) as total
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND paid_date IS NULL
            AND due_date IS NOT NULL
        """, [client_id])[0]

        if not result['total'] or result['total'] == 0:
            return 100  # No outstanding = healthy

        current_pct = (result['current_amt'] or 0) / result['total']
        moderate_pct = (result['moderate_amt'] or 0) / result['total']

        return 100 * current_pct + 50 * moderate_pct
```

---

## 10. Finance Truth & AR

### 10.1 AR Definition (Single Source of Truth)

**Accounts Receivable (AR):** `status IN ('sent', 'overdue') AND paid_date IS NULL`

**Valid AR for calculations:** AR AND `due_date IS NOT NULL` AND `client_id IS NOT NULL`

**Invalid AR:** AR but missing `due_date` or `client_id` → resolution queue, excluded from calculations

### 10.2 Aging Buckets

| Bucket | Days Overdue |
|--------|--------------|
| `current` | ≤0 |
| `1-30` | 1-30 |
| `31-60` | 31-60 |
| `61-90` | 61-90 |
| `90+` | >90 |
| `NULL` | Not AR, or invalid AR |

### 10.3 Finance Truth Module

```python
class FinanceTruth:

    def run(self) -> Dict:
        """Calculate AR metrics using only VALID AR invoices."""

        # Only valid AR: sent/overdue, unpaid, with due_date and client_id
        ar_data = self.store.query("""
            SELECT client_id, aging_bucket, SUM(amount) as total
            FROM invoices
            WHERE status IN ('sent', 'overdue')
            AND paid_date IS NULL
            AND due_date IS NOT NULL
            AND client_id IS NOT NULL
            GROUP BY client_id, aging_bucket
        """)

        # Aggregate...
        return results
```

---

## 11. Orchestration

[Unchanged from v4.2]

---

## 12. Schema Definitions

```sql
-- Tasks (NO is_internal column)
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    title TEXT NOT NULL,
    notes TEXT,
    status TEXT DEFAULT 'active',
    project_id TEXT,
    brand_id TEXT,
    client_id TEXT,
    project_link_status TEXT DEFAULT 'unlinked'
        CHECK (project_link_status IN ('linked', 'partial', 'unlinked')),
    client_link_status TEXT DEFAULT 'unlinked'
        CHECK (client_link_status IN ('linked', 'unlinked', 'n/a')),
    assignee_id TEXT,
    assignee_raw TEXT,
    lane TEXT DEFAULT 'ops',
    due_date TEXT,
    duration_min INTEGER DEFAULT 60,
    -- NO is_internal column; derived from projects.is_internal
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (assignee_id) REFERENCES team_members(id)
);

CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_client ON tasks(client_id);
CREATE INDEX idx_tasks_project_link_status ON tasks(project_link_status);
CREATE INDEX idx_tasks_client_link_status ON tasks(client_link_status);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id);

-- Communications
CREATE TABLE communications (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    thread_id TEXT,
    from_email TEXT,
    from_domain TEXT,
    to_emails TEXT,
    subject TEXT,
    snippet TEXT,
    body_text TEXT,
    content_hash TEXT,
    received_at TEXT,
    client_id TEXT,
    link_status TEXT DEFAULT 'unlinked' CHECK (link_status IN ('linked', 'unlinked')),
    processed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX idx_communications_client ON communications(client_id);
CREATE INDEX idx_communications_processed ON communications(processed);
CREATE INDEX idx_communications_content_hash ON communications(content_hash);
CREATE INDEX idx_communications_from_email ON communications(from_email);
CREATE INDEX idx_communications_from_domain ON communications(from_domain);

-- Projects
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    brand_id TEXT,  -- NOT NULL enforced by gate when is_internal=0
    client_id TEXT, -- DERIVED, NULL when is_internal=1
    is_internal INTEGER NOT NULL DEFAULT 0,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'project' CHECK (type IN ('project', 'retainer')),
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

-- Clients
CREATE TABLE clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT DEFAULT 'C',
    health_score REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Brands
CREATE TABLE brands (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    UNIQUE(client_id, name)
);

-- Client Identities
CREATE TABLE client_identities (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    client_id TEXT NOT NULL,
    identity_type TEXT NOT NULL CHECK (identity_type IN ('email', 'domain')),
    identity_value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    UNIQUE(identity_type, identity_value)
);

-- Team Members
CREATE TABLE team_members (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    asana_gid TEXT,
    default_lane TEXT DEFAULT 'ops',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Invoices
CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    client_id TEXT,
    client_name TEXT,
    brand_id TEXT,
    project_id TEXT,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft', 'sent', 'paid', 'overdue', 'void')),
    paid_date TEXT,
    aging_bucket TEXT CHECK (aging_bucket IN ('current', '1-30', '31-60', '61-90', '90+', NULL)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX idx_invoices_client ON invoices(client_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_ar ON invoices(status, paid_date)
    WHERE status IN ('sent', 'overdue') AND paid_date IS NULL;

-- Capacity Lanes
CREATE TABLE capacity_lanes (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name TEXT UNIQUE NOT NULL,
    owner_id TEXT,
    weekly_hours REAL NOT NULL CHECK (weekly_hours > 0),
    buffer_pct REAL DEFAULT 20,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES team_members(id)
);

-- Resolution Queue
CREATE TABLE resolution_queue (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2,
    context TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    resolution_action TEXT,
    UNIQUE(entity_type, entity_id, issue_type)
);

CREATE INDEX idx_resolution_queue_pending
ON resolution_queue(priority, created_at)
WHERE resolved_at IS NULL;

-- Pending Actions
CREATE TABLE pending_actions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    idempotency_key TEXT UNIQUE NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    payload TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    approval_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
    proposed_by TEXT,
    decided_at TEXT,
    decided_by TEXT,
    executed_at TEXT,
    execution_result TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_pending_actions_status ON pending_actions(status);

-- Asana Maps
CREATE TABLE asana_project_map (
    asana_gid TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asana_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE asana_user_map (
    asana_gid TEXT PRIMARY KEY,
    team_member_id TEXT NOT NULL,
    asana_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (team_member_id) REFERENCES team_members(id)
);

-- Commitments
CREATE TABLE commitments (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    source_type TEXT NOT NULL DEFAULT 'communication',
    source_id TEXT NOT NULL,
    text TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('promise', 'request')),
    confidence REAL,
    deadline TEXT,
    speaker TEXT,
    target TEXT,
    client_id TEXT,
    task_id TEXT,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'fulfilled', 'broken', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES communications(id),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_commitments_source ON commitments(source_id);
CREATE INDEX idx_commitments_client ON commitments(client_id);
```

---

## 13. Implementation Sequence

### Phase 1: Schema (Day 1)
- Remove `is_internal` from tasks table (if exists)
- Add `project_link_status`, `client_link_status` columns
- Add all indexes

### Phase 2: Normalization (Day 2)
- Update normalizer for two-status logic
- Verify all 6 data_integrity invariants pass

### Phase 3-5: [Unchanged]

---

## 14. Validation & Acceptance

### 14.1 Key Queries

```sql
-- Verify no tasks.is_internal column
SELECT COUNT(*) AS c FROM pragma_table_info('tasks') WHERE name = 'is_internal';
-- Expected: c = 0

-- Internal tasks: project_link='linked', client_link='n/a'
SELECT COUNT(*) AS c FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE p.is_internal = 1
AND (t.project_link_status != 'linked' OR t.client_link_status != 'n/a');
-- Expected: c = 0

-- Client coverage excludes n/a
SELECT
    COUNT(CASE WHEN client_link_status = 'linked' THEN 1 END) as linked,
    COUNT(CASE WHEN client_link_status = 'unlinked' THEN 1 END) as unlinked,
    COUNT(CASE WHEN client_link_status = 'n/a' THEN 1 END) as na
FROM tasks;

-- Finance uses due_date directly
SELECT COUNT(*) AS c FROM invoices
WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
AND due_date IS NOT NULL AND aging_bucket IS NULL;
-- Expected: c = 0 (all valid AR has bucket)
```

### 14.2 Acceptance Criteria

| Criterion | Pass Condition |
|-----------|----------------|
| No tasks.is_internal | Column doesn't exist |
| data_integrity includes partial check | Invariant 4 runs with explicit c.id IS NOT NULL |
| Resolution queue no double-queue | Distinct issue_types |
| client_unlinked_unexpected is rare | Should be 0 unless corruption |
| Finance uses due_date | All AR queries include `due_date IS NOT NULL` |
| All 6 invariants pass | `_check_data_integrity()` returns True |
| Query consistency | All COUNT queries use `AS c` alias, coverage uses `AS pct` |
| Coverage queries | Use canonical `100.0 * SUM(...) / NULLIF(SUM(...), 0)` pattern |
| Store returns dict rows | `row['column']` access works |
| Dates are ISO normalized | All due_date values are `YYYY-MM-DD` or NULL |

---

## 15. Dashboard Architecture

### 15.1 Design Principles

| Principle | Implementation |
|-----------|----------------|
| Offline-first | Static HTML/CSS/JS; no build step required |
| No backend | Reads JSON exports; no API server |
| Single artifact | One `index.html` + data files |
| Framework-free | Vanilla JS only; copy-paste deployable |
| Graceful degradation | Missing data → clear "no data" state, not crash |

### 15.2 Page Structure

| Page | Purpose | URL |
|------|---------|-----|
| Home ("Now") | Executive status + today's risks + deltas | `/` or `index.html` |
| Resolution Queue | P1/P2 work queue with actions | `#queue` |
| Domains | Deep-dive per domain (Delivery, Clients, etc.) | `#domain/{name}` |
| History | Run history, trend charts | `#history` |

### 15.3 Unified Snapshot Schema

One file per cycle. Dashboard reads only `snapshot.json` + `previous_snapshot.json`.

```
output/
├── snapshot.json          # Complete cycle output (single source)
└── previous_snapshot.json # Prior cycle for delta computation
```

**`snapshot.json` complete schema:**

```json
{
  "meta": {
    "run_id": "2026-02-03T09:00:00Z",
    "started_at": "2026-02-03T09:00:00Z",
    "finished_at": "2026-02-03T09:00:47Z",
    "duration_seconds": 47,
    "confidence": "degraded",
    "blocked_capabilities": ["commitment_tracking"]
  },

  "gates": {
    "summary": { "passed": 8, "failed": 2, "total": 10 },
    "items": [
      { "name": "data_integrity", "passed": true, "blocking": true, "value": null },
      { "name": "client_coverage", "passed": false, "blocking": false, "value": 62.0, "target": 80.0 }
    ]
  },

  "queue": {
    "p1_count": 3,
    "p2_count": 12,
    "items": [
      {
        "id": "q-001",
        "priority": "P1",
        "issue_type": "task_unlinked",
        "entity_type": "task",
        "entity_id": "t-123",
        "summary": "Task 'Design review' has no project",
        "suggested_action": "Link to project or mark internal",
        "created_at": "2026-02-03T08:00:00Z"
      }
    ]
  },

  "risks": {
    "items": [
      {
        "id": "r-001",
        "rank": 1,
        "score": 87,
        "type": "ar_severe",
        "title": "Invoice #1042 90+ days overdue",
        "driver": "$12,000 outstanding from Acme Corp",
        "impact": 12000,
        "domain": "cash",
        "entity_type": "invoice",
        "entity_id": "inv-1042",
        "drill_url": "#domain/cash?invoice=inv-1042"
      }
    ]
  },

  "domains": {
    "delivery": {
      "status": "degraded",
      "driver": "3 projects at risk",
      "metrics": {
        "projects_on_track": 8,
        "projects_at_risk": 3,
        "projects_off_track": 1,
        "overdue_tasks": 7,
        "unlinked_tasks": 43,
        "partial_tasks": 2,
        "due_7d_count": 15
      }
    },
    "clients": {
      "status": "healthy",
      "driver": "No critical health drops",
      "metrics": {
        "total_clients": 24,
        "avg_health_score": 72,
        "clients_below_50": 2,
        "clients_drifting": 3
      }
    },
    "cash": {
      "status": "degraded",
      "driver": "$12K in 90+ bucket",
      "metrics": {
        "ar_total": 45000,
        "ar_current": 18000,
        "ar_1_30": 10000,
        "ar_31_60": 5000,
        "ar_61_90": 0,
        "ar_90_plus": 12000,
        "ar_invalid_count": 2,
        "concentration_top_client_pct": 28
      }
    },
    "comms": {
      "status": "healthy",
      "driver": "Inbox clear",
      "metrics": {
        "unprocessed": 5,
        "needs_response": 2,
        "response_overdue": 0,
        "commitments_open": 8,
        "commitments_untracked": 3,
        "commitments_deadline_7d": 2
      }
    },
    "capacity": {
      "status": "warning",
      "driver": "Design lane at 95%",
      "metrics": {
        "lanes": [
          { "name": "Design", "allocated": 38, "capacity": 40, "utilization": 95 },
          { "name": "Dev", "allocated": 28, "capacity": 40, "utilization": 70 }
        ],
        "overloaded_lanes": 0,
        "reality_gap_hours": 4,
        "time_debt_hours": 8
      }
    },
    "data": {
      "status": "degraded",
      "driver": "client_coverage at 62%",
      "metrics": {
        "gates_passed": 8,
        "gates_failed": 2,
        "client_coverage_pct": 62,
        "commitment_ready_pct": 34.6,
        "project_brand_coverage_pct": 100
      }
    }
  },

  "deltas": {
    "gate_flips": [
      { "gate": "client_coverage", "from": true, "to": false }
    ],
    "queue_p1": { "previous": 2, "current": 3, "delta": 1 },
    "queue_p2": { "previous": 10, "current": 12, "delta": 2 },
    "ar_total": { "previous": 42000, "current": 45000, "delta": 3000 },
    "ar_severe": { "previous": 10000, "current": 12000, "delta": 2000 },
    "overdue_count": { "previous": 5, "current": 7, "delta": 2 },
    "unprocessed_comms": { "previous": 8, "current": 5, "delta": -3 }
  }
}
```

### 15.4 Risk Ranking Algorithm

Cross-domain risks are scored 0-100 and ranked for "Today's Risks" display.

#### Risk Types & Base Scores

| Risk Type | Domain | Base Score | Modifiers |
|-----------|--------|------------|-----------|
| `task_overdue` | delivery | 40 | +5 per day overdue, +20 if P1/critical |
| `project_off_track` | delivery | 60 | +10 per blocker |
| `ar_severe` | cash | 70 | +0.001 × amount (max +30) |
| `ar_concentration` | cash | 50 | +20 if >40% single client |
| `client_health_drop` | clients | 45 | +2 × health_delta (if negative) |
| `commitment_at_risk` | comms | 55 | +15 if untracked, +10 per day until deadline |
| `response_overdue` | comms | 50 | +5 per day overdue |
| `capacity_overload` | capacity | 60 | +5 per 10% over 100% |

#### Score Calculation

```python
def calculate_risk_score(risk_type: str, context: dict) -> int:
    base = BASE_SCORES[risk_type]
    score = base

    if risk_type == 'task_overdue':
        score += min(context['days_overdue'] * 5, 25)
        if context.get('priority') in ('P1', 'critical'):
            score += 20

    elif risk_type == 'ar_severe':
        score += min(context['amount'] * 0.001, 30)

    elif risk_type == 'client_health_drop':
        score += abs(context['health_delta']) * 2

    elif risk_type == 'commitment_at_risk':
        if context.get('task_id') is None:
            score += 15  # untracked
        days_to_deadline = context.get('days_to_deadline', 999)
        if days_to_deadline <= 7:
            score += (7 - days_to_deadline) * 10 / 7

    elif risk_type == 'capacity_overload':
        overage = context['utilization'] - 100
        score += (overage // 10) * 5

    return min(score, 100)
```

#### Gate-Aware Confidence Labels

Every risk must carry a data confidence label based on gate status. Without this, exec trust breaks.

**Confidence labels:**
| Label | Condition | Display | Behavior |
|-------|-----------|---------|----------|
| `reliable` | All required gates for domain pass | No badge | Show normally |
| `degraded` | Coverage/quality gates fail | ⚠️ "Data incomplete" | Show with warning |
| `blocked` | Blocking gate fails | 🚫 | **Do not show derived claims** |

**Gate-to-domain mapping:**
```python
DOMAIN_GATES = {
    'delivery': {
        'blocking': ['data_integrity'],
        'quality': ['project_brand_required', 'project_client_populated']
    },
    'clients': {
        'blocking': ['data_integrity'],
        'quality': ['client_coverage']
    },
    'cash': {
        'blocking': ['data_integrity', 'finance_ar_clean'],
        'quality': ['finance_ar_coverage']
    },
    'comms': {
        'blocking': ['data_integrity'],
        'quality': ['commitment_ready']
    },
    'capacity': {
        'blocking': ['data_integrity', 'capacity_baseline'],
        'quality': []
    }
}

def get_domain_confidence(domain: str, gates: dict) -> str:
    """
    Determine confidence label for a domain based on gate status.

    Args:
        domain: Domain name
        gates: Dict of gate_name -> passed (bool)

    Returns:
        'reliable' | 'degraded' | 'blocked'
    """
    domain_gates = DOMAIN_GATES.get(domain, {'blocking': [], 'quality': []})

    # Check blocking gates first
    for gate in domain_gates['blocking']:
        if not gates.get(gate, False):
            return 'blocked'

    # Check quality gates
    for gate in domain_gates['quality']:
        if not gates.get(gate, False):
            return 'degraded'

    return 'reliable'
```

**Risk generation with confidence:**
```python
def generate_risks_with_confidence(snapshot: dict) -> list[dict]:
    """
    Generate risks with gate-aware confidence labels.
    Blocked domains produce NO risks (not even with warnings).
    """
    gates = {g['name']: g['passed'] for g in snapshot['gates']['items']}
    risks = []

    for risk in collect_all_risks(snapshot):
        domain = risk['domain']
        confidence = get_domain_confidence(domain, gates)

        # Blocked = do not emit risk
        if confidence == 'blocked':
            continue

        risk['data_confidence'] = confidence
        risk['confidence_note'] = get_confidence_note(domain, confidence, gates)

        # Degraded risks get score penalty
        if confidence == 'degraded':
            risk['score'] = risk['score'] * 0.8  # 20% penalty

        risks.append(risk)

    return risks

def get_confidence_note(domain: str, confidence: str, gates: dict) -> str | None:
    """
    Generate human-readable note explaining degraded confidence.
    """
    if confidence == 'reliable':
        return None

    # Find which quality gate failed
    domain_gates = DOMAIN_GATES[domain]
    failed = [g for g in domain_gates['quality'] if not gates.get(g, False)]

    notes = {
        'client_coverage': "Client coverage at {pct}% - some client risks may be missing",
        'commitment_ready': "Commitment extraction incomplete - open loops may be understated",
        'finance_ar_coverage': "AR data incomplete - amounts may be understated",
        'project_brand_required': "Some projects missing brand - client attribution incomplete"
    }

    return notes.get(failed[0], "Data quality below threshold") if failed else None
```

**Risk JSON with confidence:**
```json
{
  "id": "r-003",
  "rank": 3,
  "score": 52,
  "type": "client_health_drop",
  "title": "Acme Corp health dropped to 45",
  "domain": "clients",
  "data_confidence": "degraded",
  "confidence_note": "Client coverage at 62% - some client risks may be missing",
  "driver": "2 overdue tasks, 1 unanswered thread",
  ...
}
```

**Dashboard display rules:**
| Confidence | Home Page | Domain Page |
|------------|-----------|-------------|
| `reliable` | Show | Show |
| `degraded` | Show with ⚠️ badge + tooltip | Show with banner explaining gap |
| `blocked` | **Hide entirely** | Show "Data unavailable" placeholder |

#### Ranking Rules

1. Filter out `blocked` risks (never show)
2. Sort by score descending (degraded risks already penalized 20%)
3. Tie-breaker: domain priority (cash > delivery > clients > comms > capacity)
4. Tie-breaker 2: `reliable` before `degraded` at same score
5. Max 7 risks displayed on Home page
6. Risks scoring < 30 are excluded from Home (still visible in domain pages)

### 15.5 Delta Persistence

After each cycle:
1. Rename current `snapshot.json` → `previous_snapshot.json`
2. Write new `snapshot.json`
3. Dashboard computes `deltas` section by comparing the two

If `previous_snapshot.json` doesn't exist (first run), all deltas show as "-" (no comparison).

---

## 16. Home Page Widgets

### 16.1 Widget Inventory (12 max)

| # | Widget | Type | Purpose |
|---|--------|------|---------|
| 1 | Executive Status Strip | Banner | System health at a glance |
| 2 | Today's Risks | Card stack | Cross-domain prioritized problems |
| 3-8 | Domain Tiles (×6) | Scorecard | Per-domain status + driver |
| 9 | What Changed | Change log | Deltas since last run |

### 16.2 Widget Specifications

#### Widget 1: Executive Status Strip (Banner)

**Position:** Top of page, full width

**Content:**
- Last successful run: timestamp + duration
- Overall confidence: `Blocked` / `Degraded` / `Healthy`
- Blocked capabilities list (if any)

**Visual states:**
| Confidence | Color | Icon |
|------------|-------|------|
| Blocked | Red | ⛔ |
| Degraded | Amber | ⚠️ |
| Healthy | Green | ✓ |

**Data source:** `run_meta.json`

---

#### Widget 2: Today's Risks (Ranked Cards)

**Position:** Below banner, prominent placement

**Content:** Top 5-7 risks across all domains, ranked by impact

**Risk types surfaced:**
| Risk Type | Source | Priority Signal |
|-----------|--------|-----------------|
| Overdue work | tasks | Priority + days overdue |
| AR severe | invoices | Amount + aging bucket |
| Client health drop | clients | Health delta negative |
| Commitment at risk | commitments | Deadline near + no task |
| Capacity overload | capacity | Lane > 100% effective |

**Card structure:**
```
┌─────────────────────────────────────┐
│ [Icon] Risk Title                   │
│ Driver: {why this is a risk}        │
│ Impact: {quantified if possible}    │
│ [Drill →]                           │
└─────────────────────────────────────┘
```

**Data source:** Aggregated from `queue.json`, `metrics.json`

---

#### Widgets 3-8: Domain Tiles (Scoreboard)

**Position:** Grid layout, 6 tiles

**Domains:**
1. **Delivery** - Task completion, overdue rate
2. **Clients** - Health scores, coverage
3. **Cash** - AR totals, severe bucket
4. **Comms** - Unprocessed, commitment extraction
5. **Capacity** - Lane loads, overload risk
6. **Data Confidence** - Gate pass rate, coverage %

**Tile structure:**
```
┌──────────────────┐
│ Domain Name      │
│ ● Status         │
│ Δ +/-            │
│ Driver: {text}   │
└──────────────────┘
```

**Status values:** `Healthy` / `Degraded` / `Blocked`

**Data source:** `metrics.json`, `gates.json`

---

#### Widget 9: What Changed Since Last Run

**Position:** Below domain tiles

**Content:** Delta log showing meaningful changes

**Change types tracked:**
| Change | Display |
|--------|---------|
| Gate flip (pass→fail) | 🔴 `{gate}` now failing |
| Gate flip (fail→pass) | 🟢 `{gate}` now passing |
| Queue P1 delta | `P1: {n}` → `{m}` ({±diff}) |
| Queue P2 delta | `P2: {n}` → `{m}` ({±diff}) |
| AR total delta | `AR: ${n}` → `${m}` ({±diff}) |
| AR severe delta | `Severe: ${n}` → `${m}` ({±diff}) |
| Overdue delta | `Overdue: {n}` → `{m}` ({±diff}) |
| Unprocessed comms delta | `Comms: {n}` → `{m}` ({±diff}) |

**Visual treatment:**
- Increases (bad): Red text
- Decreases (good): Green text
- No change: Gray/muted

**Data source:** Compare `metrics.json` vs `previous_run.json`

---

### 16.3 Drill-Down Links

Each risk card and domain tile links to detailed view:

| Widget | Drill Target |
|--------|--------------|
| Risk card | `#queue?filter={risk_type}` |
| Domain tile | `#domain/{domain_name}` |
| Gate flip | `#domain/data?gate={gate_name}` |

---

## 17. Domain Page Specifications

Each domain page provides "hours of synthesis" - the deep-dive that would otherwise require manual cross-referencing across multiple tools.

### 17.1 Delivery Command

**URL:** `#domain/delivery`

**Sections:**

#### Project Status Board
| Status | Derivation |
|--------|------------|
| On Track | No overdue tasks, no blockers, chain health ≥ 80% |
| At Risk | Overdue tasks OR blockers OR chain health < 80% |
| Off Track | Multiple overdue + blockers + chain health < 50% |

**Project status derivation:**
```python
def calc_project_status(project_id: str) -> dict:
    tasks = get_project_tasks(project_id, status__ne='done')

    overdue = [t for t in tasks if t['due_date'] and t['due_date'] < today]
    blocked = [t for t in tasks if t.get('is_blocked')]

    # Chain health = % of tasks with valid project+client links
    linked = len([t for t in tasks if t['project_link_status'] == 'linked'
                  and t['client_link_status'] in ('linked', 'n/a')])
    chain_health = (linked / len(tasks) * 100) if tasks else 100

    # Status derivation
    if len(overdue) == 0 and len(blocked) == 0 and chain_health >= 80:
        status = 'on_track'
    elif len(overdue) >= 2 and len(blocked) >= 1 and chain_health < 50:
        status = 'off_track'
    else:
        status = 'at_risk'

    return {
        'status': status,
        'overdue_count': len(overdue),
        'blocked_count': len(blocked),
        'chain_health': chain_health,
        'total_tasks': len(tasks),
        'next_milestone': get_next_milestone(project_id)
    }
```

**Status display:**
| Status | Badge Color | Icon |
|--------|-------------|------|
| On Track | Green | ✓ |
| At Risk | Amber | ⚠️ |
| Off Track | Red | ✗ |

Display: Card per project with status badge, owner, next milestone.

#### Work Integrity
- **Unlinked tasks:** Count + list (tasks with `project_link_status = 'unlinked'`)
- **Partial chains:** Count + list (tasks with `project_link_status = 'partial'`)
- **Missing brand:** Projects without brand_id (blocks client attribution)
- **Missing client chains:** Linked tasks where client_id resolution fails

Each item links to resolution queue entry.

#### Due Soon Heat
Matrix view: Lanes × Assignees

| Cell | Color |
|------|-------|
| 0 due | Gray |
| 1-2 due | Yellow |
| 3+ due | Red |

Time window: Due within 7 days.

#### Drilldowns
- Project card → Project detail page (tasks, timeline, health)
- Task count → Filtered task list

---

### 17.2 Client 360

**URL:** `#domain/clients` (list) and `#domain/clients/{id}` (detail)

**List View:** All clients sorted by health score (lowest first)

**Detail View (per client):**

#### Health Score Calculation

**Formula:** `health = 100 - (delivery_penalty × 0.4 + comms_penalty × 0.3 + ar_penalty × 0.3)`

**Driver penalties (0-100 scale each):**

```python
def calc_delivery_penalty(client_id: str) -> float:
    tasks = get_client_tasks(client_id, status='open')
    overdue = [t for t in tasks if t['due_date'] < today and t['status'] != 'done']
    blocked = [t for t in tasks if t['is_blocked']]

    penalty = 0
    penalty += min(len(overdue) * 15, 60)      # 15 pts per overdue, max 60
    penalty += min(len(blocked) * 10, 30)       # 10 pts per blocked, max 30
    penalty += min(sum(t['days_overdue'] for t in overdue) * 2, 40)  # 2 pts per day, max 40
    return min(penalty, 100)

def calc_comms_penalty(client_id: str) -> float:
    threads = get_client_threads(client_id)
    awaiting = [t for t in threads if t['needs_response'] and t['direction'] == 'inbound']

    penalty = 0
    for thread in awaiting:
        wait_days = (today - thread['last_inbound_date']).days
        if wait_days <= 1: penalty += 5
        elif wait_days <= 3: penalty += 15
        elif wait_days <= 7: penalty += 30
        else: penalty += 50  # 7+ days = critical
    return min(penalty, 100)

def calc_ar_penalty(client_id: str) -> float:
    invoices = get_client_invoices(client_id, status='outstanding')

    penalty = 0
    for inv in invoices:
        if inv['aging_bucket'] == 'current': penalty += 0
        elif inv['aging_bucket'] == '1-30': penalty += 10
        elif inv['aging_bucket'] == '31-60': penalty += 25
        elif inv['aging_bucket'] == '61-90': penalty += 50
        elif inv['aging_bucket'] == '90+': penalty += 80
    return min(penalty, 100)

def calc_health_score(client_id: str) -> int:
    d = calc_delivery_penalty(client_id)
    c = calc_comms_penalty(client_id)
    a = calc_ar_penalty(client_id)
    return max(0, int(100 - (d * 0.4 + c * 0.3 + a * 0.3)))
```

**Health score interpretation:**
| Score | Status | Action |
|-------|--------|--------|
| 80-100 | Healthy | Maintain |
| 60-79 | Watch | Review open loops |
| 40-59 | At Risk | Proactive outreach |
| 0-39 | Critical | Immediate escalation |

#### Open Loops
| Loop Type | Source | Display |
|-----------|--------|---------|
| Overdue deliverables | tasks | Task name + days overdue |
| Unanswered comms | communications | Thread subject + wait time |
| Open commitments | commitments | Promise text + deadline |

#### Last Touch & Drift Detection

**Last touch calculation:**
```python
def get_last_touch(client_id: str) -> dict:
    last_comm = get_latest_communication(client_id)  # Any direction
    last_meeting = get_latest_calendar_event(client_id, type='meeting')

    last_touch_date = max(
        last_comm['date'] if last_comm else date.min,
        last_meeting['date'] if last_meeting else date.min
    )

    return {
        'date': last_touch_date,
        'source': 'communication' if last_comm and last_comm['date'] == last_touch_date else 'meeting',
        'freshness_days': (today - last_touch_date).days
    }
```

**Drift thresholds by client tier:**
| Tier | Definition | Max Days Since Touch | Alert Trigger |
|------|------------|---------------------|---------------|
| 1 | Top 20% by revenue | 7 | > 7 days |
| 2 | Active retainer | 14 | > 14 days |
| 3 | Project-based | 21 | > 21 days |
| 4 | Dormant/past | 60 | > 60 days |

Tier is derived from `clients.tier` column or defaults based on revenue rank.

#### Drilldowns
- Communications → Thread list filtered by client
- Tasks → Task list filtered by client
- Invoices → AR list filtered by client

---

### 17.3 Cash / AR Control

**URL:** `#domain/cash`

**Sections:**

#### Outstanding by Aging Bucket
| Bucket | Definition | Display |
|--------|------------|---------|
| Current | Not yet due | Amount + count |
| 1-30 | 1-30 days overdue | Amount + count |
| 31-60 | 31-60 days overdue | Amount + count |
| 61-90 | 61-90 days overdue | Amount + count |
| 90+ | >90 days overdue | Amount + count (SEVERE) |

Visualization: Stacked bar or bucket cards.

#### Concentration Risk

**Calculation:**
```python
def calc_concentration_risk() -> dict:
    """
    Concentration risk = exposure to single-client AR default.
    """
    invoices = get_outstanding_invoices()
    total_ar = sum(inv['amount'] for inv in invoices)

    if total_ar == 0:
        return {'risk_level': 'none', 'clients': [], 'total_ar': 0}

    # Group by client
    by_client = defaultdict(float)
    for inv in invoices:
        by_client[inv['client_id']] += inv['amount']

    # Sort by amount descending
    ranked = sorted(by_client.items(), key=lambda x: -x[1])

    # Calculate shares
    clients = []
    for client_id, amount in ranked[:5]:
        client = get_client(client_id)
        share = (amount / total_ar) * 100
        clients.append({
            'client_id': client_id,
            'client_name': client['name'],
            'amount': amount,
            'share_pct': round(share, 1),
            'flagged': share > 30
        })

    # Top client share determines risk level
    top_share = clients[0]['share_pct'] if clients else 0

    return {
        'risk_level': 'critical' if top_share > 50 else 'high' if top_share > 40 else 'elevated' if top_share > 30 else 'normal',
        'top_client_share': top_share,
        'clients': clients,
        'total_ar': total_ar
    }
```

**Risk thresholds:**
| Top Client Share | Risk Level | Display |
|------------------|------------|---------|
| > 50% | Critical | 🔴 Red badge + alert |
| > 40% | High | 🟠 Orange badge |
| > 30% | Elevated | 🟡 Yellow badge |
| ≤ 30% | Normal | No flag |

**Display:** Top 5 clients table with amount, share %, and flag indicator.

---

#### Invalid AR (Resolution Queue Integration)

**Invalid AR detection:**
```python
def get_invalid_ar() -> dict:
    """
    Invalid AR = invoices that can't be properly tracked/aged.
    Each invalid invoice generates a resolution queue item.
    """
    invoices = get_invoices(status__in=['sent', 'overdue', 'partial'])

    invalid = {
        'missing_due_date': [],
        'missing_client': [],
        'invalid_status': [],
        'orphaned': []  # client_id points to non-existent client
    }

    for inv in invoices:
        if inv['due_date'] is None:
            invalid['missing_due_date'].append(inv)

        if inv['client_id'] is None:
            invalid['missing_client'].append(inv)
        elif not client_exists(inv['client_id']):
            invalid['orphaned'].append(inv)

        if inv['status'] not in VALID_STATUSES:
            invalid['invalid_status'].append(inv)

    return invalid

def generate_ar_queue_items(invalid: dict) -> list[dict]:
    """
    Generate resolution queue items for invalid AR.
    """
    items = []

    for inv in invalid['missing_due_date']:
        items.append({
            'priority': 'P1',  # Blocks aging calculation
            'issue_type': 'ar_missing_due_date',
            'entity_type': 'invoice',
            'entity_id': inv['id'],
            'summary': f"Invoice #{inv['number']} missing due date",
            'suggested_action': "Add due date in Xero or mark as paid/void",
            'drill_url': f"#domain/cash?invoice={inv['id']}"
        })

    for inv in invalid['missing_client']:
        items.append({
            'priority': 'P2',
            'issue_type': 'ar_missing_client',
            'entity_type': 'invoice',
            'entity_id': inv['id'],
            'summary': f"Invoice #{inv['number']} not linked to client",
            'suggested_action': "Link to client in Xero or create client record",
            'drill_url': f"#domain/cash?invoice={inv['id']}"
        })

    for inv in invalid['orphaned']:
        items.append({
            'priority': 'P1',
            'issue_type': 'ar_orphaned_client',
            'entity_type': 'invoice',
            'entity_id': inv['id'],
            'summary': f"Invoice #{inv['number']} references non-existent client {inv['client_id']}",
            'suggested_action': "Create client or reassign invoice",
            'drill_url': f"#domain/cash?invoice={inv['id']}"
        })

    return items
```

**Dashboard display:**
| Category | Count | Drill Action |
|----------|-------|--------------|
| Missing due date | {n} | `#queue?filter=ar_missing_due_date` |
| Missing client | {n} | `#queue?filter=ar_missing_client` |
| Orphaned client | {n} | `#queue?filter=ar_orphaned_client` |

Click count → filtered resolution queue view.

---

#### Cash Risk Next 14 Days

**Calculation:**
```python
def calc_14_day_exposure() -> dict:
    """
    14-day cash risk = money at risk in the next 2 weeks.
    Combines: already overdue + coming due soon.
    """
    today = date.today()
    window_end = today + timedelta(days=14)

    invoices = get_outstanding_invoices()

    already_overdue = []
    due_soon = []

    for inv in invoices:
        if inv['due_date'] is None:
            continue  # Invalid AR, handled separately

        due = parse_date(inv['due_date'])

        if due < today:
            days_overdue = (today - due).days
            already_overdue.append({
                'invoice_id': inv['id'],
                'invoice_number': inv['number'],
                'client_id': inv['client_id'],
                'client_name': get_client(inv['client_id'])['name'],
                'amount': inv['amount'],
                'due_date': inv['due_date'],
                'days_overdue': days_overdue,
                'severity': 'critical' if days_overdue > 60 else 'high' if days_overdue > 30 else 'moderate'
            })
        elif due <= window_end:
            days_until = (due - today).days
            due_soon.append({
                'invoice_id': inv['id'],
                'invoice_number': inv['number'],
                'client_id': inv['client_id'],
                'client_name': get_client(inv['client_id'])['name'],
                'amount': inv['amount'],
                'due_date': inv['due_date'],
                'days_until_due': days_until,
                'urgency': 'imminent' if days_until <= 3 else 'soon' if days_until <= 7 else 'upcoming'
            })

    return {
        'already_overdue': {
            'count': len(already_overdue),
            'total': sum(i['amount'] for i in already_overdue),
            'items': sorted(already_overdue, key=lambda x: -x['days_overdue'])
        },
        'due_soon': {
            'count': len(due_soon),
            'total': sum(i['amount'] for i in due_soon),
            'items': sorted(due_soon, key=lambda x: x['days_until_due'])
        },
        'total_exposure': sum(i['amount'] for i in already_overdue) + sum(i['amount'] for i in due_soon),
        'window_days': 14
    }
```

**Display:**
```
┌─────────────────────────────────────────────────────┐
│ 14-Day Cash Exposure: $47,500                       │
├─────────────────────────────────────────────────────┤
│ 🔴 Already Overdue    $32,000  (5 invoices)         │
│ 🟡 Due in ≤14 days    $15,500  (3 invoices)         │
└─────────────────────────────────────────────────────┘
```

Expandable sections show individual invoices sorted by urgency.

---

#### Drilldowns
| Element | Drill Target | Filter |
|---------|--------------|--------|
| Aging bucket | `#invoices?bucket={bucket}` | Pre-filtered by aging |
| Client row | `#domain/clients/{id}` | Client 360 page |
| Invalid count | `#queue?filter={issue_type}` | Resolution queue filtered |
| Overdue invoice | `#invoices/{id}` | Invoice detail + actions |
| Due soon invoice | `#invoices/{id}` | Invoice detail + actions |

---

### 17.4 Comms & Commitments

**URL:** `#domain/comms`

**Sections:**

#### Inbox Triage
| Category | Definition | Action |
|----------|------------|--------|
| Unprocessed | New, not yet reviewed | Process |
| Unread | Marked unread / flagged | Review |
| Needs response | Inbound, no outbound reply | Respond |
| Response deadline | Has explicit deadline | Prioritize |

Display: Count per category + expandable list.

**Response deadline logic:**

```python
def get_response_deadline(comm: dict) -> date | None:
    # Explicit deadline from commitment extraction
    if comm.get('response_deadline'):
        return parse_date(comm['response_deadline'])

    # Implicit deadline based on client tier
    client = get_client(comm['client_id'])
    tier_deadlines = {1: 1, 2: 2, 3: 3, 4: 7}  # days

    if comm['direction'] == 'inbound' and comm['needs_response']:
        return comm['date'] + timedelta(days=tier_deadlines.get(client['tier'], 3))

    return None

def is_response_overdue(comm: dict) -> bool:
    deadline = get_response_deadline(comm)
    return deadline is not None and today > deadline
```

**Response status derivation:**
| Status | Condition |
|--------|-----------|
| `on_time` | Response sent before deadline |
| `pending` | Needs response, deadline not passed |
| `overdue` | Needs response, deadline passed |
| `n/a` | No response needed (outbound, informational) |

#### Commitments Dashboard
| View | Filter |
|------|--------|
| Open promises | type='promise', status='open' |
| Open requests | type='request', status='open' |
| Deadline approaching | deadline < 7 days |
| Untracked | task_id IS NULL (no linked task) |

Card per commitment: text, speaker, target, deadline, linked task (or "⚠️ untracked").

#### Relationship Drift

**Drift detection logic:**
```python
def get_drifting_clients() -> list[dict]:
    drifting = []
    for client in get_active_clients():
        touch = get_last_touch(client['id'])
        threshold = TIER_THRESHOLDS[client['tier']]  # From §17.2

        if touch['freshness_days'] > threshold:
            # Check for scheduled future touchpoint
            future = get_future_events(client['id'], days=14)

            drifting.append({
                'client_id': client['id'],
                'client_name': client['name'],
                'tier': client['tier'],
                'last_touch': touch['date'],
                'threshold_days': threshold,
                'drift_days': touch['freshness_days'] - threshold,
                'has_scheduled': len(future) > 0,
                'next_scheduled': future[0]['date'] if future else None
            })

    return sorted(drifting, key=lambda x: (-x['tier'], -x['drift_days']))
```

**Drift severity:**
| Drift Days | Severity | Display |
|------------|----------|---------|
| 1-7 over threshold | Warning | Yellow |
| 8-14 over threshold | High | Orange |
| 15+ over threshold | Critical | Red |

#### Drilldowns
- Communication → Thread detail
- Commitment → Source communication + linked task
- Client drift → Client 360

---

### 17.5 Capacity & Calendar

**URL:** `#domain/capacity`

**Sections:**

#### Utilization by Lane
| Lane | Allocated | Capacity | Utilization | Status |
|------|-----------|----------|-------------|--------|
| {lane} | X hrs | Y hrs | X/Y % | 🟢/🟡/🔴 |

Status thresholds:
- 🟢 Healthy: < 80%
- 🟡 Warning: 80-100%
- 🔴 Overload: > 100%

#### Upcoming Week View
- **Blocked time:** Meetings, focus blocks, OOO
- **Demand:** Tasks due this week (estimated hours)
- **Conflicts:** Overlapping events, double-booked slots
- **Time debt:** Rolled-over tasks from previous weeks

**Blocked time calculation:**
```python
def get_blocked_hours(assignee: str, week_start: date) -> float:
    events = get_calendar_events(assignee, week_start, week_start + timedelta(days=7))

    blocked = 0
    for event in events:
        if event['type'] in ('meeting', 'focus_block', 'ooo', 'appointment'):
            blocked += event['duration_hours']

    return blocked
```

**Time debt definition:**
```python
def get_time_debt(assignee: str) -> dict:
    """
    Time debt = hours from overdue tasks that should have been done.
    Represents work that "rolled over" and compounds current demand.
    """
    overdue_tasks = get_tasks(
        assignee=assignee,
        due_date__lt=today,
        status__ne='done'
    )

    debt_hours = sum(t.get('estimated_hours', 2) for t in overdue_tasks)  # Default 2h if no estimate

    return {
        'hours': debt_hours,
        'task_count': len(overdue_tasks),
        'oldest_task_date': min(t['due_date'] for t in overdue_tasks) if overdue_tasks else None
    }
```

#### Reality Gap

**Hour sources:**
| Source | Calculation |
|--------|-------------|
| **Capacity** | `lanes.weekly_hours` for assignee's lane (default: 40) |
| **Blocked time** | Sum of calendar event durations (meetings, focus, OOO) |
| **Available** | `Capacity - Blocked time` |
| **Demand (scheduled)** | Sum of `estimated_hours` for tasks due this week |
| **Demand (debt)** | Sum of `estimated_hours` for overdue tasks (time debt) |
| **Total demand** | `Scheduled + Debt` |
| **Gap** | `Total demand - Available` |

**Reality gap calculation:**
```python
def calc_reality_gap(assignee: str, week_start: date) -> dict:
    capacity = get_lane_capacity(assignee)  # Weekly hours from lane config
    blocked = get_blocked_hours(assignee, week_start)
    available = max(0, capacity - blocked)

    # This week's tasks
    scheduled_tasks = get_tasks(
        assignee=assignee,
        due_date__gte=week_start,
        due_date__lt=week_start + timedelta(days=7),
        status__ne='done'
    )
    scheduled_hours = sum(t.get('estimated_hours', 2) for t in scheduled_tasks)

    # Overdue tasks (time debt)
    debt = get_time_debt(assignee)

    total_demand = scheduled_hours + debt['hours']
    gap = total_demand - available

    return {
        'capacity': capacity,
        'blocked': blocked,
        'available': available,
        'scheduled_hours': scheduled_hours,
        'debt_hours': debt['hours'],
        'total_demand': total_demand,
        'gap': gap,
        'status': 'feasible' if gap <= 0 else 'tight' if gap <= 8 else 'unrealistic'
    }
```

| Gap | Status | Action |
|-----|--------|--------|
| ≤ 0 | Feasible | On track |
| 1-8 hrs | Tight | Monitor, may need reprioritization |
| > 8 hrs | Unrealistic | Requires scope cut or deadline shift |

#### Drilldowns
- Lane → Tasks filtered by lane
- Day → Calendar view for that day
- Overload → Task reprioritization view

---

### 17.6 Data Confidence

**URL:** `#domain/data`

**Sections:**

#### Gate Status
All gates with current pass/fail status:

| Gate | Status | Last Change | Impact |
|------|--------|-------------|--------|
| data_integrity | ✓ Pass | 2026-02-03 | Blocking |
| client_coverage | ✗ Fail (62%) | 2026-02-03 | Degrade |
| ... | ... | ... | ... |

#### Coverage Metrics
| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Client link coverage | 62% | 80% | -18% |
| Commitment ready | 34.6% | 50% | -15.4% |
| Project brand coverage | 100% | 100% | ✓ |

#### Resolution Queue Summary
| Priority | Count | Oldest |
|----------|-------|--------|
| P1 | X | Y days |
| P2 | X | Y days |

Link to full resolution queue.

#### Drilldowns
- Gate → Gate detail (what's failing, remediation)
- Coverage metric → Items contributing to gap
- Queue → Resolution queue page

---

## 18. Exec Moves Engine

### 18.1 Purpose

Measurement without recommendation is reporting. The Moves engine transforms snapshot state into **3 prioritized actions** with rationale, confidence, and drill-down - bridging observation to execution.

### 18.2 Move Structure

```json
{
  "moves": [
    {
      "id": "m-001",
      "rank": 1,
      "title": "Chase Acme Corp invoice #1042",
      "rationale": "90+ days overdue ($12K), largest AR exposure, client health still good (72) - high recovery probability",
      "confidence": 0.85,
      "impact": {
        "domain": "cash",
        "metric": "ar_90_plus",
        "delta": -12000
      },
      "action_type": "communication",
      "suggested_action": {
        "type": "email",
        "to": "billing@acmecorp.com",
        "subject": "Invoice #1042 - 90 days overdue",
        "body_template": "ar_followup_90"
      },
      "drill_url": "#domain/cash?invoice=inv-1042",
      "source_risks": ["r-001"],
      "approval_options": ["send_email", "create_task", "copy_to_clipboard", "dismiss"]
    }
  ],
  "generated_at": "2026-02-03T09:00:35Z",
  "snapshot_id": "2026-02-03T09:00:00Z"
}
```

### 18.3 Move Generation Algorithm

```python
def generate_moves(snapshot: dict, max_moves: int = 3) -> list[dict]:
    """
    Generate top N moves from snapshot state.

    Pipeline:
    1. Determine domain confidence from gates
    2. Collect candidate moves from non-blocked domains only
    3. Tag moves with confidence labels
    4. Score and rank candidates (degraded moves penalized)
    5. Dedupe (no two moves on same entity)
    6. Return top N with rationale
    """
    gates = {g['name']: g['passed'] for g in snapshot['gates']['items']}
    candidates = []

    # Collect from each domain generator (skip blocked domains)
    domain_generators = {
        'cash': generate_cash_moves,
        'delivery': generate_delivery_moves,
        'clients': generate_client_moves,
        'comms': generate_comms_moves,
        'capacity': generate_capacity_moves
    }

    for domain, generator in domain_generators.items():
        confidence = get_domain_confidence(domain, gates)

        # Blocked domains generate NO moves
        if confidence == 'blocked':
            continue

        domain_moves = generator(snapshot)

        # Tag each move with confidence
        for move in domain_moves:
            move['data_confidence'] = confidence
            if confidence == 'degraded':
                move['confidence_note'] = get_confidence_note(domain, confidence, gates)

        candidates.extend(domain_moves)

    # Score and rank (degraded moves get 20% penalty in calc_move_score)
    scored = [(calc_move_score(m, snapshot), m) for m in candidates]
    scored.sort(key=lambda x: -x[0])

    # Dedupe by entity
    seen_entities = set()
    final = []
    for score, move in scored:
        entity_key = f"{move['entity_type']}:{move['entity_id']}"
        if entity_key not in seen_entities:
            move['score'] = score
            final.append(move)
            seen_entities.add(entity_key)
        if len(final) >= max_moves:
            break

    # Add rank
    for i, move in enumerate(final):
        move['rank'] = i + 1

    return final
```

**Move confidence rules:**
| Domain Confidence | Move Behavior |
|-------------------|---------------|
| `reliable` | Generate normally, full score |
| `degraded` | Generate with warning, 20% score penalty |
| `blocked` | **Do not generate moves** |

Moves carry `data_confidence` and `confidence_note` fields for dashboard display.

### 18.4 Domain Move Generators

#### Cash Moves
```python
def generate_cash_moves(snapshot: dict) -> list[dict]:
    moves = []
    cash = snapshot['domains']['cash']['metrics']

    # Move: Chase severe AR
    if cash['ar_90_plus'] > 0:
        # Get top invoice in 90+ bucket
        invoice = get_top_ar_invoice(bucket='90+')
        client = get_client(invoice['client_id'])

        moves.append({
            'title': f"Chase {client['name']} invoice #{invoice['number']}",
            'rationale': f"90+ days overdue (${invoice['amount']:,}), "
                        f"{'high' if client['health_score'] > 60 else 'uncertain'} recovery probability",
            'confidence': 0.85 if client['health_score'] > 60 else 0.5,
            'impact': {'domain': 'cash', 'metric': 'ar_90_plus', 'delta': -invoice['amount']},
            'action_type': 'communication',
            'entity_type': 'invoice',
            'entity_id': invoice['id'],
            'suggested_action': {
                'type': 'email',
                'template': 'ar_followup_90',
                'to': client['billing_email']
            }
        })

    # Move: Address AR concentration
    if cash['concentration_top_client_pct'] > 40:
        moves.append({
            'title': "Diversify AR concentration risk",
            'rationale': f"Top client is {cash['concentration_top_client_pct']}% of AR - "
                        "accelerate invoicing to other clients or chase secondary balances",
            'confidence': 0.6,
            'impact': {'domain': 'cash', 'metric': 'concentration', 'delta': -10},
            'action_type': 'decision',
            'entity_type': 'portfolio',
            'entity_id': 'ar_concentration'
        })

    return moves
```

#### Delivery Moves
```python
def generate_delivery_moves(snapshot: dict) -> list[dict]:
    moves = []
    delivery = snapshot['domains']['delivery']['metrics']

    # Move: Unblock off-track project
    if delivery['projects_off_track'] > 0:
        project = get_worst_project()  # Lowest chain health + most overdue
        blockers = get_project_blockers(project['id'])

        moves.append({
            'title': f"Unblock {project['name']}",
            'rationale': f"{len(blockers)} blockers, {project['overdue_count']} overdue tasks, "
                        f"chain health {project['chain_health']:.0f}%",
            'confidence': 0.7,
            'impact': {'domain': 'delivery', 'metric': 'projects_off_track', 'delta': -1},
            'action_type': 'task',
            'entity_type': 'project',
            'entity_id': project['id'],
            'suggested_action': {
                'type': 'create_task',
                'title': f"Resolve blockers for {project['name']}",
                'subtasks': [b['description'] for b in blockers[:3]]
            }
        })

    # Move: Clear overdue spike
    if delivery['overdue_tasks'] > 5:
        moves.append({
            'title': f"Triage {delivery['overdue_tasks']} overdue tasks",
            'rationale': "Overdue count above threshold - batch review to close, reschedule, or escalate",
            'confidence': 0.8,
            'impact': {'domain': 'delivery', 'metric': 'overdue_tasks', 'delta': -delivery['overdue_tasks']},
            'action_type': 'review',
            'entity_type': 'task_batch',
            'entity_id': 'overdue_triage'
        })

    return moves
```

#### Client Moves
```python
def generate_client_moves(snapshot: dict) -> list[dict]:
    moves = []

    # Move: Rescue critical client
    critical_clients = get_clients_by_health(max_score=40)
    if critical_clients:
        client = critical_clients[0]
        drivers = get_health_drivers(client['id'])

        moves.append({
            'title': f"Rescue {client['name']} relationship",
            'rationale': f"Health score {client['health_score']} (critical). "
                        f"Drivers: {', '.join(drivers[:2])}",
            'confidence': 0.65,
            'impact': {'domain': 'clients', 'metric': 'clients_below_50', 'delta': -1},
            'action_type': 'outreach',
            'entity_type': 'client',
            'entity_id': client['id'],
            'suggested_action': {
                'type': 'schedule_call',
                'subject': f"Check-in with {client['name']}",
                'talking_points': drivers
            }
        })

    # Move: Re-engage drifting client
    drifting = get_drifting_clients()
    if drifting:
        client = drifting[0]
        moves.append({
            'title': f"Re-engage {client['client_name']}",
            'rationale': f"No touch in {client['drift_days'] + client['threshold_days']} days "
                        f"(tier {client['tier']} threshold: {client['threshold_days']}d)",
            'confidence': 0.75,
            'impact': {'domain': 'clients', 'metric': 'clients_drifting', 'delta': -1},
            'action_type': 'outreach',
            'entity_type': 'client',
            'entity_id': client['client_id']
        })

    return moves
```

#### Comms Moves
```python
def generate_comms_moves(snapshot: dict) -> list[dict]:
    moves = []
    comms = snapshot['domains']['comms']['metrics']

    # Move: Clear response backlog
    if comms['response_overdue'] > 0:
        oldest = get_oldest_response_overdue()
        moves.append({
            'title': f"Respond to {oldest['from_name']}",
            'rationale': f"Response {oldest['days_overdue']} days overdue, "
                        f"client tier {oldest['client_tier']}",
            'confidence': 0.9,
            'impact': {'domain': 'comms', 'metric': 'response_overdue', 'delta': -1},
            'action_type': 'communication',
            'entity_type': 'communication',
            'entity_id': oldest['id'],
            'suggested_action': {
                'type': 'reply',
                'thread_id': oldest['thread_id']
            }
        })

    # Move: Track untracked commitment
    if comms['commitments_untracked'] > 0:
        commitment = get_untracked_commitments()[0]
        moves.append({
            'title': f"Create task for: \"{commitment['text'][:50]}...\"",
            'rationale': f"Commitment made {commitment['created_at']}, deadline {commitment['deadline']}, "
                        "no task tracking delivery",
            'confidence': 0.85,
            'impact': {'domain': 'comms', 'metric': 'commitments_untracked', 'delta': -1},
            'action_type': 'task',
            'entity_type': 'commitment',
            'entity_id': commitment['id'],
            'suggested_action': {
                'type': 'create_task',
                'title': commitment['text'][:80],
                'due_date': commitment['deadline'],
                'link_commitment': commitment['id']
            }
        })

    return moves
```

#### Capacity Moves
```python
def generate_capacity_moves(snapshot: dict) -> list[dict]:
    moves = []
    capacity = snapshot['domains']['capacity']['metrics']

    # Move: Address overloaded lane
    overloaded = [l for l in capacity['lanes'] if l['utilization'] > 100]
    if overloaded:
        lane = max(overloaded, key=lambda x: x['utilization'])
        moves.append({
            'title': f"Rebalance {lane['name']} lane ({lane['utilization']}%)",
            'rationale': f"{lane['allocated']}h allocated vs {lane['capacity']}h capacity - "
                        "reschedule or reassign tasks",
            'confidence': 0.7,
            'impact': {'domain': 'capacity', 'metric': 'overloaded_lanes', 'delta': -1},
            'action_type': 'decision',
            'entity_type': 'lane',
            'entity_id': lane['name'],
            'suggested_action': {
                'type': 'review_tasks',
                'filter': f"lane={lane['name']}&due_date=next_7d"
            }
        })

    # Move: Address reality gap
    if capacity['reality_gap_hours'] > 8:
        moves.append({
            'title': f"Cut scope: {capacity['reality_gap_hours']}h gap this week",
            'rationale': "Demand exceeds available hours - identify tasks to defer or delegate",
            'confidence': 0.75,
            'impact': {'domain': 'capacity', 'metric': 'reality_gap_hours', 'delta': -capacity['reality_gap_hours']},
            'action_type': 'decision',
            'entity_type': 'capacity',
            'entity_id': 'reality_gap'
        })

    return moves
```

### 18.5 Move Scoring

```python
def calc_move_score(move: dict, snapshot: dict) -> float:
    """
    Score a move 0-100 based on:
    - Impact magnitude (40%)
    - Action confidence (30%)
    - Urgency (20%)
    - Domain priority (10%)

    Then apply data confidence penalty if degraded.
    """
    score = 0

    # Impact (0-40)
    impact = move.get('impact', {})
    if impact.get('domain') == 'cash':
        # Cash impact scaled by amount
        amount = abs(impact.get('delta', 0))
        score += min(amount / 1000, 40)  # $40K = max impact score
    else:
        # Other domains: flat impact based on metric improvement
        score += 20 if impact.get('delta') else 10

    # Action confidence (0-30) - how likely is this move to succeed
    score += move.get('confidence', 0.5) * 30

    # Urgency from source risks (0-20)
    source_risks = move.get('source_risks', [])
    if source_risks:
        risk_scores = [get_risk_score(r, snapshot) for r in source_risks]
        avg_risk = sum(risk_scores) / len(risk_scores)
        score += (avg_risk / 100) * 20
    else:
        score += 10  # Default moderate urgency

    # Domain priority (0-10)
    domain_weights = {'cash': 10, 'delivery': 8, 'clients': 7, 'comms': 5, 'capacity': 4}
    score += domain_weights.get(impact.get('domain', ''), 3)

    base_score = min(score, 100)

    # Data confidence penalty
    # Degraded data = 20% penalty (move might be based on incomplete picture)
    if move.get('data_confidence') == 'degraded':
        return base_score * 0.8

    return base_score
```

**Score interpretation with confidence:**
| Score Range | Data Confidence | Recommendation |
|-------------|-----------------|----------------|
| 70-100 | reliable | Strong move, act now |
| 70-100 | degraded | Likely good move, verify data first |
| 40-69 | reliable | Moderate move, consider timing |
| 40-69 | degraded | Uncertain, improve data before acting |
| < 40 | any | Low priority, defer |

### 18.6 Approval Flow

Moves are recommendations, not auto-executions. Dashboard presents approval options:

| Option | Action | Result |
|--------|--------|--------|
| **Execute** | Perform suggested action | Email sent / task created / meeting scheduled |
| **Create Task** | Convert to tracked task | Task in delivery queue with move context |
| **Copy to Clipboard** | Export move details | Text/JSON for manual action |
| **Dismiss** | Mark as declined | Logged, excluded from next cycle |
| **Snooze** | Defer to next cycle | Re-evaluated with fresh snapshot |

**Approval logging:**
```json
{
  "move_id": "m-001",
  "decision": "execute",
  "decided_at": "2026-02-03T09:15:00Z",
  "decided_by": "moh",
  "result": {
    "success": true,
    "action_taken": "email_sent",
    "reference_id": "email-12345"
  }
}
```

### 18.7 Integration with Snapshot

Moves are generated after snapshot and appended:

```python
def run_cycle():
    # 1. Collect data
    collect_all()

    # 2. Normalize
    normalize()

    # 3. Generate snapshot
    snapshot = generate_snapshot()

    # 4. Generate moves from snapshot
    moves = generate_moves(snapshot)
    snapshot['moves'] = moves

    # 5. Write output
    write_json('output/snapshot.json', snapshot)
```

Dashboard reads `snapshot.moves` and renders the "Top 3 Moves" card on Home page.

---

## Appendix A: Deferred Items

1. **Time Blocks / Scheduling** - Tabled
2. **Nightly Rollover** - Depends on time blocks
3. **Live Xero Integration** - Manual seed only
4. **Multi-user Permissions** - Single-user

---

*End of Specification v4.11*
