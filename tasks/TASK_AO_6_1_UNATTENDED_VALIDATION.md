# AO-6.1: 72-Hour Unattended Validation

## Objective
Run the autonomous loop for 72 hours without manual intervention. Validate stability, error recovery, data freshness, and resource usage.

## Context
Before Brief 11 builds intelligence on top of the autonomous pipeline, we need proof it runs reliably. This is the system's stress test — 72 hours of real data collection, truth computation, snapshot generation, and notification delivery.

## Procedure

### Pre-Flight Checklist
- [ ] All Brief 9 collectors expanded and validated
- [ ] AO-1.1 error recovery in place
- [ ] AO-2.1 change bundles wired
- [ ] AO-3.1 /metrics and /health endpoints live
- [ ] AO-4.1 data lifecycle running daily
- [ ] AO-5.1 tests passing

### Monitoring During Run
Check every 12 hours (6 checkpoints):
1. `/health` returns `healthy` or `degraded` (not `unhealthy`)
2. `/metrics` shows cycles completing
3. `last_successful_cycle` timestamp within last cycle interval
4. DB size growth rate reasonable (not runaway)
5. No circuit breakers stuck open
6. Google Chat notifications delivering

### Success Criteria
- [ ] Zero crashes requiring manual restart
- [ ] ≥95% of cycles complete successfully
- [ ] Error recovery triggered and resolved automatically at least once
- [ ] Change bundles logged for every cycle
- [ ] DB size growth ≤5MB/day after lifecycle management
- [ ] /metrics endpoint responsive throughout
- [ ] Snapshot freshness ≤1 cycle age
- [ ] Google Chat notifications arrive on schedule

### Failure Protocol
If loop crashes:
1. Check logs for root cause
2. If fixable: fix, restart, reset 72-hour clock
3. If architectural: document issue, create follow-up task
4. Loop must complete 72 continuous hours to pass

## Deliverables
- 72-hour run log with cycle-by-cycle results
- Resource usage report (CPU, memory, DB growth)
- Error recovery incident log (what failed, how it recovered)
- Final health check output

## Estimated Effort
Low (active) / High (elapsed) — mostly monitoring over 3 days
