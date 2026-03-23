"""
Notification Hooks for Intelligence Layer.

Creates notification records when significant events occur.
Data-only — delivery mechanism is external.

Notification types:
- CRITICAL_SIGNAL: A new critical-severity signal detected
- ESCALATION: A signal escalated in severity
- SCORE_DROP: Portfolio or entity score dropped significantly
- PATTERN_DETECTED: New structural pattern detected
- PROPOSAL_GENERATED: New high-priority proposal created
"""

import logging
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from lib.paths import db_path as get_db_path_from_lib

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    CRITICAL_SIGNAL = "critical_signal"
    ESCALATION = "escalation"
    SCORE_DROP = "score_drop"
    PATTERN_DETECTED = "pattern_detected"
    PROPOSAL_GENERATED = "proposal_generated"


class NotificationPriority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Notification:
    """A notification record."""

    id: str | None
    type: NotificationType
    priority: NotificationPriority
    title: str
    body: str
    entity_type: str | None
    entity_id: str | None
    data: dict
    created_at: str
    delivered_at: str | None = None

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "type": self.type.value,
            "priority": self.priority.value,
        }


def _get_db_path(db_path: Path | None = None) -> Path:
    """Get database path, resolving at call time to respect env overrides."""
    if db_path:
        return Path(db_path)
    return get_db_path_from_lib()


def ensure_notification_table(db_path: Path | None = None) -> None:
    """Ensure notification_queue table exists.

    Table definition lives in lib/schema.py (single source of truth).
    schema_engine.converge() creates it at startup; this is a defensive
    fallback for standalone usage.
    """
    from lib.schema import TABLES
    from lib.schema_engine import _build_create_sql

    db = _get_db_path(db_path)

    conn = sqlite3.connect(str(db))
    try:
        conn.execute(_build_create_sql("notification_queue", TABLES["notification_queue"]))
        conn.commit()
    finally:
        conn.close()


def queue_notification(notification: Notification, db_path: Path | None = None) -> str:
    """
    Add a notification to the queue.

    Returns the notification ID.
    """
    import json
    import uuid

    db = _get_db_path(db_path)
    ensure_notification_table(db_path)

    notification_id = notification.id or str(uuid.uuid4())

    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO notification_queue (
                notification_id, type, priority, title, body,
                entity_type, entity_id, data_json, created_at, delivered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                notification_id,
                notification.type.value,
                notification.priority.value,
                notification.title,
                notification.body,
                notification.entity_type,
                notification.entity_id,
                json.dumps(notification.data),
                notification.created_at,
                notification.delivered_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return notification_id


def get_pending_notifications(limit: int = 50, db_path: Path | None = None) -> list[Notification]:
    """
    Get notifications that haven't been delivered yet.
    """
    import json

    db = _get_db_path(db_path)
    ensure_notification_table(db_path)

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT * FROM notification_queue
            WHERE delivered_at IS NULL
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END,
                created_at ASC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()

        notifications = []
        for row in rows:
            notifications.append(
                Notification(
                    id=row["notification_id"],
                    type=NotificationType(row["type"]),
                    priority=NotificationPriority(row["priority"]),
                    title=row["title"],
                    body=row["body"],
                    entity_type=row["entity_type"],
                    entity_id=row["entity_id"],
                    data=json.loads(row["data_json"] or "{}"),
                    created_at=row["created_at"],
                    delivered_at=row["delivered_at"],
                )
            )

        return notifications
    finally:
        conn.close()


def mark_delivered(notification_id: str, db_path: Path | None = None) -> None:
    """Mark a notification as delivered."""
    db = _get_db_path(db_path)

    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            """
            UPDATE notification_queue
            SET delivered_at = ?
            WHERE notification_id = ?
        """,
            (datetime.now(timezone.utc).isoformat(), notification_id),
        )
        conn.commit()
    finally:
        conn.close()


# =============================================================================
# NOTIFICATION GENERATORS (Hooks)
# =============================================================================


