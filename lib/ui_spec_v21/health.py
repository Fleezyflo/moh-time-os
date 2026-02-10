"""
Health Score Module — Spec Section 6.6

Implements client and engagement health calculations.
All values are integers with proper clamping and divide-by-zero handling.
"""

import logging
from dataclasses import dataclass
from math import floor

logger = logging.getLogger(__name__)


# Health thresholds per spec 6.6
HEALTH_THRESHOLDS = {
    "poor": (0, 39),
    "fair": (40, 69),
    "good": (70, 100),
}

# Health-counted issue states per spec 6.6
HEALTH_COUNTED_STATES = {
    "surfaced",
    "acknowledged",
    "addressing",
    "awaiting_resolution",
    "regressed",
}

# Task linking coverage threshold
TASK_LINKING_THRESHOLD = 0.90


@dataclass
class ClientHealthResult:
    """Result of client health calculation."""

    score: int
    label: str
    ar_penalty: int
    issue_penalty: int
    is_provisional: bool = True  # Until task linking complete


@dataclass
class EngagementHealthResult:
    """Result of engagement health calculation."""

    score: int | None
    gating_reason: str | None  # "no_tasks" or "task_linking_incomplete"
    overdue_penalty: int = 0
    completion_lag: int = 0


def health_label(score: int | None) -> str:
    """
    Get label for health score.

    Spec: 6.6 Thresholds
    """
    if score is None:
        return "N/A"

    if score <= 39:
        return "poor"
    if score <= 69:
        return "fair"
    return "good"


def client_health(
    ar_outstanding: float, ar_overdue: float, open_issues_high_critical: int
) -> ClientHealthResult:
    """
    Calculate client health score.

    Spec: 6.6 Client Health (v1 — provisional)

    Args:
        ar_outstanding: Total unpaid invoices (sent + overdue)
        ar_overdue: Total overdue invoices
        open_issues_high_critical: Count of high/critical issues in health-counted states

    Returns:
        ClientHealthResult with score, label, and penalties

    Formula:
        AR_penalty = floor(min(40, overdue_ratio * 60))
        Issue_penalty = min(30, open_issues * 10)
        Health = max(0, 100 - AR_penalty - Issue_penalty)
    """
    # Safe ratio calculation
    overdue_ratio = 0.0 if ar_outstanding == 0 else min(1.0, ar_overdue / ar_outstanding)

    # AR penalty: floor(min(40, ratio * 60))
    ar_penalty = floor(min(40, overdue_ratio * 60))

    # Issue penalty: only high/critical, only health-counted states
    issue_penalty = min(30, open_issues_high_critical * 10)

    # Final score
    score = max(0, 100 - ar_penalty - issue_penalty)

    return ClientHealthResult(
        score=score,
        label=health_label(score),
        ar_penalty=ar_penalty,
        issue_penalty=issue_penalty,
        is_provisional=True,  # v1 is always provisional
    )


def engagement_health(
    open_tasks_in_source: int,
    linked_open_tasks: int,
    tasks_overdue: int,
    avg_days_late: float,
) -> EngagementHealthResult:
    """
    Calculate engagement health score.

    Spec: 6.6 / 6.17 Engagement Health (v1)

    Args:
        open_tasks_in_source: Count of open, non-archived, top-level tasks in Asana project
        linked_open_tasks: Count of DB tasks linked to engagement where task is open
        tasks_overdue: Count of overdue linked tasks
        avg_days_late: Average days late for completed tasks (excludes null due_date)

    Returns:
        EngagementHealthResult with score or gating reason

    Gating:
        1. If open_tasks_in_source == 0 → (null, "no_tasks")
        2. If linked_pct < 0.90 → (null, "task_linking_incomplete")

    Formula:
        Overdue_penalty = floor(min(50, overdue_ratio * 80))
        Completion_lag = floor(min(30, avg_days_late * 5))
        Health = max(0, 100 - Overdue_penalty - Completion_lag)
    """
    # Gating check 1: must have open tasks in source project
    if open_tasks_in_source == 0:
        return EngagementHealthResult(
            score=None,
            gating_reason="no_tasks",
        )

    # Gating check 2: require sufficient task linking coverage
    linked_pct = linked_open_tasks / open_tasks_in_source
    if linked_pct < TASK_LINKING_THRESHOLD:
        return EngagementHealthResult(
            score=None,
            gating_reason="task_linking_incomplete",
        )

    # Health calculation uses linked open tasks
    tasks_total = linked_open_tasks

    # Safe ratio calculation
    overdue_ratio = 0.0 if tasks_total == 0 else min(1.0, tasks_overdue / tasks_total)

    # Overdue penalty
    overdue_penalty = floor(min(50, overdue_ratio * 80))

    # Completion lag
    completion_lag = floor(min(30, avg_days_late * 5))

    # Final score
    score = max(0, 100 - overdue_penalty - completion_lag)

    return EngagementHealthResult(
        score=score,
        gating_reason=None,
        overdue_penalty=overdue_penalty,
        completion_lag=completion_lag,
    )


