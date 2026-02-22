# TASK: Gmail Historical Backfill
> Brief: DATA_FOUNDATION | Phase: 1 | Sequence: 1.2 | Status: PENDING

## Context

The Gmail collector (`lib/collectors/gmail.py`) exists and works — but has only captured 255 messages, all from Feb 11-12, 2026. This appears to be a single test run. Gmail is the primary external communication channel for client relationships.

Database state: `gmail_messages` has 255 rows. `artifacts` has 2,856 Gmail artifacts but the raw messages table is nearly empty. The system's entity linking and communication gap detection is blind without email history.

Config shows Gmail was disabled in the last discovery run:
```json
{"include": {"gmail": false, "calendar": true, "tasks": true, "chat": false}}
```

## Objective

Configure and execute a historical Gmail backfill covering at minimum the last 6 months, and enable Gmail in the ongoing sync schedule.

## Instructions

1. Read `lib/collectors/gmail.py` to understand the current collection logic.
2. Read `engine/gogcli.py` to understand the Google API client configuration.
3. Check if there are date-range or pagination parameters for the Gmail collector.
4. Update `config_kv` to set `gmail: true` in the discovery include config.
5. If the collector has a date-range parameter, configure it for 6-month lookback.
6. If the collector lacks historical backfill capability, add a `since` parameter that accepts an ISO date string and translates to Gmail's `after:` query parameter.
7. Test the collector locally with a dry-run (verify API connectivity without writing to DB if possible).
8. Run existing tests: `pytest tests/ -q`

## Preconditions
- [ ] Task DF-1.1 complete (or can run in parallel if independent)
- [ ] Google API credentials are configured (check `.env` or `config/`)
- [ ] Test suite passing

## Validation
1. Gmail collector code has a `since` or date-range parameter
2. `config_kv` shows `gmail: true` in the include config
3. `pytest tests/ -q` all pass
4. Collector can be invoked without error (even if actual API call requires credentials)

## Acceptance Criteria
- [ ] Gmail collector supports historical backfill with configurable date range
- [ ] Gmail is enabled in the ongoing sync configuration
- [ ] No test regressions
- [ ] No guardrail violations

## Output
- Modified: `lib/collectors/gmail.py`
- Modified: config (via `config_kv` table or config file)
- Possibly modified: `engine/gogcli.py`

## On Completion
- Update HEARTBEAT: Task DF-1.2 complete — Gmail collector supports historical backfill, enabled in sync config
- Note: Actual backfill execution requires API credentials at runtime

## On Failure
- If Google API credentials are not available in this environment, document what's needed in Blocked
- The code changes should still be made even if the actual sync can't run here
