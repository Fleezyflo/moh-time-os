"""S3.4: collect_gmail_for_user / collect_calendar_for_user must not advance
the sync cursor when zero rows were fetched (the range was empty/glitched),
so the gap is re-fetched next sweep."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.collectors import all_users_runner

# db_path is never opened in these tests (set_cursor is patched out); a temp
# path keeps bandit/ruff happy (no hardcoded /tmp).
UNUSED_DB = Path(tempfile.gettempdir()) / "all_users_sweep_unused.db"


def _gmail_service(messages):
    """Build a fake Gmail service returning one page with `messages`."""
    svc = MagicMock()
    (svc.users.return_value.messages.return_value.list.return_value.execute.return_value) = {
        "messages": messages,
        "nextPageToken": None,
    }
    return svc


def _calendar_service(calendar_ids, events):
    """Build a fake Calendar service.

    calendarList().list().execute() -> {"items": [{"id": ...}, ...]} (one page).
    events().list().execute()       -> {"items": events} (one page) for every
    calendar. An empty calendar_ids list means the per-calendar loop never runs,
    so total_events stays 0 and no cursor write should happen at all.
    """
    svc = MagicMock()
    (svc.calendarList.return_value.list.return_value.execute.return_value) = {
        "items": [{"id": cid} for cid in calendar_ids],
        "nextPageToken": None,
    }
    (svc.events.return_value.list.return_value.execute.return_value) = {
        "items": events,
        "nextPageToken": None,
    }
    return svc


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_gmail_service")
def test_gmail_zero_rows_does_not_advance_cursor(mock_get_svc, _mock_get_cursor, mock_set_cursor):
    mock_get_svc.return_value = _gmail_service(messages=[])

    result = all_users_runner.collect_gmail_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 0
    mock_set_cursor.assert_not_called()


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_gmail_service")
def test_gmail_nonzero_rows_advances_cursor(mock_get_svc, _mock_get_cursor, mock_set_cursor):
    mock_get_svc.return_value = _gmail_service(messages=[{"id": "m1"}, {"id": "m2"}])

    result = all_users_runner.collect_gmail_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 2
    mock_set_cursor.assert_called_once()
    args = mock_set_cursor.call_args.args
    assert args[1] == "gmail" and args[3] == "last_until" and args[4] == "2026-05-02"


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_calendar_service")
def test_calendar_zero_events_does_not_advance_user_cursor(
    mock_get_svc, _mock_get_cursor, mock_set_cursor
):
    # No calendars at all -> per-calendar loop never runs, total_events == 0,
    # so the guarded user-level set_cursor must NOT fire.
    mock_get_svc.return_value = _calendar_service(calendar_ids=[], events=[])

    result = all_users_runner.collect_calendar_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 0
    mock_set_cursor.assert_not_called()


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_calendar_service")
def test_calendar_nonzero_events_advances_user_cursor(
    mock_get_svc, _mock_get_cursor, mock_set_cursor
):
    # One calendar that yields 2 events. The per-calendar write fires once; the
    # user-level write (now guarded by total_events > 0) fires once. So exactly
    # one user-level "last_until" write with the `until` value.
    mock_get_svc.return_value = _calendar_service(
        calendar_ids=["cal-A"], events=[{"id": "e1"}, {"id": "e2"}]
    )

    result = all_users_runner.collect_calendar_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 2
    user_level = [
        c
        for c in mock_set_cursor.call_args_list
        if c.args[1] == "calendar" and c.args[3] == "last_until"
    ]
    assert len(user_level) == 1
    assert user_level[0].args[4] == "2026-05-02"


def _chat_service(spaces, messages):
    """Fake Chat service: spaces().list() -> {"spaces": [...]}, and per-space
    spaces().messages().list() -> {"messages": [...]}."""
    svc = MagicMock()
    (svc.spaces.return_value.list.return_value.execute.return_value) = {
        "spaces": [{"name": s} for s in spaces],
        "nextPageToken": None,
    }
    (svc.spaces.return_value.messages.return_value.list.return_value.execute.return_value) = {
        "messages": messages,
        "nextPageToken": None,
    }
    return svc


def _drive_service(files):
    """Fake Drive service: files().list() -> {"files": [...]}."""
    svc = MagicMock()
    (svc.files.return_value.list.return_value.execute.return_value) = {
        "files": files,
        "nextPageToken": None,
    }
    return svc


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_chat_service")
def test_chat_zero_messages_does_not_advance_cursor(
    mock_get_svc, _mock_get_cursor, mock_set_cursor
):
    # No spaces -> the per-space message loop never runs, total_messages == 0.
    mock_get_svc.return_value = _chat_service(spaces=[], messages=[])

    result = all_users_runner.collect_chat_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 0
    mock_set_cursor.assert_not_called()


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_chat_service")
def test_chat_nonzero_messages_advances_cursor(mock_get_svc, _mock_get_cursor, mock_set_cursor):
    # One space with one in-window message -> total_messages > 0 -> cursor writes.
    mock_get_svc.return_value = _chat_service(
        spaces=["spaces/AAA"],
        messages=[{"name": "m1", "createTime": "2026-05-01T12:00:00Z"}],
    )

    result = all_users_runner.collect_chat_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 1
    chat_writes = [
        c
        for c in mock_set_cursor.call_args_list
        if c.args[1] == "chat" and c.args[3] == "last_until"
    ]
    assert len(chat_writes) == 1
    assert chat_writes[0].args[4] == "2026-05-02"


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_drive_service")
def test_drive_zero_files_does_not_advance_cursor(mock_get_svc, _mock_get_cursor, mock_set_cursor):
    mock_get_svc.return_value = _drive_service(files=[])

    result = all_users_runner.collect_drive_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 0
    mock_set_cursor.assert_not_called()


@patch.object(all_users_runner, "set_cursor")
@patch.object(all_users_runner, "get_cursor", return_value=None)
@patch.object(all_users_runner, "get_drive_service")
def test_drive_nonzero_files_advances_cursor(mock_get_svc, _mock_get_cursor, mock_set_cursor):
    mock_get_svc.return_value = _drive_service(
        files=[{"id": "f1", "name": "a.doc"}, {"id": "f2", "name": "b.doc"}]
    )

    result = all_users_runner.collect_drive_for_user(
        "user@example.com", "2026-05-01", "2026-05-02", 100, UNUSED_DB
    )

    assert result["count"] == 2
    drive_writes = [
        c
        for c in mock_set_cursor.call_args_list
        if c.args[1] == "drive" and c.args[3] == "last_until"
    ]
    assert len(drive_writes) == 1
    assert drive_writes[0].args[4] == "2026-05-02"
