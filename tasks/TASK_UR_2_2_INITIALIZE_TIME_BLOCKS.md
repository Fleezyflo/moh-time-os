# TASK: Initialize Time Blocks from Calendar Data
> Brief: USER_READINESS | Phase: 2 | Sequence: 2.2 | Status: PENDING

## Context

The scheduler (`lib/time_truth/scheduler.py`) builds schedules from time blocks, but `time_blocks` table is empty — CalendarSync never ran against the live DB. Without time blocks, the time truth module produces empty output.

Calendar events exist in the DB (collected by `collectors/calendar_direct.py`). They need to be converted into time blocks.

## Objective

Run CalendarSync to populate `time_blocks` from existing calendar events. Verify the scheduler can produce output.

## Instructions

1. Check calendar_events exist:
   ```sql
   SELECT COUNT(*) FROM calendar_events;
   SELECT * FROM calendar_events LIMIT 5;
   ```

2. Check time_blocks is empty:
   ```sql
   SELECT COUNT(*) FROM time_blocks;
   ```

3. Read CalendarSync API:
   ```python
   from lib.time_truth.calendar_sync import CalendarSync
   # Understand: sync(), sync_range(), what it reads, what it writes
   ```

4. Run the sync:
   ```python
   cs = CalendarSync(db_path="data/moh_time_os.db")
   result = cs.sync()  # or cs.sync_range(start, end)
   ```

5. If CalendarSync fails (missing columns, wrong schema), fix the immediate issue and re-run.

6. Verify blocks were created:
   ```sql
   SELECT COUNT(*) FROM time_blocks;
   SELECT block_type, COUNT(*) FROM time_blocks GROUP BY block_type;
   ```

7. Test the scheduler can read them:
   ```python
   from lib.time_truth.scheduler import Scheduler
   s = Scheduler(db_path="data/moh_time_os.db")
   schedule = s.build_schedule(date="2026-02-21")
   print(schedule)
   ```

## Preconditions
- [ ] UR-2.1 complete (truth cycle created)
- [ ] calendar_events table has data

## Validation
1. `time_blocks` count > 0
2. Scheduler produces non-empty schedule for recent dates
3. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] time_blocks populated from calendar events
- [ ] Scheduler produces schedule output
- [ ] No test regressions

## Output
- Modified: live DB (time_blocks populated)
- Possibly modified: CalendarSync if schema fix needed
