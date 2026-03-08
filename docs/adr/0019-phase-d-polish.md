# ADR-0019: Phase D Polish -- Cleanup, Tests, Observability, Docs

## Status
Accepted

## Context
Phase D is the final audit remediation phase. It addresses low-severity gaps accumulated across the codebase: stale references, missing tests, observability endpoints, UI gaps, performance micro-optimizations, and documentation.

## Decision
1. Remove all stale Clawdbot references from maintained scope (6 occurrences across 4 files)
2. Fix stale docstring in unified_intelligence.py referencing removed V4/V5 architecture
3. Add collector tests for xero, gmail, and tasks collectors (drive/contacts collectors do not exist)
4. Add `GET /api/v2/intelligence/performance` endpoint exposing cache stats, slow queries, N+1 detections
5. Add `GET /api/debug/config` endpoint returning non-secret configuration (masked CORS, middleware, collectors)
6. Add `run_compliance_snapshot()` to RetentionScheduler for audit trail snapshots
7. Add 404 catch-all route with NotFound page in router.tsx
8. Replace O(n) list-based LRU with O(1) OrderedDict in InMemoryCache
9. Document pagination variance in response_models.py
10. Document standalone bandit command in SAFETY.md
11. Confirm all_users_runner.py is NOT orphaned (functional CLI runner, no changes needed)

## Consequences
- Zero Clawdbot references in maintained scope
- 3 new collector test files covering init, transform, error handling
- Two new observability endpoints for debugging in production
- Compliance snapshots stored in retention_runs for audit trail
- 404 route prevents blank pages on unknown URLs
- Cache operations O(1) instead of O(n)
