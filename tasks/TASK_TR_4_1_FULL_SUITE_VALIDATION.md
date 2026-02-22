# TASK: Full Test Suite Validation — Zero Failures
> Brief: TEST_REMEDIATION | Phase: 4 | Sequence: 4.1 | Status: PENDING

## Context

After TR-1.1, TR-1.2, TR-2.1, and TR-3.1, all root causes should be resolved:
- `from datetime import UTC` → replaced with `timezone.utc` (26 files)
- `from enum import StrEnum` → backported for 3.10 (16 files)
- `pydantic` + `fastapi` → installed
- `asana_project_map` test fixture → aligned with production schema

This task validates that all 58 failures are resolved and no regressions were introduced.

## Objective

Achieve a fully green test suite: 0 errors, 0 failures.

## Instructions

1. Run the full suite with verbose output:
   ```bash
   pytest tests/ -v --tb=short 2>&1 | tee /tmp/test_results.txt
   ```

2. Check for any remaining failures:
   ```bash
   grep -c "FAILED\|ERROR" /tmp/test_results.txt
   ```

3. If any tests still fail, investigate and fix. Likely causes:
   - A file was missed in TR-1.1 or TR-1.2
   - An import chain pulls in an unfixed module
   - A pydantic version incompatibility (check schema.py validators)
   - A fastapi version incompatibility (check test expectations)

4. For each remaining failure, apply the minimal fix (import shim, not logic change).

5. Run `pytest tests/ -q` — confirm 0 failures, 0 errors.

6. Record the final count:
   ```
   X passed, 0 failed, 0 errors in Y.YYs
   ```

## Preconditions
- [ ] TR-1.1 complete (UTC imports fixed)
- [ ] TR-1.2 complete (StrEnum imports fixed)
- [ ] TR-2.1 complete (pydantic + fastapi installed)
- [ ] TR-3.1 complete (asana_project_map fixture fixed)

## Validation
1. `pytest tests/ -q` exits 0
2. Output shows `X passed` with no `failed` or `error` lines
3. X ≥ 530 (current 490 collected + ~45 previously uncollectable)
4. `pytest tests/ -q --co` shows 0 collection errors

## Acceptance Criteria
- [ ] Full test suite passes with 0 failures, 0 errors
- [ ] All 14 previously-erroring modules now collect
- [ ] All 39 previously-failing tests now pass
- [ ] All 5 previously-erroring scenario tests now pass
- [ ] Total passing count documented

## On Completion
- Update HEARTBEAT:
  - Mark Brief TEST_REMEDIATION as COMPLETE
  - Update System State: Tests line with final count
  - Record: "58 failures → 0"
  - Set Active Work to awaiting next brief
- Commit all changes

## On Failure
- If specific tests still fail, document which and why in HEARTBEAT → Blocked
- Remaining failures must be traced to a root cause with a plan
- Do not mark brief complete with any failures

## Output
- Possibly modified: additional source files (if stragglers found)
- Updated: HEARTBEAT.md (brief completion)
