# TASK: Fix lane column reference in lane_assigner.py
> Brief: AUDIT_REMEDIATION | Priority: P0 | Sequence: P0.1 | Status: PENDING

## Context

`lib/lane_assigner.py:190` references `t.lane` in a SQL query, but the schema column is `lane_id`. This will produce a runtime SQL error when the lane assignment query runs.

## Objective

Fix the column reference from `t.lane` to `t.lane_id` and verify no other stale column references exist.

## Instructions

1. Open `lib/lane_assigner.py`, line 190:
   ```sql
   SELECT t.id, t.title, t.source, t.tags, t.lane,
   ```
   Change `t.lane` → `t.lane_id`

2. Grep the entire codebase for other `t.lane` references that aren't `t.lane_id`:
   ```
   grep -rn 't\.lane[^_]' lib/ api/ engine/
   ```
   Fix any additional occurrences.

## Preconditions
- [ ] None

## Validation
1. `grep -rn 't\.lane[^_]' lib/` — zero results referencing the column (comments OK)
2. `ruff check lib/lane_assigner.py` — clean
3. `bandit -r lib/lane_assigner.py` — clean
4. `python -m pytest tests/ -k lane` — passes

## Acceptance Criteria
- [ ] `t.lane` replaced with `t.lane_id` at line 190
- [ ] No other stale `t.lane` column references in codebase
- [ ] ruff, bandit clean

## Output
- Modified: `lib/lane_assigner.py`

## Estimate
10 minutes
