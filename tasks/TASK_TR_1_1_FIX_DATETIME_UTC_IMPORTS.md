# TASK: Fix datetime.UTC Imports for Python 3.10 Compatibility
> Brief: TEST_REMEDIATION | Phase: 1 | Sequence: 1.1 | Status: PENDING

## Context

`datetime.UTC` was introduced in Python 3.11. Our environment runs Python 3.10.12. 26 source files use `from datetime import UTC`, causing ImportError at collection time for 14 test modules and runtime failures for 20+ more.

The canonical Python 3.10 equivalent is `datetime.timezone.utc`. Both are identical objects — `UTC` is just an alias added for convenience in 3.11.

## Objective

Replace all `from datetime import UTC` with the 3.10-compatible `datetime.timezone.utc` across the entire codebase.

## Instructions

1. Create a compatibility shim at `lib/compat.py`:
   ```python
   """Python 3.10/3.11+ compatibility shims."""
   from datetime import timezone

   UTC = timezone.utc
   ```

2. Replace `from datetime import UTC` in all 26 files:

   **Pattern:** Change `from datetime import UTC, datetime, timedelta, timezone` → `from datetime import datetime, timedelta, timezone` + add `from lib.compat import UTC` (or inline `UTC = timezone.utc`).

   **Simpler alternative:** In each file, replace the import line to use `timezone.utc` directly and replace all references to `UTC` with `timezone.utc`. Choose whichever pattern results in cleaner diffs.

   **Files (26 total):**
   - `lib/status_engine.py`
   - `lib/scheduling_engine.py`
   - `lib/state_tracker.py`
   - `lib/priority_engine.py`
   - `lib/projects.py`
   - `lib/heartbeat_processor.py`
   - `lib/delegation_engine.py`
   - `lib/entity_linker.py`
   - `lib/config_store.py`
   - `lib/conflicts.py`
   - `lib/change_bundles.py`
   - `lib/safety/utils.py`
   - `lib/observability/logging.py`
   - `lib/observability/health.py`
   - `lib/collectors/calendar.py`
   - `lib/collectors/all_users_runner.py`
   - `lib/delegation_graph.py`
   - `collectors/scheduled_collect.py`
   - `collectors/gmail_multi_user.py`
   - `engine/tasks_discovery.py`
   - `engine/financial_pulse.py`
   - `engine/heartbeat_pulse.py`
   - `engine/knowledge_base.py`
   - `engine/chat_discovery.py`
   - `engine/discovery.py`
   - `cli/tasks_reset.py`

3. After replacing, run:
   ```
   python -c "from datetime import timezone; UTC = timezone.utc; print(UTC)"
   ```
   Confirm it works on 3.10.

4. Run `grep -r "from datetime import UTC" lib/ engine/ collectors/ cli/ api/` — should return 0 results.

## Preconditions
- [ ] None — this is the first task

## Validation
1. `grep -r "from datetime import UTC" lib/ engine/ collectors/ cli/ api/` returns empty
2. `python -c "import lib.observability"` succeeds (was blocked by UTC)
3. `python -c "import lib.safety"` succeeds (was blocked by UTC)
4. `python -c "import lib.collectors.calendar"` succeeds (was blocked by UTC)
5. `pytest tests/test_audit.py tests/test_safety.py -q --co` — collection succeeds (no import errors)
6. `pytest tests/ -q` — collection errors reduced by ≥8

## Acceptance Criteria
- [ ] Zero files contain `from datetime import UTC`
- [ ] All 26 files use `timezone.utc` (directly or via compat shim)
- [ ] No behavioral changes — `timezone.utc` is identical to `UTC`
- [ ] Previously-blocked test modules now collect successfully

## Output
- Modified: 26 source files
- Optionally new: `lib/compat.py` (if using shim pattern)
