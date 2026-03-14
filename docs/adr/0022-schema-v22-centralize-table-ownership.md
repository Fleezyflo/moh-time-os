# ADR-0022: Schema v22 — Centralize All Table Ownership in schema.py

## Status
Accepted

## Context
Seven service and intelligence modules created tables at runtime via `_ensure_tables()` methods containing `CREATE TABLE IF NOT EXISTS`. This masked column drift: if `lib/schema.py` defined a table with 11 columns but the runtime DDL created it with 19, whichever ran first won and `schema_engine.converge()` could never detect the mismatch. The `proposals_v4` table had a split-brain definition (different primary key and column sets in `schema.py` vs `proposal_service.py`).

Affected files: `signal_service.py`, `issue_service.py`, `proposal_service.py`, `coupling_service.py`, `drift_detection.py`, `signal_suppression.py`, `engagement_lifecycle.py`.

## Decision
1. Migrate all runtime-created tables into `lib/schema.py` as the single source of truth.
2. Delete all `_ensure_tables()` methods from service constructors.
3. Extend `schema_engine._build_create_sql()` to support composite primary keys (needed by `drift_baselines`).
4. Add regression tests that source-scan all 7 files to prevent reintroduction of runtime DDL.
5. Bump schema version to 22.

## Consequences
- `schema_engine` is now the sole schema owner. No service creates tables at runtime.
- `converge()` can detect and fix column drift on all tables.
- 63 regression tests enforce the contract (source scans, column checks, index verification, INSERT simulations).
- Any future table additions must go through `schema.py` or CI will fail.
