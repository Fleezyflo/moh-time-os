"""
Time OS V5 — Calendar/Meet Detector

Detects signals from Calendar events (collected JSON).
"""

import logging
from datetime import datetime

from ..data_loader import get_data_loader
from ..database import Database
from ..models import Signal, SignalSource
from .base import SignalDetector

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class CalendarMeetDetector(SignalDetector):
    """
    Detects signals from Calendar events.

    Reads from out/calendar-next.json (collector output).

    Signal Types:
    - meeting_scheduled: Client meeting scheduled (neutral/positive)
    - meeting_cancelled: Meeting was cancelled
    """

    detector_id = "calendar_meet"
    detector_version = "5.0.0"
    signal_types = ["meeting_scheduled", "meeting_cancelled"]

    def __init__(self, db: Database):
        super().__init__(db)
        self.loader = get_data_loader()

    def detect(self) -> list[Signal]:
        """Run detection and return signals."""
        self.log_detection_start()
        self.load_existing_signals()

        signals = []
        signals.extend(self._detect_meetings())

        self.log_detection_end(len(signals))
        return signals

    def _detect_meetings(self) -> list[Signal]:
        """Detect meeting signals from calendar events."""
        signals = []
        events = self.loader.get_calendar_events()

        for event in events:
            event_id = event.get("id")
            if not event_id:
                continue

            status = event.get("status", "confirmed")
            summary = event.get("summary", "")

            # Skip internal/personal events (no attendees or single attendee)
            attendees = event.get("attendees", [])
            if len(attendees) < 2:
                continue

            # Determine signal type
            if status == "cancelled":
                signal_type = "meeting_cancelled"
                valence = -1
                magnitude = 0.3
            else:
                signal_type = "meeting_scheduled"
                valence = 0  # Neutral - just informational
                magnitude = 0.2

            # Skip if signal exists
            if self.signal_exists(signal_type, event_id):
                continue

            # Get event time
            start = event.get("start", {})
            start_time = start.get("dateTime") or start.get("date")

            signal = self.create_signal(
                signal_type=signal_type,
                valence=valence,
                magnitude=magnitude,
                entity_type="meeting",
                entity_id=event_id,
                source_type=SignalSource.CALENDAR,
                source_id=event_id,
                value={
                    "summary": summary,
                    "start": start_time,
                    "status": status,
                    "attendee_count": len(attendees),
                    "organizer": event.get("organizer", {}).get("email", ""),
                },
                occurred_at=self._parse_time(start_time),
                detection_confidence=1.0,
                attribution_confidence=0.6,  # May not map to specific client
            )

            signals.append(signal)
            self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} meeting signals")
        return signals

    def _parse_time(self, time_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        if not time_str:
            return datetime.now()
        try:
            if "T" in time_str:
                return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return datetime.fromisoformat(time_str)
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse time string '{time_str}': {e}")
            return datetime.now()
