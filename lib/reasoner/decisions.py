"""
Decision Maker - Creates decisions based on insights and anomalies.
"""

import json
import logging
from datetime import datetime
from uuid import uuid4

from ..governance import GovernanceEngine, get_governance
from ..state_store import StateStore, get_store

logger = logging.getLogger(__name__)


class DecisionMaker:
    """
    Creates decisions from insights and anomalies.

    This is WIRING POINT #8:
    Insights/Anomalies → Decisions → Governance → Execute or Approve
    """

    def __init__(self, store: StateStore = None, governance: GovernanceEngine = None):
        self.store = store or get_store()
        self.governance = governance or get_governance()

    def process_insights(self) -> list[dict]:
        """Process actionable insights and create decisions."""
        decisions = []

        # Get actionable insights that haven't been acted on
        insights = self.store.query("""
            SELECT * FROM insights
            WHERE actionable = 1 AND action_taken = 0
            AND (expires_at IS NULL OR datetime(expires_at) > datetime('now'))
            ORDER BY created_at DESC
        """)

        for insight in insights:
            decision = self._create_decision_from_insight(insight)
            if decision:
                decisions.append(decision)
                # Mark insight as processed
                self.store.update("insights", insight["id"], {"action_taken": 1})

        return decisions

    def _create_decision_from_insight(self, insight: dict) -> dict | None:
        """Create a decision from an insight."""
        insight_type = insight.get("type", "")
        insight.get("domain", "")
        data = {}
        if insight.get("data"):
            try:
                data = json.loads(insight.get("data", "{}"))
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Could not parse insight data JSON: {e}")

        decision = None

        # Handle schedule conflicts
        if "schedule_conflict" in insight_type or "Overlap" in insight.get("title", ""):
            decision = self._create_conflict_decision(insight, data)

        # Handle overdue tasks
        elif "overdue" in insight_type.lower():
            decision = self._create_overdue_decision(insight, data)

        # Handle email backlog
        elif "email_backlog" in insight_type:
            decision = self._create_email_decision(insight, data)

        # Handle deadline warnings
        elif "deadline" in insight_type.lower():
            decision = self._create_deadline_decision(insight, data)

        if decision:
            self._store_decision(decision)

        return decision

    def _create_conflict_decision(self, insight: dict, data: dict) -> dict:
        """Create decision for schedule conflict."""
        return {
            "domain": "calendar",
            "decision_type": "conflict_resolution",
            "description": insight.get("title", "Schedule conflict detected"),
            "input_data": data,
            "options": [
                {"action": "reschedule_second", "label": "Reschedule second event"},
                {"action": "decline_second", "label": "Decline second event"},
                {"action": "notify_attendees", "label": "Notify attendees of conflict"},
                {"action": "ignore", "label": "Ignore (handle manually)"},
            ],
            "selected_option": "notify_attendees",
            "rationale": "Calendar conflict needs resolution",
            "confidence": 0.9,
            "requires_approval": True,
        }

    def _create_overdue_decision(self, insight: dict, data: dict) -> dict:
        """Create decision for overdue tasks."""
        task_ids = data.get("tasks", [])
        severity = "critical" if "critical" in insight.get("type", "") else "high"

        return {
            "domain": "tasks",
            "decision_type": "overdue_handling",
            "description": insight.get("title", "Overdue tasks need attention"),
            "input_data": data,
            "options": [
                {"action": "escalate", "label": "Escalate to priority"},
                {"action": "reschedule", "label": "Reschedule deadlines"},
                {"action": "delegate", "label": "Delegate tasks"},
                {"action": "notify", "label": "Send reminder notification"},
            ],
            "selected_option": "notify",
            "rationale": f"{len(task_ids)} tasks are overdue",
            "confidence": 0.85,
            "requires_approval": severity == "critical",
        }

    def _create_email_decision(self, insight: dict, data: dict) -> dict:
        """Create decision for email backlog."""
        count = data.get("count", 0)

        return {
            "domain": "email",
            "decision_type": "backlog_handling",
            "description": insight.get("title", "Email backlog building up"),
            "input_data": data,
            "options": [
                {"action": "batch_archive", "label": "Archive low-priority emails"},
                {"action": "create_tasks", "label": "Create tasks for responses"},
                {"action": "notify", "label": "Send reminder notification"},
            ],
            "selected_option": "notify",
            "rationale": f"{count} emails awaiting response",
            "confidence": 0.7,
            "requires_approval": True,
        }

    def _create_deadline_decision(self, insight: dict, data: dict) -> dict:
        """Create decision for upcoming deadlines."""
        return {
            "domain": "tasks",
            "decision_type": "deadline_reminder",
            "description": insight.get("title", "Upcoming deadlines"),
            "input_data": data,
            "options": [
                {"action": "notify", "label": "Send reminder"},
                {"action": "block_calendar", "label": "Block time on calendar"},
                {"action": "ignore", "label": "Ignore"},
            ],
            "selected_option": "notify",
            "rationale": "Deadline approaching soon",
            "confidence": 0.8,
            "requires_approval": False,
        }

    def _store_decision(self, decision: dict) -> str:
        """Store decision in database."""
        decision_id = f"decision_{uuid4().hex[:8]}"

        # Check governance
        can_auto, reason = self.governance.can_execute(
            domain=decision["domain"],
            action=decision["decision_type"],
            context={"confidence": decision.get("confidence", 0)},
        )

        confidence = decision.get("confidence", 0.5)
        domain_config = self.governance.get_domain_config(decision["domain"])
        threshold = domain_config.get("auto_threshold", 0.8)
        mode = domain_config.get("mode", "observe")

        # Auto-approve if:
        # 1. Governance mode is auto_low or auto
        # 2. Confidence meets threshold
        # 3. OR governance explicitly allows (can_auto) and doesn't require approval
        approved = None
        auto_approved = False

        if (
            mode in ("auto_low", "auto")
            and confidence >= threshold
            or can_auto
            and not decision.get("requires_approval")
        ):
            approved = 1
            auto_approved = True

        self.store.insert(
            "decisions",
            {
                "id": decision_id,
                "domain": decision["domain"],
                "decision_type": decision["decision_type"],
                "description": decision.get("description", ""),
                "input_data": json.dumps(decision.get("input_data", {})),
                "options": json.dumps(decision.get("options", [])),
                "selected_option": json.dumps(decision.get("selected_option")),
                "rationale": decision.get("rationale", ""),
                "confidence": confidence,
                "requires_approval": 1 if decision.get("requires_approval") else 0,
                "approved": approved,
                "approved_at": datetime.now().isoformat() if approved else None,
                "created_at": datetime.now().isoformat(),
            },
        )

        decision["id"] = decision_id

        # If auto-approved, create the action immediately
        if auto_approved:
            self._create_action_from_decision(
                {
                    "id": decision_id,
                    "domain": decision["domain"],
                    "decision_type": decision["decision_type"],
                    "selected_option": decision.get("selected_option"),
                    "input_data": json.dumps(decision.get("input_data", {})),
                }
            )

        return decision_id

    def get_pending_decisions(self) -> list[dict]:
        """Get decisions awaiting approval."""
        return self.store.get_pending_decisions()

    def approve_decision(self, decision_id: str) -> bool:
        """Approve a pending decision."""
        decision = self.store.get("decisions", decision_id)
        if not decision:
            return False

        self.store.update(
            "decisions",
            decision_id,
            {"approved": 1, "approved_at": datetime.now().isoformat()},
        )

        # Create action for execution
        self._create_action_from_decision(decision)
        return True

    def reject_decision(self, decision_id: str) -> bool:
        """Reject a pending decision."""
        decision = self.store.get("decisions", decision_id)
        if not decision:
            return False

        self.store.update(
            "decisions",
            decision_id,
            {"approved": 0, "approved_at": datetime.now().isoformat()},
        )
        return True

    def _create_action_from_decision(self, decision: dict):
        """Create an action from an approved decision."""
        action_id = f"action_{uuid4().hex[:8]}"

        selected = decision.get("selected_option", "")
        if isinstance(selected, str):
            try:
                selected = json.loads(selected)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Could not parse selected_option as JSON: {e}")

        input_data = {}
        if decision.get("input_data"):
            try:
                input_data = json.loads(decision.get("input_data", "{}"))
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Could not parse input_data JSON: {e}")

        payload = {
            "decision_id": decision["id"],
            "action": selected.get("action")
            if isinstance(selected, dict)
            else selected,
            "data": input_data,
        }

        self.store.insert(
            "actions",
            {
                "id": action_id,
                "type": f"{decision['domain']}_{decision['decision_type']}",
                "target_system": decision["domain"],
                "payload": json.dumps(payload),
                "status": "approved",
                "requires_approval": 0,
                "approved_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
            },
        )
