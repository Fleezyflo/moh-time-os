# GUARDRAILS VERIFICATION MANIFEST

**Generated:** 2026-02-16
**Status:** ALL GUARDS NOW BLOCKING

## How Guards Work

- Exit 0 = PASS (no violations)
- Exit 1 = FAIL (violations found, commit blocked)
- Pre-commit runs all guards on every commit
- CI runs all guards on every push

---

## VERIFICATION COMMANDS

### 1. See Guard Configuration

```bash
# See all guards defined
cat .pre-commit-config.yaml

# See CI workflow
cat .github/workflows/ci.yml

# See guardrails workflow
cat .github/workflows/guardrails.yml

# List all guard scripts
ls -la scripts/check_*.py
```

### 2. Run All Guards

```bash
# Run all guards (what pre-commit does)
cd moh_time_os && uv run pre-commit run --all-files

# Run a specific guard by ID
uv run pre-commit run no-secrets --all-files
uv run pre-commit run no-sql-fstrings --all-files
```

### 3. Prove Each Guard Blocks

Each command below shows violations. Exit code 1 = blocking works.

```bash
# P0 SECURITY
uv run python scripts/check_secrets.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_sql_fstrings.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_path_traversal.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_pii_logging.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_vulnerabilities.py && echo "PASS" || echo "BLOCKED"

# P1 ARCHITECTURE
uv run python scripts/check_duplicate_endpoints.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_import_boundaries.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_api_breaking.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_monolith_files.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_empty_db.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_migration_safety.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_licenses.py && echo "PASS" || echo "BLOCKED"

# P2 CODE QUALITY
uv run python scripts/check_circular_imports.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_dead_code.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_complexity.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_docstrings.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_error_handling.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_no_print.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_global_state.py && echo "PASS" || echo "BLOCKED"

# P2 DATABASE
uv run python scripts/check_query_safety.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_transaction_safety.py && echo "PASS" || echo "BLOCKED"

# P2 API
uv run python scripts/check_endpoint_auth.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_pagination.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_response_types.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_http_timeouts.py && echo "PASS" || echo "BLOCKED"

# P2 ASYNC/PERF
uv run python scripts/check_async_blocking.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_hardcoded_config.py && echo "PASS" || echo "BLOCKED"

# P2 TESTING
uv run python scripts/check_test_skips.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_new_code_tests.py && echo "PASS" || echo "BLOCKED"

# P2 DEPS
uv run python scripts/check_lockfile_sync.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_unused_deps.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_env_vars.py && echo "PASS" || echo "BLOCKED"

# FRONTEND
uv run python scripts/check_no_console.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_accessibility.py && echo "PASS" || echo "BLOCKED"
uv run python scripts/check_bundle_size.py && echo "PASS" || echo "BLOCKED"

# TYPE CHECKING
uv run python scripts/check_mypy.py && echo "PASS" || echo "BLOCKED"
```

### 4. Verify Pre-commit Hook is Installed

```bash
# Check hook exists and is executable
ls -la .git/hooks/pre-commit
cat .git/hooks/pre-commit

# Test hook by attempting a commit (will fail if guards fail)
git commit --allow-empty -m "test: verify guards block"
```

### 5. Test Guard Catches Violation (Proof)

```bash
# Create a file with a secret and verify it's caught
echo 'API_KEY = "sk-1234567890abcdef"' > /tmp/test_secret.py
cp /tmp/test_secret.py lib/test_secret.py
uv run python scripts/check_secrets.py
# Should show violation and exit 1
rm lib/test_secret.py

# Create a file with SQL f-string and verify it's caught
echo 'cursor.execute(f"SELECT * FROM {table}")' > /tmp/test_sql.py
cp /tmp/test_sql.py lib/test_sql.py
uv run python scripts/check_sql_fstrings.py
# Should show violation and exit 1
rm lib/test_sql.py
```

---

## GUARD INVENTORY

