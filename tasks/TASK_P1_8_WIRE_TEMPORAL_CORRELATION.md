# TASK: Wire Temporal Context and Correlation Confidence
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.8 | Status: PENDING

## Context

Two modules with minimal wiring (indexed but not called):

1. `lib/intelligence/temporal.py` (710 lines) — Three classes:
   - `BusinessCalendar` (line 80) — holiday/business-day awareness
   - `TemporalNormalizer` (line 334) — adjusts metrics for business days
   - `RecencyWeighter` (line 524) — weights recent data higher
   Currently 1 import from intelligence index only.

2. `lib/intelligence/correlation_confidence.py` (220 lines) — `CorrelationConfidenceCalculator` class, `CorrelationSignalEvidence`, `ConfidenceFactors`. Adjusts pattern correlation confidence based on evidence quality. Currently 1 import from index only.

## Objective

Wire temporal normalization into the scoring pipeline and correlation confidence into pattern detection.

## Instructions

### 1. Wire `TemporalNormalizer` BEFORE scoring in `_intelligence_phase()`

Temporal normalization should happen before scoring so that scores account for business calendar context:

```python
try:
    from lib.intelligence.temporal import TemporalNormalizer, BusinessCalendar
    calendar = BusinessCalendar()  # or with config
    normalizer = TemporalNormalizer(calendar)
    # Normalize raw metrics before scoring
    normalizer.normalize_current_data(db_path)  # adapt to actual method
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Intelligence: temporal normalization failed: {e}")
```

### 2. Wire `RecencyWeighter` into signal detection

Apply recency weighting to signal detection so recent signals carry more weight:

```python
from lib.intelligence.temporal import RecencyWeighter
weighter = RecencyWeighter()
# Apply to signal results
```

### 3. Wire `CorrelationConfidenceCalculator` AFTER pattern detection

After `detect_all_patterns()` runs, refine confidence scores:

```python
try:
    from lib.intelligence.correlation_confidence import CorrelationConfidenceCalculator
    confidence_calc = CorrelationConfidenceCalculator(db_path)
    refined_patterns = confidence_calc.refine(patterns)  # adapt to actual method
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Intelligence: correlation confidence failed: {e}")
```

### 4. Read actual signatures

These modules may take different constructor args. Read each before wiring.

## Preconditions
- [ ] None

## Validation
1. Scores adjusted for weekends/holidays
2. Pattern confidence includes correlation factors
3. `ruff check`, `bandit` clean on all touched files
4. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] `TemporalNormalizer` runs before scoring
- [ ] `RecencyWeighter` applied to signal detection
- [ ] `CorrelationConfidenceCalculator` refines pattern confidence
- [ ] No regression in scoring or pattern detection
- [ ] ruff, bandit clean

## Output
- Modified: `lib/autonomous_loop.py`

## Estimate
2 hours

## Branch
`feat/wire-temporal-correlation`
