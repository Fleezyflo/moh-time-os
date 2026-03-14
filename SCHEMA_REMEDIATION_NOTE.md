# Schema/Runtime Contract Remediation — v22

## Summary

Schema version bumped from 21 to 22. All runtime SQL references now resolve
against the canonical schema in `lib/schema.py`. Fresh DB bootstrap works.
63 regression tests verify the contracts. No runtime DDL remains in any v4
service or intelligence/lifecycle module — `schema_engine` is the sole schema owner.

## Lane 1 Fixes (initial pass)

### 1. governance_history — phantom table (CRITICAL)

- **What:** `api/server.py` L2292, L3160, L5214 INSERT/SELECT `governance_history` but no schema definition existed anywhere.
- **Fix:** Added `TABLES["governance_history"]` to `lib/schema.py` with columns matching all server.py usage: id, decision_id, action, type, target_id, processed_by, side_effects, created_at.
- **Verification:** `test_governance_history_exists`, `test_governance_history_insert`, `test_governance_history_query`.

### 2. Six fixture-only views — missing in production (CRITICAL)

- **What:** `v_task_with_client`, `v_client_operational_profile`, `v_project_operational_state`, `v_person_load_profile`, `v_communication_client_link`, `v_invoice_client_project` existed only in `tests/fixtures/fixture_db.py`. `lib/query_engine.py` uses them in 50+ queries — production calls crash on fresh DB.
- **Fix:** Promoted all 6 views into `schema.VIEWS` dict. `schema_engine.create_fresh()` and `schema_engine.converge()` now create them. Removed duplicate definitions from `fixture_db.py`.
- **Verification:** 6 individual view queryable tests, `test_views_not_only_in_fixture`, `test_converge_creates_views`.

### 3. signals table column mismatch (HIGH)

- **What:** `TABLES["signals"]` had 11 columns. `lib/v4/signal_service.py` runtime DDL created 17 columns. Runtime DDL masked the drift.
- **Fix:** Extended `TABLES["signals"]` to 19 columns matching the full v4 column set.
- **Verification:** `test_signals_columns_complete`, `test_signals_insert_v4_columns`, `test_signals_resolve_update`.

### 4. V4 service tables missing from schema (HIGH)

- **What:** `signal_definitions`, `detector_versions`, `detector_runs`, `signal_feedback`, `issue_signals`, `issue_evidence`, `decision_log`, `handoffs` — all created at runtime but absent from `lib/schema.py`.
- **Fix:** Added all 8 tables to `lib/schema.py` with indexes.
- **Verification:** `test_signal_support_tables_exist`, parametrized `test_issue_table_exists`.

## Lane 2 Fixes (critical review)

### 5. proposals_v4 split-brain schema (CRITICAL — missed by Lane 1)

- **What:** `schema.py` defined `proposals_v4` with `id TEXT PRIMARY KEY` and 14 aggregator-style columns. `proposal_service.py` runtime DDL defined it with `proposal_id TEXT PRIMARY KEY` and 22 v4-style columns. `spec_router.py` references columns from BOTH sets. Whichever `CREATE TABLE IF NOT EXISTS` ran first won.
- **Fix:** Rewrote `TABLES["proposals_v4"]` with `proposal_id` as PK and all columns from both sources. Added indexes.
- **Verification:** `test_proposals_v4_pk_is_proposal_id`, `test_proposals_v4_v4_service_columns`, `test_proposals_v4_aggregator_columns`, `test_proposals_v4_insert_v4_service`.

### 6. Runtime DDL in coupling_service.py and proposal_service.py (HIGH — missed by Lane 1)

- **What:** Lane 1 only cleaned `signal_service.py` and `issue_service.py`. Both `coupling_service.py` and `proposal_service.py` still had runtime DDL.
- **Fix:** Deleted `_ensure_tables()` entirely from all 4 v4 services.
- **Verification:** `TestNoRuntimeDDL` (4 services), `TestNoEnsureTables` (4 services).

### 7. No-op stubs replaced with clean deletion (MEDIUM)

- **What:** Lane 1 left `_ensure_tables()` as no-op stubs. Dead code suggesting runtime DDL ownership.
- **Fix:** Deleted entirely. Constructors now only set `self.db_path`.

## Lane 3 Fixes (final audit)

### 8. Dead columns removed from proposals_v4 (MEDIUM)

