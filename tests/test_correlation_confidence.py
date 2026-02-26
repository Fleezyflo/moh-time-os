"""
Tests for CorrelationConfidenceCalculator — evidence-based confidence.

Brief 18 (ID), Task ID-1.1 + ID-6.1
"""

from datetime import datetime, timedelta

import pytest

from lib.intelligence.correlation_confidence import (
    CorrelationConfidenceCalculator,
    CorrelationSignalEvidence,
)


@pytest.fixture
def calculator():
    return CorrelationConfidenceCalculator(cycle_length_hours=24)


def _signal(key, severity="WARNING", hours_ago=0, present=True, ref_time=None):
    if ref_time is None:
        ref_time = datetime(2026, 4, 15, 12, 0)
    return CorrelationSignalEvidence(
        signal_key=key,
        signal_type=f"sig_{key}",
        severity=severity,
        detected_at=ref_time - timedelta(hours=hours_ago),
        is_present=present,
    )


class TestComponentCompleteness:
    def test_all_present(self, calculator):
        signals = [_signal("a"), _signal("b"), _signal("c")]
        f = calculator.calculate(signals, required_signals=3)
        assert f.component_completeness == 1.0

    def test_partial_present(self, calculator):
        signals = [_signal("a"), _signal("b", present=False)]
        f = calculator.calculate(signals, required_signals=3)
        assert abs(f.component_completeness - 1 / 3) < 0.01

    def test_none_present(self, calculator):
        signals = [_signal("a", present=False), _signal("b", present=False)]
        f = calculator.calculate(signals, required_signals=2)
        assert f.component_completeness == 0.0

    def test_zero_required(self, calculator):
        f = calculator.calculate([_signal("a")], required_signals=0)
        assert f.component_completeness == 1.0


class TestSeverityAlignment:
    def test_all_same_severity(self, calculator):
        signals = [_signal("a", "CRITICAL"), _signal("b", "CRITICAL")]
        f = calculator.calculate(signals, required_signals=2)
        assert f.severity_alignment == 1.0

    def test_mixed_critical_watch(self, calculator):
        signals = [_signal("a", "CRITICAL"), _signal("b", "WATCH")]
        f = calculator.calculate(signals, required_signals=2)
        assert f.severity_alignment < 0.5

    def test_mixed_warning_watch(self, calculator):
        signals = [_signal("a", "WARNING"), _signal("b", "WATCH")]
        f = calculator.calculate(signals, required_signals=2)
        assert 0.2 < f.severity_alignment < 0.7

    def test_single_signal(self, calculator):
        signals = [_signal("a", "CRITICAL")]
        f = calculator.calculate(signals, required_signals=1)
        assert f.severity_alignment == 1.0


class TestTemporalProximity:
    def test_same_cycle(self, calculator):
        ref = datetime(2026, 4, 15, 12, 0)
        signals = [_signal("a", hours_ago=1, ref_time=ref)]
        f = calculator.calculate(signals, required_signals=1, reference_time=ref)
        assert f.temporal_proximity > 0.95

    def test_three_cycles_ago(self, calculator):
        ref = datetime(2026, 4, 15, 12, 0)
        signals = [_signal("a", hours_ago=72, ref_time=ref)]  # 3 cycles
        f = calculator.calculate(signals, required_signals=1, reference_time=ref)
        assert abs(f.temporal_proximity - 0.5) < 0.05  # half-life = 3 cycles

    def test_six_cycles_ago(self, calculator):
        ref = datetime(2026, 4, 15, 12, 0)
        signals = [_signal("a", hours_ago=144, ref_time=ref)]  # 6 cycles
        f = calculator.calculate(signals, required_signals=1, reference_time=ref)
        assert abs(f.temporal_proximity - 0.25) < 0.05

    def test_no_present_signals(self, calculator):
        signals = [_signal("a", present=False)]
        f = calculator.calculate(signals, required_signals=1)
        assert f.temporal_proximity == 0.0


class TestRecurrenceFactor:
    def test_always_present(self, calculator):
        history = {
            "sig_a": [True, True, True, True, True, True],
            "sig_b": [True, True, True, True, True, True],
        }
        f = calculator.calculate(
            [_signal("a"), _signal("b")],
            required_signals=2,
            recurrence_history=history,
        )
        assert f.recurrence_factor == 1.0

    def test_never_present_historically(self, calculator):
        history = {
            "sig_a": [True, False, False, False, False, False],
            "sig_b": [True, False, False, False, False, False],
        }
        f = calculator.calculate(
            [_signal("a"), _signal("b")],
            required_signals=2,
            recurrence_history=history,
        )
        assert f.recurrence_factor == 0.0

    def test_partial_recurrence(self, calculator):
        history = {
            "sig_a": [True, True, True, False, True, False],
            "sig_b": [True, True, False, True, True, False],
        }
        f = calculator.calculate(
            [_signal("a"), _signal("b")],
            required_signals=2,
            recurrence_history=history,
        )
        # Past cycles: [T&T, T&F, F&T, T&T, F&F] = [T, F, F, T, F] = 2/5 = 0.4
        assert abs(f.recurrence_factor - 0.4) < 0.01

    def test_no_history(self, calculator):
        f = calculator.calculate([_signal("a")], required_signals=1, recurrence_history={})
        assert f.recurrence_factor == 0.0


class TestFinalConfidence:
    def test_perfect_correlation(self, calculator):
        ref = datetime(2026, 4, 15, 12, 0)
        signals = [
            _signal("a", "CRITICAL", hours_ago=0, ref_time=ref),
            _signal("b", "CRITICAL", hours_ago=0, ref_time=ref),
        ]
        history = {
            "a": [True, True, True, True, True, True],
            "b": [True, True, True, True, True, True],
        }
        f = calculator.calculate(
            signals,
            required_signals=2,
            recurrence_history=history,
            reference_time=ref,
        )
        assert f.final_confidence > 0.8

    def test_weak_correlation(self, calculator):
        ref = datetime(2026, 4, 15, 12, 0)
        signals = [
            _signal("a", "CRITICAL", hours_ago=144, ref_time=ref),
            _signal("b", "WATCH", hours_ago=144, ref_time=ref, present=False),
        ]
        f = calculator.calculate(signals, required_signals=3)
        assert f.final_confidence < 0.6

    def test_empty_signals(self, calculator):
        f = calculator.calculate([], required_signals=3)
        assert f.final_confidence == 0.0
