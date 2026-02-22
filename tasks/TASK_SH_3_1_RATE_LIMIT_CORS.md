# SH-3.1: Rate Limiting + CORS/CSP Hardening

## Objective
Add per-key rate limiting to prevent abuse, and lock down CORS/CSP headers to protect the dashboard from XSS/clickjacking.

## Context
No rate limiting exists. A single client can hammer the API, and since SQLite doesn't handle concurrent writes well, this can corrupt data or stall the system. No CORS headers means any origin can call the API. No CSP means the dashboard is vulnerable to injection.

## Implementation

### Rate Limiting
```python
# In-memory sliding window counter (no Redis needed for single-instance)
class RateLimiter:
    def __init__(self):
        self._windows: dict[str, list[float]] = {}

    def check(self, key_id: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.time()
        window = self._windows.setdefault(key_id, [])
        # Prune expired entries
        window[:] = [t for t in window if now - t < window_seconds]
        if len(window) >= limit:
            return False  # Rate limited
        window.append(now)
        return True

# Middleware integration
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    key_info = get_current_key(request)
    if key_info and not rate_limiter.check(key_info.id, key_info.rate_limit_per_min):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "60"}
        )
    return await call_next(request)
```

### CORS Configuration
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.environ.get("MOH_DASHBOARD_ORIGIN", "http://localhost:8080"),
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "X-API-Token", "Content-Type"],
)
```

### CSP Headers
```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

## Validation
- [ ] Rate-limited key gets 429 after exceeding limit
- [ ] 429 response includes Retry-After header
- [ ] CORS blocks requests from unauthorized origins
- [ ] CSP headers present on all responses
- [ ] X-Frame-Options prevents iframe embedding
- [ ] Dashboard still works with CORS properly configured
- [ ] Rate limit resets after window expires

## Files Modified
- `api/server.py` — add middleware stack
- `api/auth.py` — integrate rate limiter

## Estimated Effort
Medium — ~150 lines of middleware + config