| ID | Name | Priority | Script | Blocks On |
|----|------|----------|--------|-----------|
| no-secrets | No hardcoded secrets | P0 | check_secrets.py | API keys, tokens, passwords |
| no-vulnerabilities | No vulnerable deps | P0 | check_vulnerabilities.py | Known CVEs |
| no-sql-fstrings | No SQL injection | P0 | check_sql_fstrings.py | f-string in SQL |
| path-traversal | Path traversal | P0 | check_path_traversal.py | Unsafe path ops |
| pii-logging | No PII in logs | P0 | check_pii_logging.py | Email/phone in logs |
| no-duplicate-endpoints | No duplicate endpoints | P1 | check_duplicate_endpoints.py | Same route twice |
| import-boundaries | Import boundaries | P1 | check_import_boundaries.py | Layer violations |
| no-breaking-api | No breaking API | P1 | check_api_breaking.py | Removed endpoints |
| no-monolith-files | No monolith files | P1 | check_monolith_files.py | Files >1000 lines |
| no-empty-db-files | No empty .db files | P1 | check_empty_db.py | Empty databases |
| safe-migrations | Safe migrations | P1 | check_migration_safety.py | DROP without backup |
| license-check | License compatibility | P1 | check_licenses.py | Copyleft in deps |
| no-circular-imports | Circular imports | P2 | check_circular_imports.py | Import cycles |
| dead-code | Dead code | P2 | check_dead_code.py | Unused functions |
| complexity | Complexity | P2 | check_complexity.py | Cyclomatic >15 |
| docstrings | Docstrings | P2 | check_docstrings.py | Missing docstrings |
| error-handling | Error handling | P2 | check_error_handling.py | Bare except |
| no-print | No print() | P2 | check_no_print.py | print() calls |
| global-state | Global state | P2 | check_global_state.py | Mutable globals |
| query-safety | Query safety | P2 | check_query_safety.py | Unbounded queries |
| transaction-safety | Transaction safety | P2 | check_transaction_safety.py | Missing transactions |
| endpoint-auth | Endpoint auth | P2 | check_endpoint_auth.py | Unprotected endpoints |
| pagination | Pagination | P2 | check_pagination.py | Unbounded lists |
| response-types | Response types | P2 | check_response_types.py | Missing types |
| http-timeouts | HTTP timeouts | P2 | check_http_timeouts.py | Missing timeouts |
| async-blocking | Async blocking | P2 | check_async_blocking.py | Sync in async |
| hardcoded-config | Hardcoded config | P2 | check_hardcoded_config.py | Magic numbers |
| test-skips | Test skips | P2 | check_test_skips.py | @skip without reason |
| new-code-tests | New code tests | P2 | check_new_code_tests.py | Code without tests |
| lockfile-sync | Lockfile sync | P2 | check_lockfile_sync.py | Lock out of sync |
| unused-deps | Unused deps | P2 | check_unused_deps.py | Unused packages |
| env-vars | Env vars | P2 | check_env_vars.py | Undocumented vars |
| no-console | No console.* | FE | check_no_console.py | console.log |
| accessibility | Accessibility | FE | check_accessibility.py | Missing aria |
| bundle-size | Bundle size | FE | check_bundle_size.py | Over budget |
| mypy | Type checking | P2 | check_mypy.py | Type errors |

---

## WHAT CHANGED

### Before (Broken)
- 30/42 scripts returned `1` unconditionally (always fail)
- Pre-commit wasn't installed locally
- Git hook failed silently
- CI had `|| true` and `continue-on-error: true` bypasses
- Commits went through without any guard running

### After (Fixed)
- All scripts return 0 on pass, 1 on fail
- Pre-commit installed via `uv run pre-commit install`
- Git hook properly invokes pre-commit
- CI removed all bypasses
- Every commit must pass all guards

---

## CURRENT VIOLATIONS (Existing Debt)

These violations exist in the codebase and need to be fixed:

```
SQL Injection:     19+ f-string SQL queries
Duplicate Routes:  5 duplicate API endpoints
Import Violations: 4 layer boundary breaks
Complexity:        29+ functions over threshold
```

Guards are now blocking. New code cannot add violations.
Existing violations must be cleaned up.
