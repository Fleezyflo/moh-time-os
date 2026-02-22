"""
Tests for DriftDetector — metric drift detection.

Brief 28 (IO), Task IO-3.1
"""

import pytest

from lib.intelligence.drift_detection import (
    DriftAlert,
    DriftDetector,
    classify_drift_severity,
)


@pytest.fixture
def detector(tmp_path):
    db_path = tmp_path / "test_drift.db"
    return DriftDetector(db_path=db_path)


class TestClassifyDriftSeverity:
    def test_no_drift(self):
        assert classify_drift_severity(0.5) is None
        assert classify_drift_severity(1.0) is None

    def test_minor(self):
        assert classify_drift_severity(1.5) == "minor"
        assert classify_drift_severity(2.0) == "minor"

    def test_moderate(self):
        assert classify_drift_severity(2.5) == "moderate"
        assert classify_drift_severity(3.0) == "moderate"

    def test_major(self):
        assert classify_drift_severity(3.5) == "major"
        assert classify_drift_severity(5.0) == "major"

    def test_negative_sigma(self):
        assert classify_drift_severity(-2.0) == "minor"
        assert classify_drift_severity(-3.5) == "major"


class TestUpdateBaseline:
    def test_creates_baseline(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        # Should not raise; verify by checking drift
        alert = detector.check_drift("health_score", "client", "c1", 80)
        assert alert is None  # 80 is close to mean

    def test_too_few_values(self, detector):
        detector.update_baseline("health_score", "client", "c1", [80])
        # No baseline should be created
        alert = detector.check_drift("health_score", "client", "c1", 50)
        assert alert is None


class TestCheckDrift:
    def test_no_drift_within_normal(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        alert = detector.check_drift("health_score", "client", "c1", 80)
        assert alert is None

    def test_minor_drift_detected(self, detector):
        # Mean ~80, stddev ~2
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        # Value far from mean
        alert = detector.check_drift("health_score", "client", "c1", 74)
        assert alert is not None
        assert alert.severity in ("minor", "moderate", "major")
        assert alert.direction == "down"

    def test_major_drift_detected(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        # Extreme value
        alert = detector.check_drift("health_score", "client", "c1", 50)
        assert alert is not None
        assert alert.severity == "major"
        assert alert.direction == "down"

    def test_upward_drift(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        alert = detector.check_drift("health_score", "client", "c1", 95)
        assert alert is not None
        assert alert.direction == "up"

    def test_no_baseline_returns_none(self, detector):
        alert = detector.check_drift("health_score", "client", "c1", 50)
        assert alert is None

    def test_alert_has_explanation(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        alert = detector.check_drift("health_score", "client", "c1", 50)
        assert alert is not None
        assert "health_score" in alert.explanation
        assert "std devs" in alert.explanation


class TestRecentAlerts:
    def test_get_alerts(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        detector.check_drift("health_score", "client", "c1", 50)

        alerts = detector.get_recent_alerts()
        assert len(alerts) == 1

    def test_filter_by_severity(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        detector.check_drift("health_score", "client", "c1", 50)  # major

        alerts = detector.get_recent_alerts(severity="major")
        assert len(alerts) == 1
        alerts = detector.get_recent_alerts(severity="minor")
        assert len(alerts) == 0

    def test_empty_alerts(self, detector):
        alerts = detector.get_recent_alerts()
        assert alerts == []


class TestDriftSummary:
    def test_summary(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        detector.check_drift("health_score", "client", "c1", 50)

        summary = detector.get_drift_summary()
        assert summary["total_alerts"] == 1
        assert summary["baselines_tracked"] == 1
        assert "major" in summary["by_severity"]

    def test_summary_empty(self, detector):
        summary = detector.get_drift_summary()
        assert summary["total_alerts"] == 0
        assert summary["baselines_tracked"] == 0


class TestDriftAlertToDict:
    def test_to_dict(self, detector):
        values = [80, 82, 78, 81, 79, 83, 77, 80]
        detector.update_baseline("health_score", "client", "c1", values)
        alert = detector.check_drift("health_score", "client", "c1", 50)
        assert alert is not None
        d = alert.to_dict()
        assert "metric_name" in d
        assert "deviation_sigma" in d
        assert "severity" in d
