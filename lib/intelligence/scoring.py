"""
Scoring framework for MOH TIME OS operational intelligence.

Defines health dimensions, normalization methods, and scoring constants
for agency entities (Client, Project, Person, Portfolio).

This module contains DEFINITIONS ONLY. Computation is in scorecard.py (Task 0.2).

Reference: data/scoring_model_20260213.md
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EntityType(Enum):
    """Entity types that can be scored."""

    CLIENT = "client"
    PROJECT = "project"
    PERSON = "person"
    PORTFOLIO = "portfolio"


class ScoreRange(Enum):
    """Score interpretation ranges."""

    CRITICAL = "critical"  # 0-30: Requires immediate attention
    AT_RISK = "at_risk"  # 31-50: Deteriorating, needs intervention
    STABLE = "stable"  # 51-70: Healthy but worth monitoring
    HEALTHY = "healthy"  # 71-90: Performing well
    STRONG = "strong"  # 91-100: Exceptional performance


class NormMethod(Enum):
    """Normalization methods for score computation."""

    PERCENTILE = "percentile"  # Rank against peers
    THRESHOLD = "threshold"  # Against absolute targets
    RELATIVE = "relative"  # Against own history


@dataclass
class ScoringDimension:
    """
    Definition of a scoring dimension.

    A dimension is one aspect of entity health (e.g., "Operational Health" for clients).
    Multiple dimensions combine into a composite score.
    """

    name: str
    description: str
    entity_type: EntityType
    input_metrics: list[str]  # Query engine return keys
    query_function: str  # Query engine function name
    normalization: NormMethod
    weight: float  # Contribution to composite (sum to 1.0 per entity)
    critical_below: float = 30.0  # Score below this = CRITICAL
    warning_below: float = 60.0  # Score below this = WARNING

    def __post_init__(self):
        """Validate weight is in valid range."""
        if not 0 < self.weight <= 1.0:
            raise ValueError(f"Weight must be 0 < w <= 1.0, got {self.weight}")


@dataclass
class EntityScore:
    """
    Complete score for an entity.

    Contains dimension scores and computed composite.
    """

    entity_type: EntityType
    entity_id: str
    entity_name: str
    dimension_scores: dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    score_range: ScoreRange = ScoreRange.STABLE
    computed_at: str | None = None

    def get_range(self) -> ScoreRange:
        """Determine score range from composite."""
        if self.composite_score <= 30:
            return ScoreRange.CRITICAL
        elif self.composite_score <= 50:
            return ScoreRange.AT_RISK
        elif self.composite_score <= 70:
            return ScoreRange.STABLE
        elif self.composite_score <= 90:
            return ScoreRange.HEALTHY
        else:
            return ScoreRange.STRONG


# =============================================================================
# CLIENT DIMENSIONS
# =============================================================================

CLIENT_OPERATIONAL_HEALTH = ScoringDimension(
    name="operational_health",
    description="Are deliverables on track? Based on completion rate and overdue tasks.",
    entity_type=EntityType.CLIENT,
    input_metrics=["completion_rate", "overdue_tasks", "active_tasks", "total_tasks"],
    query_function="client_task_summary",
    normalization=NormMethod.THRESHOLD,
    weight=0.30,
)

CLIENT_FINANCIAL_HEALTH = ScoringDimension(
    name="financial_health",
    description="Are invoices current? Is revenue stable?",
    entity_type=EntityType.CLIENT,
    input_metrics=["total_outstanding", "total_invoiced", "financial_ar_overdue", "total_paid"],
    query_function="client_portfolio_overview",
    normalization=NormMethod.THRESHOLD,
    weight=0.30,
)

CLIENT_COMMUNICATION_HEALTH = ScoringDimension(
    name="communication_health",
    description="Is engagement active? Based on communication volume vs peers.",
    entity_type=EntityType.CLIENT,
    input_metrics=["entity_links_count", "communications_count"],
    query_function="client_metrics_in_period",
    normalization=NormMethod.PERCENTILE,
    weight=0.25,
)

CLIENT_ENGAGEMENT_TRAJECTORY = ScoringDimension(
    name="engagement_trajectory",
    description="Is the relationship growing or fading?",
    entity_type=EntityType.CLIENT,
    input_metrics=["communications_count", "tasks_created"],
    query_function="client_trajectory",
    normalization=NormMethod.RELATIVE,
    weight=0.15,
)

CLIENT_DIMENSIONS: list[ScoringDimension] = [
    CLIENT_OPERATIONAL_HEALTH,
    CLIENT_FINANCIAL_HEALTH,
    CLIENT_COMMUNICATION_HEALTH,
    CLIENT_ENGAGEMENT_TRAJECTORY,
]


# =============================================================================
# PROJECT DIMENSIONS
# =============================================================================

PROJECT_VELOCITY = ScoringDimension(
    name="velocity",
    description="Are tasks being completed at a healthy rate?",
    entity_type=EntityType.PROJECT,
    input_metrics=["completion_rate_pct", "completed_tasks", "total_tasks"],
    query_function="project_operational_state",
    normalization=NormMethod.THRESHOLD,
    weight=0.35,
)

PROJECT_RISK_EXPOSURE = ScoringDimension(
    name="risk_exposure",
    description="How many tasks are overdue or at risk?",
    entity_type=EntityType.PROJECT,
    input_metrics=["overdue_tasks", "open_tasks"],
    query_function="project_operational_state",
    normalization=NormMethod.THRESHOLD,
    weight=0.35,
)

PROJECT_TEAM_COVERAGE = ScoringDimension(
    name="team_coverage",
    description="Is the project adequately staffed?",
    entity_type=EntityType.PROJECT,
    input_metrics=["assigned_people_count", "open_tasks"],
    query_function="project_operational_state",
    normalization=NormMethod.THRESHOLD,
    weight=0.15,
)

PROJECT_SCOPE_CONTROL = ScoringDimension(
    name="scope_control",
    description="Is scope stable or expanding uncontrollably?",
    entity_type=EntityType.PROJECT,
    input_metrics=["total_tasks", "completed_tasks"],
    query_function="project_operational_state",
    normalization=NormMethod.RELATIVE,
    weight=0.15,
)

PROJECT_DIMENSIONS: list[ScoringDimension] = [
    PROJECT_VELOCITY,
    PROJECT_RISK_EXPOSURE,
    PROJECT_TEAM_COVERAGE,
    PROJECT_SCOPE_CONTROL,
]


# =============================================================================
# PERSON DIMENSIONS
# =============================================================================

PERSON_LOAD_BALANCE = ScoringDimension(
    name="load_balance",
    description="Is workload sustainable? Not overloaded, not idle.",
    entity_type=EntityType.PERSON,
    input_metrics=["active_tasks"],
    query_function="person_operational_profile",
    normalization=NormMethod.THRESHOLD,
    weight=0.40,
)

PERSON_OUTPUT_CONSISTENCY = ScoringDimension(
    name="output_consistency",
    description="Are tasks being completed steadily?",
    entity_type=EntityType.PERSON,
    input_metrics=["assigned_tasks", "active_tasks"],
    query_function="person_operational_profile",
    normalization=NormMethod.THRESHOLD,
    weight=0.30,
)

PERSON_SPREAD = ScoringDimension(
    name="spread",
    description="Working across healthy number of projects?",
    entity_type=EntityType.PERSON,
    input_metrics=["project_count"],
    query_function="person_operational_profile",
    normalization=NormMethod.THRESHOLD,
    weight=0.15,
)

PERSON_AVAILABILITY_RISK = ScoringDimension(
    name="availability_risk",
    description="Risk of being a bottleneck? (Lower = healthier)",
    entity_type=EntityType.PERSON,
    input_metrics=["active_tasks", "project_count"],
    query_function="person_operational_profile",
    normalization=NormMethod.PERCENTILE,
    weight=0.15,
)

PERSON_DIMENSIONS: list[ScoringDimension] = [
    PERSON_LOAD_BALANCE,
    PERSON_OUTPUT_CONSISTENCY,
    PERSON_SPREAD,
    PERSON_AVAILABILITY_RISK,
]


# =============================================================================
# PORTFOLIO DIMENSIONS
# =============================================================================

PORTFOLIO_REVENUE_CONCENTRATION = ScoringDimension(
    name="revenue_concentration",
    description="Is revenue diversified or dependent on few clients?",
    entity_type=EntityType.PORTFOLIO,
    input_metrics=["total_invoiced"],
    query_function="client_portfolio_overview",
    normalization=NormMethod.THRESHOLD,
    weight=0.30,
)

PORTFOLIO_RESOURCE_CONCENTRATION = ScoringDimension(
    name="resource_concentration",
    description="Is work distributed or bottlenecked on few people?",
    entity_type=EntityType.PORTFOLIO,
    input_metrics=["max_tasks_per_person", "avg_tasks_per_person"],
    query_function="team_capacity_overview",
    normalization=NormMethod.THRESHOLD,
    weight=0.25,
)

PORTFOLIO_CLIENT_HEALTH_DISTRIBUTION = ScoringDimension(
    name="client_health_distribution",
    description="What proportion of clients are healthy vs at-risk?",
    entity_type=EntityType.PORTFOLIO,
    input_metrics=["client_composite_scores"],  # Computed from client scores
    query_function="score_all_clients",  # Internal function
    normalization=NormMethod.THRESHOLD,
    weight=0.25,
)

PORTFOLIO_CAPACITY_UTILIZATION = ScoringDimension(
    name="capacity_utilization",
    description="Is team at sustainable utilization?",
    entity_type=EntityType.PORTFOLIO,
    input_metrics=["people_overloaded", "people_available", "total_people"],
    query_function="team_capacity_overview",
    normalization=NormMethod.THRESHOLD,
    weight=0.20,
)

PORTFOLIO_DIMENSIONS: list[ScoringDimension] = [
    PORTFOLIO_REVENUE_CONCENTRATION,
    PORTFOLIO_RESOURCE_CONCENTRATION,
    PORTFOLIO_CLIENT_HEALTH_DISTRIBUTION,
    PORTFOLIO_CAPACITY_UTILIZATION,
]


# =============================================================================
# ALL DIMENSIONS BY ENTITY TYPE
# =============================================================================

DIMENSIONS_BY_TYPE: dict[EntityType, list[ScoringDimension]] = {
    EntityType.CLIENT: CLIENT_DIMENSIONS,
    EntityType.PROJECT: PROJECT_DIMENSIONS,
    EntityType.PERSON: PERSON_DIMENSIONS,
    EntityType.PORTFOLIO: PORTFOLIO_DIMENSIONS,
}


# =============================================================================
# VALIDATION
# =============================================================================


def validate_dimensions() -> list[str]:
    """
    Validate that all dimension definitions are internally consistent.

    Returns list of error messages (empty if valid).
    """
    errors = []

    for entity_type, dimensions in DIMENSIONS_BY_TYPE.items():
        # Check weights sum to 1.0
        total_weight = sum(d.weight for d in dimensions)
        if abs(total_weight - 1.0) > 0.001:
            errors.append(f"{entity_type.value}: weights sum to {total_weight}, expected 1.0")

        # Check for duplicate dimension names
        names = [d.name for d in dimensions]
        if len(names) != len(set(names)):
            errors.append(f"{entity_type.value}: duplicate dimension names")

        # Check entity_type consistency
        for d in dimensions:
            if d.entity_type != entity_type:
                errors.append(
                    f"{d.name}: entity_type mismatch "
                    f"(dimension says {d.entity_type}, registered under {entity_type})"
                )

    return errors


def get_dimensions(entity_type: EntityType) -> list[ScoringDimension]:
    """Get all scoring dimensions for an entity type."""
    return DIMENSIONS_BY_TYPE.get(entity_type, [])


# =============================================================================
# SCORE RANGE HELPERS
# =============================================================================


def score_to_range(score: float) -> ScoreRange:
    """Convert numeric score to ScoreRange."""
    if score <= 30:
        return ScoreRange.CRITICAL
    elif score <= 50:
        return ScoreRange.AT_RISK
    elif score <= 70:
        return ScoreRange.STABLE
    elif score <= 90:
        return ScoreRange.HEALTHY
    else:
        return ScoreRange.STRONG


def range_to_bounds(score_range: ScoreRange) -> tuple[float, float]:
    """Get (min, max) bounds for a score range."""
    bounds = {
        ScoreRange.CRITICAL: (0, 30),
        ScoreRange.AT_RISK: (31, 50),
        ScoreRange.STABLE: (51, 70),
        ScoreRange.HEALTHY: (71, 90),
        ScoreRange.STRONG: (91, 100),
    }
    return bounds.get(score_range, (0, 100))


# Run validation on import to catch definition errors early
_validation_errors = validate_dimensions()
if _validation_errors:
    import warnings

    warnings.warn(f"Scoring dimension validation errors: {_validation_errors}", stacklevel=2)


# =============================================================================
# NORMALIZATION FUNCTIONS
# =============================================================================


def normalize_percentile(value: float, all_values: list[float]) -> float:
    """
    Score 0-100 based on where value ranks among all_values.

    Highest value = 100, lowest = 0.
    Handles ties by using average rank.
    Returns 50.0 for empty or single-item lists.
    """
    if not all_values or len(all_values) < 2:
        return 50.0

    if value is None:
        return 50.0

    # Filter out None values
    clean_values = [v for v in all_values if v is not None]
    if len(clean_values) < 2:
        return 50.0

    # Count how many values are below this one
    below_count = sum(1 for v in clean_values if v < value)
    equal_count = sum(1 for v in clean_values if v == value)

    # Use average rank for ties
    percentile = (below_count + (equal_count - 1) / 2) / (len(clean_values) - 1)

    return min(100.0, max(0.0, percentile * 100))


def normalize_threshold(value: float, target: float, direction: str = "higher_is_better") -> float:
    """
    Score 0-100 based on distance from target.

    For higher_is_better: at or above target = 100, at zero = 0
    For lower_is_better: at or below target = 100, at 2x target = 0
    Linear interpolation between.
    """
    if value is None:
        return 50.0

    if target == 0:
        return 100.0 if value == 0 else 50.0

    if direction == "higher_is_better":
        # At or above target = 100
        if value >= target:
            return 100.0
        # Linear scale from 0 to target
        return min(100.0, max(0.0, (value / target) * 100))
    else:
        # lower_is_better: at or below target = 100
        if value <= target:
            return 100.0
        # Scale: at 2x target = 0
        ratio = (value - target) / target
        return min(100.0, max(0.0, 100 - ratio * 100))


def normalize_relative(current: float, baseline: float) -> float:
    """
    Score 0-100 based on current vs historical baseline.

    At baseline = 70 (stable).
    Above baseline scales up (max 100 at 2x baseline).
    Below baseline scales down (min 0 at 0).
    """
    if current is None or baseline is None:
        return 50.0

    if baseline == 0:
        if current == 0:
            return 70.0  # Stable at zero
        return 100.0 if current > 0 else 0.0

    ratio = current / baseline

    if ratio >= 1.0:
        # Above baseline: scale 70 -> 100 as ratio goes 1.0 -> 2.0
        return min(100.0, 70 + (ratio - 1.0) * 30)
    else:
        # Below baseline: scale 70 -> 0 as ratio goes 1.0 -> 0
        return max(0.0, ratio * 70)


# =============================================================================
# DIMENSION SCORING
# =============================================================================


def score_dimension(
    dimension: ScoringDimension, metrics: dict, context: dict | None = None
) -> dict:
    """
    Compute score for a single dimension.

    Args:
        dimension: The ScoringDimension definition
        metrics: Dict of metric values (keys should match dimension.input_metrics)
        context: Additional context for normalization:
            - For PERCENTILE: {"all_values": list[float]}
            - For RELATIVE: {"baseline": float}

    Returns:
        {
            "dimension": dimension.name,
            "score": float (0-100) or None if data unavailable,
            "classification": "critical"|"warning"|"healthy"|"data_unavailable",
            "metrics_used": {metric_name: value, ...},
            "normalization": dimension.normalization.value
        }
    """
    context = context or {}

    # Extract metrics
    metrics_used = {}
    missing_metrics = []

    for metric_name in dimension.input_metrics:
        value = metrics.get(metric_name)
        if value is not None:
            metrics_used[metric_name] = value
        else:
            missing_metrics.append(metric_name)

    # If all metrics missing, return null score
    if not metrics_used:
        return {
            "dimension": dimension.name,
            "score": None,
            "classification": "data_unavailable",
            "metrics_used": {},
            "normalization": dimension.normalization.value,
            "missing_metrics": missing_metrics,
        }

    # Compute raw value based on dimension
    raw_value = _compute_dimension_raw_value(dimension, metrics_used)

    # Normalize
    if dimension.normalization == NormMethod.PERCENTILE:
        all_values = context.get("all_values", [raw_value])
        score = normalize_percentile(raw_value, all_values)
    elif dimension.normalization == NormMethod.THRESHOLD:
        target = context.get("target", 100.0)
        direction = context.get("direction", "higher_is_better")
        score = normalize_threshold(raw_value, target, direction)
    elif dimension.normalization == NormMethod.RELATIVE:
        baseline = context.get("baseline", raw_value)
        score = normalize_relative(raw_value, baseline)
    else:
        score = 50.0

    # Classify
    if score <= dimension.critical_below:
        classification = "critical"
    elif score <= dimension.warning_below:
        classification = "warning"
    else:
        classification = "healthy"

    return {
        "dimension": dimension.name,
        "score": round(score, 1),
        "classification": classification,
        "metrics_used": metrics_used,
        "normalization": dimension.normalization.value,
        "raw_value": raw_value,
    }


def _compute_dimension_raw_value(dimension: ScoringDimension, metrics: dict) -> float:
    """
    Compute the raw value for a dimension from its metrics.

    This is dimension-specific logic that combines input metrics into
    a single value suitable for normalization.
    """
    name = dimension.name

    # CLIENT DIMENSIONS
    if name == "operational_health":
        # completion_rate * 0.6 + (100 - overdue_penalty) * 0.4
        completion_rate = metrics.get("completion_rate", 50)
        overdue = metrics.get("overdue_tasks", 0)
        active = metrics.get("active_tasks", 1) or 1
        overdue_ratio = overdue / active
        overdue_penalty = min(100, overdue_ratio * 200)
        return completion_rate * 0.6 + (100 - overdue_penalty) * 0.4

    elif name == "financial_health":
        total_invoiced = metrics.get("total_invoiced", 0) or 1
        total_paid = metrics.get("total_paid", 0)
        ar_overdue = metrics.get("financial_ar_overdue", 0)
        payment_ratio = total_paid / total_invoiced
        overdue_ratio = ar_overdue / total_invoiced
        return (payment_ratio * 70) + ((1 - overdue_ratio) * 30)

    elif name == "communication_health":
        # For percentile: just use raw communication count
        return metrics.get("communications_count", metrics.get("entity_links_count", 0))

    elif name == "engagement_trajectory":
        # Compute engagement trend from recent communication and task activity
        recent_comms = metrics.get("recent_communications", metrics.get("communications_count", 0))
        total_comms = metrics.get("total_communications", metrics.get("communications_count", 0))
        active_tasks = metrics.get("active_tasks", 0)
        completed_tasks = metrics.get("completed_tasks", 0)

        # If explicit trend_score is available, use it
        if metrics.get("trend_score") is not None:
            return metrics["trend_score"]

        # Otherwise compute from activity signals
        # Higher recent comms relative to total = growing engagement
        comm_ratio = recent_comms / max(total_comms, 1) if total_comms > 0 else 0.5
        task_momentum = (
            completed_tasks / max(active_tasks + completed_tasks, 1)
            if (active_tasks + completed_tasks) > 0
            else 0.5
        )
        return comm_ratio * 50 + task_momentum * 50

    # PROJECT DIMENSIONS
    elif name == "velocity":
        return metrics.get("completion_rate_pct", 50)

    elif name == "risk_exposure":
        overdue = metrics.get("overdue_tasks", 0)
        open_tasks = metrics.get("open_tasks", 1) or 1
        overdue_ratio = overdue / open_tasks
        return max(0, 100 - (overdue_ratio * 150))

    elif name == "team_coverage":
        people = metrics.get("assigned_people_count", 0)
        open_tasks = metrics.get("open_tasks", 0)
        if people == 0 and open_tasks > 0:
            return 0
        if people == 0:
            return 50
        tasks_per_person = open_tasks / people
        return max(0, 100 - (tasks_per_person - 10) * 5)

    elif name == "scope_control":
        total = metrics.get("total_tasks", 1) or 1
        completed = metrics.get("completed_tasks", 0)
        return (completed / total) * 100

    # PERSON DIMENSIONS
    elif name == "load_balance":
        active = metrics.get("active_tasks", 10)
        if 5 <= active <= 15:
            return 100
        return max(0, 100 - abs(active - 10) * 5)

    elif name == "output_consistency":
        assigned = metrics.get("assigned_tasks", 1) or 1
        active = metrics.get("active_tasks", 0)
        completed = assigned - active
        return (completed / assigned) * 100 if assigned > 0 else 50

    elif name == "spread":
        projects = metrics.get("project_count", 3)
        if 2 <= projects <= 5:
            return 100
        if projects == 1:
            return 60
        if projects > 5:
            return max(0, 100 - (projects - 5) * 10)
        return 50

    elif name == "availability_risk":
        # For percentile: dependency score = active * projects
        active = metrics.get("active_tasks", 0)
        projects = metrics.get("project_count", 1)
        return active * projects

    # PORTFOLIO DIMENSIONS
    elif name == "revenue_concentration":
        # This needs special handling - pass through for percentile
        return metrics.get("top_client_share", 0.5) * 100

    elif name == "resource_concentration":
        max_tasks = metrics.get("max_tasks_per_person", 10)
        avg_tasks = metrics.get("avg_tasks_per_person", 10) or 10
        ratio = max_tasks / avg_tasks
        return max(0, 100 - (ratio - 1) * 30)

    elif name == "client_health_distribution":
        return metrics.get("healthy_client_pct", 50) * 100

    elif name == "capacity_utilization":
        total = metrics.get("total_people", 1) or 1
        overloaded = metrics.get("people_overloaded", 0)
        available = metrics.get("people_available", 0)
        balanced = 1 - (overloaded / total) - (available / total)
        return max(0, balanced * 100)

    # Default: average of all metrics
    values = [v for v in metrics.values() if isinstance(v, (int, float))]
    return sum(values) / len(values) if values else 50.0


# =============================================================================
# SCORE CLASSIFICATION
# =============================================================================


def classify_score(score: float) -> str:
    """Map a 0-100 score to operational classification string."""
    if score is None:
        return "data_unavailable"
    if score <= 30:
        return "critical"
    elif score <= 50:
        return "at_risk"
    elif score <= 70:
        return "stable"
    elif score <= 90:
        return "healthy"
    else:
        return "strong"
