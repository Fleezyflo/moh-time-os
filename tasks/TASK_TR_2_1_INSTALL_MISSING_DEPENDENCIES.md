# TASK: Install Missing Test Dependencies (pydantic, fastapi)
> Brief: TEST_REMEDIATION | Phase: 2 | Sequence: 2.1 | Status: PENDING

## Context

9 test modules fail to collect because `pydantic` and `fastapi` are not installed in the test environment. These are declared in `pyproject.toml` as dependencies but missing from the current virtualenv / system Python.

**pydantic blocks (7 modules):**
- tests/contract/test_invariants.py
- tests/contract/test_schema.py
- tests/contract/test_thresholds.py
- tests/negative/test_empty_when_data_exists.py
- tests/negative/test_missing_sections.py
- tests/negative/test_unresolved_scopes.py
- tests/property/test_invariants.py

**fastapi blocks (2 modules + 2 runtime failures):**
- tests/test_api_contracts.py
- tests/test_stub_endpoints.py
- tests/test_intelligence_api.py (2 failures: test_wrap_response_structure, test_wrap_response_with_params — import `api.intelligence_router` which needs fastapi)

**Source files using pydantic (6):**
- lib/contracts/schema.py
- api/server.py
- api/spec_router.py
- lib/v5/api/routes/signals.py
- lib/v5/api/routes/health.py
- lib/v5/api/routes/issues.py

**Source files using fastapi (8):**
- api/server.py
- api/spec_router.py
- api/intelligence_router.py
- api/auth.py
- lib/v5/api/main.py
- lib/v5/api/routes/signals.py
- lib/v5/api/routes/health.py
- lib/v5/api/routes/issues.py

## Objective

Install pydantic and fastapi so all test modules can collect and run.

## Instructions

1. Check current install method:
   ```bash
   which pip3 && pip3 --version
   cat pyproject.toml | grep -A20 "dependencies"
   ```

2. Install the packages:
   ```bash
   pip3 install pydantic fastapi httpx --break-system-packages
   ```
   Note: `httpx` is needed by `fastapi.testclient.TestClient` (replacement for `requests` in newer fastapi).

3. Verify imports:
   ```python
   import pydantic; print(pydantic.VERSION)
   import fastapi; print(fastapi.__version__)
   from fastapi.testclient import TestClient; print("TestClient OK")
   ```

4. Check if any version constraints exist in pyproject.toml and install compatible versions if needed.

## Preconditions
- [ ] TR-1.1 and TR-1.2 complete (UTC + StrEnum fixed)

## Validation
1. `python -c "from pydantic import BaseModel"` succeeds
2. `python -c "from fastapi.testclient import TestClient"` succeeds
3. `python -c "from lib.contracts.schema import *"` succeeds
4. `pytest tests/contract/ tests/negative/ tests/property/ -q --co` — all collect (0 errors)
5. `pytest tests/test_api_contracts.py tests/test_stub_endpoints.py -q --co` — all collect
6. `pytest tests/test_intelligence_api.py -q` — 15/15 pass (including the 2 that were failing)

## Tests Unblocked by This Fix
- 7 contract/negative/property test modules (collection errors → should collect)
- 2 API test modules (collection errors → should collect)
- 2 intelligence_api tests (runtime failures → should pass)

## Acceptance Criteria
- [ ] pydantic importable
- [ ] fastapi importable
- [ ] All 9 previously-erroring test modules now collect
- [ ] The 2 intelligence_api failures now pass

## Output
- Installed packages: pydantic, fastapi, httpx
- No source file changes
