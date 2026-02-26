"""
Tests for Calendar write-back integration.

Tests CalendarWriter without calling real Calendar API.
All Google API calls are mocked using unittest.mock.
"""

from unittest.mock import MagicMock, patch

from lib.integrations.calendar_writer import CalendarWriter, CalendarWriteResult

# ============================================================
# CalendarWriter Initialization Tests
# ============================================================


class TestCalendarWriterInit:
    """Test CalendarWriter initialization."""

    def test_init_with_default_params(self):
        """Can initialize with default parameters."""
        writer = CalendarWriter()
        assert writer.delegated_user == "molham@hrmny.co"
        assert writer.dry_run is False
        assert writer._service is None

    def test_init_with_custom_user(self):
        """Can initialize with custom delegated user."""
        writer = CalendarWriter(delegated_user="custom@example.com")
        assert writer.delegated_user == "custom@example.com"

    def test_init_with_env_var_user(self, monkeypatch):
        """Can initialize with CALENDAR_USER env var."""
        monkeypatch.setenv("CALENDAR_USER", "env_user@example.com")
        writer = CalendarWriter()
        assert writer.delegated_user == "env_user@example.com"

    def test_init_dry_run_mode(self):
        """Can enable dry-run mode."""
        writer = CalendarWriter(dry_run=True)
        assert writer.dry_run is True

    def test_init_with_custom_credentials_path(self, tmp_path):
        """Can initialize with custom credentials path."""
        creds_file = tmp_path / "sa.json"
        creds_file.write_text('{"type": "service_account"}')
        writer = CalendarWriter(credentials_path=str(creds_file))
        assert writer.credentials_path == str(creds_file)


# ============================================================
# CalendarWriter Event Creation Tests
# ============================================================


class TestCalendarWriterCreateEvent:
    """Test event creation."""

    def test_create_event_minimal_dry_run(self):
        """Can create minimal event in dry-run mode."""
        writer = CalendarWriter(dry_run=True)
        result = writer.create_event(
            calendar_id="primary",
            summary="Team Meeting",
            start="2026-02-21T10:00:00",
            end="2026-02-21T11:00:00",
        )

        assert result.success
        assert result.event_id == "event_dry_run"
        assert result.data["dry_run"] is True
        assert result.data["summary"] == "Team Meeting"

    def test_create_event_with_all_fields_dry_run(self):
        """Can create event with all optional fields in dry-run."""
        writer = CalendarWriter(dry_run=True)
        result = writer.create_event(
            calendar_id="primary",
            summary="Full Meeting",
            start="2026-02-21T14:00:00",
            end="2026-02-21T15:00:00",
            description="Team sync",
            attendees=["alice@example.com", "bob@example.com"],
            location="Conf Room A",
            reminders={"useDefault": True},
        )

        assert result.success
        assert result.data["summary"] == "Full Meeting"

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_create_event_via_api(self, mock_get_service):
        """Can create event via API."""
        mock_service = MagicMock()
        mock_response = {
            "id": "event_123",
            "summary": "Team Meeting",
            "htmlLink": "https://calendar.google.com/...",
        }
        mock_service.events().insert.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.create_event(
            calendar_id="primary",
            summary="Team Meeting",
            start="2026-02-21T10:00:00",
            end="2026-02-21T11:00:00",
        )

        assert result.success
        assert result.event_id == "event_123"
        assert result.link == "https://calendar.google.com/..."
        mock_service.events().insert.assert_called_once()

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_create_event_with_attendees(self, mock_get_service):
        """Can create event with attendees."""
        mock_service = MagicMock()
        mock_response = {"id": "event_456"}
        mock_service.events().insert.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.create_event(
            calendar_id="primary",
            summary="Team Meeting",
            start="2026-02-21T10:00:00",
            end="2026-02-21T11:00:00",
            attendees=["alice@example.com", "bob@example.com"],
        )

        assert result.success
        # Verify attendees were included in call
        call_args = mock_service.events().insert.call_args
        assert "attendees" in call_args.kwargs["body"]

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_create_event_api_error(self, mock_get_service):
        """Handles API errors correctly."""
        mock_service = MagicMock()
        mock_service.events().insert.return_value.execute.side_effect = Exception("403 Forbidden")
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.create_event(
            calendar_id="primary",
            summary="Meeting",
            start="2026-02-21T10:00:00",
            end="2026-02-21T11:00:00",
        )

        assert not result.success
        assert "403" in result.error


