# MOH Time OS — Engineering Gap Report
## Logging, Error Handling & Tooling Audit

**Date:** 2026-03-02
**Scope:** Full backend + frontend stack
**Severity scale:** CRITICAL (blocks production) · HIGH (causes failures) · MEDIUM (causes friction) · LOW (cleanup)

---

## 1. Logging: Built But Never Turned On

The observability module (`lib/observability/logging.py`) has a well-designed structured logging system — JSON formatter, rotating file handler, correlation ID injection, human-readable dev formatter. **None of it activates.**

### CRITICAL: `configure_logging()` is never called

- **Location:** `api/server.py:5255-5267` — `main()` goes straight to `uvicorn.run()` with no logging setup.
- **Impact:** Server runs with Python's default `basicConfig`. No JSON output, no file rotation, no correlation IDs in log lines, no explicit log level control.
- **Fix:** One line in `main()` before `uvicorn.run()`:
  ```python
  configure_logging(level=os.getenv("LOG_LEVEL", "INFO"), json_format=not os.getenv("DEV_MODE"))
  ```

### HIGH: SSE error handlers missing stack traces

- **Location:** `api/sse_router.py` lines 159, 177, 216 — three `logger.error(f"... {e}")` calls without `exc_info=True`.
- **Impact:** Stream errors lose their stack trace. You see "SSE stream error: [object]" with no way to trace the cause.

### MEDIUM: Log level mismatches

- `server.py:154` — detector startup failure logged at INFO with a `[WARN]` prefix in the message string. Should be `logger.warning()`.
- `server.py:2643` — "Failed to update" logged at INFO. Should be WARNING.

### MEDIUM: 90 modules have no logger

Most `lib/` modules follow `logger = logging.getLogger(__name__)` consistently (205 of 295 files). But 90 modules — including `lib/capacity_truth/__init__.py`, `lib/collectors/tasks.py`, `lib/notifier/digest.py`, `lib/intelligence/scoring.py` — have no logger at all. Errors in these modules either bubble up silently or get caught by a parent with no context about the originating module.

### What's working well

- intelligence_router.py uses `logger.exception()` (39 instances) — best practice, auto-includes exc_info.
- spec_router.py and server.py use `exc_info=True` in 13+ error handlers.
- CorrelationIdMiddleware IS mounted (`server.py:78`) — request IDs propagate via context vars.
- No silent exception swallowing found anywhere. Zero bare `except: pass`.

---

## 2. Error Handling: Three Systems, No Contract

### CRITICAL: No error code catalog

There is no enum, constants file, or documented set of error codes. Each endpoint invents its own:

- `server.py:182` returns `{"error": "ui_build_missing"}`
- `spec_router.py:573` returns `detail={"error": "transition_failed", "message": ...}`
- `intelligence_router.py:20` defaults to literal string `"ERROR"`

The frontend (`api.ts:113`) compensates with a triple-fallback: `body.detail || body.error || body.message`. This is fragile — the next endpoint that puts the message in a different field breaks silently.

### CRITICAL: Three incompatible error response schemas

| Schema | Where used | Shape |
|--------|-----------|-------|
| IntelligenceResponse envelope | intelligence_router, some spec_router | `{status: "error", error: msg, error_code: "ERROR"}` at HTTP 200 |
| HTTPException | spec_router, server.py | `{detail: string_or_dict}` at HTTP 4xx/5xx |
| JSONResponse | server.py:182 | `{error: code, hint: msg}` at arbitrary status |

The frontend `ApiError` class only tracks HTTP status code. It has no `error_code` field and cannot differentiate between a 404 "client not found" and a 404 "UI build missing."

### HIGH: No global exception handler

- **Location:** `server.py` — zero `@app.exception_handler` decorators.
- **Impact:** Any unhandled exception (KeyError, AttributeError, import error) becomes a raw 500 with the default FastAPI traceback. No structured error response, no correlation ID, no error code.

### HIGH: Same 500 for different failure modes

20+ endpoints in spec_router.py catch `(sqlite3.Error, ValueError)` and return `HTTPException(status_code=500, detail=str(e))`. This means:

- Database constraint violation → 500
- NULL pointer in Python → 500
- Missing table → 500
- Transient lock contention → 500

The frontend can't distinguish transient from permanent errors. Retry logic is impossible. Alert rules can't filter noise.

### What's working well

- intelligence_router's `_error_response()` helper is the closest thing to a standard pattern.
- spec_router catches specific exception types (`sqlite3.Error`, `ValueError`, `HTTPException`) — not bare `except:`.
- `raise ... from e` exception chaining used in 20+ locations.

---

## 3. Tooling: What's There vs What's Missing

### Already configured and running

