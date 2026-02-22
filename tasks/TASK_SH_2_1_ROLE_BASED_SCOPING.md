# SH-2.1: Role-Based Endpoint Scoping

## Objective
Gate every API endpoint by role: admin (full access), operator (read + write), viewer (read-only). Enforce at the middleware level so no endpoint can accidentally bypass access control.

## Context
Current endpoints use `@Depends(require_auth)` or `@Depends(optional_auth)` — binary yes/no. After SH-1.1, every key has a role. This task enforces what each role can do.

## Implementation

### Role Definitions
| Role | Read | Write | Admin |
|------|------|-------|-------|
| viewer | ✅ All GET endpoints | ❌ | ❌ |
| operator | ✅ All GET endpoints | ✅ POST/PUT/PATCH (data operations) | ❌ |
| admin | ✅ All GET endpoints | ✅ All write operations | ✅ Key management, config, dangerous ops |

### Endpoint Classification
```python
# Decorator-based scoping
def require_role(minimum_role: str):
    """Require at least this role level."""
    role_hierarchy = {"viewer": 0, "operator": 1, "admin": 2}
    def dependency(key_info: APIKeyInfo = Depends(authenticate)):
        if role_hierarchy.get(key_info.role, -1) < role_hierarchy[minimum_role]:
            raise HTTPException(403, f"Requires {minimum_role} role")
        return key_info
    return Depends(dependency)

# Usage:
@app.get("/api/v1/snapshot", dependencies=[require_role("viewer")])
@app.post("/api/v1/resolution/{id}/approve", dependencies=[require_role("operator")])
@app.post("/api/v1/keys/generate", dependencies=[require_role("admin")])
```

### Endpoint Audit
Every endpoint in `api/server.py`, `api/spec_router.py`, `api/intelligence_router.py` must be classified:
- GET endpoints → viewer minimum
- POST/PUT/PATCH data endpoints → operator minimum
- DELETE, key management, config → admin minimum
- /health and /metrics → no auth (operational monitoring)

### Middleware Enforcement
```python
@app.middleware("http")
async def enforce_auth(request, call_next):
    # Skip auth for: /health, /metrics, /docs, /openapi.json
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    # All other paths require valid key
    # (Individual endpoint decorators handle role checks)
```

## Validation
- [ ] Viewer key can GET all endpoints
- [ ] Viewer key gets 403 on POST/PUT/DELETE
- [ ] Operator key can read + write data
- [ ] Operator key gets 403 on admin endpoints (key management)
- [ ] Admin key has full access
- [ ] /health and /metrics accessible without auth
- [ ] No endpoint accidentally unprotected (audit script)

## Files Modified
- `api/auth.py` — add require_role dependency
- `api/server.py` — classify all endpoints
- `api/spec_router.py` — classify all endpoints
- `api/intelligence_router.py` — classify all endpoints

## Estimated Effort
Medium — ~150 lines of role logic + audit of all endpoints
