"""
Time OS V4 - Proposal Scoring

Computes proposal scores based on:
- Urgency: How severe/time-sensitive are the signals
- Breadth: How many signals corroborate the issue
- Diversity: How many different signal types
- Impact: Client tier, engagement type, project value

Score range: 0-200
Executive attention threshold: 50+
Critical threshold: 100+
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def compute_urgency_score(signal: dict[str, Any]) -> float:
    """
    Compute urgency score for a single signal.

    Returns: 0-60 based on signal type and severity
    """
    signal_type = signal.get("signal_type", "")
    value = signal.get("value", {})
    if isinstance(value, str):
        import json

        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            # Internal signal data - malformed affects scoring accuracy
            logger.warning(f"Signal has invalid value JSON, scoring with defaults: {e}")
            value = {}

    if signal_type == "deadline_overdue":
        days = value.get("days_overdue", 0)
        if days is None:
            days = 0
        # 1 day = 22, 7 days = 34, 14 days = 48, 20+ days = 60
        return min(60, 20 + days * 2)

    if signal_type == "ar_aging_risk":
        days = value.get("days_overdue", 0) or 0
        amount = value.get("overdue_amount", 0) or 0
        # Combine time and money factors
        return min(60, 10 + days * 0.5 + amount / 2000)

    if signal_type == "deadline_approaching":
        days_until = value.get("days_until", 7) or 7
        # 1 day until = 25, 3 days = 15, 6+ days = 0
        return max(0, 30 - days_until * 5)

    if signal_type == "client_health_declining":
        # Fixed moderate urgency for relationship signals
        return 35

    if signal_type == "communication_gap":
        days = value.get("days_silent", 0) or value.get("days", 0) or 0
        # 3 days = 16, 7 days = 24, 14 days = 38
        return min(40, 10 + days * 2)

    if signal_type in ("hierarchy_violation", "data_quality_issue"):
        # Process/hygiene signals - lower urgency
        return 15

    if signal_type == "commitment_made":
        # Informational - lowest urgency
        return 5

    # Unknown signal type - default
    return 10


def compute_breadth_score(signals: list[dict]) -> float:
    """
    Compute breadth score based on signal count.
    More signals = more confidence this needs attention.

    Returns: 0-40
    """
    count = len(signals)
    # 1 signal = 4, 5 signals = 20, 10+ signals = 40
    return min(40, count * 4)


def compute_diversity_score(signals: list[dict]) -> float:
    """
    Compute diversity score based on signal type variety.
    Multiple signal types = systemic issue.

    Returns: 0-30
    """
    unique_types = set()
    for sig in signals:
        sig_type = sig.get("signal_type", "unknown")
        # Group similar types
        if "deadline" in sig_type:
            unique_types.add("deadline")
        elif "health" in sig_type or "relationship" in sig_type:
            unique_types.add("health")
        elif "ar_" in sig_type or "invoice" in sig_type:
            unique_types.add("financial")
        elif "communication" in sig_type:
            unique_types.add("communication")
        elif "commitment" in sig_type:
            unique_types.add("commitment")
        elif "violation" in sig_type or "quality" in sig_type:
            unique_types.add("process")
        else:
            unique_types.add(sig_type)

    # 1 type = 8, 2 types = 16, 3 types = 24, 4+ types = 30
    return min(30, len(unique_types) * 8)


def compute_impact_multiplier(hierarchy: dict[str, Any]) -> float:
    """
    Compute impact multiplier based on business context.

    Returns: 0.8-2.0
    """
    # Client tier factor
    tier = hierarchy.get("client_tier", "C")
    tier_multipliers = {"A": 1.5, "B": 1.2, "C": 1.0, None: 0.8}
    client_mult = tier_multipliers.get(tier, 1.0)

    # Engagement type factor
    engagement = hierarchy.get("engagement_type", "project")
    if engagement == "retainer":
        engagement_mult = 1.1  # Retainers = ongoing relationship
    else:
        engagement_mult = 1.0

    # Project value factor
    value = hierarchy.get("project_value", 0) or 0
    if value > 50000:
        value_mult = 1.3
    elif value > 20000:
        value_mult = 1.1
    else:
        value_mult = 1.0

    # Combine (multiplicative but capped)
    combined = client_mult * engagement_mult * value_mult
    return min(2.0, max(0.8, combined))


def compute_proposal_score(
    signals: list[dict], hierarchy: dict[str, Any]
) -> dict[str, Any]:
    """
    Compute full proposal score from signals and hierarchy context.

    Args:
        signals: List of signal dicts with signal_type, value, severity
        hierarchy: Dict with client_tier, engagement_type, project_value

    Returns:
        {
            'score': float (0-200),
            'breakdown': {
                'urgency': float,
                'breadth': float,
                'diversity': float,
                'impact_multiplier': float
            }
        }
    """
    if not signals:
        return {
            "score": 0.0,
            "breakdown": {
                "urgency": 0,
                "breadth": 0,
                "diversity": 0,
                "impact_multiplier": 1.0,
            },
        }

    # Urgency: max of all signal urgencies
    urgency_scores = [compute_urgency_score(sig) for sig in signals]
    urgency = max(urgency_scores) if urgency_scores else 0

    # Breadth: based on count
    breadth = compute_breadth_score(signals)

    # Diversity: based on type variety
    diversity = compute_diversity_score(signals)

    # Impact multiplier
    impact_mult = compute_impact_multiplier(hierarchy)

    # Final score
    raw_score = urgency + breadth + diversity
    final_score = raw_score * impact_mult

    return {
        "score": round(final_score, 1),
        "breakdown": {
            "urgency": round(urgency, 1),
            "breadth": round(breadth, 1),
            "diversity": round(diversity, 1),
            "impact_multiplier": round(impact_mult, 2),
        },
    }


def get_worst_signal_text(signals: list[dict]) -> str:
    """
    Get human-readable description of the worst/most urgent signal.
    Returns actionable, specific text with actual values.
    """
    if not signals:
        return "No active signals"

    # Find signal with highest urgency
    worst = max(signals, key=lambda s: compute_urgency_score(s))

    signal_type = worst.get("signal_type", "unknown")
    value = worst.get("value", {})
    if isinstance(value, str):
        import json

        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Signal has invalid value JSON for nudge generation: {e}")
            value = {}

    task_title = value.get("title", value.get("task_title", ""))
    if task_title and len(task_title) > 35:
        task_title = task_title[:32] + "..."

    owner = value.get("owner", value.get("assignee", ""))
    if owner == "unassigned":
        owner = ""

    if signal_type == "deadline_overdue":
        days = value.get("days_overdue", 0)
        text = (
            f"{task_title}: {days}d overdue" if task_title else f"Task {days}d overdue"
        )
        return f"{text} [{owner}]" if owner else text

    if signal_type == "deadline_approaching":
        days = value.get("days_until", 0)
        text = f"{task_title}: due in {days}d" if task_title else f"Task due in {days}d"
        return f"{text} [{owner}]" if owner else text

    if signal_type == "ar_aging_risk":
        amount = value.get("overdue_amount", value.get("ar_total", 0))
        days = value.get("days_outstanding", 0)
        amount_k = amount / 1000 if amount >= 1000 else amount
        if amount >= 1000:
            return f"${amount_k:.0f}k AR overdue ({days}d)"
        return f"${amount:,.0f} AR overdue ({days}d)"

    if signal_type == "client_health_declining":
        status = value.get("health_status", "poor")
        trend = value.get("trend", "declining")
        client = value.get("client_name", "")
        return f"Health: {status}, trend {trend}" + (f" ({client})" if client else "")

    if signal_type == "communication_gap":
        days = value.get(
            "days_since_contact", value.get("days_silent", value.get("days", 0))
        )
        client = value.get("client_name", "")
        return f"No contact: {days}d" + (f" ({client})" if client else "")

    if signal_type == "data_quality_issue":
        msg = value.get("message", "Data issue")
        return msg[:60] if len(msg) <= 60 else msg[:57] + "..."

    # Fallback: try to extract something useful
    msg = value.get("message", "")
    if msg:
        return msg[:60] if len(msg) <= 60 else msg[:57] + "..."
    return signal_type.replace("_", " ").title()


# Test
if __name__ == "__main__":
    # Test signals
    test_signals = [
        {
            "signal_type": "deadline_overdue",
            "value": {"days_overdue": 12, "title": "Design post"},
        },
        {
            "signal_type": "deadline_overdue",
            "value": {"days_overdue": 5, "title": "Video edit"},
        },
        {
            "signal_type": "deadline_approaching",
            "value": {"days_until": 2, "title": "Final delivery"},
        },
        {"signal_type": "client_health_declining", "value": {}},
    ]

    test_hierarchy = {
        "client_tier": "A",
        "engagement_type": "project",
        "project_value": 45000,
    }

    result = compute_proposal_score(test_signals, test_hierarchy)
    logger.info(f"Score: {result['score']}")
    logger.info(f"Breakdown: {result['breakdown']}")
    logger.info(f"Worst: {get_worst_signal_text(test_signals)}")