| Tool | Status | Notes |
|------|--------|-------|
| ruff (lint + format) | ✅ Full | Handles imports, style, security rules |
| bandit | ✅ Full | Security scanning in CI + pre-commit |
| mypy | ⚠️ Partial | Baseline mode, `ignore_missing_imports=true`, no strict enforcement |
| pytest + pytest-cov | ✅ Full | 40% coverage threshold, nightly runs |
| semgrep | ✅ Full | Custom rules in `.semgrep/`, PR-blocking |
| pip-audit | ✅ Full | Dependency vuln scanning in CI + nightly |
| vulture | ✅ Nightly | Dead code detection, advisory |
| mutmut | ✅ Nightly | Mutation testing, lib/safety only |
| TypeScript strict | ✅ Full | `strict: true`, `noUnusedLocals`, `noUnusedParameters` |
| ESLint | ⚠️ Partial | Missing accessibility plugin |
| Prettier | ✅ Full | In pre-commit and CI |
| Vitest | ⚠️ Partial | Configured but `environment: 'node'` (should be jsdom), no CI integration |
| Bundle budget | ✅ Full | 650KB JS, 100KB CSS, custom check script |
| Custom tracing | ✅ Local | W3C traceparent, context propagation — no remote exporter |

### Missing: Production readiness gaps

| Gap | Severity | What to add |
|-----|----------|-------------|
| **No error tracking service** | CRITICAL | Sentry or Rollbar — centralized error aggregation with dedup, alerting, release tracking |
| **No accessibility linting** | HIGH | `eslint-plugin-jsx-a11y` — catches missing alt text, broken ARIA, keyboard traps |
| **No E2E tests** | HIGH | Playwright or Cypress — validate actual user flows end-to-end |
| **No metrics export** | HIGH | Prometheus scrape endpoint — custom Counter/Gauge classes exist but aren't exposed |
| **No DB backup strategy** | HIGH | SQLite backup tooling, recovery procedure, integrity checks |
| **mypy not strict** | MEDIUM | `ignore_missing_imports=true` and no `disallow_untyped_defs` — types are optional in practice |
| **Vitest misconfigured** | MEDIUM | Environment is `node` instead of `jsdom` — React component tests can't mount |
| **No docstring linting** | MEDIUM | pydocstyle or ruff's D-rules — enforce param documentation |
| **No complexity limits** | MEDIUM | Enable ruff McCabe (C901) with max-complexity threshold |
| **40% coverage threshold** | MEDIUM | Low for a production system — especially `lib/safety/` which gets mutation testing but regular coverage is low |
| **No OpenTelemetry** | LOW | Custom tracing works locally but won't export to Jaeger/Datadog in production |
| **No visual regression** | LOW | No Percy/Chromatic for UI screenshot diffs |
| **No slow query logging** | LOW | No SQLite query timing or EXPLAIN plan analysis |

---

## 4. The Schedule/Capacity 500s — Root Cause

The browser logs you shared show all capacity and schedule endpoints returning 500. Based on the code audit:

**Endpoints failing:** `/api/capacity/lanes`, `/api/capacity/utilization`, `/api/capacity/forecast`, `/api/capacity/debt`, `/api/week`, `/api/notifications/stats`

**All defined in:** `api/server.py` (lines 456-512, 2848-2854, 2942-2948)

**All use:** Lazy imports of `lib/capacity_truth` and `lib/time_truth` modules inside route handlers.

**Most likely cause:** The backend server (uvicorn on port 8420) is either not running or hitting a runtime error in these modules. Because there's no global exception handler and `configure_logging()` is never called, you get a raw 500 with no structured error in the response and potentially no server-side log either.

**To diagnose:** Start the backend and curl each endpoint directly:
```bash
curl -s http://localhost:8420/api/capacity/lanes | python -m json.tool
curl -s http://localhost:8420/api/capacity/utilization | python -m json.tool
curl -s http://localhost:8420/api/week | python -m json.tool
curl -s http://localhost:8420/api/notifications/stats | python -m json.tool
```

The FastAPI dev mode response body will include the traceback.

**Also failing:** `GET /api/v2/events/stream` returns 404. The route exists in `sse_router.py:190` and is mounted at `server.py:104`. A 404 means the router failed to mount — likely an import error in sse_router.py that gets swallowed during `app.include_router()`.

---

## 5. Recommended Fix Order

**Phase A — Make errors visible (1-2 sessions):**
1. Call `configure_logging()` in `server.py:main()`
2. Add global exception handler returning structured `{error_code, message, request_id}`
3. Add `exc_info=True` to SSE error handlers
4. Fix log level mismatches

**Phase B — Standardize error responses (2-3 sessions):**
1. Create `api/errors.py` with error code enum and unified `ErrorResponse` model
2. Refactor 20+ catch blocks in spec_router.py to use specific codes (NOT_FOUND, VALIDATION_ERROR, DATABASE_ERROR, CONFLICT)
3. Update `fetchJson` in api.ts to extract `error_code` and expose it on `ApiError`
4. Add error code to observability metrics

**Phase C — Close tooling gaps (2-3 sessions):**
1. Add `eslint-plugin-jsx-a11y` to frontend
2. Fix Vitest environment to jsdom, add component test examples
3. Enable ruff McCabe complexity rules
4. Tighten mypy to strict mode incrementally
5. Raise coverage threshold to 60%+

**Phase D — Production observability (future):**
1. Sentry integration for error tracking
2. Prometheus metrics endpoint
3. OpenTelemetry exporter for distributed tracing
4. DB backup automation + integrity checks