# ============================================================
# CalendarWriter Event Update Tests
# ============================================================


class TestCalendarWriterUpdateEvent:
    """Test event updates."""

    def test_update_event_dry_run(self):
        """Can update event in dry-run mode."""
        writer = CalendarWriter(dry_run=True)
        result = writer.update_event(
            calendar_id="primary",
            event_id="event_123",
            updates={"summary": "New Title"},
        )

        assert result.success
        assert result.event_id == "event_123"
        assert result.data["dry_run"] is True

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_update_event_via_api(self, mock_get_service):
        """Can update event via API."""
        mock_service = MagicMock()

        # Mock get to fetch existing event
        existing_event = {
            "id": "event_123",
            "summary": "Old Title",
            "start": {"dateTime": "2026-02-21T10:00:00"},
            "end": {"dateTime": "2026-02-21T11:00:00"},
        }
        mock_service.events().get.return_value.execute.return_value = existing_event

        # Mock update
        updated_event = existing_event.copy()
        updated_event["summary"] = "New Title"
        mock_service.events().update.return_value.execute.return_value = updated_event
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.update_event(
            calendar_id="primary",
            event_id="event_123",
            updates={"summary": "New Title"},
        )

        assert result.success
        assert result.event_id == "event_123"
        mock_service.events().get.assert_called_once()
        mock_service.events().update.assert_called_once()

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_update_event_time(self, mock_get_service):
        """Can update event time."""
        mock_service = MagicMock()

        existing = {
            "id": "event_123",
            "summary": "Meeting",
            "start": {"dateTime": "2026-02-21T10:00:00"},
            "end": {"dateTime": "2026-02-21T11:00:00"},
        }
        mock_service.events().get.return_value.execute.return_value = existing

        updated = existing.copy()
        updated["start"] = {"dateTime": "2026-02-21T14:00:00"}
        updated["end"] = {"dateTime": "2026-02-21T15:00:00"}
        mock_service.events().update.return_value.execute.return_value = updated

        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.update_event(
            calendar_id="primary",
            event_id="event_123",
            updates={
                "start": "2026-02-21T14:00:00",
                "end": "2026-02-21T15:00:00",
            },
        )

        assert result.success


# ============================================================
# CalendarWriter Event Deletion Tests
# ============================================================


class TestCalendarWriterDeleteEvent:
    """Test event deletion."""

    def test_delete_event_dry_run(self):
        """Can delete event in dry-run mode."""
        writer = CalendarWriter(dry_run=True)
        result = writer.delete_event("primary", "event_123")

        assert result.success
        assert result.event_id == "event_123"

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_delete_event_via_api(self, mock_get_service):
        """Can delete event via API."""
        mock_service = MagicMock()
        mock_service.events().delete.return_value.execute.return_value = None
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.delete_event("primary", "event_123")

        assert result.success
        assert result.event_id == "event_123"
        assert result.data["deleted"] is True
        mock_service.events().delete.assert_called_once()

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_delete_event_not_found(self, mock_get_service):
        """Handles event not found error."""
        mock_service = MagicMock()
        mock_service.events().delete.return_value.execute.side_effect = Exception("404 Not Found")
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.delete_event("primary", "invalid_event")

        assert not result.success
        assert "404" in result.error


# ============================================================
# CalendarWriter Quick Add Tests
# ============================================================


class TestCalendarWriterQuickAdd:
    """Test quick add (natural language) event creation."""

    def test_quick_add_dry_run(self):
        """Can quick add event in dry-run mode."""
        writer = CalendarWriter(dry_run=True)
        result = writer.create_quick_event(
            calendar_id="primary",
            text="Team meeting tomorrow at 3pm",
        )

        assert result.success
        assert result.event_id == "event_dry_run"

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_quick_add_via_api(self, mock_get_service):
        """Can quick add via API."""
        mock_service = MagicMock()
        mock_response = {
            "id": "event_789",
            "summary": "Team meeting tomorrow at 3pm",
            "htmlLink": "https://calendar.google.com/...",
        }
        mock_service.events().quickAdd.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.create_quick_event(
            calendar_id="primary",
            text="Team meeting tomorrow at 3pm",
        )

        assert result.success
        assert result.event_id == "event_789"
        mock_service.events().quickAdd.assert_called_once()


