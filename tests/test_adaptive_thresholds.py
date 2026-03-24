"""
Tests for adaptive threshold engine, seasonal modifiers, and calibration reports.

GAP-10-04: Covers ThresholdAdjuster, CalibrationReporter, and end-to-end
signal -> effectiveness -> adjustment flow.
"""

from datetime import date
from unittest.mock import Mock, patch

import pytest
import yaml

from lib.intelligence.threshold_adjuster import (
    MAX_CHANGE_PER_CYCLE,
    AdjustmentHistory,
    SignalEffectiveness,
    ThresholdAdjuster,
    ThresholdAdjustment,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_thresholds(tmp_path):
    """Create a temporary thresholds.yaml for testing."""
    thresholds = {
        "signals": {
            "sig_client_comm_drop": {
                "threshold_ratio": 0.5,
                "operator": "lt",
            },
            "sig_client_neglected": {
                "value": 21,
                "operator": "gt",
            },
            "sig_client_invoice_aging": {
                "value": 45,
                "operator": "gt",
            },
            "sig_person_overloaded": {
                "value": 120,
                "operator": "gt",
            },
            "sig_project_stalled": {
                "value": 14,
                "operator": "gt",
            },
        },
    }
    path = tmp_path / "thresholds.yaml"
    with open(path, "w") as f:
        yaml.dump(thresholds, f)
    return path


@pytest.fixture
def adjuster(sample_thresholds):
    """Create ThresholdAdjuster with test thresholds."""
    return ThresholdAdjuster(
        thresholds_path=sample_thresholds,
        cooldown_days=0,  # No cooldown for tests
    )


@pytest.fixture
def high_fp_feedback():
    """Feedback with high false positive rate (< 50% TPR)."""
    return [
        {"signal_id": "sig_client_neglected", "was_true_positive": False, "action_taken": False}
        for _ in range(8)
    ] + [
        {"signal_id": "sig_client_neglected", "was_true_positive": True, "action_taken": True}
        for _ in range(4)
    ]


@pytest.fixture
def high_effectiveness_feedback():
    """Feedback with high TPR and high action rate."""
    return [
        {"signal_id": "sig_client_neglected", "was_true_positive": True, "action_taken": True}
        for _ in range(12)
    ]


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestSignalEffectiveness:
    def test_to_dict(self):
        eff = SignalEffectiveness(
            signal_id="sig_test",
            total_fires=10,
            true_positives=7,
            false_positives=3,
            actions_taken=5,
            true_positive_rate=0.7,
            action_rate=0.5,
        )
        d = eff.to_dict()
        assert d["signal_id"] == "sig_test"
        assert d["true_positive_rate"] == 0.7

    def test_defaults(self):
        eff = SignalEffectiveness(signal_id="sig_test")
        assert eff.total_fires == 0
        assert eff.true_positive_rate == 0.0


class TestThresholdAdjustment:
    def test_to_dict(self):
        adj = ThresholdAdjustment(
            signal_id="sig_test",
            field="value",
            old_value=21.0,
            new_value=25.0,
            reason="test",
            adjustment_type="effectiveness",
        )
        d = adj.to_dict()
        assert d["signal_id"] == "sig_test"
        assert d["old_value"] == 21.0
        assert d["new_value"] == 25.0
        assert d["applied"] is False


class TestAdjustmentHistory:
    def test_to_dict_empty(self):
        hist = AdjustmentHistory(signal_id="sig_test")
        d = hist.to_dict()
        assert d["signal_id"] == "sig_test"
        assert d["adjustments"] == []
        assert d["frozen"] is False


# =============================================================================
# THRESHOLD ADJUSTER TESTS
# =============================================================================


class TestThresholdAdjuster:
    def test_load_thresholds(self, adjuster):
        """Verify thresholds load from YAML."""
        thresholds = adjuster.get_current_thresholds()
        assert "signals" in thresholds
        assert "sig_client_neglected" in thresholds["signals"]
        assert thresholds["signals"]["sig_client_neglected"]["value"] == 21

    def test_no_adjustment_insufficient_samples(self, adjuster):
        """Below MIN_FEEDBACK_SAMPLES -> no adjustments."""
        feedback = [
            {"signal_id": "sig_client_neglected", "was_true_positive": False, "action_taken": False}
            for _ in range(5)
        ]
        result = adjuster.run_adjustment_cycle(feedback)
        assert result["applied_count"] == 0

    def test_high_false_positive_relaxes_threshold(self, adjuster, high_fp_feedback):
        """High FP rate should relax (increase) the threshold value."""
        original = adjuster.get_current_thresholds()["signals"]["sig_client_neglected"]["value"]
        result = adjuster.run_adjustment_cycle(high_fp_feedback)

        # Should have at least one effectiveness adjustment
        eff_adjustments = [
            a for a in result["adjustments"] if a["adjustment_type"] == "effectiveness"
        ]
        assert len(eff_adjustments) > 0

        # New value should be higher (relaxed)
        new_thresholds = adjuster.get_current_thresholds()
        assert new_thresholds["signals"]["sig_client_neglected"]["value"] > original

    def test_high_effectiveness_tightens_threshold(self, adjuster, high_effectiveness_feedback):
        """High TPR + high action rate should tighten (decrease) the threshold."""
        original = adjuster.get_current_thresholds()["signals"]["sig_client_neglected"]["value"]
        result = adjuster.run_adjustment_cycle(high_effectiveness_feedback)

        eff_adjustments = [
            a for a in result["adjustments"] if a["adjustment_type"] == "effectiveness"
        ]
        assert len(eff_adjustments) > 0
        new_thresholds = adjuster.get_current_thresholds()
        assert new_thresholds["signals"]["sig_client_neglected"]["value"] < original

    def test_cap_at_30_percent(self, adjuster):
        """Adjustments must not exceed +-30% of original."""
        # Create extreme feedback (0% TPR)
        feedback = [
            {"signal_id": "sig_client_neglected", "was_true_positive": False, "action_taken": False}
            for _ in range(20)
        ]
        original = adjuster.get_current_thresholds()["signals"]["sig_client_neglected"]["value"]
        adjuster.run_adjustment_cycle(feedback)

        new_val = adjuster.get_current_thresholds()["signals"]["sig_client_neglected"]["value"]
        max_allowed = original * (1 + MAX_CHANGE_PER_CYCLE)
        assert new_val <= max_allowed + 0.01  # Float tolerance

    def test_save_thresholds(self, adjuster, high_fp_feedback, sample_thresholds):
        """Verify save_thresholds writes back to YAML."""
        adjuster.run_adjustment_cycle(high_fp_feedback)
        assert adjuster.save_thresholds() is True

        # Reload and verify
        with open(sample_thresholds) as f:
            reloaded = yaml.safe_load(f)
        assert reloaded["signals"]["sig_client_neglected"]["value"] != 21

    def test_missing_thresholds_file(self, tmp_path):
        """Non-existent file should return empty signals."""
        adjuster = ThresholdAdjuster(
            thresholds_path=tmp_path / "nonexistent.yaml",
            cooldown_days=0,
        )
        assert adjuster.get_current_thresholds() == {"signals": {}}

    def test_get_history_empty(self, adjuster):
        """History is empty before any adjustments."""
        assert adjuster.get_history() == []

    def test_get_history_after_adjustment(self, adjuster, high_fp_feedback):
        """History records adjustments."""
        adjuster.run_adjustment_cycle(high_fp_feedback)
        history = adjuster.get_history()
        assert len(history) > 0
        assert history[0]["signal_id"] == "sig_client_neglected"


# =============================================================================
# SEASONAL MODIFIER TESTS
# =============================================================================


class TestSeasonalModifiers:
    def test_q4_modifiers_applied(self, adjuster):
        """Q4 close season should tighten financial signals."""
        # Q4 is typically Nov-Dec
        q4_date = date(2025, 11, 15)
        with patch.object(adjuster._calendar, "get_season", return_value="q4_close"):
            with patch.object(
                adjuster._calendar,
                "get_day_context",
                return_value=Mock(is_ramadan=False),
            ):
                result = adjuster.run_adjustment_cycle([], reference_date=q4_date)

        assert result["season"] == "q4_close"
        seasonal_adjs = [a for a in result["adjustments"] if a["adjustment_type"] == "seasonal"]
        # Should have adjustments for invoice_aging at minimum
        if "sig_client_invoice_aging" in adjuster.get_current_thresholds().get("signals", {}):
            assert len(seasonal_adjs) > 0

    def test_ramadan_modifiers_applied(self, adjuster):
        """Ramadan should relax communication thresholds."""
        with patch.object(adjuster._calendar, "get_season", return_value="normal"):
            with patch.object(
                adjuster._calendar,
                "get_day_context",
                return_value=Mock(is_ramadan=True),
            ):
                modifiers = adjuster.get_seasonal_modifiers(date(2025, 3, 15))

        assert modifiers["is_ramadan"] is True
        assert "sig_client_comm_drop" in modifiers["modifiers"]
        assert modifiers["modifiers"]["sig_client_comm_drop"] > 1.0  # Relaxed

    def test_summer_modifiers(self, adjuster):
        """Summer slowdown should relax activity thresholds."""
        with patch.object(adjuster._calendar, "get_season", return_value="summer_slowdown"):
            with patch.object(
                adjuster._calendar,
                "get_day_context",
                return_value=Mock(is_ramadan=False),
            ):
                modifiers = adjuster.get_seasonal_modifiers(date(2025, 7, 15))

        assert modifiers["season"] == "summer_slowdown"
        assert "sig_project_stalled" in modifiers["modifiers"]

    def test_normal_season_no_modifiers(self, adjuster):
        """Normal season should have no seasonal modifiers."""
        with patch.object(adjuster._calendar, "get_season", return_value="normal"):
            with patch.object(
                adjuster._calendar,
                "get_day_context",
                return_value=Mock(is_ramadan=False),
            ):
                modifiers = adjuster.get_seasonal_modifiers(date(2025, 4, 15))

        assert modifiers["modifiers"] == {}


# =============================================================================
# OSCILLATION DETECTION TESTS
# =============================================================================


class TestOscillationDetection:
    def test_oscillation_freezes_signal(self, sample_thresholds):
        """Threshold that flip-flops 3+ times should be frozen."""
        adjuster = ThresholdAdjuster(
            thresholds_path=sample_thresholds,
            cooldown_days=0,
        )

        sig_id = "sig_client_neglected"

        # Simulate oscillating adjustments manually
        hist = AdjustmentHistory(signal_id=sig_id)
        adjuster._history[sig_id] = hist

        # Up, down, up = 2 direction changes, then one more
        adjustments = [
            ThresholdAdjustment(sig_id, "value", 21, 25, "up", "test"),
            ThresholdAdjustment(sig_id, "value", 25, 20, "down", "test"),
            ThresholdAdjustment(sig_id, "value", 20, 26, "up", "test"),
        ]

        for adj in adjustments:
            hist.adjustments.append(adj)
            adjuster._check_oscillation(hist)

        assert hist.frozen is True
        assert "Oscillation detected" in hist.freeze_reason

    def test_no_oscillation_same_direction(self, sample_thresholds):
        """Adjustments all in same direction should not freeze."""
        adjuster = ThresholdAdjuster(
            thresholds_path=sample_thresholds,
            cooldown_days=0,
        )

        sig_id = "sig_client_neglected"
        hist = AdjustmentHistory(signal_id=sig_id)
        adjuster._history[sig_id] = hist

        # All going up
        adjustments = [
            ThresholdAdjustment(sig_id, "value", 21, 23, "up1", "test"),
            ThresholdAdjustment(sig_id, "value", 23, 25, "up2", "test"),
            ThresholdAdjustment(sig_id, "value", 25, 27, "up3", "test"),
        ]

        for adj in adjustments:
            hist.adjustments.append(adj)
            adjuster._check_oscillation(hist)

        assert hist.frozen is False


# =============================================================================
# CALIBRATION REPORTER TESTS
# =============================================================================


class TestCalibrationReporter:
    def test_weekly_report(self):
        """Weekly report should return valid CalibrationReport."""
        from lib.intelligence.calibration_reporter import CalibrationReporter

        reporter = CalibrationReporter()
        report = reporter.weekly_report(feedback=[])
        d = report.to_dict()
        assert d["report_type"] == "weekly"
        assert "generated_at" in d

    def test_effectiveness_report(self):
        """Effectiveness report with feedback data."""
        from lib.intelligence.calibration_reporter import CalibrationReporter

        feedback = [
            {"signal_id": "sig_test", "was_true_positive": True, "action_taken": True}
            for _ in range(15)
        ]
        reporter = CalibrationReporter()
        report = reporter.effectiveness_report(feedback=feedback)
        d = report.to_dict()
        assert d["report_type"] == "effectiveness"

    def test_history_report(self):
        """History report for a specific signal."""
        from lib.intelligence.calibration_reporter import CalibrationReporter

        reporter = CalibrationReporter()
        report = reporter.history_report(signal_id="sig_client_neglected")
        d = report.to_dict()
        assert d["report_type"] == "history"

    def test_format_for_briefing(self):
        """Briefing format should have expected keys."""
        from lib.intelligence.calibration_reporter import CalibrationReporter

        reporter = CalibrationReporter()
        report = reporter.weekly_report(feedback=[])
        briefing = reporter.format_for_briefing(report)
        assert "type" in briefing
        assert briefing["type"] == "calibration_update"
        assert "headline" in briefing


# =============================================================================
# END-TO-END TESTS
# =============================================================================


class TestEndToEnd:
    def test_signal_effectiveness_adjustment_cycle(self, sample_thresholds):
        """Full cycle: feedback -> effectiveness -> adjustment -> history."""
        adjuster = ThresholdAdjuster(
            thresholds_path=sample_thresholds,
            cooldown_days=0,
        )

        # Create feedback showing low TPR for client_neglected
        feedback = [
            {"signal_id": "sig_client_neglected", "was_true_positive": False, "action_taken": False}
            for _ in range(15)
        ]

        original = adjuster.get_current_thresholds()["signals"]["sig_client_neglected"]["value"]

        with patch.object(adjuster._calendar, "get_season", return_value="normal"):
            with patch.object(
                adjuster._calendar,
                "get_day_context",
                return_value=Mock(is_ramadan=False),
            ):
                result = adjuster.run_adjustment_cycle(feedback)

        # Verify effectiveness was computed
        assert len(result["effectiveness"]) == 1
        assert result["effectiveness"][0]["true_positive_rate"] == 0.0

        # Verify adjustment was applied
        assert result["applied_count"] > 0

        # Verify threshold changed
        new_val = adjuster.get_current_thresholds()["signals"]["sig_client_neglected"]["value"]
        assert new_val > original

        # Verify history recorded
        history = adjuster.get_history("sig_client_neglected")
        assert len(history) == 1
        assert len(history[0]["adjustments"]) > 0
