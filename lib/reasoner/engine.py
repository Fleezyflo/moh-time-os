"""
Reasoner Engine - Main orchestrator for decision-making.
"""

import logging
from datetime import datetime
from typing import Any

from ..governance import GovernanceEngine, get_governance
from ..state_store import StateStore, get_store
from .decisions import DecisionMaker

logger = logging.getLogger(__name__)


class ReasonerEngine:
    """
    Main reasoning engine - processes analysis results and creates decisions.

    This is WIRING POINT #9:
    Analysis → Reasoning → Decisions → Governance → Actions
    """

    def __init__(self, store: StateStore = None, governance: GovernanceEngine = None):
        self.store = store or get_store()
        self.governance = governance or get_governance()
        self.decision_maker = DecisionMaker(
            store=self.store, governance=self.governance
        )

    def process_cycle(self) -> dict[str, Any]:
        """
        Run one reasoning cycle.
        Returns summary of decisions made.
        """
        logger.info("Running reasoning cycle")

        results = {
            "timestamp": datetime.now().isoformat(),
            "decisions_created": 0,
            "decisions_auto_approved": 0,
            "decisions_pending": 0,
        }

        # Process actionable insights
        decisions = self.decision_maker.process_insights()
        results["decisions_created"] = len(decisions)

        # Count auto-approved vs pending
        for decision in decisions:
            decision_record = self.store.get("decisions", decision.get("id"))
            if decision_record:
                if decision_record.get("approved") == 1:
                    results["decisions_auto_approved"] += 1
                elif decision_record.get("approved") is None:
                    results["decisions_pending"] += 1

        logger.info(
            f"Reasoning cycle complete: {results['decisions_created']} decisions created"
        )

        return results

    def get_pending_count(self) -> int:
        """Get count of pending decisions."""
        return self.store.count("decisions", "approved IS NULL")

    def get_status(self) -> dict[str, Any]:
        """Get reasoner status."""
        return {
            "pending_decisions": self.get_pending_count(),
            "governance_status": self.governance.get_status(),
            "last_cycle": datetime.now().isoformat(),
        }
