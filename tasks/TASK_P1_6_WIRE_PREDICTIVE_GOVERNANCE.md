# TASK: Wire Predictive Intelligence and Data Governance (intelligence layer)
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.6 | Status: PENDING

## Context

Two substantial modules exist with zero imports from the pipeline:

1. `lib/intelligence/predictive_intelligence.py` — `PredictiveIntelligence` class, `EarlyWarning`, `HealthForecast`, `ProactiveRecommendation`. Functions: `linear_forecast()`, `detect_decline_pattern()`, `estimate_churn_probability()`. Early warning system for entity health decline.

2. `lib/intelligence/data_governance.py` (674 lines) — Full GDPR-style governance within intelligence layer:
   - `DataCatalog` class (column/table classification)
   - `DataExporter` class (export management)
   - `SubjectAccessManager` class (SAR/deletion)
   - `RetentionEnforcer` class (data retention)
   - `ComplianceReporter` class (compliance reports)

**Note:** `lib/governance/` (separate directory) IS wired. This is the intelligence-layer governance that adds data classification and compliance reporting to the intelligence pipeline specifically.

## Objective

Wire predictive intelligence into the loop and expose governance reporting via API.

## Instructions

### 1. Wire `PredictiveIntelligence` into `_intelligence_phase()`

After scoring + signals, run predictive intelligence to generate early warnings:

```python
try:
    from lib.intelligence.predictive_intelligence import PredictiveIntelligence
    predictor = PredictiveIntelligence(db_path)
    warnings = predictor.generate_early_warnings()  # adapt to actual method
    results["early_warnings"] = len(warnings) if warnings else 0
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Intelligence: predictive failed: {e}")
```

### 2. Wire `ComplianceReporter` periodically (not every cycle)

Data governance compliance is expensive. Run it every N cycles or once per day:

```python
# Add a counter or timestamp check
if self._should_run_compliance():
    try:
        from lib.intelligence.data_governance import ComplianceReporter
        reporter = ComplianceReporter(db_path)
        report = reporter.generate()
        results["compliance_report"] = True
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.error(f"Intelligence: compliance report failed: {e}")
```

### 3. Add API endpoints

- `/api/v2/intelligence/predictions/early-warnings` — returns current early warnings
- `/api/v2/intelligence/governance/compliance-report` — returns latest compliance report

## Preconditions
- [ ] None

## Validation
1. Early warnings generated for declining entities
2. Compliance report queryable via API
3. Governance modules don't run every cycle (performance guard)
4. `ruff check`, `bandit` clean
5. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] `PredictiveIntelligence` wired into intelligence phase
- [ ] `ComplianceReporter` runs periodically
- [ ] Both API endpoints return valid JSON
- [ ] ruff, bandit clean

## Output
- Modified: `lib/autonomous_loop.py`, `api/intelligence_router.py`

## Estimate
2.5 hours

## Branch
`feat/wire-predictive-governance`
