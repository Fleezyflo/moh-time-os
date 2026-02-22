# IO-1.1: Computation Audit Trail

## Objective

Log every intelligence computation with inputs, outputs, and timing so that any score/signal/pattern can be traced back to what caused it.

## What Exists

- `intelligence_events` table logs signal_fired/pattern_detected events but not the computation that produced them
- `score_history` records final scores but not what metrics went in
- Logger calls exist but unstructured

## Deliverables

### New table: `intelligence_audit` (via v33 migration)

```sql
CREATE TABLE IF NOT EXISTS intelligence_audit (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    module TEXT NOT NULL,            -- 'scoring', 'signals', 'patterns', 'cost', 'quality'
    operation TEXT NOT NULL,         -- 'score_client', 'evaluate_signal', 'detect_pattern', etc.
    entity_type TEXT,
    entity_id TEXT,
    inputs_json TEXT NOT NULL,       -- serialized input metrics/data
    outputs_json TEXT NOT NULL,      -- serialized result
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL,            -- 'success', 'partial', 'error'
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_audit_cycle ON intelligence_audit(cycle_id);
CREATE INDEX idx_audit_entity ON intelligence_audit(entity_type, entity_id);
CREATE INDEX idx_audit_module ON intelligence_audit(module, operation);
CREATE INDEX idx_audit_time ON intelligence_audit(created_at);
```

### New file: `lib/intelligence/audit.py`

```python
class IntelligenceAuditor:
    """Records computation audit trail for intelligence modules."""

    def __init__(self, db_path: Path, cycle_id: str): ...

    @contextmanager
    def trace(self, module: str, operation: str,
              entity_type: str = None, entity_id: str = None,
              inputs: dict = None):
        """Context manager that times and logs a computation.

        Usage:
            with auditor.trace("scoring", "score_client", "client", "abc",
                              inputs={"tasks": 45, "overdue": 3}):
                result = score_client("abc")
        """
        # Records: start_time, inputs
        # On __exit__: records outputs, duration, status
        # On exception: records error, status='error'

    def record(self, module: str, operation: str, entity_type: str,
               entity_id: str, inputs: dict, outputs: dict,
               duration_ms: int, status: str = "success") -> bool:
        """Direct record (for cases where context manager isn't convenient)."""

    def get_entity_audit(self, entity_type: str, entity_id: str,
                         cycle_id: str = None, limit: int = 100) -> list[dict]:
        """Get all audit entries for an entity, optionally for a specific cycle."""

    def get_cycle_audit(self, cycle_id: str) -> dict:
        """Get full audit for a cycle — all modules, timing, error counts."""

    def cleanup(self, days: int = 7) -> int:
        """Delete audit entries older than N days. Keep recent for debugging."""
```

### Integration into `_intelligence_phase()`

Wrap each sub-step with `auditor.trace()`:

```python
auditor = IntelligenceAuditor(db_path, cycle_id)

# Sub-step 1: Scoring
with auditor.trace("scoring", "score_all_clients"):
    scores = score_all_clients(db_path=db_path)
```

### What gets logged as inputs/outputs

| Module | Operation | Inputs | Outputs |
|--------|-----------|--------|---------|
| scoring | score_client | { entity_id, dimensions_available } | { composite_score, classification, dimension_scores } |
| scoring | score_all_clients | { count } | { scored: N, skipped: N } |
| signals | evaluate_signal | { signal_type, entity, metrics_snapshot } | { detected: bool, severity, evidence } |
| signals | detect_all | {} | { total_signals, by_severity } |
| patterns | detect_pattern | { pattern_type } | { detected: bool, confidence, entities } |
| cost | compute_client | { client_id } | { effort, efficiency, profitability } |
| quality | score_entity | { entity_type, entity_id } | { quality_score, domains } |

**Size limit:** inputs_json and outputs_json capped at 10KB each. Truncate large arrays (e.g., full signal lists → just counts).

## Retention

Audit data is high-volume. Default retention: 7 days. Configurable. `cleanup()` called in data lifecycle phase (AO-4.1).

## Validation

- trace() records correct inputs and outputs
- trace() captures duration accurately
- trace() records errors on exception
- get_entity_audit returns correct entries for entity
- get_cycle_audit returns full cycle breakdown
- cleanup removes old entries
- Integration in _intelligence_phase() doesn't slow cycle by >5%

## Estimated Effort

~300 lines
