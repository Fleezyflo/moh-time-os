# Phase A: Production Hardening

**Priority:** Ship first — everything here makes the running system more reliable.
**Estimated PRs:** 2-3 (can split API-facing vs daemon-facing if needed)

---

## Scope

Make the production daemon, API, and collectors robust for 24/7 unattended operation. This phase touches nothing in the intelligence layer — it's purely operational.

## Work Items

### API Hardening

**Health endpoint with real checks (GAP-08-06, GAP-12-05, PR-FRESH-01)**
`/api/health` currently returns `{"status": "healthy"}` unconditionally. Wire `lib/observability/health.py` HealthReport into it — DB connectivity (SELECT 1), collector last-run times, component-level status. Return 503 on critical failures. Add `/api/ready` as a lightweight probe (no subsystem checks) for load balancer probes.

Files: `api/server.py`, `lib/observability/health.py`

**Path traversal prevention (PR-FRESH-02)**
SPA fallback in `api/server.py` doesn't validate requested paths. Add `Path.resolve()` + `is_relative_to()` check to prevent `../../etc/passwd` escapes. Return 403 for traversal attempts.

Files: `api/server.py`

**CORS production warning (GAP-08-07)**
Log a WARNING at startup when `CORS_ORIGINS=*` and environment suggests production.

Files: `api/server.py` or `lib/security/headers.py`

**Production validator expansion (GAP-08-05)**
`scripts/validate_production.py` only checks imports and DB connectivity. Add: API endpoint smoke test, daemon component init, notification system check, collector instantiation, gate evaluation dry run.

Files: `scripts/validate_production.py`

### Daemon Reliability

**Log rotation (GAP-09-05)**
`daemon.py` uses plain `FileHandler`. `configure_log_rotation()` exists in `lib/observability/logging.py` (50MB, 5 backups) but is never called. Replace FileHandler with RotatingFileHandler.

Files: `lib/daemon.py`

**Memory monitoring (GAP-09-06)**
Add periodic memory usage logging (every N cycles) using `resource.getrusage()`. Log RSS. Optionally trigger `gc.collect()` above threshold.

Files: `lib/daemon.py`

**Cycle time tracking (GAP-11-01)**
`run_cycle()` logs phase transitions but never calls `PerformanceMonitor.record_timing()`. Wire per-phase and total cycle duration into PerformanceMonitor.

Files: `lib/autonomous_loop.py`

**Service definition (GAP-09-07)**
Create macOS launchd plist with KeepAlive for auto-restart. Document installation.

Files: `ops/com.mohtime.daemon.plist` (create)

### Collector Hardening

**XeroCollector resilience (GAP-09-02)**
XeroCollector doesn't extend BaseCollector — no circuit breaker, no retry_with_backoff. Refactor to extend BaseCollector or add equivalent resilience.

Files: `lib/collectors/xero_collector.py`

**WatchdogTimer (PR-FRESH-04)**
Add `WatchdogTimer` using `signal.SIGALRM` to enforce hard time limits on collector runs. Wrap each collector sync in scheduled_collect.py.

Files: `lib/collectors/watchdog.py` (create), `lib/collectors/scheduled_collect.py`

**Stale lock detection (PR-FRESH-05)**
Enhance CollectorLock: store PID + timestamp on acquire. On failure, check if holding PID is alive (`os.kill(pid, 0)`). Break stale locks. Add TTL (30 min).

Files: `lib/collectors/scheduled_collect.py` or `lib/collectors/lock.py` (create)

**Orchestrator completeness (GAP-09-01)**
Add drive and contacts to `_init_collectors()` — currently only 6 of 8 mapped.

Files: `lib/collectors/orchestrator.py`

**all_users_runner.py (GAP-09-03)**
Investigate whether it's orphaned. Delete or wire.

Files: `lib/collectors/all_users_runner.py`

**OAuth token refresh (GAP-11-04)**
Collectors use `google.oauth2.service_account` but have no token refresh handling. Use `AuthorizedSession` for auto-refresh or add retry-on-auth-error logic.

Files: `lib/collectors/base.py`, `lib/collectors/xero_collector.py`

## Verification

- [ ] `/api/health` returns component-level status, 503 on DB failure
- [ ] `/api/ready` returns 200 in <10ms
- [ ] Path traversal returns 403
- [ ] Daemon log rotates at 50MB
- [ ] Memory usage logged every N cycles
- [ ] Cycle time appears in PerformanceMonitor
- [ ] XeroCollector has circuit breaker + retry
- [ ] WatchdogTimer kills hung collectors
- [ ] Stale locks from dead PIDs are broken
- [ ] All 8 collectors in orchestrator
- [ ] Expired OAuth tokens trigger refresh
- [ ] `validate_production.py` covers API + daemon + collectors
- [ ] All existing tests pass
- [ ] `ruff check`, `bandit -r`, `ruff format --check` clean