def count_health_issues(issues: list) -> int:
    """
    Count issues that affect health penalty.

    Spec: 6.6 Health-counted states

    Only counts:
    - severity in ('high', 'critical')
    - state in HEALTH_COUNTED_STATES
    - suppressed = false
    """
    count = 0
    for issue in issues:
        if issue.get("suppressed"):
            continue
        if issue.get("severity") not in ("high", "critical"):
            continue
        if issue.get("state") not in HEALTH_COUNTED_STATES:
            continue
        count += 1
    return count


def ar_overdue_pct(ar_outstanding: float, ar_overdue: float) -> int:
    """
    Calculate AR overdue percentage.

    Spec: 0.1 Rounding Conventions
    - ar_overdue_pct: round() (nearest integer)
    """
    if ar_outstanding == 0:
        return 0
    ratio = ar_overdue / ar_outstanding
    return round(ratio * 100)


# Test functions
def _test_client_health():
    """Test client health calculation."""

    # Test 1: Perfect health (no AR, no issues)
    result = client_health(0, 0, 0)
    assert result.score == 100
    assert result.ar_penalty == 0
    assert result.issue_penalty == 0
    logger.info("✓ Perfect health test passed")
    # Test 2: 50% AR overdue
    result = client_health(100000, 50000, 0)
    assert result.ar_penalty == 30  # floor(0.5 * 60) = 30
    assert result.score == 70
    logger.info("✓ 50% AR overdue test passed")
    # Test 3: Full AR overdue (100%)
    result = client_health(100000, 100000, 0)
    assert result.ar_penalty == 40  # capped at 40
    assert result.score == 60
    logger.info("✓ Full AR overdue test passed")
    # Test 4: Issues only
    result = client_health(0, 0, 2)
    assert result.ar_penalty == 0
    assert result.issue_penalty == 20  # 2 * 10
    assert result.score == 80
    logger.info("✓ Issues only test passed")
    # Test 5: Capped issue penalty
    result = client_health(0, 0, 5)
    assert result.issue_penalty == 30  # capped at 30
    assert result.score == 70
    logger.info("✓ Capped issue penalty test passed")
    # Test 6: Combined penalties
    result = client_health(100000, 50000, 2)
    assert result.ar_penalty == 30
    assert result.issue_penalty == 20
    assert result.score == 50
    logger.info("✓ Combined penalties test passed")
    logger.info("All client health tests passed!")


def _test_engagement_health():
    """Test engagement health calculation."""

    # Test 1: No tasks in source
    result = engagement_health(0, 0, 0, 0.0)
    assert result.score is None
    assert result.gating_reason == "no_tasks"
    logger.info("✓ No tasks gating test passed")
    # Test 2: Low linking coverage (< 90%)
    result = engagement_health(10, 8, 0, 0.0)  # 80% linked
    assert result.score is None
    assert result.gating_reason == "task_linking_incomplete"
    logger.info("✓ Low linking gating test passed")
    # Test 3: Perfect health (90%+ linked, no overdue, no late)
    result = engagement_health(10, 9, 0, 0.0)
    assert result.score == 100
    assert result.gating_reason is None
    logger.info("✓ Perfect engagement health test passed")
    # Test 4: Some overdue tasks
    result = engagement_health(10, 10, 3, 0.0)  # 30% overdue
    assert result.overdue_penalty == 24  # floor(0.3 * 80)
    assert result.score == 76
    logger.info("✓ Overdue penalty test passed")
    # Test 5: Completion lag
    result = engagement_health(10, 10, 0, 4.0)  # 4 days avg late
    assert result.completion_lag == 20  # floor(4 * 5)
    assert result.score == 80
    logger.info("✓ Completion lag test passed")
    # Test 6: Combined penalties
    result = engagement_health(10, 10, 5, 6.0)  # 50% overdue, 6d late
    assert result.overdue_penalty == 40  # floor(0.5 * 80)
    assert result.completion_lag == 30  # capped at 30
    assert result.score == 30
    logger.info("✓ Combined engagement penalties test passed")
    logger.info("All engagement health tests passed!")


if __name__ == "__main__":
    _test_client_health()
    _test_engagement_health()
