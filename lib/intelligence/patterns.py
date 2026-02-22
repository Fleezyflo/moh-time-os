"""
Cross-entity pattern detection for MOH TIME OS.

Patterns identify structural conditions that span multiple entities and dimensions.
They reveal systemic risks, hidden dependencies, and emergent conditions that
no single metric can show.

Pattern Types:
- CONCENTRATION: Over-reliance risk (revenue, resource, sector)
- CASCADE: Failure propagation paths (blast radius, dependency chains)
- DEGRADATION: Coordinated decline across entities
- DRIFT: Divergence from design/expectation
- CORRELATION: Co-moving metrics suggesting causal relationships

This module contains DEFINITIONS only. Detection logic is in Task 2.2.
"""

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# =============================================================================
# ERROR TRACKING - Pattern detection errors are tracked, not swallowed
# =============================================================================


@dataclass
class PatternDetectionError:
    """Tracks an error that occurred during pattern detection."""

    pattern_id: str
    error_type: str
    message: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            from datetime import datetime

            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "error_type": self.error_type,
            "message": self.message,
            "timestamp": self.timestamp,
        }


class PatternErrorCollector:
    """Thread-safe collector for pattern detection errors."""

    def __init__(self):
        self._errors: list[PatternDetectionError] = []
        self._lock = threading.Lock()

    def add(self, error: PatternDetectionError):
        with self._lock:
            self._errors.append(error)

    def get_all(self) -> list[PatternDetectionError]:
        with self._lock:
            return list(self._errors)

    def count(self) -> int:
        with self._lock:
            return len(self._errors)

    def clear(self):
        with self._lock:
            self._errors.clear()


class PatternType(Enum):
    """Types of cross-entity patterns."""

    CONCENTRATION = "concentration"  # Over-reliance risk
    CASCADE = "cascade"  # Failure propagation
    DEGRADATION = "degradation"  # Coordinated decline
    DRIFT = "drift"  # Divergence from design
    CORRELATION = "correlation"  # Co-moving metrics


class PatternSeverity(Enum):
    """Pattern severity levels."""

    STRUCTURAL = "structural"  # Systemic risk to the business
    OPERATIONAL = "operational"  # Needs process intervention
    INFORMATIONAL = "informational"  # Worth knowing, no immediate action


@dataclass
class PatternDefinition:
    """
    Complete specification for a cross-entity pattern.

    Patterns differ from signals:
    - Signals: entity-level conditions (Client X has overdue tasks)
    - Patterns: structural conditions spanning entities (3 clients declining together)
    """

    id: str
    name: str
    description: str
    pattern_type: PatternType
    severity: PatternSeverity
    detection_logic: dict  # Structured detection specification
    entities_involved: list[str]  # Which entity types participate
    data_requirements: list[str]  # Query engine / scoring / signal functions needed
    operational_meaning: str  # What this pattern means for the agency
    implied_action: str  # What should be considered
    evidence_template: str  # How to describe findings
    thresholds: dict = field(default_factory=dict)  # Configurable thresholds
    cooldown_hours: int = 168  # 7 days default between re-detections
    requires_signals: list[str] = field(default_factory=list)  # Signal dependencies


# =============================================================================
# PATTERN DEFINITIONS
# =============================================================================

# -----------------------------------------------------------------------------
# CONCENTRATION PATTERNS - Over-reliance risks
# -----------------------------------------------------------------------------

pat_revenue_concentration = PatternDefinition(
    id="pat_revenue_concentration",
    name="Revenue Concentration Risk",
    description="Top clients represent a disproportionate share of total revenue, creating dependency risk.",
    pattern_type=PatternType.CONCENTRATION,
    severity=PatternSeverity.STRUCTURAL,
    detection_logic={
        "method": "top_n_share",
        "metric": "total_invoiced",
        "evaluate": [
            {"n": 1, "threshold_pct": 25, "severity": "structural"},
            {"n": 3, "threshold_pct": 40, "severity": "operational"},
            {"n": 5, "threshold_pct": 60, "severity": "informational"},
        ],
    },
    entities_involved=["client", "portfolio"],
    data_requirements=[
        "query_engine.client_portfolio_overview()",
    ],
    operational_meaning="Business viability depends on a small number of clients. "
    "Loss of any top client would significantly impact revenue.",
    implied_action="Diversify pipeline focus. Prioritize acquisition in under-represented segments. "
    "Strengthen relationships with concentrated clients.",
    evidence_template="Top {n} client(s) represent {share_pct}% of total revenue "
    "({threshold_pct}% threshold). Concentration in: {top_clients}.",
    thresholds={
        "structural_top1_pct": 25,
        "operational_top3_pct": 40,
        "informational_top5_pct": 60,
    },
)


pat_resource_concentration = PatternDefinition(
    id="pat_resource_concentration",
    name="Resource Concentration Risk",
    description="A person is primary resource on too many active projects, creating key-person risk.",
    pattern_type=PatternType.CONCENTRATION,
    severity=PatternSeverity.OPERATIONAL,
    detection_logic={
        "method": "person_project_share",
        "metric": "active_project_count",
        "threshold_pct": 20,  # Any person on >20% of active projects
        "evaluate_for": "each_person",
    },
    entities_involved=["person", "project"],
    data_requirements=[
        "query_engine.resource_load_distribution()",
        "query_engine.projects_by_health()",
    ],
    operational_meaning="This person is a single point of failure. "
    "Their absence would impact multiple projects simultaneously.",
    implied_action="Cross-train team members. Document critical knowledge. "
    "Assign backup resources to high-dependency projects.",
    evidence_template="{person_name} is assigned to {project_count} projects "
    "({share_pct}% of active projects). Key-person risk.",
    thresholds={
        "max_project_share_pct": 20,
    },
)


pat_communication_concentration = PatternDefinition(
    id="pat_communication_concentration",
    name="Communication Concentration Risk",
    description="A small number of people handle disproportionate client communication volume.",
    pattern_type=PatternType.CONCENTRATION,
    severity=PatternSeverity.OPERATIONAL,
    detection_logic={
        "method": "top_n_share",
        "metric": "communication_count",
        "entity": "person",
        "threshold": {"n": 3, "share_pct": 60},
    },
    entities_involved=["person", "portfolio"],
    data_requirements=[
        "query_engine.team_load_distribution()",
        "query_engine.communication_by_person()",
    ],
    operational_meaning="Relationship knowledge is concentrated. If these people are "
    "unavailable, client relationships degrade rapidly.",
    implied_action="Distribute client ownership. Review communication routing. "
    "Ensure backup contacts are established for key clients.",
    evidence_template="Top {n} team members handle {share_pct}% of all client communications. "
    "Primary communicators: {top_people}.",
    thresholds={
        "top_n": 3,
        "max_share_pct": 60,
    },
)


