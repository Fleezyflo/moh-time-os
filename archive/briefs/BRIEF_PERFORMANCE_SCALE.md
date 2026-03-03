# Brief 14: PERFORMANCE_SCALE
> **Objective:** Eliminate performance bottlenecks, add caching, fix N+1 queries, build a PostgreSQL migration path, and establish performance baselines — so the system scales beyond single-user load.
>
> **Why now:** After Brief 13 locks down security, the system is production-accessible. But SQLite can't handle concurrent writes, N+1 queries in team endpoints degrade under load, there's no caching layer, and no path to a proper RDBMS. Before real daily use stresses the system, performance must be addressed.

## Scope

### What This Brief Does
1. **Query optimization** — fix N+1 patterns in spec_router.py, add missing indexes, optimize hot queries
2. **Caching layer** — in-memory cache for expensive computations (snapshots, truth values, cost-to-serve)
3. **PostgreSQL compatibility** — abstract DB layer to support both SQLite (dev) and PostgreSQL (production)
4. **API pagination enforcement** — ensure every list endpoint respects limits, add cursor-based pagination
5. **Async execution** — move long-running operations (collectors, analyzers) to background tasks
6. **Performance baselines** — load testing, response time targets, regression detection

### What This Brief Does NOT Do
- Build new features
- Change security model (Brief 13)
- Migrate to PostgreSQL (just build the compatibility layer)

## Dependencies
- Brief 13 (SECURITY_HARDENING) complete — auth and rate limiting in place

## Phase Structure

| Phase | Focus | Tasks |
|-------|-------|-------|
| 1 | Query Optimization | PS-1.1: Fix N+1 queries + add indexes |
| 2 | Caching | PS-2.1: In-memory cache layer for hot data |
| 3 | Database Abstraction | PS-3.1: PostgreSQL compatibility layer |
| 4 | API Performance | PS-4.1: Pagination enforcement + async operations |
| 5 | Validation | PS-5.1: Load testing + performance baselines |

## Task Queue

| Seq | Task ID | Title | Status |
|-----|---------|-------|--------|
| 1 | PS-1.1 | Fix N+1 Queries + Add Indexes | PENDING |
| 2 | PS-2.1 | In-Memory Cache Layer | PENDING |
| 3 | PS-3.1 | PostgreSQL Compatibility Layer | PENDING |
| 4 | PS-4.1 | Pagination Enforcement + Async Ops | PENDING |
| 5 | PS-5.1 | Load Testing + Performance Baselines | PENDING |

## Success Criteria
- Zero N+1 query patterns in API endpoints
- Hot endpoints (snapshot, health, signals) cached with configurable TTL
- DB layer abstraction allows switching SQLite ↔ PostgreSQL via config
- Every list endpoint paginated (default 50, max 100)
- Dashboard home loads in <1 second (from <2s target)
- Load test: 50 concurrent requests/sec sustained without errors
