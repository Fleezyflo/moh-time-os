# Cross-Cutting Correctness Remediation -- Final Report

## Audit History

Pass 1-4: created `lib/clock.py`, `lib/credential_paths.py`, eliminated ~520 bare datetime.now() in production code, eliminated 48+ module-level DB_PATH captures, added locks to 7 shared-state patterns. Pass 5: eliminated deferred items -- test files, archive Python, collector SA_FILE, daemon paths. Pass 6: reverted history-rewriting markdown edits, replaced regex heuristics with AST-based detection. Pass 7 (hostile verification + fix): found and fixed 5 naive datetime defects (aliased dt.now(), 4 fromtimestamp-without-tz), 10 module-level path captures missed by name-based list (DEFAULT_DB, DEFAULT_SA_FILE, V5_DB_PATH, SCHEDULE_PATH, KEY_PATH, CONFIG_PATH x2, KB_PATH), 13 unprotected lazy singleton initializers in lib/v4/. Replaced all test detectors with structural AST-based versions.

## Scope and boundaries

**Maintained runtime code**: all `.py` files in `lib/`, `api/`, `cli/`, `engine/`, `scripts/`, and `tests/`. This is the enforced boundary -- structural AST regression tests cover this scope.

**Archived Python code**: `.py` files in `docs/archive/v5/` and `_archive/legacy_collectors/`. Fixed to match time and path policies. Regression tests cover these.

**Historical documentation**: `.md` files in `_archive/specs/`, `archive/briefs/`, `archive/plans/`, `archive/specs/`. Contain pseudocode reflecting design at time of writing. Intentionally unchanged -- not executable code.

**Excluded by definition**: `lib/clock.py` (the canonical time module itself), string literals in test assertions, and `REPO_ROOT = Path(__file__).parent.parent` (static project-structure constant).

## What was fixed

### 1. Time policy

All executable `datetime.now()`, `datetime.utcnow()`, and `datetime.fromtimestamp(ts)` (without tz) calls eliminated from maintained scope.

Specific defects found by hostile verification (Pass 7):
- `lib/collectors/orchestrator.py:281`: aliased `from datetime import datetime as dt; dt.now()` -- invisible to name-based detectors
- `lib/health.py:98`: `datetime.fromtimestamp(st_mtime)` subtracted from aware datetime -- TypeError at runtime
- `lib/backup.py:70`: naive `fromtimestamp` producing inconsistent types
- `lib/v4/ingest_pipeline.py:535`: naive `fromtimestamp` in else branch vs aware in if branch
- `scripts/docs_inventory.py:82`: naive `fromtimestamp` in utility script

### 2. Path/config determinism

All module-level path captures converted to getter functions. Structural AST detector ensures no UPPER_CASE module-level assignment calls `db_path()`, `v5_db_path()`, `google_sa_file()`, `project_root()`, `config_dir()`, `os.path.join()`, or similar path-producing functions.

Files fixed in Pass 7 (missed by name-based list):
- `lib/intelligence/notifications.py`: DEFAULT_DB
- `lib/integrations/calendar_writer.py`: DEFAULT_SA_FILE
- `lib/integrations/gmail_writer.py`: DEFAULT_SA_FILE
- `lib/sync_health.py`: SCHEDULE_PATH
- `lib/migrations/add_communications_columns.py`: DEFAULT_DB
- `lib/migrations/v29_spec_alignment.py`: V5_DB_PATH
- `lib/v4/artifact_service.py`: KEY_PATH
- `cli/xero_auth.py`: CONFIG_PATH
- `cli/xero_auth_auto.py`: CONFIG_PATH
- `engine/knowledge_base.py`: KB_PATH

### 3. Thread safety -- 20 patterns locked

Original 7 patterns (Pass 1-2):
- CircuitBreaker, RateLimiter, Migration flag, Daemon orchestrator, Cache singleton, Feature flags (RLock), Export cache

13 new patterns (Pass 7):
- All lib/v4/ lazy singleton initializers now use `threading.Lock()` with double-checked locking: `_FERNET`, `_artifact_service`, `_hooks`, `_coupling_service`, `_entity_link_service`, `_identity_service`, `_ingest_pipeline`, `_issue_service`, `_orchestrator`, `_policy_service`, `_proposal_service`, `_report_service`, `_signal_service`

### 4. Credential paths -- centralized with env override

All credential paths route through `lib/credential_paths.py`. All collector SA_FILE definitions use runtime-resolved `_sa_file()` getter.

### 5. Import-order safety

No circular imports. `lib/clock.py` and `lib/credential_paths.py` import only from leaf modules.

## What guardrails prevent regression

### Structural AST detectors (`tests/test_cross_cutting_correctness.py`)

**Datetime detectors** (structural -- not name-based):
- `_ast_collect_datetime_aliases()`: collects ALL aliased names for the datetime class from import statements
- `_ast_find_bare_datetime_calls()`: detects `.now()`/`.utcnow()` on ANY alias, not just literal "datetime"
- `_ast_find_naive_fromtimestamp()`: detects `.fromtimestamp()` without tz argument
- `test_no_aliased_bare_now_in_production`: catches aliased imports like `dt.now()`
- `test_no_naive_fromtimestamp_in_production`: catches `fromtimestamp(ts)` without tz
- `test_no_bare_datetime_now_in_tests`, `test_no_bare_datetime_now_in_archives`, `test_no_utcnow_in_tests`

**Path-capture detector** (structural -- not name-based):
- `_ast_find_module_level_path_calls()`: AST-walks top-level UPPER_CASE assignments, checks if RHS calls any path-producing function
- `test_no_module_level_path_calls_in_production`: catches ANY new module-level path capture regardless of variable name

**Singleton safety detector**:
- `test_v4_singletons_have_locks`: scans lib/v4/ for `global _X; if _X is None` patterns and verifies threading.Lock exists

**Why structural matters**: The name-based list missed DEFAULT_DB, DEFAULT_SA_FILE, V5_DB_PATH, SCHEDULE_PATH, KEY_PATH, CONFIG_PATH, KB_PATH. The alias-unaware detector missed `dt.now()`. The structural detectors catch patterns, not names.

## Items not covered (by definition, not deferral)

1. **Direct `sqlite3.connect()` call sites**: path arguments trace back to `paths.db_path()` at call time.
2. **`REPO_ROOT` module-level definitions**: static project-structure constant, not runtime-configurable.
3. **Historical markdown pseudocode**: not executable code.

## Status

Prompt 4 closure is supported by:
- Zero violations from structural AST datetime detector (aliases, fromtimestamp, bare now/utcnow)
- Zero violations from structural AST path-capture detector (any module-level call to path-producing functions)
- Zero unprotected singleton initializers in lib/v4/
- All 20 modified files compile successfully
- 50 regression tests across 12 test classes enforce all invariants
