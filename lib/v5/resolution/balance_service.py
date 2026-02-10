"""
Time OS V5 — Balance Service

Handles signal balancing logic.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from ..database import Database
from ..models import Signal, now_iso
from ..repositories.signal_repository import SignalRepository
from .balance_rules import (
    BALANCE_PAIRS,
    SUSTAINED_BALANCE_COUNT,
    SUSTAINED_BALANCE_DAYS,
    ScopeMatchRule,
    can_balance,
    get_balancing_types,
    get_scope_match_rule,
    requires_sustained_balance,
)

logger = logging.getLogger(__name__)


class BalanceService:
    """
    Handles signal balancing logic.

    When a positive signal arrives, checks if it can balance
    any existing negative signals based on:
    - Balance rules (which types can balance which)
    - Scope matching (same entity, client, etc.)
    - Sustained balance requirements
    """

    def __init__(self, db: Database):
        """
        Initialize balance service.

        Args:
            db: Database instance
        """
        self.db = db
        self.repo = SignalRepository(db)

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    def process_new_signal(self, signal) -> list[str]:
        """
        Process a new signal and check for balancing.

        If the signal is positive, checks if it can balance any
        existing negative signals.

        Args:
            signal: New signal (Signal object or dict)

        Returns:
            List of signal IDs that were balanced
        """
        # Handle dict or Signal object
        if isinstance(signal, dict):
            valence = signal.get("valence")
            signal.get("id")
            signal.get("signal_type")
        else:
            valence = signal.valence

        # Only positive signals can balance
        if valence != 1:
            return []

        balanced_ids = []

        # Find negative signals this could potentially balance
        candidates = self._find_balance_candidates(signal)

        for neg_signal in candidates:
            if self._can_balance_signal(signal, neg_signal):
                self._mark_balanced(neg_signal.id, signal.id)
                balanced_ids.append(neg_signal.id)
                logger.info(
                    f"Signal {neg_signal.id} ({neg_signal.signal_type}) balanced by {signal.id} ({signal.signal_type})"
                )

        # Recalculate affected issues if any signals were balanced
        if balanced_ids:
            self._recalculate_affected_issues(balanced_ids)

        return balanced_ids

    # =========================================================================
    # Find Balance Candidates
    # =========================================================================

    def _find_balance_candidates(self, positive_signal) -> list[dict[str, Any]]:
        """
        Find negative signals that could potentially be balanced.

        Args:
            positive_signal: Positive signal (dict or Signal)

        Returns:
            List of candidate negative signals (as dicts)
        """

        # Normalize to dict access
        def get(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        signal_type = get(positive_signal, "signal_type")
        entity_id = get(positive_signal, "entity_id")
        entity_type = get(positive_signal, "entity_type")

        # Find which negative types this positive can balance
        negative_types_to_check = []
        for neg_type, pos_types in BALANCE_PAIRS.items():
            if signal_type in pos_types:
                negative_types_to_check.append(neg_type)

        if not negative_types_to_check:
            return []

        # Build query based on scope
        # We'll do broad query then filter by specific rules
        conditions = [
            "status = 'active'",
            "valence = -1",
        ]
        params = []

        # Add signal type filter
        placeholders = ",".join(["?" for _ in negative_types_to_check])
        conditions.append(f"signal_type IN ({placeholders})")
        params.extend(negative_types_to_check)

        # Add scope filter - at minimum same client or same entity
        scope_conditions = []

        if entity_id:
            scope_conditions.append("(entity_type = ? AND entity_id = ?)")
            params.extend([entity_type, entity_id])

        scope_client_id = get(positive_signal, "scope_client_id")
        if scope_client_id:
            scope_conditions.append("scope_client_id = ?")
            params.append(scope_client_id)

        if scope_conditions:
            conditions.append(f"({' OR '.join(scope_conditions)})")

        where = " AND ".join(conditions)

        return self.db.fetch_all(
            f"""
            SELECT * FROM signals_v5
            WHERE {where}
            ORDER BY detected_at DESC
        """,
            tuple(params),
        )

    # =========================================================================
    # Balance Checks
    # =========================================================================

    def _can_balance_signal(self, positive, negative) -> bool:
        """
        Check if a positive signal can balance a negative signal.

        Args:
            positive: Positive signal (dict)
            negative: Negative signal (dict)

        Returns:
            True if balance is possible
        """

        def get(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        pos_type = get(positive, "signal_type")
        neg_type = get(negative, "signal_type")

        # 1. Check balance rules
        if not can_balance(neg_type, pos_type):
            return False

        # 2. Check scope matching
        if not self._check_scope_match(positive, negative):
            return False

        # 3. Check sustained balance requirement
        return not (
            requires_sustained_balance(neg_type)
            and not self._check_sustained_balance(negative, positive)
        )

    def _check_scope_match(self, positive, negative) -> bool:
        """
        Check if signals match according to scope rules.

        Args:
            positive: Positive signal (dict)
            negative: Negative signal (dict)

        Returns:
            True if scope matches
        """

        def get(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        neg_type = get(negative, "signal_type")
        rule = get_scope_match_rule(neg_type)

        pos_entity_type = get(positive, "entity_type")
        pos_entity_id = get(positive, "entity_id")
        neg_entity_type = get(negative, "entity_type")
        neg_entity_id = get(negative, "entity_id")

        if rule == ScopeMatchRule.EXACT_ENTITY:
            # Must be same entity type and ID
            return pos_entity_type == neg_entity_type and pos_entity_id == neg_entity_id

        if rule == ScopeMatchRule.SAME_PROJECT:
            # Same project (or exact entity match)
            if pos_entity_type == neg_entity_type and pos_entity_id == neg_entity_id:
                return True
            return (
                positive.scope_project_id is not None
                and positive.scope_project_id == negative.scope_project_id
            )

        if rule == ScopeMatchRule.SAME_BRAND:
            # Same brand
            if (
                positive.entity_type == negative.entity_type
                and positive.entity_id == negative.entity_id
            ):
                return True
            return (
                positive.scope_brand_id is not None
                and positive.scope_brand_id == negative.scope_brand_id
            )

        if rule == ScopeMatchRule.SAME_CLIENT:
            # Same client
            if (
                positive.entity_type == negative.entity_type
                and positive.entity_id == negative.entity_id
            ):
                return True
            return (
                positive.scope_client_id is not None
                and positive.scope_client_id == negative.scope_client_id
            )

        # Default: same client
        return (
            positive.scope_client_id is not None
            and positive.scope_client_id == negative.scope_client_id
        )

    def _check_sustained_balance(self, negative: Signal, new_positive: Signal) -> bool:
        """
        Check if sustained balance requirement is met.

        For signals that require sustained positivity (e.g., sentiment_negative),
        we need multiple positive signals over a period of time.

        Args:
            negative: Negative signal to balance
            new_positive: New positive signal being evaluated

        Returns:
            True if sustained balance is met
        """
        # Get balancing types for this negative signal
        balancing_types = get_balancing_types(negative.signal_type)
        if not balancing_types:
            return False

        # Calculate cutoff date
        cutoff = (datetime.now() - timedelta(days=SUSTAINED_BALANCE_DAYS)).isoformat()

        # Count recent positive signals of balancing types for same scope
        placeholders = ",".join(["?" for _ in balancing_types])

        row = self.db.fetch_one(
            f"""
            SELECT COUNT(*) as count
            FROM signals_v5
            WHERE signal_type IN ({placeholders})
              AND valence = 1
              AND detected_at >= ?
              AND scope_client_id = ?
              AND status IN ('active', 'consumed')
        """,
            tuple(balancing_types) + (cutoff, negative.scope_client_id),
        )

        count = row["count"] if row else 0

        # +1 for the new signal we're processing
        total_count = count + 1

        return total_count >= SUSTAINED_BALANCE_COUNT

    # =========================================================================
    # Mark Balanced
    # =========================================================================

    def _mark_balanced(self, signal_id: str, by_signal_id: str) -> None:
        """
        Mark a signal as balanced.

        Args:
            signal_id: Signal to mark balanced
            by_signal_id: Signal that balanced it
        """
        self.repo.mark_balanced(signal_id, by_signal_id)

    # =========================================================================
    # Issue Recalculation
    # =========================================================================

    def _recalculate_affected_issues(self, balanced_signal_ids: list[str]) -> None:
        """
        Recalculate issues affected by balanced signals.

        Args:
            balanced_signal_ids: List of signal IDs that were balanced
        """
        # Find issues containing these signals
        for signal_id in balanced_signal_ids:
            rows = self.db.fetch_all(
                """
                SELECT id, signal_ids
                FROM issues_v5
                WHERE signal_ids LIKE ?
                  AND state NOT IN ('closed')
            """,
                (f"%{signal_id}%",),
            )

            for row in rows:
                self._recalculate_issue_balance(row["id"])

    def _recalculate_issue_balance(self, issue_id: str) -> None:
        """
        Recalculate balance for a specific issue.

        Args:
            issue_id: Issue ID
        """
        import json

        # Get issue and its signals
        issue_row = self.db.fetch_one(
            """
            SELECT id, signal_ids, state
            FROM issues_v5
            WHERE id = ?
        """,
            (issue_id,),
        )

        if not issue_row:
            return

        signal_ids = json.loads(issue_row["signal_ids"] or "[]")
        if not signal_ids:
            return

        # Calculate balance from active signals only
        placeholders = ",".join(["?" for _ in signal_ids])
        balance_row = self.db.fetch_one(
            f"""
            SELECT
                SUM(CASE WHEN valence = -1 AND status = 'active' THEN
                    magnitude * CASE
                        WHEN julianday('now') - julianday(detected_at) > 365 THEN 0.1
                        WHEN julianday('now') - julianday(detected_at) > 180 THEN 0.25
                        WHEN julianday('now') - julianday(detected_at) > 90 THEN 0.5
                        WHEN julianday('now') - julianday(detected_at) > 30 THEN 0.8
                        ELSE 1.0
                    END
                ELSE 0 END) as neg_mag,
                SUM(CASE WHEN valence = 1 AND status = 'active' THEN
                    magnitude * CASE
                        WHEN julianday('now') - julianday(detected_at) > 365 THEN 0.1
                        WHEN julianday('now') - julianday(detected_at) > 180 THEN 0.25
                        WHEN julianday('now') - julianday(detected_at) > 90 THEN 0.5
                        WHEN julianday('now') - julianday(detected_at) > 30 THEN 0.8
                        ELSE 1.0
                    END
                ELSE 0 END) as pos_mag,
                SUM(CASE WHEN valence = -1 AND status = 'active' THEN 1 ELSE 0 END) as neg_count,
                SUM(CASE WHEN valence = 1 AND status = 'active' THEN 1 ELSE 0 END) as pos_count
            FROM signals_v5
            WHERE id IN ({placeholders})
        """,
            tuple(signal_ids),
        )

        neg_mag = balance_row["neg_mag"] or 0
        pos_mag = balance_row["pos_mag"] or 0
        net_score = pos_mag - neg_mag

        # Update issue balance
        self.db.update(
            "issues_v5",
            {
                "balance_negative_magnitude": neg_mag,
                "balance_positive_magnitude": pos_mag,
                "balance_negative_count": balance_row["neg_count"] or 0,
                "balance_positive_count": balance_row["pos_count"] or 0,
                "balance_net_score": net_score,
                "updated_at": now_iso(),
            },
            "id = ?",
            [issue_id],
        )

        # Check if issue should auto-resolve
        if net_score >= 0 and issue_row["state"] == "addressing":
            self._maybe_auto_resolve(issue_id)

    def _maybe_auto_resolve(self, issue_id: str) -> None:
        """
        Check if an issue should auto-resolve.

        Args:
            issue_id: Issue ID
        """
        issue = self.db.fetch_one(
            """
            SELECT state, balance_net_score
            FROM issues_v5
            WHERE id = ?
        """,
            (issue_id,),
        )

        if not issue:
            return

        # Only auto-resolve if actively being addressed and balance is positive
        if issue["state"] == "addressing" and issue["balance_net_score"] >= 0:
            now = datetime.now()
            monitoring_until = (now + timedelta(days=90)).isoformat()

            self.db.update(
                "issues_v5",
                {
                    "state": "monitoring",
                    "resolved_at": now.isoformat(),
                    "resolution_method": "signals_balanced",
                    "monitoring_until": monitoring_until,
                    "updated_at": now.isoformat(),
                },
                "id = ?",
                [issue_id],
            )

            logger.info(f"Issue {issue_id} auto-resolved due to balanced signals")

    # =========================================================================
    # Batch Balancing
    # =========================================================================

    def run_balance_check(self) -> dict[str, int]:
        """
        Run balance check for all active positive signals.

        This is useful for catching up after initial data load.

        Returns:
            Dict with stats
        """
        stats = {"checked": 0, "balanced": 0}

        # Get active positive signals
        rows = self.db.fetch_all("""
            SELECT * FROM signals_v5
            WHERE status = 'active'
              AND valence = 1
            ORDER BY detected_at DESC
            LIMIT 1000
        """)

        for row in rows:
            signal = Signal.from_row(row)
            balanced = self.process_new_signal(signal)
            stats["checked"] += 1
            stats["balanced"] += len(balanced)

        logger.info(
            f"Balance check complete: {stats['checked']} checked, {stats['balanced']} balanced"
        )
        return stats