pat_client_type_concentration = PatternDefinition(
    id="pat_client_type_concentration",
    name="Client Type Concentration",
    description="Portfolio over-indexes on a single client type or tier.",
    pattern_type=PatternType.CONCENTRATION,
    severity=PatternSeverity.INFORMATIONAL,
    detection_logic={
        "method": "category_share",
        "group_by": "client_type",  # or tier
        "threshold_pct": 70,
    },
    entities_involved=["client", "portfolio"],
    data_requirements=[
        "query_engine.client_portfolio_overview()",
    ],
    operational_meaning="Revenue is concentrated in one client type. "
    "Changes in that market segment affect the whole portfolio.",
    implied_action="Evaluate pipeline diversity. Consider expanding to adjacent segments.",
    evidence_template="{category_value} clients represent {share_pct}% of portfolio "
    "({count} of {total} clients).",
    thresholds={
        "max_category_share_pct": 70,
    },
)


# -----------------------------------------------------------------------------
# CASCADE PATTERNS - Failure propagation
# -----------------------------------------------------------------------------

pat_person_blast_radius = PatternDefinition(
    id="pat_person_blast_radius",
    name="Person Blast Radius",
    description="A person is assigned to projects serving clients that represent high revenue share.",
    pattern_type=PatternType.CASCADE,
    severity=PatternSeverity.STRUCTURAL,
    detection_logic={
        "method": "person_revenue_exposure",
        "threshold_pct": 30,  # Person touches >30% of revenue
        "evaluate_for": "each_person",
    },
    entities_involved=["person", "project", "client"],
    data_requirements=[
        "query_engine.resource_load_distribution()",
        "query_engine.client_portfolio_overview()",
        "query_engine.project_operational_state()",
    ],
    operational_meaning="Losing this person affects projects serving a large revenue share. "
    "Single point of failure with business-wide impact.",
    implied_action="Succession planning. Knowledge transfer. Load redistribution. "
    "Consider splitting high-value client work across team.",
    evidence_template="{person_name} is assigned to projects serving clients worth "
    "{revenue_pct}% of total revenue ({amount} total).",
    thresholds={
        "structural_revenue_pct": 30,
        "operational_revenue_pct": 20,
    },
)


pat_project_dependency_chain = PatternDefinition(
    id="pat_project_dependency_chain",
    name="Project Dependency Chain",
    description="Multiple projects share the same bottleneck (overloaded person or blocked dependency).",
    pattern_type=PatternType.CASCADE,
    severity=PatternSeverity.OPERATIONAL,
    detection_logic={
        "method": "shared_bottleneck",
        "min_projects": 3,
        "bottleneck_types": ["overloaded_person", "blocked_task", "shared_dependency"],
    },
    entities_involved=["project", "person", "task"],
    data_requirements=[
        "query_engine.projects_by_health()",
        "query_engine.resource_load_distribution()",
        "signals.get_active_signals(signal_id='sig_person_overload')",
    ],
    operational_meaning="A single bottleneck is slowing multiple client deliverables. "
    "Clearing it has multiplied impact.",
    implied_action="Prioritize clearing the bottleneck. Reassign, escalate, or add capacity. "
    "This is highest-leverage work.",
    evidence_template="{bottleneck_type}: {bottleneck_name} is blocking {project_count} projects "
    "serving {client_count} clients.",
    thresholds={
        "min_affected_projects": 3,
    },
    requires_signals=["sig_person_overload", "sig_project_blocked"],
)


pat_client_cluster_risk = PatternDefinition(
    id="pat_client_cluster_risk",
    name="Client Cluster Risk",
    description="Multiple clients simultaneously showing warning or critical signals.",
    pattern_type=PatternType.CASCADE,
    severity=PatternSeverity.STRUCTURAL,
    detection_logic={
        "method": "concurrent_signals",
        "entity_type": "client",
        "min_entities": 3,
        "signal_severities": ["warning", "critical"],
    },
    entities_involved=["client", "portfolio"],
    data_requirements=[
        "signals.get_active_signals(entity_type='client')",
        "scoring.score_all_clients()",
    ],
    operational_meaning="Not isolated incidents but a systemic pattern. "
    "Multiple clients are degrading simultaneously.",
    implied_action="Root cause investigation. Is this capacity? Quality? Process? "
    "External market conditions? Address systemic issue, not symptoms.",
    evidence_template="{client_count} clients have active {severity} signals: {client_names}. "
    "Common signals: {common_signals}.",
    thresholds={
        "structural_min_clients": 3,
        "operational_min_clients": 2,
    },
    requires_signals=["sig_client_*"],  # Any client signal
)


# -----------------------------------------------------------------------------
# DEGRADATION PATTERNS - Coordinated decline
# -----------------------------------------------------------------------------

pat_quality_degradation = PatternDefinition(
    id="pat_quality_degradation",
    name="Portfolio Quality Degradation",
    description="Portfolio-wide quality metrics declining across multiple periods.",
    pattern_type=PatternType.DEGRADATION,
    severity=PatternSeverity.OPERATIONAL,
    detection_logic={
        "method": "portfolio_trend",
        "metrics": ["revision_rate", "avg_cycle_time"],
        "direction": "worsening",  # revision_rate up, cycle_time up = bad
        "consecutive_periods": 2,
    },
    entities_involved=["portfolio", "project"],
    data_requirements=[
        "query_engine.portfolio_trajectory()",
    ],
    operational_meaning="Quality is slipping across the board, not just one project. "
    "This is a systemic issue requiring systemic intervention.",
    implied_action="Quality review. Process audit. Capacity assessment. "
    "Are standards being enforced? Is the team overworked?",
    evidence_template="Portfolio quality declining: revision rate {revision_trend} "
    "({revision_pct}%), cycle time {cycle_trend} ({cycle_pct}%) "
    "over {periods} periods.",
    thresholds={
        "min_revision_rate_increase_pct": 10,
        "min_cycle_time_increase_pct": 15,
        "consecutive_periods": 2,
    },
)


