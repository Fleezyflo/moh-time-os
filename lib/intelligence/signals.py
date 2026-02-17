"""
Signal detection framework for MOH TIME OS.

Defines detectable operational signals, their conditions, and severity.
Signals are the detection layer: they fire when conditions are met,
carry a severity, and imply a response.

This module contains DEFINITIONS ONLY. Detection logic is in signal_detector.py (Task 1.2).

Reference: data/signal_catalog_20260214.md
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SignalSeverity(Enum):
    """Signal severity levels."""

    CRITICAL = "critical"  # Needs action today
    WARNING = "warning"  # Needs attention this week
    WATCH = "watch"  # Worth tracking, no action yet


class SignalCategory(Enum):
    """Signal categories by detection type."""

    THRESHOLD = "threshold"  # Metric crossed a boundary
    TREND = "trend"  # Trajectory shifted direction
    ANOMALY = "anomaly"  # Deviation from pattern
    COMPOUND = "compound"  # Multiple conditions combined


@dataclass
class SignalDefinition:
    """
    Definition of a detectable signal.

    A signal represents a condition that warrants attention.
    When detected, it carries evidence and implies an action.
    """

    id: str  # e.g., "sig_client_comm_drop"
    name: str  # e.g., "Client Communication Drop"
    description: str  # What this signal means operationally
    category: SignalCategory
    entity_type: str  # "client", "project", "person", "portfolio"
    severity: SignalSeverity
    conditions: dict  # Structured conditions for detection
    implied_action: str  # What to consider doing
    evidence_template: str  # Template for describing evidence
    cooldown_hours: int = 24  # Don't re-fire within this window
    escalation_after_days: int = 0  # Escalate severity after N days (0 = no escalation)
    escalation_to: SignalSeverity | None = None  # Target severity for escalation
    fast_eval: bool = True  # Can be evaluated quickly (no per-entity queries)


@dataclass
class DetectedSignal:
    """
    A signal that has been detected for a specific entity.

    Created by the signal detector when conditions are met.
    """

    signal_id: str
    entity_type: str
    entity_id: str
    entity_name: str
    severity: SignalSeverity
    evidence: dict  # Actual values that triggered the signal
    evidence_text: str  # Human-readable evidence description
    implied_action: str
    detected_at: str  # ISO timestamp
    first_detected_at: str | None = None  # For tracking duration
    escalated: bool = False


# =============================================================================
# THRESHOLD SIGNALS - Metric crosses a boundary
# =============================================================================

SIG_CLIENT_COMM_DROP = SignalDefinition(
    id="sig_client_comm_drop",
    name="Client Communication Drop",
    description="Client communication volume dropped significantly below their historical average.",
    category=SignalCategory.THRESHOLD,
    entity_type="client",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "communications_count",
        "operator": "lt",
        "threshold_ratio": 0.5,  # Below 50% of baseline
        "baseline": "90d_average",
        "baseline_period_days": 90,
        "measurement_period_days": 30,
        "query_function": "client_metrics_in_period",
    },
    implied_action="Schedule a check-in call to understand if something has changed.",
    evidence_template="Communication volume in the last 30 days ({current}) is {pct_of_baseline}% of the 90-day average ({baseline}).",
    cooldown_hours=72,
    fast_eval=False,  # Requires 2 period queries per client
)

SIG_CLIENT_OVERDUE_TASKS = SignalDefinition(
    id="sig_client_overdue_tasks",
    name="Client Overdue Tasks",
    description="Client has multiple tasks overdue by more than a week.",
    category=SignalCategory.THRESHOLD,
    entity_type="client",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "overdue_tasks",
        "operator": "gt",
        "value": 5,
        "min_days_overdue": 7,
        "query_function": "client_task_summary",
    },
    implied_action="Review project status and identify blockers. Consider resource reallocation.",
    evidence_template="{overdue_count} tasks are overdue by more than 7 days.",
    cooldown_hours=48,
)

SIG_CLIENT_INVOICE_AGING = SignalDefinition(
    id="sig_client_invoice_aging",
    name="Client Invoice Aging",
    description="Client has an invoice outstanding past the acceptable threshold.",
    category=SignalCategory.THRESHOLD,
    entity_type="client",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "invoice_days_outstanding",
        "operator": "gt",
        "value": 45,
        "query_function": "client_portfolio_overview",
    },
    implied_action="Finance team follow-up. Review payment terms and relationship status.",
    evidence_template="Invoice outstanding for {days} days (threshold: 45 days).",
    cooldown_hours=72,
    escalation_after_days=15,
    escalation_to=SignalSeverity.CRITICAL,
)

SIG_CLIENT_SCORE_CRITICAL = SignalDefinition(
    id="sig_client_score_critical",
    name="Client Score Critical",
    description="Client's composite health score has dropped into critical range.",
    category=SignalCategory.THRESHOLD,
    entity_type="client",
    severity=SignalSeverity.CRITICAL,
    conditions={
        "type": "threshold",
        "metric": "composite_score",
        "operator": "lt",
        "value": 30,
        "query_function": "score_client",
    },
    implied_action="Account review meeting. Understand root causes across all dimensions.",
    evidence_template="Client composite score is {score} (critical threshold: 30).",
    cooldown_hours=24,
    fast_eval=False,  # Requires running full scoring per client
)

SIG_PROJECT_STALLED = SignalDefinition(
    id="sig_project_stalled",
    name="Project Stalled",
    description="Project has open tasks but no completions in an extended period.",
    category=SignalCategory.THRESHOLD,
    entity_type="project",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "days_since_completion",
        "operator": "gt",
        "value": 14,
        "requires": "open_tasks > 0",
        "query_function": "project_operational_state",
    },
    implied_action="Investigate what's blocking progress. Check for dependencies or resource issues.",
    evidence_template="No task completions in {days} days despite {open_tasks} open tasks.",
    cooldown_hours=72,
)

SIG_PROJECT_OVERLOADED = SignalDefinition(
    id="sig_project_overloaded",
    name="Project Overloaded",
    description="Project has more active tasks than its team can reasonably handle.",
    category=SignalCategory.THRESHOLD,
    entity_type="project",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "tasks_per_person",
        "operator": "gt",
        "value": 15,  # More than 15 tasks per assigned person
        "query_function": "project_operational_state",
    },
    implied_action="Review capacity allocation. Consider adding resources or reducing scope.",
    evidence_template="{tasks_per_person} active tasks per person (threshold: 15).",
    cooldown_hours=48,
)

SIG_PERSON_OVERLOADED = SignalDefinition(
    id="sig_person_overloaded",
    name="Person Overloaded",
    description="Person is assigned more tasks than sustainable across all projects.",
    category=SignalCategory.THRESHOLD,
    entity_type="person",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "active_tasks",
        "operator": "gt",
        "value": 25,
        "query_function": "person_operational_profile",
    },
    implied_action="Redistribute workload. Check if tasks can be delegated or deprioritized.",
    evidence_template="{active_tasks} active tasks assigned (threshold: 25).",
    cooldown_hours=48,
)

SIG_PERSON_CONCENTRATION = SignalDefinition(
    id="sig_person_concentration",
    name="Person Concentration Risk",
    description="Person is sole assignee on multiple active projects (single point of failure).",
    category=SignalCategory.THRESHOLD,
    entity_type="person",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "sole_assignee_projects",
        "operator": "gt",
        "value": 3,
        "query_function": "person_operational_profile",
    },
    implied_action="Cross-train or assign backup. Reduce bus-factor risk.",
    evidence_template="Sole assignee on {count} projects (threshold: 3).",
    cooldown_hours=168,  # Weekly
)

SIG_PORTFOLIO_REVENUE_CONCENTRATION = SignalDefinition(
    id="sig_portfolio_revenue_concentration",
    name="Portfolio Revenue Concentration",
    description="Revenue is overly concentrated in a small number of clients.",
    category=SignalCategory.THRESHOLD,
    entity_type="portfolio",
    severity=SignalSeverity.WATCH,
    conditions={
        "type": "threshold",
        "metric": "top_n_client_share",
        "n": 3,
        "operator": "gt",
        "value": 0.40,  # Top 3 clients > 40%
        "query_function": "client_portfolio_overview",
    },
    implied_action="Diversification strategy. Focus business development on new clients.",
    evidence_template="Top 3 clients represent {pct}% of revenue (threshold: 40%).",
    cooldown_hours=168,
)

SIG_PORTFOLIO_CAPACITY_CEILING = SignalDefinition(
    id="sig_portfolio_capacity_ceiling",
    name="Portfolio Capacity Ceiling",
    description="Team is operating near or at capacity across the board.",
    category=SignalCategory.THRESHOLD,
    entity_type="portfolio",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "threshold",
        "metric": "avg_load_score",
        "operator": "gt",
        "value": 80,
        "query_function": "team_capacity_overview",
    },
    implied_action="Consider hiring or reducing scope. Avoid taking on new work.",
    evidence_template="Average team load score is {score} (threshold: 80).",
    cooldown_hours=72,
)


# =============================================================================
# TREND SIGNALS - Trajectory shifted direction
# =============================================================================

SIG_CLIENT_DECLINING = SignalDefinition(
    id="sig_client_declining",
    name="Client Health Declining",
    description="Client's composite score has been decreasing for multiple consecutive periods.",
    category=SignalCategory.TREND,
    entity_type="client",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "trend",
        "metric": "composite_score",
        "direction": "declining",
        "consecutive_periods": 3,
        "period_size_days": 30,
        "query_function": "client_trajectory",
    },
    implied_action="Proactive outreach. Identify what's driving the decline before it becomes critical.",
    evidence_template="Composite score declining for {periods} consecutive months: {trend_values}.",
    cooldown_hours=168,
)

SIG_CLIENT_ENGAGEMENT_FADING = SignalDefinition(
    id="sig_client_engagement_fading",
    name="Client Engagement Fading",
    description="Client communication and meeting frequency both declining.",
    category=SignalCategory.TREND,
    entity_type="client",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "trend",
        "metrics": ["communications_count", "meetings_count"],
        "direction": "declining",
        "consecutive_periods": 2,
        "period_size_days": 30,
        "all_must_decline": True,
        "query_function": "client_trajectory",
    },
    implied_action="Relationship at risk. Schedule strategic check-in at appropriate level.",
    evidence_template="Both communication and meeting frequency declining for {periods} months.",
    cooldown_hours=168,
)

SIG_PERSON_OUTPUT_DECLINING = SignalDefinition(
    id="sig_person_output_declining",
    name="Person Output Declining",
    description="Person's task completion rate has been declining.",
    category=SignalCategory.TREND,
    entity_type="person",
    severity=SignalSeverity.WATCH,
    conditions={
        "type": "trend",
        "metric": "completion_rate",
        "direction": "declining",
        "consecutive_periods": 3,
        "period_size_days": 30,
        "query_function": "person_trajectory",
    },
    implied_action="Check-in conversation. Understand if workload, engagement, or blockers are the cause.",
    evidence_template="Task completion rate declining for {periods} consecutive months.",
    cooldown_hours=168,
)

SIG_PORTFOLIO_QUALITY_DECLINING = SignalDefinition(
    id="sig_portfolio_quality_declining",
    name="Portfolio Quality Declining",
    description="Portfolio-wide quality indicators are trending down.",
    category=SignalCategory.TREND,
    entity_type="portfolio",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "trend",
        "metric": "avg_completion_rate",
        "direction": "declining",
        "consecutive_periods": 3,
        "period_size_days": 30,
        "query_function": "portfolio_trajectory",
    },
    implied_action="Systemic quality review. Check for process issues, resource constraints, or scope creep.",
    evidence_template="Portfolio completion rate declining for {periods} consecutive months.",
    cooldown_hours=168,
)


# =============================================================================
# ANOMALY SIGNALS - Deviation from pattern
# =============================================================================

SIG_CLIENT_COMM_ANOMALY = SignalDefinition(
    id="sig_client_comm_anomaly",
    name="Client Communication Anomaly",
    description="Client communication volume significantly deviates from their established pattern.",
    category=SignalCategory.ANOMALY,
    entity_type="client",
    severity=SignalSeverity.WATCH,
    conditions={
        "type": "anomaly",
        "metric": "communications_count",
        "deviation_threshold": 2.0,  # Standard deviations
        "baseline_period_days": 180,
        "measurement_period_days": 30,
        "direction": "any",  # Both high and low are interesting
        "query_function": "client_trajectory",
    },
    implied_action="Investigate what changed. High volume might mean issues; low volume might mean disengagement.",
    evidence_template="Communication volume is {deviation}σ from 6-month mean (current: {current}, mean: {mean}).",
    cooldown_hours=72,
)

SIG_PERSON_REVISION_ANOMALY = SignalDefinition(
    id="sig_person_revision_anomaly",
    name="Person Revision Anomaly",
    description="Person's work revision rate is abnormally high compared to their history.",
    category=SignalCategory.ANOMALY,
    entity_type="person",
    severity=SignalSeverity.WATCH,
    conditions={
        "type": "anomaly",
        "metric": "revision_rate",
        "deviation_threshold": 2.0,
        "baseline_period_days": 180,
        "measurement_period_days": 30,
        "direction": "high",  # Only high revision rates are concerning
        "query_function": "person_trajectory",
    },
    implied_action="Possible quality or scope issue. Review recent work and feedback patterns.",
    evidence_template="Revision rate is {deviation}σ above historical mean.",
    cooldown_hours=72,
)

SIG_PROJECT_CYCLE_ANOMALY = SignalDefinition(
    id="sig_project_cycle_anomaly",
    name="Project Cycle Time Anomaly",
    description="Project's task cycle time is abnormally long compared to its history.",
    category=SignalCategory.ANOMALY,
    entity_type="project",
    severity=SignalSeverity.WATCH,
    conditions={
        "type": "anomaly",
        "metric": "avg_cycle_time",
        "deviation_threshold": 2.0,
        "baseline_period_days": 90,
        "measurement_period_days": 30,
        "direction": "high",
        "query_function": "project_operational_state",
    },
    implied_action="Process bottleneck investigation. Check for blockers, dependencies, or resource constraints.",
    evidence_template="Average cycle time is {deviation}σ above project historical mean.",
    cooldown_hours=72,
)


# =============================================================================
# COMPOUND SIGNALS - Multiple conditions combined
# =============================================================================

SIG_CLIENT_CHURN_RISK = SignalDefinition(
    id="sig_client_churn_risk",
    name="Client Churn Risk",
    description="Multiple warning signs indicate client may be at risk of leaving.",
    category=SignalCategory.COMPOUND,
    entity_type="client",
    severity=SignalSeverity.CRITICAL,
    conditions={
        "type": "compound",
        "operator": "all",  # All conditions must be true
        "conditions": [
            {"signal_ref": "sig_client_comm_drop"},
            {"signal_ref": "sig_client_invoice_aging"},
            {"signal_ref": "sig_client_overdue_tasks"},
        ],
    },
    implied_action="Executive-level outreach immediately. This client may be leaving.",
    evidence_template="Multiple warning signs: communication drop + aging invoice + overdue tasks.",
    cooldown_hours=24,
)

SIG_PERSON_BURNOUT_RISK = SignalDefinition(
    id="sig_person_burnout_risk",
    name="Person Burnout Risk",
    description="Multiple indicators suggest person may be at risk of burnout.",
    category=SignalCategory.COMPOUND,
    entity_type="person",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "compound",
        "operator": "all",
        "conditions": [
            {"signal_ref": "sig_person_overloaded"},
            {"signal_ref": "sig_person_output_declining"},
        ],
    },
    implied_action="Workload intervention needed. Have a conversation about sustainability.",
    evidence_template="Overloaded + declining output indicates potential burnout risk.",
    cooldown_hours=168,
)

SIG_PROJECT_CASCADE_RISK = SignalDefinition(
    id="sig_project_cascade_risk",
    name="Project Cascade Risk",
    description="Stalled project combined with overloaded primary resource.",
    category=SignalCategory.COMPOUND,
    entity_type="project",
    severity=SignalSeverity.WARNING,
    conditions={
        "type": "compound",
        "operator": "all",
        "conditions": [
            {"signal_ref": "sig_project_stalled"},
            {
                "type": "threshold",
                "metric": "primary_assignee_load",
                "operator": "gt",
                "value": 25,
            },
        ],
    },
    implied_action="Resource conflict needs resolution. The person blocking this is overloaded elsewhere.",
    evidence_template="Project stalled and primary assignee is overloaded ({tasks} tasks).",
    cooldown_hours=48,
)

SIG_CLIENT_HIDDEN_COST = SignalDefinition(
    id="sig_client_hidden_cost",
    name="Client Hidden Cost",
    description="Client appears profitable but has high operational cost indicators.",
    category=SignalCategory.COMPOUND,
    entity_type="client",
    severity=SignalSeverity.WATCH,
    conditions={
        "type": "compound",
        "operator": "all",
        "conditions": [
            {
                "type": "threshold",
                "metric": "financial_health_score",
                "operator": "gt",
                "value": 60,  # Financially healthy
            },
            {
                "type": "threshold",
                "metric": "operational_health_score",
                "operator": "lt",
                "value": 40,  # Operationally costly
            },
        ],
    },
    implied_action="Pricing review. This client may be unprofitable despite revenue.",
    evidence_template="Financial health score {fin_score} but operational health score only {ops_score}.",
    cooldown_hours=168,
)


# =============================================================================
# SIGNAL CATALOG
# =============================================================================

SIGNAL_CATALOG: dict[str, SignalDefinition] = {
    # Threshold signals
    "sig_client_comm_drop": SIG_CLIENT_COMM_DROP,
    "sig_client_overdue_tasks": SIG_CLIENT_OVERDUE_TASKS,
    "sig_client_invoice_aging": SIG_CLIENT_INVOICE_AGING,
    "sig_client_score_critical": SIG_CLIENT_SCORE_CRITICAL,
    "sig_project_stalled": SIG_PROJECT_STALLED,
    "sig_project_overloaded": SIG_PROJECT_OVERLOADED,
    "sig_person_overloaded": SIG_PERSON_OVERLOADED,
    "sig_person_concentration": SIG_PERSON_CONCENTRATION,
    "sig_portfolio_revenue_concentration": SIG_PORTFOLIO_REVENUE_CONCENTRATION,
    "sig_portfolio_capacity_ceiling": SIG_PORTFOLIO_CAPACITY_CEILING,
    # Trend signals
    "sig_client_declining": SIG_CLIENT_DECLINING,
    "sig_client_engagement_fading": SIG_CLIENT_ENGAGEMENT_FADING,
    "sig_person_output_declining": SIG_PERSON_OUTPUT_DECLINING,
    "sig_portfolio_quality_declining": SIG_PORTFOLIO_QUALITY_DECLINING,
    # Anomaly signals
    "sig_client_comm_anomaly": SIG_CLIENT_COMM_ANOMALY,
    "sig_person_revision_anomaly": SIG_PERSON_REVISION_ANOMALY,
    "sig_project_cycle_anomaly": SIG_PROJECT_CYCLE_ANOMALY,
    # Compound signals
    "sig_client_churn_risk": SIG_CLIENT_CHURN_RISK,
    "sig_person_burnout_risk": SIG_PERSON_BURNOUT_RISK,
    "sig_project_cascade_risk": SIG_PROJECT_CASCADE_RISK,
    "sig_client_hidden_cost": SIG_CLIENT_HIDDEN_COST,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_signal(signal_id: str) -> SignalDefinition | None:
    """Get a signal definition by ID."""
    return SIGNAL_CATALOG.get(signal_id)


def get_signals_by_entity_type(entity_type: str) -> list[SignalDefinition]:
    """Get all signals that apply to an entity type."""
    return [s for s in SIGNAL_CATALOG.values() if s.entity_type == entity_type]


def get_signals_by_category(category: SignalCategory) -> list[SignalDefinition]:
    """Get all signals in a category."""
    return [s for s in SIGNAL_CATALOG.values() if s.category == category]


def get_signals_by_severity(severity: SignalSeverity) -> list[SignalDefinition]:
    """Get all signals at a severity level."""
    return [s for s in SIGNAL_CATALOG.values() if s.severity == severity]


def validate_signal_catalog() -> list[str]:
    """
    Validate signal catalog integrity.

    Checks:
    - All compound signals reference existing signals
    - All signals have required fields

    Returns list of error messages (empty if valid).
    """
    errors = []

    for sig_id, signal in SIGNAL_CATALOG.items():
        # Check required fields
        if not signal.id:
            errors.append(f"{sig_id}: missing id")
        if not signal.conditions:
            errors.append(f"{sig_id}: missing conditions")
        if not signal.implied_action:
            errors.append(f"{sig_id}: missing implied_action")

        # Check compound signal references
        if signal.category == SignalCategory.COMPOUND:
            for cond in signal.conditions.get("conditions", []):
                ref = cond.get("signal_ref")
                if ref and ref not in SIGNAL_CATALOG:
                    errors.append(f"{sig_id}: references unknown signal '{ref}'")

        # Check escalation target
        if signal.escalation_to and signal.escalation_after_days == 0:
            errors.append(f"{sig_id}: has escalation_to but no escalation_after_days")

    return errors


# Run validation on import
_validation_errors = validate_signal_catalog()
if _validation_errors:
    import warnings

    warnings.warn(f"Signal catalog validation errors: {_validation_errors}", stacklevel=2)


# =============================================================================
# THRESHOLD CONFIGURATION - Load from thresholds.yaml
# =============================================================================

from pathlib import Path as _ThresholdPath

import yaml

THRESHOLDS_PATH = _ThresholdPath(__file__).parent / "thresholds.yaml"


def load_thresholds() -> dict:
    """Load threshold configuration from YAML file."""
    if not THRESHOLDS_PATH.exists():
        return {}

    try:
        with open(THRESHOLDS_PATH) as f:
            config = yaml.safe_load(f)
        return config.get("signals", {})
    except Exception as e:
        import warnings

        warnings.warn(f"Failed to load thresholds.yaml: {e}", stacklevel=2)
        return {}


def apply_thresholds(thresholds: dict = None):
    """
    Apply threshold config to signal definitions.

    This patches the conditions dict in each SignalDefinition
    with values from the config file.
    """
    if thresholds is None:
        thresholds = load_thresholds()

    if not thresholds:
        return

    for sig_id, config in thresholds.items():
        if sig_id not in SIGNAL_CATALOG:
            continue

        signal_def = SIGNAL_CATALOG[sig_id]
        conditions = signal_def.conditions

        # Apply threshold values
        if "value" in config:
            conditions["value"] = config["value"]
        if "threshold_ratio" in config:
            conditions["threshold_ratio"] = config["threshold_ratio"]
        if "operator" in config:
            conditions["operator"] = config["operator"]
        if "n" in config:
            conditions["n"] = config["n"]


def get_threshold(signal_id: str, key: str = "value"):
    """Get a specific threshold value for a signal."""
    thresholds = load_thresholds()
    if signal_id in thresholds:
        return thresholds[signal_id].get(key)
    return None


def export_signals_for_review(output_path: str = None, quick: bool = True) -> str:
    """
    Export current signal detections for threshold tuning review.

    Returns CSV data with signal detections and their evidence,
    useful for reviewing which signals are noise vs real issues.

    Args:
        output_path: Optional file path to write CSV
        quick: If True, use fast signal detection (default)
    """
    import csv
    import io
    from datetime import datetime

    # Detect signals
    result = detect_all_signals(quick=quick)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "signal_id",
            "signal_name",
            "severity",
            "entity_type",
            "entity_id",
            "entity_name",
            "metric",
            "current_value",
            "threshold_value",
            "detected_at",
            "notes",
        ]
    )

    # Data rows
    for sig in result["signals"]:
        evidence = sig.get("evidence", {})
        writer.writerow(
            [
                sig.get("signal_id"),
                sig.get("signal_name"),
                sig.get("severity"),
                sig.get("entity_type"),
                sig.get("entity_id"),
                sig.get("entity_name"),
                evidence.get("metric"),
                evidence.get("current_value"),
                evidence.get("threshold_value"),
                sig.get("detected_at"),
                "",  # Notes column for manual review
            ]
        )

    csv_data = output.getvalue()

    if output_path:
        with open(output_path, "w") as f:
            f.write(csv_data)

    return csv_data


def reload_thresholds():
    """Reload thresholds from config file (call after editing thresholds.yaml)."""
    apply_thresholds()


# Apply thresholds from config on module load
apply_thresholds()


# =============================================================================
# SIGNAL DETECTION - Condition Evaluators
# =============================================================================

import logging
import statistics
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_engine(db_path: Path | None = None):
    """Get query engine instance."""
    from lib.query_engine import QueryEngine

    return QueryEngine(db_path) if db_path else QueryEngine()


# =============================================================================
# DETECTION CACHE - Avoid repeated queries during a single detection run
# =============================================================================


class DetectionCache:
    """
    Cache for pre-loaded data during signal detection.

    Avoids O(n²) behavior by loading data once and indexing for O(1) lookup.
    Create one instance per detect_all_signals() call.
    """

    def __init__(self, db_path: Path | None = None):
        self.engine = _get_engine(db_path)
        self.db_path = db_path
        self._clients = None
        self._clients_by_id = None
        self._projects = None
        self._projects_by_id = None
        self._persons = None
        self._persons_by_id = None
        self._task_summaries = {}
        self._metrics_cache = {}
        self._overdue_counts = None  # Batch-loaded overdue task counts

    @property
    def clients(self) -> list:
        if self._clients is None:
            self._clients = self.engine.client_portfolio_overview()
            self._clients_by_id = {c.get("client_id"): c for c in self._clients}
        return self._clients

    def get_client(self, client_id: str) -> dict | None:
        _ = self.clients  # Ensure loaded
        return self._clients_by_id.get(client_id)

    @property
    def projects(self) -> list:
        if self._projects is None:
            self._projects = self.engine.projects_by_health(min_tasks=1)
            self._projects_by_id = {p.get("project_id"): p for p in self._projects}
        return self._projects

    def get_project(self, project_id: str) -> dict | None:
        _ = self.projects  # Ensure loaded
        return self._projects_by_id.get(project_id)

    @property
    def persons(self) -> list:
        if self._persons is None:
            self._persons = self.engine.resource_load_distribution()
            self._persons_by_id = {p.get("person_id"): p for p in self._persons}
        return self._persons

    def get_person(self, person_id: str) -> dict | None:
        _ = self.persons  # Ensure loaded
        return self._persons_by_id.get(person_id)

    def get_task_summary(self, client_id: str) -> dict:
        if client_id not in self._task_summaries:
            self._task_summaries[client_id] = self.engine.client_task_summary(client_id)
        return self._task_summaries[client_id]

    def get_overdue_count(self, client_id: str) -> int:
        """Get overdue task count for a client (batch loaded on first access)."""
        if self._overdue_counts is None:
            self._load_overdue_counts()
        return self._overdue_counts.get(client_id, 0)

    def _load_overdue_counts(self):
        """Batch load overdue task counts for all clients in one query."""
        import sqlite3

        from lib import paths

        db = self.db_path or paths.db_path()
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT client_id, COUNT(*) as overdue_count
            FROM v_task_with_client
            WHERE due_date < date('now')
              AND task_status NOT IN ('done', 'complete', 'completed')
              AND client_id IS NOT NULL
            GROUP BY client_id
        """)

        self._overdue_counts = {row["client_id"]: row["overdue_count"] for row in cursor.fetchall()}
        conn.close()

    def get_client_metrics(self, client_id: str, since: str, until: str) -> dict:
        key = f"{client_id}:{since}:{until}"
        if key not in self._metrics_cache:
            self._metrics_cache[key] = self.engine.client_metrics_in_period(client_id, since, until)
        return self._metrics_cache[key]


