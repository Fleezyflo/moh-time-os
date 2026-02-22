"""
Approval Policies — Configurable rules for auto-approval vs require-human.

Determines which actions auto-approve and which require human review based on:
- Risk level
- Action type
- Entity type
- Confidence score
"""

import logging
from dataclasses import dataclass
from typing import Optional

from lib.actions.action_framework import (
    ActionProposal,
    ApprovalDecision,
    RiskLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRule:
    """Single approval rule."""

    action_type_pattern: str  # e.g., "task_*" or "calendar_create" (wildcard support)
    risk_threshold: RiskLevel  # Risk level at which approval required
    auto_approve: bool  # Auto-approve if <= threshold
    require_two_approvals: bool = False
    cooldown_seconds: int | None = None


class ApprovalPolicy:
    """Approval policy configuration."""

    def __init__(self, rules: list[ApprovalRule]):
        self.rules = rules

    def find_matching_rule(self, proposal: ActionProposal) -> ApprovalRule | None:
        """Find first matching rule for proposal."""
        for rule in self.rules:
            if self._matches_pattern(proposal.type, rule.action_type_pattern):
                if self._check_risk_threshold(proposal.risk_level, rule.risk_threshold):
                    return rule
        return None

    def _matches_pattern(self, action_type: str, pattern: str) -> bool:
        """Check if action type matches pattern (supports wildcards)."""
        if pattern == "*":
            return True
        if not pattern.endswith("*"):
            return action_type == pattern
        # Wildcard: match prefix
        prefix = pattern[:-1]  # Remove trailing *
        return action_type.startswith(prefix)

    def _check_risk_threshold(self, risk_level: RiskLevel, threshold: RiskLevel) -> bool:
        """Check if risk level is at or below threshold."""
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        risk_index = risk_order.index(risk_level)
        threshold_index = risk_order.index(threshold)
        return risk_index <= threshold_index


# Default approval policies
DEFAULT_POLICIES = [
    # Low-risk task actions auto-approve
    ApprovalRule(
        action_type_pattern="task_create", risk_threshold=RiskLevel.LOW, auto_approve=True
    ),
    ApprovalRule(
        action_type_pattern="task_update", risk_threshold=RiskLevel.LOW, auto_approve=True
    ),
    ApprovalRule(
        action_type_pattern="task_snooze", risk_threshold=RiskLevel.LOW, auto_approve=True
    ),
    # Medium-risk calendar actions auto-approve
    ApprovalRule(
        action_type_pattern="calendar_create", risk_threshold=RiskLevel.MEDIUM, auto_approve=True
    ),
    ApprovalRule(
        action_type_pattern="calendar_update", risk_threshold=RiskLevel.MEDIUM, auto_approve=True
    ),
    # High-risk deletions require approval
    ApprovalRule(
        action_type_pattern="task_delete",
        risk_threshold=RiskLevel.CRITICAL,
        auto_approve=False,
        require_two_approvals=True,
    ),
    ApprovalRule(
        action_type_pattern="calendar_delete",
        risk_threshold=RiskLevel.CRITICAL,
        auto_approve=False,
        require_two_approvals=True,
    ),
    # Notifications are low-risk
    ApprovalRule(
        action_type_pattern="notification_*", risk_threshold=RiskLevel.MEDIUM, auto_approve=True
    ),
    # Email actions are medium-risk
    ApprovalRule(action_type_pattern="email_*", risk_threshold=RiskLevel.MEDIUM, auto_approve=True),
    # All critical actions require approval
    ApprovalRule(
        action_type_pattern="*",
        risk_threshold=RiskLevel.CRITICAL,
        auto_approve=False,
        require_two_approvals=True,
    ),
    # Default: require approval for anything not matched
    ApprovalRule(action_type_pattern="*", risk_threshold=RiskLevel.CRITICAL, auto_approve=False),
]


class PolicyEngine:
    """Evaluates approval policies against proposals."""

    def __init__(self, policy: ApprovalPolicy = None):
        self.policy = policy or ApprovalPolicy(DEFAULT_POLICIES)

    def evaluate(self, proposal: ActionProposal) -> ApprovalDecision:
        """
        Evaluate approval policy for proposal.

        Returns ApprovalDecision with approval status and reason.
        """
        # Find matching rule
        rule = self.policy.find_matching_rule(proposal)

        if not rule:
            # No matching rule: require approval
            return ApprovalDecision(
                approved=False,
                requires_approval=True,
                requires_two_approvals=False,
                reason="No matching approval policy found",
                policy_matched=None,
            )

        # Evaluate confidence score
        if proposal.confidence_score < 0.5 and rule.auto_approve:
            # Low confidence overrides auto-approve
            return ApprovalDecision(
                approved=False,
                requires_approval=True,
                requires_two_approvals=False,
                reason=f"Low confidence score ({proposal.confidence_score}) requires approval",
                policy_matched=rule.action_type_pattern,
            )

        if rule.auto_approve:
            return ApprovalDecision(
                approved=True,
                requires_approval=False,
                requires_two_approvals=False,
                reason=f"Auto-approved: {rule.action_type_pattern} at {rule.risk_threshold.value} risk",
                policy_matched=rule.action_type_pattern,
            )
        else:
            return ApprovalDecision(
                approved=False,
                requires_approval=True,
                requires_two_approvals=rule.require_two_approvals,
                reason=f"Requires approval: {rule.action_type_pattern} at {rule.risk_threshold.value} risk",
                policy_matched=rule.action_type_pattern,
            )
