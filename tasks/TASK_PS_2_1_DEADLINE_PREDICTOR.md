# PS-2.1: Project Deadline Predictor

## Objective
Build a DeadlinePredictor that uses task completion velocity, remaining task count, and scope change rate to project completion dates via Monte Carlo simulation. Compare against committed deadlines and flag risks.

## Implementation

### DeadlinePredictor (`lib/predictive/deadline_predictor.py`)
```python
class DeadlinePredictor:
    """Monte Carlo deadline prediction using velocity + scope data."""

    def predict(self, project_id: str, simulations: int = 100) -> DeadlinePrediction:
        """
        Monte Carlo simulation:
          1. Get tasks_remaining for project
          2. Get velocity (tasks/week) from trajectory engine
          3. Get scope_change_rate (new tasks added per week, rolling 4-week avg)
          4. For each simulation:
             - Sample velocity from normal(mean_velocity, velocity_stddev)
             - Sample scope_change from normal(mean_scope_change, scope_stddev)
             - Compute weeks_to_complete = remaining / (velocity - scope_change)
             - Record predicted_date
          5. Return median, p10, p90 confidence interval
        """

    def predict_all_active(self) -> List[DeadlinePrediction]:
        """Run prediction for all projects with committed deadlines."""

    def get_at_risk(self, buffer_days: int = 3) -> List[DeadlinePrediction]:
        """Projects where p50 predicted date > committed date - buffer."""
```

### Prediction Output
```python
@dataclass
class DeadlinePrediction:
    project_id: str
    project_name: str
    committed_deadline: str | None
    tasks_remaining: int
    velocity_tasks_per_week: float
    scope_change_per_week: float
    predicted_date_p10: str      # optimistic (10th percentile)
    predicted_date_p50: str      # most likely (median)
    predicted_date_p90: str      # pessimistic (90th percentile)
    days_ahead_or_behind: int    # negative = behind schedule
    risk_level: str              # 'on_track' | 'at_risk' | 'behind'
    confidence: float            # 0-1, based on velocity stability
    simulation_results: List[str]  # raw dates from Monte Carlo runs
```

### Risk Level Calculation
```python
def _assess_risk(self, prediction: DeadlinePrediction) -> str:
    if prediction.committed_deadline is None:
        return 'no_deadline'
    if prediction.predicted_date_p50 <= prediction.committed_deadline:
        if prediction.predicted_date_p90 <= prediction.committed_deadline:
            return 'on_track'       # even pessimistic case makes it
        return 'at_risk'            # median makes it, pessimistic doesn't
    return 'behind'                 # median already misses deadline
```

### API Endpoints
```
GET  /api/v2/predictive/deadlines/:project_id
GET  /api/v2/predictive/deadlines/all
GET  /api/v2/predictive/deadlines/at-risk?buffer=3
```

## Validation
- [ ] Monte Carlo produces 100 simulation results
- [ ] p10/p50/p90 dates calculated correctly from simulation distribution
- [ ] Projects with zero velocity return risk_level = 'behind'
- [ ] Scope change rate correctly reduces effective velocity
- [ ] Risk levels assigned correctly based on committed vs predicted
- [ ] Projects without deadlines return 'no_deadline' risk
- [ ] Confidence lower when velocity has high variance

## Files Created
- `lib/predictive/deadline_predictor.py`
- `tests/test_deadline_predictor.py`

## Estimated Effort
Large — ~500 lines (Monte Carlo + statistics)