def _evaluate_threshold(
    condition: dict,
    entity_type: str,
    entity_id: str,
    db_path: Path | None = None,
    cache: DetectionCache = None,
) -> dict | None:
    """
    Evaluate a threshold condition.

    Returns evidence dict if triggered, None if not.

    If cache is provided, uses cached data for O(1) lookups.
    Otherwise falls back to direct queries (slower).
    """
    # Use cache if available, otherwise create engine for fallback
    if cache is None:
        cache = DetectionCache(db_path)

    metric = condition.get("metric")
    operator = condition.get("operator", "gt")
    threshold = condition.get("value")
    threshold_ratio = condition.get("threshold_ratio")

    # Get current value based on entity type and query function
    current_value = None
    baseline_value = None

    try:
        if entity_type == "client":
            # Get client data from cache (O(1) lookup)
            client = cache.get_client(entity_id)

            if not client:
                return None

            if metric == "communications_count":
                # Need period comparison for communication
                since_30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                since_90 = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                until = datetime.now().strftime("%Y-%m-%d")

                recent = cache.get_client_metrics(entity_id, since_30, until)
                baseline_period = cache.get_client_metrics(entity_id, since_90, since_30)

                current_value = recent.get("communications_count", 0)
                # Normalize baseline to 30-day equivalent
                baseline_value = baseline_period.get("communications_count", 0) / 2

            elif metric == "overdue_tasks":
                # Use batch-loaded overdue counts (single query for all clients)
                current_value = cache.get_overdue_count(entity_id)

            elif metric == "composite_score":
                from lib.intelligence.scorecard import score_client

                scorecard = score_client(entity_id, cache.db_path)
                current_value = scorecard.get("composite_score")

            elif metric in client:
                current_value = client.get(metric, 0)

        elif entity_type == "project":
            project = cache.get_project(entity_id)
            if not project:
                # Fallback for projects not in health list
                project = cache.engine.project_operational_state(entity_id)
            if not project:
                return None

            if metric == "tasks_per_person":
                open_tasks = project.get("open_tasks", 0)
                people = project.get("assigned_people_count", 1) or 1
                current_value = open_tasks / people
            else:
                current_value = project.get(metric, 0)

        elif entity_type == "person":
            person = cache.get_person(entity_id)
            if not person:
                person = cache.engine.person_operational_profile(entity_id)
            if not person:
                return None
            current_value = person.get(metric, 0)

        elif entity_type == "portfolio":
            if metric == "top_n_client_share":
                portfolio = cache.clients  # Use cached clients
                total = sum(c.get("total_invoiced", 0) for c in portfolio)
                if total > 0:
                    sorted_clients = sorted(
                        portfolio, key=lambda x: x.get("total_invoiced", 0), reverse=True
                    )
                    n = condition.get("n", 3)
                    top_n_sum = sum(c.get("total_invoiced", 0) for c in sorted_clients[:n])
                    current_value = top_n_sum / total
                else:
                    current_value = 0

            elif metric == "avg_load_score":
                capacity = cache.engine.team_capacity_overview()
                # Compute average load from distribution
                dist = capacity.get("distribution", [])
                if dist:
                    scores = [p.get("load_score", 0) for p in dist]
                    current_value = sum(scores) / len(scores) if scores else 0
                else:
                    current_value = 0

    except Exception as e:
        logger.debug(f"Error evaluating threshold for {entity_type}/{entity_id}: {e}")
        return None

    if current_value is None:
        return None

    # Determine threshold to compare against
    if threshold_ratio is not None and baseline_value is not None:
        effective_threshold = baseline_value * threshold_ratio
    else:
        effective_threshold = threshold

    if effective_threshold is None:
        return None

    # Evaluate condition
    triggered = False
    if operator == "lt":
        triggered = current_value < effective_threshold
    elif operator == "lte":
        triggered = current_value <= effective_threshold
    elif operator == "gt":
        triggered = current_value > effective_threshold
    elif operator == "gte":
        triggered = current_value >= effective_threshold
    elif operator == "eq":
        triggered = current_value == effective_threshold

    if not triggered:
        return None

    return {
        "metric": metric,
        "current_value": current_value,
        "threshold_value": effective_threshold,
        "baseline_value": baseline_value,
        "operator": operator,
        "triggered": True,
    }


