"""
Intelligence proposal generation for MOH TIME OS.

Assembles scores, signals, and patterns into actionable intelligence.
This is the layer that turns detection into communication.

A proposal is: "Client X's communication dropped 40%, their last two task 
deadlines slipped, and they have an invoice 30 days overdue — this account 
needs a check-in call."

Multiple signals + scores + patterns assembled into one actionable item.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# PROPOSAL STRUCTURE
# =============================================================================

class ProposalType(Enum):
    """Types of intelligence proposals."""
    CLIENT_RISK = "client_risk"           # Client health concern
    RESOURCE_RISK = "resource_risk"       # Person/capacity concern
    PROJECT_RISK = "project_risk"         # Project health concern
    PORTFOLIO_RISK = "portfolio_risk"     # Systemic/structural concern
    FINANCIAL_ALERT = "financial_alert"   # Revenue/payment concern
    OPPORTUNITY = "opportunity"           # Positive signal worth noting


class ProposalUrgency(Enum):
    """Urgency levels for proposals."""
    IMMEDIATE = "immediate"     # Act today
    THIS_WEEK = "this_week"     # Act within 5 business days
    MONITOR = "monitor"         # Track, no immediate action


@dataclass
class Proposal:
    """
    An actionable intelligence proposal.
    
    Combines scores, signals, and patterns into a single coherent
    recommendation that implies action.
    """
    id: str                           # "prop_YYYYMMDD_NNN"
    type: ProposalType
    urgency: ProposalUrgency
    headline: str                     # One sentence: what + what to do
    entity: dict                      # {"type": "client", "id": "...", "name": "..."}
    summary: str                      # 2-3 sentence explanation
    evidence: list[dict]              # Supporting evidence items
    implied_action: str               # Concrete next step
    related_entities: list[dict] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    active_signals: list[str] = field(default_factory=list)
    active_patterns: list[str] = field(default_factory=list)
    first_detected: str = ""
    trend: str = "new"                # "escalating" | "stable" | "improving" | "new"
    confidence: str = "medium"        # "high" | "medium" | "low"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "urgency": self.urgency.value,
            "headline": self.headline,
            "entity": self.entity,
            "summary": self.summary,
            "evidence": self.evidence,
            "implied_action": self.implied_action,
            "related_entities": self.related_entities,
            "scores": self.scores,
            "active_signals": self.active_signals,
            "active_patterns": self.active_patterns,
            "first_detected": self.first_detected,
            "trend": self.trend,
            "confidence": self.confidence,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

import uuid

def _generate_proposal_id() -> str:
    """Generate a unique proposal ID."""
    now = datetime.now()
    unique = uuid.uuid4().hex[:6]
    return f"prop_{now.strftime('%Y%m%d')}_{unique}"


def _format_evidence_item(
    source: str,
    source_id: str,
    description: str,
    data: dict = None
) -> dict:
    """Format a single evidence item."""
    return {
        "source": source,
        "source_id": source_id,
        "description": description,
        "data": data or {},
    }


def _format_evidence(
    scorecard: dict = None,
    signals: list[dict] = None,
    patterns: list[dict] = None
) -> list[dict]:
    """
    Format evidence items for a proposal.
    
    Evidence is ordered by impact: most concerning items first.
    """
    evidence = []
    
    # Add score evidence
    if scorecard:
        score = scorecard.get("composite_score", 0)
        classification = scorecard.get("classification", "unknown")
        evidence.append(_format_evidence_item(
            source="score",
            source_id="composite",
            description=f"Health score: {score}/100 ({classification})",
            data={"score": score, "classification": classification}
        ))
        
        # Add dimension scores
        dimensions = scorecard.get("dimensions", {})
        for dim_name, dim_data in dimensions.items():
            if isinstance(dim_data, dict):
                dim_score = dim_data.get("score", 0)
                if dim_score < 50:  # Only include concerning dimensions
                    evidence.append(_format_evidence_item(
                        source="score",
                        source_id=f"dim_{dim_name}",
                        description=f"{dim_name.replace('_', ' ').title()}: {dim_score}/100",
                        data={"dimension": dim_name, "score": dim_score}
                    ))
    
    # Add signal evidence
    if signals:
        for sig in signals:
            severity = sig.get("severity", "watch")
            evidence.append(_format_evidence_item(
                source="signal",
                source_id=sig.get("signal_id", "unknown"),
                description=sig.get("evidence_text", sig.get("signal_name", "Signal detected")),
                data={
                    "severity": severity,
                    "signal_id": sig.get("signal_id"),
                }
            ))
    
    # Add pattern evidence
    if patterns:
        for pat in patterns:
            evidence.append(_format_evidence_item(
                source="pattern",
                source_id=pat.get("pattern_id", "unknown"),
                description=pat.get("evidence_narrative", pat.get("pattern_name", "Pattern detected")),
                data={
                    "severity": pat.get("severity"),
                    "pattern_id": pat.get("pattern_id"),
                }
            ))
    
    # Sort by severity/impact (critical first)
    severity_order = {"critical": 0, "structural": 0, "warning": 1, "operational": 1, "watch": 2, "informational": 2}
    evidence.sort(key=lambda e: severity_order.get(e.get("data", {}).get("severity", "watch"), 3))
    
    return evidence


def _generate_headline(
    proposal_type: ProposalType,
    entity: dict,
    evidence: list[dict],
    scorecard: dict = None
) -> str:
    """
    Generate a concise, actionable headline.
    
    Good: 'Client Acme Corp at risk: communication down 40%, score dropped to 28'
    Bad: 'Alert: anomaly detected in client metrics'
    """
    entity_name = entity.get("name", "Unknown")
    entity_type = entity.get("type", "entity")
    
    # Extract key metrics from evidence
    concerns = []
    for ev in evidence[:3]:  # Top 3 concerns
        desc = ev.get("description", "")
        if desc and len(desc) < 50:
            concerns.append(desc)
    
    # Get score if available
    score_str = ""
    if scorecard:
        score = scorecard.get("composite_score")
        classification = scorecard.get("classification", "")
        if score is not None:
            score_str = f"score {score} ({classification})"
    
    # Build headline based on type
    if proposal_type == ProposalType.CLIENT_RISK:
        if score_str:
            headline = f"{entity_name}: {score_str}"
        else:
            headline = f"{entity_name}: health concern"
        if concerns:
            headline += f" — {concerns[0]}"
    
    elif proposal_type == ProposalType.RESOURCE_RISK:
        headline = f"{entity_name}: capacity concern"
        if concerns:
            headline += f" — {concerns[0]}"
    
    elif proposal_type == ProposalType.PROJECT_RISK:
        headline = f"Project {entity_name}: delivery risk"
        if concerns:
            headline += f" — {concerns[0]}"
    
    elif proposal_type == ProposalType.PORTFOLIO_RISK:
        headline = f"Portfolio alert: {concerns[0] if concerns else 'structural risk detected'}"
    
    elif proposal_type == ProposalType.FINANCIAL_ALERT:
        headline = f"{entity_name}: financial attention needed"
        if concerns:
            headline += f" — {concerns[0]}"
    
    elif proposal_type == ProposalType.OPPORTUNITY:
        headline = f"{entity_name}: positive signal"
        if concerns:
            headline += f" — {concerns[0]}"
    
    else:
        headline = f"{entity_name}: attention needed"
    
    return headline


def _generate_summary(
    entity: dict,
    evidence: list[dict],
    scorecard: dict = None
) -> str:
    """Generate a 2-3 sentence summary."""
    entity_name = entity.get("name", "Unknown")
    
    # Count evidence types
    signal_count = sum(1 for e in evidence if e.get("source") == "signal")
    pattern_count = sum(1 for e in evidence if e.get("source") == "pattern")
    
    parts = []
    
    if scorecard:
        score = scorecard.get("composite_score")
        classification = scorecard.get("classification")
        if score is not None:
            parts.append(f"{entity_name} has a health score of {score}/100 ({classification}).")
    
    if signal_count > 0:
        parts.append(f"{signal_count} active signal(s) detected.")
    
    if pattern_count > 0:
        parts.append(f"Part of {pattern_count} structural pattern(s).")
    
    # Add top concerns
    top_concerns = [e.get("description") for e in evidence[:2] if e.get("source") == "signal"]
    if top_concerns:
        parts.append(f"Key concerns: {'; '.join(top_concerns)}.")
    
    return " ".join(parts) if parts else "Review recommended based on current intelligence."


def _generate_action(
    proposal_type: ProposalType,
    entity: dict,
    evidence: list[dict]
) -> str:
    """Generate concrete next step."""
    entity_name = entity.get("name", "Unknown")
    
    if proposal_type == ProposalType.CLIENT_RISK:
        return f"Review {entity_name} account status. Schedule check-in if needed."
    
    elif proposal_type == ProposalType.RESOURCE_RISK:
        return f"Review {entity_name}'s workload. Consider redistribution if overloaded."
    
    elif proposal_type == ProposalType.PROJECT_RISK:
        return f"Check project {entity_name} status. Address blockers or timeline risks."
    
    elif proposal_type == ProposalType.PORTFOLIO_RISK:
        return "Review portfolio-level risks. Consider structural interventions."
    
    elif proposal_type == ProposalType.FINANCIAL_ALERT:
        return f"Follow up on {entity_name} financials. Check payment status."
    
    elif proposal_type == ProposalType.OPPORTUNITY:
        return f"Note positive signal for {entity_name}. Consider expanding engagement."
    
    return "Review and determine appropriate action."


def _determine_urgency(
    score_classification: str = None,
    signal_severities: list[str] = None,
    pattern_severities: list[str] = None,
    trend: str = "new"
) -> ProposalUrgency:
    """
    Determine urgency from combined severity indicators.
    
    IMMEDIATE if: any CRITICAL signal, or CRITICAL score + escalating trend, or structural pattern
    THIS_WEEK if: any WARNING signal, or AT_RISK score
    MONITOR if: only WATCH signals, or STABLE score
    """
    signal_severities = signal_severities or []
    pattern_severities = pattern_severities or []
    
    # Check for IMMEDIATE conditions
    if "critical" in signal_severities:
        return ProposalUrgency.IMMEDIATE
    if score_classification == "critical" and trend == "escalating":
        return ProposalUrgency.IMMEDIATE
    if "structural" in pattern_severities:
        return ProposalUrgency.IMMEDIATE
    
    # Check for THIS_WEEK conditions
    if "warning" in signal_severities:
        return ProposalUrgency.THIS_WEEK
    if score_classification in ["critical", "at_risk"]:
        return ProposalUrgency.THIS_WEEK
    if "operational" in pattern_severities:
        return ProposalUrgency.THIS_WEEK
    
    # Default to MONITOR
    return ProposalUrgency.MONITOR


def _determine_trend(signals: list[dict] = None) -> str:
    """
    Determine if this proposal represents a new issue, escalating, stable, or improving.
    """
    if not signals:
        return "new"
    
    # Check signal evaluation counts
    eval_counts = [s.get("evaluation_count", 1) for s in signals if "evaluation_count" in s]
    
    if not eval_counts:
        return "new"
    
    avg_count = sum(eval_counts) / len(eval_counts)
    
    if avg_count <= 1:
        return "new"
    elif avg_count <= 3:
        return "stable"
    else:
        return "escalating"


def _determine_confidence(
    scorecard: dict = None,
    signals: list[dict] = None,
    patterns: list[dict] = None
) -> str:
    """Determine confidence level based on evidence completeness."""
    evidence_count = 0
    
    if scorecard and scorecard.get("composite_score") is not None:
        evidence_count += 1
    
    if signals:
        evidence_count += len(signals)
    
    if patterns:
        evidence_count += len(patterns)
    
    if evidence_count >= 3:
        return "high"
    elif evidence_count >= 1:
        return "medium"
    return "low"


# =============================================================================
# PROPOSAL ASSEMBLY
# =============================================================================

def _assemble_client_proposal(
    client_id: str,
    client_name: str,
    scorecard: dict = None,
    signals: list[dict] = None,
    patterns: list[dict] = None
) -> Proposal:
    """Assemble a client-level proposal from all available intelligence."""
    signals = signals or []
    patterns = patterns or []
    
    entity = {"type": "client", "id": client_id, "name": client_name}
    evidence = _format_evidence(scorecard, signals, patterns)
    
    # Determine proposal type
    # Check for financial signals
    financial_signals = [s for s in signals if "payment" in s.get("signal_id", "").lower()]
    if financial_signals:
        proposal_type = ProposalType.FINANCIAL_ALERT
    else:
        proposal_type = ProposalType.CLIENT_RISK
    
    # Determine urgency
    signal_severities = [s.get("severity") for s in signals]
    pattern_severities = [p.get("severity") for p in patterns]
    classification = scorecard.get("classification") if scorecard else None
    trend = _determine_trend(signals)
    urgency = _determine_urgency(classification, signal_severities, pattern_severities, trend)
    
    return Proposal(
        id=_generate_proposal_id(),
        type=proposal_type,
        urgency=urgency,
        headline=_generate_headline(proposal_type, entity, evidence, scorecard),
        entity=entity,
        summary=_generate_summary(entity, evidence, scorecard),
        evidence=evidence,
        implied_action=_generate_action(proposal_type, entity, evidence),
        active_signals=[s.get("signal_id") for s in signals],
        active_patterns=[p.get("pattern_id") for p in patterns],
        scores={"composite": scorecard.get("composite_score")} if scorecard else {},
        first_detected=datetime.now().isoformat(),
        trend=trend,
        confidence=_determine_confidence(scorecard, signals, patterns),
    )


def _assemble_resource_proposal(
    person_id: str,
    person_name: str,
    scorecard: dict = None,
    signals: list[dict] = None,
    patterns: list[dict] = None
) -> Proposal:
    """Assemble a resource/person-level proposal."""
    signals = signals or []
    patterns = patterns or []
    
    entity = {"type": "person", "id": person_id, "name": person_name}
    evidence = _format_evidence(scorecard, signals, patterns)
    proposal_type = ProposalType.RESOURCE_RISK
    
    signal_severities = [s.get("severity") for s in signals]
    pattern_severities = [p.get("severity") for p in patterns]
    classification = scorecard.get("classification") if scorecard else None
    trend = _determine_trend(signals)
    urgency = _determine_urgency(classification, signal_severities, pattern_severities, trend)
    
    return Proposal(
        id=_generate_proposal_id(),
        type=proposal_type,
        urgency=urgency,
        headline=_generate_headline(proposal_type, entity, evidence, scorecard),
        entity=entity,
        summary=_generate_summary(entity, evidence, scorecard),
        evidence=evidence,
        implied_action=_generate_action(proposal_type, entity, evidence),
        active_signals=[s.get("signal_id") for s in signals],
        active_patterns=[p.get("pattern_id") for p in patterns],
        scores={"composite": scorecard.get("composite_score")} if scorecard else {},
        first_detected=datetime.now().isoformat(),
        trend=trend,
        confidence=_determine_confidence(scorecard, signals, patterns),
    )


def _assemble_project_proposal(
    project_id: str,
    project_name: str,
    scorecard: dict = None,
    signals: list[dict] = None,
    patterns: list[dict] = None
) -> Proposal:
    """Assemble a project-level proposal."""
    signals = signals or []
    patterns = patterns or []
    
    entity = {"type": "project", "id": project_id, "name": project_name}
    evidence = _format_evidence(scorecard, signals, patterns)
    proposal_type = ProposalType.PROJECT_RISK
    
    signal_severities = [s.get("severity") for s in signals]
    pattern_severities = [p.get("severity") for p in patterns]
    classification = scorecard.get("classification") if scorecard else None
    trend = _determine_trend(signals)
    urgency = _determine_urgency(classification, signal_severities, pattern_severities, trend)
    
    return Proposal(
        id=_generate_proposal_id(),
        type=proposal_type,
        urgency=urgency,
        headline=_generate_headline(proposal_type, entity, evidence, scorecard),
        entity=entity,
        summary=_generate_summary(entity, evidence, scorecard),
        evidence=evidence,
        implied_action=_generate_action(proposal_type, entity, evidence),
        active_signals=[s.get("signal_id") for s in signals],
        active_patterns=[p.get("pattern_id") for p in patterns],
        scores={"composite": scorecard.get("composite_score")} if scorecard else {},
        first_detected=datetime.now().isoformat(),
        trend=trend,
        confidence=_determine_confidence(scorecard, signals, patterns),
    )


def _assemble_portfolio_proposal(
    pattern: dict,
    supporting_signals: list[dict] = None
) -> Proposal:
    """Assemble a portfolio-level proposal from a structural pattern."""
    supporting_signals = supporting_signals or []
    
    entity = {"type": "portfolio", "id": "portfolio", "name": "Portfolio"}
    evidence = _format_evidence(patterns=[pattern])
    
    # Add supporting signal evidence
    if supporting_signals:
        for sig in supporting_signals[:5]:
            evidence.append(_format_evidence_item(
                source="signal",
                source_id=sig.get("signal_id", ""),
                description=sig.get("evidence_text", "Supporting signal"),
                data={"severity": sig.get("severity")}
            ))
    
    proposal_type = ProposalType.PORTFOLIO_RISK
    pattern_severity = pattern.get("severity", "informational")
    urgency = _determine_urgency(
        pattern_severities=[pattern_severity]
    )
    
    return Proposal(
        id=_generate_proposal_id(),
        type=proposal_type,
        urgency=urgency,
        headline=_generate_headline(proposal_type, entity, evidence),
        entity=entity,
        summary=pattern.get("evidence_narrative", "Structural pattern detected."),
        evidence=evidence,
        implied_action=pattern.get("implied_action", "Review portfolio-level risks."),
        active_signals=[s.get("signal_id") for s in supporting_signals],
        active_patterns=[pattern.get("pattern_id")],
        related_entities=pattern.get("entities_involved", []),
        first_detected=datetime.now().isoformat(),
        trend="new",
        confidence=pattern.get("confidence", "medium"),
    )


# =============================================================================
# DEDUPLICATION AND MERGING
# =============================================================================

def _merge_proposals(proposals: list[Proposal]) -> list[Proposal]:
    """
    Merge multiple proposals about the same entity into one richer proposal.
    
    Rules:
    - Same entity → merge evidence lists, take highest urgency, combine actions
    - Never lose evidence: merged proposal has union of all evidence items
    """
    if not proposals:
        return []
    
    # Group by entity key
    by_entity = {}
    for prop in proposals:
        key = (prop.entity.get("type"), prop.entity.get("id"))
        if key not in by_entity:
            by_entity[key] = []
        by_entity[key].append(prop)
    
    merged = []
    for key, group in by_entity.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            # Merge multiple proposals for same entity
            base = group[0]
            
            # Collect all evidence (deduplicated by source_id)
            all_evidence = {}
            for prop in group:
                for ev in prop.evidence:
                    ev_key = ev.get("source_id", str(ev))
                    if ev_key not in all_evidence:
                        all_evidence[ev_key] = ev
            
            # Take highest urgency
            urgency_order = {ProposalUrgency.IMMEDIATE: 0, ProposalUrgency.THIS_WEEK: 1, ProposalUrgency.MONITOR: 2}
            highest_urgency = min(group, key=lambda p: urgency_order.get(p.urgency, 3)).urgency
            
            # Collect all signals and patterns
            all_signals = list(set(sig for prop in group for sig in prop.active_signals))
            all_patterns = list(set(pat for prop in group for pat in prop.active_patterns))
            
            # Create merged proposal
            merged_evidence = list(all_evidence.values())
            merged_prop = Proposal(
                id=base.id,
                type=base.type,
                urgency=highest_urgency,
                headline=_generate_headline(base.type, base.entity, merged_evidence, base.scores),
                entity=base.entity,
                summary=base.summary,
                evidence=merged_evidence,
                implied_action=base.implied_action,
                related_entities=base.related_entities,
                scores=base.scores,
                active_signals=all_signals,
                active_patterns=all_patterns,
                first_detected=base.first_detected,
                trend=base.trend,
                confidence="high" if len(merged_evidence) >= 3 else base.confidence,
            )
            merged.append(merged_prop)
    
    return merged


# =============================================================================
# MAIN PROPOSAL GENERATION
# =============================================================================

def generate_proposals(
    signals: dict = None,
    patterns: dict = None,
    db_path: Optional[Path] = None
) -> list[Proposal]:
    """
    Generate proposals from the current intelligence state.
    
    Process:
    1. For each entity with active signals, create a proposal
    2. For each detected pattern, create a portfolio-level proposal
    3. Deduplicate: merge proposals about the same entity
    4. Return sorted list (IMMEDIATE first)
    """
    proposals = []
    signals = signals or {}
    patterns = patterns or {}
    
    signal_list = signals.get("signals", [])
    pattern_list = patterns.get("patterns", [])
    
    # Group signals by entity
    signals_by_entity = {}
    for sig in signal_list:
        entity_type = sig.get("entity_type")
        entity_id = sig.get("entity_id")
        entity_name = sig.get("entity_name", entity_id)
        key = (entity_type, entity_id)
        
        if key not in signals_by_entity:
            signals_by_entity[key] = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "signals": []
            }
        signals_by_entity[key]["signals"].append(sig)
    
    # Create entity-level proposals
    for key, data in signals_by_entity.items():
        entity_type = data["entity_type"]
        entity_id = data["entity_id"]
        entity_name = data["entity_name"]
        entity_signals = data["signals"]
        
        # Find patterns involving this entity
        entity_patterns = [
            p for p in pattern_list
            if any(
                e.get("id") == entity_id or e.get("type") == entity_type
                for e in p.get("entities_involved", [])
            )
        ]
        
        if entity_type == "client":
            prop = _assemble_client_proposal(
                entity_id, entity_name,
                signals=entity_signals,
                patterns=entity_patterns
            )
            proposals.append(prop)
        
        elif entity_type == "person":
            prop = _assemble_resource_proposal(
                entity_id, entity_name,
                signals=entity_signals,
                patterns=entity_patterns
            )
            proposals.append(prop)
        
        elif entity_type == "project":
            prop = _assemble_project_proposal(
                entity_id, entity_name,
                signals=entity_signals,
                patterns=entity_patterns
            )
            proposals.append(prop)
    
    # Create portfolio-level proposals from structural patterns
    structural_patterns = [p for p in pattern_list if p.get("severity") == "structural"]
    for pattern in structural_patterns:
        # Find supporting signals
        supporting = [
            s for s in signal_list
            if s.get("signal_id") in pattern.get("supporting_signals", [])
        ]
        prop = _assemble_portfolio_proposal(pattern, supporting)
        proposals.append(prop)
    
    # Merge and deduplicate
    proposals = _merge_proposals(proposals)
    
    # Sort by urgency (IMMEDIATE first)
    urgency_order = {ProposalUrgency.IMMEDIATE: 0, ProposalUrgency.THIS_WEEK: 1, ProposalUrgency.MONITOR: 2}
    proposals.sort(key=lambda p: urgency_order.get(p.urgency, 3))
    
    return proposals


def generate_proposals_from_live_data(db_path: Optional[Path] = None) -> dict:
    """
    Run full intelligence pipeline and generate proposals.
    
    Convenience function that runs signal detection, pattern detection,
    and proposal generation in one call.
    """
    from lib.intelligence.signals import detect_all_signals
    from lib.intelligence.patterns import detect_all_patterns
    
    # Run detections
    signals = detect_all_signals(db_path, quick=True)  # Use quick mode for speed
    patterns = detect_all_patterns(db_path)
    
    # Generate proposals
    proposals = generate_proposals(signals, patterns, db_path)
    
    # Summarize
    by_urgency = {"immediate": 0, "this_week": 0, "monitor": 0}
    by_type = {}
    
    for prop in proposals:
        urgency = prop.urgency.value
        ptype = prop.type.value
        
        if urgency in by_urgency:
            by_urgency[urgency] += 1
        if ptype not in by_type:
            by_type[ptype] = 0
        by_type[ptype] += 1
    
    return {
        "generated_at": datetime.now().isoformat(),
        "total_proposals": len(proposals),
        "by_urgency": by_urgency,
        "by_type": by_type,
        "proposals": [p.to_dict() for p in proposals],
        "source_signals": signals.get("total_signals", 0),
        "source_patterns": patterns.get("total_detected", 0),
    }


# =============================================================================
# PRIORITY RANKING
# =============================================================================

@dataclass
class PriorityScore:
    """Priority score breakdown for a proposal."""
    proposal_id: str
    raw_score: float              # 0-100, higher = more urgent
    urgency_component: float      # Contribution from urgency classification
    impact_component: float       # Contribution from business impact
    recency_component: float      # Contribution from how new/escalating
    confidence_component: float   # Contribution from evidence quality
    rank: int = 0                 # Position in sorted list (1 = most urgent)
    
    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "raw_score": round(self.raw_score, 1),
            "urgency_component": round(self.urgency_component, 1),
            "impact_component": round(self.impact_component, 1),
            "recency_component": round(self.recency_component, 1),
            "confidence_component": round(self.confidence_component, 1),
            "rank": self.rank,
        }


# Default scoring weights
DEFAULT_WEIGHTS = {
    "urgency": 0.40,
    "impact": 0.30,
    "recency": 0.15,
    "confidence": 0.15,
}


def _score_urgency(proposal: Proposal) -> float:
    """
    Score 0-100 based on urgency classification + signal severity.
    
    IMMEDIATE = 100, THIS_WEEK = 60, MONITOR = 20.
    Bonus +20 if any CRITICAL signals. Bonus +10 if escalating trend.
    """
    base_scores = {
        ProposalUrgency.IMMEDIATE: 100,
        ProposalUrgency.THIS_WEEK: 60,
        ProposalUrgency.MONITOR: 20,
    }
    
    score = base_scores.get(proposal.urgency, 40)
    
    # Check for critical signals in evidence
    for ev in proposal.evidence:
        if ev.get("data", {}).get("severity") == "critical":
            score = min(100, score + 20)
            break
    
    # Bonus for escalating trend
    if proposal.trend == "escalating":
        score = min(100, score + 10)
    
    return score


def _score_impact(proposal: Proposal, db_path: Optional[Path] = None) -> float:
    """
    Score 0-100 based on business impact of the affected entity.
    
    For client proposals: based on client revenue share
    For resource proposals: based on person's assignment count
    For project proposals: based on project importance
    For portfolio proposals: always 100
    """
    entity_type = proposal.entity.get("type")
    
    # Portfolio proposals always high impact
    if entity_type == "portfolio" or proposal.type == ProposalType.PORTFOLIO_RISK:
        return 100
    
    # Try to get impact from scores
    composite = proposal.scores.get("composite")
    if composite is not None:
        # Lower health score = higher urgency
        # Score 0 health = 100 impact, Score 100 health = 0 impact
        return max(0, 100 - composite)
    
    # Default scores by type
    type_defaults = {
        ProposalType.CLIENT_RISK: 70,
        ProposalType.RESOURCE_RISK: 60,
        ProposalType.PROJECT_RISK: 50,
        ProposalType.FINANCIAL_ALERT: 80,
        ProposalType.OPPORTUNITY: 30,
    }
    
    return type_defaults.get(proposal.type, 50)


def _score_recency(proposal: Proposal) -> float:
    """
    Score 0-100 based on how new or dynamic this issue is.
    
    New (first detected today) = 100.
    Escalating = 80.
    Stable (unchanged for >7 days) = 30.
    Improving = 10.
    """
    trend_scores = {
        "new": 100,
        "escalating": 80,
        "stable": 30,
        "improving": 10,
    }
    
    return trend_scores.get(proposal.trend, 50)


def _score_confidence(proposal: Proposal) -> float:
    """
    Score 0-100 based on evidence quality.
    
    High confidence = 100.
    Medium = 60.
    Low = 30.
    """
    confidence_scores = {
        "high": 100,
        "medium": 60,
        "low": 30,
    }
    
    return confidence_scores.get(proposal.confidence, 50)


def compute_priority_score(
    proposal: Proposal,
    db_path: Optional[Path] = None,
    weights: dict = None
) -> PriorityScore:
    """
    Compute the priority score for a single proposal.
    """
    weights = weights or DEFAULT_WEIGHTS
    
    # Compute component scores
    urgency = _score_urgency(proposal)
    impact = _score_impact(proposal, db_path)
    recency = _score_recency(proposal)
    confidence = _score_confidence(proposal)
    
    # Compute weighted total
    raw_score = (
        weights.get("urgency", 0.4) * urgency +
        weights.get("impact", 0.3) * impact +
        weights.get("recency", 0.15) * recency +
        weights.get("confidence", 0.15) * confidence
    )
    
    return PriorityScore(
        proposal_id=proposal.id,
        raw_score=raw_score,
        urgency_component=urgency * weights.get("urgency", 0.4),
        impact_component=impact * weights.get("impact", 0.3),
        recency_component=recency * weights.get("recency", 0.15),
        confidence_component=confidence * weights.get("confidence", 0.15),
    )


def rank_proposals(
    proposals: list[Proposal],
    db_path: Optional[Path] = None,
    weights: dict = None
) -> list[tuple[Proposal, PriorityScore]]:
    """
    Score and rank all proposals.
    
    Returns list of (Proposal, PriorityScore) tuples sorted by priority score descending.
    Rank field is set (1 = most urgent).
    """
    scored = []
    
    for proposal in proposals:
        score = compute_priority_score(proposal, db_path, weights)
        scored.append((proposal, score))
    
    # Sort by raw_score descending
    scored.sort(key=lambda x: x[1].raw_score, reverse=True)
    
    # Assign ranks
    for i, (prop, score) in enumerate(scored):
        score.rank = i + 1
    
    return scored


def get_top_proposals(
    proposals: list[Proposal],
    n: int = 5,
    db_path: Optional[Path] = None,
    weights: dict = None
) -> list[tuple[Proposal, PriorityScore]]:
    """
    Return the top N proposals by priority.
    
    This is the '5am before a client meeting' view.
    """
    ranked = rank_proposals(proposals, db_path, weights)
    return ranked[:n]


def get_proposals_by_type(
    proposals: list[Proposal],
    proposal_type: ProposalType,
    db_path: Optional[Path] = None,
    weights: dict = None
) -> list[tuple[Proposal, PriorityScore]]:
    """
    Return proposals filtered by type, still ranked by priority.
    """
    filtered = [p for p in proposals if p.type == proposal_type]
    return rank_proposals(filtered, db_path, weights)


def get_proposals_for_entity(
    proposals: list[Proposal],
    entity_type: str,
    entity_id: str,
    db_path: Optional[Path] = None,
    weights: dict = None
) -> list[tuple[Proposal, PriorityScore]]:
    """
    Return all proposals involving a specific entity.
    """
    filtered = []
    for prop in proposals:
        # Check primary entity
        if prop.entity.get("type") == entity_type and prop.entity.get("id") == entity_id:
            filtered.append(prop)
            continue
        # Check related entities
        for related in prop.related_entities:
            if related.get("type") == entity_type and related.get("id") == entity_id:
                filtered.append(prop)
                break
    
    return rank_proposals(filtered, db_path, weights)


# =============================================================================
# DAILY BRIEFING
# =============================================================================

def generate_daily_briefing(
    proposals: list[Proposal],
    db_path: Optional[Path] = None
) -> dict:
    """
    Produce a structured daily briefing from ranked proposals.
    
    This is the single output Moh reads at the start of the day.
    """
    ranked = rank_proposals(proposals, db_path)
    
    # Categorize by urgency
    immediate = [(p, s) for p, s in ranked if p.urgency == ProposalUrgency.IMMEDIATE]
    this_week = [(p, s) for p, s in ranked if p.urgency == ProposalUrgency.THIS_WEEK]
    monitor = [(p, s) for p, s in ranked if p.urgency == ProposalUrgency.MONITOR]
    
    # Build critical items (top 3 IMMEDIATE with full evidence)
    critical_items = []
    for prop, score in immediate[:3]:
        critical_items.append({
            "headline": prop.headline,
            "entity": prop.entity,
            "evidence": prop.evidence[:5],  # Top 5 evidence items
            "implied_action": prop.implied_action,
            "priority_score": score.raw_score,
            "rank": score.rank,
        })
    
    # Build attention items (top 5 THIS_WEEK with headlines)
    attention_items = []
    for prop, score in this_week[:5]:
        attention_items.append({
            "headline": prop.headline,
            "entity": prop.entity,
            "implied_action": prop.implied_action,
            "priority_score": score.raw_score,
            "rank": score.rank,
        })
    
    # Watching items (MONITOR headlines only)
    watching = []
    for prop, score in monitor[:10]:
        watching.append({
            "headline": prop.headline,
            "entity_name": prop.entity.get("name"),
        })
    
    # Portfolio health assessment
    pattern_count = sum(1 for p in proposals if p.type == ProposalType.PORTFOLIO_RISK)
    
    # Determine overall trend
    escalating = sum(1 for p in proposals if p.trend == "escalating")
    improving = sum(1 for p in proposals if p.trend == "improving")
    
    if escalating > improving + 2:
        trend = "declining"
    elif improving > escalating + 2:
        trend = "improving"
    else:
        trend = "stable"
    
    # Simple overall score: 100 - (immediate * 10 + this_week * 3)
    overall_score = max(0, 100 - (len(immediate) * 10 + len(this_week) * 3))
    
    return {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_proposals": len(proposals),
            "immediate_count": len(immediate),
            "this_week_count": len(this_week),
            "monitor_count": len(monitor),
        },
        "critical_items": critical_items,
        "attention_items": attention_items,
        "watching": watching,
        "portfolio_health": {
            "overall_score": overall_score,
            "active_structural_patterns": pattern_count,
            "trend": trend,
        },
        "top_proposal": ranked[0][0].headline if ranked else None,
    }
