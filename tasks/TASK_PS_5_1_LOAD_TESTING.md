# PS-5.1: Load Testing + Performance Baselines

## Objective
Establish performance baselines, run load tests, and create a regression detection system so performance degradation is caught early.

## Implementation

### Performance Baselines
Measure and record for every endpoint:
```
| Endpoint | p50 | p95 | p99 | Max | Target |
|----------|-----|-----|-----|-----|--------|
| GET /health | - | - | - | - | <50ms |
| GET /snapshot | - | - | - | - | <500ms |
| GET /clients | - | - | - | - | <200ms |
| GET /signals | - | - | - | - | <200ms |
| GET /patterns | - | - | - | - | <300ms |
| GET /cost-to-serve | - | - | - | - | <500ms |
| Dashboard home (all data) | - | - | - | - | <1000ms |
```

### Load Test Script
```python
# scripts/load_test.py
import asyncio
import httpx
import time
import statistics

async def load_test(url: str, concurrency: int, duration_sec: int):
    """Hit endpoint with N concurrent requests for M seconds."""
    results = []
    async with httpx.AsyncClient() as client:
        async def worker():
            while time.time() < end_time:
                start = time.time()
                resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                elapsed = (time.time() - start) * 1000
                results.append({"status": resp.status_code, "ms": elapsed})

        end_time = time.time() + duration_sec
        await asyncio.gather(*[worker() for _ in range(concurrency)])

    # Report
    latencies = [r["ms"] for r in results if r["status"] == 200]
    errors = [r for r in results if r["status"] != 200]
    print(f"Requests: {len(results)}, Errors: {len(errors)}")
    print(f"p50: {statistics.median(latencies):.0f}ms")
    print(f"p95: {sorted(latencies)[int(len(latencies)*0.95)]:.0f}ms")
    print(f"p99: {sorted(latencies)[int(len(latencies)*0.99)]:.0f}ms")
```

### Load Test Scenarios
1. **Baseline**: 1 concurrent user, all endpoints, record response times
2. **Light load**: 10 concurrent users, 60 seconds, all GET endpoints
3. **Medium load**: 50 concurrent users, 120 seconds, hot endpoints only
4. **Spike test**: 0 → 100 users in 10 seconds, measure degradation
5. **Sustained**: 20 concurrent users, 30 minutes, watch for memory leaks

### Regression Detection
- Store baseline results in `performance_baselines.json`
- CI step (if added): run light load test, fail if p95 > 2x baseline
- Manual: compare after each brief's changes

## Validation
- [ ] Baseline recorded for all critical endpoints
- [ ] Load test script runs successfully
- [ ] 50 concurrent requests/sec sustained for 2 minutes without 5xx errors
- [ ] No memory leaks detected over 30-minute sustained test
- [ ] Dashboard home loads in <1 second under light load
- [ ] Performance baselines documented

## Files Created
- `scripts/load_test.py`
- `performance_baselines.json`

## Estimated Effort
Medium — ~200 lines load test script + systematic measurement
