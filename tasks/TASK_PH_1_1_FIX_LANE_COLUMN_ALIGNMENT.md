# TASK: Fix lane vs lane_id Column Alignment
> Brief: PIPELINE_HARDENING | Phase: 1 | Sequence: 1.1 | Status: PENDING

## Context

The `tasks` table has column `lane_id`, but 2 modules query `t.lane`:
- `lib/lane_assigner.py` line 194: `SELECT t.id, t.title, t.source, t.tags, t.lane,`
- `lib/agency_snapshot/capacity_command_page7.py` lines 506, 519, 532: `SELECT t.id, t.title, t.lane, ...`

This causes `sqlite3.OperationalError: no such column: t.lane` when lane_assigner or capacity snapshot runs.

## Objective

Align all code references to use `lane_id` (the actual column name), or add `lane` as an alias column. Preferred: update code to use `lane_id` since that's what the DB has.

## Instructions

1. Search for all references to `t.lane` or `tasks.lane` (excluding `lane_id`):
   ```bash
   grep -rn "t\.lane[^_]" lib/ --include="*.py"
   grep -rn "tasks\.lane[^_]" lib/ --include="*.py"
   ```

2. In each file, replace `t.lane` or column reference `lane` with `lane_id`:
   - `lib/lane_assigner.py`: line 194 `t.lane` → `t.lane_id`
   - `lib/agency_snapshot/capacity_command_page7.py`: all SQL queries referencing `t.lane` → `t.lane_id`

3. Check for any Python-side references like `row["lane"]` or `task["lane"]` and update to `row["lane_id"]` / `task["lane_id"]`.

4. Verify the NamedTuple / dataclass fields in capacity_command_page7.py — if there's a `lane` field being populated from SQL, update the query alias: `t.lane_id AS lane` (preserves Python-side field name).

## Preconditions
- [ ] Brief 6 (Test Remediation) complete

## Validation
1. `grep -rn "t\.lane[^_]" lib/ --include="*.py"` returns empty OR all are aliased `AS lane`
2. `python3 -c "from lib.lane_assigner import LaneAssigner"` succeeds
3. `pytest tests/ -q` — no regressions

## Acceptance Criteria
- [ ] No raw `t.lane` references without alias
- [ ] lane_assigner.py queries `lane_id`
- [ ] capacity_command_page7.py queries `lane_id`
- [ ] No test regressions

## Output
- Modified: `lib/lane_assigner.py`
- Modified: `lib/agency_snapshot/capacity_command_page7.py`
- Possibly modified: other files found by grep