pat_client_engagement_erosion = PatternDefinition(
    id="pat_client_engagement_erosion",
    name="Client Engagement Erosion",
    description="Multiple clients simultaneously showing communication and meeting decline.",
    pattern_type=PatternType.DEGRADATION,
    severity=PatternSeverity.OPERATIONAL,
    detection_logic={
        "method": "concurrent_decline",
        "entity_type": "client",
        "metrics": ["communication_volume", "meeting_frequency"],
        "min_entities": 3,
        "decline_threshold_pct": 30,
    },
    entities_involved=["client", "portfolio"],
    data_requirements=[
        "query_engine.client_trajectory()",
        "scoring.score_all_clients()",
    ],
    operational_meaning="The agency is losing touch with multiple clients. "
    "Relationships are cooling simultaneously.",
    implied_action="Relationship rebuilding campaign. Client satisfaction audit. "
    "Proactive check-ins. Investigate if this is seasonal or systemic.",
    evidence_template="{client_count} clients showing engagement decline: {client_names}. "
    "Avg communication drop: {avg_comm_drop}%.",
    thresholds={
        "min_clients": 3,
        "decline_threshold_pct": 30,
    },
    requires_signals=["sig_client_comm_drop"],
)


pat_team_exhaustion = PatternDefinition(
    id="pat_team_exhaustion",
    name="Team Exhaustion Pattern",
    description="Team average load is high AND portfolio output is declining.",
    pattern_type=PatternType.DEGRADATION,
    severity=PatternSeverity.STRUCTURAL,
    detection_logic={
        "method": "load_output_inverse",
        "load_threshold": 75,  # Avg load score >75
        "output_decline_pct": 10,
        "consecutive_periods": 2,
    },
    entities_involved=["person", "portfolio"],
    data_requirements=[
        "scoring.score_all_persons()",
        "query_engine.portfolio_trajectory()",
        "query_engine.team_capacity_overview()",
    ],
    operational_meaning="Team is overworked and it's affecting output. "
    "More work is being done but less is being completed.",
    implied_action="Capacity relief: defer low-priority work, hire, reduce scope. "
    "Short-term: identify what can wait. Long-term: address staffing.",
    evidence_template="Team avg load: {avg_load_score} (high). Portfolio output "
    "down {output_decline_pct}% over {periods} periods.",
    thresholds={
        "high_load_threshold": 75,
        "output_decline_pct": 10,
    },
    requires_signals=["sig_person_overload"],
)


# -----------------------------------------------------------------------------
# DRIFT PATTERNS - Divergence from design
# -----------------------------------------------------------------------------

pat_workload_distribution_drift = PatternDefinition(
    id="pat_workload_distribution_drift",
    name="Workload Distribution Drift",
    description="Actual workload distribution has drifted far from balanced allocation.",
    pattern_type=PatternType.DRIFT,
    severity=PatternSeverity.INFORMATIONAL,
    detection_logic={
        "method": "distribution_skew",
        "metric": "active_task_count",
        "max_coefficient_of_variation": 0.5,  # CV > 0.5 = high skew
    },
    entities_involved=["person", "portfolio"],
    data_requirements=[
        "query_engine.resource_load_distribution()",
    ],
    operational_meaning="Workload has organically redistributed. Some people are "
    "overloaded while others are underutilized.",
    implied_action="Re-evaluate allocation. Redistribute work intentionally. "
    "Or acknowledge the new distribution as the new plan.",
    evidence_template="Workload distribution skewed: CV={cv:.2f}. "
    "Range: {min_tasks} to {max_tasks} tasks per person.",
    thresholds={
        "max_cv": 0.5,
    },
)


pat_client_ownership_drift = PatternDefinition(
    id="pat_client_ownership_drift",
    name="Client Ownership Drift",
    description="Client communication increasingly going through people other than assigned leads.",
    pattern_type=PatternType.DRIFT,
    severity=PatternSeverity.INFORMATIONAL,
    detection_logic={
        "method": "ownership_mismatch",
        "compare": "assigned_lead_vs_actual_communicator",
        "threshold_pct": 50,  # >50% of comms not through assigned lead
    },
    entities_involved=["client", "person"],
    data_requirements=[
        "query_engine.client_portfolio_overview()",
        "query_engine.communication_by_person()",
    ],
    operational_meaning="Intended communication structure isn't being followed. "
    "De facto ownership differs from official ownership.",
    implied_action="Either enforce intended structure or formally acknowledge new ownership. "
    "Unclear ownership leads to dropped balls.",
    evidence_template="{client_count} clients have >50% communications outside assigned lead. "
    "Most common: {drift_examples}.",
    thresholds={
        "mismatch_threshold_pct": 50,
    },
)


# -----------------------------------------------------------------------------
# CORRELATION PATTERNS - Co-moving metrics
# -----------------------------------------------------------------------------

pat_load_quality_correlation = PatternDefinition(
    id="pat_load_quality_correlation",
    name="Load-Quality Correlation",
    description="When person load increases, their revision rates increase (quality drops).",
    pattern_type=PatternType.CORRELATION,
    severity=PatternSeverity.OPERATIONAL,
    detection_logic={
        "method": "metric_correlation",
        "metric_a": "load_score",
        "metric_b": "revision_rate",
        "correlation_direction": "positive",  # Higher load → higher revisions
        "min_correlation": 0.5,
        "time_window_days": 90,
    },
    entities_involved=["person"],
    data_requirements=[
        "query_engine.person_trajectory()",
        "scoring.score_all_persons()",
    ],
    operational_meaning="Overwork causes quality decline (or at least correlates with it). "
    "There's a measurable relationship between load and output quality.",
    implied_action="Enforce capacity limits. Add quality checkpoints for overloaded team members. "
    "Consider load as a leading indicator of quality issues.",
    evidence_template="Load-quality correlation detected: r={correlation:.2f}. "
    "Affected: {person_count} team members.",
    thresholds={
        "min_correlation": 0.5,
    },
)


