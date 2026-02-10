"""
Priority scoring for items.

Explicit, deterministic scoring. No magic, no LLM vibes.
Score 0-100. Higher = more urgent.

Components:
- Due date pressure (0-40 points)
- Client tier (0-25 points)
- Client health (0-15 points)
- Stakes keywords (0-10 points)
- Waiting duration (0-10 points)
"""

from datetime import date


def calculate_priority(
    due: str = None,
    status: str = "open",
    waiting_since: str = None,
    client_tier: str = None,
    client_health: str = None,
    stakes: str = None,
) -> int:
    """
    Calculate priority score 0-100.

    Higher = more urgent.
    Used for sorting and surfacing decisions.
    """
    score = 0
    today = date.today()

    # ─────────────────────────────────────────────────────────────────
    # DUE DATE PRESSURE (0-40 points)
    # ─────────────────────────────────────────────────────────────────
    if due and status == "open":
        try:
            due_date = date.fromisoformat(due)
            days_until = (due_date - today).days

            if days_until < 0:
                # Overdue: 20 base + 2 per day overdue, max 40
                score += min(40, 20 + abs(days_until) * 2)
            elif days_until == 0:
                # Due today
                score += 20
            elif days_until == 1:
                # Due tomorrow
                score += 17
            elif days_until <= 3:
                # Due in 2-3 days
                score += 15
            elif days_until <= 7:
                # Due this week
                score += 10
            elif days_until <= 14:
                # Due in 2 weeks
                score += 5
            # > 14 days: 0 points
        except ValueError:
            pass  # Invalid date format, skip

    # ─────────────────────────────────────────────────────────────────
    # CLIENT TIER (0-25 points)
    # ─────────────────────────────────────────────────────────────────
    tier_scores = {"A": 25, "B": 15, "C": 5}
    if client_tier:
        score += tier_scores.get(client_tier.upper(), 0)

    # ─────────────────────────────────────────────────────────────────
    # CLIENT HEALTH (0-15 points)
    # ─────────────────────────────────────────────────────────────────
    health_scores = {"critical": 15, "poor": 10, "fair": 5, "good": 2, "excellent": 0}
    if client_health:
        score += health_scores.get(client_health.lower(), 0)

    # ─────────────────────────────────────────────────────────────────
    # STAKES KEYWORDS (0-10 points)
    # ─────────────────────────────────────────────────────────────────
    if stakes:
        stakes_lower = stakes.lower()
        high_stakes_keywords = [
            "contract",
            "deadline",
            "launch",
            "critical",
            "urgent",
            "escalate",
            "legal",
            "compliance",
            "penalty",
            "expiring",
            "renewal",
            "termination",
        ]
        medium_stakes_keywords = [
            "important",
            "key",
            "major",
            "significant",
            "priority",
            "flagship",
            "strategic",
        ]

        if any(kw in stakes_lower for kw in high_stakes_keywords):
            score += 10
        elif any(kw in stakes_lower for kw in medium_stakes_keywords):
            score += 5

    # ─────────────────────────────────────────────────────────────────
    # WAITING DURATION (0-10 points)
    # ─────────────────────────────────────────────────────────────────
    if status == "waiting" and waiting_since:
        try:
            waiting_date = date.fromisoformat(waiting_since[:10])
            waiting_days = (today - waiting_date).days
            score += min(10, waiting_days)  # 1 point per day, max 10
        except ValueError:
            pass

    return min(100, score)


# ─────────────────────────────────────────────────────────────────────
# THRESHOLDS
# ─────────────────────────────────────────────────────────────────────

SURFACE_IMMEDIATELY_THRESHOLD = 70  # Proactive alert (e.g., Tier A + overdue)
SURFACE_IN_BRIEF_THRESHOLD = 40  # Include in morning brief
SURFACE_ON_QUERY_THRESHOLD = 0  # Always show when asked


def should_surface_immediately(score: int) -> bool:
    """Should this item trigger an immediate proactive alert?"""
    return score >= SURFACE_IMMEDIATELY_THRESHOLD


def should_surface_in_brief(score: int) -> bool:
    """Should this item be included in the morning brief?"""
    return score >= SURFACE_IN_BRIEF_THRESHOLD


def priority_label(score: int) -> str:
    """Human-readable priority label."""
    if score >= 70:
        return "🔴 Critical"
    if score >= 50:
        return "🟠 High"
    if score >= 30:
        return "🟡 Medium"
    return "🟢 Low"
