"""
Tests for NotificationIntelligence — smart notification routing.

Brief 21 (NI), Task NI-1.1
"""

from datetime import datetime

import pytest

from lib.intelligence.notification_intelligence import (
    NotificationIntelligence,
    is_work_hours,
    select_channel,
)


@pytest.fixture
def ni():
    return NotificationIntelligence()


class TestIsWorkHours:
    def test_weekday_work_hours(self):
        # Monday 10 AM
        dt = datetime(2026, 2, 16, 10, 0)  # Monday
        assert is_work_hours(dt) is True

    def test_weekday_after_hours(self):
        dt = datetime(2026, 2, 16, 20, 0)  # Monday 8 PM
        assert is_work_hours(dt) is False

    def test_friday_is_weekend(self):
        dt = datetime(2026, 2, 20, 10, 0)  # Friday
        assert is_work_hours(dt) is False

    def test_saturday_is_weekend(self):
        dt = datetime(2026, 2, 21, 10, 0)  # Saturday
        assert is_work_hours(dt) is False


class TestSelectChannel:
    def test_critical_work_hours(self):
        assert select_channel("critical", True) == "push"

    def test_critical_after_hours(self):
        assert select_channel("critical", False) == "sms"

    def test_high_work_hours(self):
        assert select_channel("high", True) == "email_urgent"

    def test_normal_after_hours(self):
        assert select_channel("normal", False) == "digest"

    def test_low(self):
        assert select_channel("low", True) == "digest"


class TestDecide:
    def test_critical_sends_immediately(self, ni):
        work_time = datetime(2026, 2, 16, 10, 0)  # Monday 10 AM
        d = ni.decide("client", "c1", "sig_1", "critical", current_time=work_time)
        assert d.should_send_now is True
        assert d.channel == "push"

    def test_suppressed_signal(self, ni):
        d = ni.decide("client", "c1", "sig_1", "high", is_suppressed=True)
        assert d.should_send_now is False
        assert d.channel == "silent"
        assert d.suppress_reason is not None

    def test_batches_after_hours(self, ni):
        after_hours = datetime(2026, 2, 16, 22, 0)  # Monday 10 PM
        d = ni.decide("client", "c1", "sig_1", "normal", current_time=after_hours)
        assert d.should_send_now is False
        assert d.batch_with == "morning_digest"

    def test_to_dict(self, ni):
        d = ni.decide("client", "c1", "sig_1", "normal")
        result = d.to_dict()
        assert "channel" in result
        assert "urgency" in result


class TestFatigue:
    def test_fatigue_after_burst(self, ni):
        work_time = datetime(2026, 2, 16, 10, 0)
        # Send 5 notifications quickly
        for i in range(5):
            ni.decide("client", f"c{i}", f"sig_{i}", "high", current_time=work_time)

        # 6th should be deferred
        d = ni.decide("client", "c5", "sig_5", "normal", current_time=work_time)
        assert d.should_send_now is False
        assert "fatigue" in d.reason

    def test_critical_bypasses_fatigue(self, ni):
        work_time = datetime(2026, 2, 16, 10, 0)
        for i in range(6):
            ni.decide("client", f"c{i}", f"sig_{i}", "high", current_time=work_time)

        d = ni.decide("client", "c6", "sig_6", "critical", current_time=work_time)
        assert d.should_send_now is True

    def test_fatigue_state(self, ni):
        state = ni.get_fatigue_state()
        assert state.notifications_last_hour == 0
        assert state.is_fatigued is False


class TestBatching:
    def test_batch_deferred(self, ni):
        decisions = [
            ni.decide(
                "client",
                "c1",
                "sig_1",
                "normal",
                is_suppressed=False,
                current_time=datetime(2026, 2, 16, 22, 0),
            ),
            ni.decide(
                "client",
                "c2",
                "sig_2",
                "low",
                is_suppressed=False,
                current_time=datetime(2026, 2, 16, 22, 0),
            ),
        ]
        batches = ni.batch_notifications(decisions)
        assert len(batches) == 1
        assert batches[0].batch_key == "morning_digest"
        assert len(batches[0].notifications) == 2
