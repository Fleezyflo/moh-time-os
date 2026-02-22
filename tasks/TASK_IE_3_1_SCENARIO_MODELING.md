# IE-3.1: Scenario Modeling Engine

## Objective
Build `lib/intelligence/scenario_engine.py` — answer "what-if" questions: "If we take client X, what happens to capacity?" "If we lose team member Y, which projects are at risk?"

## Context
Scenario modeling is a MASTER_SPEC requirement but NOT IMPLEMENTED. With cost-to-serve (IE-1.1) and pattern recognition (IE-2.1) providing the data foundation, scenario modeling builds on top to project future states.

## Implementation

### Scenario Types

1. **Add Client**: Given a client profile (estimated hours, communication volume, meeting frequency), project impact on team capacity and revenue
2. **Remove Client**: Given a client, project freed capacity, revenue loss, and team rebalancing needs
3. **Lose Team Member**: Given a team member, project affected projects, capacity gap, and redistribution options
4. **Add Team Member**: Given a role and capacity, project which overloaded projects benefit most
5. **Change Scope**: Given a project scope change (hours delta), project impact on other projects

### Engine Structure
```python
class ScenarioEngine:
    def __init__(self, db, cost_analyzer: CostToServeAnalyzer):
        self.db = db
        self.cost = cost_analyzer

    def simulate_add_client(self, client_profile: ClientProfile) -> ScenarioResult:
        """What happens if we onboard this client?"""
        current_capacity = self.get_team_capacity()
        required_capacity = client_profile.estimated_weekly_hours
        impact = self.compute_capacity_impact(current_capacity, required_capacity)
        revenue_projection = client_profile.estimated_monthly_revenue
        cost_projection = self.cost.estimate_client_cost(client_profile)
        return ScenarioResult(...)

    def simulate_lose_member(self, member_id: str) -> ScenarioResult:
        """What happens if this team member leaves?"""
        member_load = self.get_member_workload(member_id)
        affected_projects = self.get_member_projects(member_id)
        redistribution = self.compute_redistribution(member_load, affected_projects)
        return ScenarioResult(...)

@dataclass
class ScenarioResult:
    scenario_type: str
    summary: str
    capacity_impact: CapacityImpact  # before/after utilization
    revenue_impact: float
    cost_impact: float
    risk_factors: list[str]
    recommendations: list[str]
    affected_projects: list[str]
    affected_team_members: list[str]
    confidence: float
```

### Data Dependencies
- `capacity_truth` → current team utilization
- `cost_to_serve` → per-client cost baseline
- `time_blocks` → who works on what
- `tasks` → project assignments
- `invoices` → revenue baseline

## Validation
- [ ] Add-client scenario returns capacity and revenue projections
- [ ] Lose-member scenario identifies all affected projects
- [ ] Results are internally consistent (capacity before + delta = capacity after)
- [ ] Edge cases: fully utilized team, single-person projects, zero-revenue clients
- [ ] Tests with fixture data

## Files Created
- `lib/intelligence/scenario_engine.py`
- `tests/test_scenario_engine.py`

## Estimated Effort
Large — ~350 lines, complex capacity modeling and projection logic
