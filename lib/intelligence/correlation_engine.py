"""
Cross-domain pattern correlation engine for MOH TIME OS.

Correlates patterns and signals across domains to identify compound risks,
cross-domain causality, and produce actionable intelligence briefs.

Domain definitions:
- FINANCIAL: Revenue, payments, financial health
- OPERATIONAL: Quality, delivery, process efficiency
- RESOURCE: People capacity, project assignment
- COMMUNICATION: Client relationships, information flow
- DELIVERY: Projects, milestones, dependencies
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import sqlite3

from lib.intelligence.correlation_confidence import (
    CorrelationConfidenceCalculator,
    CorrelationSignalEvidence,
)
from lib.intelligence.patterns import (
    PATTERN_LIBRARY,
    PatternSeverity,
    PatternType,
    detect_all_patterns,
)
from lib.intelligence.signals import detect_all_signals

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class Domain(Enum):
    """Operational domains for correlation."""

    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    RESOURCE = "resource"
    COMMUNICATION = "communication"
    DELIVERY = "delivery"


class CorrelationType(Enum):
    """Types of cross-domain correlations."""

    CAUSAL = "causal"  # A causes B
    CO_OCCURRING = "co_occurring"  # A and B happen together
    AMPLIFYING = "amplifying"  # A amplifies B


class HealthGrade(Enum):
    """Overall health grades based on risk distribution."""

    A = "A"  # Excellent - no structural findings
    B = "B"  # Good - operational issues only
    C = "C"  # Fair - 1 structural or multiple operational
    D = "D"  # Poor - 2+ structural or compound risks
    F = "F"  # Critical - 3+ structural with compound risks


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class CompoundRisk:
    """Risk created by multiple patterns/signals firing together."""

    id: str
    name: str
    description: str
    component_pattern_ids: list[str] = field(default_factory=list)
    component_signal_ids: list[str] = field(default_factory=list)
    domains_affected: list[Domain] = field(default_factory=list)
    compound_severity: str = "operational"  # structural, operational, informational
    risk_narrative: str = ""
    combined_evidence: dict = field(default_factory=dict)
    detected_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "component_pattern_ids": self.component_pattern_ids,
            "component_signal_ids": self.component_signal_ids,
            "domains_affected": [d.value for d in self.domains_affected],
            "compound_severity": self.compound_severity,
            "risk_narrative": self.risk_narrative,
            "combined_evidence": self.combined_evidence,
            "detected_at": self.detected_at,
        }


@dataclass
class CrossDomainCorrelation:
    """Correlation between findings in different domains."""

    source_domain: Domain
    target_domain: Domain
    source_findings: list[str] = field(default_factory=list)
    target_findings: list[str] = field(default_factory=list)
    correlation_type: CorrelationType = CorrelationType.CO_OCCURRING
    explanation: str = ""
    confidence: float = 0.0  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "source_domain": self.source_domain.value,
            "target_domain": self.target_domain.value,
            "source_findings": self.source_findings,
            "target_findings": self.target_findings,
            "correlation_type": self.correlation_type.value,
            "explanation": self.explanation,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class PriorityAction:
    """Recommended action based on detected risks."""

    action_id: str
    description: str
    urgency: str  # IMMEDIATE, SOON, MONITOR
    source_risks: list[str] = field(default_factory=list)
    domains: list[Domain] = field(default_factory=list)
    expected_impact: str = ""

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "urgency": self.urgency,
            "source_risks": self.source_risks,
            "domains": [d.value for d in self.domains],
            "expected_impact": self.expected_impact,
        }


@dataclass
class IntelligenceBrief:
    """Complete intelligence brief from full scan."""

    generated_at: str
    pattern_results: dict = field(default_factory=dict)
    signal_results: dict = field(default_factory=dict)
    compound_risks: list[CompoundRisk] = field(default_factory=list)
    cross_domain_correlations: list[CrossDomainCorrelation] = field(default_factory=list)
    priority_actions: list[PriorityAction] = field(default_factory=list)
    executive_summary: str = ""
    health_grade: HealthGrade = HealthGrade.B

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "pattern_results": self.pattern_results,
            "signal_results": self.signal_results,
            "compound_risks": [r.to_dict() for r in self.compound_risks],
            "cross_domain_correlations": [c.to_dict() for c in self.cross_domain_correlations],
            "priority_actions": [a.to_dict() for a in self.priority_actions],
            "executive_summary": self.executive_summary,
            "health_grade": self.health_grade.value,
        }


# =============================================================================
# DOMAIN CLASSIFICATION MAPPING
# =============================================================================

PATTERN_DOMAIN_MAP = {
    # FINANCIAL
    "pat_revenue_concentration": Domain.FINANCIAL,
    "pat_comm_payment_correlation": Domain.FINANCIAL,
    # OPERATIONAL
    "pat_quality_degradation": Domain.OPERATIONAL,
    "pat_workload_distribution_drift": Domain.OPERATIONAL,
    "pat_load_quality_correlation": Domain.OPERATIONAL,
    # RESOURCE
    "pat_resource_concentration": Domain.RESOURCE,
    "pat_person_blast_radius": Domain.RESOURCE,
    "pat_team_exhaustion": Domain.RESOURCE,
    # COMMUNICATION
    "pat_communication_concentration": Domain.COMMUNICATION,
    "pat_client_ownership_drift": Domain.COMMUNICATION,
    "pat_client_engagement_erosion": Domain.COMMUNICATION,
    # DELIVERY
    "pat_project_dependency_chain": Domain.DELIVERY,
    "pat_client_cluster_risk": Domain.DELIVERY,
    "pat_client_type_concentration": Domain.DELIVERY,
}

SIGNAL_DOMAIN_MAP = {
    # FINANCIAL
    "sig_client_invoice_aging": Domain.FINANCIAL,
    "sig_client_hidden_cost": Domain.FINANCIAL,
    # OPERATIONAL
    "sig_portfolio_quality_declining": Domain.OPERATIONAL,
    "sig_person_output_declining": Domain.OPERATIONAL,
    # RESOURCE
    "sig_person_overloaded": Domain.RESOURCE,
    "sig_person_concentration": Domain.RESOURCE,
    "sig_person_burnout_risk": Domain.RESOURCE,
    "sig_portfolio_capacity_ceiling": Domain.RESOURCE,
    # COMMUNICATION
    "sig_client_comm_drop": Domain.COMMUNICATION,
    "sig_client_engagement_fading": Domain.COMMUNICATION,
    "sig_client_comm_anomaly": Domain.COMMUNICATION,
    # DELIVERY
    "sig_client_overdue_tasks": Domain.DELIVERY,
    "sig_project_stalled": Domain.DELIVERY,
    "sig_project_cascade_risk": Domain.DELIVERY,
    "sig_client_cluster_risk": Domain.DELIVERY,
    "sig_client_churn_risk": Domain.DELIVERY,
    "sig_client_score_critical": Domain.DELIVERY,
    "sig_project_overloaded": Domain.DELIVERY,
}


# =============================================================================
# COMPOUND RISK RULES
# =============================================================================

COMPOUND_RISK_RULES = [
    {
        "id": "revenue_cliff",
        "name": "Revenue Cliff Risk",
        "description": "Revenue concentration + client engagement erosion = imminent revenue loss",
        "patterns": ["pat_revenue_concentration"],
        "signals": ["sig_client_comm_drop", "sig_client_engagement_fading"],
        "min_matches": 1,
        "severity": "structural",
    },
    {
        "id": "capacity_collapse",
        "name": "Capacity Collapse Risk",
        "description": "Resource concentration + team exhaustion = workload unsustainable",
        "patterns": ["pat_resource_concentration", "pat_team_exhaustion"],
        "signals": ["sig_person_overloaded"],
        "min_matches": 1,
        "severity": "structural",
    },
    {
        "id": "quality_spiral",
        "name": "Service Quality Spiral Risk",
        "description": "Quality degradation + communication concentration = relationship damage",
        "patterns": ["pat_quality_degradation", "pat_communication_concentration"],
        "signals": ["sig_client_overdue_tasks"],
        "min_matches": 1,
        "severity": "structural",
    },
    {
        "id": "single_point_failure",
        "name": "Single Point of Failure Cascade",
        "description": "Person blast radius + project dependency chain = business-wide impact",
        "patterns": ["pat_person_blast_radius", "pat_project_dependency_chain"],
        "signals": [],
        "min_matches": 1,
        "severity": "structural",
    },
    {
        "id": "overload_degradation",
        "name": "Overload-Induced Degradation",
        "description": "Load-quality correlation + workload drift = quality collapse under load",
        "patterns": ["pat_load_quality_correlation", "pat_workload_distribution_drift"],
        "signals": ["sig_portfolio_quality_declining"],
        "min_matches": 1,
        "severity": "operational",
    },
    {
        "id": "domain_systemic",
        "name": "Domain Systemic Risk",
        "description": "3+ patterns in same domain = systemic issue, not isolated",
        "patterns": [],  # Matched by rule logic
        "signals": [],
        "min_matches": 3,  # At least 3 in same domain
        "severity": "operational",
        "rule": "same_domain_threshold",
    },
]


# =============================================================================
# CORRELATION ENGINE
# =============================================================================


class CorrelationEngine:
    """
    Cross-domain pattern and signal correlation engine.

    Runs pattern and signal detection, correlates findings across domains,
    identifies compound risks, and generates actionable intelligence.
    """

    def __init__(self, db_path=None):
        """Initialize the correlation engine."""
        self.db_path = db_path
        self.logger = logger

    def run_full_scan(self) -> IntelligenceBrief:
        """
        Execute complete intelligence scan.

        Runs all patterns and signals, correlates findings, identifies
        compound risks, and generates priority actions.
        """
        scan_started = datetime.now().isoformat()

        # Run pattern detection
        try:
            pattern_results = detect_all_patterns(self.db_path)
            patterns = pattern_results.get("patterns", [])
        except (sqlite3.Error, ValueError, OSError) as e:
            self.logger.error(f"Error detecting patterns: {e}")
            patterns = []
            pattern_results = {}

        # Run signal detection
        try:
            signal_results = detect_all_signals(self.db_path)
            signals = signal_results.get("signals", [])
        except (sqlite3.Error, ValueError, OSError) as e:
            self.logger.error(f"Error detecting signals: {e}")
            signals = []
            signal_results = {}

        # Find compound risks
        compound_risks = self.find_compound_risks(patterns, signals)

        # Find cross-domain correlations
        all_findings = {
            "patterns": patterns,
            "signals": signals,
        }
        cross_domain = self.cross_domain_correlations(all_findings)

        # Generate priority actions
        priority_actions = self.generate_priority_actions(
            compound_risks, patterns, signals, cross_domain
        )

        # Calculate health grade
        health_grade = self._calculate_health_grade(patterns, compound_risks)

        # Build executive summary
        summary = self._build_executive_summary(patterns, signals, compound_risks, health_grade)

        return IntelligenceBrief(
            generated_at=scan_started,
            pattern_results=pattern_results,
            signal_results=signal_results,
            compound_risks=compound_risks,
            cross_domain_correlations=cross_domain,
            priority_actions=priority_actions,
            executive_summary=summary,
            health_grade=health_grade,
        )

    def classify_domain(self, pattern_or_signal_id: str) -> Domain | None:
        """
        Classify a pattern or signal ID to its operational domain.

        Returns the Domain enum value, or None if not found.
        """
        if pattern_or_signal_id in PATTERN_DOMAIN_MAP:
            return PATTERN_DOMAIN_MAP[pattern_or_signal_id]
        if pattern_or_signal_id in SIGNAL_DOMAIN_MAP:
            return SIGNAL_DOMAIN_MAP[pattern_or_signal_id]
        return None

    def find_compound_risks(self, patterns: list, signals: list) -> list[CompoundRisk]:
        """
        Identify compound risks from multiple firing patterns/signals.

        Applies hardcoded compound risk rules to detect multi-factor risks.
        """
        compound_risks = []

        # Extract IDs for matching
        pattern_ids = {p.get("pattern_id") for p in patterns}
        signal_ids = {s.get("signal_id") for s in signals}

        # Check each rule
        for rule in COMPOUND_RISK_RULES:
            if rule.get("rule") == "same_domain_threshold":
                # Special handling: 3+ patterns in same domain
                risks = self._check_domain_systemic_risk(patterns, rule)
                compound_risks.extend(risks)
            else:
                # Standard rule: check pattern + signal combinations
                rule_patterns = rule.get("patterns", [])
                rule_signals = rule.get("signals", [])

                pattern_matches = [p for p in rule_patterns if p in pattern_ids]
                signal_matches = [s for s in rule_signals if s in signal_ids]
                total_matches = len(pattern_matches) + len(signal_matches)

                if total_matches >= rule.get("min_matches", 1):
                    # Rule triggered
                    risk = CompoundRisk(
                        id=rule["id"],
                        name=rule["name"],
                        description=rule["description"],
                        component_pattern_ids=pattern_matches,
                        component_signal_ids=signal_matches,
                        domains_affected=self._get_domains_for_findings(
                            pattern_matches, signal_matches
                        ),
                        compound_severity=rule.get("severity", "operational"),
                        risk_narrative=rule["description"],
                        detected_at=datetime.now().isoformat(),
                    )
                    compound_risks.append(risk)

        return compound_risks

    def _check_domain_systemic_risk(self, patterns: list, rule: dict) -> list[CompoundRisk]:
        """Check if 3+ patterns exist in the same domain (systemic risk)."""
        risks = []

        # Group patterns by domain
        by_domain = {}
        for pattern in patterns:
            pattern_id = pattern.get("pattern_id")
            domain = self.classify_domain(pattern_id)
            if domain:
                if domain not in by_domain:
                    by_domain[domain] = []
                by_domain[domain].append(pattern_id)

        # Find domains with 3+ patterns
        for domain, pattern_ids in by_domain.items():
            if len(pattern_ids) >= rule.get("min_matches", 3):
                risk = CompoundRisk(
                    id=f"systemic_{domain.value}",
                    name=f"{domain.value.title()} Systemic Risk",
                    description=f"{len(pattern_ids)} patterns detected in {domain.value} domain",
                    component_pattern_ids=pattern_ids,
                    domains_affected=[domain],
                    compound_severity=rule.get("severity", "operational"),
                    risk_narrative=f"Multiple systemic issues in {domain.value}: {', '.join(pattern_ids)}",
                    detected_at=datetime.now().isoformat(),
                )
                risks.append(risk)

        return risks

    def cross_domain_correlations(self, findings: dict) -> list[CrossDomainCorrelation]:
        """
        Find correlations between findings in different domains.

        Identifies causal, co-occurring, and amplifying relationships.
        """
        correlations = []

        patterns = findings.get("patterns", [])
        signals = findings.get("signals", [])

        # Build domain maps
        pattern_by_domain = {}
        for pattern in patterns:
            pattern_id = pattern.get("pattern_id")
            domain = self.classify_domain(pattern_id)
            if domain:
                if domain not in pattern_by_domain:
                    pattern_by_domain[domain] = []
                pattern_by_domain[domain].append(pattern_id)

        signal_by_domain = {}
        for signal in signals:
            signal_id = signal.get("signal_id")
            domain = self.classify_domain(signal_id)
            if domain:
                if domain not in signal_by_domain:
                    signal_by_domain[domain] = []
                signal_by_domain[domain].append(signal_id)

        # Check known causal relationships
        causal_pairs = [
            (Domain.RESOURCE, Domain.OPERATIONAL, "Overload → Quality decline"),
            (Domain.FINANCIAL, Domain.COMMUNICATION, "Revenue risk → Engagement drop"),
            (Domain.RESOURCE, Domain.DELIVERY, "Capacity shortage → Delivery delays"),
            (Domain.COMMUNICATION, Domain.FINANCIAL, "Engagement fade → Payment delays"),
        ]

        for source_domain, target_domain, explanation in causal_pairs:
            source_items = pattern_by_domain.get(source_domain, []) + signal_by_domain.get(
                source_domain, []
            )
            target_items = pattern_by_domain.get(target_domain, []) + signal_by_domain.get(
                target_domain, []
            )

            if source_items and target_items:
                # Compute confidence from signal evidence
                all_ids = source_items[:3] + target_items[:3]
                calc = CorrelationConfidenceCalculator()
                evidence = [
                    CorrelationSignalEvidence(
                        signal_key=sid,
                        signal_type=sid,
                        severity="WARNING",  # Default; full lookup deferred
                        detected_at=datetime.now(),
                        is_present=True,
                    )
                    for sid in all_ids
                ]
                factors = calc.calculate(evidence, required_signals=2)
                confidence = factors.final_confidence

                correlation = CrossDomainCorrelation(
                    source_domain=source_domain,
                    target_domain=target_domain,
                    source_findings=source_items[:3],  # Top 3
                    target_findings=target_items[:3],
                    correlation_type=CorrelationType.CAUSAL,
                    explanation=explanation,
                    confidence=confidence,
                )
                correlations.append(correlation)

        return correlations

    def generate_priority_actions(
        self,
        compound_risks: list[CompoundRisk],
        patterns: list,
        signals: list,
        cross_domain: list[CrossDomainCorrelation],
    ) -> list[PriorityAction]:
        """
        Generate prioritized actionable recommendations.

        Based on compound risks, severity distribution, and domain impact.
        """
        actions = []

        # High-urgency actions from compound risks
        for risk in compound_risks:
            if risk.compound_severity == "structural":
                urgency = "IMMEDIATE"
            else:
                urgency = "SOON"

            action = PriorityAction(
                action_id=f"action_{risk.id}",
                description=f"Address {risk.name}: {risk.description}",
                urgency=urgency,
                source_risks=[risk.id],
                domains=risk.domains_affected,
                expected_impact=self._describe_impact(risk),
            )
            actions.append(action)

        # Domain-specific actions
        pattern_by_domain = {}
        for pattern in patterns:
            pattern_id = pattern.get("pattern_id")
            domain = self.classify_domain(pattern_id)
            if domain:
                if domain not in pattern_by_domain:
                    pattern_by_domain[domain] = []
                pattern_by_domain[domain].append(pattern_id)

        # For domains with multiple issues
        for domain, pattern_ids in pattern_by_domain.items():
            if len(pattern_ids) >= 2:
                action = PriorityAction(
                    action_id=f"domain_{domain.value}",
                    description=f"Conduct {domain.value} domain review: {len(pattern_ids)} issues detected",
                    urgency="SOON",
                    domains=[domain],
                    expected_impact=f"Reduce {domain.value} domain risk factors",
                )
                actions.append(action)

        # Sort by urgency
        urgency_order = {"IMMEDIATE": 0, "SOON": 1, "MONITOR": 2}
        actions.sort(key=lambda a: urgency_order.get(a.urgency, 3))

        return actions

    def _get_domains_for_findings(self, pattern_ids: list, signal_ids: list) -> list[Domain]:
        """Get unique domains for a set of findings."""
        domains = set()
        for pid in pattern_ids:
            domain = self.classify_domain(pid)
            if domain:
                domains.add(domain)
        for sid in signal_ids:
            domain = self.classify_domain(sid)
            if domain:
                domains.add(domain)
        return list(domains)

    def _calculate_health_grade(self, patterns: list, compound_risks: list) -> HealthGrade:
        """
        Calculate overall health grade based on risk distribution.

        A: No structural findings, ≤2 operational
        B: No structural, ≤5 operational
        C: 1 structural OR >5 operational
        D: 2+ structural OR any compound risk
        F: 3+ structural AND compound risks
        """
        structural_count = 0
        operational_count = 0

        for pattern in patterns:
            severity = pattern.get("severity", "informational")
            if severity == "structural":
                structural_count += 1
            elif severity == "operational":
                operational_count += 1

        compound_risk_count = len(compound_risks)

        # Apply grading rules
        if structural_count >= 3 and compound_risk_count > 0:
            return HealthGrade.F
        elif structural_count >= 2 or compound_risk_count > 0:
            return HealthGrade.D
        elif structural_count >= 1 or operational_count > 5:
            return HealthGrade.C
        elif operational_count > 2:
            return HealthGrade.B
        else:
            return HealthGrade.A

    def _build_executive_summary(
        self, patterns: list, signals: list, compound_risks: list, health_grade: HealthGrade
    ) -> str:
        """Build human-readable executive summary of findings."""
        lines = []

        lines.append(f"Health Grade: {health_grade.value}")
        lines.append("")

        # Pattern summary
        if patterns:
            structural = [p for p in patterns if p.get("severity") == "structural"]
            operational = [p for p in patterns if p.get("severity") == "operational"]
            lines.append(
                f"Patterns: {len(patterns)} detected ({len(structural)} structural, {len(operational)} operational)"
            )

        # Signal summary
        if signals:
            critical = [s for s in signals if s.get("severity") == "critical"]
            warning = [s for s in signals if s.get("severity") == "warning"]
            lines.append(
                f"Signals: {len(signals)} detected ({len(critical)} critical, {len(warning)} warning)"
            )

        # Compound risks
        if compound_risks:
            lines.append(f"Compound Risks: {len(compound_risks)} identified")
            for risk in compound_risks[:3]:
                lines.append(f"  - {risk.name}: {risk.description}")

        lines.append("")
        lines.append("Recommended Actions: See priority_actions for specific recommendations.")

        return "\n".join(lines)

    def _describe_impact(self, risk: CompoundRisk) -> str:
        """Describe the expected impact of addressing a compound risk."""
        domain_str = ", ".join(d.value for d in risk.domains_affected)
        return f"Reduce {domain_str} domain risk; improve stability and capacity"