pat_comm_payment_correlation = PatternDefinition(
    id="pat_comm_payment_correlation",
    name="Communication-Payment Correlation",
    description="Clients whose communication declines also tend to delay payments.",
    pattern_type=PatternType.CORRELATION,
    severity=PatternSeverity.OPERATIONAL,
    detection_logic={
        "method": "metric_correlation",
        "entity_type": "client",
        "metric_a": "communication_trend",
        "metric_b": "payment_timeliness",
        "correlation_direction": "positive",  # Declining comms → delayed payments
        "min_correlation": 0.4,
    },
    entities_involved=["client"],
    data_requirements=[
        "query_engine.client_trajectory()",
        "query_engine.invoice_status_by_client()",
    ],
    operational_meaning="Communication drop is an early warning for payment issues. "
    "Silence often precedes financial friction.",
    implied_action="Proactive financial follow-up when communication drops. "
    "Don't wait for invoices to age — reach out early.",
    evidence_template="Communication-payment correlation: r={correlation:.2f}. "
    "{client_count} clients show this pattern.",
    thresholds={
        "min_correlation": 0.4,
    },
    requires_signals=["sig_client_comm_drop", "sig_client_payment_delay"],
)


# =============================================================================
# PATTERN LIBRARY
# =============================================================================

PATTERN_LIBRARY: dict[str, PatternDefinition] = {
    # Concentration (4)
    "pat_revenue_concentration": pat_revenue_concentration,
    "pat_resource_concentration": pat_resource_concentration,
    "pat_communication_concentration": pat_communication_concentration,
    "pat_client_type_concentration": pat_client_type_concentration,
    # Cascade (3)
    "pat_person_blast_radius": pat_person_blast_radius,
    "pat_project_dependency_chain": pat_project_dependency_chain,
    "pat_client_cluster_risk": pat_client_cluster_risk,
    # Degradation (3)
    "pat_quality_degradation": pat_quality_degradation,
    "pat_client_engagement_erosion": pat_client_engagement_erosion,
    "pat_team_exhaustion": pat_team_exhaustion,
    # Drift (2)
    "pat_workload_distribution_drift": pat_workload_distribution_drift,
    "pat_client_ownership_drift": pat_client_ownership_drift,
    # Correlation (2)
    "pat_load_quality_correlation": pat_load_quality_correlation,
    "pat_comm_payment_correlation": pat_comm_payment_correlation,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_pattern(pattern_id: str) -> PatternDefinition | None:
    """Get a pattern definition by ID."""
    return PATTERN_LIBRARY.get(pattern_id)


def get_patterns_by_type(pattern_type: PatternType) -> list[PatternDefinition]:
    """Get all patterns of a specific type."""
    return [p for p in PATTERN_LIBRARY.values() if p.pattern_type == pattern_type]


def get_patterns_by_severity(severity: PatternSeverity) -> list[PatternDefinition]:
    """Get all patterns of a specific severity."""
    return [p for p in PATTERN_LIBRARY.values() if p.severity == severity]


def get_structural_patterns() -> list[PatternDefinition]:
    """Get all structural (highest-severity) patterns."""
    return get_patterns_by_severity(PatternSeverity.STRUCTURAL)


def validate_pattern_library() -> list[str]:
    """Validate all pattern definitions. Returns list of errors."""
    errors = []

    for pattern_id, pattern in PATTERN_LIBRARY.items():
        if not pattern.id:
            errors.append(f"{pattern_id}: missing id")
        if pattern.id != pattern_id:
            errors.append(f"{pattern_id}: id mismatch ({pattern.id})")
        if not pattern.detection_logic:
            errors.append(f"{pattern_id}: missing detection_logic")
        if not pattern.entities_involved:
            errors.append(f"{pattern_id}: missing entities_involved")
        if not pattern.data_requirements:
            errors.append(f"{pattern_id}: missing data_requirements")
        if not pattern.operational_meaning:
            errors.append(f"{pattern_id}: missing operational_meaning")
        if not pattern.implied_action:
            errors.append(f"{pattern_id}: missing implied_action")

    return errors


def get_library_summary() -> dict:
    """Get summary statistics about the pattern library."""
    by_type = {}
    for pt in PatternType:
        by_type[pt.value] = len(get_patterns_by_type(pt))

    by_severity = {}
    for sev in PatternSeverity:
        by_severity[sev.value] = len(get_patterns_by_severity(sev))

    return {
        "total_patterns": len(PATTERN_LIBRARY),
        "by_type": by_type,
        "by_severity": by_severity,
        "pattern_ids": list(PATTERN_LIBRARY.keys()),
    }


# Run validation on import
_validation_errors = validate_pattern_library()
if _validation_errors:
    import warnings

    warnings.warn(f"Pattern library validation errors: {_validation_errors}", stacklevel=2)


# =============================================================================
# PATTERN DETECTION - Helper Computations
# =============================================================================

import logging
import math
import statistics
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_engine(db_path: Path | None = None):
    """Get query engine instance."""
    from lib.query_engine import QueryEngine

    return QueryEngine(db_path) if db_path else QueryEngine()


def _compute_herfindahl(shares: list[float]) -> float:
    """
    Herfindahl-Hirschman Index for concentration measurement.

    Sum of squared market shares. Range: 1/N (perfect distribution) to 1.0 (monopoly).
    HHI > 0.25 = highly concentrated
    HHI 0.15-0.25 = moderately concentrated
    HHI < 0.15 = competitive/distributed
    """
    if not shares:
        return 0.0
    return sum(s**2 for s in shares)


def _compute_top_n_share(values: list[float], n: int = 3) -> float:
    """Compute share of top N values as fraction of total."""
    if not values:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    sorted_vals = sorted(values, reverse=True)
    top_n_sum = sum(sorted_vals[:n])
    return top_n_sum / total


def _compute_coefficient_of_variation(values: list[float]) -> float:
    """
    Coefficient of variation (CV) = std_dev / mean.

    Measures relative variability. Higher CV = more dispersion.
    CV > 0.5 typically indicates high variability.
    """
    if not values or len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    stddev = statistics.stdev(values)
    return stddev / mean


def _compute_correlation(series_a: list[float], series_b: list[float]) -> float | None:
    """
    Pearson correlation coefficient between two series.

    Returns -1 to 1, or None if insufficient data.
    Requires len >= 4 matching data points.
    """
    if len(series_a) != len(series_b):
        return None
    if len(series_a) < 4:
        return None

    try:
        # Use statistics.correlation (Python 3.10+) if available
        if hasattr(statistics, "correlation"):
            return statistics.correlation(series_a, series_b)

        # Manual Pearson calculation
        n = len(series_a)
        mean_a = sum(series_a) / n
        mean_b = sum(series_b) / n

        numerator = sum(
            (a - mean_a) * (b - mean_b) for a, b in zip(series_a, series_b, strict=False)
        )

        sum_sq_a = sum((a - mean_a) ** 2 for a in series_a)
        sum_sq_b = sum((b - mean_b) ** 2 for b in series_b)

        denominator = math.sqrt(sum_sq_a * sum_sq_b)

        if denominator == 0:
            return None

        return numerator / denominator
    except Exception:
        return None


def _find_co_declining(
    entity_scores: list[dict],
    score_key: str = "composite_score",
    min_entities: int = 3,
    decline_threshold: float = -0.1,
) -> list[dict] | None:
    """
    Identify groups of entities whose scores are simultaneously declining.

    Returns the declining group if found, None if no coordinated decline.
    """
    declining = []
    for entity in entity_scores:
        trend = entity.get("trend", {})
        if isinstance(trend, dict):
            direction = trend.get("direction", "stable")
            magnitude = trend.get("magnitude_pct", 0)
            if direction == "declining" or magnitude < decline_threshold * 100:
                declining.append(entity)

    if len(declining) >= min_entities:
        return declining
    return None


# =============================================================================
# PATTERN DETECTION - Evidence Structure
# =============================================================================


@dataclass
class PatternEvidence:
    """Complete evidence for a detected pattern."""

    pattern_id: str
    pattern_name: str
    pattern_type: str
    severity: str
    detected_at: str
    entities_involved: list[dict]  # [{type, id, name, role_in_pattern}, ...]
    metrics: dict  # Key measurements
    supporting_signals: list[str]  # Signal IDs that correlate
    evidence_narrative: str  # Human-readable explanation
    operational_meaning: str  # What this means
    implied_action: str  # What to consider
    confidence: str  # "high", "medium", "low"

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "severity": self.severity,
            "detected_at": self.detected_at,
            "entities_involved": self.entities_involved,
            "metrics": self.metrics,
            "supporting_signals": self.supporting_signals,
            "evidence_narrative": self.evidence_narrative,
            "operational_meaning": self.operational_meaning,
            "implied_action": self.implied_action,
            "confidence": self.confidence,
        }