def _evaluate_trend(
    condition: dict, entity_type: str, entity_id: str, db_path: Path | None = None
) -> dict | None:
    """
    Evaluate a trend condition using trajectory functions.

    Returns evidence dict if triggered, None if not.
    """
    engine = _get_engine(db_path)
    metric = condition.get("metric")
    direction = condition.get("direction", "declining")
    consecutive = condition.get("consecutive_periods", 3)
    period_days = condition.get("period_size_days", 30)

    try:
        if entity_type == "client":
            trajectory = engine.client_trajectory(
                entity_id, window_size_days=period_days, num_windows=consecutive + 1
            )
        elif entity_type == "person":
            trajectory = engine.person_trajectory(
                entity_id, window_size_days=period_days, num_windows=consecutive + 1
            )
        elif entity_type == "portfolio":
            # Portfolio trajectory uses aggregate
            trajectories = engine.portfolio_trajectory(
                window_size_days=period_days, num_windows=consecutive + 1
            )
            if not trajectories:
                return None
            # Aggregate across all clients
            trajectory = {"trends": {}}
            # Use portfolio-level aggregation from team capacity trends
            # For now, skip portfolio trends (need custom implementation)
            return None
        else:
            return None

        trends = trajectory.get("trends", {})
        metric_trend = trends.get(metric, {})
        actual_direction = metric_trend.get("direction", "stable")
        magnitude = metric_trend.get("magnitude_pct", 0)
        confidence = metric_trend.get("confidence", "low")

    except Exception as e:
        logger.debug(f"Error evaluating trend for {entity_type}/{entity_id}: {e}")
        return None

    # Check if trend matches expected direction
    if actual_direction != direction:
        return None

    # Check confidence
    if confidence == "low":
        return None  # Don't fire on low confidence trends

    return {
        "metric": metric,
        "direction": actual_direction,
        "magnitude_pct": magnitude,
        "confidence": confidence,
        "consecutive_periods": consecutive,
        "triggered": True,
    }


