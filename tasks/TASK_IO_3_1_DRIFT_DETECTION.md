# IO-3.1: Intelligence Drift Detection

## Objective

Detect when the intelligence layer's outputs are drifting — scores clustering toward a narrow range, signals getting noisier (too many firing), or patterns becoming stale (same ones firing every cycle without change). Drift means the system is losing discriminating power.

## Dependencies

- IO-1.1 (audit trail)
- Brief 17 (score_history, signal_state, pattern_snapshots)

## Deliverables

### New file: `lib/intelligence/drift_detector.py`

```python
class DriftDetector:
    """Detects when intelligence outputs are losing discriminating power."""

    def __init__(self, db_path: Path): ...

    def detect_score_clustering(self, entity_type: str, days: int = 14) -> dict:
        """Detect if scores are converging toward a narrow range.
        Computes standard deviation of scores over time.
        Alert if stdev drops below 10 (scores bunching up).
        Returns:
        {
            "entity_type": "client",
            "current_stdev": 8.2,
            "previous_stdev": 14.5,  # 14 days ago
            "drift_detected": True,
            "direction": "converging",
            "headline": "Client scores are clustering — 80% of clients now score 55-70"
        }
        """

    def detect_signal_noise(self, days: int = 14) -> dict:
        """Detect if signals are getting noisier (too many firing).
        Alert if >60% of entities have active signals (threshold too loose)
        or <10% have signals (threshold too tight).
        Returns:
        {
            "signal_rate": 0.72,  # 72% of entities have signals
            "previous_rate": 0.45,
            "drift_detected": True,
            "direction": "noisy",
            "worst_signal_types": ["client_overdue_tasks"],  # most over-triggered
            "headline": "72% of clients have active signals — thresholds may be too loose"
        }
        """

    def detect_pattern_staleness(self, cycles: int = 10) -> dict:
        """Detect if the same patterns fire every cycle without change.
        Stale = same pattern, same entities, same severity for N consecutive cycles.
        Returns:
        {
            "stale_patterns": [
                { "pattern_id": "revenue_concentration", "consecutive_cycles": 8,
                  "entities_unchanged": True, "confidence_stable": True }
            ],
            "total_patterns": 12,
            "stale_count": 3,
            "headline": "3 patterns have been unchanged for 8+ cycles — consider recalibrating"
        }
        """

    def run_full_drift_scan(self) -> dict:
        """Run all drift checks and return combined report.
        Returns:
        {
            "score_drift": { ... },
            "signal_noise": { ... },
            "pattern_staleness": { ... },
            "overall_health": "ok" | "drifting" | "degraded",
            "recommendations": ["Tighten client_overdue_tasks threshold from 5 to 7", ...]
        }
        """
```

### Integration

- Run drift detection weekly (not every cycle — too noisy)
- Add to data lifecycle as a weekly check
- Emit `intelligence_drift` event when drift detected
- Include drift status in intelligence quality overview (DQ-4.1)

### Drift responses

Drift detection doesn't auto-fix. It surfaces recommendations that feed into:
- GAP-C (Adaptive Thresholds) — automated threshold adjustment
- recalibrate.py — manual recalibration

## Validation

- Score clustering detected when stdev drops below threshold
- Signal noise detected when firing rate exceeds 60%
- Pattern staleness detected for patterns unchanged over N cycles
- Full drift scan produces coherent report
- Recommendations are actionable (not vague)
- No false positives on healthy intelligence output distribution

## Estimated Effort

~250 lines
