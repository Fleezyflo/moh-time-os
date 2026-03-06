# TASK: Wire Scenario Engine and Trajectory (deeper)
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.7 | Status: PENDING

## Context

Both modules are imported in `lib/intelligence/__init__.py` (the index) but NOT called by `_intelligence_phase()` or any API route. They're indexed but dormant.

1. `lib/intelligence/scenario_engine.py` (1188 lines) — `ScenarioEngine` class, `ScenarioType(StrEnum)`, `ScenarioResult`, `ScenarioComparison`. Models "what if" scenarios for business decisions.

2. `lib/intelligence/trajectory.py` (713 lines) — `TrajectoryEngine` class, `TrendDirection(Enum)`, `VelocityResult`, `AccelerationResult`, `TrendAnalysis`, `SeasonalityResult`, `ProjectionResult`, `FullTrajectory`. Computes velocity, acceleration, seasonality, projections for score trends.

## Objective

Wire trajectory into the loop and expose both via API endpoints.

## Instructions

### 1. Fix StrEnum dependency first

`scenario_engine.py:27` uses `from enum import StrEnum`. This MUST be fixed to `from lib.compat import StrEnum` before wiring. If TASK-P0-3 hasn't been done yet, do that fix in this file at minimum.

### 2. Wire `TrajectoryEngine` into `_intelligence_phase()`

After scoring, compute trajectories per entity:

```python
try:
    from lib.intelligence.trajectory import TrajectoryEngine
    trajectory_engine = TrajectoryEngine(db_path)
    trajectories = trajectory_engine.compute_all()  # adapt to actual method
    results["trajectories_computed"] = len(trajectories) if trajectories else 0
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Intelligence: trajectory failed: {e}")
```

### 3. Wire `ScenarioEngine` into API only (on-demand, not every cycle)

Scenario modeling is expensive and user-triggered. Don't run in the loop. Expose via API:

- `/api/v2/intelligence/trajectory/{entity_type}/{entity_id}` — returns trend data
- `/api/v2/intelligence/scenarios/model` — POST, accepts scenario config, returns results
- `/api/v2/intelligence/scenarios/compare` — POST, compares two scenarios

### 4. Read actual method signatures

```
python -c "from lib.intelligence.trajectory import TrajectoryEngine; print([m for m in dir(TrajectoryEngine) if not m.startswith('_')])"
python -c "from lib.intelligence.scenario_engine import ScenarioEngine; print([m for m in dir(ScenarioEngine) if not m.startswith('_')])"
```

## Preconditions
- [ ] TASK-P0-3 (StrEnum fix) must be done first, OR fix `scenario_engine.py:27` inline

## Validation
1. Trajectory computed per entity after scoring
2. `/api/v2/intelligence/trajectory/client/{id}` returns trend data
3. `/api/v2/intelligence/scenarios/model` accepts config, returns results
4. `ruff check`, `bandit` clean
5. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] `TrajectoryEngine` wired into intelligence phase
- [ ] `ScenarioEngine` exposed via API (not in loop)
- [ ] StrEnum import fixed
- [ ] All three API endpoints return valid JSON
- [ ] ruff, bandit clean

## Output
- Modified: `lib/autonomous_loop.py`, `api/intelligence_router.py`
- Possibly modified: `lib/intelligence/scenario_engine.py` (StrEnum fix)

## Estimate
2 hours

## Branch
`feat/wire-scenario-trajectory`
