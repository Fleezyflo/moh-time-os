"""
Debt Tracker - Track and resolve time debt for lanes.

Responsibilities:
- Accrue new time debt for lanes
- Resolve existing debt
- Generate debt reports per lane
"""

import logging
from datetime import datetime

from lib.capacity_truth.calculator import CapacityCalculator
from lib.state_store import get_store

logger = logging.getLogger(__name__)


class DebtTracker:
    """
    Manages time debt for work lanes.
    """

    def __init__(self, store=None):
        self.store = store or get_store()
        self.calculator = CapacityCalculator(self.store)

    def accrue_debt(
        self, lane: str, amount: int, reason: str, source_task_id: str | None = None
    ) -> str:
        """
        Accrue new time debt for a lane.

        Args:
            lane: Lane id
            amount: Minutes of debt
            reason: Reason for debt (e.g., overflow, missed)
            source_task_id: Optional task that caused debt
        Returns:
            debt_id
        """
        debt_id = f"debt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{lane}"
        now = datetime.now().isoformat()
        data = {
            "id": debt_id,
            "lane": lane,
            "amount_min": amount,
            "reason": reason,
            "source_task_id": source_task_id,
            "incurred_at": now,
            "resolved_at": None,
        }
        self.store.insert("time_debt", data)
        return debt_id

    def resolve_debt(self, debt_id: str) -> tuple[bool, str]:
        """
        Mark a debt entry as resolved.

        Args:
            debt_id: ID of debt to resolve
        Returns:
            (success, message)
        """
        rows = self.store.query("SELECT * FROM time_debt WHERE id = ?", [debt_id])
        if not rows:
            return False, "Debt entry not found"
        now = datetime.now().isoformat()
        self.store.query("UPDATE time_debt SET resolved_at = ? WHERE id = ?", [now, debt_id])
        return True, "Debt resolved"

    def get_debt_report(self, lane: str | None = None) -> dict:
        """
        Generate a report of time debt per lane or overall.

        Args:
            lane: Specific lane id (optional)
        Returns:
            Report dict with totals and entries
        """
        params = []
        q = "SELECT * FROM time_debt"
        if lane:
            q += " WHERE lane = ?"
            params.append(lane)
        q += " ORDER BY incurred_at DESC"
        rows = self.store.query(q, params)

        total_open = sum(r["amount_min"] for r in rows if r["resolved_at"] is None)
        total_resolved = sum(r["amount_min"] for r in rows if r["resolved_at"] is not None)

        entries = []
        for r in rows:
            entries.append(
                {
                    "id": r["id"],
                    "lane": r["lane"],
                    "amount_min": r["amount_min"],
                    "reason": r["reason"],
                    "source_task_id": r["source_task_id"],
                    "incurred_at": r["incurred_at"],
                    "resolved_at": r["resolved_at"],
                }
            )

        return {
            "lane": lane,
            "total_open_min": total_open,
            "total_resolved_min": total_resolved,
            "entries": entries,
        }


# Test
if __name__ == "__main__":
    tracker = DebtTracker()
    logger.info("Testing DebtTracker")
    logger.info("-" * 40)
    # Accrue debt
    debt_id = tracker.accrue_debt("ops", 30, "Missed deadline", source_task_id="task_123")
    logger.info(f"Accrued debt: {debt_id}")
    # Report
    report = tracker.get_debt_report("ops")
    logger.info(f"Report open: {report['total_open_min']} min")
    # Resolve
    success, msg = tracker.resolve_debt(debt_id)
    logger.info(f"Resolve: {success}, {msg}")
    report2 = tracker.get_debt_report("ops")
    logger.info(
        f"Report after resolve open: {report2['total_open_min']} min, resolved: {report2['total_resolved_min']} min"
    )
