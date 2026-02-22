# TASK: Resume Calendar + Chat Sync and Establish Cron Schedule
> Brief: DATA_FOUNDATION | Phase: 3 | Sequence: 3.2 | Status: PENDING

## Context

Calendar sync stopped on Feb 12 (38,643 events, data up to Feb 13). Chat sync also stopped Feb 12 (183,244 messages). Both collectors work — they just aren't running.

A launchd plist exists: `com.mohtimeos.api.plist` in the project root. The system has `lib/daemon.py`, `lib/cron_tasks.py`, and `run_cycle.sh` for scheduled execution.

The `config_kv` table shows the last discovery run configuration with Gmail and Chat disabled.

The system needs automated periodic collection to stay current — this is fundamental to the "always on" operator intelligence promise in the DIRECTIVE.

## Objective

Configure and verify automated sync for all collectors (Calendar, Chat, Gmail, Asana, Xero) with proper scheduling and error handling.

## Instructions

1. Read `lib/daemon.py`, `lib/cron_tasks.py`, and `run_cycle.sh` to understand existing scheduling.
2. Read `lib/collectors/orchestrator.py` to understand how collectors are invoked.
3. Update `config_kv` to enable all collectors:
   ```json
   {"include": {"gmail": true, "calendar": true, "tasks": true, "chat": true}}
   ```
4. Verify `run_cycle.sh` invokes all collectors in order.
5. Create `config/sync_schedule.yaml` if it doesn't exist:
   ```yaml
   schedules:
     asana: { interval_minutes: 30, enabled: true }
     gmail: { interval_minutes: 15, enabled: true }
     calendar: { interval_minutes: 60, enabled: true }
     chat: { interval_minutes: 60, enabled: true }
     xero: { interval_minutes: 360, enabled: true }
   ```
6. Ensure `lib/daemon.py` or `lib/cron_tasks.py` reads this config and respects it.
7. Verify the launchd plist `com.mohtimeos.api.plist` is correctly configured for macOS auto-start.
8. Add health check: if any collector hasn't run in 2x its interval, log a warning to `cycle_logs`.
9. Write tests for schedule config parsing and health check logic.
10. Run: `pytest tests/ -q`

## Preconditions
- [ ] Task DF-1.1 (Asana fix) and DF-1.2 (Gmail backfill) complete
- [ ] Test suite passing

## Validation
1. `config_kv` shows all collectors enabled
2. `run_cycle.sh` references all collectors
3. Schedule config exists and is parseable
4. Health check logic detects stale collectors
5. All tests pass

## Acceptance Criteria
- [ ] All 5 collectors enabled in config
- [ ] Sync schedule defined with per-collector intervals
- [ ] Health check alerts on stale collectors
- [ ] launchd plist verified for macOS deployment
- [ ] All tests pass
- [ ] No guardrail violations

## Output
- Modified: `config_kv` table
- New/Modified: `config/sync_schedule.yaml`
- Modified: `lib/daemon.py` or `lib/cron_tasks.py`
- Modified: `run_cycle.sh` (if needed)
- New: `tests/test_sync_schedule.py`

## On Completion
- Update HEARTBEAT: Task DF-3.2 complete — All collectors enabled, sync schedule configured
- Record: collector config state

## On Failure
- If daemon/cron code is too coupled to modify safely, document the refactor needed in Blocked
