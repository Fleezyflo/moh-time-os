# TASK: Link Orphaned Projects to Tasks via Asana GID Matching
> Brief: DATA_FOUNDATION | Phase: 2 | Sequence: 2.3 | Status: PENDING

## Context

305 of 354 projects (86%) have zero tasks linked. Meanwhile, 3,542 Asana tasks exist with `source_id` (Asana GID) and `project` (project name string). The `asana_project_map` table has 36 entries mapping project names to Asana GIDs.

The disconnect: tasks have `project_id = NULL` because the normalizer that should link `task.project` (name string) → `projects.id` isn't running or is incomplete. Tasks also have `project_link_status = 'unlinked'`.

Three linking strategies are available:
1. **Asana GID match:** task has `_project_gid` from collection → match to `projects.asana_project_id`
2. **Name match:** task has `project` (name string) → fuzzy match to `projects.name_normalized`
3. **Asana project map:** `asana_project_map` table has explicit mappings

## Objective

Link orphaned tasks to their parent projects using all three matching strategies, and update `project_link_status` accordingly.

## Instructions

1. Read the task and project schemas. Check `lib/` for existing normalizer/linker code.
2. Create `lib/task_project_linker.py` with:
   - `link_by_asana_gid(db_path)`: Match tasks where source='asana' to projects via Asana GID
   - `link_by_name(db_path)`: Fuzzy match task.project → projects.name_normalized
   - `link_by_map(db_path)`: Use asana_project_map for explicit mappings
   - `link_all(db_path)`: Run all three in priority order (GID > map > name)
   - Each function: UPDATE tasks SET project_id=X, project_link_status='linked' WHERE ...
   - Also cascade `client_id` from the matched project: UPDATE tasks SET client_id = (SELECT client_id FROM projects WHERE id = tasks.project_id)
3. Add CLI command: `timeos link-tasks [--dry-run]`
4. Write tests covering each linking strategy
5. Run: `pytest tests/ -q`

## Preconditions
- [ ] Task DF-1.1 complete (Asana sync fixed)
- [ ] Test suite passing

## Validation
1. `SELECT COUNT(*) FROM tasks WHERE project_id IS NOT NULL` increases significantly
2. `SELECT COUNT(*) FROM projects p WHERE EXISTS (SELECT 1 FROM tasks t WHERE t.project_id = p.id)` > 100
3. `SELECT COUNT(*) FROM tasks WHERE client_id IS NOT NULL` increases
4. All tests pass

## Acceptance Criteria
- [ ] Three linking strategies implemented in priority order
- [ ] Tasks correctly linked to projects
- [ ] Client IDs cascaded from projects to tasks
- [ ] `project_link_status` updated to 'linked'
- [ ] Dry-run mode available
- [ ] All tests pass
- [ ] No guardrail violations

## Output
- New: `lib/task_project_linker.py`
- New: `tests/test_task_project_linker.py`
- Modified: CLI file

## On Completion
- Update HEARTBEAT: Task DF-2.3 complete — N tasks linked to projects, M projects now have tasks
- Record: task link rate, project coverage

## On Failure
- If name matching produces too many false positives, use higher threshold and document in Blocked
