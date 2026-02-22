# IE-4.1: Trajectory & Trend Computation

## Objective
Wire existing signal infrastructure to compute real trajectories — where is each metric heading over time — replacing hardcoded or static trend data.

## Context
The signal/issue model exists in both V4 and V5 architectures. Signals are written but trajectories (direction + velocity of change) are either hardcoded or not computed. The dashboard serves stale data from Feb 9. This task makes trajectories live.

## Implementation

### Trajectory Computation
```python
# lib/intelligence/trajectories.py

class TrajectoryComputer:
    def compute(self, metric: str, entity_id: str, window_days: int = 30) -> Trajectory:
        """Compute trend direction and velocity for a metric over time."""
        data_points = self.get_historical_values(metric, entity_id, window_days)
        if len(data_points) < 3:
            return Trajectory(direction="insufficient_data", velocity=0.0)

        slope = self.linear_regression_slope(data_points)
        volatility = self.compute_volatility(data_points)

        return Trajectory(
            direction="improving" if slope > threshold else "declining" if slope < -threshold else "stable",
            velocity=abs(slope),
            volatility=volatility,
            data_points=len(data_points),
            period_days=window_days,
            confidence=self.confidence_from_r_squared(data_points),
        )

@dataclass
class Trajectory:
    direction: str  # improving, declining, stable, insufficient_data
    velocity: float  # rate of change (units per day)
    volatility: float  # standard deviation of changes
    data_points: int
    period_days: int
    confidence: float  # R² of trend line
```

### Metrics to Track
| Metric | Entity | Source |
|--------|--------|--------|
| task_completion_rate | project | tasks table |
| email_response_time | client | communications table |
| meeting_acceptance_rate | team_member | calendar_attendees |
| invoice_collection_days | client | invoices table |
| capacity_utilization | team_member | time_blocks |
| communication_volume | client | communications table |
| overdue_task_count | project | tasks table |

### Storage
- Trajectories computed daily, stored in `trajectories` table
- Historical trajectory values kept for meta-trend analysis
- Trajectory data feeds into snapshot generation (live, not hardcoded)

### Integration
- TrajectoryComputer runs after truth modules in the cycle
- Results stored in DB and included in agency snapshot
- Pattern engine (IE-2.1) consumes trajectories as input signals

## Validation
- [ ] Trajectories computed for all defined metrics
- [ ] Direction correctly identifies improving/declining/stable
- [ ] Confidence score reflects data quality (low for sparse data)
- [ ] Snapshot uses live trajectory data instead of hardcoded values
- [ ] Historical trajectories accumulate over multiple cycles

## Files Created
- `lib/intelligence/trajectories.py`
- `tests/test_trajectories.py`

## Estimated Effort
Medium — ~200 lines, straightforward statistical computation