# ============================================================
# CalendarWriter Move Event Tests
# ============================================================


class TestCalendarWriterMoveEvent:
    """Test moving events between calendars."""

    def test_move_event_dry_run(self):
        """Can move event in dry-run mode."""
        writer = CalendarWriter(dry_run=True)
        result = writer.move_event(
            calendar_id="primary",
            event_id="event_123",
            destination_calendar_id="secondary@example.com",
        )

        assert result.success
        assert result.event_id == "event_123"

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_move_event_via_api(self, mock_get_service):
        """Can move event via API."""
        mock_service = MagicMock()
        mock_response = {"id": "event_123"}
        mock_service.events().move.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.move_event(
            calendar_id="primary",
            event_id="event_123",
            destination_calendar_id="secondary@example.com",
        )

        assert result.success
        mock_service.events().move.assert_called_once()


# ============================================================
# CalendarWriter Attendee Tests
# ============================================================


class TestCalendarWriterAttendee:
    """Test attendee management."""

    def test_add_attendee_dry_run(self):
        """Can add attendee in dry-run mode."""
        writer = CalendarWriter(dry_run=True)
        result = writer.add_attendee(
            calendar_id="primary",
            event_id="event_123",
            email="newperson@example.com",
        )

        assert result.success
        assert result.event_id == "event_123"

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_add_attendee_via_api(self, mock_get_service):
        """Can add attendee via API."""
        mock_service = MagicMock()

        # Mock get
        existing = {
            "id": "event_123",
            "summary": "Meeting",
            "attendees": [{"email": "alice@example.com"}],
        }
        mock_service.events().get.return_value.execute.return_value = existing

        # Mock update
        updated = existing.copy()
        updated["attendees"].append({"email": "bob@example.com"})
        mock_service.events().update.return_value.execute.return_value = updated

        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.add_attendee(
            calendar_id="primary",
            event_id="event_123",
            email="bob@example.com",
        )

        assert result.success
        mock_service.events().get.assert_called_once()
        mock_service.events().update.assert_called_once()

    @patch("lib.integrations.calendar_writer.CalendarWriter._get_service")
    def test_add_attendee_duplicate(self, mock_get_service):
        """Does not add duplicate attendees."""
        mock_service = MagicMock()

        existing = {
            "id": "event_123",
            "attendees": [{"email": "alice@example.com"}],
        }
        mock_service.events().get.return_value.execute.return_value = existing

        updated = existing.copy()
        mock_service.events().update.return_value.execute.return_value = updated

        mock_get_service.return_value = mock_service

        writer = CalendarWriter(dry_run=False)
        result = writer.add_attendee(
            calendar_id="primary",
            event_id="event_123",
            email="alice@example.com",  # Already exists
        )

        assert result.success
        # Verify attendee list wasn't changed
        call_args = mock_service.events().update.call_args
        assert len(call_args.kwargs["body"]["attendees"]) == 1


# ============================================================
# CalendarWriter Free Slots Tests
# ============================================================


