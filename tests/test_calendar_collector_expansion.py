"""
Tests for expanded Calendar Collector (CS-5.1).

Tests the ~85% API coverage implementation including:
- Attendee response status and organizer flags
- Conference/video call links extraction
- Recurrence rules collection
- Event type detection (default, focusTime, outOfOffice, workingLocation)
- Multi-calendar support
- Organizer field extraction
- Multiple tables storage (calendar_attendees, calendar_recurrence_rules)

All tests use mocks - NO live API calls.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from lib.collectors.calendar import CalendarCollector
from lib.state_store import StateStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_store():
    """Mock StateStore for testing."""
    store = MagicMock(spec=StateStore)
    store.insert_many.return_value = 5  # Simulate inserting 5 rows
    return store


@pytest.fixture
def collector(mock_store):
    """Create a CalendarCollector with mocked store."""
    config = {"sync_interval": 300, "lookback_days": 30, "lookahead_days": 30, "max_results": 200}
    collector = CalendarCollector(config=config, store=mock_store)
    return collector


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================


@pytest.fixture
def mock_event_with_full_data():
    """Mock event with all expanded fields."""
    return {
        "id": "event_123",
        "summary": "Team Standup Meeting",
        "start": {"dateTime": "2026-02-21T09:00:00Z"},
        "end": {"dateTime": "2026-02-21T09:30:00Z"},
        "location": "Google Meet",
        "description": "Daily standup",
        "status": "confirmed",
        "created": "2026-02-01T10:00:00Z",
        "updated": "2026-02-21T10:00:00Z",
        "htmlLink": "https://calendar.google.com/calendar/event_123",
        "calendar_id": "primary",
        "organizer": {
            "email": "molham@hrmny.co",
            "displayName": "Molham",
        },
        "attendees": [
            {
                "email": "molham@hrmny.co",
                "displayName": "Molham",
                "responseStatus": "accepted",
                "organizer": True,
                "self": True,
            },
            {
                "email": "john@example.com",
                "displayName": "John Doe",
                "responseStatus": "accepted",
                "organizer": False,
                "self": False,
            },
            {
                "email": "jane@example.com",
                "displayName": "Jane Smith",
                "responseStatus": "tentative",
                "organizer": False,
                "self": False,
            },
            {
                "email": "bob@example.com",
                "displayName": "Bob Wilson",
                "responseStatus": "declined",
                "organizer": False,
                "self": False,
            },
        ],
        "conferenceData": {
            "entryPoints": [
                {
                    "entryPointType": "video",
                    "uri": "https://meet.google.com/abc-defg-hij",
                    "label": "Google Meet",
                },
                {
                    "entryPointType": "phone",
                    "uri": "tel:+1-555-123-4567",
                    "label": "Phone",
                },
            ],
            "conferenceSolution": {
                "key": {
                    "type": "hangoutsMeet",
                },
                "name": "Google Meet",
            },
        },
        "recurrence": ["RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20260630T235959Z"],
        "eventType": "default",
    }


@pytest.fixture
def mock_focus_time_event():
    """Mock focus time event."""
    return {
        "id": "event_focus",
        "summary": "Focus Time",
        "start": {"dateTime": "2026-02-21T14:00:00Z"},
        "end": {"dateTime": "2026-02-21T15:00:00Z"},
        "location": "",
        "status": "confirmed",
        "created": "2026-02-21T08:00:00Z",
        "updated": "2026-02-21T08:00:00Z",
        "htmlLink": "https://calendar.google.com/calendar/event_focus",
        "calendar_id": "primary",
        "organizer": {"email": "molham@hrmny.co", "displayName": "Molham"},
        "attendees": [
            {
                "email": "molham@hrmny.co",
                "responseStatus": "accepted",
                "organizer": True,
                "self": True,
            }
        ],
        "eventType": "focusTime",
    }


@pytest.fixture
def mock_out_of_office_event():
    """Mock out-of-office event."""
    return {
        "id": "event_ooo",
        "summary": "Out of Office",
        "start": {"date": "2026-03-01"},
        "end": {"date": "2026-03-05"},
        "status": "confirmed",
        "created": "2026-02-21T08:00:00Z",
        "updated": "2026-02-21T08:00:00Z",
        "htmlLink": "https://calendar.google.com/calendar/event_ooo",
        "calendar_id": "primary",
        "organizer": {"email": "molham@hrmny.co", "displayName": "Molham"},
        "attendees": [
            {
                "email": "molham@hrmny.co",
                "responseStatus": "accepted",
                "organizer": True,
                "self": True,
            }
        ],
        "eventType": "outOfOffice",
    }


@pytest.fixture
def mock_recurring_event():
    """Mock recurring event with multiple rules."""
    return {
        "id": "event_recurring",
        "summary": "Weekly Team Meeting",
        "start": {"dateTime": "2026-02-21T10:00:00Z"},
        "end": {"dateTime": "2026-02-21T11:00:00Z"},
        "location": "Conference Room A",
        "status": "confirmed",
        "created": "2026-02-01T10:00:00Z",
        "updated": "2026-02-21T10:00:00Z",
        "htmlLink": "https://calendar.google.com/calendar/event_recurring",
        "calendar_id": "work",
        "organizer": {"email": "manager@example.com", "displayName": "Manager"},
        "attendees": [
            {
                "email": "molham@hrmny.co",
                "displayName": "Molham",
                "responseStatus": "accepted",
            },
            {"email": "alice@example.com", "displayName": "Alice", "responseStatus": "accepted"},
        ],
        "recurrence": [
            "RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20260630T235959Z",
            "EXDATE:20260228T100000Z",
        ],
        "eventType": "default",
    }


@pytest.fixture
def mock_event_no_conference():
    """Mock event without conference data."""
    return {
        "id": "event_no_conf",
        "summary": "In-person Meeting",
        "start": {"dateTime": "2026-02-21T11:00:00Z"},
        "end": {"dateTime": "2026-02-21T12:00:00Z"},
        "location": "Building A, Room 101",
        "status": "confirmed",
        "created": "2026-02-21T08:00:00Z",
        "updated": "2026-02-21T08:00:00Z",
        "htmlLink": "https://calendar.google.com/calendar/event_no_conf",
        "calendar_id": "primary",
        "organizer": {"email": "molham@hrmny.co", "displayName": "Molham"},
        "attendees": [
            {
                "email": "molham@hrmny.co",
                "responseStatus": "accepted",
                "organizer": True,
                "self": True,
            }
        ],
        "eventType": "default",
    }


# =============================================================================
# ORGANIZER EXTRACTION TESTS
# =============================================================================


class TestExtractOrganizer:
    """Tests for _extract_organizer method."""

    def test_extract_organizer_with_email_and_name(self, collector, mock_event_with_full_data):
        """Should extract organizer email and name."""
        email, name = collector._extract_organizer(mock_event_with_full_data)

        assert email == "molham@hrmny.co"
        assert name == "Molham"

    def test_extract_organizer_with_only_email(self, collector):
        """Should extract organizer with only email."""
        event = {
            "organizer": {
                "email": "test@example.com",
            }
        }

        email, name = collector._extract_organizer(event)

        assert email == "test@example.com"
        assert name == ""

    def test_extract_organizer_missing(self, collector):
        """Should return empty strings when organizer missing."""
        event = {"id": "event_1"}

        email, name = collector._extract_organizer(event)

        assert email == ""
        assert name == ""

    def test_extract_organizer_invalid_type(self, collector):
        """Should handle invalid organizer type."""
        event = {"organizer": "not_a_dict"}

        email, name = collector._extract_organizer(event)

        assert email == ""
        assert name == ""


# =============================================================================
# CONFERENCE EXTRACTION TESTS
# =============================================================================


class TestExtractConference:
    """Tests for _extract_conference method."""

    def test_extract_video_url_and_type(self, collector, mock_event_with_full_data):
        """Should extract video URL and conference type from conferenceData."""
        url, conf_type = collector._extract_conference(mock_event_with_full_data)

        assert url == "https://meet.google.com/abc-defg-hij"
        assert conf_type == "hangoutsMeet"

    def test_extract_conference_no_video_entry(self, collector):
        """Should return empty URL when no video entry point."""
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "phone",
                        "uri": "tel:+1-555-123-4567",
                    }
                ],
                "conferenceSolution": {"key": {"type": "hangoutsMeet"}},
            }
        }

        url, conf_type = collector._extract_conference(event)

        assert url == ""
        assert conf_type == "hangoutsMeet"

    def test_extract_conference_missing(self, collector):
        """Should return empty strings when conferenceData missing."""
        event = {"id": "event_1"}

        url, conf_type = collector._extract_conference(event)

        assert url == ""
        assert conf_type == ""

    def test_extract_conference_invalid_type(self, collector):
        """Should handle invalid conferenceData type."""
        event = {"conferenceData": "not_a_dict"}

        url, conf_type = collector._extract_conference(event)

        assert url == ""
        assert conf_type == ""


# =============================================================================
# RECURRENCE EXTRACTION TESTS
# =============================================================================


class TestExtractRecurrence:
    """Tests for _extract_recurrence method."""

    def test_extract_single_recurrence_rule(self, collector):
        """Should extract single RRULE as string."""
        event = {"recurrence": ["RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20260630T235959Z"]}

        rrule = collector._extract_recurrence(event)

        assert rrule == "RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20260630T235959Z"

    def test_extract_multiple_recurrence_rules(self, collector, mock_recurring_event):
        """Should extract multiple RRULEs joined by comma."""
        rrule = collector._extract_recurrence(mock_recurring_event)

        assert "RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20260630T235959Z" in rrule
        assert "EXDATE:20260228T100000Z" in rrule
        assert "," in rrule

    def test_extract_no_recurrence(self, collector):
        """Should return empty string when no recurrence."""
        event = {"id": "event_1"}

        rrule = collector._extract_recurrence(event)

        assert rrule == ""

    def test_extract_recurrence_invalid_type(self, collector):
        """Should handle invalid recurrence type."""
        event = {"recurrence": "not_a_list"}

        rrule = collector._extract_recurrence(event)

        assert rrule == ""


# =============================================================================
# ATTENDEE COUNTING TESTS
# =============================================================================


class TestCountAttendees:
    """Tests for _count_attendees method."""

    def test_count_attendees_with_mixed_responses(self, collector, mock_event_with_full_data):
        """Should count total, accepted, and declined attendees."""
        attendees = mock_event_with_full_data["attendees"]

        total, accepted, declined = collector._count_attendees(attendees)

        assert total == 4
        assert accepted == 2  # molham and john
        assert declined == 1  # bob

    def test_count_attendees_empty_list(self, collector):
        """Should return zeros for empty attendee list."""
        total, accepted, declined = collector._count_attendees([])

        assert total == 0
        assert accepted == 0
        assert declined == 0

    def test_count_attendees_invalid_type(self, collector):
        """Should handle invalid attendees type."""
        total, accepted, declined = collector._count_attendees("not_a_list")

        assert total == 0
        assert accepted == 0
        assert declined == 0

    def test_count_attendees_with_tentative(self, collector, mock_event_with_full_data):
        """Should only count accepted and declined, not tentative."""
        attendees = mock_event_with_full_data["attendees"]

        total, accepted, declined = collector._count_attendees(attendees)

        # jane has "tentative" response, should not be counted in accepted
        assert total == 4
        assert accepted == 2  # only molham and john (not jane)
        assert declined == 1


# =============================================================================
# ATTENDEE TRANSFORMATION TESTS
# =============================================================================


class TestTransformAttendees:
    """Tests for _transform_attendees method."""

    def test_transform_attendees_with_multiple_statuses(self, collector, mock_event_with_full_data):
        """Should correctly transform attendees list."""
        attendees = mock_event_with_full_data["attendees"]

        rows = collector._transform_attendees("event_123", attendees)

        assert len(rows) == 4
        assert rows[0]["email"] == "molham@hrmny.co"
        assert rows[0]["organizer"] == 1
        assert rows[0]["self"] == 1
        assert rows[0]["response_status"] == "accepted"

        assert rows[3]["email"] == "bob@example.com"
        assert rows[3]["organizer"] == 0
        assert rows[3]["response_status"] == "declined"

    def test_transform_attendees_empty_list(self, collector):
        """Should return empty list for empty attendees."""
        rows = collector._transform_attendees("event_1", [])

        assert rows == []

    def test_transform_attendees_invalid_type(self, collector):
        """Should handle invalid attendees type."""
        rows = collector._transform_attendees("event_1", "not_a_list")

        assert rows == []

    def test_transform_attendees_missing_fields(self, collector):
        """Should handle attendees with missing fields."""
        attendees = [
            {
                "email": "test@example.com",
                # missing displayName, responseStatus, organizer, self
            }
        ]

        rows = collector._transform_attendees("event_1", attendees)

        assert len(rows) == 1
        assert rows[0]["email"] == "test@example.com"
        assert rows[0]["display_name"] is None
        assert rows[0]["response_status"] is None


# =============================================================================
# RECURRENCE TRANSFORMATION TESTS
# =============================================================================


class TestTransformRecurrence:
    """Tests for _transform_recurrence method."""

    def test_transform_single_recurrence_rule(self, collector):
        """Should transform single RRULE to table row."""
        recurrence = ["RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20260630T235959Z"]

        rows = collector._transform_recurrence("event_123", recurrence)

        assert len(rows) == 1
        assert rows[0]["event_id"] == "event_123"
        assert rows[0]["rrule"] == "RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20260630T235959Z"

    def test_transform_multiple_recurrence_rules(self, collector):
        """Should transform multiple RRULEs to separate rows."""
        recurrence = [
            "RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20260630T235959Z",
            "EXDATE:20260228T100000Z",
        ]

        rows = collector._transform_recurrence("event_456", recurrence)

        assert len(rows) == 2
        assert rows[0]["rrule"] == "RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20260630T235959Z"
        assert rows[1]["rrule"] == "EXDATE:20260228T100000Z"

    def test_transform_empty_recurrence(self, collector):
        """Should return empty list for empty recurrence."""
        rows = collector._transform_recurrence("event_1", [])

        assert rows == []

    def test_transform_recurrence_invalid_type(self, collector):
        """Should handle invalid recurrence type."""
        rows = collector._transform_recurrence("event_1", "not_a_list")

        assert rows == []


# =============================================================================
# EVENT TYPE DETECTION TESTS
# =============================================================================


class TestEventTypeDetection:
    """Tests for event type detection in transform method."""

    def test_focus_time_event_type(self, collector, mock_focus_time_event):
        """Should detect focus time event type."""
        raw_data = {"events": [mock_focus_time_event]}

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["event_type"] == "focusTime"

    def test_out_of_office_event_type(self, collector, mock_out_of_office_event):
        """Should detect out-of-office event type."""
        raw_data = {"events": [mock_out_of_office_event]}

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["event_type"] == "outOfOffice"

    def test_default_event_type(self, collector, mock_event_with_full_data):
        """Should detect default event type."""
        raw_data = {"events": [mock_event_with_full_data]}

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["event_type"] == "default"


# =============================================================================
# MULTI-CALENDAR SUPPORT TESTS
# =============================================================================


class TestMultiCalendarSupport:
    """Tests for multi-calendar support in transform method."""

    def test_calendar_id_from_primary(self, collector, mock_event_with_full_data):
        """Should include calendar_id from event."""
        raw_data = {"events": [mock_event_with_full_data]}

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["calendar_id"] == "primary"

    def test_calendar_id_from_secondary_calendar(self, collector, mock_recurring_event):
        """Should handle secondary calendar ID."""
        raw_data = {"events": [mock_recurring_event]}

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["calendar_id"] == "work"

    def test_calendar_id_defaults_to_primary(self, collector, mock_event_no_conference):
        """Should default to primary if calendar_id not set."""
        event = mock_event_no_conference.copy()
        del event["calendar_id"]
        raw_data = {"events": [event]}

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["calendar_id"] == "primary"


# =============================================================================
# TRANSFORM METHOD COMPREHENSIVE TESTS
# =============================================================================


class TestTransformFull:
    """Tests for full transform method with all expanded fields."""

    def test_transform_event_with_all_fields(self, collector, mock_event_with_full_data):
        """Should transform event with all expanded fields."""
        raw_data = {"events": [mock_event_with_full_data]}

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        event = transformed[0]

        # Basic fields
        assert event["id"] == "calendar_event_123"
        assert event["title"] == "Team Standup Meeting"
        assert event["status"] == "confirmed"

        # Expanded fields
        assert event["organizer_email"] == "molham@hrmny.co"
        assert event["organizer_name"] == "Molham"
        assert event["conference_url"] == "https://meet.google.com/abc-defg-hij"
        assert event["conference_type"] == "hangoutsMeet"
        assert "RRULE:FREQ=DAILY" in event["recurrence"]
        assert event["event_type"] == "default"
        assert event["calendar_id"] == "primary"
        assert event["attendee_count"] == 4
        assert event["accepted_count"] == 2
        assert event["declined_count"] == 1

    def test_transform_multiple_events(
        self, collector, mock_event_with_full_data, mock_focus_time_event, mock_out_of_office_event
    ):
        """Should transform multiple events with different types."""
        raw_data = {
            "events": [
                mock_event_with_full_data,
                mock_focus_time_event,
                mock_out_of_office_event,
            ]
        }

        transformed = collector.transform(raw_data)

        assert len(transformed) == 3
        assert transformed[0]["event_type"] == "default"
        assert transformed[1]["event_type"] == "focusTime"
        assert transformed[2]["event_type"] == "outOfOffice"

    def test_transform_skips_events_without_id(self, collector):
        """Should skip events without ID."""
        raw_data = {
            "events": [
                {"summary": "Event without ID", "start": {"dateTime": "2026-02-21T10:00:00Z"}},
                {
                    "id": "event_1",
                    "summary": "Valid Event",
                    "start": {"dateTime": "2026-02-21T10:00:00Z"},
                },
            ]
        }

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["id"] == "calendar_event_1"

    def test_transform_skips_events_without_start_time(self, collector):
        """Should skip events without valid start time."""
        raw_data = {
            "events": [
                {"id": "event_1", "summary": "Event without time"},
                {
                    "id": "event_2",
                    "summary": "Valid Event",
                    "start": {"dateTime": "2026-02-21T10:00:00Z"},
                },
            ]
        }

        transformed = collector.transform(raw_data)

        assert len(transformed) == 1
        assert transformed[0]["id"] == "calendar_event_2"
