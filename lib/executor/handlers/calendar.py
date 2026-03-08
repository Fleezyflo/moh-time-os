"""
Calendar Handler - Executes calendar-related actions.

Supports two modes:
1. Local-only: stores events in local SQLite "events" table
2. Google Calendar: delegates to CalendarWriter for Google Calendar API calls

GAP-10-08: CalendarWriter integration for bidirectional calendar sync.
"""

import json
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class CalendarHandler:
    """Handles calendar-related action execution."""

    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}
        self._writer = None

    def _get_writer(self):
        """Lazy-initialize CalendarWriter if credentials available."""
        if self._writer is not None:
            return self._writer

        try:
            from lib.integrations.calendar_writer import CalendarWriter

            dry_run = self.config.get("dry_run", False)
            self._writer = CalendarWriter(dry_run=dry_run)
            logger.info("CalendarHandler: CalendarWriter enabled")
        except (ImportError, ValueError, OSError) as e:
            logger.warning("CalendarHandler: CalendarWriter not available: %s", e)
            self._writer = None

        return self._writer

    def execute(self, action: dict) -> dict:
        """Execute a calendar action."""
        action_type = action.get("action_type")

        handlers = {
            "create": self._create_event,
            "update": self._update_event,
            "delete": self._delete_event,
            "reschedule": self._reschedule_event,
        }

        handler = handlers.get(action_type)
        if not handler:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            return handler(action)
        except (sqlite3.Error, ValueError, OSError):
            raise

    def _create_event(self, action: dict) -> dict:
        data = action.get("data", {})

        # Try Google Calendar first
        writer = self._get_writer()
        if writer is not None:
            event_body = {
                "summary": data["title"],
                "start": {"dateTime": data["start_time"]},
                "end": {"dateTime": data["end_time"]} if data.get("end_time") else {},
                "location": data.get("location", ""),
                "description": data.get("description", ""),
            }
            if data.get("attendees"):
                event_body["attendees"] = [{"email": a} for a in data["attendees"]]

            calendar_id = data.get("calendar_id", "primary")
            result = writer.create_event(calendar_id, event_body)

            if result.success:
                # Also store locally for tracking
                local_id = f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.store.insert(
                    "events",
                    {
                        "id": local_id,
                        "source": "google_calendar",
                        "title": data["title"],
                        "start_time": data["start_time"],
                        "end_time": data.get("end_time"),
                        "location": data.get("location"),
                        "context": json.dumps({"google_event_id": result.event_id}),
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    },
                )
                return {
                    "success": True,
                    "event_id": local_id,
                    "google_event_id": result.event_id,
                    "html_link": result.data.get("htmlLink") if result.data else None,
                }

            logger.error("CalendarWriter.create_event failed: %s", result.error)
            return {"success": False, "error": result.error}

        # Fallback to local-only
        local_id = f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.store.insert(
            "events",
            {
                "id": local_id,
                "source": "time_os",
                "title": data["title"],
                "start_time": data["start_time"],
                "end_time": data.get("end_time"),
                "location": data.get("location"),
                "context": json.dumps(data.get("context", {})),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
        )
        return {"success": True, "event_id": local_id}

    def _update_event(self, action: dict) -> dict:
        event_id = action.get("event_id")
        data = action.get("data", {})

        # Check if this event has a Google Calendar counterpart
        writer = self._get_writer()
        if writer is not None and data.get("google_event_id"):
            calendar_id = data.get("calendar_id", "primary")
            google_event_id = data.pop("google_event_id")
            update_body = {}
            if "title" in data:
                update_body["summary"] = data["title"]
            if "start_time" in data:
                update_body["start"] = {"dateTime": data["start_time"]}
            if "end_time" in data:
                update_body["end"] = {"dateTime": data["end_time"]}
            if "location" in data:
                update_body["location"] = data["location"]

            if update_body:
                result = writer.update_event(calendar_id, google_event_id, update_body)
                if not result.success:
                    logger.error("CalendarWriter.update_event failed: %s", result.error)
                    return {"success": False, "error": result.error}

        # Always update local record
        data["updated_at"] = datetime.now().isoformat()
        self.store.update("events", event_id, data)
        return {"success": True, "event_id": event_id}

    def _delete_event(self, action: dict) -> dict:
        event_id = action.get("event_id")

        # Check for Google Calendar counterpart
        writer = self._get_writer()
        data = action.get("data", {})
        if writer is not None and data.get("google_event_id"):
            calendar_id = data.get("calendar_id", "primary")
            result = writer.delete_event(calendar_id, data["google_event_id"])
            if not result.success:
                logger.error("CalendarWriter.delete_event failed: %s", result.error)
                return {"success": False, "error": result.error}

        self.store.delete("events", event_id)
        return {"success": True, "event_id": event_id}

    def _reschedule_event(self, action: dict) -> dict:
        event_id = action.get("event_id")
        data = action.get("data", {})

        # Reschedule on Google Calendar if linked
        writer = self._get_writer()
        if writer is not None and data.get("google_event_id"):
            calendar_id = data.get("calendar_id", "primary")
            update_body = {
                "start": {"dateTime": data["start_time"]},
            }
            if data.get("end_time"):
                update_body["end"] = {"dateTime": data["end_time"]}

            result = writer.update_event(calendar_id, data["google_event_id"], update_body)
            if not result.success:
                logger.error("CalendarWriter.update_event (reschedule) failed: %s", result.error)
                return {"success": False, "error": result.error}

        self.store.update(
            "events",
            event_id,
            {
                "start_time": data["start_time"],
                "end_time": data.get("end_time"),
                "updated_at": datetime.now().isoformat(),
            },
        )
        return {"success": True, "event_id": event_id}