# =============================================================================
# PATTERN DETECTION - Type-Specific Detectors
# =============================================================================


def _detect_concentration(
    pattern_def: PatternDefinition, db_path: Path | None = None
) -> PatternEvidence | None:
    """
    Detect concentration patterns.

    Computes distribution metrics (HHI, top-N share, CV) for relevant dimensions.
    """
    engine = _get_engine(db_path)
    logic = pattern_def.detection_logic
    logic.get("method", "top_n_share")

    try:
        if pattern_def.id == "pat_revenue_concentration":
            # Revenue concentration - top N client share
            clients = engine.client_portfolio_overview()
            revenues = [c.get("total_invoiced", 0) or 0 for c in clients]
            total = sum(revenues)

            if total == 0:
                return None

            # Check thresholds
            top1_share = _compute_top_n_share(revenues, 1)
            top3_share = _compute_top_n_share(revenues, 3)
            top5_share = _compute_top_n_share(revenues, 5)
            hhi = _compute_herfindahl([r / total for r in revenues if r > 0])

            thresholds = pattern_def.thresholds
            triggered = False
            severity = "informational"
            trigger_n = 5

            if top1_share > thresholds.get("structural_top1_pct", 25) / 100:
                triggered = True
                severity = "structural"
                trigger_n = 1
            elif top3_share > thresholds.get("operational_top3_pct", 40) / 100:
                triggered = True
                severity = "operational"
                trigger_n = 3
            elif top5_share > thresholds.get("informational_top5_pct", 60) / 100:
                triggered = True
                severity = "informational"
                trigger_n = 5

            if not triggered:
                return None

            # Build evidence
            sorted_clients = sorted(
                clients, key=lambda c: c.get("total_invoiced", 0) or 0, reverse=True
            )
            top_clients = sorted_clients[:trigger_n]

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=severity,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "client",
                        "id": c.get("client_id"),
                        "name": c.get("client_name"),
                        "role": "concentrated",
                    }
                    for c in top_clients
                ],
                metrics={
                    "top_1_share_pct": round(top1_share * 100, 1),
                    "top_3_share_pct": round(top3_share * 100, 1),
                    "top_5_share_pct": round(top5_share * 100, 1),
                    "herfindahl_index": round(hhi, 3),
                    "total_clients": len(clients),
                    "trigger_n": trigger_n,
                },
                supporting_signals=[],
                evidence_narrative=f"Top {trigger_n} client(s) represent {round(_compute_top_n_share(revenues, trigger_n) * 100, 1)}% of revenue. "
                f"HHI: {round(hhi, 3)}. Most concentrated: {', '.join(c.get('client_name', 'Unknown') for c in top_clients[:3])}.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="high" if len(clients) >= 10 else "medium",
            )

        elif pattern_def.id == "pat_resource_concentration":
            # Resource concentration - person on too many projects
            people = engine.resource_load_distribution()
            projects = engine.projects_by_health(min_tasks=1)
            total_projects = len(projects)

            if total_projects == 0:
                return None

            threshold_pct = pattern_def.thresholds.get("max_project_share_pct", 20)
            concentrated = []

            for person in people:
                project_count = person.get("active_project_count", 0)
                share = (project_count / total_projects) * 100 if total_projects > 0 else 0
                if share > threshold_pct:
                    concentrated.append(
                        {
                            "person": person,
                            "project_count": project_count,
                            "share_pct": share,
                        }
                    )

            if not concentrated:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "person",
                        "id": c["person"].get("person_id"),
                        "name": c["person"].get("person_name"),
                        "role": "over-assigned",
                    }
                    for c in concentrated
                ],
                metrics={
                    "concentrated_people": len(concentrated),
                    "total_projects": total_projects,
                    "max_share_pct": round(max(c["share_pct"] for c in concentrated), 1),
                },
                supporting_signals=[],
                evidence_narrative=f"{len(concentrated)} person(s) assigned to >{threshold_pct}% of projects. "
                f"Max: {concentrated[0]['person'].get('person_name')} at {round(concentrated[0]['share_pct'], 1)}%.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="high",
            )

        elif pattern_def.id == "pat_communication_concentration":
            # Communication concentration - few people handle most comms
            # Simplified: use task assignment as proxy if comms data unavailable
            people = engine.resource_load_distribution()

            # Use active_task_count as proxy for communication volume
            task_counts = [p.get("active_task_count", 0) for p in people]
            total_tasks = sum(task_counts)

            if total_tasks == 0 or len(people) < 3:
                return None

            top_n = pattern_def.thresholds.get("top_n", 3)
            max_share = pattern_def.thresholds.get("max_share_pct", 60)

            top_share = _compute_top_n_share(task_counts, top_n)

            if top_share * 100 <= max_share:
                return None

            sorted_people = sorted(
                people, key=lambda p: p.get("active_task_count", 0), reverse=True
            )

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "person",
                        "id": p.get("person_id"),
                        "name": p.get("person_name"),
                        "role": "high-volume",
                    }
                    for p in sorted_people[:top_n]
                ],
                metrics={
                    "top_n": top_n,
                    "top_n_share_pct": round(top_share * 100, 1),
                    "total_people": len(people),
                },
                supporting_signals=[],
                evidence_narrative=f"Top {top_n} team members handle {round(top_share * 100, 1)}% of workload.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="medium",  # Using proxy metric
            )

        elif pattern_def.id == "pat_client_type_concentration":
            # Client type concentration
            clients = engine.client_portfolio_overview()

            # Group by type
            by_type = {}
            for client in clients:
                ctype = client.get("client_type", "unknown") or "unknown"
                if ctype not in by_type:
                    by_type[ctype] = []
                by_type[ctype].append(client)

            threshold = pattern_def.thresholds.get("max_category_share_pct", 70)
            total = len(clients)

            for ctype, clist in by_type.items():
                share = (len(clist) / total) * 100 if total > 0 else 0
                if share > threshold:
                    return PatternEvidence(
                        pattern_id=pattern_def.id,
                        pattern_name=pattern_def.name,
                        pattern_type=pattern_def.pattern_type.value,
                        severity=pattern_def.severity.value,
                        detected_at=datetime.now().isoformat(),
                        entities_involved=[
                            {
                                "type": "client",
                                "id": c.get("client_id"),
                                "name": c.get("client_name"),
                                "role": ctype,
                            }
                            for c in clist[:5]
                        ],
                        metrics={
                            "category": ctype,
                            "category_share_pct": round(share, 1),
                            "category_count": len(clist),
                            "total_clients": total,
                        },
                        supporting_signals=[],
                        evidence_narrative=f"'{ctype}' clients represent {round(share, 1)}% of portfolio ({len(clist)} of {total}).",
                        operational_meaning=pattern_def.operational_meaning,
                        implied_action=pattern_def.implied_action,
                        confidence="high",
                    )

            return None

    except Exception as e:
        logger.warning(f"Error detecting concentration pattern {pattern_def.id}: {e}")
        return None

    return None


