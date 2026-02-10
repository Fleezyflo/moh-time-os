"""
Time OS V5 — Signal Repository

Raw database operations for signals.
"""

from typing import Any

from ..database import Database
from ..models import Signal, SignalCategory, SignalStatus, now_iso


class SignalRepository:
    """Repository for signal database operations."""

    def __init__(self, db: Database):
        """
        Initialize repository.

        Args:
            db: Database instance
        """
        self.db = db

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def insert(self, signal: Signal) -> str:
        """
        Insert a new signal.

        Args:
            signal: Signal to insert

        Returns:
            Signal ID
        """
        data = {
            "id": signal.id,
            "signal_type": signal.signal_type,
            "signal_category": signal.signal_category.value
            if isinstance(signal.signal_category, SignalCategory)
            else signal.signal_category,
            "valence": signal.valence,
            "magnitude": signal.magnitude,
            "entity_type": signal.entity_type,
            "entity_id": signal.entity_id,
            "scope_task_id": signal.scope_task_id,
            "scope_project_id": signal.scope_project_id,
            "scope_retainer_id": signal.scope_retainer_id,
            "scope_brand_id": signal.scope_brand_id,
            "scope_client_id": signal.scope_client_id,
            "scope_person_id": signal.scope_person_id,
            "source_type": signal.source_type.value
            if hasattr(signal.source_type, "value")
            else signal.source_type,
            "source_id": signal.source_id,
            "source_url": signal.source_url,
            "source_excerpt": signal.source_excerpt,
            "value_json": signal.value_json,
            "detection_confidence": signal.detection_confidence,
            "attribution_confidence": signal.attribution_confidence,
            "status": signal.status.value
            if isinstance(signal.status, SignalStatus)
            else signal.status,
            "balanced_by_signal_id": signal.balanced_by_signal_id,
            "consumed_by_issue_id": signal.consumed_by_issue_id,
            "occurred_at": signal.occurred_at,
            "detected_at": signal.detected_at,
            "expires_at": signal.expires_at,
            "balanced_at": signal.balanced_at,
            "detector_id": signal.detector_id,
            "detector_version": signal.detector_version,
            "created_at": signal.created_at,
            "updated_at": signal.updated_at,
        }

        self.db.insert("signals_v5", data)
        return signal.id

    def insert_many(self, signals: list[Signal]) -> int:
        """
        Insert multiple signals.

        Args:
            signals: List of signals

        Returns:
            Number of signals inserted
        """
        if not signals:
            return 0

        for signal in signals:
            self.insert(signal)

        return len(signals)

    def update(self, signal_id: str, updates: dict[str, Any]) -> bool:
        """
        Update a signal.

        Args:
            signal_id: Signal ID
            updates: Fields to update

        Returns:
            True if updated
        """
        updates["updated_at"] = now_iso()

        # Convert enums to values
        if "status" in updates and hasattr(updates["status"], "value"):
            updates["status"] = updates["status"].value

        count = self.db.update("signals_v5", updates, "id = ?", [signal_id])
        return count > 0

    def get(self, signal_id: str) -> Signal | None:
        """
        Get a signal by ID.

        Args:
            signal_id: Signal ID

        Returns:
            Signal or None
        """
        row = self.db.fetch_one("SELECT * FROM signals_v5 WHERE id = ?", (signal_id,))
        if row:
            return Signal.from_row(row)
        return None

    def delete(self, signal_id: str) -> bool:
        """
        Delete a signal.

        Args:
            signal_id: Signal ID

        Returns:
            True if deleted
        """
        count = self.db.delete("signals_v5", "id = ?", [signal_id])
        return count > 0

    # =========================================================================
    # Queries
    # =========================================================================

    def find_by_entity(
        self, entity_type: str, entity_id: str, status: str | None = None
    ) -> list[Signal]:
        """
        Find signals for an entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            status: Optional status filter

        Returns:
            List of signals
        """
        if status:
            rows = self.db.fetch_all(
                """
                SELECT * FROM signals_v5
                WHERE entity_type = ? AND entity_id = ? AND status = ?
                ORDER BY detected_at DESC
            """,
                (entity_type, entity_id, status),
            )
        else:
            rows = self.db.fetch_all(
                """
                SELECT * FROM signals_v5
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY detected_at DESC
            """,
                (entity_type, entity_id),
            )

        return [Signal.from_row(row) for row in rows]

    def find_by_scope(
        self,
        scope_type: str,
        scope_id: str,
        status: str | None = "active",
        valence: int | None = None,
        limit: int = 100,
    ) -> list[Signal]:
        """
        Find signals by scope (client, brand, project, etc.).

        Args:
            scope_type: Scope type (client, brand, project, retainer, task)
            scope_id: Scope ID
            status: Optional status filter
            valence: Optional valence filter
            limit: Maximum results

        Returns:
            List of signals
        """
        scope_column = f"scope_{scope_type}_id"

        conditions = [f"{scope_column} = ?"]
        params = [scope_id]

        if status:
            conditions.append("status = ?")
            params.append(status)

        if valence is not None:
            conditions.append("valence = ?")
            params.append(valence)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = self.db.fetch_all(
            f"""
            SELECT * FROM signals_v5
            WHERE {where}
            ORDER BY detected_at DESC
            LIMIT ?
        """,
            tuple(params),
        )

        return [Signal.from_row(row) for row in rows]

    def find_active(
        self,
        signal_types: list[str] | None = None,
        client_id: str | None = None,
        days: int = 30,
        limit: int = 500,
    ) -> list[Signal]:
        """
        Find active signals.

        Args:
            signal_types: Optional filter by signal types
            client_id: Optional filter by client
            days: Signals from last N days
            limit: Maximum results

        Returns:
            List of signals
        """
        conditions = [
            "status = 'active'",
            f"detected_at > datetime('now', '-{days} days')",
        ]
        params = []

        if signal_types:
            placeholders = ",".join(["?" for _ in signal_types])
            conditions.append(f"signal_type IN ({placeholders})")
            params.extend(signal_types)

        if client_id:
            conditions.append("scope_client_id = ?")
            params.append(client_id)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = self.db.fetch_all(
            f"""
            SELECT * FROM signals_v5
            WHERE {where}
            ORDER BY detected_at DESC
            LIMIT ?
        """,
            tuple(params),
        )

        return [Signal.from_row(row) for row in rows]

    def find_for_issue_formation(
        self,
        signal_types: list[str],
        scope_column: str,
        min_count: int = 1,
        min_magnitude: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Find signals grouped by scope for issue formation.

        Args:
            signal_types: Signal types to include
            scope_column: Column to group by (e.g., "scope_client_id")
            min_count: Minimum signal count
            min_magnitude: Minimum total negative magnitude

        Returns:
            List of grouped results with signal IDs and aggregates
        """
        placeholders = ",".join(["?" for _ in signal_types])

        return self.db.fetch_all(
            f"""
            SELECT
                {scope_column} as scope_id,
                scope_client_id,
                scope_brand_id,
                scope_project_id,
                scope_retainer_id,
                GROUP_CONCAT(id) as signal_ids,
                COUNT(*) as signal_count,
                SUM(CASE WHEN valence = -1 THEN magnitude *
                    CASE
                        WHEN julianday('now') - julianday(detected_at) > 365 THEN 0.1
                        WHEN julianday('now') - julianday(detected_at) > 180 THEN 0.25
                        WHEN julianday('now') - julianday(detected_at) > 90 THEN 0.5
                        WHEN julianday('now') - julianday(detected_at) > 30 THEN 0.8
                        ELSE 1.0
                    END
                ELSE 0 END) as negative_magnitude,
                SUM(CASE WHEN valence = 1 THEN magnitude *
                    CASE
                        WHEN julianday('now') - julianday(detected_at) > 365 THEN 0.1
                        WHEN julianday('now') - julianday(detected_at) > 180 THEN 0.25
                        WHEN julianday('now') - julianday(detected_at) > 90 THEN 0.5
                        WHEN julianday('now') - julianday(detected_at) > 30 THEN 0.8
                        ELSE 1.0
                    END
                ELSE 0 END) as positive_magnitude,
                COUNT(DISTINCT signal_category) as category_count
            FROM signals_v5
            WHERE status = 'active'
              AND {scope_column} IS NOT NULL
              AND signal_type IN ({placeholders})
            GROUP BY {scope_column}
            HAVING signal_count >= ? AND negative_magnitude >= ?
        """,
            tuple(signal_types) + (min_count, min_magnitude),
        )

    # =========================================================================
    # Status Updates
    # =========================================================================

    def mark_consumed(self, signal_ids: list[str], issue_id: str) -> int:
        """
        Mark signals as consumed by an issue.

        Args:
            signal_ids: List of signal IDs
            issue_id: Issue ID

        Returns:
            Number of signals updated
        """
        if not signal_ids:
            return 0

        placeholders = ",".join(["?" for _ in signal_ids])

        with self.db.transaction() as conn:
            cursor = conn.execute(
                f"""
                UPDATE signals_v5
                SET status = 'consumed',
                    consumed_by_issue_id = ?,
                    updated_at = ?
                WHERE id IN ({placeholders})
            """,
                (issue_id, now_iso()) + tuple(signal_ids),
            )
            return cursor.rowcount

    def mark_balanced(self, signal_id: str, by_signal_id: str) -> bool:
        """
        Mark a signal as balanced.

        Args:
            signal_id: Signal to mark balanced
            by_signal_id: Signal that balanced it

        Returns:
            True if updated
        """
        return self.update(
            signal_id,
            {
                "status": SignalStatus.BALANCED.value,
                "balanced_by_signal_id": by_signal_id,
                "balanced_at": now_iso(),
            },
        )

    def mark_expired(self, signal_ids: list[str]) -> int:
        """
        Mark signals as expired.

        Args:
            signal_ids: List of signal IDs

        Returns:
            Number of signals updated
        """
        if not signal_ids:
            return 0

        placeholders = ",".join(["?" for _ in signal_ids])

        with self.db.transaction() as conn:
            cursor = conn.execute(
                f"""
                UPDATE signals_v5
                SET status = 'expired',
                    updated_at = ?
                WHERE id IN ({placeholders})
            """,
                (now_iso(),) + tuple(signal_ids),
            )
            return cursor.rowcount

    def expire_old_signals(self) -> int:
        """
        Expire signals past their expiry date.

        Returns:
            Number of signals expired
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE signals_v5
                SET status = 'expired',
                    updated_at = ?
                WHERE status = 'active'
                  AND expires_at IS NOT NULL
                  AND datetime(expires_at) < datetime('now')
            """,
                (now_iso(),),
            )
            return cursor.rowcount

    # =========================================================================
    # Aggregations
    # =========================================================================

    def get_balance_for_scope(self, scope_type: str, scope_id: str) -> dict[str, Any]:
        """
        Get signal balance for a scope.

        Args:
            scope_type: Scope type
            scope_id: Scope ID

        Returns:
            Dict with balance metrics
        """
        scope_column = f"scope_{scope_type}_id"

        row = self.db.fetch_one(
            f"""
            SELECT
                COUNT(CASE WHEN valence = -1 THEN 1 END) as negative_count,
                SUM(CASE WHEN valence = -1 THEN magnitude *
                    CASE
                        WHEN julianday('now') - julianday(detected_at) > 365 THEN 0.1
                        WHEN julianday('now') - julianday(detected_at) > 180 THEN 0.25
                        WHEN julianday('now') - julianday(detected_at) > 90 THEN 0.5
                        WHEN julianday('now') - julianday(detected_at) > 30 THEN 0.8
                        ELSE 1.0
                    END
                ELSE 0 END) as negative_magnitude,
                COUNT(CASE WHEN valence = 0 THEN 1 END) as neutral_count,
                COUNT(CASE WHEN valence = 1 THEN 1 END) as positive_count,
                SUM(CASE WHEN valence = 1 THEN magnitude *
                    CASE
                        WHEN julianday('now') - julianday(detected_at) > 365 THEN 0.1
                        WHEN julianday('now') - julianday(detected_at) > 180 THEN 0.25
                        WHEN julianday('now') - julianday(detected_at) > 90 THEN 0.5
                        WHEN julianday('now') - julianday(detected_at) > 30 THEN 0.8
                        ELSE 1.0
                    END
                ELSE 0 END) as positive_magnitude
            FROM signals_v5
            WHERE {scope_column} = ?
              AND status = 'active'
        """,
            (scope_id,),
        )

        if not row:
            return {
                "negative_count": 0,
                "negative_magnitude": 0.0,
                "neutral_count": 0,
                "positive_count": 0,
                "positive_magnitude": 0.0,
                "net_score": 0.0,
            }

        neg_mag = row["negative_magnitude"] or 0.0
        pos_mag = row["positive_magnitude"] or 0.0

        return {
            "negative_count": row["negative_count"] or 0,
            "negative_magnitude": neg_mag,
            "neutral_count": row["neutral_count"] or 0,
            "positive_count": row["positive_count"] or 0,
            "positive_magnitude": pos_mag,
            "net_score": pos_mag - neg_mag,
        }

    def count_by_category(
        self, client_id: str | None = None, days: int = 30
    ) -> dict[str, dict[str, int]]:
        """
        Count signals by category and valence.

        Args:
            client_id: Optional client filter
            days: Days to look back

        Returns:
            Dict of category -> {negative, neutral, positive}
        """
        conditions = [
            "status = 'active'",
            f"detected_at > datetime('now', '-{days} days')",
        ]
        params = []

        if client_id:
            conditions.append("scope_client_id = ?")
            params.append(client_id)

        where = " AND ".join(conditions)

        rows = self.db.fetch_all(
            f"""
            SELECT
                signal_category,
                valence,
                COUNT(*) as count
            FROM signals_v5
            WHERE {where}
            GROUP BY signal_category, valence
        """,
            tuple(params),
        )

        result = {}
        for row in rows:
            cat = row["signal_category"]
            if cat not in result:
                result[cat] = {"negative": 0, "neutral": 0, "positive": 0}

            if row["valence"] == -1:
                result[cat]["negative"] = row["count"]
            elif row["valence"] == 0:
                result[cat]["neutral"] = row["count"]
            else:
                result[cat]["positive"] = row["count"]

        return result
