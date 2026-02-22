# CS-2.1: Build Collector Resilience Infrastructure

## Objective
Add retry with exponential backoff, circuit breakers, rate limiting, and partial success handling to the base collector class so all collectors inherit production-grade resilience.

## Context
Current collectors (`lib/collectors/base.py`) have no retry logic. A single API timeout kills the entire collection cycle. Rate limit errors from Google/Asana/Xero APIs cause silent failures. No collector tracks partial success — it's all-or-nothing.

## Implementation

### Enhance `lib/collectors/base.py`

```python
# Add to BaseCollector or create lib/collectors/resilience.py

class CollectorResilience:
    """Production-grade API resilience for all collectors."""

    def __init__(self, collector_name: str, config: dict | None = None):
        self.collector_name = collector_name
        self.max_retries = (config or {}).get("max_retries", 3)
        self.base_delay = (config or {}).get("base_delay", 1.0)
        self.max_delay = (config or {}).get("max_delay", 60.0)
        self.circuit_breaker_threshold = (config or {}).get("cb_threshold", 5)
        self.circuit_breaker_reset = (config or {}).get("cb_reset_seconds", 300)
        self._failure_count = 0
        self._circuit_open_until: float | None = None
        self._rate_limit_until: float | None = None

    def retry_with_backoff(self, func, *args, **kwargs):
        """Retry with exponential backoff + jitter."""
        ...

    def check_circuit_breaker(self) -> bool:
        """Return True if circuit is closed (safe to call)."""
        ...

    def record_rate_limit(self, retry_after: float):
        """Honor API rate limit headers."""
        ...

    def record_success(self):
        """Reset failure counters on success."""
        ...

    def record_failure(self, error: Exception):
        """Track failures, potentially open circuit."""
        ...
```

### Partial Success Tracking

```python
@dataclass
class CollectionResult:
    """Track what succeeded and what failed in a collection run."""
    collector_name: str
    started_at: str
    finished_at: str
    total_items: int
    successful_items: int
    failed_items: int
    errors: list[dict]  # [{endpoint, error, timestamp}]
    rate_limited: bool
    circuit_broken: bool

    @property
    def success_rate(self) -> float:
        if self.total_items == 0:
            return 0.0
        return self.successful_items / self.total_items

    @property
    def is_partial(self) -> bool:
        return 0 < self.successful_items < self.total_items
```

### Wire Into Existing Collectors
Each collector's `collect()` method wraps API calls through `resilience.retry_with_backoff()`. The orchestrator (`lib/collectors/orchestrator.py`) checks circuit breaker status before calling each collector and logs `CollectionResult` for every run.

## Validation
- [ ] Base retry works with exponential backoff (test with mock failures)
- [ ] Circuit breaker opens after N failures, auto-resets after timeout
- [ ] Rate limit headers (429 Retry-After) are honored
- [ ] Partial success — collector returns data for endpoints that succeeded
- [ ] CollectionResult logged for every run with full error detail
- [ ] Orchestrator skips circuit-broken collectors gracefully

## Files Modified
- `lib/collectors/base.py` — add resilience mixin or base class
- `lib/collectors/resilience.py` — new module (if separate)
- `lib/collectors/orchestrator.py` — wire circuit breaker checks + result logging
- `lib/collectors/asana.py` — wrap API calls
- `lib/collectors/gmail.py` — wrap API calls
- `lib/collectors/calendar.py` — wrap API calls
- `lib/collectors/xero.py` — wrap API calls

## Estimated Effort
Medium-Large — ~250 lines new code + wiring into 5 collectors
