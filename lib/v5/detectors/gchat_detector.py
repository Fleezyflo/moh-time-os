"""
Time OS V5 — Google Chat Detector

Detects signals from Google Chat data (collected JSON).
"""

import logging
from datetime import datetime

from ..data_loader import get_data_loader
from ..database import Database
from ..models import Signal, SignalSource
from .base import SignalDetector

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# Escalation keywords
ESCALATION_KEYWORDS = [
    "urgent",
    "asap",
    "escalate",
    "disappointed",
    "unacceptable",
    "frustrated",
    "concerned",
    "issue",
    "problem",
    "unhappy",
    "not happy",
    "delay",
    "overdue",
    "late",
    "waiting",
]

# Positive sentiment keywords
POSITIVE_KEYWORDS = [
    "thank",
    "thanks",
    "great",
    "excellent",
    "amazing",
    "perfect",
    "love",
    "awesome",
    "fantastic",
    "wonderful",
    "happy",
    "pleased",
    "appreciate",
    "well done",
    "good job",
]


class GoogleChatDetector(SignalDetector):
    """
    Detects signals from Google Chat messages.

    Reads from out/chat-full.json (collector output).

    Signal Types:
    - escalation_detected: Message contains escalation language
    - sentiment_negative: Message has negative sentiment
    - sentiment_positive: Message has positive sentiment (balancing)
    """

    detector_id = "gchat"
    detector_version = "5.0.0"
    signal_types = ["escalation_detected", "sentiment_negative", "sentiment_positive"]

    def __init__(self, db: Database):
        super().__init__(db)
        self.loader = get_data_loader()

    def detect(self) -> list[Signal]:
        """Run detection and return signals."""
        self.log_detection_start()
        self.load_existing_signals()

        signals = []
        signals.extend(self._detect_escalations())
        signals.extend(self._detect_sentiment())

        self.log_detection_end(len(signals))
        return signals

    def _detect_escalations(self) -> list[Signal]:
        """Detect escalation language in messages."""
        signals = []
        messages = self.loader.get_chat_messages()

        for msg in messages:
            msg_id = msg.get("name", msg.get("id", ""))
            if not msg_id:
                continue

            text = (msg.get("text") or "").lower()
            if not text:
                continue

            # Check for escalation keywords
            escalation_matches = [kw for kw in ESCALATION_KEYWORDS if kw in text]

            if len(escalation_matches) >= 2:  # Multiple escalation indicators
                # Skip if signal exists
                if self.signal_exists("escalation_detected", msg_id):
                    continue

                signal = self.create_signal(
                    signal_type="escalation_detected",
                    valence=-1,
                    magnitude=0.8,
                    entity_type="message",
                    entity_id=msg_id,
                    source_type=SignalSource.GCHAT,
                    source_id=msg_id,
                    source_excerpt=text[:200],
                    value={
                        "space": msg.get("space_display_name", msg.get("space_name", "")),
                        "sender": msg.get("sender", ""),
                        "keywords_matched": escalation_matches,
                    },
                    occurred_at=self._parse_time(msg.get("create_time")),
                    detection_confidence=0.75,
                    attribution_confidence=0.7,
                )

                signals.append(signal)
                self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} escalations")
        return signals

    def _detect_sentiment(self) -> list[Signal]:
        """Detect positive/negative sentiment in messages."""
        signals = []
        messages = self.loader.get_chat_messages()

        for msg in messages:
            msg_id = msg.get("name", msg.get("id", ""))
            if not msg_id:
                continue

            text = (msg.get("text") or "").lower()
            if not text or len(text) < 20:  # Skip very short messages
                continue

            # Count sentiment indicators
            positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
            negative_count = sum(1 for kw in ESCALATION_KEYWORDS if kw in text)

            # Positive sentiment (no escalation, has positive keywords)
            if positive_count >= 2 and negative_count == 0:
                if not self.signal_exists("sentiment_positive", msg_id):
                    signal = self.create_signal(
                        signal_type="sentiment_positive",
                        valence=1,
                        magnitude=0.5,
                        entity_type="message",
                        entity_id=msg_id,
                        source_type=SignalSource.GCHAT,
                        source_id=msg_id,
                        source_excerpt=text[:200],
                        value={
                            "space": msg.get("space_display_name", msg.get("space_name", "")),
                            "sender": msg.get("sender", ""),
                        },
                        occurred_at=self._parse_time(msg.get("create_time")),
                        detection_confidence=0.7,
                        attribution_confidence=0.7,
                    )
                    signals.append(signal)
                    self.log_signal(signal)

            # Negative sentiment (has negative keywords, not already escalation)
            elif negative_count == 1:  # Single negative indicator (escalations caught separately)
                if not self.signal_exists("sentiment_negative", msg_id):
                    signal = self.create_signal(
                        signal_type="sentiment_negative",
                        valence=-1,
                        magnitude=0.4,
                        entity_type="message",
                        entity_id=msg_id,
                        source_type=SignalSource.GCHAT,
                        source_id=msg_id,
                        source_excerpt=text[:200],
                        value={
                            "space": msg.get("space_display_name", msg.get("space_name", "")),
                            "sender": msg.get("sender", ""),
                        },
                        occurred_at=self._parse_time(msg.get("create_time")),
                        detection_confidence=0.6,
                        attribution_confidence=0.7,
                    )
                    signals.append(signal)
                    self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} sentiment signals")
        return signals

    def _parse_time(self, time_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        if not time_str:
            return datetime.now()
        try:
            # Handle various formats
            if "T" in time_str:
                return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return datetime.now()
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse time string '{time_str}': {e}")
            return datetime.now()
