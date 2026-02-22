# IA-6.1: API Contract Tests & Validation

## Objective

Comprehensive test suite validating every intelligence API endpoint. Tests serve as both validation and living documentation of the API contract.

## Dependencies

- IA-1.1 through IA-5.1 (all endpoints must exist)

## Test Strategy

### Test Infrastructure

Use `httpx.AsyncClient` with FastAPI's `TestClient`. Create a test database with known intelligence data seeded in fixtures.

### Fixture: Seeded Intelligence Database

Create `tests/fixtures/seed_intelligence.py` that populates:
- 5 clients with varying health scores (critical, at_risk, stable, healthy, strong)
- 10 projects with scores
- 5 persons with scores
- 8 active signals across severities
- 4 detected patterns across types
- 3 cost snapshots
- Score history for 30 days (for trajectory tests)
- 5 intelligence events

### Test Files

#### `tests/test_intelligence_api_router.py` (~100 lines)
- Router mounts and responds to /api/v3/intelligence prefix
- Response envelope has correct shape
- Freshness metadata populates correctly
- Unknown routes return 404
- Empty DB returns 503

#### `tests/test_intelligence_api_entity.py` (~150 lines)
- GET /entity/client/{id}/profile returns full profile
- GET /entity/client/{id}/health returns score + classification
- GET /entity/client/{id}/health/history returns time series
- GET /entity/client/{id}/signals returns filtered list
- GET /entity/client/{id}/timeline returns chronological events
- Unknown entity returns 404
- Unknown entity_type returns 400
- Profile includes all sections (signals, patterns, trajectory, cost)

#### `tests/test_intelligence_api_portfolio.py` (~120 lines)
- GET /portfolio/dashboard returns all sections
- Entity counts match seeded data
- Top concerns sorted by severity
- GET /portfolio/entities with pagination works
- GET /portfolio/entities with classification filter works
- GET /portfolio/health/history returns correct date range
- GET /portfolio/proposals returns ranked list

#### `tests/test_intelligence_api_signals.py` (~120 lines)
- GET /signals returns all active signals
- Severity filter works (critical only)
- Entity type filter works
- Signal detail includes evidence
- POST /signals/{key}/acknowledge updates state
- GET /signals/summary counts match detail counts
- GET /signals/history returns state transitions

#### `tests/test_intelligence_api_patterns.py` (~100 lines)
- GET /patterns returns all detected patterns
- Direction filter works
- Pattern detail includes evidence chain
- GET /patterns/summary counts match detail counts
- Pattern history shows cycle-over-cycle changes

#### `tests/test_intelligence_api_scenarios.py` (~110 lines)
- POST /scenarios/client-loss returns impact assessment
- POST /scenarios/client-addition returns capacity analysis
- POST /scenarios/resource-change handles all change types
- POST /scenarios/pricing-change returns profitability comparison
- POST /scenarios/workload-rebalance returns recommendations
- Invalid client_id returns 404
- Missing required fields return 422

### Contract Shape Validators

For each response type, a Pydantic model that validates the shape. Tests assert responses parse without error through these models.

## Performance Baseline

Run each endpoint 100 times against seeded DB, report:
- p50, p95, p99 response times
- Flag any endpoint exceeding its target

| Endpoint Category | Target p95 |
|------------------|-----------|
| Health (lightweight) | <20ms |
| Profile (assembled) | <100ms |
| List endpoints | <50ms |
| Portfolio dashboard | <200ms |
| Scenarios | <2000ms |

## Validation

- All tests pass
- No test uses live DB
- Every endpoint has at least 3 tests (happy path, filter, error case)
- Performance baseline established and documented
- Response shapes match documented API contracts

## Estimated Effort

~500 lines across 6 test files + fixtures
