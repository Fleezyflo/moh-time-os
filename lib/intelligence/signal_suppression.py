"""
Signal Suppression — MOH TIME OS

Manages signal suppression windows and auto-deprioritization.
Extends signal_lifecycle.py with dismiss tracking and suppression logic.

Brief 22 (SM), Task SM-3.1

Suppression rules:
- Dismissed signal suppressed for 7 days (default window)
- 3+ dismissals → 30-day suppression window
- 70%+ dismiss rate → auto-deprioritize (severity capped at 'watch')
"""

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Suppression configuration
DEFAULT_SUPPRESS_DAYS = 7
REPEAT_DISMISS_SUPPRESS_DAYS = 30
REPEAT_DISMISS_THRESHOLD = 3
AUTO_DEPRIORITIZE_DISMISS_RATE = 0.70


@dataclass
class SuppressionRecord:
    """A suppression entry for a signal."""

    id: str
    signal_key: str
    entity_type: str
    entity_id: str
    reason: str  # 'user_dismiss' | 'auto_deprioritize' | 'duplicate' | 'resolved'
    suppressed_at: str
    expires_at: str
    dismiss_count: int = 1
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "signal_key": self.signal_key,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "reason": self.reason,
            "suppressed_at": self.suppressed_at,
            "expires_at": self.expires_at,
            "dismiss_count": self.dismiss_count,
            "is_active": self.is_active,
        }


@dataclass
class SignalDismissStats:
    """Dismiss statistics for a signal type + entity pair."""

    signal_key: str
    total_raised: int
    total_dismissed: int
    dismiss_rate: float
    is_auto_deprioritized: bool
    current_suppress_window_days: int

    def to_dict(self) -> dict:
        return {
            "signal_key": self.signal_key,
            "total_raised": self.total_raised,
            "total_dismissed": self.total_dismissed,
            "dismiss_rate": round(self.dismiss_rate, 4),
            "is_auto_deprioritized": self.is_auto_deprioritized,
            "current_suppress_window_days": self.current_suppress_window_days,
        }


