# API Intelligence Endpoints — Proposal

> **Status:** Awaiting approval (GUARDRAILS: API changes require explicit approval)
> **Date:** 2026-02-13

## Namespace: /api/v2/intelligence/

All endpoints are **read-only GET** requests. No modifications to existing `spec_router.py` endpoints.

## Endpoints

### Portfolio Overview
| Endpoint | Method | Parameters | Response | Query Engine Function |
|----------|--------|------------|----------|----------------------|
| `/portfolio/overview` | GET | `?since=&until=&order_by=` | List of clients with operational metrics | `client_portfolio_overview()` |
| `/portfolio/risks` | GET | `?overdue_threshold=&aging_threshold=` | List of structural risks | `portfolio_structural_risks()` |
| `/portfolio/trajectory` | GET | `?window_days=30&num_windows=6&min_activity=1` | List of client trajectories | `portfolio_trajectory()` |

### Client Endpoints
| Endpoint | Method | Parameters | Response | Query Engine Function |
|----------|--------|------------|----------|----------------------|
| `/clients/{client_id}/profile` | GET | — | Deep client profile with nested data | `client_deep_profile()` |
| `/clients/{client_id}/tasks` | GET | — | Task summary for client | `client_task_summary()` |
| `/clients/{client_id}/communication` | GET | `?since=&until=` | Communication metrics | `client_communication_summary()` |
| `/clients/{client_id}/trajectory` | GET | `?window_days=30&num_windows=6` | Client trajectory with trends | `client_trajectory()` |
| `/clients/{client_id}/compare` | GET | `?period_a_start=&period_a_end=&period_b_start=&period_b_end=` | Period comparison | `compare_client_periods()` |
| `/clients/compare` | GET | `?period_a_start=&...` | All clients comparison | `compare_portfolio_periods()` |

### Team Endpoints
| Endpoint | Method | Parameters | Response | Query Engine Function |
|----------|--------|------------|----------|----------------------|
| `/team/distribution` | GET | — | Team load distribution | `resource_load_distribution()` |
| `/team/capacity` | GET | — | Team capacity overview | `team_capacity_overview()` |
| `/team/{person_id}/profile` | GET | — | Person operational profile | `person_operational_profile()` |
| `/team/{person_id}/trajectory` | GET | `?window_days=30&num_windows=6` | Person trajectory | `person_trajectory()` |

### Project Endpoints
| Endpoint | Method | Parameters | Response | Query Engine Function |
|----------|--------|------------|----------|----------------------|
| `/projects/{project_id}/state` | GET | — | Project operational state | `project_operational_state()` |
| `/projects/health` | GET | `?min_tasks=1` | Projects ranked by health | `projects_by_health()` |

### Financial Endpoints
| Endpoint | Method | Parameters | Response | Query Engine Function |
|----------|--------|------------|----------|----------------------|
| `/financial/aging` | GET | — | Invoice aging report | `invoice_aging_report()` |

## Response Format

All endpoints return:
```json
{
  "status": "ok",
  "data": { ... },
  "computed_at": "2026-02-13T19:30:00Z",
  "params": { 
    "since": null,
    "until": null
  }
}
```

Error responses:
```json
{
  "status": "error",
  "error": "Client not found",
  "error_code": "NOT_FOUND"
}
```

## Implementation Plan

1. Create `api/intelligence_router.py` as separate FastAPI APIRouter
2. Mount in main app: `app.include_router(intelligence_router, prefix="/api/v2/intelligence")`
3. No modifications to `spec_router.py`
4. All endpoints call query engine functions directly

## Impact Assessment

| Item | Impact |
|------|--------|
| New files | `api/intelligence_router.py`, `tests/test_intelligence_api.py` |
| Modified files | Main app file to mount router (NOT spec_router.py) |
| Existing endpoints | No changes |
| Database | Read-only access via query engine |
| Tests | ~15-20 new endpoint tests |

## Endpoint Count
- Portfolio: 3 endpoints
- Client: 6 endpoints
- Team: 4 endpoints
- Project: 2 endpoints
- Financial: 1 endpoint
- **Total: 16 endpoints**

## Approval Request

Per GUARDRAILS.md Rule 2: "Do not modify api/spec_router.py without explicit approval."

This proposal:
- Does NOT modify spec_router.py
- Creates a NEW router (intelligence_router.py)
- All endpoints are read-only GET requests
- Fully tested before deployment

**Request:** Approval to proceed with implementation (Task 3.3 Steps 3-5).