def _evaluate_anomaly(
    condition: dict, entity_type: str, entity_id: str, db_path: Path | None = None
) -> dict | None:
    """
    Evaluate an anomaly condition.

    Returns evidence dict if triggered, None if not.
    """
    engine = _get_engine(db_path)
    metric = condition.get("metric")
    deviation_threshold = condition.get("deviation_threshold", 2.0)
    baseline_days = condition.get("baseline_period_days", 180)
    measurement_days = condition.get("measurement_period_days", 30)
    direction = condition.get("direction", "any")

    try:
        # Get historical values for baseline
        now = datetime.now()
        (now - timedelta(days=baseline_days)).strftime("%Y-%m-%d")
        (now - timedelta(days=measurement_days)).strftime("%Y-%m-%d")
        now.strftime("%Y-%m-%d")

        if entity_type == "client":
            # Get multiple periods to compute stddev
            trajectory = engine.client_trajectory(
                entity_id, window_size_days=30, num_windows=baseline_days // 30
            )
            windows = trajectory.get("windows", [])

            if len(windows) < 3:
                return None  # Not enough data

            values = [
                w.get("metrics", {}).get(metric, 0) for w in windows[:-1]
            ]  # Exclude most recent
            current = windows[-1].get("metrics", {}).get(metric, 0) if windows else 0

        else:
            # Other entity types - need similar trajectory support
            return None

        if not values or len(values) < 2:
            return None

        mean = statistics.mean(values)
        stddev = statistics.stdev(values) if len(values) > 1 else 0

        if stddev == 0:
            return None  # Can't compute deviation with no variance

        deviation = (current - mean) / stddev

    except Exception as e:
        logger.debug(f"Error evaluating anomaly for {entity_type}/{entity_id}: {e}")
        return None

    # Check if deviation exceeds threshold
    if direction == "high" and deviation < deviation_threshold:
        return None
    if direction == "low" and deviation > -deviation_threshold:
        return None
    if direction == "any" and abs(deviation) < deviation_threshold:
        return None

    return {
        "metric": metric,
        "current_value": current,
        "mean": round(mean, 2),
        "stddev": round(stddev, 2),
        "deviation": round(deviation, 2),
        "threshold": deviation_threshold,
        "direction": direction,
        "triggered": True,
    }


