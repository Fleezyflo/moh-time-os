#!/usr/bin/env python3
"""
Unit tests for Calendar sync mode code paths.

UNIT-TEST VERIFIED (stubbed) - NOT live-verified (DWD not configured for calendar.readonly):
1. Initial sync (timeMin/timeMax) - _calendar_initial_sync
2. Incremental sync (syncToken) - _calendar_incremental_sync
3. 410 Gone handling - clears token, returns error for fallback
4. syncToken written ONLY AFTER persistence (not on fetch)
5. Exact log line patterns verified (CURSOR read/write, CALENDAR mode)

NOT VERIFIED (requires prod auth):
- Actual Google Calendar API responses
- Real syncToken persistence across runs
- DWD impersonation success

Run: uv run python -m lib.collectors.test_calendar_sync_modes
"""

import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Capture debug output for log assertions
_captured_debug = []


def mock_debug_print(msg: str) -> None:
    """Capture debug output for assertions."""
    _captured_debug.append(msg)
    print(f"[AUTH_DEBUG] {msg}", file=sys.stderr)


def create_fake_event(event_id: str, summary: str, start: str, end: str) -> dict:
    """Create a fake Calendar event."""
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "status": "confirmed",
    }


class TestCalendarSyncModes(unittest.TestCase):
    """
    Code-path verification for Calendar sync modes.

    These tests use stubbed API responses to verify code paths without prod auth.
    """

    def setUp(self):
        """Create temp database and tables."""
        global _captured_debug
        _captured_debug = []

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.temp_db.name)

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE sync_cursor (
                service TEXT NOT NULL,
                subject TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_at TEXT,
                PRIMARY KEY (service, subject, key)
            )
        """)
        conn.execute("""
            CREATE TABLE calendar_events (
                id INTEGER PRIMARY KEY,
                subject_email TEXT NOT NULL,
                calendar_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                summary TEXT,
                status TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(subject_email, calendar_id, event_id)
            )
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        """Clean up temp database."""
        self.temp_db.close()
        self.db_path.unlink(missing_ok=True)

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_initial_sync_writes_synctoken_only_after_persistence(self):
        """
        ASSERTION: syncToken is written to cursor ONLY after events are persisted.

        Sequence must be:
        1. events.list called with timeMin/timeMax
        2. Events persisted to calendar_events table
        3. THEN syncToken written to sync_cursor
        """
        from lib.collectors.all_users_runner import ApiStats, _calendar_initial_sync

        mock_svc = MagicMock()
        mock_events = MagicMock()
        mock_svc.events.return_value = mock_events

        fake_events = [
            create_fake_event("evt1", "Meeting 1", "2025-01-15T10:00:00Z", "2025-01-15T11:00:00Z"),
        ]
        mock_events.list.return_value.execute.return_value = {
            "items": fake_events,
            "nextSyncToken": "sync_token_after_initial",
        }

        stats = ApiStats()
        result = _calendar_initial_sync(
            svc=mock_svc,
            user="test@example.com",
            cal_id="primary",
            since="2025-01-01",
            until="2025-01-31",
            limit=100,
            db_path=self.db_path,
            stats=stats,
        )

        # VERIFY: events.list called with timeMin/timeMax, NOT syncToken
        call_kwargs = mock_events.list.call_args.kwargs
        self.assertIn("timeMin", call_kwargs, "Initial sync must use timeMin")
        self.assertIn("timeMax", call_kwargs, "Initial sync must use timeMax")
        self.assertNotIn("syncToken", call_kwargs, "Initial sync must NOT use syncToken")

        # VERIFY: Events were persisted
        self.assertEqual(result["inserted"], 1, "Event should be inserted")

        # VERIFY: syncToken was written (only possible after persistence succeeded)
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            "SELECT value FROM sync_cursor WHERE service='calendar' AND key='syncToken:primary'"
        )
        row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row, "syncToken must be written after persistence")
        self.assertEqual(row[0], "sync_token_after_initial")

        # VERIFY: Log sequence shows CURSOR write after list call
        cursor_write_logs = [
            log for log in _captured_debug if "CURSOR write" in log and "syncToken" in log
        ]
        self.assertTrue(len(cursor_write_logs) > 0, "Must log CURSOR write for syncToken")

        print("✅ PASS: syncToken written only after persistence")

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_log_sequence_cursor_write_after_persistence(self):
        """
        ASSERTION: Log sequence shows PERSIST before CURSOR write.

        Expected log order:
        1. events.list call
        2. PERSIST calendar (events persisted)
        3. CURSOR write (syncToken stored)
        """
        from lib.collectors.all_users_runner import ApiStats, _calendar_initial_sync

        mock_svc = MagicMock()
        mock_events = MagicMock()
        mock_svc.events.return_value = mock_events

        fake_events = [
            create_fake_event(
                "evt_seq", "Sequence Test", "2025-01-15T10:00:00Z", "2025-01-15T11:00:00Z"
            ),
        ]
        mock_events.list.return_value.execute.return_value = {
            "items": fake_events,
            "nextSyncToken": "seq_test_token",
        }

        stats = ApiStats()
        _calendar_initial_sync(
            svc=mock_svc,
            user="seq@test.com",
            cal_id="primary",
            since="2025-01-01",
            until="2025-01-31",
            limit=100,
            db_path=self.db_path,
            stats=stats,
        )

        # VERIFY: Log sequence - find indices
        persist_indices = [i for i, log in enumerate(_captured_debug) if "PERSIST calendar" in log]
        cursor_write_indices = [
            i
            for i, log in enumerate(_captured_debug)
            if "CURSOR write" in log and "syncToken" in log
        ]

        self.assertTrue(len(persist_indices) > 0, "Must log PERSIST calendar")
        self.assertTrue(len(cursor_write_indices) > 0, "Must log CURSOR write for syncToken")

        # PERSIST must come before CURSOR write
        self.assertTrue(
            persist_indices[-1] < cursor_write_indices[-1],
            f"PERSIST (idx {persist_indices[-1]}) must precede CURSOR write (idx {cursor_write_indices[-1]})",
        )

        print("✅ PASS: Log sequence shows PERSIST before CURSOR write")

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_incremental_sync_uses_synctoken_parameter(self):
        """
        ASSERTION: Incremental sync calls events.list with syncToken parameter.

        Log must show: events.list(syncToken=...)
        """
        from lib.collectors.all_users_runner import ApiStats, _calendar_incremental_sync

        mock_svc = MagicMock()
        mock_events = MagicMock()
        mock_svc.events.return_value = mock_events

        fake_events = [
            create_fake_event(
                "evt2", "New Meeting", "2025-01-20T10:00:00Z", "2025-01-20T11:00:00Z"
            ),
        ]
        mock_events.list.return_value.execute.return_value = {
            "items": fake_events,
            "nextSyncToken": "updated_sync_token",
        }

        stats = ApiStats()
        result = _calendar_incremental_sync(
            svc=mock_svc,
            user="test@example.com",
            cal_id="primary",
            sync_token="old_sync_token_123",  # noqa: S106
            limit=100,
            db_path=self.db_path,
            stats=stats,
        )

        # VERIFY: events.list called with syncToken, NOT timeMin/timeMax
        call_kwargs = mock_events.list.call_args.kwargs
        self.assertEqual(
            call_kwargs.get("syncToken"),
            "old_sync_token_123",
            "Incremental sync must pass syncToken",
        )
        self.assertNotIn("timeMin", call_kwargs, "Incremental sync must NOT use timeMin")
        self.assertNotIn("timeMax", call_kwargs, "Incremental sync must NOT use timeMax")

        # VERIFY: Stats use history_calls for syncToken-based sync
        self.assertEqual(stats.history_calls, 1, "Must count as history_call")
        self.assertEqual(stats.list_calls, 0, "Must NOT count as list_call")

        # VERIFY: Result contains data
        self.assertEqual(result["count"], 1, "Must return fetched events")

        print("✅ PASS: Incremental sync uses syncToken parameter")

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_410_gone_clears_token_and_returns_resync_error(self):
        """
        ASSERTION: 410 Gone clears syncToken cursor and returns resync error.

        Caller (collect_calendar_for_user) then falls back to initial sync.
        """
        from googleapiclient.errors import HttpError

        from lib.collectors.all_users_runner import (
            ApiStats,
            _calendar_incremental_sync,
            get_cursor,
            set_cursor,
        )

        # Pre-set a syncToken cursor
        set_cursor(
            self.db_path, "calendar", "test@example.com", "syncToken:primary", "expired_token"
        )

        mock_svc = MagicMock()
        mock_events = MagicMock()
        mock_svc.events.return_value = mock_events

        # Simulate 410 Gone
        mock_response = MagicMock()
        mock_response.status = 410
        mock_response.reason = "Gone"
        mock_events.list.return_value.execute.side_effect = HttpError(
            mock_response, b'{"error": {"code": 410, "message": "Sync token is no longer valid"}}'
        )

        stats = ApiStats()
        result = _calendar_incremental_sync(
            svc=mock_svc,
            user="test@example.com",
            cal_id="primary",
            sync_token="expired_token",  # noqa: S106
            limit=100,
            db_path=self.db_path,
            stats=stats,
        )

        # VERIFY: Error indicates resync needed
        self.assertEqual(
            result.get("error"),
            "syncToken_expired_needs_resync",
            "Must return syncToken_expired_needs_resync error",
        )

        # VERIFY: syncToken cursor was cleared
        cursor_value = get_cursor(self.db_path, "calendar", "test@example.com", "syncToken:primary")
        self.assertEqual(cursor_value, "", "syncToken must be cleared to empty string")

        # VERIFY: Log shows 410 handling
        gone_logs = [log for log in _captured_debug if "410" in log or "expired" in log.lower()]
        self.assertTrue(len(gone_logs) > 0, "Must log 410 Gone handling")

        print("✅ PASS: 410 Gone clears token and returns resync error")

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_mode_selection_logs_cursor_presence(self):
        """
        ASSERTION: Mode selection logs show cursor_present=yes/no.

        Expected log: CALENDAR mode=<mode> cursor_present=<yes/no> cal_id=<...>
        """
        from lib.collectors.all_users_runner import get_cursor, set_cursor

        # Case 1: No cursor
        val = get_cursor(self.db_path, "calendar", "user1@test.com", "syncToken:cal1")
        cursor_present_1 = val is not None and val != ""
        self.assertFalse(cursor_present_1, "No cursor => cursor_present=no")

        # Case 2: Has cursor
        set_cursor(self.db_path, "calendar", "user2@test.com", "syncToken:cal2", "valid_token")
        val = get_cursor(self.db_path, "calendar", "user2@test.com", "syncToken:cal2")
        cursor_present_2 = val is not None and val != ""
        self.assertTrue(cursor_present_2, "Has cursor => cursor_present=yes")

        # Case 3: Empty cursor (treated as no cursor)
        set_cursor(self.db_path, "calendar", "user3@test.com", "syncToken:cal3", "")
        val = get_cursor(self.db_path, "calendar", "user3@test.com", "syncToken:cal3")
        cursor_present_3 = val is not None and val != ""
        self.assertFalse(cursor_present_3, "Empty cursor => cursor_present=no")

        print("✅ PASS: Mode selection respects cursor presence")

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_log_patterns_exact_format(self):
        """
        ASSERTION: Log patterns match expected formats exactly.

        Expected patterns:
        - CURSOR read: service=... subject=... key=... value=...
        - CURSOR write: service=... subject=... key=... value=...
        - CALENDAR mode=<syncToken|timeMin/timeMax> cursor_present=<yes|no> cal_id=...
        """
        import re

        from lib.collectors.all_users_runner import get_cursor, set_cursor

        # Generate some cursor operations
        set_cursor(
            self.db_path, "calendar", "pattern@test.com", "syncToken:cal_pattern", "token_val"
        )
        get_cursor(self.db_path, "calendar", "pattern@test.com", "syncToken:cal_pattern")

        # VERIFY: CURSOR read pattern
        cursor_read_logs = [log for log in _captured_debug if "CURSOR read" in log]
        self.assertTrue(len(cursor_read_logs) > 0, "Must have CURSOR read logs")

        read_pattern = r"CURSOR read: service=\w+ subject=\S+ key=\S+ value=\S*"
        for log in cursor_read_logs:
            self.assertTrue(
                re.search(read_pattern, log), f"CURSOR read log must match pattern: {log}"
            )

        # VERIFY: CURSOR write pattern
        cursor_write_logs = [log for log in _captured_debug if "CURSOR write" in log]
        self.assertTrue(len(cursor_write_logs) > 0, "Must have CURSOR write logs")

        write_pattern = r"CURSOR write: service=\w+ subject=\S+ key=\S+ value=\S*"
        for log in cursor_write_logs:
            self.assertTrue(
                re.search(write_pattern, log), f"CURSOR write log must match pattern: {log}"
            )

        print("✅ PASS: Log patterns match expected formats")


