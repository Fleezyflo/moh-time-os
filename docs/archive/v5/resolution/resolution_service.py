"""
Time OS V5 — Resolution Service

Handles issue resolution, monitoring, and regression detection.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from ..database import Database
from ..models import ResolutionMethod, now_iso
from ..repositories.signal_repository import SignalRepository

logger = logging.getLogger(__name__)


class ResolutionService:
    """
    Handles issue resolution and monitoring.

    Responsibilities:
    - Resolve issues (manual, auto, or balanced)
    - Manage 90-day monitoring period
    - Detect regressions
    - Close issues after successful monitoring
    """

    # Monitoring period after resolution
    MONITORING_DAYS = 90

    # Regression thresholds
    REGRESSION_SIGNAL_COUNT = 3
    REGRESSION_MAGNITUDE = 1.5

    def __init__(self, db: Database):
        """
        Initialize resolution service.

        Args:
            db: Database instance
        """
        self.db = db
        self.signal_repo = SignalRepository(db)

    # =========================================================================
    # Manual Resolution
    # =========================================================================

    def resolve_issue(
        self,
        issue_id: str,
        method: ResolutionMethod,
        resolved_by: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """
        Resolve an issue and start monitoring period.

        Args:
            issue_id: Issue ID
            method: Resolution method
            resolved_by: User who resolved
            notes: Resolution notes

        Returns:
            True if resolved
        """
        # Get issue
        issue = self.db.fetch_one(
            """
            SELECT id, state FROM issues_v5 WHERE id = ?
        """,
            (issue_id,),
        )

        if not issue:
            logger.warning(f"Issue {issue_id} not found")
            return False

        if issue["state"] not in ("detected", "surfaced", "acknowledged", "addressing"):
            logger.warning(
                f"Issue {issue_id} cannot be resolved from state {issue['state']}"
            )
            return False

        now = datetime.now()
        monitoring_until = (now + timedelta(days=self.MONITORING_DAYS)).isoformat()

        # Update to resolved, then monitoring
        self.db.update(
            "issues_v5",
            {
                "state": "monitoring",
                "resolved_at": now.isoformat(),
                "resolution_method": method.value
                if hasattr(method, "value")
                else method,
                "resolved_by": resolved_by,
                "resolution_notes": notes,
                "monitoring_until": monitoring_until,
                "updated_at": now.isoformat(),
            },
            "id = ?",
            [issue_id],
        )

        # Record state history
        self._record_state_change(issue_id, "resolved", resolved_by)
        self._record_state_change(issue_id, "monitoring", resolved_by)

        logger.info(
            f"Issue {issue_id} resolved via {method}, monitoring until {monitoring_until}"
        )

        return True

    def dismiss_issue(
        self, issue_id: str, dismissed_by: str, reason: str | None = None
    ) -> bool:
        """
        Dismiss an issue as not relevant (false positive).

        Args:
            issue_id: Issue ID
            dismissed_by: User who dismissed
            reason: Dismissal reason

        Returns:
            True if dismissed
        """
        issue = self.db.fetch_one(
            """
            SELECT id, state FROM issues_v5 WHERE id = ?
        """,
            (issue_id,),
        )

        if not issue:
            return False

        if issue["state"] in ("closed", "monitoring"):
            return False

        now = now_iso()

        self.db.update(
            "issues_v5",
            {
                "state": "closed",
                "resolved_at": now,
                "resolution_method": "dismissed",
                "resolved_by": dismissed_by,
                "resolution_notes": reason,
                "closed_at": now,
                "updated_at": now,
            },
            "id = ?",
            [issue_id],
        )

        self._record_state_change(issue_id, "closed", dismissed_by)

        logger.info(f"Issue {issue_id} dismissed by {dismissed_by}")

        return True

    # =========================================================================
    # Regression Detection
    # =========================================================================

    def check_regressions(self) -> list[str]:
        """
        Check for issues in monitoring that are regressing.

        Returns:
            List of issue IDs that regressed
        """
        regressed_ids = []

        # Find issues in monitoring state
        issues = self.db.fetch_all("""
            SELECT id, scope_type, scope_id, issue_subtype,
                   resolved_at, monitoring_until
            FROM issues_v5
            WHERE state = 'monitoring'
              AND datetime(monitoring_until) > datetime('now')
        """)

        for issue in issues:
            if self._check_regression(issue):
                self._reopen_issue(issue["id"])
                regressed_ids.append(issue["id"])

        # Close issues that completed monitoring without regression
        closed_count = self._close_completed_monitoring()

        if regressed_ids:
            logger.info(f"Detected {len(regressed_ids)} regressions")
        if closed_count:
            logger.info(f"Closed {closed_count} issues after monitoring")

        return regressed_ids

    def _check_regression(self, issue: dict[str, Any]) -> bool:
        """
        Check if an issue is regressing.

        Regression = new negative signals since resolution that exceed thresholds.
        """
        resolved_at = issue["resolved_at"]
        scope_type = issue["scope_type"]
        scope_id = issue["scope_id"]

        # Query new negative signals since resolution
        scope_column = f"scope_{scope_type}_id"

        row = self.db.fetch_one(
            f"""
            SELECT
                COUNT(*) as count,
                SUM(magnitude *
                    CASE
                        WHEN julianday('now') - julianday(detected_at) > 365 THEN 0.1
                        WHEN julianday('now') - julianday(detected_at) > 180 THEN 0.25
                        WHEN julianday('now') - julianday(detected_at) > 90 THEN 0.5
                        WHEN julianday('now') - julianday(detected_at) > 30 THEN 0.8
                        ELSE 1.0
                    END
                ) as magnitude
            FROM signals_v5
            WHERE status = 'active'
              AND valence = -1
              AND detected_at > ?
              AND {scope_column} = ?
        """,
            (resolved_at, scope_id),
        )

        if not row:
            return False

        count = row["count"] or 0
        magnitude = row["magnitude"] or 0

        # Check thresholds
        return (
            count >= self.REGRESSION_SIGNAL_COUNT
            or magnitude >= self.REGRESSION_MAGNITUDE
        )

    def _reopen_issue(self, issue_id: str) -> None:
        """Reopen an issue due to regression."""

        now = now_iso()

        self.db.update(
            "issues_v5",
            {
                "state": "surfaced",
                "regression_count": self.db.fetch_value(
                    "SELECT regression_count + 1 FROM issues_v5 WHERE id = ?",
                    (issue_id,),
                ),
                "last_regression_at": now,
                "resolved_at": None,
                "resolution_method": None,
                "monitoring_until": None,
                "updated_at": now,
            },
            "id = ?",
            [issue_id],
        )

        self._record_state_change(issue_id, "surfaced", None)

        logger.warning(f"Issue {issue_id} regressed and reopened")

    def _close_completed_monitoring(self) -> int:
        """Close issues that completed monitoring without regression."""

        now = now_iso()

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE issues_v5
                SET state = 'closed',
                    closed_at = ?,
                    updated_at = ?
                WHERE state = 'monitoring'
                  AND datetime(monitoring_until) <= datetime('now')
            """,
                (now, now),
            )

            return cursor.rowcount

    # =========================================================================
    # Issue State Management
    # =========================================================================

    def acknowledge_issue(self, issue_id: str, user_id: str) -> bool:
        """Mark an issue as acknowledged."""

        issue = self.db.fetch_one(
            "SELECT state FROM issues_v5 WHERE id = ?", (issue_id,)
        )

        if not issue or issue["state"] != "surfaced":
            return False

        now = now_iso()

        self.db.update(
            "issues_v5",
            {
                "state": "acknowledged",
                "acknowledged_at": now,
                "acknowledged_by": user_id,
                "updated_at": now,
            },
            "id = ?",
            [issue_id],
        )

        self._record_state_change(issue_id, "acknowledged", user_id)

        return True

    def start_addressing(self, issue_id: str, user_id: str | None = None) -> bool:
        """Mark an issue as being addressed."""

        issue = self.db.fetch_one(
            "SELECT state FROM issues_v5 WHERE id = ?", (issue_id,)
        )

        if not issue or issue["state"] not in ("surfaced", "acknowledged"):
            return False

        now = now_iso()

        self.db.update(
            "issues_v5",
            {
                "state": "addressing",
                "addressing_started_at": now,
                "updated_at": now,
            },
            "id = ?",
            [issue_id],
        )

        self._record_state_change(issue_id, "addressing", user_id)

        return True

    # =========================================================================
    # History Tracking
    # =========================================================================

    def _record_state_change(
        self, issue_id: str, new_state: str, by: str | None
    ) -> None:
        """Record state change in history."""

        issue = self.db.fetch_one(
            "SELECT state_history FROM issues_v5 WHERE id = ?", (issue_id,)
        )

        if not issue:
            return

        history = json.loads(issue["state_history"] or "[]")
        history.append({"state": new_state, "timestamp": now_iso(), "by": by})

        self.db.update(
            "issues_v5", {"state_history": json.dumps(history)}, "id = ?", [issue_id]
        )

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def run_resolution_check(self) -> dict[str, int]:
        """
        Run resolution check for addressing issues.

        Checks if any issues should auto-resolve due to balanced signals.

        Returns:
            Dict with stats
        """
        stats = {"checked": 0, "auto_resolved": 0}

        # Find issues being addressed
        issues = self.db.fetch_all("""
            SELECT id, balance_net_score
            FROM issues_v5
            WHERE state = 'addressing'
        """)

        for issue in issues:
            stats["checked"] += 1

            # Auto-resolve if balance is positive
            if issue["balance_net_score"] >= 0:
                self.resolve_issue(issue["id"], ResolutionMethod.SIGNALS_BALANCED)
                stats["auto_resolved"] += 1

        return stats
