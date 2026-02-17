"""
Notification Delivery Module.

Delivers queued notifications via configured channels.
Currently supports: Slack webhook.

Environment:
    SLACK_WEBHOOK_URL: Slack incoming webhook URL (required for delivery)

Usage:
    from lib.intelligence.delivery import deliver_pending
    result = deliver_pending(limit=50)
"""

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .notifications import (
    Notification,
    NotificationPriority,
    NotificationType,
    get_pending_notifications,
    mark_delivered,
)

logger = logging.getLogger(__name__)

# Default DB path
DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "moh_time_os.db"


@dataclass
class DeliveryResult:
    """Result of a delivery batch."""

    total: int = 0
    delivered: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "delivered": self.delivered,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": round(self.delivered / self.total * 100, 1) if self.total > 0 else 0,
            "errors": self.errors,
        }


def get_slack_webhook_url() -> str | None:
    """Get Slack webhook URL from environment."""
    return os.environ.get("SLACK_WEBHOOK_URL")


def format_slack_message(notification: Notification) -> dict:
    """
    Format notification as Slack message with rich attachment.

    Maps notification type to color and emoji:
    - CRITICAL_SIGNAL: red (danger)
    - ESCALATION: orange (warning)
    - SCORE_DROP: yellow
    - PATTERN_DETECTED: blue
    - PROPOSAL_GENERATED: green (good)
    """
    # Color mapping
    color_map = {
        NotificationType.CRITICAL_SIGNAL: "danger",  # red
        NotificationType.ESCALATION: "#FF8C00",  # dark orange
        NotificationType.SCORE_DROP: "warning",  # yellow
        NotificationType.PATTERN_DETECTED: "#2196F3",  # blue
        NotificationType.PROPOSAL_GENERATED: "good",  # green
    }

    # Priority prefix
    priority_prefix = {
        NotificationPriority.HIGH: "🔴 HIGH",
        NotificationPriority.MEDIUM: "🟡 MEDIUM",
        NotificationPriority.LOW: "🟢 LOW",
    }

    color = color_map.get(notification.type, "#808080")
    priority = priority_prefix.get(notification.priority, "")

    # Build fields
    fields = []
    if notification.entity_type and notification.entity_id:
        fields.append(
            {
                "title": "Entity",
                "value": f"{notification.entity_type}: {notification.entity_id}",
                "short": True,
            }
        )
    fields.append(
        {
            "title": "Priority",
            "value": priority,
            "short": True,
        }
    )

    # Build attachment
    attachment = {
        "color": color,
        "title": notification.title,
        "text": notification.body or "",
        "fields": fields,
        "footer": f"Moh Time OS | {notification.type.value}",
        "ts": int(datetime.fromisoformat(notification.created_at).timestamp()),
    }

    return {
        "attachments": [attachment],
    }


def deliver_to_slack(
    notification: Notification,
    webhook_url: str | None = None,
) -> tuple[bool, str | None]:
    """
    Deliver a single notification to Slack.

    Args:
        notification: The notification to deliver
        webhook_url: Slack webhook URL (defaults to SLACK_WEBHOOK_URL env)

    Returns:
        Tuple of (success, error_message)
    """
    url = webhook_url or get_slack_webhook_url()
    if not url:
        return False, "SLACK_WEBHOOK_URL not configured"

    message = format_slack_message(notification)

    try:
        data = json.dumps(message).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return True, None
            return False, f"HTTP {response.status}"

    except urllib.error.HTTPError as e:
        return False, f"HTTP error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, f"URL error: {e.reason}"
    except TimeoutError:
        return False, "Request timeout"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def deliver_pending(
    limit: int = 50,
    webhook_url: str | None = None,
    db_path: Path | None = None,
) -> DeliveryResult:
    """
    Deliver pending notifications.

    Args:
        limit: Maximum notifications to process
        webhook_url: Slack webhook URL (defaults to env)
        db_path: Database path (defaults to standard location)

    Returns:
        DeliveryResult with counts and errors
    """
    result = DeliveryResult()
    url = webhook_url or get_slack_webhook_url()

    if not url:
        logger.warning("SLACK_WEBHOOK_URL not configured - skipping delivery")
        result.skipped = limit
        result.errors.append("SLACK_WEBHOOK_URL not configured")
        return result

    notifications = get_pending_notifications(limit=limit, db_path=db_path)
    result.total = len(notifications)

    for notification in notifications:
        success, error = deliver_to_slack(notification, webhook_url=url)

        if success:
            mark_delivered(notification.id, db_path=db_path)
            result.delivered += 1
            logger.info(f"Delivered notification {notification.id}: {notification.title}")
        else:
            result.failed += 1
            result.errors.append(f"{notification.id}: {error}")
            logger.warning(f"Failed to deliver {notification.id}: {error}")

    return result


def get_delivery_stats(db_path: Path | None = None) -> dict:
    """
    Get delivery statistics.

    Returns queue and delivery status.
    """
    import sqlite3

    db = db_path or DEFAULT_DB

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        # Total in queue
        total = conn.execute("SELECT COUNT(*) as c FROM notification_queue").fetchone()["c"]

        # Pending (not delivered)
        pending = conn.execute(
            "SELECT COUNT(*) as c FROM notification_queue WHERE delivered_at IS NULL"
        ).fetchone()["c"]

        # Delivered
        delivered = conn.execute(
            "SELECT COUNT(*) as c FROM notification_queue WHERE delivered_at IS NOT NULL"
        ).fetchone()["c"]

        # By priority (pending only)
        by_priority = {}
        for row in conn.execute(
            """
            SELECT priority, COUNT(*) as c
            FROM notification_queue
            WHERE delivered_at IS NULL
            GROUP BY priority
        """
        ):
            by_priority[row["priority"]] = row["c"]

        # By type (pending only)
        by_type = {}
        for row in conn.execute(
            """
            SELECT type, COUNT(*) as c
            FROM notification_queue
            WHERE delivered_at IS NULL
            GROUP BY type
        """
        ):
            by_type[row["type"]] = row["c"]

        # Recent deliveries (last 24h)
        recent = conn.execute(
            """
            SELECT COUNT(*) as c
            FROM notification_queue
            WHERE delivered_at IS NOT NULL
            AND delivered_at > datetime('now', '-1 day')
        """
        ).fetchone()["c"]

        # Oldest pending
        oldest = conn.execute(
            """
            SELECT created_at
            FROM notification_queue
            WHERE delivered_at IS NULL
            ORDER BY created_at ASC
            LIMIT 1
        """
        ).fetchone()

        return {
            "total": total,
            "pending": pending,
            "delivered": delivered,
            "recent_24h": recent,
            "by_priority": by_priority,
            "by_type": by_type,
            "oldest_pending": oldest["created_at"] if oldest else None,
            "webhook_configured": get_slack_webhook_url() is not None,
        }
    finally:
        conn.close()
