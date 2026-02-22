# TASK: Bootstrap Capacity Lanes from Team Members
> Brief: DATA_FOUNDATION | Phase: 3 | Sequence: 3.3 | Status: PENDING

## Context

The `capacity_lanes` table has 0 rows. The `team_members` table has 31 people with `default_lane` assignments (mostly 'client' and 'growth'). The DIRECTIVE explicitly calls for capacity intelligence: "What does our actual capacity look like — not headcount but real bandwidth?"

Without capacity lanes, the system can't answer workload questions, detect overload patterns, or model "what if we take on this client" scenarios.

Team members with lanes:
- Molham Homsi → growth
- Ahmed Salah, Fady, Zeiad, Noura, Youssef, Tasneem, Aya, Elija → client
- Plus ~22 more team members

## Objective

Bootstrap capacity lanes from team member data and link tasks to lanes through assignee matching, enabling workload analysis.

## Instructions

1. Read `lib/capacity_truth/` for existing capacity logic.
2. Read the `capacity_lanes` schema: `id, name, display_name, owner, weekly_hours, buffer_pct, color, created_at, updated_at`
3. Create `lib/capacity_truth/lane_bootstrap.py`:
   - `bootstrap_lanes(db_path)`:
     - Extract unique `default_lane` values from `team_members`
     - Create one capacity_lane per unique lane
     - Default: weekly_hours=40, buffer_pct=0.2
     - For 'growth' lane: weekly_hours=45, buffer_pct=0.15 (operator lane, lower buffer)
   - `assign_tasks_to_lanes(db_path)`:
     - Match task.assignee → team_members.name → team_members.default_lane
     - Store lane assignment on tasks (add `lane_id` column if needed)
   - `lane_load_report(db_path)`:
     - Per lane: total tasks, active tasks, overdue tasks, team member count
     - Per person in lane: task count, overdue count
     - Return structured dict for API consumption
4. Add CLI command: `timeos lane-report`
5. Write tests
6. Run: `pytest tests/ -q`

## Preconditions
- [ ] Task DF-2.3 complete (tasks linked to projects and assigned)
- [ ] Test suite passing

## Validation
1. `SELECT COUNT(*) FROM capacity_lanes` > 0
2. Lane report shows per-person task distribution
3. All tests pass

## Acceptance Criteria
- [ ] Capacity lanes created from team member data
- [ ] Tasks mapped to lanes through assignee → team member → lane chain
- [ ] Lane load report available via CLI
- [ ] Lane config is editable (weekly_hours, buffer_pct)
- [ ] All tests pass
- [ ] No guardrail violations

## Output
- New: `lib/capacity_truth/lane_bootstrap.py`
- New: `tests/test_lane_bootstrap.py`
- Modified: CLI file (add `lane-report` command)
- Populated: `capacity_lanes` table

## On Completion
- Update HEARTBEAT: Task DF-3.3 complete — N capacity lanes created, tasks mapped to lanes
- Record: lane count, lane distribution

## On Failure
- If `default_lane` values are inconsistent or missing for team members, document the cleanup needed
