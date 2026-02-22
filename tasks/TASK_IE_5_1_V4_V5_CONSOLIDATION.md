# IE-5.1: V4/V5 Architecture Consolidation

## Objective
Merge the V4 (artifact-signal-issue) and V5 (signal-balance-pattern) architectures into a single unified model, eliminating duplicate tables, competing signal stores, and parallel computation.

## Context
V4 and V5 are both complete, functioning architectures that compute overlapping data independently:
- V4: `artifacts` → `signals_v4` → `issues_v4`
- V5: `signals_v5` → `balance_scores` → `patterns_v5`

Both store signals, both compute risk scores, both feed separate dashboards. Neither knows about the other. This creates data inconsistency and maintenance burden.

## Implementation

### Unified Model Design
```
signals (unified) → insights → actions
```

- **signals**: Every computed metric from any source. One table, typed by domain.
- **insights**: Patterns, trajectories, and risk scores derived from signals. Replaces both V4 issues and V5 patterns.
- **actions**: Recommended or automated responses. Feeds resolution queue.

### Migration Strategy
1. Create unified `signals` table with superset schema
2. Create unified `insights` table replacing `issues_v4` and `patterns_v5`
3. Write migration to copy V4 signals → unified signals
4. Write migration to copy V5 signals → unified signals (dedup on overlap)
5. Update all consumers to read from unified tables
6. Deprecate V4/V5 parallel tables (don't delete — mark as legacy)

### Unified Signal Schema
```sql
CREATE TABLE signals_unified (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,  -- time, commitment, capacity, client, financial
    metric TEXT NOT NULL,  -- task_completion_rate, email_response_time, etc
    entity_type TEXT NOT NULL,  -- project, client, team_member
    entity_id TEXT NOT NULL,
    value REAL NOT NULL,
    previous_value REAL,
    direction TEXT,  -- improving, declining, stable
    severity TEXT,  -- critical, warning, info, normal
    computed_at TEXT NOT NULL,
    cycle_id TEXT,
    source TEXT NOT NULL,  -- truth_module, pattern_engine, trajectory
    metadata_json TEXT  -- flexible additional data
);
```

### Consumer Updates
- Agency snapshot reads from `signals_unified` + `insights`
- Pattern engine writes to `insights`
- Trajectory computer writes to `signals_unified`
- Dashboard API serves from unified tables
- Resolution queue reads from `insights` with severity filter

## Validation
- [ ] Unified tables contain all data from both V4 and V5
- [ ] No duplicate signals after migration
- [ ] All consumers updated to read unified tables
- [ ] Dashboard serves data from unified source
- [ ] V4/V5 tables marked legacy but not deleted
- [ ] No regression in signal counts or insight generation

## Files Modified
- `lib/db/migrations/` — new migration for unified tables
- Multiple lib modules that reference V4 or V5 tables
- `api/server.py` — endpoints serve from unified tables
- Agency snapshot builder

## Estimated Effort
Large — ~400 lines of migration + consumer updates across many files
