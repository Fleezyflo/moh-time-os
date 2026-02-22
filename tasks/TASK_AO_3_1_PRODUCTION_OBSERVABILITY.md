# AO-3.1: Production Observability

## Objective
Expose a `/metrics` endpoint with Prometheus-compatible metrics, wire structured logging for every cycle, and create a health check endpoint.

## Context
`lib/observability/` has structured logging, metrics collection, and tracing infrastructure — but no `/metrics` endpoint is exposed. The API server (`api/server.py`) has no health endpoint. Without observability, a silent failure in the autonomous loop is invisible until Molham notices stale data.

## Implementation

### /metrics Endpoint
```python
# In api/server.py
@app.get("/metrics")
def metrics():
    """Prometheus-compatible metrics export."""
    return Response(
        content=observability.metrics.export_prometheus(),
        media_type="text/plain"
    )
```

### Metrics to Expose
- `moh_cycle_total` — counter of completed cycles (labels: status=success|partial|failed)
- `moh_cycle_duration_seconds` — histogram of cycle duration
- `moh_collector_items_total` — counter per collector (labels: collector, status)
- `moh_truth_computation_seconds` — histogram per truth module
- `moh_snapshot_generation_seconds` — histogram
- `moh_notification_sent_total` — counter (labels: channel, status)
- `moh_db_size_bytes` — gauge of database file size
- `moh_last_successful_cycle_timestamp` — gauge
- `moh_circuit_breaker_status` — gauge per job (0=closed, 1=open)

### /health Endpoint
```python
@app.get("/health")
def health():
    """System health check."""
    return {
        "status": "healthy" | "degraded" | "unhealthy",
        "last_cycle": "2026-02-21T10:30:00Z",
        "cycle_age_minutes": 15,
        "circuit_breakers": {"collectors": "closed", "truth": "closed"},
        "db_size_mb": 556,
        "uptime_seconds": 86400,
    }
```

### Structured Cycle Logging
Every cycle emits a structured JSON log entry:
```json
{
    "event": "cycle_complete",
    "cycle_id": "c-20260221-103000",
    "duration_ms": 4523,
    "jobs": {
        "collect": {"status": "success", "items": 147, "duration_ms": 2100},
        "truth": {"status": "success", "items": 4, "duration_ms": 890},
        "snapshot": {"status": "success", "pages": 13, "duration_ms": 1200},
        "notify": {"status": "success", "sent": 1, "duration_ms": 333}
    },
    "degraded": false
}
```

## Validation
- [ ] GET /metrics returns valid Prometheus format
- [ ] GET /health returns current system state
- [ ] Every cycle produces structured JSON log entry
- [ ] Metrics update in real-time during cycle execution
- [ ] Health status reflects actual loop state (degraded when circuit broken)

## Files Modified
- `api/server.py` — add /metrics and /health endpoints
- `lib/observability/metrics.py` — add export_prometheus() if not present
- `lib/autonomous_loop.py` — emit structured cycle logs

## Estimated Effort
Medium — mostly wiring existing observability infrastructure to HTTP endpoints
