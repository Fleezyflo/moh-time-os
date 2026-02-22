"""
Integration tests for temporal intelligence layer.

Brief 31 (TC), Task TC-5.1

Tests end-to-end scenarios combining BusinessCalendar, TemporalNormalizer,
RecencyWeighter, and SignalLifecycleTracker.
"""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from lib.intelligence.signal_lifecycle import (
    SignalLifecycleTracker,
    SignalPersistence,
)
from lib.intelligence.temporal import (
    BusinessCalendar,
    RecencyWeighter,
    TemporalNormalizer,
)


def _create_test_db(tmp_path: Path) -> Path:
    """Create test database with signal_state + lifecycle columns."""
    db_path = tmp_path / "integration_test.db"
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
def cal():
    return BusinessCalendar()


@pytest.fixture
def normalizer(cal):
    return TemporalNormalizer(cal)


@pytest.fixture
def weighter(cal):
    return RecencyWeighter(cal, half_life_days=14)


class TestRamadanCommunicationDrop:
    """Scenario: Communication scores decline during Ramadan — expected behavior."""

    def test_ramadan_adjusts_response_expectations(self, normalizer):
        """During Ramadan, expected response time is longer."""
        # Sent during Ramadan on a Sunday
        sent = datetime(2026, 3, 1, 11, 0)  # Ramadan Sunday, 11 AM
        result = normalizer.expected_response_time(sent, response_hours=8.0)
        assert result["context_note"] != ""  # Should mention Ramadan

    def test_ramadan_working_minutes_reduced(self, cal):
        """Working minutes are 300 during Ramadan vs 600 normally."""
        ramadan_day = date(2026, 3, 1)
        normal_day = date(2026, 4, 15)
        assert cal.get_working_minutes(ramadan_day) == 300
        assert cal.get_working_minutes(normal_day) == 600

    def test_recency_weighted_trend_during_ramadan(self, weighter):
        """Declining scores during Ramadan visible in weighted trend."""
        ref = date(2026, 3, 15)  # During Ramadan
        cal = weighter.calendar
        points = []
        # Pre-Ramadan: high scores
        for i in range(5):
            d = cal.add_business_days(date(2026, 2, 10), i)
            points.append((d, 80.0))
        # During Ramadan: lower scores (expected)
        for i in range(5):
            d = cal.add_business_days(date(2026, 3, 1), i)
            points.append((d, 55.0))

        trend = weighter.weighted_trend(points, ref)
        # Recency-weighted mean should be closer to 55 (recent Ramadan scores)
        assert trend["weighted_mean"] < trend["unweighted_mean"]


class TestWeekendOverdueNotInflated:
    """Scenario: Task due Friday, checked Monday — not 3 calendar days late."""

    def test_due_friday_checked_monday(self, normalizer):
        """Business days late should be 1, not 3."""
        result = normalizer.business_days_late(
            due_date=date(2026, 2, 20),  # Friday
            current_date=date(2026, 2, 23),  # Monday (Sunday in UAE is working)
        )
        # Fri(due), Sat(skip), Sun(1 business day late)
        # Wait — in UAE, Sunday is a working day. Let me reconsider.
        # Fri=weekend(skip), Sat=weekend(skip), Sun=working(1 day late)
        # Actually: due Friday means it should have been done by Friday.
        # But Friday is weekend! So effectively due Thursday (last working day).
        # Fri-Sat are weekend, Sun is first working day after = 1 business day late.
        assert result == 1  # Not 3

    def test_calendar_days_would_be_more(self, normalizer):
        """Verify calendar days would inflate the number."""
        due = date(2026, 2, 20)  # Friday
        check = date(2026, 2, 23)  # Monday
        calendar_days = (check - due).days
        business_days = normalizer.business_days_late(due, check)
        assert calendar_days == 3
        assert business_days < calendar_days


class TestChronicSignalEscalation:
    """Scenario: Watch signal persists 15+ business days → auto-escalate to warning."""

    def test_chronic_watch_escalates(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        cal = BusinessCalendar()
        tracker = SignalLifecycleTracker(db_path=db_path, calendar=cal)

        # Seed a signal detected 16 business days ago
        old_date = cal.add_business_days(date.today(), -16)
        first_detected = datetime(old_date.year, old_date.month, old_date.day, 10, 0)

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            INSERT INTO signal_state (
                signal_key, signal_type, entity_type, entity_id,
                severity, detected_at, first_detected_at,
                detection_count, consecutive_cycles,
                initial_severity, peak_severity, escalation_history_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 16, 16, ?, ?, '[]')
            """,
            (
                "sig_overdue::client_x",
                "overdue_tasks",
                "client",
                "client_x",
                "watch",
                datetime.now().isoformat(),
                first_detected.isoformat(),
                "watch",
                "watch",
            ),
        )
        conn.commit()
        conn.close()

        # Auto-escalate
        escalations = tracker.auto_escalate_chronic_signals()
        assert len(escalations) == 1

        # Verify lifecycle updated
        lc = tracker.get_lifecycle("sig_overdue::client_x")
        assert lc.current_severity == "warning"
        assert lc.persistence == SignalPersistence.ESCALATING
        assert len(lc.escalation_history) >= 1


class TestRecencyWeightedTrendReversal:
    """Scenario: Good old scores, bad recent scores — weighted trend reveals decline."""

    def test_trend_reversal_detected(self, weighter):
        ref = date(2026, 4, 15)
        cal = weighter.calendar
        points = []

        # 20 days of old good scores
        for i in range(15):
            d = cal.add_business_days(ref, -(25 - i))
            points.append((d, 82.0 + (i % 3)))

        # 5 days of recent bad scores
        for i in range(5):
            d = cal.add_business_days(ref, -(4 - i))
            points.append((d, 52.0 - i))

        trend = weighter.weighted_trend(points, ref)

        # Unweighted would average around 73 (looks okay)
        # Weighted should be closer to recent bad scores
        assert trend["direction"] == "declining"
        assert trend["recency_delta"] < 0
        assert trend["weighted_mean"] < 70


class TestBusinessDaysConsistency:
    """Cross-module consistency: calendar and normalizer agree."""

    def test_business_days_agree(self, cal, normalizer):
        start = date(2026, 2, 16)  # Monday
        end = date(2026, 2, 23)  # Monday
        bd_cal = cal.business_days_between(start, end)
        bd_late = normalizer.business_days_late(start, end)
        assert bd_cal == bd_late

    def test_aging_matches_calendar(self, cal, normalizer):
        start = date(2026, 2, 16)
        end = date(2026, 3, 16)
        aging = normalizer.normalize_aging(start, end)
        bd_cal = cal.business_days_between(start, end)
        assert aging["business_days"] == bd_cal