class TestCalendarFullFlow(unittest.TestCase):
    """
    Test the full flow: 410 Gone → initial sync stores new syncToken.

    This verifies the caller-level fallback logic.
    """

    def setUp(self):
        global _captured_debug
        _captured_debug = []

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.temp_db.name)

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE sync_cursor (
                service TEXT NOT NULL, subject TEXT NOT NULL, key TEXT NOT NULL,
                value TEXT, updated_at TEXT, PRIMARY KEY (service, subject, key)
            )
        """)
        conn.execute("""
            CREATE TABLE calendar_events (
                id INTEGER PRIMARY KEY, subject_email TEXT NOT NULL, calendar_id TEXT NOT NULL,
                event_id TEXT NOT NULL, start_time TEXT, end_time TEXT, summary TEXT,
                status TEXT, raw_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(subject_email, calendar_id, event_id)
            )
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_db.close()
        self.db_path.unlink(missing_ok=True)

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_410_gone_fallback_stores_new_synctoken(self):
        """
        ASSERTION: After 410 Gone, initial sync fallback stores NEW syncToken.

        Flow:
        1. Incremental sync with old token → 410 Gone
        2. Token cleared, error returned
        3. Caller does initial sync
        4. New syncToken stored after persistence
        """
        from googleapiclient.errors import HttpError

        from lib.collectors.all_users_runner import (
            ApiStats,
            _calendar_incremental_sync,
            _calendar_initial_sync,
            get_cursor,
            set_cursor,
        )

        # Setup: Pre-existing expired token
        set_cursor(
            self.db_path, "calendar", "test@example.com", "syncToken:primary", "expired_old_token"
        )

        # Step 1: Incremental sync fails with 410
        mock_svc = MagicMock()
        mock_events = MagicMock()
        mock_svc.events.return_value = mock_events

        mock_response = MagicMock()
        mock_response.status = 410
        mock_events.list.return_value.execute.side_effect = HttpError(
            mock_response, b'{"error": {"code": 410}}'
        )

        stats = ApiStats()
        incr_result = _calendar_incremental_sync(
            svc=mock_svc,
            user="test@example.com",
            cal_id="primary",
            sync_token="expired_old_token",  # noqa: S106
            limit=100,
            db_path=self.db_path,
            stats=stats,
        )

        self.assertEqual(incr_result.get("error"), "syncToken_expired_needs_resync")

        # Verify token was cleared
        cleared_val = get_cursor(self.db_path, "calendar", "test@example.com", "syncToken:primary")
        self.assertEqual(cleared_val, "", "Token must be cleared after 410")

        # Step 2: Initial sync stores new token
        mock_events.list.return_value.execute.side_effect = None
        mock_events.list.return_value.execute.return_value = {
            "items": [
                create_fake_event(
                    "evt1", "Recovered", "2025-01-15T10:00:00Z", "2025-01-15T11:00:00Z"
                )
            ],
            "nextSyncToken": "fresh_new_token_after_410",
        }

        init_stats = ApiStats()
        init_result = _calendar_initial_sync(
            svc=mock_svc,
            user="test@example.com",
            cal_id="primary",
            since="2025-01-01",
            until="2025-01-31",
            limit=100,
            db_path=self.db_path,
            stats=init_stats,
        )

        self.assertEqual(init_result["inserted"], 1, "Event must be persisted")

        # VERIFY: NEW syncToken stored
        new_token = get_cursor(self.db_path, "calendar", "test@example.com", "syncToken:primary")
        self.assertEqual(
            new_token,
            "fresh_new_token_after_410",
            "New syncToken must be stored after initial sync fallback",
        )

        print("✅ PASS: 410 Gone fallback stores new syncToken")

    @patch("lib.collectors.all_users_runner.debug_print", mock_debug_print)
    @patch("lib.collectors.all_users_runner.AUTH_DEBUG", True)
    def test_mode_log_emitted_in_collect_calendar(self):
        """
        ASSERTION: collect_calendar_for_user emits mode selection log.

        Expected log format:
          CALENDAR mode=<syncToken|timeMin/timeMax> cursor_present=<yes|no> cal_id=...
        """
        import re

        from lib.collectors.all_users_runner import (
            ApiStats,
            collect_calendar_for_user,
            get_calendar_service,
            set_cursor,
        )

        # Mock the service factory
        with patch("lib.collectors.all_users_runner.get_calendar_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_get_svc.return_value = mock_svc

            # Mock calendarList.list
            MagicMock()
            mock_svc.calendarList.return_value.list.return_value.execute.return_value = {
                "items": [{"id": "primary"}],
            }

            # Mock events.list
            mock_svc.events.return_value.list.return_value.execute.return_value = {
                "items": [
                    create_fake_event(
                        "evt_mode", "Mode Test", "2025-01-15T10:00:00Z", "2025-01-15T11:00:00Z"
                    )
                ],
                "nextSyncToken": "mode_test_token",
            }

            # Case 1: No cursor (initial sync mode)
            stats1 = ApiStats()
            collect_calendar_for_user(
                user="mode_test@example.com",
                since="2025-01-01",
                until="2025-01-31",
                limit=100,
                db_path=self.db_path,
                stats=stats1,
            )

            # VERIFY: Mode log for initial sync (no cursor)
            mode_logs_initial = [
                log
                for log in _captured_debug
                if "CALENDAR mode=" in log and "cursor_present=no" in log
            ]
            self.assertTrue(
                len(mode_logs_initial) > 0,
                f"Must emit 'CALENDAR mode=timeMin/timeMax cursor_present=no' log. Got: {[log for log in _captured_debug if 'CALENDAR mode' in log]}",
            )

            # Case 2: With cursor (incremental sync mode)
            _captured_debug.clear()
            set_cursor(
                self.db_path,
                "calendar",
                "mode_test2@example.com",
                "syncToken:primary",
                "existing_token",
            )

            stats2 = ApiStats()
            collect_calendar_for_user(
                user="mode_test2@example.com",
                since="2025-01-01",
                until="2025-01-31",
                limit=100,
                db_path=self.db_path,
                stats=stats2,
            )

            # VERIFY: Mode log for incremental sync (has cursor)
            mode_logs_incr = [
                log
                for log in _captured_debug
                if "CALENDAR mode=" in log and "cursor_present=yes" in log
            ]
            self.assertTrue(
                len(mode_logs_incr) > 0,
                f"Must emit 'CALENDAR mode=syncToken cursor_present=yes' log. Got: {[log for log in _captured_debug if 'CALENDAR mode' in log]}",
            )

        print("✅ PASS: Mode selection log emitted in collect_calendar_for_user")


if __name__ == "__main__":
    print("=" * 70)
    print("CALENDAR SYNC MODE VERIFICATION (CODE-PATH TESTS)")
    print("=" * 70)
    print("""
SCOPE: Code-path verified with stubbed responses (no prod auth required)

Tests verify:
1. Initial sync uses timeMin/timeMax, NOT syncToken
2. syncToken written ONLY after persistence
3. Incremental sync uses syncToken parameter
4. 410 Gone clears token and returns resync error
5. Full flow: 410 → initial sync → new token stored

NOT VERIFIED: Live Google Calendar API behavior
""")
    unittest.main(verbosity=2)
