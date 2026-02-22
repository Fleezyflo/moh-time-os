# PS-1.1: Capacity Forecaster

## Objective
Build a CapacityForecaster that projects load per lane, per person, per day for the next 14 days using current lane assignments, task velocity from the trajectory engine, and known upcoming commitments.

## Implementation

### CapacityForecaster (`lib/predictive/capacity_forecaster.py`)
```python
class CapacityForecaster:
    """14-day rolling capacity forecast using trajectory + lane data."""

    def forecast(self, horizon_days: int = 14) -> CapacityForecast:
        """
        Compute daily load projections per lane and per person.
        Steps:
          1. Load current lane assignments (Brief 5 capacity_lanes)
          2. Get task velocity per person from TrajectoryEngine
          3. Load upcoming PTO/holidays from calendar_events
          4. Project daily: new_tasks_expected - tasks_completed_at_velocity
          5. Accumulate into running load per day
        Returns CapacityForecast with daily breakdowns.
        """

    def get_overcommitted_days(self, threshold_pct: float = 100.0) -> List[OvercommitWarning]:
        """Flag days where projected load > threshold, at least 5 days ahead."""

    def suggest_rebalancing(self, forecast: CapacityForecast) -> List[RebalanceSuggestion]:
        """When lane A > 100% and lane B < 80%, suggest task moves."""

    def factor_pto(self, person_id: str, dates: List[str]) -> None:
        """Reduce person's available capacity on PTO days to 0."""
```

### Data Sources
```python
# From Brief 5 — Capacity Lanes
lanes = lane_manager.get_all_lanes()  # 7 lanes, current assignments

# From Brief 11 — Trajectory Engine
velocity = trajectory_engine.get_velocity(person_id)  # tasks/week
trend = trajectory_engine.get_trend(person_id)  # accelerating/decelerating

# From Brief 9 — Calendar Collector
pto_events = calendar_collector.get_events(
    person_id, category='out_of_office', range_days=14
)
```

### Forecast Output Schema
```python
@dataclass
class DailyForecast:
    date: str
    lane_id: str
    person_id: str
    assigned_tasks: int
    projected_completions: float  # based on velocity
    projected_new: float           # based on pipeline
    load_pct: float                # (assigned - completed + new) / capacity
    is_overcommitted: bool

@dataclass
class CapacityForecast:
    generated_at: str
    horizon_days: int
    daily: List[DailyForecast]
    overcommit_warnings: List[OvercommitWarning]
    summary: Dict[str, float]  # lane_id → avg_load_pct
```

### API Endpoints
```
GET  /api/v2/predictive/capacity?horizon=14&lane=...
GET  /api/v2/predictive/capacity/overcommitted?threshold=100
GET  /api/v2/predictive/capacity/rebalance
```

### Configurable Thresholds
```python
CAPACITY_CONFIG = {
    'overcommit_threshold_pct': 100,
    'warning_lookahead_days': 5,
    'rebalance_source_threshold': 100,  # suggest moves FROM lanes above this
    'rebalance_target_threshold': 80,   # suggest moves TO lanes below this
    'working_hours_per_day': 8,
}
```

## Validation
- [ ] Forecast produces 14 days of daily load projections
- [ ] PTO days correctly reduce person's capacity to 0
- [ ] Overcommit warnings fire when load > threshold
- [ ] Warnings only fire for days ≥5 days in the future
- [ ] Rebalancing suggestions reference correct source/target lanes
- [ ] Velocity data from trajectory engine correctly applied
- [ ] Empty lanes return 0% load (not error)

## Files Created
- `lib/predictive/capacity_forecaster.py`
- `api/predictive_router.py` (shared across PS tasks)
- `tests/test_capacity_forecaster.py`

## Estimated Effort
Large — ~600 lines