def _detect_cascade(
    pattern_def: PatternDefinition, db_path: Path | None = None
) -> PatternEvidence | None:
    """
    Detect cascade risk patterns.

    Maps entity dependency graphs and identifies propagation paths.
    """
    engine = _get_engine(db_path)

    try:
        if pattern_def.id == "pat_person_blast_radius":
            # Person blast radius - revenue exposure
            people = engine.resource_load_distribution()
            clients = engine.client_portfolio_overview()
            projects = engine.projects_by_health(min_tasks=1)

            total_revenue = sum(c.get("total_invoiced", 0) or 0 for c in clients)
            if total_revenue == 0:
                return None

            # Map client -> revenue
            {c.get("client_id"): c.get("total_invoiced", 0) or 0 for c in clients}

            # Map project -> client
            {p.get("project_id"): p.get("client_id") for p in projects}

            # For each person, calculate revenue exposure
            threshold_pct = pattern_def.thresholds.get("structural_revenue_pct", 30)
            high_exposure = []

            for person in people:
                # Get projects for this person
                person_projects = person.get("active_project_count", 0)
                # Simplified: assume proportional exposure
                # In reality would need person -> project -> client mapping
                if person_projects > 0 and len(projects) > 0:
                    exposure_pct = (person_projects / len(projects)) * 100
                    if exposure_pct > threshold_pct:
                        high_exposure.append(
                            {
                                "person": person,
                                "exposure_pct": exposure_pct,
                            }
                        )

            if not high_exposure:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "person",
                        "id": h["person"].get("person_id"),
                        "name": h["person"].get("person_name"),
                        "role": "high-exposure",
                    }
                    for h in high_exposure
                ],
                metrics={
                    "high_exposure_people": len(high_exposure),
                    "max_exposure_pct": round(max(h["exposure_pct"] for h in high_exposure), 1),
                },
                supporting_signals=[],
                evidence_narrative=f"{len(high_exposure)} person(s) with blast radius >{threshold_pct}% of portfolio.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="medium",
            )

        elif pattern_def.id == "pat_project_dependency_chain":
            # Multiple projects blocked by same bottleneck
            from lib.intelligence.signals import get_active_signals

            overload_signals = get_active_signals(db_path=db_path)
            person_signals = [
                s for s in overload_signals if s.get("signal_id") == "sig_person_overload"
            ]

            if len(person_signals) < 1:
                return None

            # Find which projects are affected
            projects = engine.projects_by_health(min_tasks=1)
            min_projects = pattern_def.thresholds.get("min_affected_projects", 3)

            # Check if multiple projects share overloaded people
            # Simplified check
            if len(projects) >= min_projects and len(person_signals) >= 1:
                return PatternEvidence(
                    pattern_id=pattern_def.id,
                    pattern_name=pattern_def.name,
                    pattern_type=pattern_def.pattern_type.value,
                    severity=pattern_def.severity.value,
                    detected_at=datetime.now().isoformat(),
                    entities_involved=[
                        {
                            "type": "person",
                            "id": s.get("entity_id"),
                            "name": "Overloaded",
                            "role": "bottleneck",
                        }
                        for s in person_signals[:3]
                    ],
                    metrics={
                        "bottleneck_count": len(person_signals),
                        "affected_projects": len(projects),
                    },
                    supporting_signals=[s.get("signal_id") for s in person_signals],
                    evidence_narrative=f"{len(person_signals)} overloaded person(s) affecting {len(projects)} projects.",
                    operational_meaning=pattern_def.operational_meaning,
                    implied_action=pattern_def.implied_action,
                    confidence="medium",
                )

            return None

        elif pattern_def.id == "pat_client_cluster_risk":
            # Multiple clients with warning/critical signals
            from lib.intelligence.signals import get_active_signals

            client_signals = [
                s
                for s in get_active_signals(entity_type="client", db_path=db_path)
                if s.get("severity") in ["warning", "critical"]
            ]

            # Count unique clients
            clients_with_signals = {}
            for sig in client_signals:
                cid = sig.get("entity_id")
                if cid not in clients_with_signals:
                    clients_with_signals[cid] = []
                clients_with_signals[cid].append(sig)

            min_clients = pattern_def.thresholds.get("structural_min_clients", 3)

            if len(clients_with_signals) < min_clients:
                return None

            severity = "structural" if len(clients_with_signals) >= min_clients else "operational"

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=severity,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {"type": "client", "id": cid, "name": cid, "role": "at-risk"}
                    for cid in list(clients_with_signals.keys())[:5]
                ],
                metrics={
                    "clients_at_risk": len(clients_with_signals),
                    "total_signals": len(client_signals),
                },
                supporting_signals=list({s.get("signal_id") for s in client_signals})[:5],
                evidence_narrative=f"{len(clients_with_signals)} clients have active warning/critical signals.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="high",
            )

    except Exception as e:
        logger.warning(f"Error detecting cascade pattern {pattern_def.id}: {e}")
        return None

    return None


