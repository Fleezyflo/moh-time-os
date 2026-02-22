# AO-1.1: Harden Autonomous Loop

## Objective
Add error recovery, exponential backoff, circuit breakers, and graceful degradation to `lib/autonomous_loop.py` so it survives any single-point failure without crashing.

## Context
The autonomous loop (882 lines) runs the full pipeline: collect → normalize → truth → snapshot → notify. Currently, if any step throws an exception, the entire cycle dies. No retry, no backoff, no isolation between steps. A single API timeout in collection kills truth computation and notification delivery.

## Implementation

### Per-Job Isolation
```python
class JobResult:
    job_name: str
    status: str  # "success" | "partial" | "failed" | "skipped"
    duration_ms: int
    error: str | None
    items_processed: int

class CycleResult:
    cycle_id: str
    started_at: str
    finished_at: str
    jobs: list[JobResult]

    @property
    def healthy(self) -> bool:
        return all(j.status in ("success", "partial") for j in self.jobs)
```

Each job in the cycle runs in its own try/except. A failed collector doesn't prevent truth computation on existing data. A failed truth module doesn't prevent snapshot generation from cached data.

### Backoff Strategy
- Job failure → retry once after 30s
- Second failure → skip job this cycle, schedule retry next cycle
- 3 consecutive cycle failures for same job → circuit break, alert via Google Chat
- Circuit reset after 5 successful cycles

### Graceful Degradation
- If collectors fail: truth modules run on stale data, snapshot notes staleness
- If truth modules fail: snapshot uses last-known-good truth values
- If snapshot fails: notification sends "degraded" alert instead of full brief
- If notification fails: log error, continue loop (non-blocking)

### Health State
```python
class LoopHealth:
    consecutive_failures: dict[str, int]  # job_name → count
    last_successful_cycle: str | None
    circuit_broken_jobs: set[str]
    degraded: bool
```

## Validation
- [ ] Single job failure doesn't crash the cycle
- [ ] Retry fires once on first failure
- [ ] Circuit breaker opens after 3 consecutive failures
- [ ] Degraded mode produces snapshot with staleness warnings
- [ ] CycleResult logged with full job status breakdown
- [ ] Loop recovers automatically when failed service returns

## Files Modified
- `lib/autonomous_loop.py` — major refactor of cycle execution

## Estimated Effort
Large — ~200 lines of new isolation/recovery logic in a complex 882-line file
