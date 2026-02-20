#!/usr/bin/env python3
"""
MOH Time OS — Priority Scoring Engine

Per MOH_TIME_OS_PRIORITY.md spec:
- Multi-dimensional scoring
- Configurable weights
- Action thresholds
- Attribution
"""

import json
import logging
from datetime import UTC, date, datetime, timedelta

from .config_store import get

logger = logging.getLogger(__name__)

# Default weights (can be overridden in config)
DEFAULT_WEIGHTS = {
    "urgency": 0.22,
    "impact": 0.22,
    "deadline_proximity": 0.18,
    "sensitivity": 0.16,
    "stakeholder": 0.10,
    "waiting_aging": 0.07,
    "meeting_linked": 0.05,
}

# Level mappings (text → numeric)
LEVEL_SCORES = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.3,
    "none": 0.0,
}

# Sensitivity scores
SENSITIVITY_SCORES = {
    "financial": 0.9,
    "legal": 1.0,
    "security": 1.0,
    "reputation": 0.7,
    "execCritical": 0.9,
    "clientVIP": 0.8,
    "privacy": 0.6,
}

# Stakeholder tier scores
STAKEHOLDER_SCORES = {
    "alwaysUrgent": 1.0,
    "important": 0.7,
    "significant": 0.5,
    "normal": 0.3,
}

# Action thresholds
THRESHOLDS = {
    "propose_task_create": 0.45,
    "propose_delegation": 0.55,
    "propose_calendar_block": 0.60,
    "immediate_alert": 0.75,
}


def get_weights() -> dict[str, float]:
    """Get scoring weights from config or use defaults."""
    config_weights = get("priority.weights")
    if config_weights:
        return config_weights
    return DEFAULT_WEIGHTS


def score_urgency(item: dict) -> tuple[float, str]:
    """Score urgency dimension."""
    urgency = item.get("urgency", "medium").lower()
    score = LEVEL_SCORES.get(urgency, 0.5)
    return score, f"urgency={urgency}"


def score_impact(item: dict) -> tuple[float, str]:
    """Score impact dimension."""
    impact = item.get("impact", "medium").lower()
    score = LEVEL_SCORES.get(impact, 0.5)
    return score, f"impact={impact}"


def score_deadline_proximity(item: dict) -> tuple[float, str]:
    """Score based on how close the deadline is."""
    due = item.get("due")
    if not due:
        return 0.2, "no deadline"

    try:
        due_date = date.fromisoformat(due)
        today = date.today()
        days_until = (due_date - today).days

        if days_until < 0:
            return 1.0, f"overdue by {-days_until} days"
        if days_until == 0:
            return 0.95, "due today"
        if days_until == 1:
            return 0.85, "due tomorrow"
        if days_until <= 3:
            return 0.7, f"due in {days_until} days"
        if days_until <= 7:
            return 0.5, f"due in {days_until} days"
        return 0.3, f"due in {days_until} days"
    except (ValueError, TypeError) as e:
        logger.debug(f"Could not parse deadline '{due}': {e}")
        return 0.2, "invalid deadline"


def score_sensitivity(item: dict) -> tuple[float, str]:
    """Score based on sensitivity flags."""
    flags = item.get("sensitivity_flags", [])
    if isinstance(flags, str):
        flags = [f.strip() for f in flags.split(",") if f.strip()]

    if not flags:
        return 0.0, "no sensitivity flags"

    # Take highest sensitivity score
    max_score = 0.0
    max_flag = None

    for flag in flags:
        score = SENSITIVITY_SCORES.get(flag.lower(), 0.0)
        if score > max_score:
            max_score = score
            max_flag = flag

    return max_score, f"sensitivity={max_flag}"


def score_stakeholder(item: dict) -> tuple[float, str]:
    """Score based on stakeholder tier."""
    # Could be derived from client, counterparty, or explicit field
    stakeholder_tier = item.get("stakeholder_tier", "normal")
    score = STAKEHOLDER_SCORES.get(stakeholder_tier, 0.3)
    return score, f"stakeholder_tier={stakeholder_tier}"


def score_waiting_aging(item: dict) -> tuple[float, str]:
    """Score based on how long item has been waiting."""
    waiting_since = item.get("waiting_since")
    if not waiting_since:
        return 0.0, "not waiting"

    try:
        waiting_date = datetime.fromisoformat(waiting_since.replace("Z", "+00:00"))
        days_waiting = (datetime.now(UTC) - waiting_date).days

        if days_waiting >= 7:
            return 0.9, f"waiting {days_waiting} days (critical)"
        if days_waiting >= 5:
            return 0.7, f"waiting {days_waiting} days"
        if days_waiting >= 3:
            return 0.5, f"waiting {days_waiting} days"
        return 0.3, f"waiting {days_waiting} days"
    except (ValueError, TypeError, AttributeError) as e:
        logger.debug(f"Could not parse waiting_since '{waiting_since}': {e}")
        return 0.0, "invalid waiting date"


