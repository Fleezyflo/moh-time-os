# AO-5.1: Core Test Coverage Push

## Objective
Write tests for the critical untested modules: autonomous_loop.py, change_bundles.py, truth_cycle.py, collector orchestrator, and agency_snapshot. Target ≥80% coverage on these modules.

## Context
Current test coverage: 18% (49 test files for 235 lib modules). The most critical modules — the ones that run unattended and make decisions — have zero tests. This is unacceptable before autonomous operation.

## Modules to Test

### 1. `lib/autonomous_loop.py` (882 lines, 0% coverage)
- Test cycle execution with mocked jobs
- Test error recovery: job failure → retry → circuit break
- Test graceful degradation: collectors fail → truth still runs
- Test CycleResult generation
- Test health state tracking

### 2. `lib/change_bundles.py` (coverage unknown)
- Test bundle creation, commit, rollback
- Test before/after state tracking
- Test retention purge
- Test manual rollback via bundle ID

### 3. `lib/truth_cycle.py` (new in Brief 8, needs tests from inception)
- Test orchestration: time→commitment→capacity→client
- Test partial failure: one module fails, others continue
- Test typed result output
- Test with empty/missing data

### 4. `lib/collectors/orchestrator.py` (187 lines)
- Test collector scheduling
- Test circuit breaker integration
- Test partial success handling
- Test CollectionResult aggregation

### 5. `lib/agency_snapshot.py` or equivalent
- Test page generation with real-shaped data
- Test snapshot completeness (all pages present)
- Test with degraded data (some truth modules failed)

### Test Strategy
- Use pytest with fixtures for DB setup/teardown
- Mock external APIs (Asana, Gmail, Calendar, Xero, Chat)
- Test both happy path and failure modes
- Use `tmp_path` for DB isolation
- No live API calls in tests (enforce via `check_no_live_db_in_tests.sh`)

## Validation
- [ ] `pytest tests/test_autonomous_loop.py` — all pass
- [ ] `pytest tests/test_change_bundles.py` — all pass
- [ ] `pytest tests/test_truth_cycle.py` — all pass
- [ ] `pytest tests/test_orchestrator.py` — all pass
- [ ] `pytest tests/test_agency_snapshot.py` — all pass
- [ ] Coverage for these 5 modules ≥80%
- [ ] No live DB/API calls in any test

## Files Created
- `tests/test_autonomous_loop.py`
- `tests/test_change_bundles.py`
- `tests/test_truth_cycle.py`
- `tests/test_orchestrator.py`
- `tests/test_agency_snapshot.py`

## Estimated Effort
Large — ~500-700 lines of tests across 5 files
