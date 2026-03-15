"""
DigestEngine - Batches notifications into daily/weekly/hourly digests.

Handles queueing, grouping by category, and formatting notifications
for digest delivery instead of individual messages.

Receives a store (StateStore) via constructor.  All DB access goes
through store.query() for reads and store.insert() / store.update()
for writes.  Tables and indexes are owned by lib/schema.py, not here.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from lib import safe_sql

log = logging.getLogger(__name__)

# Severity ordering for sorting (higher index = higher priority)
SEVERITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class DigestEngine:
    """Manages notification digests for batched delivery.

    Tables (digest_queue, digest_history) and their indexes are defined
    in lib/schema.py and created by schema_engine during DB init.
    DigestEngine does not create or manage schema.

    All DB access goes through self.store:
    - store.query() for SELECTs
    - store.insert() for INSERTs (write-locked)
    - store.update() for UPDATEs (write-locked)
    """

    def __init__(self, store):
        """Initialize digest engine.

        Args:
            store: StateStore instance (or any object providing
                   .query(sql, params), .insert(table, data),
                   and .update(table, id, data)).
        """
        self.store = store
        # Track items that failed to queue so digest can report degradation
        self._dropped_count: int = 0
        self._dropped_high_severity: int = 0

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
            now = datetime.now(timezone.utc).isoformat()

            self.store.insert(
                "digest_queue",
                {
                    "id": f"{user_id}_{notification_id}_{bucket}_{now}",
                    "user_id": user_id,
                    "notification_id": notification_id,
                    "event_type": event_type,
                    "category": category,
                    "severity": severity,
                    "bucket": bucket,
                    "created_at": now,
                },
            )
            return True
        except (sqlite3.Error, ValueError, OSError) as e:
            # Track drops for degradation reporting in generated digests
            self._dropped_count += 1
            if severity in ("critical", "high"):
                self._dropped_high_severity += 1
                log.error(
                    "DIGEST DROP: Failed to queue %s-severity notification %s: %s",
                    severity,
                    notification_id,
                    e,
                )
            else:
                log.warning("Failed to queue notification %s: %s", notification_id, e)
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
            sql = safe_sql.select(
                "digest_queue",
                columns="id, notification_id, event_type, category, severity",
                where="user_id = ? AND bucket = ? AND processed = 0",
                order_by="severity DESC, created_at ASC",
            )
            rows = self.store.query(sql, [user_id, bucket])

            if not rows:
                return None

            # Group by category
            categories: dict[str, list[dict]] = {}
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
            for category in categories:
                categories[category].sort(
                    key=lambda x: SEVERITY_ORDER.get(x["severity"], 0), reverse=True
                )

            # Build summary
            summary = {}
            total_items = 0
            for category, items in categories.items():
                summary[category] = {"count": len(items)}
                total_items += len(items)

            # Include degradation info if any items were dropped
            result: dict = {
                "total": total_items,
                "categories": categories,
                "summary": summary,
                "bucket": bucket,
            }
            if self._dropped_count > 0:
                result["degraded"] = True
                result["dropped_count"] = self._dropped_count
                result["dropped_high_severity"] = self._dropped_high_severity
            return result
        except (sqlite3.Error, ValueError, OSError) as e:
            log.error("Failed to generate digest: %s", e)
            return None

    def mark_as_processed(self, user_id: str, notification_ids: list, bucket: str) -> bool:
        """
        Mark items as processed in the digest queue.

        Uses store.update() (write-locked) instead of raw SQL to ensure
        write serialization with concurrent queue_notification/insert calls.

        Args:
            user_id: User ID
            notification_ids: List of notification IDs to mark processed
            bucket: Bucket name

        Returns:
            True on success, False on failure
        """
        try:
            now = datetime.now(timezone.utc).isoformat()

            for notif_id in notification_ids:
                # Look up row IDs matching this notification in this bucket
                sql = safe_sql.select(
                    "digest_queue",
                    columns="id",
                    where="user_id = ? AND notification_id = ? AND bucket = ? AND processed = 0",
                )
                rows = self.store.query(sql, [user_id, notif_id, bucket])
                # Update each matching row through the write-locked path
                for row in rows:
                    self.store.update(
                        "digest_queue",
                        row["id"],
                        {"processed": 1, "processed_at": now},
                    )
            return True
        except (sqlite3.Error, ValueError, OSError) as e:
            log.error("Failed to mark as processed: %s", e)
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
            digest_id = str(uuid.uuid4())
            digest_json = json.dumps(digest) if digest else "{}"
            item_count = digest.get("total", 0) if digest else 0

            self.store.insert(
                "digest_history",
                {
                    "id": digest_id,
                    "user_id": user_id,
                    "bucket": bucket,
                    "digest_json": digest_json,
                    "item_count": item_count,
                    "sent_at": sent_time,
                },
            )
            return True
        except (sqlite3.Error, ValueError, OSError) as e:
            log.error("Failed to record digest sent: %s", e)
            return False

    def get_pending_count(self, user_id: str) -> dict:
        """
        Get count of pending items by bucket for a user.

        Args:
            user_id: User ID

        Returns:
            Dict mapping bucket -> count of pending items
        """
        sql = safe_sql.select(
            "digest_queue",
            columns="bucket, COUNT(*) as count",
            where="user_id = ? AND processed = 0",
            suffix="GROUP BY bucket",
        )
        rows = self.store.query(sql, [user_id])

        counts = {}
        for row in rows:
            counts[row["bucket"]] = row["count"]
        return counts

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

        # Surface degradation to the user — not just in logs
        if digest.get("degraded"):
            dropped = digest.get("dropped_count", 0)
            dropped_high = digest.get("dropped_high_severity", 0)
            lines.append(
                f"WARNING: {dropped} notification(s) could not be included in this digest."
            )
            if dropped_high > 0:
                lines.append(f"  {dropped_high} of these were high/critical severity.")
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
            ".degraded-warning { background: #fff3cd; border: 1px solid #ffc107; "
            "border-radius: 4px; padding: 12px; margin-bottom: 16px; color: #856404; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{bucket} Digest</h1>",
        ]

        # Surface degradation to the user in HTML digests
        if digest.get("degraded"):
            dropped = digest.get("dropped_count", 0)
            dropped_high = digest.get("dropped_high_severity", 0)
            warning_text = f"{dropped} notification(s) could not be included in this digest."
            if dropped_high > 0:
                warning_text += f" {dropped_high} of these were high/critical severity."
            html_parts.append(
                f'<div class="degraded-warning"><strong>Warning:</strong> {warning_text}</div>'
            )

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
