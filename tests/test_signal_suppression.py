"""
Tests for SignalSuppression — dismiss tracking and suppression windows.

Brief 22 (SM), Task SM-3.1
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib.intelligence.signal_suppression import (
    AUTO_DEPRIORITIZE_DISMISS_RATE,
    DEFAULT_SUPPRESS_DAYS,
    REPEAT_DISMISS_SUPPRESS_DAYS,
    REPEAT_DISMISS_THRESHOLD,
    SignalSuppression,
    SuppressionRecord,
)


@pytest.fixture
def suppression(tmp_path):
    db_path = tmp_path / "test_suppress.db"
    return SignalSuppression(db_path=db_path)


class TestDismissSignal:
    def test_first_dismiss(self, suppression):
        record = suppression.dismiss_signal(
            signal_key="sig_overdue::client_a",
            entity_type="client",
            entity_id="client_a",
            reason="user_dismiss",
        )
        assert record.signal_key == "sig_overdue::client_a"
        assert record.dismiss_count == 1
        assert record.is_active is True
        assert record.reason == "user_dismiss"

    def test_default_window_7_days(self, suppression):
        record = suppression.dismiss_signal("sig_test::c1", "client", "c1")
        suppressed_dt = datetime.fromisoformat(record.suppressed_at)
        expires_dt = datetime.fromisoformat(record.expires_at)
        diff = (expires_dt - suppressed_dt).days
        assert diff == DEFAULT_SUPPRESS_DAYS

    def test_repeat_dismiss_extends_window(self, suppression):
        # Dismiss REPEAT_DISMISS_THRESHOLD times
        for _i in range(REPEAT_DISMISS_THRESHOLD):
            record = suppression.dismiss_signal("sig_test::c1", "client", "c1")

        suppressed_dt = datetime.fromisoformat(record.suppressed_at)
        expires_dt = datetime.fromisoformat(record.expires_at)
        diff = (expires_dt - suppressed_dt).days
        assert diff == REPEAT_DISMISS_SUPPRESS_DAYS

    def test_dismiss_count_increments(self, suppression):
        r1 = suppression.dismiss_signal("sig_test::c1", "client", "c1")
        assert r1.dismiss_count == 1
        r2 = suppression.dismiss_signal("sig_test::c1", "client", "c1")
        assert r2.dismiss_count == 2
        r3 = suppression.dismiss_signal("sig_test::c1", "client", "c1")
        assert r3.dismiss_count == 3


class TestIsSuppressed:
    def test_suppressed_after_dismiss(self, suppression):
        suppression.dismiss_signal("sig_test::c1", "client", "c1")
        assert suppression.is_suppressed("sig_test::c1") is True

    def test_not_suppressed_unknown(self, suppression):
        assert suppression.is_suppressed("sig_unknown") is False

    def test_expired_not_suppressed(self, suppression):
        suppression.dismiss_signal("sig_test::c1", "client", "c1")
        # Manually expire the suppression
        conn = sqlite3.connect(str(suppression.db_path))
        past = (datetime.now() - timedelta(days=1)).isoformat()
        conn.execute(
            "UPDATE signal_suppressions SET expires_at = ?",
            (past,),
        )
        conn.commit()
        conn.close()
        assert suppression.is_suppressed("sig_test::c1") is False


class TestRecordSignalRaised:
    def test_records_raised_event(self, suppression):
        suppression.record_signal_raised("sig_test::c1", "client", "c1")
        stats = suppression.get_dismiss_stats("sig_test::c1")
        assert stats.total_raised == 1
        assert stats.total_dismissed == 0


class TestDismissStats:
    def test_empty_stats(self, suppression):
        stats = suppression.get_dismiss_stats("sig_nonexistent")
        assert stats.total_raised == 0
        assert stats.total_dismissed == 0
        assert stats.dismiss_rate == 0.0
        assert stats.is_auto_deprioritized is False

    def test_stats_after_activity(self, suppression):
        suppression.record_signal_raised("sig_test::c1", "client", "c1")
        suppression.record_signal_raised("sig_test::c1", "client", "c1")
        suppression.dismiss_signal("sig_test::c1", "client", "c1")

        stats = suppression.get_dismiss_stats("sig_test::c1")
        assert stats.total_raised == 2
        assert stats.total_dismissed == 1
        # dismiss_rate = 1/(2+1) = 0.333
        assert stats.dismiss_rate == pytest.approx(1 / 3, abs=0.01)
        assert stats.is_auto_deprioritized is False

    def test_high_dismiss_rate_deprioritized(self, suppression):
        # Raise once, dismiss many times → high dismiss rate
        suppression.record_signal_raised("sig_test::c1", "client", "c1")
        for _ in range(REPEAT_DISMISS_THRESHOLD):
            suppression.dismiss_signal("sig_test::c1", "client", "c1")

        stats = suppression.get_dismiss_stats("sig_test::c1")
        # 3 dismissed, 1 raised → rate = 3/4 = 0.75 >= 0.70
        assert stats.dismiss_rate >= AUTO_DEPRIORITIZE_DISMISS_RATE
        assert stats.is_auto_deprioritized is True


class TestShouldDeprioritize:
    def test_not_deprioritized_initially(self, suppression):
        assert suppression.should_deprioritize("sig_test::c1") is False

    def test_deprioritized_after_many_dismissals(self, suppression):
        suppression.record_signal_raised("sig_test::c1", "client", "c1")
        for _ in range(REPEAT_DISMISS_THRESHOLD):
            suppression.dismiss_signal("sig_test::c1", "client", "c1")
        assert suppression.should_deprioritize("sig_test::c1") is True


class TestExpireSuppressions:
    def test_expire_old_suppressions(self, suppression):
        suppression.dismiss_signal("sig_test::c1", "client", "c1")
        # Manually backdate expiry
        conn = sqlite3.connect(str(suppression.db_path))
        past = (datetime.now() - timedelta(days=1)).isoformat()
        conn.execute("UPDATE signal_suppressions SET expires_at = ?", (past,))
        conn.commit()
        conn.close()

        expired_count = suppression.expire_suppressions()
        assert expired_count == 1
        assert suppression.is_suppressed("sig_test::c1") is False

    def test_no_expire_when_fresh(self, suppression):
        suppression.dismiss_signal("sig_test::c1", "client", "c1")
        expired_count = suppression.expire_suppressions()
        assert expired_count == 0
        assert suppression.is_suppressed("sig_test::c1") is True


class TestActiveSuppressions:
    def test_get_active(self, suppression):
        suppression.dismiss_signal("sig_1::c1", "client", "c1")
        suppression.dismiss_signal("sig_2::c2", "client", "c2")

        active = suppression.get_active_suppressions()
        assert len(active) == 2

    def test_filter_by_entity(self, suppression):
        suppression.dismiss_signal("sig_1::c1", "client", "c1")
        suppression.dismiss_signal("sig_2::c2", "client", "c2")

        active = suppression.get_active_suppressions(entity_type="client", entity_id="c1")
        assert len(active) == 1
        assert active[0].signal_key == "sig_1::c1"


class TestSuppressionSummary:
    def test_summary(self, suppression):
        suppression.dismiss_signal("sig_1::c1", "client", "c1")
        suppression.dismiss_signal("sig_2::c2", "client", "c2", reason="duplicate")

        summary = suppression.get_suppression_summary()
        assert summary["active_suppressions"] == 2
        assert "user_dismiss" in summary["by_reason"]
        assert "duplicate" in summary["by_reason"]

    def test_summary_empty(self, suppression):
        summary = suppression.get_suppression_summary()
        assert summary["active_suppressions"] == 0


class TestSuppressionRecordToDict:
    def test_to_dict(self, suppression):
        record = suppression.dismiss_signal("sig_test::c1", "client", "c1")
        d = record.to_dict()
        assert d["signal_key"] == "sig_test::c1"
        assert d["is_active"] is True
        assert "expires_at" in d
