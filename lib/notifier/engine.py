"""
NotificationEngine - Direct delivery to user without AI.

Processes pending notifications and delivers via channels.
CRITICAL: Does NOT go through AI. Direct API calls only.
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationEngine:
    """
    Processes pending notifications and delivers via channels.
    CRITICAL: Does NOT go through AI. Direct API calls only.

    Integrates:
    - DigestEngine: batches non-urgent notifications into digests
    - NotificationIntelligence: gates sends with fatigue/timing/channel logic
    - SignalSuppression: filters dismissed signals before notifying
    """

    def __init__(self, store, config: dict = None):
        """
        Args:
            store: StateStore instance
            config: From config/governance.yaml notification settings
        """
        self.store = store
        self.config = config or {}
        self._load_channels()
        self._init_intelligence()

    def _init_intelligence(self):
        """Initialize notification intelligence and digest subsystems."""
        self._notification_intel = None
        self._digest_engine = None

        try:
            from lib.intelligence.notification_intelligence import NotificationIntelligence

            self._notification_intel = NotificationIntelligence()
            logger.info("NotificationEngine: notification intelligence enabled")
        except (ImportError, ValueError, OSError) as e:
            logger.error(f"NotificationEngine: notification intelligence init failed: {e}")

        try:
            from lib.notifier.digest import DigestEngine

            self._digest_engine = DigestEngine()
            logger.info("NotificationEngine: digest engine enabled")
        except (ImportError, sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"NotificationEngine: digest engine init failed: {e}")

    def _load_channels(self):
        """Load configured notification channels."""
        self.channels = {}
        channel_config = self.config.get("channels", {})

        # Google Chat webhook — default notification channel
        gchat_url = os.environ.get("MOH_GCHAT_WEBHOOK_URL") or channel_config.get(
            "google_chat", {}
        ).get("webhook_url")

        if gchat_url:
            from lib.notifier.channels.google_chat import GoogleChatChannel

            dry_run = channel_config.get("google_chat", {}).get("dry_run", False)
            self.channels["google_chat"] = GoogleChatChannel(webhook_url=gchat_url, dry_run=dry_run)

        # Email channel — for digest and email_urgent delivery
        email_config = channel_config.get("email", {})
        email_enabled = email_config.get("enabled", False) or os.environ.get("GMAIL_SA_FILE")
        if email_enabled:
            try:
                from lib.notifier.channels.email import EmailChannel

                self.channels["email"] = EmailChannel(
                    credentials_path=email_config.get("credentials_path"),
                    delegated_user=email_config.get("delegated_user"),
                    default_recipient=email_config.get("default_recipient"),
                    dry_run=email_config.get("dry_run", False),
                )
                self.channels["email_urgent"] = self.channels["email"]
                logger.info("NotificationEngine: email channel enabled")
            except (ImportError, ValueError, OSError) as e:
                logger.error("NotificationEngine: email channel init failed: %s", e)

    async def process_pending(self) -> list[dict]:
        """
        Process all unsent notifications.

        Returns:
            List of {id, channel, status, error?}

        Implementation:
            1. SELECT * FROM notifications WHERE sent_at IS NULL
            2. For each, check rate limits (max 3 critical/day)
            3. Route to appropriate channel based on priority
            4. Call channel handler
            5. UPDATE notifications SET sent_at = NOW()
        """
        results = []

        # Get pending notifications
        pending = self.store.query("""
            SELECT id, type, priority, title, body, action_url, action_data, channels, created_at
            FROM notifications
            WHERE sent_at IS NULL
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'normal' THEN 3
                    ELSE 4
                END,
                created_at ASC
        """)

        for row in pending:
            notif_id = row["id"]
            priority = row["priority"]
            title = row["title"]
            body = row["body"]
            channels_json = row["channels"]

            # Check rate limit
            if not self._check_rate_limit(priority):
                results.append(
                    {
                        "id": notif_id,
                        "status": "rate_limited",
                        "error": f"Rate limit exceeded for {priority} priority",
                    }
                )
                continue

            # Check quiet hours for non-critical
            if priority != "critical" and self._is_quiet_hours():
                results.append(
                    {
                        "id": notif_id,
                        "status": "deferred",
                        "error": "Quiet hours - deferred",
                    }
                )
                continue

            # Parse channels or use default
            if channels_json:
                try:
                    target_channels = json.loads(channels_json)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid channels JSON for notification {notif_id}: {e}")
                    results.append(
                        {
                            "id": notif_id,
                            "status": "error",
                            "error": "No notification channel configured",
                        }
                    )
                    continue
            else:
                results.append(
                    {
                        "id": notif_id,
                        "status": "error",
                        "error": "No notification channel configured",
                    }
                )
                continue

            # Build message
            message = f"**{title}**"
            if body:
                message += f"\n\n{body}"

            # Send via each channel
            for channel_name in target_channels:
                if channel_name not in self.channels:
                    results.append(
                        {
                            "id": notif_id,
                            "channel": channel_name,
                            "status": "error",
                            "error": f"Channel {channel_name} not configured",
                        }
                    )
                    continue

                try:
                    channel = self.channels[channel_name]
                    result = await channel.send(message, priority=priority)

                    if result.get("success"):
                        # Mark as sent
                        self.store.update(
                            "notifications",
                            notif_id,
                            {
                                "sent_at": datetime.now().isoformat(),
                                "delivery_channel": channel_name,
                                "delivery_id": result.get("message_id"),
                            },
                        )

                        results.append(
                            {
                                "id": notif_id,
                                "channel": channel_name,
                                "status": "sent",
                                "message_id": result.get("message_id"),
                            }
                        )
                    else:
                        results.append(
                            {
                                "id": notif_id,
                                "channel": channel_name,
                                "status": "error",
                                "error": result.get("error", "Unknown error"),
                            }
                        )

                except (sqlite3.Error, ValueError, OSError) as e:
                    results.append(
                        {
                            "id": notif_id,
                            "channel": channel_name,
                            "status": "error",
                            "error": str(e),
                        }
                    )

        return results

    def process_pending_sync(self) -> list[dict]:
        """
        Synchronous version of process_pending using send_sync.
        Use this when asyncio is not available or for simpler integration.
        """
        results = []

        pending = self.store.query("""
            SELECT id, type, priority, title, body, action_url, action_data, channels, created_at
            FROM notifications
            WHERE sent_at IS NULL
            ORDER BY
                CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
                created_at ASC
            LIMIT 20
        """)

        # Collect deferred decisions for digest batching
        deferred_decisions = []

        for row in pending:
            notif_id = row["id"]
            priority = row["priority"]
            title = row["title"]
            body = row["body"]
            channels_json = row["channels"]

            # --- Intelligence gating: let NotificationIntelligence decide ---
            if self._notification_intel is not None:
                try:
                    action_data = row.get("action_data", "")
                    signal_id = ""
                    entity_type = ""
                    entity_id = ""
                    if action_data:
                        try:
                            ad = json.loads(action_data)
                            signal_id = ad.get("signal_id", "")
                            entity_type = ad.get("entity_type", "")
                            entity_id = ad.get("entity_id", "")
                        except (json.JSONDecodeError, TypeError):
                            pass

                    decision = self._notification_intel.decide(
                        entity_type=entity_type or "system",
                        entity_id=entity_id or notif_id,
                        signal_id=signal_id or notif_id,
                        urgency=priority,
                    )

                    if not decision.should_send_now:
                        deferred_decisions.append(decision)
                        results.append(
                            {
                                "id": notif_id,
                                "status": "deferred_by_intelligence",
                                "reason": decision.reason,
                            }
                        )
                        # Queue to digest if digest engine is available
                        if self._digest_engine is not None and decision.batch_with:
                            try:
                                self._digest_engine.queue_notification(
                                    user_id="molham",
                                    notification_id=notif_id,
                                    event_type=row.get("type", "alert"),
                                    category=entity_type or "general",
                                    severity=priority,
                                    bucket=decision.batch_with,
                                )
                            except (sqlite3.Error, ValueError, OSError) as e:
                                logger.error(f"NotificationEngine: digest queue failed: {e}")
                        continue
                except (ValueError, TypeError, OSError) as e:
                    logger.error(f"NotificationEngine: intelligence decision failed: {e}")
                    # Fall through to normal send on intelligence failure

            if not self._check_rate_limit(priority):
                results.append({"id": notif_id, "status": "rate_limited"})
                continue

            if priority != "critical" and self._is_quiet_hours():
                results.append({"id": notif_id, "status": "deferred"})
                continue

            if channels_json:
                try:
                    target_channels = json.loads(channels_json)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid channels JSON for notification {notif_id}: {e}")
                    results.append(
                        {
                            "id": notif_id,
                            "status": "error",
                            "error": "No notification channel configured",
                        }
                    )
                    continue
            else:
                results.append(
                    {
                        "id": notif_id,
                        "status": "error",
                        "error": "No notification channel configured",
                    }
                )
                continue

            message = f"**{title}**"
            if body:
                message += f"\n\n{body}"

            for channel_name in target_channels:
                if channel_name not in self.channels:
                    results.append(
                        {
                            "id": notif_id,
                            "channel": channel_name,
                            "status": "error",
                            "error": f"{channel_name} not configured",
                        }
                    )
                    continue

                try:
                    channel = self.channels[channel_name]
                    # Use sync method
                    result = channel.send_sync(message, priority=priority)

                    if result.get("success"):
                        self.store.update(
                            "notifications",
                            notif_id,
                            {
                                "sent_at": datetime.now().isoformat(),
                                "delivery_channel": channel_name,
                                "delivery_id": result.get("message_id"),
                            },
                        )
                        results.append({"id": notif_id, "channel": channel_name, "status": "sent"})
                    else:
                        results.append(
                            {
                                "id": notif_id,
                                "channel": channel_name,
                                "status": "error",
                                "error": result.get("error"),
                            }
                        )
                except (sqlite3.Error, ValueError, OSError) as e:
                    results.append(
                        {
                            "id": notif_id,
                            "channel": channel_name,
                            "status": "error",
                            "error": str(e),
                        }
                    )

        return results

    def create_notification(
        self,
        type: str,
        priority: str,
        title: str,
        body: str = None,
        action_url: str = None,
        action_data: dict = None,
        channels: list[str] = None,
    ) -> str:
        """
        Create a new notification for delivery.

        Args:
            type: 'alert' | 'reminder' | 'insight' | 'decision'
            priority: 'critical' | 'high' | 'normal' | 'low'
            title: Notification title
            body: Optional body text
            action_url: Optional URL for action
            action_data: Optional action data dict
            channels: Optional list of channels

        Returns:
            notification_id
        """
        notif_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        self.store.insert(
            "notifications",
            {
                "id": notif_id,
                "type": type,
                "priority": priority,
                "title": title,
                "body": body,
                "action_url": action_url,
                "action_data": json.dumps(action_data) if action_data else None,
                "channels": json.dumps(channels) if channels else None,
                "created_at": now,
            },
        )

        return notif_id

    def _check_rate_limit(self, priority: str) -> bool:
        """
        Check if we can send another notification of this priority.

        Limits (from MOH_TIME_OS_REPORTING.md):
            - critical: 3/day
            - high: 5/day
            - normal: 10/day
            - low: unlimited (but batched)
        """
        limits = {
            "critical": 3,
            "high": 5,
            "normal": 10,
            "low": 999999,  # Effectively unlimited
        }

        limit = limits.get(priority, 10)

        # Count sent today
        today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()

        count = self.store.count(
            "notifications",
            where="priority = ? AND sent_at >= ?",
            params=[priority, today_start],
        )

        return count < limit

    def _is_quiet_hours(self) -> bool:
        """Check if we're in quiet hours (23:00 - 08:00 Dubai time)."""
        quiet_config = self.config.get("quiet_hours", {})
        if not quiet_config.get("enabled", True):
            return False

        now = datetime.now()
        hour = now.hour

        start_hour = int(quiet_config.get("start", "23:00").split(":")[0])
        end_hour = int(quiet_config.get("end", "08:00").split(":")[0])

        # Handle overnight quiet hours
        if start_hour > end_hour:
            return hour >= start_hour or hour < end_hour
        return start_hour <= hour < end_hour

    def get_pending_count(self) -> dict:
        """Get count of pending notifications by priority."""
        results = self.store.query("""
            SELECT priority, COUNT(*) as cnt FROM notifications
            WHERE sent_at IS NULL
            GROUP BY priority
        """)

        return {row["priority"]: row["cnt"] for row in results}

    def get_sent_today(self) -> dict:
        """Get count of sent notifications today by priority."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()

        results = self.store.query(
            """
            SELECT priority, COUNT(*) as cnt FROM notifications
            WHERE sent_at >= ?
            GROUP BY priority
        """,
            [today_start],
        )

        return {row["priority"]: row["cnt"] for row in results}

    # --- Notification Muting (GAP-10-06) ---

    def mute_entity(self, entity_id: str, mute_until: str, reason: str = "") -> str:
        """
        Mute notifications for an entity until a given datetime.

        Args:
            entity_id: Entity to mute (e.g., "client:acme")
            mute_until: ISO datetime string for mute expiry
            reason: Optional reason for muting

        Returns:
            mute_id
        """
        mute_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        self.store.insert(
            "notification_mutes",
            {
                "id": mute_id,
                "entity_id": entity_id,
                "muted_at": now,
                "mute_until": mute_until,
                "mute_reason": reason,
            },
        )

        logger.info("Muted entity %s until %s (reason: %s)", entity_id, mute_until, reason)
        return mute_id

    def unmute_entity(self, entity_id: str) -> bool:
        """
        Remove active mute for an entity by setting mute_until to now.

        Returns:
            True if a mute was found and cleared, False otherwise.
        """
        now = datetime.now().isoformat()
        active = self.store.query(
            """
            SELECT id FROM notification_mutes
            WHERE entity_id = ? AND mute_until > ?
            ORDER BY mute_until DESC LIMIT 1
        """,
            [entity_id, now],
        )

        if not active:
            return False

        self.store.update(
            "notification_mutes",
            active[0]["id"],
            {"mute_until": now},
        )
        logger.info("Unmuted entity %s", entity_id)
        return True

    def is_muted(self, entity_id: str) -> bool:
        """Check if an entity is currently muted."""
        now = datetime.now().isoformat()
        count = self.store.count(
            "notification_mutes",
            where="entity_id = ? AND mute_until > ?",
            params=[entity_id, now],
        )
        return count > 0

    def get_active_mutes(self) -> list[dict]:
        """Return all currently active mutes."""
        now = datetime.now().isoformat()
        return self.store.query(
            """
            SELECT id, entity_id, muted_at, mute_until, mute_reason
            FROM notification_mutes
            WHERE mute_until > ?
            ORDER BY mute_until ASC
        """,
            [now],
        )

    # --- Notification Analytics (GAP-10-07) ---

    def track_delivery(
        self,
        notification_id: str,
        channel: str,
        outcome: str,
        metadata: dict = None,
    ) -> str:
        """
        Track a notification delivery outcome.

        Args:
            notification_id: ID of the notification
            channel: Delivery channel name
            outcome: 'delivered' | 'failed' | 'opened' | 'acted_on'
            metadata: Optional metadata dict

        Returns:
            analytics_id
        """
        analytics_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        self.store.insert(
            "notification_analytics",
            {
                "id": analytics_id,
                "notification_id": notification_id,
                "channel": channel,
                "outcome": outcome,
                "metadata": json.dumps(metadata) if metadata else None,
                "recorded_at": now,
            },
        )

        return analytics_id

    def get_analytics_summary(self, days: int = 30) -> dict:
        """
        Get notification analytics summary for the last N days.

        Returns:
            {
                "total_sent": int,
                "by_channel": {"google_chat": {"delivered": N, "failed": N, ...}},
                "by_outcome": {"delivered": N, "failed": N, ...},
                "action_rate": float
            }
        """
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        rows = self.store.query(
            """
            SELECT channel, outcome, COUNT(*) as cnt
            FROM notification_analytics
            WHERE recorded_at >= ?
            GROUP BY channel, outcome
        """,
            [cutoff],
        )

        by_channel: dict[str, dict[str, int]] = {}
        by_outcome: dict[str, int] = {}
        total = 0

        for row in rows:
            ch = row["channel"]
            oc = row["outcome"]
            cnt = row["cnt"]
            total += cnt

            if ch not in by_channel:
                by_channel[ch] = {}
            by_channel[ch][oc] = cnt

            by_outcome[oc] = by_outcome.get(oc, 0) + cnt

        acted = by_outcome.get("acted_on", 0)
        delivered = by_outcome.get("delivered", 0) + acted
        action_rate = acted / delivered if delivered > 0 else 0.0

        return {
            "total_sent": total,
            "by_channel": by_channel,
            "by_outcome": by_outcome,
            "action_rate": round(action_rate, 4),
        }
