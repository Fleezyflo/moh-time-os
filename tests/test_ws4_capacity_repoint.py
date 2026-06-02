"""WS4 S4.4 — capacity page must read the live `events` table.

We build a tiny sqlite DB at a tmp path containing ONLY the live `events`
table (no legacy `calendar_events`). If the capacity page still queried
calendar_events, the OperationalError swallow would zero the metrics; with
the repoint it must read real focus/meeting hours.

The event times are computed relative to date.today() so they always fall
inside the THIS_WEEK horizon window (today 00:00 .. today+7d), regardless of
the calendar date the suite runs on. (A fixed 2026-06-01 literal would drop
out of the window on any later run day and produce a false-negative.)
"""

import sqlite3
from datetime import date, datetime, time

import pytest

from lib.agency_snapshot.capacity_command_page7 import CapacityCommandPage7Engine, Horizon

# A meeting (2h) and a focusTime block (3h), both anchored to today at a fixed
# wall-clock so they sit strictly inside [today 00:00, today+7d 23:59].
_TODAY = date.today()
_MEETING_START = datetime.combine(_TODAY, time(9, 0, 0)).isoformat()
_MEETING_END = datetime.combine(_TODAY, time(11, 0, 0)).isoformat()
_FOCUS_START = datetime.combine(_TODAY, time(13, 0, 0)).isoformat()
_FOCUS_END = datetime.combine(_TODAY, time(16, 0, 0)).isoformat()
_UPDATED_AT = datetime.combine(_TODAY, time(8, 0, 0)).isoformat()


def _make_events_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE events (
            id TEXT PRIMARY KEY, source TEXT, source_id TEXT, title TEXT,
            start_time TEXT, end_time TEXT, event_type TEXT,
            created_at TEXT, updated_at TEXT
        )
        """
    )
    # One meeting (2h) and one focusTime block (3h), both today.
    conn.executemany(
        "INSERT INTO events (id,title,start_time,end_time,event_type,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("e1", "Standup", _MEETING_START, _MEETING_END, "default", _UPDATED_AT),
            ("e2", "Deep work", _FOCUS_START, _FOCUS_END, "focusTime", _UPDATED_AT),
        ],
    )
    conn.commit()
    conn.close()


def test_capacity_does_not_query_calendar_events(tmp_path):
    """The repointed page must succeed with NO calendar_events table present."""
    db = tmp_path / "events_only.db"
    _make_events_db(db)

    page = CapacityCommandPage7Engine(db_path=str(db), horizon=Horizon.THIS_WEEK)
    meeting_hours, focus_hours, _largest, meeting_count, focus_count = page._load_calendar_events()

    assert meeting_count == 1
    assert focus_count == 1
    assert meeting_hours == pytest.approx(2.0)
    assert focus_hours == pytest.approx(3.0)


def test_capacity_calendar_last_sync_reads_events_updated_at(tmp_path):
    db = tmp_path / "events_only.db"
    _make_events_db(db)

    page = CapacityCommandPage7Engine(db_path=str(db), horizon=Horizon.THIS_WEEK)
    page._load_trust_state()
    assert page.calendar_last_sync_at == _UPDATED_AT


def _make_tz_aware_events_db(path):
    """Events with tz-AWARE timestamps (the live production shape) plus one naive
    all-day block — the mix that crashed the page once it read real `events`."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE events (
            id TEXT PRIMARY KEY, source TEXT, source_id TEXT, title TEXT,
            start_time TEXT, end_time TEXT, event_type TEXT,
            created_at TEXT, updated_at TEXT
        )
        """
    )
    # Tz-aware meeting (+04:00) and tz-aware focusTime block, plus a NAIVE all-day
    # block — comparing/subtracting these mixed kinds is what raised TypeError.
    aware_m_start = datetime.combine(_TODAY, time(9, 0, 0)).isoformat() + "+04:00"
    aware_m_end = datetime.combine(_TODAY, time(11, 0, 0)).isoformat() + "+04:00"
    aware_f_start = datetime.combine(_TODAY, time(13, 0, 0)).isoformat() + "+04:00"
    aware_f_end = datetime.combine(_TODAY, time(16, 0, 0)).isoformat() + "+04:00"
    naive_allday_start = datetime.combine(_TODAY, time(0, 0, 0)).isoformat()
    naive_allday_end = datetime.combine(_TODAY, time(1, 0, 0)).isoformat()
    aware_updated = datetime.combine(_TODAY, time(8, 0, 0)).isoformat() + "+04:00"
    conn.executemany(
        "INSERT INTO events (id,title,start_time,end_time,event_type,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("e1", "Standup", aware_m_start, aware_m_end, "default", aware_updated),
            ("e2", "Deep work", aware_f_start, aware_f_end, "focusTime", aware_updated),
            ("e3", "All day", naive_allday_start, naive_allday_end, "default", aware_updated),
        ],
    )
    conn.commit()
    conn.close()


def test_capacity_handles_tz_aware_and_naive_event_times(tmp_path):
    """Regression: live `events` timestamps are tz-aware (and all-day ones naive);
    _load_calendar_events / _compute_largest_contiguous_focus must NOT raise
    'can't compare/subtract offset-naive and offset-aware datetimes'."""
    db = tmp_path / "events_tz.db"
    _make_tz_aware_events_db(db)

    page = CapacityCommandPage7Engine(db_path=str(db), horizon=Horizon.THIS_WEEK)
    # Must not raise; _compute_largest_contiguous_focus runs inside this call.
    meeting_hours, focus_hours, largest, meeting_count, focus_count = page._load_calendar_events()
    assert focus_count == 1
    assert focus_hours == pytest.approx(3.0)
    assert meeting_count == 2  # the +04:00 standup + the naive all-day block
    assert largest >= 0.0  # focus-window computation completed without a tz crash


def test_capacity_reality_gap_confidence_not_forced_invalid_on_aware_sync(tmp_path):
    """Regression: a tz-aware calendar_last_sync_at must compute a real recency,
    not trip the aware/naive TypeError that forced reality_gap_confidence=invalid."""
    from datetime import timezone

    from lib.agency_snapshot.capacity_command_page7 import Confidence

    db = tmp_path / "events_tz2.db"
    _make_tz_aware_events_db(db)

    page = CapacityCommandPage7Engine(db_path=str(db), horizon=Horizon.THIS_WEEK)
    # Set the trust factors so confidence is gated only by the calendar-recency
    # branch we are testing; use a recent tz-aware sync timestamp.
    page.capacity_baseline = True
    page.tasks_lane_coverage_pct = 100.0
    page.duration_missing_pct = 0.0
    page.calendar_last_sync_at = datetime.now(timezone.utc).isoformat()  # aware, recent

    page._compute_reality_gap_confidence()  # must not raise

    # The swallowed-TypeError marker must be absent (it was present pre-fix), and a
    # recent aware sync must yield HIGH confidence, not the forced-LOW/MED path.
    assert "calendar sync time invalid" not in page._why_low
    assert page.reality_gap_confidence == Confidence.HIGH
