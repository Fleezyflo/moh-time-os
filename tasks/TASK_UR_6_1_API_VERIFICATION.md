# TASK: Verify All Intelligence Endpoints Return Real Data
> Brief: USER_READINESS | Phase: 6 | Sequence: 6.1 | Status: PENDING

## Context

The API surface includes:
- `api/intelligence_router.py`: 8+ endpoints for portfolio, client, person intelligence
- `lib/v5/api/routes/health.py`: Health dashboard, client health, timeline
- `api/server.py`: ~140 endpoints including spec-compliant routes

These endpoints return real computed data — but nobody's verified the full chain (DB → engine → API response) on current data after all the schema fixes and pipeline hardening.

## Objective

Hit every intelligence and health endpoint, verify non-empty real data responses, document any that fail.

## Instructions

1. Start the API server:
   ```bash
   cd /sessions/loving-blissful-keller/mnt/clawd/moh_time_os
   python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000 &
   ```

2. Test each intelligence endpoint:
   ```bash
   # Portfolio overview
   curl -s http://localhost:8000/api/v2/intelligence/portfolio/overview | python3 -m json.tool | head -30

   # Portfolio risks
   curl -s http://localhost:8000/api/v2/intelligence/portfolio/risks | python3 -m json.tool | head -30

   # Portfolio trajectory
   curl -s http://localhost:8000/api/v2/intelligence/portfolio/trajectory | python3 -m json.tool | head -30

   # Client intelligence (use a real client_id from DB)
   curl -s http://localhost:8000/api/v2/intelligence/client/{client_id} | python3 -m json.tool | head -30

   # Person intelligence
   curl -s http://localhost:8000/api/v2/intelligence/person/{person_id} | python3 -m json.tool | head -30
   ```

3. Test V5 health endpoints:
   ```bash
   curl -s http://localhost:8000/api/v5/health/dashboard | python3 -m json.tool | head -30
   curl -s http://localhost:8000/api/v5/health/client/{client_id} | python3 -m json.tool | head -30
   ```

4. For each endpoint, verify:
   - HTTP 200 response
   - Non-empty response body
   - Real data (not empty arrays or zero counts)
   - No error messages in response

5. If auth is required (`dependencies=[Depends(require_auth)]`), check if it can be bypassed for testing or if there's a test token.

6. Document results:
   ```
   | Endpoint | Status | Data? | Notes |
   |----------|--------|-------|-------|
   | /portfolio/overview | 200 | Yes | 160 clients returned |
   | /portfolio/risks | 200 | Yes | 5 risks identified |
   | ... | ... | ... | ... |
   ```

7. For any failing endpoints, trace the error and apply minimal fix.

8. Stop the server after testing.

## Preconditions
- [ ] UR-5.1 complete (daemon ran, snapshot exists)

## Validation
1. All intelligence endpoints return HTTP 200
2. All responses contain real data (non-empty)
3. No 500 errors
4. Results documented in commit message

## Acceptance Criteria
- [ ] Every intelligence endpoint tested
- [ ] Every health endpoint tested
- [ ] All return real data
- [ ] Any fixes applied for failing endpoints
- [ ] Results documented

## Output
- Possibly modified: API route files (if fixes needed)
- Documentation: endpoint test results in commit message
