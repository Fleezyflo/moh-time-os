# Phase D: Polish

**Priority:** Ship last — low-severity cleanup, test coverage, docs, observability.
**Estimated PRs:** 1-2

---

## Scope

Nothing here blocks production or features. It's all low-severity: dead references, missing tests, observability endpoints, documentation, performance micro-optimization.

## Work Items

### Cleanup

**Stale Clawdbot references (GAP-08-01)**
4 stale comment references to Clawdbot in `cron_tasks.py` (2), `autonomous_loop.py` (1), `notifier/__init__.py` (1). Remove or update.

**Stale docstring (GAP-12-03)**
`unified_intelligence.py` docstring references "parallel V4 and V5" but V5 is independent. Update to reflect reality.

**all_users_runner.py cleanup (GAP-09-03)**
If not resolved in Phase A, delete if orphaned or wire if needed.

### Test Coverage

**Collector tests (GAP-09-04)**
No dedicated tests for xero, gmail, tasks, drive, or contacts collectors. Create test files covering: init, happy path sync, API error handling, data transformation.

Files: `tests/test_xero_collector.py`, `tests/test_gmail_collector.py`, `tests/test_tasks_collector.py`, `tests/test_drive_collector.py`, `tests/test_contacts_collector.py` (all create)

### Observability

**Performance profiling endpoint (GAP-11-02)**
PerformanceMonitor and QueryOptimizer exist but aren't API-accessible. Add `/api/v2/intelligence/performance` exposing cache stats, slow queries, N+1 detections, baselines.

Files: `api/intelligence_router.py`

**Config debug endpoint (GAP-12-06)**
Add `/api/debug/config` returning: CORS origins (masked), middleware stack, collector intervals, rate limits. No secrets exposed.

Files: `api/server.py`

**Scheduled compliance reports (GAP-11-07)**
Add compliance report generation to RetentionScheduler's periodic tasks. Store snapshots for audit trail.

Files: `lib/governance/retention_scheduler.py`

### UI

**404 catch-all route (GAP-12-01)**
No catch-all route in `router.tsx`. Add NotFound page with link back to inbox.

Files: `time-os-ui/src/pages/NotFound.tsx` (create), `time-os-ui/src/router.tsx`

### Performance

**Cache O(1) fix (GAP-11-03)**
`InMemoryCache._touch()` uses `list.remove()` (O(n)). Replace with `OrderedDict` for O(1) LRU.

Files: `lib/intelligence/performance_scale.py`

### Documentation

**Pagination variance (GAP-13-02)**
Domain-specific list responses diverge from PaginatedResponse without documentation. Add docstrings or ADR.

Files: `api/response_models.py` or `docs/adr/`

**Standalone bandit command (GAP-11-05)**
Document `bandit -r lib/ api/ -c pyproject.toml` for manual security audits.

Files: `docs/` or README

## Done When

- Zero grep hits for "Clawdbot" or "clawdbot" in codebase
- Stale docstring corrected
- 5 new collector test files created matching existing test patterns
- `/api/v2/intelligence/performance` endpoint exists returning cache and query stats
- `/api/debug/config` endpoint exists returning non-secret config
- Compliance scheduling wired
- 404 route in router.tsx with NotFound page
- `InMemoryCache._touch()` uses OrderedDict for O(1) LRU
- Pagination variance documented in docstrings or ADR
- Bandit standalone command documented