def _evaluate_compound(
    condition: dict,
    entity_type: str,
    entity_id: str,
    db_path: Path | None = None,
    _evaluated: dict | None = None,
) -> dict | None:
    """
    Evaluate a compound condition by checking sub-conditions.

    Returns evidence dict if triggered, None if not.
    """
    operator = condition.get("operator", "all")
    sub_conditions = condition.get("conditions", [])

    if not sub_conditions:
        return None

    _evaluated = _evaluated or {}
    results = []

    for sub in sub_conditions:
        if "signal_ref" in sub:
            # Reference to another signal
            ref_id = sub["signal_ref"]
            ref_signal = get_signal(ref_id)

            if not ref_signal:
                results.append({"ref": ref_id, "triggered": False, "error": "unknown signal"})
                continue

            # Evaluate the referenced signal
            ref_result = evaluate_signal(ref_signal, entity_type, entity_id, db_path, _evaluated)
            results.append(
                {
                    "ref": ref_id,
                    "triggered": ref_result is not None,
                }
            )

        elif "type" in sub:
            # Inline condition
            sub_type = sub["type"]
            if sub_type == "threshold":
                sub_result = _evaluate_threshold(sub, entity_type, entity_id, db_path)
            else:
                sub_result = None

            results.append(
                {
                    "condition": sub,
                    "triggered": sub_result is not None,
                }
            )

    # Evaluate compound logic
    triggered_count = sum(1 for r in results if r.get("triggered"))

    if operator == "all":
        triggered = triggered_count == len(results)
    elif operator == "any":
        triggered = triggered_count > 0
    else:
        triggered = False

    if not triggered:
        return None

    return {
        "operator": operator,
        "sub_results": results,
        "triggered_count": triggered_count,
        "total_conditions": len(results),
        "triggered": True,
    }


