"""
Tests for SignalLifecycleTracker — signal persistence and escalation.

Brief 31 (TC), Task TC-4.1 + TC-5.1
"""

import json
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from lib.intelligence.signal_lifecycle import (
    SignalLifecycleTracker,
    SignalPersistence,
)
from lib.intelligence.temporal import BusinessCalendar


def _create_test_db(tmp_path: Path) -> Path:
    """Create a test database with signal_state table + lifecycle columns."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE signal_state (
            signal_key TEXT PRIMARY KEY,
            signal_type TEXT,
            entity_type TEXT,
            entity_id TEXT,
            severity TEXT,
            detected_at TEXT,
            value REAL,
            threshold REAL,
            evidence_json TEXT,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_at TEXT,
            first_detected_at TEXT,
            detection_count INTEGER DEFAULT 1,
            consecutive_cycles INTEGER DEFAULT 1,
            initial_severity TEXT,
            peak_severity TEXT,
            escalation_history_json TEXT DEFAULT '[]',
            resolved_at TEXT,
            resolution_type TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def tracker(tmp_path):
    db_path = _create_test_db(tmp_path)
    cal = BusinessCalendar()
    return SignalLifecycleTracker(db_path=db_path, calendar=cal)


class TestFirstDetection:
    """New signal detection creates lifecycle."""

    def test_first_detection_returns_lifecycle(self, tracker):
        lc = tracker.update_lifecycle_on_detection(
            signal_key="sig_test::client_1",
            current_severity="watch",
            signal_type="overdue_tasks",
            entity_type="client",
            entity_id="client_1",
        )
        assert lc is not None
        assert lc.signal_key == "sig_test::client_1"
        assert lc.detection_count == 1
        assert lc.persistence == SignalPersistence.NEW

    def test_first_detection_sets_initial_severity(self, tracker):
        lc = tracker.update_lifecycle_on_detection(
            signal_key="sig_test::client_2",
            current_severity="warning",
            signal_type="comm_drop",
            entity_type="client",
            entity_id="client_2",
        )
        assert lc.initial_severity == "warning"
        assert lc.current_severity == "warning"
        assert lc.peak_severity == "warning"


class TestSubsequentDetections:
    """Repeated detections update lifecycle."""

    def test_second_detection_increments_count(self, tracker):
        tracker.update_lifecycle_on_detection(
            signal_key="sig_test",
            current_severity="watch",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        lc = tracker.update_lifecycle_on_detection(
            signal_key="sig_test",
            current_severity="watch",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        assert lc.detection_count == 2
        assert lc.consecutive_cycles == 2

    def test_severity_change_recorded(self, tracker):
        tracker.update_lifecycle_on_detection(
            signal_key="sig_esc",
            current_severity="watch",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        lc = tracker.update_lifecycle_on_detection(
            signal_key="sig_esc",
            current_severity="warning",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        assert lc.current_severity == "warning"
        assert lc.peak_severity == "warning"
        assert len(lc.escalation_history) == 1
        assert lc.escalation_history[0]["old_severity"] == "watch"
        assert lc.escalation_history[0]["new_severity"] == "warning"


class TestPersistenceClassification:
    """Signal persistence levels."""

    def test_new_signal(self, tracker):
        tracker.update_lifecycle_on_detection(
            signal_key="sig_new",
            current_severity="watch",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        assert tracker.classify_persistence("sig_new") == SignalPersistence.NEW

    def test_recent_signal(self, tracker, tmp_path):
        """Signal detected 2 business days ago."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cal = BusinessCalendar()
        two_bd_ago = cal.add_business_days(date.today(), -2)
        first_detected = datetime(two_bd_ago.year, two_bd_ago.month, two_bd_ago.day, 10, 0)
        conn.execute(
            """
            INSERT INTO signal_state (
                signal_key, signal_type, entity_type, entity_id,
                severity, detected_at, first_detected_at,
                detection_count, consecutive_cycles,
                initial_severity, peak_severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 3, 3, ?, ?)
            """,
            (
                "sig_recent",
                "test",
                "client",
                "c1",
                "watch",
                datetime.now().isoformat(),
                first_detected.isoformat(),
                "watch",
                "watch",
            ),
        )
        conn.commit()
        conn.close()
        t = SignalLifecycleTracker(db_path=db_path, calendar=cal)
        assert t.classify_persistence("sig_recent") == SignalPersistence.RECENT

    def test_chronic_signal(self, tracker, tmp_path):
        """Signal detected 15 business days ago."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cal = BusinessCalendar()
        old_date = cal.add_business_days(date.today(), -15)
        first_detected = datetime(old_date.year, old_date.month, old_date.day, 10, 0)
        conn.execute(
            """
            INSERT INTO signal_state (
                signal_key, signal_type, entity_type, entity_id,
                severity, detected_at, first_detected_at,
                detection_count, consecutive_cycles,
                initial_severity, peak_severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 10, 10, ?, ?)
            """,
            (
                "sig_chronic",
                "test",
                "client",
                "c1",
                "watch",
                datetime.now().isoformat(),
                first_detected.isoformat(),
                "watch",
                "watch",
            ),
        )
        conn.commit()
        conn.close()
        t = SignalLifecycleTracker(db_path=db_path, calendar=cal)
        assert t.classify_persistence("sig_chronic") == SignalPersistence.CHRONIC

    def test_escalating_overrides_age(self, tracker, tmp_path):
        """Severity increase takes priority over age classification."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cal = BusinessCalendar()
        old_date = cal.add_business_days(date.today(), -5)
        first_detected = datetime(old_date.year, old_date.month, old_date.day, 10, 0)
        conn.execute(
            """
            INSERT INTO signal_state (
                signal_key, signal_type, entity_type, entity_id,
                severity, detected_at, first_detected_at,
                detection_count, consecutive_cycles,
                initial_severity, peak_severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 5, 5, ?, ?)
            """,
            (
                "sig_esc",
                "test",
                "client",
                "c1",
                "warning",
                datetime.now().isoformat(),
                first_detected.isoformat(),
                "watch",
                "warning",  # initial=watch, current=warning → escalating
            ),
        )
        conn.commit()
        conn.close()
        t = SignalLifecycleTracker(db_path=db_path, calendar=cal)
        assert t.classify_persistence("sig_esc") == SignalPersistence.ESCALATING

    def test_nonexistent_signal(self, tracker):
        assert tracker.classify_persistence("nonexistent") is None


