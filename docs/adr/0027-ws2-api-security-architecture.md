# ADR 0027: API security architecture — global auth middleware, CORS, rate limiting

- Status: Accepted
- Date: 2026-06-02
- Workstream: WS2 (API Security Hardening)
- Findings: api-auth-unwired-all-routes-open (critical),
  api-hard-data-deletion-no-router-authz (high), api-cors-wildcard-credentials (high),
  api-rate-limiter-unwired (high), api-auth-test-broken-and-stale (high),
  api-public-unauthenticated-sse-event-injector (medium),
  sse-token-in-url-query-string (medium), no-rest-auth-from-client (low),
  protectedroute-noop-passthrough (low)

## Context

The entire ~285-route FastAPI surface in `api/server.py` was reachable with no
credential: `require_auth` existed but was attached to zero routes. Destructive
mutation (`DELETE /api/tasks/{id}`), GDPR SAR deletion, governance export, the
SSE event injector, and admin seeding were all unauthenticated. CORS defaulted
to `"*"` with `allow_credentials=True` (credentialed CSRF). The rate limiter was
constructed but never invoked. The auth regression tests imported a nonexistent
`create_app` and a stale "always passes" assertion.

This ADR records the security architecture because `api/server.py` is a
governance-gated file (Governance Checks → `scripts/check_adr_required.sh`).

## Decision

1. **One global ASGI `AuthMiddleware`** (`api/auth_middleware.py`) enforces a
   shared-secret Bearer token (constant-time `verify_token`) on every request
   except a small public allowlist (`is_public_path`: health, auth handshake,
   docs, static UI) and CORS `OPTIONS` preflight. This is the correct single
   enforcement layer for the many bare `@app` routes that are not mounted via a
   router, in a single-credential single-user system.

2. **Router-level `Depends(require_auth)` defense-in-depth** on every
   `include_router` (except the public auth handshake router), so a mounted
   route stays gated even if the global middleware is ever removed.

3. **CORS is an explicit allowlist.** A missing `CORS_ORIGINS` defaults to the
   Vite dev origin; `"*"` as ANY parsed element is a hard startup failure
   (Starlette sets `allow_all_origins = "*" in allow_origins`, so a single `*`
   token re-enables credentialed Origin reflection). `SecurityHeadersMiddleware`
   no longer emits `access-control-*` headers — `CORSMiddleware` is the sole
   CORS owner (no two competing header sets).

4. **`RateLimitMiddleware`** throttles write/destructive methods per client key;
   the `debug/config` `rate_limits.enabled` flag reflects actual middleware
   registration, not merely the object's existence.

5. **SSE exception.** The browser `EventSource` API cannot set request headers,
   so `GET /api/v2/events/stream` authenticates via a `?token=` query param,
   validated in-handler (`verify_token`, constant time, 401 on mismatch). That
   one exact path is exempt from `AuthMiddleware` and is mounted without the
   router-level dependency; `events/history` and `events/publish` keep
   header-based `Depends(require_auth)`. The query-token tradeoff (proxy/Referer
   log leakage) is documented at the call site; it is the only header-less path.

6. **Frontend** sends `Authorization: Bearer` from a single token source
   (`lib/auth.ts`) on every REST wrapper in BOTH `lib/api.ts` and the parallel
   `intelligence/api.ts` client; `ProtectedRoute` is a real single-user guard.

7. **CI gate.** A `Run Auth tests` step in the PR-gating `python-tests` job runs
   the 401-boundary proofs on every PR.

## Consequences

- Every destructive route returns 401 without a valid token (verified by an
  end-to-end smoke over the live app object and by `tests/test_auth_middleware.py`
  + `tests/test_auth_and_side_effects.py::TestAuthEnforcement`).
- RBACMiddleware / `require_role` remain dead (they depend on a per-request role
  no layer sets); a multi-role model would be a separate ADR, out of WS2 scope.
- Out of scope, filed separately: the chat `ActionFramework()` constructor bug,
  a pre-existing collector-error-propagation test, and the SIGNAL_CATALOG count
  test — none are API-security and none are caused by WS2.
