"""
Evidence-Based Correlation Confidence — MOH TIME OS

Replaces hardcoded correlation confidence scores (0.7) with computed
confidence based on evidence quality. Multi-factor formula:

    confidence = (0.35 × component_completeness
                + 0.25 × severity_alignment
                + 0.20 × temporal_proximity
                + 0.20 × recurrence_factor)

Brief 18 (ID), Task ID-1.1
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, stdev

logger = logging.getLogger(__name__)


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

    def to_dict(self) -> dict:
        return {
            "component_completeness": round(self.component_completeness, 4),
            "severity_alignment": round(self.severity_alignment, 4),
            "temporal_proximity": round(self.temporal_proximity, 4),
            "recurrence_factor": round(self.recurrence_factor, 4),
            "final_confidence": round(self.final_confidence, 4),
        }


SEVERITY_MAP = {"CRITICAL": 3, "WARNING": 2, "WATCH": 1}


class CorrelationConfidenceCalculator:
    """Computes evidence-based confidence for compound risk correlations."""

    def __init__(self, cycle_length_hours: int = 24):
        """
        Initialize with cycle length.

        Args:
            cycle_length_hours: Length of one intelligence cycle in hours (default 24).
        """
        self.cycle_length_hours = cycle_length_hours

    def calculate(
        self,
        signals: list[CorrelationSignalEvidence],
        required_signals: int,
        recurrence_history: dict[str, list[bool]] | None = None,
        reference_time: datetime | None = None,
    ) -> ConfidenceFactors:
        """
        Calculate confidence for a correlation.

        Args:
            signals: Signals with evidence for this correlation.
            required_signals: Number of signals required for the compound rule.
            recurrence_history: Per-signal history of presence across cycles.
                Maps signal_key -> [present_in_cycle_0, ..., present_in_cycle_N]
                where cycle_0 is current.
            reference_time: Reference time for temporal calculations (default: now).

        Returns:
            ConfidenceFactors with final_confidence in [0.0, 1.0].
        """
        if not signals:
            return ConfidenceFactors(
                component_completeness=0.0,
                severity_alignment=0.0,
                temporal_proximity=0.0,
                recurrence_factor=0.0,
                final_confidence=0.0,
            )

        if reference_time is None:
            reference_time = datetime.now()

        if recurrence_history is None:
            recurrence_history = {}

        comp = self._component_completeness(signals, required_signals)
        sev = self._severity_alignment(signals)
        temp = self._temporal_proximity(signals, reference_time)
        rec = self._recurrence_factor(recurrence_history)

        final = 0.35 * comp + 0.25 * sev + 0.20 * temp + 0.20 * rec

        return ConfidenceFactors(
            component_completeness=comp,
            severity_alignment=sev,
            temporal_proximity=temp,
            recurrence_factor=rec,
            final_confidence=min(1.0, max(0.0, final)),
        )

    def _component_completeness(
        self,
        signals: list[CorrelationSignalEvidence],
        required_signals: int,
    ) -> float:
        """Fraction of required components currently present."""
        if required_signals <= 0:
            return 1.0
        present_count = sum(1 for s in signals if s.is_present)
        return min(1.0, present_count / required_signals)

    def _severity_alignment(
        self,
        signals: list[CorrelationSignalEvidence],
    ) -> float:
        """
        Measure of consistency in signal severities.

        1.0 if all same severity, penalised for mixed.
        Single signal = trivially aligned = 1.0.
        """
        present = [s for s in signals if s.is_present]
        if len(present) < 2:
            return 1.0

        values = [SEVERITY_MAP.get(s.severity, 1) for s in present]
        if len(set(values)) == 1:
            return 1.0

        std_sev = stdev(values)
        # Max possible std for range [1,3] with 2 values is 1.0
        max_possible_std = 1.0
        alignment = max(0.0, 1.0 - (std_sev / max_possible_std))
        return alignment

    def _temporal_proximity(
        self,
        signals: list[CorrelationSignalEvidence],
        reference_time: datetime,
    ) -> float:
        """
        1.0 if detected in current cycle, decays exponentially over time.

        Half-life = 3 cycles (e.g. 72 hours at 24h cycles).
        """
        present = [s for s in signals if s.is_present]
        if not present:
            return 0.0

        proximities = []
        half_life_hours = self.cycle_length_hours * 3

        for signal in present:
            hours_since = max(
                0.0,
                (reference_time - signal.detected_at).total_seconds() / 3600,
            )
            # 2^(-hours_since / half_life_hours)
            proximity = 2 ** (-hours_since / half_life_hours)
            proximities.append(proximity)

        return mean(proximities)

    def _recurrence_factor(
        self,
        recurrence_history: dict[str, list[bool]],
        lookback_cycles: int = 5,
    ) -> float:
        """
        Fraction of recent cycles where ALL required signals were
        simultaneously present.
        """
        if not recurrence_history:
            return 0.0

        histories = list(recurrence_history.values())
        if not histories:
            return 0.0

        # Trim all histories to lookback_cycles length (skip index 0 = current)
        trimmed = []
        for h in histories:
            # h[0] is current cycle, h[1:] is historical
            past = h[1 : lookback_cycles + 1] if len(h) > 1 else []
            trimmed.append(past)

        if not trimmed or not trimmed[0]:
            return 0.0

        # Align lengths
        min_len = min(len(t) for t in trimmed)
        if min_len == 0:
            return 0.0

        # For each past cycle, check if ALL signals were present
        all_present_count = 0
        for i in range(min_len):
            if all(t[i] for t in trimmed):
                all_present_count += 1

        return all_present_count / min_len
