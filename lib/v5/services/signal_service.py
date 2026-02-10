"""
Time OS V5 — Signal Service

Business logic for signal operations.
"""

import logging
from typing import Any

from ..database import Database
from ..models import Signal, SignalBalance, SignalStatus
from ..repositories.signal_repository import SignalRepository

logger = logging.getLogger(__name__)


class SignalService:
    """
    Service for signal operations.

    Handles validation, enrichment, storage, and retrieval of signals.
    """

    def __init__(self, db: Database):
        """
        Initialize service.

        Args:
            db: Database instance
        """
        self.db = db
        self.repo = SignalRepository(db)

    # =========================================================================
    # Signal Storage
    # =========================================================================

    def store_signal(self, signal: Signal) -> str:
        """
        Validate, enrich, and store a signal.

        Args:
            signal: Signal to store

        Returns:
            Signal ID

        Raises:
            ValueError: If signal is invalid
        """
        # Validate
        if not signal.validate():
            raise ValueError(f"Invalid signal: {signal.signal_type}")

        # Enrich scope chain if needed
        signal = self._enrich_scope(signal)

        # Store
        signal_id = self.repo.insert(signal)

        logger.debug(
            f"Stored signal {signal_id}: {signal.signal_type} ({signal.valence})"
        )

        return signal_id

    def store_signals(self, signals: list[Signal]) -> dict[str, int]:
        """
        Store multiple signals.

        Args:
            signals: List of signals

        Returns:
            Dict with stored count and error count
        """
        stored = 0
        errors = 0

        for signal in signals:
            try:
                self.store_signal(signal)
                stored += 1
            except Exception as e:
                logger.error(f"Failed to store signal {signal.signal_type}: {e}")
                errors += 1

        return {"stored": stored, "errors": errors}

    def _enrich_scope(self, signal: Signal) -> Signal:
        """
        Enrich signal with scope chain if missing.

        Args:
            signal: Signal to enrich

        Returns:
            Enriched signal
        """
        # If we have task scope, fill in the rest
        if signal.scope_task_id and not signal.scope_client_id:
            row = self.db.fetch_one(
                """
                SELECT project_id, retainer_cycle_id, brand_id, client_id, assignee_id
                FROM tasks_v5 WHERE id = ?
            """,
                (signal.scope_task_id,),
            )

            if row:
                signal.scope_project_id = signal.scope_project_id or row["project_id"]
                signal.scope_retainer_id = (
                    signal.scope_retainer_id or row["retainer_cycle_id"]
                )
                signal.scope_brand_id = signal.scope_brand_id or row["brand_id"]
                signal.scope_client_id = signal.scope_client_id or row["client_id"]
                signal.scope_person_id = signal.scope_person_id or row["assignee_id"]

        # If we have project scope, fill in brand/client
        elif signal.scope_project_id and not signal.scope_client_id:
            row = self.db.fetch_one(
                """
                SELECT brand_id, client_id FROM projects_v5 WHERE id = ?
            """,
                (signal.scope_project_id,),
            )

            if row:
                signal.scope_brand_id = signal.scope_brand_id or row["brand_id"]
                signal.scope_client_id = signal.scope_client_id or row["client_id"]

        # If we have brand scope, fill in client
        elif signal.scope_brand_id and not signal.scope_client_id:
            row = self.db.fetch_one(
                """
                SELECT client_id FROM brands WHERE id = ?
            """,
                (signal.scope_brand_id,),
            )

            if row:
                signal.scope_client_id = row["client_id"]

        return signal

    # =========================================================================
    # Signal Retrieval
    # =========================================================================

    def get_signal(self, signal_id: str) -> Signal | None:
        """
        Get a signal by ID.

        Args:
            signal_id: Signal ID

        Returns:
            Signal or None
        """
        return self.repo.get(signal_id)

    def list_signals(
        self,
        status: str | None = "active",
        valence: int | None = None,
        category: str | None = None,
        client_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        days: int = 30,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Signal]:
        """
        List signals with filtering.

        Args:
            status: Status filter
            valence: Valence filter (-1, 0, 1)
            category: Category filter
            client_id: Client ID filter
            entity_type: Entity type filter
            entity_id: Entity ID filter
            days: Signals from last N days
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of signals
        """
        conditions = [f"detected_at > datetime('now', '-{days} days')"]
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if valence is not None:
            conditions.append("valence = ?")
            params.append(valence)

        if category:
            conditions.append("signal_category = ?")
            params.append(category)

        if client_id:
            conditions.append("scope_client_id = ?")
            params.append(client_id)

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)

        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        rows = self.db.fetch_all(
            f"""
            SELECT * FROM signals_v5
            WHERE {where}
            ORDER BY detected_at DESC
            LIMIT ? OFFSET ?
        """,
            tuple(params),
        )

        return [Signal.from_row(row) for row in rows]

    def get_signals_for_entity(
        self, entity_type: str, entity_id: str, include_inactive: bool = False
    ) -> list[Signal]:
        """
        Get all signals for an entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            include_inactive: Include non-active signals

        Returns:
            List of signals
        """
        status = None if include_inactive else "active"
        return self.repo.find_by_entity(entity_type, entity_id, status)

    def get_signals_for_scope(
        self, scope_type: str, scope_id: str, valence: int | None = None
    ) -> list[Signal]:
        """
        Get signals for a scope (client, brand, project, etc.).

        Args:
            scope_type: Scope type
            scope_id: Scope ID
            valence: Optional valence filter

        Returns:
            List of signals
        """
        return self.repo.find_by_scope(scope_type, scope_id, valence=valence)

    # =========================================================================
    # Signal Status Updates
    # =========================================================================

    def update_signal_status(self, signal_id: str, status: SignalStatus) -> bool:
        """
        Update a signal's status.

        Args:
            signal_id: Signal ID
            status: New status

        Returns:
            True if updated
        """
        return self.repo.update(signal_id, {"status": status.value})

    def mark_signals_consumed(self, signal_ids: list[str], issue_id: str) -> int:
        """
        Mark signals as consumed by an issue.

        Args:
            signal_ids: List of signal IDs
            issue_id: Issue ID

        Returns:
            Number updated
        """
        return self.repo.mark_consumed(signal_ids, issue_id)

    def expire_old_signals(self) -> int:
        """
        Expire signals past their expiry date.

        Returns:
            Number of signals expired
        """
        count = self.repo.expire_old_signals()
        if count > 0:
            logger.info(f"Expired {count} signals")
        return count

    # =========================================================================
    # Signal Balance
    # =========================================================================

    def get_balance_for_scope(self, scope_type: str, scope_id: str) -> SignalBalance:
        """
        Get signal balance for a scope.

        Args:
            scope_type: Scope type (client, brand, project, etc.)
            scope_id: Scope ID

        Returns:
            SignalBalance object
        """
        data = self.repo.get_balance_for_scope(scope_type, scope_id)

        return SignalBalance(
            negative_count=data["negative_count"],
            negative_magnitude=data["negative_magnitude"],
            neutral_count=data["neutral_count"],
            positive_count=data["positive_count"],
            positive_magnitude=data["positive_magnitude"],
        )

    def get_balance_for_client(self, client_id: str) -> SignalBalance:
        """Get signal balance for a client."""
        return self.get_balance_for_scope("client", client_id)

    def get_balance_for_project(self, project_id: str) -> SignalBalance:
        """Get signal balance for a project."""
        return self.get_balance_for_scope("project", project_id)

    # =========================================================================
    # Signal Summary
    # =========================================================================

    def get_signal_summary(
        self, client_id: str | None = None, days: int = 30
    ) -> dict[str, Any]:
        """
        Get signal summary with counts by category and valence.

        Args:
            client_id: Optional client filter
            days: Days to include

        Returns:
            Summary dict
        """
        by_category = self.repo.count_by_category(client_id, days)

        # Calculate totals
        total_negative = sum(c["negative"] for c in by_category.values())
        total_neutral = sum(c["neutral"] for c in by_category.values())
        total_positive = sum(c["positive"] for c in by_category.values())

        return {
            "by_category": by_category,
            "totals": {
                "negative": total_negative,
                "neutral": total_neutral,
                "positive": total_positive,
                "total": total_negative + total_neutral + total_positive,
            },
            "net_count": total_positive - total_negative,
            "days": days,
            "client_id": client_id,
        }

    # =========================================================================
    # Entity Name Lookup
    # =========================================================================

    def get_entity_name(self, entity_type: str, entity_id: str) -> str | None:
        """
        Get display name for an entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            Entity name or None
        """
        table_map = {
            "task": ("tasks_v5", "title"),
            "project": ("projects_v5", "name"),
            "retainer": ("retainers", "name"),
            "brand": ("brands", "name"),
            "client": ("clients", "name"),
            "invoice": ("xero_invoices", "invoice_number"),
            "person": ("people", "name"),
        }

        if entity_type not in table_map:
            return None

        table, name_col = table_map[entity_type]

        row = self.db.fetch_one(
            f"SELECT {name_col} as name FROM {table} WHERE id = ?", (entity_id,)
        )

        return row["name"] if row else None

    def enrich_signal_with_names(self, signal: Signal) -> dict[str, Any]:
        """
        Enrich signal dict with entity names.

        Args:
            signal: Signal to enrich

        Returns:
            Dict with signal data plus names
        """
        data = signal.to_dict()

        # Add entity name
        data["entity_name"] = self.get_entity_name(signal.entity_type, signal.entity_id)

        # Add scope names
        if signal.scope_client_id:
            data["client_name"] = self.get_entity_name("client", signal.scope_client_id)
        if signal.scope_project_id:
            data["project_name"] = self.get_entity_name(
                "project", signal.scope_project_id
            )
        if signal.scope_brand_id:
            data["brand_name"] = self.get_entity_name("brand", signal.scope_brand_id)

        return data
