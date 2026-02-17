"""
Calendar Collector - Pulls events from Google Calendar via Service Account API.
Uses direct Google API with service account for domain-wide delegation.

Note: DWD allowlist has `calendar` (full) authorized, not `calendar.readonly`.
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .base import BaseCollector

logger = logging.getLogger(__name__)

# Service account configuration
SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
# Note: calendar.readonly is NOT in our DWD allowlist; calendar (full) IS authorized
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_USER = "molham@hrmny.co"

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
        """Fetch events from Google Calendar using Service Account API."""
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

            # Fetch events from primary calendar
            _debug_print("ENDPOINT: calendar.events.list(calendarId='primary')")
            results = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=min(max_results, 250),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = results.get("items", [])
            _debug_print(f"STATUS: 200 OK, {len(events)} events")

            for event in events[:max_results]:
                all_events.append(
                    {
                        "id": event.get("id"),
                        "summary": event.get("summary", ""),
                        "start": event.get("start", {}),
                        "end": event.get("end", {}),
                        "location": event.get("location", ""),
                        "description": event.get("description", ""),
                        "attendees": event.get("attendees", []),
                        "status": event.get("status", "confirmed"),
                        "created": event.get("created", ""),
                        "updated": event.get("updated", ""),
                        "htmlLink": event.get("htmlLink", ""),
                    }
                )

            return {"events": all_events}

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