class SignalSuppression:
    """Manages signal suppression windows and auto-deprioritization."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_suppressions (
                    id TEXT PRIMARY KEY,
                    signal_key TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    suppressed_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    dismiss_count INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_suppress_signal ON signal_suppressions(signal_key)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_suppress_entity "
                "ON signal_suppressions(entity_type, entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_suppress_active "
                "ON signal_suppressions(is_active, expires_at)"
            )

            # Track signal raise/dismiss history for rate calculations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_dismiss_log (
                    id TEXT PRIMARY KEY,
                    signal_key TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,  -- 'raised' | 'dismissed'
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dismiss_log_signal "
                "ON signal_dismiss_log(signal_key)"
            )
            conn.commit()
        finally:
            conn.close()

    def is_suppressed(self, signal_key: str) -> bool:
        """Check if a signal is currently suppressed."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            now = datetime.now().isoformat()
            row = conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM signal_suppressions
                WHERE signal_key = ?
                AND is_active = 1
                AND expires_at > ?
                """,
                (signal_key, now),
            ).fetchone()
            return (row[0] if row else 0) > 0
        finally:
            conn.close()

    def dismiss_signal(
        self,
        signal_key: str,
        entity_type: str,
        entity_id: str,
        reason: str = "user_dismiss",
    ) -> SuppressionRecord:
        """
        Dismiss a signal and create a suppression window.

        Suppression window scales with dismiss count:
        - 1-2 dismissals: 7 days
        - 3+ dismissals: 30 days
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Count previous dismissals for this signal
            prev_count = conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM signal_dismiss_log
                WHERE signal_key = ?
                AND event_type = 'dismissed'
                """,
                (signal_key,),
            ).fetchone()[0]

            new_dismiss_count = prev_count + 1

            # Determine suppression window
            if new_dismiss_count >= REPEAT_DISMISS_THRESHOLD:
                suppress_days = REPEAT_DISMISS_SUPPRESS_DAYS
            else:
                suppress_days = DEFAULT_SUPPRESS_DAYS

            now = datetime.now()
            expires = now + timedelta(days=suppress_days)

            # Deactivate any existing suppression for this signal
            conn.execute(
                """
                UPDATE signal_suppressions
                SET is_active = 0
                WHERE signal_key = ? AND is_active = 1
                """,
                (signal_key,),
            )

            # Create new suppression
            record = SuppressionRecord(
                id=str(uuid.uuid4()),
                signal_key=signal_key,
                entity_type=entity_type,
                entity_id=entity_id,
                reason=reason,
                suppressed_at=now.isoformat(),
                expires_at=expires.isoformat(),
                dismiss_count=new_dismiss_count,
                is_active=True,
            )

            conn.execute(
                """
                INSERT INTO signal_suppressions
                (id, signal_key, entity_type, entity_id, reason,
                 suppressed_at, expires_at, dismiss_count, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    record.id,
                    record.signal_key,
                    record.entity_type,
                    record.entity_id,
                    record.reason,
                    record.suppressed_at,
                    record.expires_at,
                    record.dismiss_count,
                ),
            )

            # Log the dismiss event
            conn.execute(
                """
                INSERT INTO signal_dismiss_log
                (id, signal_key, entity_type, entity_id, event_type, created_at)
                VALUES (?, ?, ?, ?, 'dismissed', ?)
                """,
                (str(uuid.uuid4()), signal_key, entity_type, entity_id, now.isoformat()),
            )
            conn.commit()

            return record
        finally:
            conn.close()

    def record_signal_raised(
        self,
        signal_key: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        """Record that a signal was raised (for dismiss rate tracking)."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO signal_dismiss_log
                (id, signal_key, entity_type, entity_id, event_type, created_at)
                VALUES (?, ?, ?, ?, 'raised', ?)
                """,
                (
                    str(uuid.uuid4()),
                    signal_key,
                    entity_type,
                    entity_id,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_dismiss_stats(self, signal_key: str) -> SignalDismissStats:
        """Get dismiss statistics for a signal."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            raised = conn.execute(
                "SELECT COUNT(*) FROM signal_dismiss_log WHERE signal_key = ? AND event_type = 'raised'",
                (signal_key,),
            ).fetchone()[0]
            dismissed = conn.execute(
                "SELECT COUNT(*) FROM signal_dismiss_log WHERE signal_key = ? AND event_type = 'dismissed'",
                (signal_key,),
            ).fetchone()[0]

            total = raised + dismissed
            dismiss_rate = dismissed / total if total > 0 else 0.0
            is_deprioritized = (
                dismiss_rate >= AUTO_DEPRIORITIZE_DISMISS_RATE
                and dismissed >= REPEAT_DISMISS_THRESHOLD
            )

            if dismissed >= REPEAT_DISMISS_THRESHOLD:
                window = REPEAT_DISMISS_SUPPRESS_DAYS
            else:
                window = DEFAULT_SUPPRESS_DAYS

            return SignalDismissStats(
                signal_key=signal_key,
                total_raised=raised,
                total_dismissed=dismissed,
                dismiss_rate=dismiss_rate,
                is_auto_deprioritized=is_deprioritized,
                current_suppress_window_days=window,
            )
        finally:
            conn.close()

    def should_deprioritize(self, signal_key: str) -> bool:
        """
        Check if a signal should be auto-deprioritized.

        Returns True if dismiss rate >= 70% and dismissed 3+ times.
        When True, severity should be capped at 'watch'.
        """
        stats = self.get_dismiss_stats(signal_key)
        return stats.is_auto_deprioritized

    def expire_suppressions(self) -> int:
        """Deactivate expired suppressions. Returns count expired."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """
                UPDATE signal_suppressions
                SET is_active = 0
                WHERE is_active = 1 AND expires_at <= ?
                """,
                (now,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_active_suppressions(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[SuppressionRecord]:
        """Get all active (non-expired) suppressions."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now().isoformat()
            if entity_type and entity_id:
                rows = conn.execute(
                    """
                    SELECT * FROM signal_suppressions
                    WHERE is_active = 1 AND expires_at > ?
                    AND entity_type = ? AND entity_id = ?
                    ORDER BY suppressed_at DESC
                    """,
                    (now, entity_type, entity_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM signal_suppressions
                    WHERE is_active = 1 AND expires_at > ?
                    ORDER BY suppressed_at DESC
                    """,
                    (now,),
                ).fetchall()

            return [self._row_to_record(r) for r in rows]
        finally:
            conn.close()

    def get_suppression_summary(self) -> dict[str, Any]:
        """Get summary of all suppressions."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now().isoformat()

            active = conn.execute(
                "SELECT COUNT(*) as cnt FROM signal_suppressions WHERE is_active = 1 AND expires_at > ?",
                (now,),
            ).fetchone()["cnt"]

            expired = conn.execute(
                "SELECT COUNT(*) as cnt FROM signal_suppressions WHERE is_active = 0 OR expires_at <= ?",
                (now,),
            ).fetchone()["cnt"]

            by_reason = conn.execute(
                """
                SELECT reason, COUNT(*) as cnt
                FROM signal_suppressions
                WHERE is_active = 1 AND expires_at > ?
                GROUP BY reason
                """,
                (now,),
            ).fetchall()

            # Deprioritized signals
            deprioritized = conn.execute(
                """
                SELECT signal_key, COUNT(*) as dismiss_count
                FROM signal_dismiss_log
                WHERE event_type = 'dismissed'
                GROUP BY signal_key
                HAVING COUNT(*) >= ?
                """,
                (REPEAT_DISMISS_THRESHOLD,),
            ).fetchall()

            return {
                "active_suppressions": active,
                "expired_suppressions": expired,
                "by_reason": {row["reason"]: row["cnt"] for row in by_reason},
                "deprioritized_signals": len(deprioritized),
            }
        finally:
            conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> SuppressionRecord:
        return SuppressionRecord(
            id=row["id"],
            signal_key=row["signal_key"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            reason=row["reason"],
            suppressed_at=row["suppressed_at"],
            expires_at=row["expires_at"],
            dismiss_count=row["dismiss_count"],
            is_active=bool(row["is_active"]),
        )