# =============================================================================
# SIGNAL DETECTION - Main Functions
# =============================================================================


def evaluate_signal(
    signal_def: SignalDefinition,
    entity_type: str,
    entity_id: str,
    db_path: Path | None = None,
    _evaluated: dict | None = None,
    cache: DetectionCache = None,
) -> dict | None:
    """
    Evaluate a single signal definition for a specific entity.

    Returns None if not triggered, or a detected signal dict.

    Args:
        cache: Optional DetectionCache for fast lookups (avoids O(n²) behavior)
    """
    # Check entity type matches
    if signal_def.entity_type != entity_type:
        return None

    # Track evaluated signals to avoid cycles in compound signals
    _evaluated = _evaluated or {}
    cache_key = f"{signal_def.id}:{entity_id}"

    if cache_key in _evaluated:
        return _evaluated[cache_key]

    # Mark as being evaluated (None means in progress)
    _evaluated[cache_key] = None

    condition = signal_def.conditions
    evidence = None

    try:
        if signal_def.category == SignalCategory.THRESHOLD:
            evidence = _evaluate_threshold(condition, entity_type, entity_id, db_path, cache)
        elif signal_def.category == SignalCategory.TREND:
            evidence = _evaluate_trend(condition, entity_type, entity_id, db_path)
        elif signal_def.category == SignalCategory.ANOMALY:
            evidence = _evaluate_anomaly(condition, entity_type, entity_id, db_path)
        elif signal_def.category == SignalCategory.COMPOUND:
            evidence = _evaluate_compound(condition, entity_type, entity_id, db_path, _evaluated)
    except Exception as e:
        logger.warning(f"Error evaluating signal {signal_def.id}: {e}")
        evidence = None

    if evidence is None:
        _evaluated[cache_key] = None
        return None

    # Build detected signal
    result = {
        "signal_id": signal_def.id,
        "signal_name": signal_def.name,
        "severity": signal_def.severity.value,
        "category": signal_def.category.value,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "evidence": evidence,
        "evidence_text": _format_evidence(signal_def, evidence),
        "implied_action": signal_def.implied_action,
        "detected_at": datetime.now().isoformat(),
    }

    _evaluated[cache_key] = result
    return result


def _format_evidence(signal_def: SignalDefinition, evidence: dict) -> str:
    """Format evidence into human-readable text using the template."""
    template = signal_def.evidence_template

    try:
        # Build substitution dict from evidence
        subs = {}
        for key, value in evidence.items():
            if isinstance(value, float):
                subs[key] = f"{value:.1f}"
            else:
                subs[key] = str(value)

        # Add computed fields
        if "current_value" in evidence and "baseline_value" in evidence:
            baseline = evidence["baseline_value"]
            if baseline and baseline > 0:
                pct = (evidence["current_value"] / baseline) * 100
                subs["pct_of_baseline"] = f"{pct:.0f}"

        return template.format(**subs)
    except Exception:
        return str(evidence)


def detect_signals_for_entity(
    entity_type: str,
    entity_id: str,
    db_path: Path | None = None,
    categories: list[SignalCategory] | None = None,
    cache: DetectionCache = None,
    fast_only: bool = False,
) -> list[dict]:
    """
    Run signals applicable to this entity type.

    Args:
        entity_type: Type of entity
        entity_id: Entity identifier
        db_path: Optional database path
        categories: Optional list of categories to evaluate (default: all)
                   For fast scanning, use [SignalCategory.THRESHOLD]
        cache: Optional DetectionCache for fast lookups
        fast_only: If True, skip signals that require per-entity queries

    Returns list of triggered signals, sorted by severity (CRITICAL first).
    """
    signals = get_signals_by_entity_type(entity_type)

    # Filter by categories if specified
    if categories is not None:
        signals = [s for s in signals if s.category in categories]

    # Filter by fast_eval if fast_only is True
    if fast_only:
        signals = [s for s in signals if s.fast_eval]

    detected = []
    _evaluated = {}

    for signal_def in signals:
        result = evaluate_signal(signal_def, entity_type, entity_id, db_path, _evaluated, cache)
        if result:
            detected.append(result)

    # Sort by severity (CRITICAL > WARNING > WATCH)
    severity_order = {"critical": 0, "warning": 1, "watch": 2}
    detected.sort(key=lambda x: severity_order.get(x.get("severity", "watch"), 3))

    return detected


