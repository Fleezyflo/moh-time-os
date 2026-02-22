"""
Signal Lifecycle Tracker — Persistence and escalation tracking for signals.

Brief 31 (TC), Task TC-4.1

Adds lifecycle context to signals: first detection, age in business days,
persistence classification (NEW/RECENT/ONGOING/CHRONIC/ESCALATING/RESOLVING),
and auto-escalation of chronic watch signals.

Works with the signal_state table (extended by v32 migration).
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from lib import paths
from lib.intelligence.temporal import BusinessCalendar

logger = logging.getLogger(__name__)


class SignalPersistence(Enum):
    """Signal persistence classification."""

    NEW = "new"  # First detection this cycle
    RECENT = "recent"  # 1-3 business days old
    ONGOING = "ongoing"  # 4-10 business days old
    CHRONIC = "chronic"  # 11+ business days old
    ESCALATING = "escalating"  # Severity increased since first detection
    RESOLVING = "resolving"  # Metrics improving but still above threshold


@dataclass
class SignalLifecycle:
    """Complete lifecycle context for a signal."""

    signal_key: str
    signal_type: str
    entity_type: str
    entity_id: str
    first_detected_at: datetime
    last_detected_at: datetime
    current_severity: str  # critical/warning/watch
    initial_severity: str
    detection_count: int
    consecutive_cycles: int
    business_days_active: int
    calendar_days_active: int
    persistence: SignalPersistence
    escalation_history: list[dict] = field(default_factory=list)
    peak_severity: str = "watch"
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_type: str | None = None

    def to_dict(self) -> dict:
        return {
            "signal_key": self.signal_key,
            "signal_type": self.signal_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "first_detected_at": self.first_detected_at.isoformat()
            if self.first_detected_at
            else None,
            "last_detected_at": self.last_detected_at.isoformat()
            if self.last_detected_at
            else None,
            "current_severity": self.current_severity,
            "initial_severity": self.initial_severity,
            "detection_count": self.detection_count,
            "consecutive_cycles": self.consecutive_cycles,
            "business_days_active": self.business_days_active,
            "calendar_days_active": self.calendar_days_active,
            "persistence": self.persistence.value,
            "escalation_history": self.escalation_history,
            "peak_severity": self.peak_severity,
        }


# Severity ordering for comparison
_SEVERITY_ORDER = {"watch": 1, "warning": 2, "critical": 3}


def _severity_gt(a: str, b: str) -> bool:
    """True if severity a is greater than severity b."""
    return _SEVERITY_ORDER.get(a, 0) > _SEVERITY_ORDER.get(b, 0)


def _severity_max(a: str, b: str) -> str:
    """Return the higher severity."""
    return a if _SEVERITY_ORDER.get(a, 0) >= _SEVERITY_ORDER.get(b, 0) else b


class SignalLifecycleTracker:
    """
    Tracks and classifies signal persistence and escalation.

    Reads/writes lifecycle metadata in the signal_state table
    (extended columns added by v32 migration).
    """

    # Auto-escalation: chronic watch signals upgrade after this many business days
    CHRONIC_ESCALATION_THRESHOLD_DAYS = 14

    def __init__(self, db_path: Path | None = None, calendar: BusinessCalendar | None = None):
        self.db_path = db_path or paths.db_path()
        self.calendar = calendar or BusinessCalendar()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_lifecycle(self, signal_key: str) -> SignalLifecycle | None:
        """Return full lifecycle context for a signal, or None if not found."""
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT signal_key, signal_type, entity_type, entity_id,
                       severity, detected_at,
                       first_detected_at, detection_count, consecutive_cycles,
                       initial_severity, peak_severity, escalation_history_json,
                       resolved_at, resolution_type
                FROM signal_state
                WHERE signal_key = ?
                """,
                (signal_key,),
            ).fetchone()

            if row is None:
                return None

            return self._row_to_lifecycle(dict(row))
        finally:
            conn.close()

    def _row_to_lifecycle(self, row: dict) -> SignalLifecycle:
        """Convert a signal_state row to a SignalLifecycle."""
        first_det = row.get("first_detected_at") or row.get("detected_at", "")
        last_det = row.get("detected_at", "")
        initial_sev = row.get("initial_severity") or row.get("severity", "watch")
        peak_sev = row.get("peak_severity") or row.get("severity", "watch")
        esc_json = row.get("escalation_history_json", "[]")

        try:
            first_dt = datetime.fromisoformat(first_det) if first_det else datetime.now()
        except (ValueError, TypeError):
            first_dt = datetime.now()

        try:
            last_dt = datetime.fromisoformat(last_det) if last_det else datetime.now()
        except (ValueError, TypeError):
            last_dt = datetime.now()

        try:
            esc_history = json.loads(esc_json) if esc_json else []
        except (json.JSONDecodeError, TypeError):
            esc_history = []

        now = date.today()
        bd_active = self.calendar.business_days_between(first_dt.date(), now)
        cd_active = (now - first_dt.date()).days

        current_severity = row.get("severity", "watch")

        # Classify persistence
        persistence = self._classify(
            detection_count=row.get("detection_count", 1),
            business_days_active=bd_active,
            current_severity=current_severity,
            initial_severity=initial_sev,
        )

        resolved_at = None
        if row.get("resolved_at"):
            try:
                resolved_at = datetime.fromisoformat(row["resolved_at"])
            except (ValueError, TypeError):
                pass

        return SignalLifecycle(
            signal_key=row.get("signal_key", ""),
            signal_type=row.get("signal_type", ""),
            entity_type=row.get("entity_type", ""),
            entity_id=row.get("entity_id", ""),
            first_detected_at=first_dt,
            last_detected_at=last_dt,
            current_severity=current_severity,
            initial_severity=initial_sev,
            detection_count=row.get("detection_count", 1),
            consecutive_cycles=row.get("consecutive_cycles", 1),
            business_days_active=bd_active,
            calendar_days_active=cd_active,
            persistence=persistence,
            escalation_history=esc_history,
            peak_severity=peak_sev,
            resolved_at=resolved_at,
            resolution_type=row.get("resolution_type"),
        )

    def _classify(
        self,
        detection_count: int,
        business_days_active: int,
        current_severity: str,
        initial_severity: str,
    ) -> SignalPersistence:
        """Classify signal persistence level."""
        # Priority 1: Escalating (severity increased)
        if _severity_gt(current_severity, initial_severity):
            return SignalPersistence.ESCALATING

        # Priority 2: First detection
        if detection_count <= 1:
            return SignalPersistence.NEW

        # Priority 3: Age-based
        if business_days_active <= 3:
            return SignalPersistence.RECENT
        elif business_days_active <= 10:
            return SignalPersistence.ONGOING
        else:
            return SignalPersistence.CHRONIC

    def classify_persistence(self, signal_key: str) -> SignalPersistence | None:
        """Classify a signal's persistence level. Returns None if not found."""
        lifecycle = self.get_lifecycle(signal_key)
        if lifecycle is None:
            return None
        return lifecycle.persistence

    def get_escalation_history(self, signal_key: str) -> list[dict]:
        """Return severity changes for a signal."""
        lifecycle = self.get_lifecycle(signal_key)
        if lifecycle is None:
            return []
        return lifecycle.escalation_history

    def update_lifecycle_on_detection(
        self,
        signal_key: str,
        current_severity: str,
        signal_type: str = "",
        entity_type: str = "",
        entity_id: str = "",
        evidence: dict | None = None,
    ) -> SignalLifecycle | None:
        """
        Called during signal detection to update lifecycle tracking.

        Updates detection_count, consecutive_cycles, severity changes.
        Returns updated lifecycle.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT signal_key, signal_type, entity_type, entity_id,
                       severity, detected_at,
                       first_detected_at, detection_count, consecutive_cycles,
                       initial_severity, peak_severity, escalation_history_json
                FROM signal_state
                WHERE signal_key = ?
                """,
                (signal_key,),
            ).fetchone()

            now_iso = datetime.now().isoformat()

            if row is None:
                # First detection — insert new row
                conn.execute(
                    """
                    INSERT INTO signal_state (
                        signal_key, signal_type, entity_type, entity_id,
                        severity, detected_at,
                        first_detected_at, detection_count, consecutive_cycles,
                        initial_severity, peak_severity, escalation_history_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, '[]')
                    """,
                    (
                        signal_key,
                        signal_type,
                        entity_type,
                        entity_id,
                        current_severity,
                        now_iso,
                        now_iso,
                        current_severity,
                        current_severity,
                    ),
                )
                conn.commit()
                return self.get_lifecycle(signal_key)

            # Existing signal — update lifecycle
            row_dict = dict(row)
            old_severity = row_dict.get("severity", "watch")
            row_dict.get("initial_severity") or old_severity
            peak_sev = row_dict.get("peak_severity") or old_severity
            det_count = (row_dict.get("detection_count") or 0) + 1
            consec = (row_dict.get("consecutive_cycles") or 0) + 1

            # Track escalation
            esc_json = row_dict.get("escalation_history_json", "[]")
            try:
                esc_history = json.loads(esc_json) if esc_json else []
            except (json.JSONDecodeError, TypeError):
                esc_history = []

            if current_severity != old_severity:
                esc_history.append(
                    {
                        "timestamp": now_iso,
                        "old_severity": old_severity,
                        "new_severity": current_severity,
                        "detection_count": det_count,
                    }
                )

            new_peak = _severity_max(peak_sev, current_severity)

            conn.execute(
                """
                UPDATE signal_state
                SET severity = ?,
                    detected_at = ?,
                    detection_count = ?,
                    consecutive_cycles = ?,
                    peak_severity = ?,
                    escalation_history_json = ?,
                    resolved_at = NULL,
                    resolution_type = NULL
                WHERE signal_key = ?
                """,
                (
                    current_severity,
                    now_iso,
                    det_count,
                    consec,
                    new_peak,
                    json.dumps(esc_history),
                    signal_key,
                ),
            )
            conn.commit()

            return self.get_lifecycle(signal_key)
        finally:
            conn.close()

    def update_lifecycle_on_clear(self, signal_key: str, resolution_type: str = "resolved") -> None:
        """
        Called when a signal clears. Records resolution — does NOT delete.
        """
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE signal_state
                SET resolved_at = ?,
                    resolution_type = ?,
                    consecutive_cycles = 0
                WHERE signal_key = ?
                """,
                (datetime.now().isoformat(), resolution_type, signal_key),
            )
            conn.commit()
        finally:
            conn.close()

    def get_chronic_signals(self, min_business_days: int = 11) -> list[SignalLifecycle]:
        """Return all signals active for more than N business days, sorted oldest first."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT signal_key, signal_type, entity_type, entity_id,
                       severity, detected_at,
                       first_detected_at, detection_count, consecutive_cycles,
                       initial_severity, peak_severity, escalation_history_json,
                       resolved_at, resolution_type
                FROM signal_state
                WHERE resolved_at IS NULL
                  AND first_detected_at IS NOT NULL
                ORDER BY first_detected_at ASC
                """
            ).fetchall()

            results = []
            for row in rows:
                lifecycle = self._row_to_lifecycle(dict(row))
                if lifecycle.business_days_active >= min_business_days:
                    results.append(lifecycle)
            return results
        finally:
            conn.close()

    def get_escalating_signals(self) -> list[SignalLifecycle]:
        """Return all signals whose severity has increased since first detection."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT signal_key, signal_type, entity_type, entity_id,
                       severity, detected_at,
                       first_detected_at, detection_count, consecutive_cycles,
                       initial_severity, peak_severity, escalation_history_json,
                       resolved_at, resolution_type
                FROM signal_state
                WHERE resolved_at IS NULL
                ORDER BY detected_at DESC
                """
            ).fetchall()

            results = []
            for row in rows:
                lifecycle = self._row_to_lifecycle(dict(row))
                if lifecycle.persistence == SignalPersistence.ESCALATING:
                    results.append(lifecycle)
            return results
        finally:
            conn.close()

    def get_signal_age_distribution(self) -> dict:
        """Distribution of active signal ages."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT signal_key, signal_type, entity_type, entity_id,
                       severity, detected_at,
                       first_detected_at, detection_count, consecutive_cycles,
                       initial_severity, peak_severity, escalation_history_json,
                       resolved_at, resolution_type
                FROM signal_state
                WHERE resolved_at IS NULL
                """
            ).fetchall()

            distribution = {
                "new": 0,
                "recent": 0,
                "ongoing": 0,
                "chronic": 0,
                "escalating": 0,
                "resolving": 0,
            }
            ages = []
            oldest = None
            oldest_age = 0

            for row in rows:
                lifecycle = self._row_to_lifecycle(dict(row))
                distribution[lifecycle.persistence.value] += 1
                ages.append(lifecycle.business_days_active)
                if lifecycle.business_days_active > oldest_age:
                    oldest_age = lifecycle.business_days_active
                    oldest = lifecycle

            total = sum(distribution.values())
            avg_age = sum(ages) / len(ages) if ages else 0.0
            sorted_ages = sorted(ages)
            median_age = sorted_ages[len(sorted_ages) // 2] if sorted_ages else 0

            result = {
                **distribution,
                "total_active": total,
                "avg_age_business_days": round(avg_age, 1),
                "median_age_business_days": median_age,
            }
            if oldest:
                result["oldest_signal"] = {
                    "key": oldest.signal_key,
                    "age_business_days": oldest_age,
                }
            return result
        finally:
            conn.close()

    def auto_escalate_chronic_signals(self) -> list[dict]:
        """
        Auto-escalate chronic watch signals to warning.

        Returns list of escalation events for logging/notification.
        """
        chronic = self.get_chronic_signals(min_business_days=self.CHRONIC_ESCALATION_THRESHOLD_DAYS)
        escalations = []

        for sig in chronic:
            if (
                sig.current_severity == "watch"
                and sig.business_days_active >= self.CHRONIC_ESCALATION_THRESHOLD_DAYS
            ):
                logger.info(
                    "Auto-escalating chronic signal %s from watch to warning (%d business days)",
                    sig.signal_key,
                    sig.business_days_active,
                )
                self.update_lifecycle_on_detection(
                    signal_key=sig.signal_key,
                    current_severity="warning",
                    signal_type=sig.signal_type,
                    entity_type=sig.entity_type,
                    entity_id=sig.entity_id,
                )
                escalations.append(
                    {
                        "signal_key": sig.signal_key,
                        "old_severity": "watch",
                        "new_severity": "warning",
                        "business_days_active": sig.business_days_active,
                        "reason": "chronic_auto_escalation",
                    }
                )

        return escalations
