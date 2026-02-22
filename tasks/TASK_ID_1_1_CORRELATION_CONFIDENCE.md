# ID-1.1: Evidence-Based Correlation Confidence
> Brief: Intelligence Depth & Cross-Domain Synthesis | Phase: 1 | Sequence: 1.1 | Status: PENDING

## Objective

Replace hardcoded correlation confidence scores with computed confidence based on evidence quality. Current system assigns all compound risk correlations `confidence=0.7`. This task implements a multi-factor confidence calculation that reflects the actual strength of evidence for each correlation.

## Implementation

### Confidence Formula

```
confidence = (0.35 × component_completeness + 0.25 × severity_alignment + 0.20 × temporal_proximity + 0.20 × recurrence_factor)
```

Where:
- **component_completeness**: fraction of required components present in compound risk rule (0.0 to 1.0)
- **severity_alignment**: 1.0 if all components have the same severity level, scaled down for mixed severity (0.0 to 1.0)
- **temporal_proximity**: 1.0 if detected within same intelligence cycle, exponentially decays over time using `detected_at` from `signal_state` and `pattern_snapshots` (0.0 to 1.0)
- **recurrence_factor**: ratio of recent cycles (last N cycles) where this compound risk appeared (0.0 to 1.0)

### New File: `lib/intelligence/correlation_confidence.py`

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional

@dataclass
class CorrelationSignalEvidence:
    """Evidence for one signal contributing to a correlation."""
    signal_key: str
    signal_type: str
    severity: str  # 'CRITICAL' | 'WARNING' | 'WATCH'
    detected_at: datetime
    is_present: bool  # currently active in signal_state


@dataclass
class ConfidenceFactors:
    """Breakdown of confidence calculation for inspection."""
    component_completeness: float
    severity_alignment: float
    temporal_proximity: float
    recurrence_factor: float
    final_confidence: float


class CorrelationConfidenceCalculator:
    """Computes evidence-based confidence for compound risk correlations."""

    def __init__(self, cycle_length_hours: int = 24):
        """Initialize with cycle length (default 24 hours)."""
        self.cycle_length_hours = cycle_length_hours

    def calculate(
        self,
        signals: List[CorrelationSignalEvidence],
        required_signals: int,
        recurrence_history: Dict[str, List[bool]],  # signal_key -> [present_in_cycle_1, ...]
        current_cycle_index: int = 0
    ) -> ConfidenceFactors:
        """
        Calculate confidence for a correlation.
        
        Args:
            signals: List of signals with evidence for this correlation
            required_signals: Number of signals required for the rule
            recurrence_history: Per-signal history of presence across cycles
            current_cycle_index: Index of current cycle (0 = latest)
            
        Returns:
            ConfidenceFactors with final_confidence in [0.0, 1.0]
        """

    def _component_completeness(
        self,
        signals: List[CorrelationSignalEvidence],
        required_signals: int
    ) -> float:
        """Fraction of required components currently present."""

    def _severity_alignment(
        self,
        signals: List[CorrelationSignalEvidence]
    ) -> float:
        """Measure of consistency in signal severities."""

    def _temporal_proximity(
        self,
        signals: List[CorrelationSignalEvidence],
        reference_time: Optional[datetime] = None
    ) -> float:
        """1.0 if all detected in current cycle, decays exponentially over time."""

    def _recurrence_factor(
        self,
        recurrence_history: Dict[str, List[bool]],
        lookback_cycles: int = 5
    ) -> float:
        """Ratio of recent cycles where compound risk appeared."""
```

### Modified: `lib/intelligence/correlation_engine.py`

When creating or updating compound risks:
```python
# Old approach (in correlation_engine.py):
compound_risk = {
    "correlation_id": ...,
    "confidence": 0.7,  # hardcoded
    ...
}

# New approach:
factors = self.confidence_calculator.calculate(
    signals=evidence_signals,
    required_signals=rule.required_signal_count,
    recurrence_history=self._build_recurrence_history(rule),
    current_cycle_index=0
)
compound_risk = {
    "correlation_id": ...,
    "confidence": factors.final_confidence,
    "confidence_factors": {  # optional: for debugging
        "component_completeness": factors.component_completeness,
        "severity_alignment": factors.severity_alignment,
        "temporal_proximity": factors.temporal_proximity,
        "recurrence_factor": factors.recurrence_factor,
    },
    ...
}
```

## Deepened Specifications

### Temporal Decay Formula

```python
def _temporal_proximity(self, signals: list, reference_time: datetime = None) -> float:
    """
    Exponential decay based on hours since detection.

    For each signal:
      hours_since = (reference_time - signal.detected_at).total_seconds() / 3600
      signal_proximity = 2 ** (-hours_since / (self.cycle_length_hours * 3))
      # Half-life = 3 cycles (72 hours at 24h cycles)
      # Same cycle: ~1.0, 1 cycle ago: ~0.79, 3 cycles: 0.5, 6 cycles: 0.25

    temporal_proximity = mean(signal_proximity for signal in signals if signal.is_present)

    If no present signals: return 0.0
    """
```

### Severity Alignment Penalty Formula

```python
def _severity_alignment(self, signals: list) -> float:
    """
    Measures consistency of signal severities.

    severity_map = {"CRITICAL": 3, "WARNING": 2, "WATCH": 1}
    values = [severity_map[s.severity] for s in signals if s.is_present]

    If len(values) < 2: return 1.0  # single signal = trivially aligned

    # Compute normalized standard deviation
    mean_sev = mean(values)
    std_sev = stdev(values)
    max_possible_std = 1.0  # max std when values span full range [1,3]

    alignment = 1.0 - (std_sev / max_possible_std)

    Examples:
      All CRITICAL: std=0 → alignment=1.0
      All WARNING: std=0 → alignment=1.0
      Mix CRITICAL+WATCH: std≈1.0 → alignment≈0.0
      Mix WARNING+WATCH: std≈0.5 → alignment≈0.5
    """
```

### Recurrence History Construction

```python
def _build_recurrence_history(self, rule, lookback_cycles: int = 5) -> dict:
    """
    Query pattern_snapshots for the last N cycles.
    For each signal_key in the rule's required signals:
      Check if signal was present in each cycle's signal_state snapshot.

    Returns: {
        "sig_overdue_tasks::client_x": [True, True, False, True, True],
        "sig_comm_drop::client_x": [True, False, False, False, True],
    }

    recurrence_factor = mean(
        all(signal_present for signal_present in cycle_presence)
        for cycle_presence in zip(*history.values())
    )
    # = fraction of cycles where ALL required signals were simultaneously present
    """
```

## Validation

- [ ] Confidence scores vary meaningfully across different correlation scenarios (not all 0.7)
- [ ] Full completeness (all required signals present, same severity, detected in current cycle, persistent): confidence > 0.8
- [ ] Missing one signal or mixed severities: confidence in [0.4, 0.7]
- [ ] Old signal with low recurrence: confidence < 0.5
- [ ] Temporal decay reduces confidence over time for same signals
- [ ] Recurrence history correctly computed from pattern_snapshots table
- [ ] Component completeness formula tested with varying signal counts
- [ ] Severity alignment correctly penalizes mixed severities

## Files Created
- New: `lib/intelligence/correlation_confidence.py`

## Files Modified
- Modified: `lib/intelligence/correlation_engine.py` (integrate confidence calculator)

## Estimated Effort
~200 lines — confidence calculation logic, temporal decay math, recurrence aggregation

