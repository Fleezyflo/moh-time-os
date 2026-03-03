# Brief 10: AUTONOMOUS_OPERATIONS
> **Objective:** Harden the autonomous loop into a production-grade self-healing engine with error recovery, change tracking, rollback capability, observability, and comprehensive test coverage.
>
> **Why now:** The autonomous loop (`lib/autonomous_loop.py`, 882 lines) is a real engine but has zero tests, no error recovery, no backoff strategy, and never calls the rollback infrastructure in `lib/change_bundles.py`. After Brief 9 fills the data pipeline with rich data, the loop must be bulletproof before it runs unattended.

## Scope

### What This Brief Does
1. **Autonomous loop hardening** — backoff/retry, circuit breakers, graceful degradation per job
2. **Change bundle integration** — every loop action tracked, rollback on failure
3. **Self-healing** — detect stale state, recover from partial failures, auto-restart
4. **Observability** — expose /metrics endpoint, structured logging for every loop cycle
5. **Test coverage** — autonomous_loop.py, change_bundles.py, orchestrator, truth_cycle
6. **Data lifecycle** — retention policies, archival for old sync data

### What This Brief Does NOT Do
- Expand intelligence modules (Brief 11)
- Build UI (Brief 12)
- Modify collectors (Brief 9)

## Dependencies
- Brief 9 (COLLECTOR_SUPREMACY) complete — rich data flowing into DB

## Phase Structure

| Phase | Focus | Tasks |
|-------|-------|-------|
| 1 | Loop Hardening | AO-1.1: Error recovery, backoff, circuit breakers in autonomous_loop.py |
| 2 | Change Tracking | AO-2.1: Wire change_bundles into every loop action |
| 3 | Observability | AO-3.1: Expose /metrics, structured cycle logging |
| 4 | Data Lifecycle | AO-4.1: Retention policies, archival, cleanup |
| 5 | Test Coverage | AO-5.1: Tests for loop, bundles, orchestrator, truth cycle |
| 6 | Validation | AO-6.1: 72-hour unattended run |

## Task Queue

| Seq | Task ID | Title | Status |
|-----|---------|-------|--------|
| 1 | AO-1.1 | Harden Autonomous Loop | PENDING |
| 2 | AO-2.1 | Wire Change Bundles | PENDING |
| 3 | AO-3.1 | Production Observability | PENDING |
| 4 | AO-4.1 | Data Lifecycle Management | PENDING |
| 5 | AO-5.1 | Core Test Coverage Push | PENDING |
| 6 | AO-6.1 | 72-Hour Unattended Validation | PENDING |

## Success Criteria
- Autonomous loop survives injected failures (API timeouts, DB locks, OOM)
- Every state change tracked in change_bundles with rollback capability
- /metrics endpoint returns Prometheus-compatible data
- Data older than retention window archived or purged
- Test coverage for core modules ≥80%
- 72-hour unattended run with zero manual intervention
