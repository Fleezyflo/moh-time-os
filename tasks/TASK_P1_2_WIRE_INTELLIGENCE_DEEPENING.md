# TASK: Wire Intelligence Deepening modules
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.2 | Status: PENDING

## Context

Four intelligence deepening modules exist with real code but zero imports from outside themselves:

1. `lib/intelligence/cost_proxies.py` (199 lines) — `ImprovedCostCalculator` class. Better cost calculation using task/thread/invoice data.
2. `lib/intelligence/entity_profile.py` (436 lines) — `build_entity_profile()` function + `EntityIntelligenceProfile` dataclass. Builds comprehensive intelligence profiles per entity.
3. `lib/intelligence/outcome_tracker.py` (393 lines) — `OutcomeTracker` class. Tracks signal outcomes to measure prediction accuracy.
4. `lib/intelligence/pattern_trending.py` (327 lines) — `PatternTrendAnalyzer` class. Analyzes how patterns evolve over time.

## Objective

Wire all four modules into `_intelligence_phase()` and/or API endpoints.

## Instructions

### 1. Wire into `_intelligence_phase()` in `lib/autonomous_loop.py`

- `cost_proxies.py` → after cost_to_serve (step 4). `ImprovedCostCalculator` enhances the base cost calculation.
- `entity_profile.py` → after scoring (step 1). `build_entity_profile()` aggregates scores, signals, patterns into one profile.
- `outcome_tracker.py` → after signals (step 2). `OutcomeTracker` records whether previous signals were accurate.
- `pattern_trending.py` → after patterns (step 3). `PatternTrendAnalyzer` tracks how patterns change over cycles.

```python
# Template per module (adapt method names):
try:
    from lib.intelligence.MODULE import MainClass
    instance = MainClass(db_path)
    result = instance.run()  # or .compute(), .analyze(), etc.
    results["module_key"] = len(result) if isinstance(result, list) else 1
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Intelligence: MODULE failed: {e}")
```

**Read each module's actual class/method signatures before wiring.**

### 2. Add API endpoint

In `api/intelligence_router.py`, add:
- `/entity/{entity_type}/{entity_id}/profile` — calls `build_entity_profile()` and returns the full profile

### 3. Verify imports work

```
python -c "from lib.intelligence.cost_proxies import ImprovedCostCalculator"
python -c "from lib.intelligence.entity_profile import build_entity_profile"
python -c "from lib.intelligence.outcome_tracker import OutcomeTracker"
python -c "from lib.intelligence.pattern_trending import PatternTrendAnalyzer"
```

## Preconditions
- [ ] None

## Validation
1. All four modules imported in `autonomous_loop.py`
2. `/api/v2/intelligence/entity/{type}/{id}/profile` returns JSON
3. `ruff check`, `bandit` clean on all touched files
4. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] All four modules wired into `_intelligence_phase()`
- [ ] Entity profile API endpoint exists
- [ ] Loop logs show deepening results
- [ ] ruff, bandit clean

## Output
- Modified: `lib/autonomous_loop.py`, `api/intelligence_router.py`

## Estimate
3 hours

## Branch
`feat/wire-intelligence-deepening`
