# IA-5.1: Scenario & Trajectory Endpoints

## Objective

Expose scenario modeling (what-if analysis) and trajectory projections via API. Unlike other intelligence endpoints which are read-only, scenario endpoints accept parameters and compute results on-demand.

## Dependencies

- IA-1.1 (router + envelope)
- `lib/intelligence/scenario_engine.py` (exists, 1,060 lines)
- `lib/intelligence/trajectory.py` (exists, 694 lines)
- Brief 18 ID-1.1 (correlation confidence for risk assessment)

## Endpoints

### Trajectory

#### GET `/api/v3/intelligence/trajectory/{entity_type}/{entity_id}`
Full trajectory for an entity — velocity, acceleration, trend direction, seasonality, 30-day projection.

Query params: `metric` (optional — specific metric like task_completion_rate; omit for composite score trajectory)

#### GET `/api/v3/intelligence/trajectory/portfolio`
Portfolio-level health trajectory. Returns list of entity trajectories sorted by concern (most declining first).

Query params: `entity_type` (filter), `direction` (filter: up/down/stable), `limit`

### Scenario Modeling

#### POST `/api/v3/intelligence/scenarios/client-loss`
Body: `{ "client_id": "abc123" }`
Models: revenue impact, freed capacity, affected team members, cascading project risks.

#### POST `/api/v3/intelligence/scenarios/client-addition`
Body: `{ "name": "Potential Client", "estimated_revenue": 50000, "estimated_tasks": 20 }`
Models: capacity impact, team assignment recommendations, revenue uplift, risk factors.

#### POST `/api/v3/intelligence/scenarios/resource-change`
Body: `{ "person_id": "xyz", "change_type": "departure|reduction|addition", "reduction_pct": 0.5 }`
Models: affected projects, capacity gap, redistribution options.

#### POST `/api/v3/intelligence/scenarios/pricing-change`
Body: `{ "client_id": "abc123", "new_rate": 150 }`
Models: profitability impact, comparison vs current, portfolio-level effect.

#### POST `/api/v3/intelligence/scenarios/workload-rebalance`
Body: `{}` (no params — auto-analyzes current state)
Models: optimal task redistribution, overload relief, underutilization correction.

## Response Shape (Scenarios)

```json
{
  "data": {
    "scenario_type": "client_loss",
    "parameters": { "client_id": "abc123", "client_name": "Client X" },
    "impact": {
      "revenue_change": -120000,
      "revenue_change_pct": -15.2,
      "capacity_freed_hours": 340,
      "affected_projects": 5,
      "affected_persons": 3,
      "portfolio_health_change": +4
    },
    "risks": [
      { "description": "Team member Y loses 60% of workload — may need reallocation", "severity": "warning" }
    ],
    "opportunities": [
      { "description": "Freed capacity could absorb pending Client Z onboarding", "impact": "high" }
    ],
    "recommendations": [
      "Redistribute Client X tasks before departure",
      "Review Client Z pipeline for capacity fit"
    ],
    "confidence": "medium"
  },
  "meta": { ... }
}
```

## Computation Notes

- Trajectory endpoints read from persisted `score_history` and compute trends on-the-fly (TrajectoryEngine). Target: <200ms.
- Scenario endpoints do live computation using ScenarioEngine. These are inherently more expensive. Target: <2000ms.
- Scenario results are NOT persisted — they're computed fresh each time. This is intentional (scenarios are exploratory, not recurring).
- Consider a simple in-memory cache with 5-minute TTL for repeated identical scenario requests.

## Validation

- Trajectory returns valid direction and velocity for real entities
- Trajectory portfolio sort puts most-declining entities first
- Client loss scenario returns revenue impact matching Xero data
- Resource change scenario identifies correct affected projects
- Workload rebalance produces non-trivial recommendations
- Invalid entity_id returns 404
- All scenario types handle edge cases (e.g., client with no projects)
- Response times within targets

## Estimated Effort

~300 lines