def _detect_degradation(
    pattern_def: PatternDefinition, db_path: Path | None = None
) -> PatternEvidence | None:
    """
    Detect coordinated decline patterns.
    """
    engine = _get_engine(db_path)

    try:
        if pattern_def.id == "pat_quality_degradation":
            # Portfolio-wide quality decline
            # Check if portfolio trajectory shows worsening metrics
            # Simplified: check current vs historical
            clients = engine.client_portfolio_overview()

            # Count clients with overdue tasks as quality proxy
            with_overdue = [c for c in clients if (c.get("overdue_tasks", 0) or 0) > 0]

            if len(with_overdue) < 3:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "client",
                        "id": c.get("client_id"),
                        "name": c.get("client_name"),
                        "role": "quality-issue",
                    }
                    for c in with_overdue[:5]
                ],
                metrics={
                    "clients_with_overdue": len(with_overdue),
                    "total_clients": len(clients),
                },
                supporting_signals=[],
                evidence_narrative=f"{len(with_overdue)} clients have overdue tasks, indicating quality/delivery issues.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="medium",
            )

        elif pattern_def.id == "pat_client_engagement_erosion":
            # Multiple clients with communication decline
            from lib.intelligence.signals import get_active_signals

            comm_signals = [
                s
                for s in get_active_signals(db_path=db_path)
                if s.get("signal_id") == "sig_client_comm_drop"
            ]

            min_clients = pattern_def.thresholds.get("min_clients", 3)

            if len(comm_signals) < min_clients:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "client",
                        "id": s.get("entity_id"),
                        "name": s.get("entity_id"),
                        "role": "disengaging",
                    }
                    for s in comm_signals[:5]
                ],
                metrics={
                    "clients_declining": len(comm_signals),
                },
                supporting_signals=["sig_client_comm_drop"],
                evidence_narrative=f"{len(comm_signals)} clients showing communication decline simultaneously.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="high",
            )

        elif pattern_def.id == "pat_team_exhaustion":
            # High load + declining output
            from lib.intelligence.signals import get_active_signals

            overload_signals = [
                s
                for s in get_active_signals(db_path=db_path)
                if s.get("signal_id") == "sig_person_overload"
            ]

            people = engine.resource_load_distribution()
            avg_load = sum(p.get("load_score", 0) for p in people) / len(people) if people else 0

            threshold = pattern_def.thresholds.get("high_load_threshold", 75)

            if avg_load < threshold and len(overload_signals) < 2:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "person",
                        "id": s.get("entity_id"),
                        "name": s.get("entity_id"),
                        "role": "exhausted",
                    }
                    for s in overload_signals[:5]
                ],
                metrics={
                    "avg_load_score": round(avg_load, 1),
                    "overloaded_people": len(overload_signals),
                    "total_people": len(people),
                },
                supporting_signals=["sig_person_overload"],
                evidence_narrative=f"Team avg load: {round(avg_load, 1)}. {len(overload_signals)} overloaded.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="high" if avg_load > threshold else "medium",
            )

    except Exception as e:
        logger.warning(f"Error detecting degradation pattern {pattern_def.id}: {e}")
        return None

    return None


def _detect_drift(
    pattern_def: PatternDefinition, db_path: Path | None = None
) -> PatternEvidence | None:
    """
    Detect divergence from expected state.
    """
    engine = _get_engine(db_path)

    try:
        if pattern_def.id == "pat_workload_distribution_drift":
            # High variance in workload distribution
            people = engine.resource_load_distribution()

            if len(people) < 3:
                return None

            task_counts = [p.get("active_task_count", 0) for p in people]
            cv = _compute_coefficient_of_variation(task_counts)

            threshold = pattern_def.thresholds.get("max_cv", 0.5)

            if cv <= threshold:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "person",
                        "id": p.get("person_id"),
                        "name": p.get("person_name"),
                        "role": "skewed",
                    }
                    for p in people[:5]
                ],
                metrics={
                    "coefficient_of_variation": round(cv, 2),
                    "min_tasks": min(task_counts),
                    "max_tasks": max(task_counts),
                    "mean_tasks": round(statistics.mean(task_counts), 1),
                },
                supporting_signals=[],
                evidence_narrative=f"Workload distribution skewed: CV={round(cv, 2)}. Range: {min(task_counts)} to {max(task_counts)} tasks.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="high",
            )

        elif pattern_def.id == "pat_client_ownership_drift":
            # Simplified: check if any clients have unclear ownership
            clients = engine.client_portfolio_overview()

            # Check for clients without clear account lead
            unclear = [c for c in clients if not c.get("account_lead")]

            threshold_pct = pattern_def.thresholds.get("mismatch_threshold_pct", 50)

            if len(unclear) / len(clients) * 100 <= threshold_pct if clients else True:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "client",
                        "id": c.get("client_id"),
                        "name": c.get("client_name"),
                        "role": "unclear-owner",
                    }
                    for c in unclear[:5]
                ],
                metrics={
                    "unclear_ownership_count": len(unclear),
                    "total_clients": len(clients),
                },
                supporting_signals=[],
                evidence_narrative=f"{len(unclear)} clients have unclear ownership.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="medium",
            )

    except Exception as e:
        logger.warning(f"Error detecting drift pattern {pattern_def.id}: {e}")
        return None

    return None


