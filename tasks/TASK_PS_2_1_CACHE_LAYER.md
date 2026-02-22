# PS-2.1: In-Memory Cache Layer

## Objective
Add a TTL-based in-memory cache for expensive computations — snapshots, truth values, cost-to-serve, pattern results — so repeated API calls don't recompute on every request.

## Context
Every API call hits SQLite directly. Snapshot generation involves dozens of queries across 80+ tables. Truth module outputs don't change between cycles. Cost-to-serve is expensive to recompute. Caching these with a TTL matching the cycle interval eliminates redundant work.

## Implementation

### Cache Module
```python
# lib/cache.py
import time
from threading import Lock

class TTLCache:
    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._store:
                expires_at, value = self._store[key]
                if time.time() < expires_at:
                    return value
                del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int | None = None):
        with self._lock:
            self._store[key] = (time.time() + (ttl or self.default_ttl), value)

    def invalidate(self, pattern: str | None = None):
        """Invalidate matching keys, or all keys if no pattern."""
        with self._lock:
            if pattern is None:
                self._store.clear()
            else:
                self._store = {k: v for k, v in self._store.items() if pattern not in k}

# Singleton
cache = TTLCache(default_ttl=300)  # 5 min default
```

### Cache Integration Points
| Endpoint | Cache Key | TTL | Invalidation |
|----------|-----------|-----|--------------|
| GET /snapshot | `snapshot:latest` | 5 min | On cycle_complete |
| GET /health | `health:status` | 30 sec | On cycle_complete |
| GET /signals | `signals:{filters_hash}` | 5 min | On cycle_complete |
| GET /patterns | `patterns:{filters_hash}` | 5 min | On cycle_complete |
| GET /cost-to-serve | `cts:{client_id}` | 15 min | On cycle_complete |
| GET /trajectories | `traj:{metric}:{entity}` | 15 min | On cycle_complete |

### Cache Invalidation
- On `cycle_complete` event: invalidate all cached data
- On manual trigger: `POST /api/v1/cache/invalidate` (admin only)
- TTL expiry: automatic for stale data between cycles
- Cache-Control headers: `Cache-Control: max-age=300, must-revalidate`

### Decorator Pattern
```python
def cached(key_template: str, ttl: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = key_template.format(**kwargs)
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
```

## Validation
- [ ] Cached endpoints return same data on repeated calls (cache hit)
- [ ] Cache invalidates on cycle_complete
- [ ] TTL expiry works (stale data refreshed)
- [ ] Manual invalidation via admin endpoint works
- [ ] Response time improves for cached endpoints (measure)
- [ ] Thread-safe under concurrent access

## Files Created/Modified
- New: `lib/cache.py`
- `api/server.py` — wire cache into endpoints
- `lib/autonomous_loop.py` — invalidate cache on cycle complete

## Estimated Effort
Medium — ~150 lines cache module + ~100 lines integration
