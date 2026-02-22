# TASK: Populate Project brand_ids
> Brief: PIPELINE_HARDENING | Phase: 3 | Sequence: 3.1 | Status: PENDING

## Context

The `project_brand_required` gate in `lib/gates.py` (lines 71-73) checks that projects have a `brand_id`. Currently only 40/354 projects have `brand_id` populated, causing 89% gate failure. This blocks the pipeline from advancing projects past the gates stage.

The `brands` table exists (check with `SELECT * FROM brands`). Projects can be matched to brands via:
- Client relationship: project → client → known brand
- Asana project name patterns containing brand names
- Direct brand assignment from Xero invoice data

## Objective

Populate `brand_id` for ≥90% of active projects.

## Instructions

1. Assess current state:
   ```sql
   SELECT COUNT(*) FROM projects WHERE brand_id IS NOT NULL;  -- currently 40
   SELECT COUNT(*) FROM projects;  -- 354
   SELECT COUNT(*) FROM brands;
   SELECT * FROM brands LIMIT 20;
   ```

2. Strategy A — Client-based brand inheritance:
   ```sql
   -- Projects inherit brand from their client's primary brand
   UPDATE projects
   SET brand_id = (
       SELECT b.id FROM brands b
       JOIN clients c ON c.id = projects.client_id
       WHERE b.client_id = c.id
       LIMIT 1
   )
   WHERE brand_id IS NULL AND client_id IS NOT NULL;
   ```

3. Strategy B — If brands table has no client_id linkage, derive from project names:
   ```sql
   -- Match brand name appearing in project name
   UPDATE projects
   SET brand_id = (
       SELECT b.id FROM brands b
       WHERE LOWER(projects.name) LIKE '%' || LOWER(b.name) || '%'
       LIMIT 1
   )
   WHERE brand_id IS NULL;
   ```

4. Strategy C — Create a default "Unassigned" brand for remaining projects to unblock the gate:
   ```sql
   INSERT OR IGNORE INTO brands (id, name) VALUES ('brand_default', 'Unassigned');
   UPDATE projects SET brand_id = 'brand_default' WHERE brand_id IS NULL;
   ```

5. Choose the strategy that matches the actual brands table schema. Investigate before running.

6. If `brand_id` can't reach 90% through data-driven matching, consider whether the gate threshold should be lowered. Document the decision.

## Preconditions
- [ ] PH-2.1 complete (missing tables created)

## Validation
1. `SELECT COUNT(*) FROM projects WHERE brand_id IS NOT NULL` ≥ 318 (90% of 354)
2. `python3 -c "from lib.gates import *"` succeeds
3. Gate check no longer blocks on brand_id for matched projects
4. `pytest tests/ -q` — no regressions

## Acceptance Criteria
- [ ] ≥90% of projects have brand_id populated
- [ ] Brand assignment logic documented in commit message
- [ ] No test regressions

## Output
- Modified: live DB (projects.brand_id populated)
- Possibly created: script for brand population (for reproducibility)
