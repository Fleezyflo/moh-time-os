# TASK: Fix Asana Task Sync — Completed Tasks + Full Project Coverage
> Brief: DATA_FOUNDATION | Phase: 1 | Sequence: 1.1 | Status: PENDING

## Context

The Asana collector (`lib/collectors/asana.py`) has two bugs that make task tracking useless:

1. **Line 40:** `list_tasks_in_project(proj_gid, completed=False)` — only fetches incomplete tasks. Completed tasks never sync. Result: 1 of 3,946 tasks shows "done."
2. **Line 35:** `for proj in projects[:15]` — only syncs the first 15 projects. Result: 305 of 354 projects have zero tasks.

The transform logic (lines 87-92) already handles `task.get("completed")` correctly — the problem is purely in collection.

Database state: 3,946 tasks, 3,542 from Asana. Only 1 marked "done." 530 past due date but still "active."

## Objective

Make the Asana collector sync ALL tasks (completed and incomplete) across ALL projects, with `completed_at` properly populated.

## Instructions

1. Read `lib/collectors/asana.py` and `engine/asana_client.py` to understand the current flow.
2. In `asana.py` line 40, change `completed=False` to `completed=None` (or remove the filter) to fetch all tasks.
3. In `asana.py` line 35, remove the `[:15]` slice. Add pagination if the Asana client supports it, or at minimum process all projects.
4. In the `transform` method, ensure `completed_at` is populated from `task.get("completed_at")` (Asana provides this field on completed tasks).
5. Verify the task upsert logic handles status transitions (active → completed) without creating duplicates.
6. Run existing tests: `pytest tests/ -q`
7. Write a test in `tests/test_asana_collector.py` that verifies:
   - Completed tasks get `status = "completed"` and `completed_at` is populated
   - All projects are processed (no arbitrary limit)

## Preconditions
- [ ] Test suite passing before changes
- [ ] `engine/asana_client.py` accessible and has `list_tasks_in_project` function

## Validation
1. `grep -n "completed=False" lib/collectors/asana.py` returns 0 matches
2. `grep -n "[:15]" lib/collectors/asana.py` returns 0 matches
3. `pytest tests/ -q` all pass
4. New test covers completed task transform

## Acceptance Criteria
- [ ] Asana collector fetches both completed and incomplete tasks
- [ ] No arbitrary project limit — all projects are synced
- [ ] `completed_at` field populated for completed tasks
- [ ] Transform produces `status = "completed"` for done tasks
- [ ] All tests pass including new coverage
- [ ] No guardrail violations

## Output
- Modified: `lib/collectors/asana.py`
- New/Modified: `tests/test_asana_collector.py`

## On Completion
- Update HEARTBEAT: Task DF-1.1 complete — Asana collector now syncs all tasks across all projects
- Record: collector change, test count delta

## On Failure
- Document in HEARTBEAT → Blocked
- If Asana API rate limits are a concern, document the constraint and propose batching