- **What:** `missing_confirmations` and `supersedes_proposal_id` had zero readers and zero writers in all runtime code. They were added in Lane 1 to "match" what the old runtime DDL defined, but no caller ever referenced them.
- **Fix:** Removed both columns from `TABLES["proposals_v4"]`. Added `test_proposals_v4_no_dead_columns` to catch future dead-column additions.
- **Note:** `summary` column kept — it's read by `get_proposal()` (line 362, proposal_service.py) even though no runtime code writes it yet. It has a real caller.

### 9. couplings table missing all indexes (HIGH)

- **What:** The `couplings` table had ZERO indexes despite multiple query patterns using WHERE, ORDER BY, and GROUP BY. `spec_router.py GET /api/v2/couplings` queries `WHERE anchor_ref_type = ? AND anchor_ref_id = ?` with no index — full table scan on every API call. `coupling_service.py` ORDER BY strength DESC and GROUP BY coupling_type also unindexed.
- **Fix:** Added 3 indexes: `idx_couplings_anchor` (anchor_ref_type, anchor_ref_id), `idx_couplings_strength` (strength DESC), `idx_couplings_type` (coupling_type).
- **Verification:** `test_couplings_has_anchor_index`, `test_couplings_has_strength_index`, `test_couplings_has_type_index`.

### 10. proposals_v4 missing composite index for UPDATE lookup (MEDIUM)

- **What:** `proposal_service.py` line 130 queries `WHERE scope_level = ? AND primary_ref_id = ? AND status = 'open'` — the main update path for existing proposals. No composite index covered this pattern. The existing `idx_proposals_hierarchy` covered `(client_id, brand_id, scope_level)` which doesn't help.
- **Fix:** Added `idx_proposals_v4_scope_status` on `(scope_level, primary_ref_id, status)`.
- **Verification:** `test_proposals_v4_has_scope_status_index`.

### 11. Stale comments cleaned (LOW)

- schema.py L687: "Legacy: proposals_v4" → "Proposals (v4 intelligence layer)" — it's active production, not legacy.
- schema.py L1791-1793: Referenced `CouplingService._ensure_tables()` which no longer exists. Updated to describe current ownership.

## Lane 4 Fixes (intelligence/lifecycle migration)

### 12. Runtime DDL in drift_detection.py (HIGH)

- **What:** `DriftDetector.__init__()` called `_ensure_tables()` creating `drift_baselines` (composite PK on metric_name, entity_type, entity_id) and `drift_alerts` with `idx_drift_time` index. Runtime DDL masked any column drift from schema.py.
- **Fix:** Added `TABLES["drift_baselines"]` (with composite primary key) and `TABLES["drift_alerts"]` to schema.py. Added `idx_drift_time` index. Extended `schema_engine._build_create_sql()` to support table-level `PRIMARY KEY (...)` constraints (same pattern as existing `UNIQUE` support). Deleted `_ensure_tables()` entirely.
- **Verification:** `TestDriftDetectionSchema` (3 tests: columns, composite PK upsert, alerts columns), `TestRequiredIndexes::test_drift_alerts_has_time_index`.

### 13. Runtime DDL in signal_suppression.py (HIGH)

- **What:** `SignalSuppression.__init__()` called `_ensure_tables()` creating `signal_suppressions` (3 indexes) and `signal_dismiss_log` (1 index). Same masking pattern.
- **Fix:** Added both tables and all 4 indexes to schema.py. Deleted `_ensure_tables()` entirely.
- **Verification:** `TestSignalSuppressionSchema` (2 tests), `TestRequiredIndexes::test_signal_suppressions_has_indexes` (checks 3 indexes), `TestRequiredIndexes::test_dismiss_log_has_signal_index`.

### 14. Runtime DDL in engagement_lifecycle.py (HIGH)

- **What:** `EngagementLifecycleManager.__init__()` called `_ensure_tables()` creating `engagement_transitions` with `idx_engagement_transitions_engagement_id` index. Also contained dead `ENGAGEMENT_MIGRATION` SQL block (~47 lines) at module level with zero references.
- **Fix:** Added `TABLES["engagement_transitions"]` and index to schema.py. Deleted `_ensure_tables()` and `ENGAGEMENT_MIGRATION` dead code entirely.
- **Verification:** `TestEngagementTransitionsSchema` (1 test), `TestRequiredIndexes::test_engagement_transitions_has_engagement_index`.

### 15. schema_engine composite primary key support (MEDIUM)

