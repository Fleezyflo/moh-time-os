"""
Notification Intelligence — MOH TIME OS

Smart notification routing: channel selection, urgency-aware timing,
batching, and notification fatigue management.

Brief 21 (NI), Task NI-1.1

Decides: what to notify about, when, through which channel, and
whether to batch or send immediately.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Channel priority (higher = more interruptive)
CHANNEL_PRIORITY = {
    "sms": 5,
    "push": 4,
    "email_urgent": 3,
    "email": 2,
    "digest": 1,
    "silent": 0,
}

# UAE business hours (Sunday-Thursday, 9 AM - 6 PM GST)
UAE_WORK_DAYS = {6, 0, 1, 2, 3}  # Sun=6, Mon=0, Tue=1, Wed=2, Thu=3
UAE_WORK_START = 9
UAE_WORK_END = 18

# Fatigue thresholds
MAX_NOTIFICATIONS_PER_HOUR = 5
MAX_NOTIFICATIONS_PER_DAY = 20
COOLDOWN_MINUTES_AFTER_BURST = 30


@dataclass
class NotificationDecision:
    """Decision about how to deliver a notification."""

    entity_type: str
    entity_id: str
    signal_id: str
    urgency: str  # critical | high | normal | low
    channel: str  # sms | push | email_urgent | email | digest | silent
    should_send_now: bool = True
    batch_with: str | None = None  # batch group key
    reason: str = ""
    suppress_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "signal_id": self.signal_id,
            "urgency": self.urgency,
            "channel": self.channel,
            "should_send_now": self.should_send_now,
            "batch_with": self.batch_with,
            "reason": self.reason,
            "suppress_reason": self.suppress_reason,
        }


@dataclass
class NotificationBatch:
    """A group of notifications to deliver together."""

    batch_key: str
    channel: str
    notifications: list[NotificationDecision] = field(default_factory=list)
    scheduled_for: str | None = None

    def to_dict(self) -> dict:
        return {
            "batch_key": self.batch_key,
            "channel": self.channel,
            "count": len(self.notifications),
            "notifications": [n.to_dict() for n in self.notifications],
            "scheduled_for": self.scheduled_for,
        }


@dataclass
class FatigueState:
    """Tracks notification fatigue."""

    notifications_last_hour: int = 0
    notifications_today: int = 0
    last_notification_at: str | None = None
    is_fatigued: bool = False
    cooldown_until: str | None = None

    def to_dict(self) -> dict:
        return {
            "notifications_last_hour": self.notifications_last_hour,
            "notifications_today": self.notifications_today,
            "last_notification_at": self.last_notification_at,
            "is_fatigued": self.is_fatigued,
            "cooldown_until": self.cooldown_until,
        }


def is_work_hours(dt: datetime | None = None) -> bool:
    """Check if current time is within UAE work hours."""
    dt = dt or datetime.now()
    weekday = dt.weekday()
    hour = dt.hour
    return weekday in UAE_WORK_DAYS and UAE_WORK_START <= hour < UAE_WORK_END


def select_channel(urgency: str, is_work_time: bool) -> str:
    """Select appropriate notification channel based on urgency and timing."""
    if urgency == "critical":
        return "push" if is_work_time else "sms"
    if urgency == "high":
        return "email_urgent" if is_work_time else "push"
    if urgency == "normal":
        return "email" if is_work_time else "digest"
    return "digest"


class NotificationIntelligence:
    """Smart notification routing and fatigue management."""

    def __init__(self) -> None:
        self._sent_count_hour: int = 0
        self._sent_count_day: int = 0
        self._last_sent: datetime | None = None
        self._cooldown_until: datetime | None = None

    def decide(
        self,
        entity_type: str,
        entity_id: str,
        signal_id: str,
        urgency: str = "normal",
        is_suppressed: bool = False,
        current_time: datetime | None = None,
    ) -> NotificationDecision:
        """Decide how to handle a notification."""
        now = current_time or datetime.now()
        work_time = is_work_hours(now)
        channel = select_channel(urgency, work_time)

        # Check suppression
        if is_suppressed:
            return NotificationDecision(
                entity_type=entity_type,
                entity_id=entity_id,
                signal_id=signal_id,
                urgency=urgency,
                channel="silent",
                should_send_now=False,
                suppress_reason="signal is suppressed",
                reason="suppressed",
            )

        # Check fatigue (except critical)
        if urgency != "critical" and self._is_fatigued(now):
            return NotificationDecision(
                entity_type=entity_type,
                entity_id=entity_id,
                signal_id=signal_id,
                urgency=urgency,
                channel="digest",
                should_send_now=False,
                batch_with="fatigue_batch",
                reason="deferred due to notification fatigue",
            )

        # Outside work hours: batch non-urgent
        if not work_time and urgency in ("normal", "low"):
            return NotificationDecision(
                entity_type=entity_type,
                entity_id=entity_id,
                signal_id=signal_id,
                urgency=urgency,
                channel="digest",
                should_send_now=False,
                batch_with="morning_digest",
                reason="batched for morning digest (outside work hours)",
            )

        # Record send
        self._record_send(now)

        return NotificationDecision(
            entity_type=entity_type,
            entity_id=entity_id,
            signal_id=signal_id,
            urgency=urgency,
            channel=channel,
            should_send_now=True,
            reason=f"sent via {channel}",
        )

    def batch_notifications(
        self,
        decisions: list[NotificationDecision],
    ) -> list[NotificationBatch]:
        """Group deferred notifications into batches."""
        batches: dict[str, NotificationBatch] = {}

        for d in decisions:
            if d.batch_with:
                key = d.batch_with
                if key not in batches:
                    batches[key] = NotificationBatch(
                        batch_key=key,
                        channel=d.channel,
                    )
                batches[key].notifications.append(d)

        return list(batches.values())

    def get_fatigue_state(
        self,
        current_time: datetime | None = None,
    ) -> FatigueState:
        """Get current notification fatigue state."""
        now = current_time or datetime.now()
        return FatigueState(
            notifications_last_hour=self._sent_count_hour,
            notifications_today=self._sent_count_day,
            last_notification_at=self._last_sent.isoformat() if self._last_sent else None,
            is_fatigued=self._is_fatigued(now),
            cooldown_until=self._cooldown_until.isoformat() if self._cooldown_until else None,
        )

    def reset_daily_counts(self) -> None:
        """Reset daily counters (call at start of day)."""
        self._sent_count_day = 0
        self._sent_count_hour = 0
        self._cooldown_until = None

    def _is_fatigued(self, now: datetime) -> bool:
        """Check if we're in fatigue state."""
        if self._cooldown_until and now < self._cooldown_until:
            return True
        if self._sent_count_hour >= MAX_NOTIFICATIONS_PER_HOUR:
            self._cooldown_until = now + timedelta(minutes=COOLDOWN_MINUTES_AFTER_BURST)
            return True
        if self._sent_count_day >= MAX_NOTIFICATIONS_PER_DAY:
            return True
        return False

    def _record_send(self, now: datetime) -> None:
        """Record that a notification was sent."""
        # Reset hourly counter if more than an hour since last send
        if self._last_sent and (now - self._last_sent).total_seconds() > 3600:
            self._sent_count_hour = 0
        self._sent_count_hour += 1
        self._sent_count_day += 1
        self._last_sent = now