def detect_all_client_signals(
    db_path: Path | None = None, categories: list[SignalCategory] | None = None
) -> list[dict]:
    """Run client signals against all clients."""
    # Use cache for efficient batch processing
    cache = DetectionCache(db_path)

    all_detected = []
    for client in cache.clients:
        client_id = client.get("client_id")
        if client_id:
            detected = detect_signals_for_entity("client", client_id, db_path, categories, cache)
            for d in detected:
                d["entity_name"] = client.get("client_name", "Unknown")
            all_detected.extend(detected)

    return all_detected


def detect_all_signals(
    db_path: Path | None = None, quick: bool = False, categories: list[SignalCategory] | None = None
) -> dict:
    """
    Run the signal catalog against the full database.

    Args:
        db_path: Optional database path
        quick: If True, only evaluate THRESHOLD signals (fast)
        categories: Optional list of categories to evaluate

    Returns comprehensive detection results.

    Performance: Uses DetectionCache to avoid O(n²) behavior.
    Data is loaded once and indexed for O(1) lookups.
    """
    # Create cache for this detection run - loads data once
    cache = DetectionCache(db_path)
    all_detected = []

    # Determine which categories to evaluate
    if categories is not None:
        cats = categories
    elif quick:
        cats = [SignalCategory.THRESHOLD]
    else:
        cats = None  # All categories

    # In quick mode, skip slow signals (fast_only=True)
    fast_only = quick

    # Clients - use cached data
    for client in cache.clients:
        client_id = client.get("client_id")
        if client_id:
            detected = detect_signals_for_entity(
                "client", client_id, db_path, cats, cache, fast_only
            )
            for d in detected:
                d["entity_name"] = client.get("client_name", "Unknown")
            all_detected.extend(detected)

    # Projects - use cached data
    for project in cache.projects:
        project_id = project.get("project_id")
        if project_id:
            detected = detect_signals_for_entity(
                "project", project_id, db_path, cats, cache, fast_only
            )
            for d in detected:
                d["entity_name"] = project.get("project_name", "Unknown")
            all_detected.extend(detected)

    # Persons - use cached data
    for person in cache.persons:
        person_id = person.get("person_id")
        if person_id:
            detected = detect_signals_for_entity(
                "person", person_id, db_path, cats, cache, fast_only
            )
            for d in detected:
                d["entity_name"] = person.get("person_name", "Unknown")
            all_detected.extend(detected)

    # Portfolio (single entity)
    portfolio_signals = get_signals_by_entity_type("portfolio")
    if cats is not None:
        portfolio_signals = [s for s in portfolio_signals if s.category in cats]
    if fast_only:
        portfolio_signals = [s for s in portfolio_signals if s.fast_eval]
    _evaluated = {}
    for signal_def in portfolio_signals:
        result = evaluate_signal(signal_def, "portfolio", "portfolio", db_path, _evaluated, cache)
        if result:
            result["entity_name"] = "Portfolio"
            all_detected.append(result)

    # Organize results
    by_severity = {"critical": [], "warning": [], "watch": []}
    by_entity_type = {"client": [], "project": [], "person": [], "portfolio": []}

    for signal in all_detected:
        sev = signal.get("severity", "watch")
        etype = signal.get("entity_type", "unknown")

        if sev in by_severity:
            by_severity[sev].append(signal)
        if etype in by_entity_type:
            by_entity_type[etype].append(signal)

    return {
        "detected_at": datetime.now().isoformat(),
        "total_signals": len(all_detected),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "by_entity_type": {k: len(v) for k, v in by_entity_type.items()},
        "signals": all_detected,
    }


# =============================================================================
# SIGNAL STATE TRACKING
# =============================================================================

import json
import sqlite3


def _get_db_path(db_path: Path | None = None) -> Path:
    """Get resolved database path."""
    if db_path:
        return Path(db_path)
    from lib.paths import db_path as get_default_db

    return get_default_db()


def _check_escalation(signal_record: dict, signal_def: SignalDefinition) -> str | None:
    """
    Check if a signal should escalate based on time active.

    Returns new severity string if should escalate, None if not.

    Escalation rules:
    - WATCH → WARNING after escalation_after_days
    - WARNING → CRITICAL after escalation_after_days × 2
    - CRITICAL does not escalate further
    """
    current_severity = signal_record.get("severity", "watch")
    first_detected = signal_record.get("first_detected_at")
    escalation_days = signal_def.escalation_after_days

    if not first_detected or not escalation_days:
        return None

    try:
        first_dt = datetime.fromisoformat(first_detected)
        days_active = (datetime.now() - first_dt).days
    except (ValueError, TypeError):
        return None

    # WATCH → WARNING after escalation_after_days
    if current_severity == "watch" and days_active >= escalation_days:
        return "warning"

    # WARNING → CRITICAL after escalation_after_days × 2
    if current_severity == "warning" and days_active >= (escalation_days * 2):
        return "critical"

    # CRITICAL doesn't escalate
    return None