- **What:** `_build_create_sql()` only handled column-level `PRIMARY KEY` and table-level `UNIQUE(...)`. `drift_baselines` requires table-level `PRIMARY KEY (metric_name, entity_type, entity_id)`.
- **Fix:** Added `primary_key` key support to `_build_create_sql()` — checks `table_def.get("primary_key")` and emits `PRIMARY KEY (col1, col2, ...)` as a table-level constraint, following the same pattern as the existing `unique` support.
- **Verification:** `TestDriftDetectionSchema::test_drift_baselines_composite_pk` — INSERT + ON CONFLICT upsert confirms the composite PK works.

## Files Changed

| File | Change |
|------|--------|
| `lib/schema.py` | v22: +governance_history, +8 v4 tables, +6 views, signals 19 cols, proposals_v4 31 cols (proposal_id PK, dead cols removed), +couplings indexes, +scope composite index, stale comments cleaned, +drift_baselines (composite PK), +drift_alerts, +signal_suppressions, +signal_dismiss_log, +engagement_transitions, +6 indexes |
| `lib/schema_engine.py` | Views creation in converge() Phase 4 and create_fresh(). Composite PK support in _build_create_sql(). |
| `lib/v4/signal_service.py` | _ensure_tables() deleted entirely |
| `lib/v4/issue_service.py` | _ensure_tables() deleted entirely |
| `lib/v4/proposal_service.py` | _ensure_tables() + runtime DDL deleted entirely |
| `lib/v4/coupling_service.py` | _ensure_tables() + runtime DDL deleted entirely |
| `lib/intelligence/drift_detection.py` | _ensure_tables() deleted entirely |
| `lib/intelligence/signal_suppression.py` | _ensure_tables() deleted entirely |
| `lib/ui_spec_v21/engagement_lifecycle.py` | _ensure_tables() + ENGAGEMENT_MIGRATION dead code deleted entirely |
| `tests/fixtures/fixture_db.py` | Removed FIXTURE_VIEWS (now canonical in schema.py) |
| `tests/test_schema_runtime_contract.py` | 63 regression tests covering all findings |

## Verification Path

```
pytest tests/test_schema_runtime_contract.py -v     # 63 pass
pytest tests/test_cross_entity_views.py -v           # 25 pass (unchanged)
ruff check <all changed files>                       # 0 errors
```

## What the tests prove

1. **Fresh production DB supports all runtime query paths** — INSERT/SELECT simulations for governance_history, signals, proposals_v4, couplings
2. **Production code does not depend on fixture-only schema** — views promoted, fixture definitions removed
3. **No phantom schema references remain** — governance_history, 8 v4 tables all canonical
4. **Signals contract is unified** — 19 columns matching all v4 service reads/writes
5. **proposals_v4 contract is unified** — both v4 service and aggregator columns, correct PK, dead columns removed
6. **Runtime DDL masking is gone** — source scan on all 7 service/intelligence/lifecycle files (no CREATE TABLE, no _ensure_tables)
7. **Indexes cover actual query patterns** — couplings 3 indexes, proposals_v4 6 indexes, drift/suppression/transitions 6 indexes, all verified
7b. **Composite primary keys work** — drift_baselines INSERT + ON CONFLICT upsert proves composite PK
8. **Fresh bootstrap and convergence produce identical schema** — converge tests for tables, columns, views
9. **Dead columns are caught** — test_proposals_v4_no_dead_columns prevents re-introduction

## What prevents this drift from coming back

1. **TestNoRuntimeDDL** — source-scans all 7 service/intelligence/lifecycle files for `CREATE TABLE`. Any new runtime DDL fails CI.
2. **TestNoEnsureTables** — source-scans all 7 service/intelligence/lifecycle files for `_ensure_tables`. Any re-introduction fails CI.
3. **TestProposalsV4Schema::test_proposals_v4_no_dead_columns** — explicitly checks that known dead columns (`missing_confirmations`, `supersedes_proposal_id`) don't re-appear.
4. **TestRequiredIndexes** — verifies specific indexes exist for known query patterns. New query patterns without indexes will be visible in code review.
5. **TestFreshDBTables::test_all_tables_created** — every table in schema.py must exist in fresh DB. New tables must go through schema.py.
6. **TestConverge** — converge produces the same schema as create_fresh. No divergence between fresh and migrated databases.

## Known remaining runtime DDL

None. All `_ensure_tables()` methods have been migrated to schema.py and deleted. The `CREATE TABLE` source-scan tests cover all 7 files that previously had runtime DDL.