class TestCalendarWriterFreeSlots:
    """Test finding free time slots."""

    def test_find_free_slots_empty_calendar(self):
        """Can find free slots in empty calendar."""
        mock_service = MagicMock()
        mock_response = {"items": []}
        mock_service.events().list.return_value.execute.return_value = mock_response

        with patch.object(CalendarWriter, "_get_service", return_value=mock_service):
            writer = CalendarWriter(dry_run=False)
            result = writer.find_free_slots(
                calendar_id="primary",
                start="2026-02-21T09:00:00Z",
                end="2026-02-21T17:00:00Z",
            )

            assert len(result) == 1
            assert result[0]["duration_minutes"] == 480  # 8 hours
            assert "start" in result[0]
            assert "end" in result[0]

    def test_find_free_slots_with_busy_time(self):
        """Can find free slots around busy times."""
        mock_service = MagicMock()
        mock_response = {
            "items": [
                {
                    "start": {"dateTime": "2026-02-21T10:00:00Z"},
                    "end": {"dateTime": "2026-02-21T11:00:00Z"},
                }
            ]
        }
        mock_service.events().list.return_value.execute.return_value = mock_response

        with patch.object(CalendarWriter, "_get_service", return_value=mock_service):
            writer = CalendarWriter(dry_run=False)
            result = writer.find_free_slots(
                calendar_id="primary",
                start="2026-02-21T09:00:00Z",
                end="2026-02-21T12:00:00Z",
            )

            # Should have two free slots: 9-10am and 11am-12pm
            assert len(result) >= 1
            # Each slot should be at least 30 minutes (default)
            for slot in result:
                assert slot["duration_minutes"] >= 30

    def test_find_free_slots_custom_duration(self):
        """Can find slots with custom minimum duration."""
        mock_service = MagicMock()
        mock_response = {"items": []}
        mock_service.events().list.return_value.execute.return_value = mock_response

        with patch.object(CalendarWriter, "_get_service", return_value=mock_service):
            writer = CalendarWriter(dry_run=False)
            result = writer.find_free_slots(
                calendar_id="primary",
                start="2026-02-21T09:00:00Z",
                end="2026-02-21T17:00:00Z",
                duration_minutes=120,  # Need 2 hours
            )

            assert len(result) == 1
            assert result[0]["duration_minutes"] >= 120

    def test_find_free_slots_multiple_busy_blocks(self):
        """Can find free slots between multiple busy blocks."""
        mock_service = MagicMock()
        mock_response = {
            "items": [
                {
                    "start": {"dateTime": "2026-02-21T09:00:00Z"},
                    "end": {"dateTime": "2026-02-21T10:00:00Z"},
                },
                {
                    "start": {"dateTime": "2026-02-21T14:00:00Z"},
                    "end": {"dateTime": "2026-02-21T15:00:00Z"},
                },
            ]
        }
        mock_service.events().list.return_value.execute.return_value = mock_response

        with patch.object(CalendarWriter, "_get_service", return_value=mock_service):
            writer = CalendarWriter(dry_run=False)
            result = writer.find_free_slots(
                calendar_id="primary",
                start="2026-02-21T08:00:00Z",
                end="2026-02-21T17:00:00Z",
                duration_minutes=30,
            )

            # Should find slots before 9am, between 10-2pm, and after 3pm
            assert len(result) >= 2

    def test_find_free_slots_api_error(self):
        """Handles API errors gracefully."""
        mock_service = MagicMock()
        mock_service.events().list.return_value.execute.side_effect = Exception("403 Forbidden")

        with patch.object(CalendarWriter, "_get_service", return_value=mock_service):
            writer = CalendarWriter(dry_run=False)
            result = writer.find_free_slots(
                calendar_id="primary",
                start="2026-02-21T09:00:00Z",
                end="2026-02-21T17:00:00Z",
            )

            # Should return empty list on error
            assert result == []


# ============================================================
# CalendarWriter Time Parsing Tests
# ============================================================


class TestCalendarWriterTimeParsing:
    """Test time parsing."""

    def test_parse_time_iso_datetime(self):
        """Can parse ISO datetime strings."""
        writer = CalendarWriter()
        result = writer._parse_time("2026-02-21T10:00:00")
        assert result["dateTime"] == "2026-02-21T10:00:00"
        assert "date" not in result

    def test_parse_time_date_only(self):
        """Can parse date-only strings."""
        writer = CalendarWriter()
        result = writer._parse_time("2026-02-21")
        assert result["date"] == "2026-02-21"
        assert "dateTime" not in result

    def test_parse_time_iso_with_timezone(self):
        """Can parse ISO datetime with timezone."""
        writer = CalendarWriter()
        result = writer._parse_time("2026-02-21T10:00:00Z")
        assert result["dateTime"] == "2026-02-21T10:00:00Z"


# ============================================================
# CalendarWriteResult Tests
# ============================================================


class TestCalendarWriteResult:
    """Test result object."""

    def test_result_success(self):
        """Can create success result."""
        result = CalendarWriteResult(
            success=True,
            event_id="event_123",
            link="https://calendar.google.com/...",
        )

        assert result.success
        assert result.event_id == "event_123"
        assert result.link == "https://calendar.google.com/..."
        assert result.error is None

    def test_result_failure(self):
        """Can create failure result."""
        result = CalendarWriteResult(
            success=False,
            error="API Error",
        )

        assert not result.success
        assert result.event_id is None
        assert result.error == "API Error"

    def test_result_with_data(self):
        """Can include raw API response data."""
        data = {"id": "event_123", "summary": "Meeting"}
        result = CalendarWriteResult(
            success=True,
            event_id="event_123",
            data=data,
        )

        assert result.success
        assert result.data == data