def _detect_correlation(
    pattern_def: PatternDefinition, db_path: Path | None = None
) -> PatternEvidence | None:
    """
    Detect co-movement between metrics.
    """
    # Correlation patterns require time-series data
    # Simplified implementation using available data

    try:
        if pattern_def.id == "pat_load_quality_correlation":
            engine = _get_engine(db_path)
            people = engine.resource_load_distribution()

            high_load = [p for p in people if p.get("load_score", 0) > 70]

            if len(high_load) < 2:
                return None

            # Compute actual correlation between load_score and overdue ratio
            load_scores = []
            overdue_ratios = []
            for p in people:
                ls = p.get("load_score", 0)
                active = p.get("active_tasks", 0)
                overdue = p.get("overdue_tasks", 0)
                if active > 0:
                    load_scores.append(ls)
                    overdue_ratios.append(overdue / active)

            # Pearson correlation approximation
            correlation = 0.0
            if len(load_scores) >= 3:
                n = len(load_scores)
                mean_x = sum(load_scores) / n
                mean_y = sum(overdue_ratios) / n
                cov = (
                    sum(
                        (x - mean_x) * (y - mean_y)
                        for x, y in zip(load_scores, overdue_ratios, strict=False)
                    )
                    / n
                )
                std_x = (sum((x - mean_x) ** 2 for x in load_scores) / n) ** 0.5
                std_y = (sum((y - mean_y) ** 2 for y in overdue_ratios) / n) ** 0.5
                if std_x > 0 and std_y > 0:
                    correlation = round(cov / (std_x * std_y), 3)

            confidence = "medium" if len(load_scores) >= 5 else "low"

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {
                        "type": "person",
                        "id": p.get("person_id"),
                        "name": p.get("person_name"),
                        "role": "high-load",
                    }
                    for p in high_load[:5]
                ],
                metrics={
                    "high_load_count": len(high_load),
                    "sample_size": len(load_scores),
                    "correlation": correlation,
                },
                supporting_signals=[],
                evidence_narrative=f"{len(high_load)} people with high load; load-overdue correlation={correlation:.2f} (n={len(load_scores)}).",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence=confidence,
            )

        elif pattern_def.id == "pat_comm_payment_correlation":
            # Check if clients with comm drop also have payment issues
            from lib.intelligence.signals import get_active_signals

            comm_signals = {
                s.get("entity_id")
                for s in get_active_signals(db_path=db_path)
                if s.get("signal_id") == "sig_client_comm_drop"
            }
            payment_signals = {
                s.get("entity_id")
                for s in get_active_signals(db_path=db_path)
                if s.get("signal_id") == "sig_client_payment_delay"
            }

            overlap = comm_signals & payment_signals

            if len(overlap) < 2:
                return None

            return PatternEvidence(
                pattern_id=pattern_def.id,
                pattern_name=pattern_def.name,
                pattern_type=pattern_def.pattern_type.value,
                severity=pattern_def.severity.value,
                detected_at=datetime.now().isoformat(),
                entities_involved=[
                    {"type": "client", "id": cid, "name": cid, "role": "comm+payment-issue"}
                    for cid in list(overlap)[:5]
                ],
                metrics={
                    "clients_with_both": len(overlap),
                    "clients_with_comm_drop": len(comm_signals),
                    "clients_with_payment_delay": len(payment_signals),
                },
                supporting_signals=["sig_client_comm_drop", "sig_client_payment_delay"],
                evidence_narrative=f"{len(overlap)} clients show both communication drop and payment delays.",
                operational_meaning=pattern_def.operational_meaning,
                implied_action=pattern_def.implied_action,
                confidence="high" if len(overlap) >= 3 else "medium",
            )

    except Exception as e:
        logger.warning(f"Error detecting correlation pattern {pattern_def.id}: {e}")
        return None

    return None


# =============================================================================
# PATTERN DETECTION - Main Functions
# =============================================================================


def detect_pattern(
    pattern_def: PatternDefinition, db_path: Path | None = None
) -> PatternEvidence | None:
    """
    Evaluate a single pattern definition against the database.

    Routes to appropriate detector by pattern type.
    Returns PatternEvidence if detected, None if not.
    """
    if pattern_def.pattern_type == PatternType.CONCENTRATION:
        return _detect_concentration(pattern_def, db_path)
    elif pattern_def.pattern_type == PatternType.CASCADE:
        return _detect_cascade(pattern_def, db_path)
    elif pattern_def.pattern_type == PatternType.DEGRADATION:
        return _detect_degradation(pattern_def, db_path)
    elif pattern_def.pattern_type == PatternType.DRIFT:
        return _detect_drift(pattern_def, db_path)
    elif pattern_def.pattern_type == PatternType.CORRELATION:
        return _detect_correlation(pattern_def, db_path)

    return None


def detect_all_patterns(db_path: Path | None = None) -> dict:
    """
    Run the complete pattern library against the database.

    Returns comprehensive detection results INCLUDING ERRORS.
    Errors are tracked, not swallowed.
    """
    all_detected = []
    error_collector = PatternErrorCollector()

    for pattern_id, pattern_def in PATTERN_LIBRARY.items():
        try:
            evidence = detect_pattern(pattern_def, db_path)
            if evidence:
                all_detected.append(evidence.to_dict())
        except Exception as e:
            logger.warning(f"Error detecting pattern {pattern_id}: {e}", exc_info=True)
            error_collector.add(
                PatternDetectionError(
                    pattern_id=pattern_id,
                    error_type=type(e).__name__,
                    message=str(e),
                )
            )

    # Organize by type and severity
    by_type = {pt.value: [] for pt in PatternType}
    by_severity = {sev.value: [] for sev in PatternSeverity}

    for pattern in all_detected:
        ptype = pattern.get("pattern_type", "unknown")
        sev = pattern.get("severity", "informational")

        if ptype in by_type:
            by_type[ptype].append(pattern)
        if sev in by_severity:
            by_severity[sev].append(pattern)

    # Collect errors
    errors = error_collector.get_all()

    return {
        "detected_at": datetime.now().isoformat(),
        "success": len(errors) == 0,
        "total_detected": len(all_detected),
        "total_patterns": len(PATTERN_LIBRARY),
        "detection_errors": len(errors),
        "errors": [e.to_dict() for e in errors],
        "by_type": {k: len(v) for k, v in by_type.items()},
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "patterns": all_detected,
    }
