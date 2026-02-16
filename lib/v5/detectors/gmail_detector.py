"""
Time OS V5 — Gmail Detector

Detects signals from Gmail messages.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from ..data_loader import get_data_loader
from ..database import Database
from ..models import Signal, SignalSource
from .base import SignalDetector

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# Urgent keywords
URGENT_KEYWORDS = [
    "urgent",
    "asap",
    "immediately",
    "critical",
    "deadline",
    "overdue",
    "past due",
    "final notice",
    "action required",
    "time sensitive",
    "priority",
    "escalate",
]

# Client domain patterns (external = potential client)
INTERNAL_DOMAINS = ["hrmny.co", "hrmny.ae"]


class GmailDetector(SignalDetector):
    """
    Detects signals from Gmail messages.

    Reads from out/gmail-full.json.

    Signal Types:
    - email_urgent: Email with urgent keywords from external sender
    - email_unanswered: Unread email from external sender > 2 days old
    - email_client_active: Recent client communication (positive)
    """

    detector_id = "gmail"
    detector_version = "5.0.0"
    signal_types = ["email_urgent", "email_unanswered", "email_client_active"]

    # Days threshold for unanswered
    UNANSWERED_DAYS = 2

    def __init__(self, db: Database):
        super().__init__(db)
        self.loader = get_data_loader()

    def detect(self) -> list[Signal]:
        """Run detection and return signals."""
        self.log_detection_start()
        self.load_existing_signals()

        signals = []
        signals.extend(self._detect_urgent())
        signals.extend(self._detect_unanswered())
        signals.extend(self._detect_client_active())

        self.log_detection_end(len(signals))
        return signals

    def _get_messages(self) -> list[dict[str, Any]]:
        """Get Gmail messages from data loader."""
        data = self.loader._load_json("gmail-full.json")
        if not data:
            return []
        return data.get("messages", [])

    def _is_external(self, email: str) -> bool:
        """Check if email is from external domain."""
        if not email:
            return False
        # Extract domain
        match = re.search(r"@([\w.-]+)", email.lower())
        if not match:
            return False
        domain = match.group(1)
        return domain not in INTERNAL_DOMAINS

    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date string."""
        if not date_str:
            return datetime.now()
        try:
            # Try common formats
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%S%z",
            ]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            logger.debug(f"Could not parse date string '{date_str}' with any known format")
            return datetime.now()
        except Exception as e:
            logger.debug(f"Unexpected error parsing date '{date_str}': {e}")
            return datetime.now()

    def _detect_urgent(self) -> list[Signal]:
        """Detect emails with urgent keywords from external senders."""
        signals = []
        messages = self._get_messages()

        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            sender = msg.get("from", "")
            if not self._is_external(sender):
                continue

            # Check subject and snippet for urgent keywords
            subject = (msg.get("subject") or "").lower()
            snippet = (msg.get("snippet") or "").lower()
            text = subject + " " + snippet

            urgent_matches = [kw for kw in URGENT_KEYWORDS if kw in text]
            if not urgent_matches:
                continue

            # Skip if signal exists
            if self.signal_exists("email_urgent", msg_id):
                continue

            signal = self.create_signal(
                signal_type="email_urgent",
                valence=-1,
                magnitude=0.7,
                entity_type="email",
                entity_id=msg_id,
                source_type=SignalSource.EMAIL,
                source_id=msg_id,
                source_excerpt=subject[:200],
                value={
                    "from": sender,
                    "subject": msg.get("subject"),
                    "keywords": urgent_matches,
                },
                occurred_at=self._parse_date(msg.get("date")),
                detection_confidence=0.8,
                attribution_confidence=0.6,
            )

            signals.append(signal)
            self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} urgent emails")
        return signals

    def _detect_unanswered(self) -> list[Signal]:
        """Detect unread emails from external senders older than threshold."""
        signals = []
        messages = self._get_messages()
        cutoff = datetime.now() - timedelta(days=self.UNANSWERED_DAYS)

        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            # Must be unread
            labels = msg.get("labels", [])
            if "UNREAD" not in labels:
                continue

            # Must be in inbox
            if "INBOX" not in labels:
                continue

            sender = msg.get("from", "")
            if not self._is_external(sender):
                continue

            # Check age
            msg_date = self._parse_date(msg.get("date"))
            if msg_date.replace(tzinfo=None) > cutoff:
                continue

            # Skip if signal exists
            if self.signal_exists("email_unanswered", msg_id):
                continue

            days_old = (datetime.now() - msg_date.replace(tzinfo=None)).days

            signal = self.create_signal(
                signal_type="email_unanswered",
                valence=-1,
                magnitude=min(0.3 + (days_old * 0.1), 0.8),
                entity_type="email",
                entity_id=msg_id,
                source_type=SignalSource.EMAIL,
                source_id=msg_id,
                source_excerpt=msg.get("subject", "")[:200],
                value={
                    "from": sender,
                    "subject": msg.get("subject"),
                    "days_old": days_old,
                },
                occurred_at=msg_date,
                detection_confidence=0.9,
                attribution_confidence=0.5,
            )

            signals.append(signal)
            self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} unanswered emails")
        return signals

    def _detect_client_active(self) -> list[Signal]:
        """Detect recent client communication (positive signal)."""
        signals = []
        messages = self._get_messages()

        # Only look at last 3 days for active communication
        cutoff = datetime.now() - timedelta(days=3)

        # Track senders we've already signaled
        signaled_senders = set()

        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            sender = msg.get("from", "")
            if not self._is_external(sender):
                continue

            # Extract email for dedup
            match = re.search(r"<([^>]+)>", sender)
            sender_email = match.group(1) if match else sender

            if sender_email in signaled_senders:
                continue

            # Check age - must be recent
            msg_date = self._parse_date(msg.get("date"))
            if msg_date.replace(tzinfo=None) < cutoff:
                continue

            # Skip if signal exists for this sender recently
            if self.signal_exists("email_client_active", sender_email):
                continue

            signaled_senders.add(sender_email)

            signal = self.create_signal(
                signal_type="email_client_active",
                valence=1,  # Positive - active communication
                magnitude=0.3,
                entity_type="email_thread",
                entity_id=sender_email,
                source_type=SignalSource.EMAIL,
                source_id=msg_id,
                value={
                    "from": sender,
                    "subject": msg.get("subject"),
                },
                occurred_at=msg_date,
                detection_confidence=0.9,
                attribution_confidence=0.5,
            )

            signals.append(signal)
            self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} active client signals")
        return signals
