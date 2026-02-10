"""
Calendar Collector - Pulls events from Google Calendar via gog CLI.
Uses REAL gog commands that actually work.
"""

import json
from datetime import datetime
from typing import Any

from .base import BaseCollector


class CalendarCollector(BaseCollector):
    """Collects events from Google Calendar."""

    source_name = "calendar"
    target_table = "events"

    def collect(self) -> dict[str, Any]:
        """Fetch events from Google Calendar using gog CLI."""
        try:
            lookback_days = self.config.get("lookback_days", 30)
            lookahead_days = self.config.get("lookahead_days", 30)

            # Calculate date range
            from datetime import timedelta

            today = datetime.now()
            from_date = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            to_date = (today + timedelta(days=lookahead_days)).strftime("%Y-%m-%d")

            # Get events in range (past 30 days + future 30 days)
            output = self._run_command(
                f'gog calendar list --from "{from_date}" --to "{to_date}" --max 200 --json 2>/dev/null',
                timeout=30,
            )

            if not output.strip():
                return {"events": []}

            data = self._parse_json_output(output)

            # gog calendar returns {"events": [...]}
            events = data.get("events", [])

            return {"events": events}

        except Exception as e:
            self.logger.warning(f"Calendar collection failed: {e}")
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
        """Parse event start time from gog output."""
        # gog calendar list returns events with 'start' as a string like "2026-02-01 10:00"
        # or as an object with dateTime/date
        start = event.get("start")

        if isinstance(start, str):
            # Direct string format from gog: "2026-02-01 10:00"
            try:
                dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
                return dt.isoformat()
            except ValueError:
                try:
                    dt = datetime.strptime(start, "%Y-%m-%d")
                    return dt.isoformat()
                except ValueError:
                    return start

        if isinstance(start, dict):
            # Google Calendar API format
            if "dateTime" in start:
                return start["dateTime"]
            if "date" in start:
                return f"{start['date']}T00:00:00"

        return ""

    def _parse_event_end_time(self, event: dict) -> str:
        """Parse event end time from gog output."""
        end = event.get("end")

        if isinstance(end, str):
            try:
                dt = datetime.strptime(end, "%Y-%m-%d %H:%M")
                return dt.isoformat()
            except ValueError:
                return end

        if isinstance(end, dict):
            if "dateTime" in end:
                return end["dateTime"]
            if "date" in end:
                return f"{end['date']}T23:59:59"

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
