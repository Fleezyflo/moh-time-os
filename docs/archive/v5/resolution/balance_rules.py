"""
Time OS V5 — Balance Rules Configuration

Defines which positive signals can balance which negative signals.
"""


# =============================================================================
# BALANCE PAIRS
# =============================================================================
# Maps negative signal types to positive signal types that can balance them

BALANCE_PAIRS: dict[str, list[str]] = {
    # -------------------------------------------------------------------------
    # Schedule Signals
    # -------------------------------------------------------------------------
    # Overdue task can be balanced by completion
    "task_overdue": [
        "task_completed_ontime",
        "task_completed_late",  # Completed late is still completion
        "task_completed_early",
    ],
    # Blocked task balanced by unblock
    "task_blocked": ["task_unblocked"],
    # Approaching deadline auto-expires, no balancing needed
    "task_approaching": [],
    # Due moved out is historical fact, can't be balanced
    "task_due_moved_out": [],
    # Completed late is historical fact
    "task_completed_late": [],
    # -------------------------------------------------------------------------
    # Quality Signals
    # -------------------------------------------------------------------------
    # High revisions balanced by eventual approval
    "revision_cycle_high": [
        "meeting_approval_given",
        "sentiment_positive",
    ],
    # Excessive revisions need strong approval
    "revision_cycle_excessive": [
        "meeting_approval_given",
    ],
    # -------------------------------------------------------------------------
    # Financial Signals
    # -------------------------------------------------------------------------
    # Overdue invoices balanced by payment
    "invoice_overdue_30": [
        "payment_received_ontime",
        "payment_received_late",
    ],
    "invoice_overdue_60": [
        "payment_received_ontime",
        "payment_received_late",
    ],
    "invoice_overdue_90": [
        "payment_received_ontime",
        "payment_received_late",
    ],
    # -------------------------------------------------------------------------
    # Communication Signals
    # -------------------------------------------------------------------------
    # Communication gap balanced by renewed communication
    "communication_gap": [
        "meeting_occurred",
        "sentiment_positive",
    ],
    # Slow response balanced by fast response
    "response_slow_client": [
        "response_fast_client",
    ],
    "response_slow_team": [
        "response_fast_team",
    ],
    # Negative sentiment needs sustained positivity
    "sentiment_negative": [
        "sentiment_positive",
    ],
    # Escalation balanced by resolution
    "escalation_detected": [
        "sentiment_positive",
        "meeting_decision_made",
        "meeting_approval_given",
    ],
    # Engagement decrease balanced by increase
    "engagement_decreasing": [
        "engagement_increasing",
    ],
    # -------------------------------------------------------------------------
    # Relationship Signals
    # -------------------------------------------------------------------------
    # No-show balanced by actual meeting
    "meeting_noshow_client": ["meeting_occurred"],
    "meeting_noshow_team": ["meeting_occurred"],
    # Concern raised balanced by resolution
    "meeting_concern_raised": [
        "meeting_decision_made",
        "meeting_approval_given",
    ],
    # Urgent meeting title balanced by meeting occurring
    "meeting_title_urgent": [
        "meeting_occurred",
        "meeting_decision_made",
    ],
}


# =============================================================================
# SUSTAINED BALANCE REQUIREMENTS
# =============================================================================
# Signals that require sustained positive signals over time to balance

SUSTAINED_BALANCE_REQUIRED: set[str] = {
    "sentiment_negative",  # One positive doesn't erase negative sentiment
    "engagement_decreasing",  # Need consistent engagement to prove trend reversed
}

# Days of sustained positivity required
SUSTAINED_BALANCE_DAYS = 14

# Minimum positive signal count required
SUSTAINED_BALANCE_COUNT = 3


# =============================================================================
# SCOPE MATCHING RULES
# =============================================================================
# How signals must match to balance each other


class ScopeMatchRule:
    """Rules for matching signal scopes."""

    # Exact entity match required
    EXACT_ENTITY = "exact_entity"

    # Same client is enough
    SAME_CLIENT = "same_client"

    # Same project is enough
    SAME_PROJECT = "same_project"

    # Same brand is enough
    SAME_BRAND = "same_brand"


# Default scope matching rules by signal type
SCOPE_MATCH_RULES: dict[str, str] = {
    # Task signals need exact entity match
    "task_overdue": ScopeMatchRule.EXACT_ENTITY,
    "task_blocked": ScopeMatchRule.EXACT_ENTITY,
    "revision_cycle_high": ScopeMatchRule.EXACT_ENTITY,
    "revision_cycle_excessive": ScopeMatchRule.EXACT_ENTITY,
    # Invoice signals need exact entity match
    "invoice_overdue_30": ScopeMatchRule.EXACT_ENTITY,
    "invoice_overdue_60": ScopeMatchRule.EXACT_ENTITY,
    "invoice_overdue_90": ScopeMatchRule.EXACT_ENTITY,
    # Communication signals can be balanced at client level
    "communication_gap": ScopeMatchRule.SAME_CLIENT,
    "sentiment_negative": ScopeMatchRule.SAME_CLIENT,
    "escalation_detected": ScopeMatchRule.SAME_CLIENT,
    "engagement_decreasing": ScopeMatchRule.SAME_CLIENT,
    # Response signals need same client
    "response_slow_client": ScopeMatchRule.SAME_CLIENT,
    "response_slow_team": ScopeMatchRule.SAME_CLIENT,
    # Meeting signals can be balanced at client level
    "meeting_noshow_client": ScopeMatchRule.SAME_CLIENT,
    "meeting_noshow_team": ScopeMatchRule.SAME_CLIENT,
    "meeting_concern_raised": ScopeMatchRule.SAME_CLIENT,
    "meeting_title_urgent": ScopeMatchRule.SAME_CLIENT,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_balancing_types(negative_type: str) -> list[str]:
    """
    Get signal types that can balance a negative signal.

    Args:
        negative_type: Negative signal type

    Returns:
        List of balancing signal types
    """
    return BALANCE_PAIRS.get(negative_type, [])


def can_balance(negative_type: str, positive_type: str) -> bool:
    """
    Check if a positive signal type can balance a negative signal type.

    Args:
        negative_type: Negative signal type
        positive_type: Positive signal type to check

    Returns:
        True if positive can balance negative
    """
    balancing = BALANCE_PAIRS.get(negative_type, [])
    return positive_type in balancing


def requires_sustained_balance(negative_type: str) -> bool:
    """
    Check if a signal type requires sustained positive signals.

    Args:
        negative_type: Negative signal type

    Returns:
        True if sustained balance is required
    """
    return negative_type in SUSTAINED_BALANCE_REQUIRED


def get_scope_match_rule(negative_type: str) -> str:
    """
    Get scope matching rule for a signal type.

    Args:
        negative_type: Signal type

    Returns:
        Scope matching rule
    """
    return SCOPE_MATCH_RULES.get(negative_type, ScopeMatchRule.SAME_CLIENT)