class TestSignalClearing:
    """Signal resolution."""

    def test_clear_marks_resolved(self, tracker):
        tracker.update_lifecycle_on_detection(
            signal_key="sig_clear",
            current_severity="watch",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        tracker.update_lifecycle_on_clear("sig_clear", "resolved")
        lc = tracker.get_lifecycle("sig_clear")
        assert lc is not None
        assert lc.resolved_at is not None
        assert lc.resolution_type == "resolved"

    def test_clear_does_not_delete(self, tracker):
        tracker.update_lifecycle_on_detection(
            signal_key="sig_keep",
            current_severity="watch",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        tracker.update_lifecycle_on_clear("sig_keep", "resolved")
        lc = tracker.get_lifecycle("sig_keep")
        assert lc is not None  # Still exists


class TestAutoEscalation:
    """Chronic watch signals auto-escalate to warning."""

    def test_chronic_watch_auto_escalates(self, tracker, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cal = BusinessCalendar()
        old_date = cal.add_business_days(date.today(), -16)
        first_detected = datetime(old_date.year, old_date.month, old_date.day, 10, 0)
        conn.execute(
            """
            INSERT INTO signal_state (
                signal_key, signal_type, entity_type, entity_id,
                severity, detected_at, first_detected_at,
                detection_count, consecutive_cycles,
                initial_severity, peak_severity, escalation_history_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 12, 12, ?, ?, '[]')
            """,
            (
                "sig_chronic_watch",
                "overdue_tasks",
                "client",
                "c1",
                "watch",
                datetime.now().isoformat(),
                first_detected.isoformat(),
                "watch",
                "watch",
            ),
        )
        conn.commit()
        conn.close()

        t = SignalLifecycleTracker(db_path=db_path, calendar=cal)
        escalations = t.auto_escalate_chronic_signals()
        assert len(escalations) == 1
        assert escalations[0]["old_severity"] == "watch"
        assert escalations[0]["new_severity"] == "warning"

        # Verify the update
        lc = t.get_lifecycle("sig_chronic_watch")
        assert lc.current_severity == "warning"


class TestAgeDistribution:
    """Signal age distribution analytics."""

    def test_distribution_counts(self, tracker):
        tracker.update_lifecycle_on_detection(
            signal_key="sig_a",
            current_severity="watch",
            signal_type="test",
            entity_type="client",
            entity_id="c1",
        )
        tracker.update_lifecycle_on_detection(
            signal_key="sig_b",
            current_severity="warning",
            signal_type="test",
            entity_type="client",
            entity_id="c2",
        )
        dist = tracker.get_signal_age_distribution()
        assert dist["total_active"] == 2
        assert dist["new"] == 2  # Both just created
