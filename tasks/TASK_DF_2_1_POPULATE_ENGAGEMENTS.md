# TASK: Populate Engagements Table from Project Data
> Brief: DATA_FOUNDATION | Phase: 2 | Sequence: 2.1 | Status: PENDING

## Context

The `engagements` table has a well-designed schema (project/retainer with full state machine) but contains 0 rows. Meanwhile, the `projects` table has 354 rows with an `engagement_type` column already populated: 340 projects, 11 retainers, 3 campaigns. These two systems need to be connected.

Engagements represent the commercial relationship between hrmny and a client for a specific body of work. Projects are the operational units within engagements. This distinction matters for revenue attribution and client health tracking.

Schema: `engagements(id, client_id, brand_id, name, type [project|retainer], state, asana_project_gid, asana_url, started_at, completed_at, created_at, updated_at)`

## Objective

Create a migration script that populates the `engagements` table from existing project data, establishing the engagement → project relationship.

## Instructions

1. Read the `engagements` table schema and the `projects` table data.
2. Create `lib/migrations/populate_engagements.py`:
   - For each project with `engagement_type` in ('project', 'retainer'):
     - Create an engagement with `name = project.name`, `client_id = project.client_id`, `brand_id = project.brand_id`, `type = project.engagement_type` (map 'campaign' to 'project').
     - Set `state` based on `project.status`: active → active, completed → completed, etc.
     - Copy `asana_project_id` to `asana_project_gid`.
   - For retainers: group projects by `(client_id, brand_id)` where `engagement_type = 'retainer'` into a single engagement per client+brand combo.
3. Add a foreign key or reference column on `projects` pointing to the engagement: `engagement_id TEXT REFERENCES engagements(id)`.
4. Write tests verifying the migration:
   - All 354 projects map to an engagement
   - Retainers are grouped correctly
   - State mapping is correct
5. Run: `pytest tests/ -q`

## Preconditions
- [ ] Phase 1 complete
- [ ] Test suite passing
- [ ] `engagements` table exists (schema already in place)

## Validation
1. `SELECT COUNT(*) FROM engagements` > 0 after migration
2. `SELECT COUNT(*) FROM projects WHERE engagement_id IS NULL` = 0 (or documented exceptions)
3. All tests pass

## Acceptance Criteria
- [ ] Engagements table populated from project data
- [ ] Retainers grouped by client+brand
- [ ] Projects linked back to engagements
- [ ] Migration is idempotent (safe to re-run)
- [ ] All tests pass
- [ ] No guardrail violations

## Output
- New: `lib/migrations/populate_engagements.py`
- New: `tests/test_populate_engagements.py`
- Modified: `projects` table (new `engagement_id` column if not present)

## On Completion
- Update HEARTBEAT: Task DF-2.1 complete — Engagements populated, N engagements created
- Record: table row count change, schema change

## On Failure
- If `projects` table is missing `engagement_id` column and ALTER TABLE fails, document in Blocked
