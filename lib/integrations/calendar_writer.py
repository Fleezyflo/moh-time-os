"""
Calendar Writer - Write-back integration for Google Calendar.

Handles creating, updating, deleting events, managing attendees, and finding free slots
via Google API using service account with domain-wide delegation.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Service account configuration
DEFAULT_SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_USER = "molham@hrmny.co"


@dataclass
class CalendarWriteResult:
    """Result of a Calendar write operation."""

    success: bool
    event_id: str | None = None
    data: dict | None = None
    error: str | None = None
    link: str | None = None  # HTML link to the event

    def __post_init__(self):
        """Validate result state."""
        if self.success and not self.event_id:
            logger.warning("Success result without event_id")


class CalendarWriter:
    """Create, update, and delete events in Google Calendar."""

    def __init__(
        self,
        credentials_path: str | None = None,
        delegated_user: str | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize CalendarWriter.

        Args:
            credentials_path: Path to service account JSON. If None, uses env var or default.
            delegated_user: User to impersonate. If None, uses DEFAULT_USER.
            dry_run: If True, validate without sending.
        """
        self.credentials_path = credentials_path or os.environ.get(
            "CALENDAR_SA_FILE", str(DEFAULT_SA_FILE)
        )
        self.delegated_user = delegated_user or os.environ.get("CALENDAR_USER", DEFAULT_USER)
        self.dry_run = dry_run
        self._service = None

    def _get_service(self):
        """Get Calendar API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=SCOPES
            )
            creds = creds.with_subject(self.delegated_user)
            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to get Calendar service: {e}"
            logger.error(error_msg)
            raise

    def create_event(
        self,
        calendar_id: str,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        attendees: list[str] | None = None,
        location: str = "",
        reminders: dict | None = None,
    ) -> CalendarWriteResult:
        """
        Create a calendar event.

        Args:
            calendar_id: Calendar ID (e.g., 'primary')
            summary: Event title
            start: Start time (ISO 8601)
            end: End time (ISO 8601)
            description: Event description
            attendees: List of attendee emails
            location: Event location
            reminders: Reminders dict with 'useDefault' and/or 'overrides'

        Returns:
            CalendarWriteResult with event_id on success
        """
        try:
            event = {
                "summary": summary,
                "start": self._parse_time(start),
                "end": self._parse_time(end),
            }

            if description:
                event["description"] = description

            if location:
                event["location"] = location

            if attendees:
                event["attendees"] = [{"email": email} for email in attendees]

            if reminders:
                event["reminders"] = reminders

            if self.dry_run:
                return CalendarWriteResult(
                    success=True,
                    event_id="event_dry_run",
                    data={"dry_run": True, "summary": summary, "start": start},
                )

            service = self._get_service()
            result = service.events().insert(calendarId=calendar_id, body=event).execute()

            event_id = result.get("id")
            link = result.get("htmlLink")

            logger.info(f"Created event {event_id}: {summary}")
            return CalendarWriteResult(
                success=True,
                event_id=event_id,
                link=link,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to create event: {e}"
            logger.error(error_msg)
            return CalendarWriteResult(success=False, error=error_msg)

    def update_event(
        self,
        calendar_id: str,
        event_id: str,
        updates: dict,
    ) -> CalendarWriteResult:
        """
        Update an existing event.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID to update
            updates: Dict of fields to update (summary, description, location, etc.)

        Returns:
            CalendarWriteResult
        """
        try:
            if self.dry_run:
                return CalendarWriteResult(
                    success=True,
                    event_id=event_id,
                    data={"dry_run": True, "updates": updates},
                )

            service = self._get_service()

            # Get current event
            event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

            # Apply updates
            for key, value in updates.items():
                if key in ("start", "end"):
                    event[key] = self._parse_time(value)
                else:
                    event[key] = value

            result = (
                service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )

            logger.info(f"Updated event {event_id}")
            return CalendarWriteResult(
                success=True,
                event_id=event_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to update event {event_id}: {e}"
            logger.error(error_msg)
            return CalendarWriteResult(success=False, error=error_msg)

    def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> CalendarWriteResult:
        """
        Delete a calendar event.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID to delete

        Returns:
            CalendarWriteResult
        """
        try:
            if self.dry_run:
                return CalendarWriteResult(
                    success=True,
                    event_id=event_id,
                    data={"dry_run": True},
                )

            service = self._get_service()
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()

            logger.info(f"Deleted event {event_id}")
            return CalendarWriteResult(
                success=True,
                event_id=event_id,
                data={"deleted": True},
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to delete event {event_id}: {e}"
            logger.error(error_msg)
            return CalendarWriteResult(success=False, error=error_msg)

    def create_quick_event(
        self,
        calendar_id: str,
        text: str,
    ) -> CalendarWriteResult:
        """
        Create event using quickAdd (natural language).

        Args:
            calendar_id: Calendar ID
            text: Natural language event description (e.g., "Team meeting tomorrow at 3pm")

        Returns:
            CalendarWriteResult with event_id on success
        """
        try:
            if self.dry_run:
                return CalendarWriteResult(
                    success=True,
                    event_id="event_dry_run",
                    data={"dry_run": True, "text": text},
                )

            service = self._get_service()
            result = service.events().quickAdd(calendarId=calendar_id, text=text).execute()

            event_id = result.get("id")
            link = result.get("htmlLink")

            logger.info(f"Created event via quickAdd: {text}")
            return CalendarWriteResult(
                success=True,
                event_id=event_id,
                link=link,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to create quick event: {e}"
            logger.error(error_msg)
            return CalendarWriteResult(success=False, error=error_msg)

    def move_event(
        self,
        calendar_id: str,
        event_id: str,
        destination_calendar_id: str,
    ) -> CalendarWriteResult:
        """
        Move an event to a different calendar.

        Args:
            calendar_id: Source calendar ID
            event_id: Event ID to move
            destination_calendar_id: Destination calendar ID

        Returns:
            CalendarWriteResult
        """
        try:
            if self.dry_run:
                return CalendarWriteResult(
                    success=True,
                    event_id=event_id,
                    data={"dry_run": True, "destination": destination_calendar_id},
                )

            service = self._get_service()
            result = (
                service.events()
                .move(
                    calendarId=calendar_id,
                    eventId=event_id,
                    destination=destination_calendar_id,
                )
                .execute()
            )

            logger.info(f"Moved event {event_id} to calendar {destination_calendar_id}")
            return CalendarWriteResult(
                success=True,
                event_id=event_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to move event {event_id}: {e}"
            logger.error(error_msg)
            return CalendarWriteResult(success=False, error=error_msg)

    def add_attendee(
        self,
        calendar_id: str,
        event_id: str,
        email: str,
    ) -> CalendarWriteResult:
        """
        Add an attendee to an event.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            email: Attendee email to add

        Returns:
            CalendarWriteResult
        """
        try:
            if self.dry_run:
                return CalendarWriteResult(
                    success=True,
                    event_id=event_id,
                    data={"dry_run": True, "attendee": email},
                )

            service = self._get_service()

            # Get current event
            event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

            # Add attendee
            attendees = event.get("attendees", [])
            if not any(a.get("email") == email for a in attendees):
                attendees.append({"email": email})
            event["attendees"] = attendees

            result = (
                service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )

            logger.info(f"Added attendee {email} to event {event_id}")
            return CalendarWriteResult(
                success=True,
                event_id=event_id,
                data=result,
            )

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to add attendee to event {event_id}: {e}"
            logger.error(error_msg)
            return CalendarWriteResult(success=False, error=error_msg)

    def find_free_slots(
        self,
        calendar_id: str,
        start: str,
        end: str,
        duration_minutes: int = 30,
    ) -> list[dict]:
        """
        Find free time slots in a calendar.

        Args:
            calendar_id: Calendar ID
            start: Start time (ISO 8601)
            end: End time (ISO 8601)
            duration_minutes: Minimum duration for free slot

        Returns:
            List of free slots: [{"start": "...", "end": "...", "duration_minutes": ...}, ...]
        """
        try:
            service = self._get_service()

            # Get events in range
            events = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start,
                    timeMax=end,
                    singleEvents=True,
                    orderBy="startTime",
                    fields="items(start,end)",
                )
                .execute()
            )

            busy_times = []
            for event in events.get("items", []):
                event_start = event.get("start", {})
                event_end = event.get("end", {})

                start_time = event_start.get("dateTime") or event_start.get("date")
                end_time = event_end.get("dateTime") or event_end.get("date")

                if start_time and end_time:
                    busy_times.append(
                        {
                            "start": start_time,
                            "end": end_time,
                        }
                    )

            # Sort by start time
            busy_times.sort(key=lambda x: x["start"])

            # Find gaps
            free_slots = []
            search_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            search_end = datetime.fromisoformat(end.replace("Z", "+00:00"))

            if not busy_times:
                # Entire range is free
                duration = (search_end - search_start).total_seconds() / 60
                if duration >= duration_minutes:
                    free_slots.append(
                        {
                            "start": start,
                            "end": end,
                            "duration_minutes": int(duration),
                        }
                    )
            else:
                # Check gaps between busy times
                current = search_start

                for busy in busy_times:
                    busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
                    busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

                    # Gap before this busy time
                    if current < busy_start:
                        duration = (busy_start - current).total_seconds() / 60
                        if duration >= duration_minutes:
                            free_slots.append(
                                {
                                    "start": current.isoformat(),
                                    "end": busy_start.isoformat(),
                                    "duration_minutes": int(duration),
                                }
                            )

                    current = max(current, busy_end)

                # Gap after last busy time
                if current < search_end:
                    duration = (search_end - current).total_seconds() / 60
                    if duration >= duration_minutes:
                        free_slots.append(
                            {
                                "start": current.isoformat(),
                                "end": search_end.isoformat(),
                                "duration_minutes": int(duration),
                            }
                        )

            return free_slots

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            error_msg = f"Failed to find free slots: {e}"
            logger.error(error_msg)
            return []

    def _parse_time(self, time_str: str) -> dict:
        """
        Parse time string to Google Calendar format.

        Args:
            time_str: ISO 8601 datetime string

        Returns:
            Dict with 'dateTime' key for timezone-aware, 'date' for all-day
        """
        # If it looks like just a date (YYYY-MM-DD), use date format
        if len(time_str) == 10:
            return {"date": time_str}

        # Otherwise use dateTime format
        return {"dateTime": time_str}
