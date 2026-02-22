# PS-5.1: Resource Optimizer & Validation

## Objective
Build a ResourceOptimizer that combines capacity forecasts, deadline predictions, and team capabilities to suggest rebalancing actions. Wire what-if scenarios for staffing changes. Validate all predictive models against historical accuracy.

## Implementation

### ResourceOptimizer (`lib/predictive/resource_optimizer.py`)
```python
class ResourceOptimizer:
    """Suggest task rebalancing based on predicted capacity + deadlines."""

    def optimize(self) -> List[RebalanceSuggestion]:
        """
        Algorithm:
          1. Get capacity forecast (PS-1.1)
          2. Identify overloaded people/lanes (>100% load)
          3. Identify underloaded people/lanes (<80% load)
          4. For each overloaded → underloaded pair:
             - Score skill match (expertise tags from user_profiles)
             - Score client familiarity (has person worked on this client before?)
             - Score task complexity (can underloaded person handle it?)
             - Compute feasibility_score = weighted average
          5. Rank suggestions by feasibility_score descending
          6. Return top N suggestions
        """

    def what_if_hire(self, role: str, lane_id: str, capacity_hours: int = 40) -> WhatIfResult:
        """Simulate: 'What if we hire a junior designer in Lane X?'"""

    def what_if_remove(self, person_id: str) -> WhatIfResult:
        """Simulate: 'What if Alice goes on leave for 2 weeks?'"""

    def what_if_move_tasks(self, moves: List[TaskMove]) -> WhatIfResult:
        """Simulate: 'What if we move these 5 tasks from Alice to Bob?'"""
```

### Suggestion Schema
```python
@dataclass
class RebalanceSuggestion:
    source_person_id: str
    source_person_name: str
    source_load_pct: float
    target_person_id: str
    target_person_name: str
    target_load_pct: float
    tasks_to_move: List[str]          # task IDs
    skill_match_score: float           # 0-1
    client_familiarity_score: float    # 0-1
    feasibility_score: float           # weighted composite
    projected_source_load_after: float
    projected_target_load_after: float
    reason: str                         # human-readable explanation

@dataclass
class WhatIfResult:
    scenario_description: str
    before: CapacityForecast
    after: CapacityForecast
    impact_summary: Dict[str, float]   # lane_id → load_change_pct
    deadline_impacts: List[DeadlinePrediction]  # re-predicted deadlines
    recommendation: str
```

### Scoring Weights
```python
OPTIMIZER_WEIGHTS = {
    'skill_match': 0.4,
    'client_familiarity': 0.3,
    'task_complexity': 0.2,
    'proximity': 0.1,  # same team/lane bonus
}
```

### API Endpoints
```
GET   /api/v2/predictive/optimize/suggestions
POST  /api/v2/predictive/optimize/what-if/hire
POST  /api/v2/predictive/optimize/what-if/remove
POST  /api/v2/predictive/optimize/what-if/move
```

### End-to-End Validation
```python
class PredictiveValidation:
    """Validate all Brief 23 predictive models."""

    def validate_capacity_forecast(self):
        """Compare 14-day forecast from 2 weeks ago against actuals."""

    def validate_deadline_predictions(self):
        """Compare predicted completion dates against actual completion dates."""

    def validate_cashflow_projection(self):
        """Compare projected daily balances against actual Xero data."""

    def validate_calendar_analysis(self):
        """Verify meeting load calculations against raw calendar data."""

    def accuracy_report(self) -> Dict:
        """Return MAPE (Mean Absolute Percentage Error) for each model."""
```

## Validation
- [ ] Rebalancing suggestions only propose feasible moves (skill match > 0.3)
- [ ] What-if hire correctly reduces load in target lane
- [ ] What-if remove correctly increases load on remaining team
- [ ] Suggestions ranked by feasibility score descending
- [ ] No suggestion moves tasks to someone already at >100% load
- [ ] End-to-end: forecast → predict → optimize pipeline runs without error
- [ ] Historical validation: MAPE < 30% for capacity forecasts
- [ ] All 5 predictive models callable from API endpoints

## Files Created
- `lib/predictive/resource_optimizer.py`
- `lib/predictive/validation.py`
- `tests/test_resource_optimizer.py`
- `tests/test_predictive_validation.py`

## Estimated Effort
Large — ~700 lines (optimizer + what-if + validation suite)