def notify_critical_signal(signal: dict, db_path: Path | None = None) -> str:
    """Create notification for a critical signal."""
    notification = Notification(
        id=f"sig_{signal.get('signal_id', '')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        type=NotificationType.CRITICAL_SIGNAL,
        priority=NotificationPriority.HIGH,
        title=f"🚨 Critical: {signal.get('name', 'Unknown signal')}",
        body=signal.get("evidence", ""),
        entity_type=signal.get("entity_type"),
        entity_id=signal.get("entity_id"),
        data=signal,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return queue_notification(notification, db_path)


def notify_escalation(signal: dict, from_severity: str, db_path: Path | None = None) -> str:
    """Create notification for a signal escalation."""
    notification = Notification(
        id=f"esc_{signal.get('signal_id', '')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        type=NotificationType.ESCALATION,
        priority=NotificationPriority.HIGH,
        title=f"⬆️ Escalated: {signal.get('name', 'Unknown')} ({from_severity} → {signal.get('severity')})",
        body=signal.get("evidence", ""),
        entity_type=signal.get("entity_type"),
        entity_id=signal.get("entity_id"),
        data={**signal, "escalated_from": from_severity},
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return queue_notification(notification, db_path)


def notify_score_drop(
    entity_type: str,
    entity_id: str,
    entity_name: str,
    old_score: float,
    new_score: float,
    db_path: Path | None = None,
) -> str:
    """Create notification for a significant score drop."""
    delta = new_score - old_score
    notification = Notification(
        id=f"score_{entity_type}_{entity_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        type=NotificationType.SCORE_DROP,
        priority=NotificationPriority.MEDIUM if delta > -20 else NotificationPriority.HIGH,
        title=f"📉 Score Drop: {entity_name} ({old_score:.0f} → {new_score:.0f})",
        body=f"{entity_type.title()} score dropped by {abs(delta):.0f} points",
        entity_type=entity_type,
        entity_id=entity_id,
        data={"old_score": old_score, "new_score": new_score, "delta": delta},
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return queue_notification(notification, db_path)


def notify_pattern_detected(pattern: dict, db_path: Path | None = None) -> str:
    """Create notification for a new structural pattern."""
    severity = pattern.get("severity", "informational")
    priority = (
        NotificationPriority.HIGH
        if severity == "structural"
        else NotificationPriority.MEDIUM
        if severity == "operational"
        else NotificationPriority.LOW
    )

    notification = Notification(
        id=f"pat_{pattern.get('pattern_id', '')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        type=NotificationType.PATTERN_DETECTED,
        priority=priority,
        title=f"🔺 Pattern: {pattern.get('name', 'Unknown')}",
        body=pattern.get("description", ""),
        entity_type="portfolio",
        entity_id=None,
        data=pattern,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return queue_notification(notification, db_path)


def notify_proposal(proposal: dict, db_path: Path | None = None) -> str:
    """Create notification for a high-priority proposal."""
    urgency = proposal.get("urgency", "monitor")
    priority = (
        NotificationPriority.HIGH
        if urgency == "immediate"
        else NotificationPriority.MEDIUM
        if urgency == "this_week"
        else NotificationPriority.LOW
    )

    entity = proposal.get("entity", {})
    notification = Notification(
        id=f"prop_{proposal.get('id', '')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        type=NotificationType.PROPOSAL_GENERATED,
        priority=priority,
        title=f"💡 {proposal.get('headline', 'New proposal')}",
        body=proposal.get("summary", ""),
        entity_type=entity.get("type"),
        entity_id=entity.get("id"),
        data=proposal,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return queue_notification(notification, db_path)


# =============================================================================
# HOOK RUNNER
# =============================================================================


def process_intelligence_for_notifications(
    intel_data: dict, changes: dict, db_path: Path | None = None
) -> list[str]:
    """
    Process intelligence data and changes to generate notifications.

    Returns list of notification IDs created.
    Logs warnings when expected data structures are missing so that
    silent signal/pattern/proposal drops are visible in logs.
    """
    notification_ids = []

    # Critical signals — warn if expected structure is absent
    signals = intel_data.get("signals")
    if signals is None:
        logger.warning(
            "intel_data missing 'signals' key -- no signal notifications will be created"
        )
    elif not isinstance(signals, dict):
        logger.warning(
            "intel_data['signals'] is %s, expected dict -- cannot extract by_severity",
            type(signals).__name__,
        )
    else:
        by_severity = signals.get("by_severity")
        if by_severity is None:
            logger.warning(
                "intel_data['signals'] missing 'by_severity' key "
                "-- critical signals will not be notified"
            )
        else:
            for signal in by_severity.get("critical", []):
                try:
                    nid = notify_critical_signal(signal, db_path)
                    notification_ids.append(nid)
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.warning("Failed to create signal notification: %s", e)

    # Structural patterns
    patterns = intel_data.get("patterns")
    if patterns is None:
        logger.warning(
            "intel_data missing 'patterns' key -- no pattern notifications will be created"
        )
    elif not isinstance(patterns, dict):
        logger.warning(
            "intel_data['patterns'] is %s, expected dict",
            type(patterns).__name__,
        )
    else:
        for pattern in patterns.get("structural", []):
            try:
                nid = notify_pattern_detected(pattern, db_path)
                notification_ids.append(nid)
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.warning("Failed to create pattern notification: %s", e)

    # Immediate proposals
    proposals = intel_data.get("proposals")
    if proposals is None:
        logger.warning(
            "intel_data missing 'proposals' key -- no proposal notifications will be created"
        )
    elif not isinstance(proposals, dict):
        logger.warning(
            "intel_data['proposals'] is %s, expected dict",
            type(proposals).__name__,
        )
    else:
        by_urgency = proposals.get("by_urgency")
        if by_urgency is None:
            logger.warning(
                "intel_data['proposals'] missing 'by_urgency' key "
                "-- immediate proposals will not be notified"
            )
        else:
            for proposal in by_urgency.get("immediate", []):
                try:
                    nid = notify_proposal(proposal, db_path)
                    notification_ids.append(nid)
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.warning("Failed to create proposal notification: %s", e)

    return notification_ids
