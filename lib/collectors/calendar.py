"""
Calendar Collector - Pulls events from Google Calendar via Service Account API.
Uses direct Google API with service account for domain-wide delegation.

Note: DWD allowlist has `calendar` (full) authorized, not `calendar.readonly`.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Python 3.11+ compatibility: UTC constant
try:
    from datetime import UTC  # Python 3.11+
except ImportError:
    import datetime as _dtmod  # noqa: F811

    UTC = _dtmod.timezone.utc  # noqa

from .base import BaseCollector

logger = logging.getLogger(__name__)

# Service account configuration
SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
# Note: calendar.readonly is NOT in our DWD allowlist; calendar (full) IS authorized
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_USER = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")

# Debug flag (set AUTH_DEBUG=1 to enable)
AUTH_DEBUG = os.environ.get("AUTH_DEBUG", "0") == "1"


def _debug_print(msg: str) -> None:
    """Print debug message if AUTH_DEBUG is enabled."""
    if AUTH_DEBUG:
        print(f"[AUTH_DEBUG] {msg}")


class CalendarCollector(BaseCollector):
    """Collects events from Google Calendar using Service Account."""

    source_name = "calendar"
    target_table = "events"

    def __init__(self, config: dict, store=None):
        super().__init__(config, store)
        self._service = None

    def _get_service(self, user: str = DEFAULT_USER):
        """Get Calendar API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            # Debug: show SA details
            if AUTH_DEBUG:
                with open(SA_FILE) as f:
                    sa_data = json.load(f)
                _debug_print(f"SA_EMAIL: {sa_data.get('client_email')}")
                _debug_print(f"SUBJECT: {user}")
                _debug_print(f"SCOPES: {SCOPES}")

            creds = service_account.Credentials.from_service_account_file(
                str(SA_FILE), scopes=SCOPES
            )
            creds = creds.with_subject(user)
            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except Exception as e:
            self.logger.error(f"Failed to get Calendar service: {e}")
            raise

    def collect(self) -> dict[str, Any]:
        """Fetch events from all Google Calendars using Service Account API."""
        try:
            service = self._get_service()
            all_events = []

            lookback_days = self.config.get("lookback_days", 30)
            lookahead_days = self.config.get("lookahead_days", 30)
            max_results = self.config.get("max_results", 200)

            # Calculate date range
            now = datetime.now(UTC)
            time_min = (now - timedelta(days=lookback_days)).isoformat()
            time_max = (now + timedelta(days=lookahead_days)).isoformat()

            # Step 1: List all available calendars
            _debug_print("ENDPOINT: calendar.calendarList.list")
            calendars_result = service.calendarList().list().execute()
            calendar_items = calendars_result.get("items", [])
            _debug_print(f"STATUS: 200 OK, {len(calendar_items)} calendars")

            # Step 2: Fetch events from each calendar
            per_calendar_limit = max(1, max_results // max(1, len(calendar_items)))

            for calendar in calendar_items:
                calendar_id = calendar.get("id", "primary")
                _debug_print(f"ENDPOINT: calendar.events.list(calendarId='{calendar_id}')")

                try:
                    results = (
                        service.events()
                        .list(
                            calendarId=calendar_id,
                            timeMin=time_min,
                            timeMax=time_max,
                            maxResults=min(per_calendar_limit, 250),
                            singleEvents=True,
                            orderBy="startTime",
                            fields="items(id,summary,start,end,location,description,attendees,organizer,conferenceData,recurrence,eventType,status,created,updated,htmlLink)",
                        )
                        .execute()
                    )

                    events = results.get("items", [])
                    _debug_print(f"STATUS: 200 OK, {len(events)} events from {calendar_id}")

                    for event in events:
                        event_copy = event.copy()
                        event_copy["calendar_id"] = calendar_id
                        all_events.append(event_copy)

                        # Stop if we've collected enough total events
                        if len(all_events) >= max_results:
                            return {"events": all_events[:max_results]}

                except Exception as e:
                    self.logger.warning(f"Failed to fetch events from calendar {calendar_id}: {e}")
                    continue

            return {"events": all_events[:max_results]}

        except Exception as e:
            self.logger.error(f"Calendar collection failed: {e}")
            return {"events": []}

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Calendar events to canonical format."""
        now = datetime.now().isoformat()
        transformed = []

        for event in raw_data.get("events", []):
            event_id = event.get("id")
            if not event_id:
                continue

            start_time = self._parse_event_time(event)
            end_time = self._parse_event_end_time(event)

            # Skip if no valid start time
            if not start_time:
                continue

            # Extract expanded fields
            organizer_email, organizer_name = self._extract_organizer(event)
            conference_url, conference_type = self._extract_conference(event)
            recurrence = self._extract_recurrence(event)
            event_type = event.get("eventType", "default")
            calendar_id = event.get("calendar_id", "primary")
            attendees_list = event.get("attendees", [])
            attendee_count, accepted_count, declined_count = self._count_attendees(attendees_list)

            transformed.append(
                {
                    "id": f"calendar_{event_id}",
                    "source": "calendar",
                    "source_id": event_id,
                    "title": event.get("summary", "No Title"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": event.get("location", ""),
                    "attendees": json.dumps(self._extract_attendees(event)),
                    "status": event.get("status", "confirmed"),
                    "organizer_email": organizer_email,
                    "organizer_name": organizer_name,
                    "conference_url": conference_url,
                    "conference_type": conference_type,
                    "recurrence": recurrence,
                    "event_type": event_type,
                    "calendar_id": calendar_id,
                    "attendee_count": attendee_count,
                    "accepted_count": accepted_count,
                    "declined_count": declined_count,
                    "prep_notes": json.dumps(self._infer_prep(event)),
                    "context": json.dumps(event),
                    "created_at": event.get("created", now),
                    "updated_at": now,
                }
            )

        return transformed

    def _parse_event_time(self, event: dict) -> str:
        """Parse event start time."""
        start = event.get("start", {})

        if isinstance(start, dict):
            if "dateTime" in start:
                return str(start["dateTime"])
            if "date" in start:
                return f"{start['date']}T00:00:00"

        if isinstance(start, str):
            return start

        return ""

    def _parse_event_end_time(self, event: dict) -> str:
        """Parse event end time."""
        end = event.get("end", {})

        if isinstance(end, dict):
            if "dateTime" in end:
                return str(end["dateTime"])
            if "date" in end:
                return f"{end['date']}T23:59:59"

        if isinstance(end, str):
            return end

        return ""

    def _extract_attendees(self, event: dict) -> list[str]:
        """Extract attendee emails."""
        attendees = event.get("attendees", [])
        if isinstance(attendees, list):
            return [a.get("email", "") for a in attendees if isinstance(a, dict) and a.get("email")]
        return []

    def _infer_prep(self, event: dict) -> dict:
        """Infer preparation requirements from event."""
        prep = {"time_minutes": self.config.get("prep_time_default", 15), "items": []}

        title = (event.get("summary") or "").lower()

        # Meeting types that need prep
        if any(word in title for word in ["interview", "presentation", "pitch", "demo"]):
            prep["time_minutes"] = 30
            prep["items"].append("Review materials")

        if any(word in title for word in ["1:1", "1-1", "one on one"]):
            prep["items"].append("Check notes from last meeting")

        if "call" in title or "meeting" in title:
            prep["items"].append("Join link ready")

        # Location-based prep
        location = event.get("location", "").lower()
        if location and not any(word in location for word in ["zoom", "meet", "teams", "http"]):
            prep["time_minutes"] += 15  # Travel time
            prep["items"].append("Travel to location")

        return prep

    def _extract_organizer(self, event: dict) -> tuple[str, str]:
        """Extract organizer email and name from event."""
        organizer = event.get("organizer", {})
        if isinstance(organizer, dict):
            return organizer.get("email", ""), organizer.get("displayName", "")
        return "", ""

    def _extract_conference(self, event: dict) -> tuple[str, str]:
        """Extract conference/video call URL and type from conferenceData."""
        conference_data = event.get("conferenceData", {})
        if not isinstance(conference_data, dict):
            return "", ""

        # Extract conference type
        conference_solution = conference_data.get("conferenceSolution", {})
        if isinstance(conference_solution, dict):
            solution_key = conference_solution.get("key", {})
            if isinstance(solution_key, dict):
                conference_type = solution_key.get("type", "")
            else:
                conference_type = ""
        else:
            conference_type = ""

        # Extract video entry point URL
        entry_points = conference_data.get("entryPoints", [])
        video_url = ""
        if isinstance(entry_points, list):
            for entry in entry_points:
                if isinstance(entry, dict) and entry.get("entryPointType") == "video":
                    video_url = entry.get("uri", "")
                    break

        return video_url, conference_type

    def _extract_recurrence(self, event: dict) -> str:
        """Extract recurrence rule as comma-separated RRULE string."""
        recurrence = event.get("recurrence", [])
        if isinstance(recurrence, list) and recurrence:
            return ",".join(recurrence)
        return ""

    def _count_attendees(self, attendees: list) -> tuple[int, int, int]:
        """Count total, accepted, and declined attendees."""
        if not isinstance(attendees, list):
            return 0, 0, 0

        total = len(attendees)
        accepted = sum(
            1 for a in attendees if isinstance(a, dict) and a.get("responseStatus") == "accepted"
        )
        declined = sum(
            1 for a in attendees if isinstance(a, dict) and a.get("responseStatus") == "declined"
        )

        return total, accepted, declined

    def _transform_attendees(self, event_id: str, attendees: list) -> list[dict]:
        """Transform attendees list to calendar_attendees table rows."""
        rows = []
        if not isinstance(attendees, list):
            return rows

        for idx, attendee in enumerate(attendees):
            if not isinstance(attendee, dict):
                continue

            row = {
                "id": f"{event_id}_attendee_{idx}",
                "event_id": event_id,
                "email": attendee.get("email", ""),
                "display_name": attendee.get("displayName"),
                "response_status": attendee.get("responseStatus"),
                "organizer": 1 if attendee.get("organizer", False) else 0,
                "self": 1 if attendee.get("self", False) else 0,
            }
            rows.append(row)

        return rows

    def _transform_recurrence(self, event_id: str, recurrence: list) -> list[dict]:
        """Transform recurrence array to calendar_recurrence_rules table rows."""
        rows = []
        if not isinstance(recurrence, list):
            return rows

        for idx, rrule in enumerate(recurrence):
            if not rrule:
                continue

            row = {
                "id": f"{event_id}_rrule_{idx}",
                "event_id": event_id,
                "rrule": rrule,
            }
            rows.append(row)

        return rows

    def sync(self) -> dict[str, Any]:
        """
        Override sync to handle multi-table storage.
        Primary: calendar_events (aliased as 'events')
        Secondary: calendar_attendees, calendar_recurrence_rules
        """
        cycle_start = datetime.now()

        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            self.logger.warning(f"Circuit breaker is {self.circuit_breaker.state}. Skipping sync.")
            self.metrics["circuit_opens"] += 1
            return {
                "source": self.source_name,
                "success": False,
                "error": f"Circuit breaker {self.circuit_breaker.state}",
                "timestamp": datetime.now().isoformat(),
            }

        try:
            # Step 1: Collect from external source with retry
            self.logger.info(f"Collecting from {self.source_name}")

            def collect_with_retry():
                return self.collect()

            try:
                from .resilience import retry_with_backoff

                raw_data = retry_with_backoff(collect_with_retry, self.retry_config, self.logger)
            except Exception as e:
                self.logger.error(f"Collect failed after retries: {e}")
                self.circuit_breaker.record_failure()
                self.store.update_sync_state(self.source_name, success=False, error=str(e))
                return {
                    "source": self.source_name,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

            # Step 2: Transform to canonical format
            try:
                transformed = self.transform(raw_data)
            except Exception as e:
                self.logger.warning(f"Transform failed: {e}. Attempting partial success.")
                transformed = []
                self.metrics["partial_failures"] += 1

            self.logger.info(f"Transformed {len(transformed)} items")

            # Step 3: Store primary table (events)
            stored_primary = self.store.insert_many(self.target_table, transformed)
            self.logger.info(f"Stored {stored_primary} events to {self.target_table}")

            # Step 4: Store secondary tables
            attendees_stored = 0
            recurrence_stored = 0

            for event in raw_data.get("events", []):
                event_id = event.get("id")
                if not event_id:
                    continue

                # Store attendees
                attendees = event.get("attendees", [])
                attendee_rows = self._transform_attendees(event_id, attendees)
                if attendee_rows:
                    try:
                        attendees_stored += self.store.insert_many(
                            "calendar_attendees", attendee_rows
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to store attendees for {event_id}: {e}")

                # Store recurrence rules
                recurrence = event.get("recurrence", [])
                recurrence_rows = self._transform_recurrence(event_id, recurrence)
                if recurrence_rows:
                    try:
                        recurrence_stored += self.store.insert_many(
                            "calendar_recurrence_rules", recurrence_rows
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to store recurrence for {event_id}: {e}")

            # Step 5: Update sync state and record success
            self.last_sync = datetime.now()
            self.store.update_sync_state(self.source_name, success=True, items=stored_primary)
            self.circuit_breaker.record_success()

            duration_ms = (datetime.now() - cycle_start).total_seconds() * 1000

            return {
                "source": self.source_name,
                "success": True,
                "collected": len(raw_data.get("events", [])),
                "transformed": len(transformed),
                "stored_primary": stored_primary,
                "stored_attendees": attendees_stored,
                "stored_recurrence": recurrence_stored,
                "duration_ms": duration_ms,
                "timestamp": self.last_sync.isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Sync failed for {self.source_name}: {e}")
            self.circuit_breaker.record_failure()
            self.store.update_sync_state(self.source_name, success=False, error=str(e))
            return {
                "source": self.source_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Calendar Collector CLI")
    parser.add_argument("--user", default=DEFAULT_USER, help="User to impersonate")
    parser.add_argument("--limit", type=int, default=10, help="Max events to fetch")
    args = parser.parse_args()

    # Direct API call for proof (no collector instantiation needed)
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    with open(SA_FILE) as f:
        sa_data = json.load(f)

    print(f"[AUTH_DEBUG] SA_EMAIL: {sa_data.get('client_email')}", file=sys.stderr)
    print(f"[AUTH_DEBUG] SUBJECT: {args.user}", file=sys.stderr)
    print(f"[AUTH_DEBUG] SCOPES: {SCOPES}", file=sys.stderr)

    creds = service_account.Credentials.from_service_account_file(str(SA_FILE), scopes=SCOPES)
    creds = creds.with_subject(args.user)
    service = build("calendar", "v3", credentials=creds)

    print("[AUTH_DEBUG] ENDPOINT: calendar.calendarList.list", file=sys.stderr)
    calendars = service.calendarList().list().execute()
    print(
        f"[AUTH_DEBUG] STATUS: 200 OK, {len(calendars.get('items', []))} calendars", file=sys.stderr
    )

    print("[AUTH_DEBUG] ENDPOINT: calendar.events.list(calendarId='primary')", file=sys.stderr)
    now = datetime.now(UTC)
    time_min = (now - timedelta(days=7)).isoformat()
    time_max = (now + timedelta(days=7)).isoformat()

    results = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=args.limit,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = results.get("items", [])
    print(f"[AUTH_DEBUG] STATUS: 200 OK, {len(events)} events", file=sys.stderr)

    for e in events[:5]:
        print(f"  - {e.get('summary', 'No Title')[:50]}")
