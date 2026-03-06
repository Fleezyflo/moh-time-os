# TASK: Wire Intelligence Observability modules
> Brief: AUDIT_REMEDIATION | Priority: P1 | Sequence: P1.4 | Status: PENDING

## Context

Three intelligence observability modules exist with real code but zero imports:

1. `lib/intelligence/audit_trail.py` — `AuditTrail` class. Records what the intelligence pipeline computed and why.
2. `lib/intelligence/explainability.py` — `IntelligenceExplainer` class. Produces human-readable explanations for intelligence outputs.
3. `lib/intelligence/drift_detection.py` — `DriftDetector` class. Detects when score distributions shift significantly (`DriftAlert` dataclass, `classify_drift_severity()` function).

**Note:** The general `lib/observability/` directory IS wired (metrics, tracing, health used by server.py). These are intelligence-SPECIFIC observability modules in `lib/intelligence/` that provide transparency into what the intelligence pipeline is doing.

## Objective

Wire all three into the intelligence pipeline and expose via API.

## Instructions

### 1. Wire into `_intelligence_phase()`

- `audit_trail` — wraps the entire phase. Create an `AuditTrail` instance at the START, record inputs (which entities, data freshness). At the END, record outputs (scores, signals, patterns detected).
- `explainability` — after signals and patterns, generate explanations for the top N most significant findings.
- `drift_detection` — runs at the VERY END. Compares current score distributions against historical baselines. Logs `DriftAlert` if significant shifts detected.

### 2. Add API endpoints in `api/intelligence_router.py`

- `/audit-trail` — returns recent audit entries
- `/explain/{entity_type}/{entity_id}` — returns human-readable explanations for an entity's intelligence state

### 3. Read each module first

```
python -c "from lib.intelligence.audit_trail import AuditTrail, AuditEntry"
python -c "from lib.intelligence.explainability import IntelligenceExplainer, Explanation"
python -c "from lib.intelligence.drift_detection import DriftDetector, DriftAlert"
```

## Preconditions
- [ ] None

## Validation
1. Audit trail table populated after loop cycle
2. `/api/v2/intelligence/explain/{type}/{id}` returns explanations
3. Drift alerts logged when thresholds shift
4. `ruff check`, `bandit` clean
5. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] All three modules wired
- [ ] Audit trail records per-cycle inputs and outputs
- [ ] Explainability produces readable text
- [ ] Drift detection fires alerts when distributions shift
- [ ] API endpoints return valid JSON
- [ ] ruff, bandit clean

## Output
- Modified: `lib/autonomous_loop.py`, `api/intelligence_router.py`

## Estimate
2.5 hours

## Branch
`feat/wire-intelligence-observability`