def update_signal_state(detected_signals: list[dict], db_path: Path | None = None) -> dict:
    """
    Compare newly detected signals against persisted state. Update accordingly.

    For each detected signal:
    - If NOT in signal_state (or cleared): INSERT as new active signal
    - If already active: UPDATE last_evaluated_at, increment evaluation_count
    - If active for longer than escalation_after_days: escalate severity

    For signals in signal_state that are NOT in detected_signals:
    - If active and cooldown has passed: UPDATE status to 'cleared'
    - If within cooldown: leave as active

    Returns:
    {
        "new_signals": [...],
        "ongoing_signals": [...],
        "escalated_signals": [...],
        "cleared_signals": [...]
    }
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    now = datetime.now().isoformat()

    result = {
        "new_signals": [],
        "ongoing_signals": [],
        "escalated_signals": [],
        "cleared_signals": [],
    }

    try:
        # Build set of detected signal keys
        detected_keys = set()
        for sig in detected_signals:
            key = (sig["signal_id"], sig["entity_type"], sig["entity_id"])
            detected_keys.add(key)

        # Process each detected signal
        for sig in detected_signals:
            signal_id = sig["signal_id"]
            entity_type = sig["entity_type"]
            entity_id = sig["entity_id"]
            severity = sig["severity"]
            evidence_json = json.dumps(sig.get("evidence", {}))

            # Check if already active in state table
            existing = conn.execute(
                """SELECT * FROM signal_state
                   WHERE signal_id = ? AND entity_type = ? AND entity_id = ? AND status = 'active'""",
                (signal_id, entity_type, entity_id),
            ).fetchone()

            if existing:
                # Already active - update evaluation count and timestamp
                new_count = existing["evaluation_count"] + 1

                # Check for escalation
                signal_def = get_signal(signal_id)
                new_severity = None
                if signal_def:
                    new_severity = _check_escalation(dict(existing), signal_def)

                if new_severity:
                    # Escalate
                    conn.execute(
                        """UPDATE signal_state
                           SET last_evaluated_at = ?, evaluation_count = ?,
                               severity = ?, escalated_at = ?
                           WHERE id = ?""",
                        (now, new_count, new_severity, now, existing["id"]),
                    )
                    result["escalated_signals"].append(
                        {
                            "signal_id": signal_id,
                            "entity_type": entity_type,
                            "entity_id": entity_id,
                            "old_severity": severity,
                            "new_severity": new_severity,
                        }
                    )
                else:
                    # Ongoing, no escalation
                    conn.execute(
                        """UPDATE signal_state
                           SET last_evaluated_at = ?, evaluation_count = ?
                           WHERE id = ?""",
                        (now, new_count, existing["id"]),
                    )
                    result["ongoing_signals"].append(
                        {
                            "signal_id": signal_id,
                            "entity_type": entity_type,
                            "entity_id": entity_id,
                            "evaluation_count": new_count,
                        }
                    )
            else:
                # New signal - insert
                conn.execute(
                    """INSERT INTO signal_state
                       (signal_id, entity_type, entity_id, severity, original_severity,
                        status, evidence_json, first_detected_at, last_evaluated_at, evaluation_count)
                       VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, 1)""",
                    (
                        signal_id,
                        entity_type,
                        entity_id,
                        severity,
                        severity,
                        evidence_json,
                        now,
                        now,
                    ),
                )
                result["new_signals"].append(
                    {
                        "signal_id": signal_id,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "severity": severity,
                    }
                )

        # Check for signals that should be cleared (active but not detected)
        active_signals = conn.execute(
            "SELECT * FROM signal_state WHERE status = 'active'"
        ).fetchall()

        for record in active_signals:
            key = (record["signal_id"], record["entity_type"], record["entity_id"])
            if key not in detected_keys:
                # Signal not detected this time - check cooldown
                signal_def = get_signal(record["signal_id"])
                cooldown_hours = signal_def.cooldown_hours if signal_def else 24

                last_eval = record["last_evaluated_at"]
                try:
                    last_dt = datetime.fromisoformat(last_eval)
                    hours_since = (datetime.now() - last_dt).total_seconds() / 3600
                except (ValueError, TypeError):
                    hours_since = 0

                if hours_since >= cooldown_hours:
                    # Cooldown passed - clear the signal
                    conn.execute(
                        """UPDATE signal_state
                           SET status = 'cleared', cleared_at = ?
                           WHERE id = ?""",
                        (now, record["id"]),
                    )
                    result["cleared_signals"].append(
                        {
                            "signal_id": record["signal_id"],
                            "entity_type": record["entity_type"],
                            "entity_id": record["entity_id"],
                            "was_active_for_days": (
                                datetime.now() - datetime.fromisoformat(record["first_detected_at"])
                            ).days,
                        }
                    )

        conn.commit()
    finally:
        conn.close()

    return result


def get_active_signals(
    entity_type: str | None = None,
    entity_id: str | None = None,
    severity: str | None = None,
    db_path: Path | None = None,
) -> list[dict]:
    """
    Query persisted signal state. Filter by entity and/or severity.

    Returns list of active signal records with full state info.
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    try:
        query = "SELECT * FROM signal_state WHERE status = 'active'"
        params = []

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)

        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)

        if severity:
            query += " AND severity = ?"
            params.append(severity)

        query += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_signal_history(
    entity_type: str, entity_id: str, since: str | None = None, db_path: Path | None = None
) -> list[dict]:
    """
    Full signal history for an entity: all signals that ever fired, including cleared ones.

    Enables: 'What has happened with this client over the past 6 months?'
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    try:
        query = """SELECT * FROM signal_state
                   WHERE entity_type = ? AND entity_id = ?"""
        params = [entity_type, entity_id]

        if since:
            query += " AND first_detected_at >= ?"
            params.append(since)

        query += " ORDER BY first_detected_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def acknowledge_signal(signal_state_id: int, db_path: Path | None = None) -> bool:
    """
    Mark a signal as acknowledged (user has seen it and is aware).

    Acknowledged signals remain active but won't be surfaced as 'new'.
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    now = datetime.now().isoformat()

    try:
        cursor = conn.execute(
            """UPDATE signal_state
               SET status = 'acknowledged', acknowledged_at = ?
               WHERE id = ? AND status = 'active'""",
            (now, signal_state_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_signal_summary(db_path: Path | None = None) -> dict:
    """
    Dashboard-level summary of current signal state.

    Returns counts by severity, entity type, and recent changes.
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # Time windows
    now = datetime.now()
    last_24h = (now - timedelta(hours=24)).isoformat()
    last_7d = (now - timedelta(days=7)).isoformat()

    try:
        # Total active
        total_active = conn.execute(
            "SELECT COUNT(*) as cnt FROM signal_state WHERE status IN ('active', 'acknowledged')"
        ).fetchone()["cnt"]

        # By severity
        by_severity = {"critical": 0, "warning": 0, "watch": 0}
        rows = conn.execute(
            """SELECT severity, COUNT(*) as cnt FROM signal_state
               WHERE status IN ('active', 'acknowledged') GROUP BY severity"""
        ).fetchall()
        for row in rows:
            if row["severity"] in by_severity:
                by_severity[row["severity"]] = row["cnt"]

        # By entity type
        by_entity_type = {"client": 0, "project": 0, "person": 0, "portfolio": 0}
        rows = conn.execute(
            """SELECT entity_type, COUNT(*) as cnt FROM signal_state
               WHERE status IN ('active', 'acknowledged') GROUP BY entity_type"""
        ).fetchall()
        for row in rows:
            if row["entity_type"] in by_entity_type:
                by_entity_type[row["entity_type"]] = row["cnt"]

        # New since last 24h
        new_since_last_check = conn.execute(
            "SELECT COUNT(*) as cnt FROM signal_state WHERE first_detected_at >= ?", (last_24h,)
        ).fetchone()["cnt"]

        # Escalated in last 7 days
        escalated_recently = conn.execute(
            "SELECT COUNT(*) as cnt FROM signal_state WHERE escalated_at >= ?", (last_7d,)
        ).fetchone()["cnt"]

        # Cleared in last 7 days
        recently_cleared = conn.execute(
            "SELECT COUNT(*) as cnt FROM signal_state WHERE cleared_at >= ?", (last_7d,)
        ).fetchone()["cnt"]

        return {
            "total_active": total_active,
            "by_severity": by_severity,
            "by_entity_type": by_entity_type,
            "new_since_last_check": new_since_last_check,
            "escalated_recently": escalated_recently,
            "recently_cleared": recently_cleared,
        }
    finally:
        conn.close()


def clear_all_signal_state(db_path: Path | None = None) -> int:
    """
    Clear all signal state records. For testing/reset only.

    Returns number of rows deleted.
    """
    db = _get_db_path(db_path)
    conn = sqlite3.connect(db)

    try:
        cursor = conn.execute("DELETE FROM signal_state")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
