# TASK: Wire Data Quality modules into intelligence pipeline
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.1 | Status: PENDING

## Context

Three data quality modules exist with real code but zero imports from outside themselves. They are dead code:

1. `lib/intelligence/data_freshness.py` (330 lines) — `DataFreshnessTracker` class. Tracks how stale each data source is.
2. `lib/intelligence/completeness_scorer.py` (271 lines) — `CompletenessScorer` class. Scores field completeness per entity.
3. `lib/intelligence/quality_confidence.py` (214 lines) — `QualityConfidenceAdjuster` class. Adjusts confidence scores based on data quality.

These should feed into the intelligence pipeline so that scoring and signal detection accounts for data quality.

## Objective

Wire all three modules into `_intelligence_phase()` in `lib/autonomous_loop.py` and expose via API.

## Instructions

### 1. Wire into `_intelligence_phase()` in `lib/autonomous_loop.py`

Add after step 1 (scoring), before step 2 (signals). Data quality informs signal confidence.

```python
# --- 1b. Data quality assessment ---
try:
    from lib.intelligence.data_freshness import DataFreshnessTracker
    from lib.intelligence.completeness_scorer import CompletenessScorer
    from lib.intelligence.quality_confidence import QualityConfidenceAdjuster

    freshness_tracker = DataFreshnessTracker(db_path)
    freshness_results = freshness_tracker.compute_all()
    results["freshness_checks"] = len(freshness_results) if freshness_results else 0

    completeness_scorer = CompletenessScorer(db_path)
    completeness_results = completeness_scorer.score_all()
    results["completeness_scores"] = len(completeness_results) if completeness_results else 0

    quality_adjuster = QualityConfidenceAdjuster(db_path)
    quality_results = quality_adjuster.adjust_all()
    results["quality_adjustments"] = len(quality_results) if quality_results else 0
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Intelligence: data quality assessment failed: {e}")
```

**Important:** Read each module's actual method signatures before wiring. The above is a template — adapt method names to match what actually exists in each class.

### 2. Add API endpoint in `api/intelligence_router.py`

Add a `/data-quality` GET endpoint that returns freshness + completeness + confidence data.

### 3. Verify the wiring

- Each module's main class must be importable: `python -c "from lib.intelligence.data_freshness import DataFreshnessTracker"`
- Each module must have its constructor accept `db_path` (or adapt wiring if it takes different args)

## Preconditions
- [ ] None — these modules have no dependencies on other P1 tasks

## Validation
1. `grep -rn "data_freshness\|completeness_scorer\|quality_confidence" lib/autonomous_loop.py` — shows imports
2. `grep -rn "data.quality\|data-quality" api/intelligence_router.py` — shows endpoint
3. `ruff check lib/autonomous_loop.py api/intelligence_router.py` — clean
4. `bandit -r lib/autonomous_loop.py api/intelligence_router.py` — clean
5. `python -m pytest tests/ -x` — passes

## Acceptance Criteria
- [ ] All three modules imported and called in `_intelligence_phase()`
- [ ] `/api/v2/intelligence/data-quality` endpoint exists and returns JSON
- [ ] Loop logs show freshness/completeness/quality results
- [ ] ruff, bandit clean on all touched files

## Output
- Modified: `lib/autonomous_loop.py`, `api/intelligence_router.py`

## Estimate
2 hours

## Branch
`feat/wire-data-quality`