def score_meeting_linked(item: dict, calendar_events: list[dict] = None) -> tuple[float, str]:
    """Score if item is linked to an upcoming meeting."""
    meeting_linked = item.get("meeting_linked", False)
    if not meeting_linked:
        return 0.0, "not meeting-linked"

    # Check if meeting is within 24h
    if calendar_events:
        item_id = item.get("id")
        for event in calendar_events:
            if event.get("linked_item_id") == item_id:
                start = event.get("start", {}).get("dateTime")
                if start:
                    try:
                        event_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        hours_until = (event_time - datetime.now(UTC)).total_seconds() / 3600
                        if hours_until <= 24:
                            return 1.0, f"meeting in {int(hours_until)}h"
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.debug(f"Could not parse event start time: {e}")

    return 0.5, "meeting-linked (timing unknown)"


def calculate_priority(
    item: dict,
    calendar_events: list[dict] = None,
    weights: dict[str, float] = None,
) -> dict:
    """
    Calculate priority score for an item.

    Returns dict with:
    - total_score: float 0-1
    - components: breakdown of each dimension
    - modifiers: applied modifiers
    - attribution: sources for each score
    - actions: suggested actions based on thresholds
    """
    weights = weights or get_weights()

    # Calculate each dimension
    components = {}
    attribution = []

    urgency_score, urgency_attr = score_urgency(item)
    components["urgency"] = urgency_score
    attribution.append(urgency_attr)

    impact_score, impact_attr = score_impact(item)
    components["impact"] = impact_score
    attribution.append(impact_attr)

    deadline_score, deadline_attr = score_deadline_proximity(item)
    components["deadline_proximity"] = deadline_score
    attribution.append(deadline_attr)

    sensitivity_score, sensitivity_attr = score_sensitivity(item)
    components["sensitivity"] = sensitivity_score
    attribution.append(sensitivity_attr)

    stakeholder_score, stakeholder_attr = score_stakeholder(item)
    components["stakeholder"] = stakeholder_score
    attribution.append(stakeholder_attr)

    waiting_score, waiting_attr = score_waiting_aging(item)
    components["waiting_aging"] = waiting_score
    attribution.append(waiting_attr)

    meeting_score, meeting_attr = score_meeting_linked(item, calendar_events)
    components["meeting_linked"] = meeting_score
    attribution.append(meeting_attr)

    # Calculate weighted sum
    total = 0.0
    for dim, score in components.items():
        weight = weights.get(dim, 0.0)
        total += score * weight

    # Apply modifiers
    modifiers = []

    # Hard deadline within 72h: +0.20
    due = item.get("due")
    if due:
        try:
            due_date = date.fromisoformat(due)
            days_until = (due_date - date.today()).days
            if 0 <= days_until <= 3 and item.get("deadline_type") == "hard":
                total = min(1.0, total + 0.20)
                modifiers.append("hard_deadline_72h: +0.20")
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse due date for boost calculation: {e}")

    # Financial/legal/security with high confidence: +0.15
    sensitivity_flags = item.get("sensitivity_flags", [])
    if isinstance(sensitivity_flags, str):
        sensitivity_flags = [f.strip() for f in sensitivity_flags.split(",")]

    high_sensitivity = ["financial", "legal", "security"]
    if any(f.lower() in high_sensitivity for f in sensitivity_flags):
        total = min(1.0, total + 0.15)
        modifiers.append("high_sensitivity: +0.15")

    # Determine suggested actions
    actions = []
    thresholds = get("priority.thresholds") or THRESHOLDS

    if total >= thresholds.get("immediate_alert", 0.75):
        actions.append("immediate_alert")
    if total >= thresholds.get("propose_calendar_block", 0.60):
        actions.append("propose_calendar_block")
    if total >= thresholds.get("propose_delegation", 0.55):
        actions.append("propose_delegation")
    if total >= thresholds.get("propose_task_create", 0.45):
        actions.append("propose_task_create")

    return {
        "item_id": item.get("id"),
        "total_score": round(total, 3),
        "components": components,
        "weights_used": weights,
        "modifiers": modifiers,
        "attribution": attribution,
        "suggested_actions": actions,
    }


def rank_items(items: list[dict], calendar_events: list[dict] = None) -> list[dict]:
    """
    Rank items by priority.

    Returns list of (item, priority_result) sorted by score descending.
    """
    scored = []

    for item in items:
        priority = calculate_priority(item, calendar_events)
        scored.append(
            {
                "item": item,
                "priority": priority,
            }
        )

    # Sort by score descending
    scored.sort(key=lambda x: x["priority"]["total_score"], reverse=True)

    return scored


def filter_by_action(items: list[dict], action: str) -> list[dict]:
    """Filter items that suggest a specific action."""
    results = []

    for item in items:
        priority = calculate_priority(item)
        if action in priority.get("suggested_actions", []):
            results.append(
                {
                    "item": item,
                    "priority": priority,
                }
            )

    return results


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: priority_engine.py <command> [args]")
        logger.info("Commands: score <item_json>, demo")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "demo":
        demo_item = {
            "id": "item123",
            "what": "Review Five Guys proposal",
            "urgency": "high",
            "impact": "medium",
            "due": (date.today() + timedelta(days=2)).isoformat(),
            "deadline_type": "hard",
            "sensitivity_flags": ["financial", "clientVIP"],
        }

        result = calculate_priority(demo_item)
        logger.info(json.dumps(result, indent=2))
    elif cmd == "score" and len(sys.argv) >= 3:
        item = json.loads(sys.argv[2])
        result = calculate_priority(item)
        logger.info(json.dumps(result, indent=2))
    else:
        logger.info(f"Unknown command: {cmd}")
