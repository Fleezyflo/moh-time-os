"""
DigestEngine - Batches notifications into daily/weekly/hourly digests.

Handles queueing, grouping by category, and formatting notifications
for digest delivery instead of individual messages.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Optional

from lib.store import get_connection

log = logging.getLogger(__name__)

# Severity ordering for sorting (higher index = higher priority)
SEVERITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class DigestEngine:
    """Manages notification digests for batched delivery."""

    def __init__(self):
        """Initialize digest engine with database access."""
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create digest_queue and digest_history tables if they don't exist."""
        with get_connection() as conn:
            # Create digest_queue table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS digest_queue (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    notification_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    processed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    processed_at TEXT
                )
                """
            )

            # Create digest_history table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS digest_history (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    digest_json TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    sent_at TEXT NOT NULL
                )
                """
            )

            # Create indexes for performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_digest_queue_user_bucket "
                "ON digest_queue(user_id, bucket, processed)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_digest_history_user_bucket "
                "ON digest_history(user_id, bucket)"
            )

    def queue_notification(
        self,
        user_id: str,
        notification_id: str,
        event_type: str,
        severity: str,
        bucket: str,
    ) -> bool:
        """
        Queue a notification for digest delivery.

        Args:
            user_id: User to deliver digest to
            notification_id: Unique notification ID
            event_type: Type of event (proposal, issue, etc.)
            severity: Severity level (low, medium, high, critical)
            bucket: Delivery bucket (hourly, daily, weekly)

        Returns:
            True on success, False on failure
        """
        try:
            category = self._categorize_event(event_type)
            now = datetime.now().isoformat()

            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO digest_queue
                    (id, user_id, notification_id, event_type, category, severity, bucket, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{user_id}_{notification_id}_{bucket}_{now}",
                        user_id,
                        notification_id,
                        event_type,
                        category,
                        severity,
                        bucket,
                        now,
                    ),
                )
            return True
        except (sqlite3.Error, ValueError, OSError) as e:
            log.error(f"Failed to queue notification: {e}")
            return False

    def _categorize_event(self, event_type: str) -> str:
        """
        Map event type to category.

        Args:
            event_type: The event type string

        Returns:
            Category name (proposals, issues, watchers, patterns, other)
        """
        event_type_lower = event_type.lower()

        if event_type_lower in ("proposal", "proposal_update"):
            return "proposals"
        elif event_type_lower == "issue":
            return "issues"
        elif event_type_lower == "watcher":
            return "watchers"
        elif event_type_lower == "pattern":
            return "patterns"
        else:
            return "other"

    def generate_digest(self, user_id: str, bucket: str) -> dict | None:
        """
        Generate a digest for a user and bucket.

        Args:
            user_id: User to generate digest for
            bucket: Bucket (hourly, daily, weekly)

        Returns:
            Digest dict with total, categories, summary, bucket or None if no items
        """
        try:
            with get_connection() as conn:
                # Get all pending items for this user+bucket
                rows = conn.execute(
                    """
                    SELECT id, notification_id, event_type, category, severity
                    FROM digest_queue
                    WHERE user_id = ? AND bucket = ? AND processed = 0
                    ORDER BY severity DESC, created_at ASC
                    """,
                    (user_id, bucket),
                ).fetchall()

            if not rows:
                return None

            # Group by category
            categories = {}
            for row in rows:
                category = row["category"]
                if category not in categories:
                    categories[category] = []

                categories[category].append(
                    {
                        "id": row["id"],
                        "notification_id": row["notification_id"],
                        "event_type": row["event_type"],
                        "severity": row["severity"],
                    }
                )

            # Sort items within each category by severity
            severity_values = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            for category in categories:
                categories[category].sort(
                    key=lambda x: severity_values.get(x["severity"], 0), reverse=True
                )

            # Build summary
            summary = {}
            total_items = 0
            for category, items in categories.items():
                summary[category] = {"count": len(items)}
                total_items += len(items)

            return {
                "total": total_items,
                "categories": categories,
                "summary": summary,
                "bucket": bucket,
            }
        except (sqlite3.Error, ValueError, OSError) as e:
            log.error(f"Failed to generate digest: {e}")
            return None

    def mark_as_processed(self, user_id: str, notification_ids: list, bucket: str) -> bool:
        """
        Mark items as processed in the digest queue.

        Args:
            user_id: User ID
            notification_ids: List of notification IDs to mark processed
            bucket: Bucket name

        Returns:
            True on success, False on failure
        """
        try:
            now = datetime.now().isoformat()

            with get_connection() as conn:
                for notif_id in notification_ids:
                    conn.execute(
                        """
                        UPDATE digest_queue
                        SET processed = 1, processed_at = ?
                        WHERE user_id = ? AND notification_id = ? AND bucket = ?
                        """,
                        (now, user_id, notif_id, bucket),
                    )
            return True
        except (sqlite3.Error, ValueError, OSError) as e:
            log.error(f"Failed to mark as processed: {e}")
            return False

    def record_digest_sent(self, user_id: str, bucket: str, digest: dict, sent_time: str) -> bool:
        """
        Record digest delivery in history.

        Args:
            user_id: User ID
            bucket: Bucket name
            digest: Digest data
            sent_time: When digest was sent (ISO format)

        Returns:
            True on success, False on failure
        """
        try:
            import uuid

            digest_id = str(uuid.uuid4())
            digest_json = json.dumps(digest) if digest else "{}"
            item_count = digest.get("total", 0) if digest else 0

            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO digest_history
                    (id, user_id, bucket, digest_json, item_count, sent_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (digest_id, user_id, bucket, digest_json, item_count, sent_time),
                )
            return True
        except (sqlite3.Error, ValueError, OSError) as e:
            log.error(f"Failed to record digest sent: {e}")
            return False

    def get_pending_count(self, user_id: str) -> dict:
        """
        Get count of pending items by bucket for a user.

        Args:
            user_id: User ID

        Returns:
            Dict mapping bucket -> count of pending items
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT bucket, COUNT(*) as count
                    FROM digest_queue
                    WHERE user_id = ? AND processed = 0
                    GROUP BY bucket
                    """,
                    (user_id,),
                ).fetchall()

            counts = {}
            for row in rows:
                counts[row["bucket"]] = row["count"]
            return counts
        except (sqlite3.Error, ValueError, OSError):
            raise  # was silently swallowed

    def format_plaintext(self, digest: dict | None) -> str:
        """
        Format digest as plaintext.

        Args:
            digest: Digest dict or None

        Returns:
            Plaintext representation of digest
        """
        if not digest:
            return "No notifications"

        lines = []
        bucket = digest.get("bucket", "").upper()
        lines.append(f"{bucket} DIGEST")
        lines.append("=" * 50)
        lines.append("")

        categories = digest.get("categories", {})
        if not categories:
            lines.append("No notifications")
        else:
            for category, items in categories.items():
                lines.append(f"{category.upper()}: {len(items)} items")
                for item in items:
                    severity = item.get("severity", "unknown").upper()
                    event_type = item.get("event_type", "unknown")
                    lines.append(f"  [{severity}] {event_type}")
                lines.append("")

        return "\n".join(lines)

    def format_html(self, digest: dict | None) -> str:
        """
        Format digest as HTML.

        Args:
            digest: Digest dict or None

        Returns:
            HTML representation of digest
        """
        if not digest:
            return (
                "<html><head><title>Notification Digest</title></head>"
                "<body><p>No notifications</p></body></html>"
            )

        bucket = digest.get("bucket", "unknown").capitalize()
        categories = digest.get("categories", {})

        html_parts = [
            "<html>",
            "<head>",
            f"<title>{bucket} Digest</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".category { margin: 20px 0; }",
            ".category h2 { color: #333; border-bottom: 2px solid #007bff; }",
            ".item { margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 4px; }",
            ".severity { font-weight: bold; margin-right: 10px; }",
            ".critical { color: #dc3545; }",
            ".high { color: #ff6c00; }",
            ".medium { color: #ffc107; }",
            ".low { color: #28a745; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{bucket} Digest</h1>",
        ]

        if not categories:
            html_parts.append("<p>No notifications</p>")
        else:
            for category, items in categories.items():
                html_parts.append('<div class="category">')
                html_parts.append(f"<h2>{category.capitalize()}</h2>")
                for item in items:
                    severity = item.get("severity", "unknown").lower()
                    event_type = item.get("event_type", "unknown")
                    html_parts.append('<div class="item">')
                    html_parts.append(
                        f'<span class="severity {severity}">{severity.upper()}</span>'
                    )
                    html_parts.append(f"<span>{event_type}</span>")
                    html_parts.append("</div>")
                html_parts.append("</div>")

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)
