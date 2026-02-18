"""
Intelligence Engine for MOH TIME OS.

Single entry point that orchestrates scoring, signal detection,
pattern detection, and proposal generation into a complete
operational intelligence snapshot.

Usage:
    from lib.intelligence.engine import generate_intelligence_snapshot
    snapshot = generate_intelligence_snapshot()

    from lib.intelligence.engine import get_client_intelligence
    intel = get_client_intelligence(client_id="client-123")
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# ERROR TRACKING - Errors are tracked, not swallowed
# =============================================================================


@dataclass
class StageError:
    """Represents an error that occurred during pipeline execution."""

    stage: str
    component: str
    error_type: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "component": self.component,
            "error_type": self.error_type,
            "message": self.message,
            "timestamp": self.timestamp,
        }


@dataclass
class StageResult:
    """Result of a pipeline stage with explicit success/failure tracking."""

    success: bool
    data: dict
    errors: list[StageError] = field(default_factory=list)
    partial: bool = False  # True if some components succeeded, others failed

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "partial": self.partial,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
            "data": self.data,
        }


# =============================================================================
# STAGE RUNNERS - Errors tracked explicitly, never swallowed
# =============================================================================


def _run_scoring_stage(db_path: Path | None = None) -> StageResult:
    """
    Run scoring. Errors are tracked per-component, not swallowed.
    Returns StageResult with explicit success/failure and error details.
    """
    from lib.intelligence.scorecard import (
        score_all_clients,
        score_all_persons,
        score_all_projects,
        score_portfolio,
    )

    errors: list[StageError] = []
    data = {
        "clients": [],
        "projects": [],
        "persons": [],
        "portfolio": {},
    }

    # Score clients
    try:
        data["clients"] = score_all_clients(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for clients: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="scoring",
                component="clients",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Score projects
    try:
        data["projects"] = score_all_projects(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for projects: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="scoring",
                component="projects",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Score persons
    try:
        data["persons"] = score_all_persons(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for persons: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="scoring",
                component="persons",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Score portfolio
    try:
        data["portfolio"] = score_portfolio(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for portfolio: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="scoring",
                component="portfolio",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    return StageResult(
        success=len(errors) == 0,
        partial=0 < len(errors) < 4,
        data=data,
        errors=errors,
    )


def _run_signal_stage(db_path: Path | None = None) -> StageResult:
    """
    Run signal detection and state update. Errors tracked explicitly.
    """
    from lib.intelligence.signals import (
        detect_all_signals,
        get_signal_summary,
        update_signal_state,
    )

    errors: list[StageError] = []
    data = {
        "total_active": 0,
        "new": [],
        "ongoing": [],
        "escalated": [],
        "cleared": [],
        "by_severity": {"critical": [], "warning": [], "watch": []},
        "all_signals": [],
    }

    # Detect signals
    detected_signals = []
    try:
        detection = detect_all_signals(db_path, quick=True)
        detected_signals = detection.get("signals", [])
        data["all_signals"] = detected_signals

        # Organize by severity
        for sig in detected_signals:
            sev = sig.get("severity", "watch")
            if sev in data["by_severity"]:
                data["by_severity"][sev].append(sig)
    except Exception as e:
        logger.error(f"Signal detection failed: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="signals",
                component="detection",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Update state (only if detection succeeded)
    if detected_signals or not errors:
        try:
            state_update = update_signal_state(detected_signals, db_path)
            data["new"] = state_update.get("new_signals", [])
            data["ongoing"] = state_update.get("ongoing_signals", [])
            data["escalated"] = state_update.get("escalated_signals", [])
            data["cleared"] = state_update.get("cleared_signals", [])
        except Exception as e:
            logger.error(f"Signal state update failed: {e}", exc_info=True)
            errors.append(
                StageError(
                    stage="signals",
                    component="state_update",
                    error_type=type(e).__name__,
                    message=str(e),
                )
            )

    # Get summary
    try:
        summary = get_signal_summary(db_path)
        data["total_active"] = summary.get("total_active", 0)
    except Exception as e:
        logger.error(f"Signal summary failed: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="signals",
                component="summary",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    return StageResult(
        success=len(errors) == 0,
        partial=0 < len(errors) < 3,
        data=data,
        errors=errors,
    )


def _run_pattern_stage(
    db_path: Path | None = None, scores: StageResult = None, signals: StageResult = None
) -> StageResult:
    """
    Run pattern detection. Errors tracked explicitly.
    """
    from lib.intelligence.patterns import detect_all_patterns

    errors: list[StageError] = []
    data = {
        "total_detected": 0,
        "structural": [],
        "operational": [],
        "informational": [],
        "all_patterns": [],
    }

    try:
        detection = detect_all_patterns(db_path)
        patterns = detection.get("patterns", [])
        data["all_patterns"] = patterns
        data["total_detected"] = len(patterns)

        # Organize by severity
        for pat in patterns:
            sev = pat.get("severity", "informational")
            if sev == "structural":
                data["structural"].append(pat)
            elif sev == "operational":
                data["operational"].append(pat)
            else:
                data["informational"].append(pat)

    except Exception as e:
        logger.error(f"Pattern detection failed: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="patterns",
                component="detection",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    return StageResult(
        success=len(errors) == 0,
        partial=False,
        data=data,
        errors=errors,
    )


def _run_proposal_stage(
    db_path: Path | None = None,
    scores: StageResult = None,
    signals: StageResult = None,
    patterns: StageResult = None,
) -> StageResult:
    """
    Generate and rank proposals. Errors tracked explicitly.
    """
    from lib.intelligence.proposals import (
        generate_daily_briefing,
        generate_proposals,
        rank_proposals,
    )

    errors: list[StageError] = []
    data = {
        "total": 0,
        "ranked": [],
        "by_urgency": {"immediate": [], "this_week": [], "monitor": []},
        "briefing": {},
    }

    # Build input from prior stages
    signal_data = signals.data if signals else {}
    pattern_data = patterns.data if patterns else {}

    signal_input = {
        "signals": signal_data.get("all_signals", []),
        "total_signals": len(signal_data.get("all_signals", [])),
    }
    pattern_input = {
        "patterns": pattern_data.get("all_patterns", []),
        "total_detected": len(pattern_data.get("all_patterns", [])),
    }

    # Generate proposals
    proposals = []
    try:
        proposals = generate_proposals(signal_input, pattern_input, db_path)
        data["total"] = len(proposals)
    except Exception as e:
        logger.error(f"Proposal generation failed: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="proposals",
                component="generation",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Rank proposals (only if generation succeeded)
    if proposals:
        try:
            ranked = rank_proposals(proposals, db_path)
            data["ranked"] = [{**p.to_dict(), "priority_score": s.to_dict()} for p, s in ranked]
        except Exception as e:
            logger.error(f"Proposal ranking failed: {e}", exc_info=True)
            errors.append(
                StageError(
                    stage="proposals",
                    component="ranking",
                    error_type=type(e).__name__,
                    message=str(e),
                )
            )

        # Organize by urgency
        for prop in proposals:
            urgency = prop.urgency.value
            if urgency in data["by_urgency"]:
                data["by_urgency"][urgency].append(prop.to_dict())

        # Generate briefing
        try:
            data["briefing"] = generate_daily_briefing(proposals, db_path)
        except Exception as e:
            logger.error(f"Briefing generation failed: {e}", exc_info=True)
            errors.append(
                StageError(
                    stage="proposals",
                    component="briefing",
                    error_type=type(e).__name__,
                    message=str(e),
                )
            )

    return StageResult(
        success=len(errors) == 0,
        partial=0 < len(errors) < 3,
        data=data,
        errors=errors,
    )


# =============================================================================
# METADATA COMPUTATION
# =============================================================================


def _compute_data_completeness(scores: dict) -> float:
    """
    What fraction of scoring dimensions had sufficient data?
    Low completeness → intelligence is less reliable.
    """
    total_dimensions = 0
    complete_dimensions = 0

    # Check client scores
    clients = scores.get("clients", [])
    if isinstance(clients, list):
        for client in clients[:10]:  # Sample first 10
            if not isinstance(client, dict):
                continue
            dims = client.get("dimensions", {})
            if not isinstance(dims, dict):
                continue
            for dim_name, dim_data in dims.items():
                total_dimensions += 1
                if isinstance(dim_data, dict) and dim_data.get("score") is not None:
                    complete_dimensions += 1

    if total_dimensions == 0:
        return 0.0

    return complete_dimensions / total_dimensions


def _count_entities(scores: dict) -> dict:
    """Count entities scored."""
    counts = {"clients": 0, "projects": 0, "persons": 0}

    clients = scores.get("clients", [])
    if isinstance(clients, list):
        counts["clients"] = len(clients)

    projects = scores.get("projects", [])
    if isinstance(projects, list):
        counts["projects"] = len(projects)

    persons = scores.get("persons", [])
    if isinstance(persons, list):
        counts["persons"] = len(persons)

    return counts


# =============================================================================
# MAIN PIPELINE
# =============================================================================


def generate_intelligence_snapshot(db_path: Path | None = None) -> dict:
    """
    Run the full intelligence pipeline.

    Pipeline:
    1. Score all entities (clients, projects, persons, portfolio)
    2. Detect all signals against current data
    3. Update signal state (new, ongoing, escalated, cleared)
    4. Detect all patterns
    5. Generate proposals from scores + signals + patterns
    6. Rank proposals by priority
    7. Assemble daily briefing
    8. Return complete snapshot WITH ERROR TRACKING

    Errors are never swallowed. The response includes:
    - pipeline_success: True only if ALL stages succeeded
    - pipeline_errors: List of all errors from all stages
    - Each stage has its own success/partial/error fields
    """
    start_time = time.time()
    all_errors: list[StageError] = []

    # Stage 1: Scoring
    scores = _run_scoring_stage(db_path)
    all_errors.extend(scores.errors)

    # Stage 2: Signal detection
    signals = _run_signal_stage(db_path)
    all_errors.extend(signals.errors)

    # Stage 3: Pattern detection
    patterns = _run_pattern_stage(db_path, scores, signals)
    all_errors.extend(patterns.errors)

    # Stage 4: Proposal generation
    proposals = _run_proposal_stage(db_path, scores, signals, patterns)
    all_errors.extend(proposals.errors)

    # Compute metadata
    end_time = time.time()
    generation_time = end_time - start_time

    # Pipeline health
    pipeline_success = len(all_errors) == 0
    stages_failed = sum(
        [
            not scores.success,
            not signals.success,
            not patterns.success,
            not proposals.success,
        ]
    )

    return {
        "generated_at": datetime.now().isoformat(),
        "generation_time_seconds": round(generation_time, 2),
        # EXPLICIT PIPELINE HEALTH - Never hidden
        "pipeline_success": pipeline_success,
        "pipeline_partial": stages_failed > 0 and stages_failed < 4,
        "pipeline_errors": [e.to_dict() for e in all_errors],
        "stages_failed": stages_failed,
        "scores": {
            "success": scores.success,
            "partial": scores.partial,
            "errors": [e.to_dict() for e in scores.errors],
            **scores.data,
        },
        "signals": {
            "success": signals.success,
            "partial": signals.partial,
            "errors": [e.to_dict() for e in signals.errors],
            "total_active": signals.data.get("total_active", 0),
            "new": signals.data.get("new", []),
            "ongoing": signals.data.get("ongoing", []),
            "escalated": signals.data.get("escalated", []),
            "cleared": signals.data.get("cleared", []),
            "by_severity": signals.data.get("by_severity", {}),
        },
        "patterns": {
            "success": patterns.success,
            "partial": patterns.partial,
            "errors": [e.to_dict() for e in patterns.errors],
            "total_detected": patterns.data.get("total_detected", 0),
            "structural": patterns.data.get("structural", []),
            "operational": patterns.data.get("operational", []),
            "informational": patterns.data.get("informational", []),
        },
        "proposals": {
            "success": proposals.success,
            "partial": proposals.partial,
            "errors": [e.to_dict() for e in proposals.errors],
            "total": proposals.data.get("total", 0),
            "ranked": proposals.data.get("ranked", []),
            "by_urgency": proposals.data.get("by_urgency", {}),
        },
        "briefing": proposals.data.get("briefing", {}),
        "meta": {
            "entities_scored": _count_entities(scores.data),
            "signals_evaluated": len(signals.data.get("all_signals", [])),
            "patterns_evaluated": patterns.data.get("total_detected", 0),
            "data_completeness": _compute_data_completeness(scores.data),
        },
    }


# =============================================================================
# TARGETED INTELLIGENCE FUNCTIONS
# =============================================================================


def get_client_intelligence(client_id: str, db_path: Path | None = None) -> dict:
    """
    Everything the system knows about one client.
    Errors are tracked explicitly, not swallowed.
    """
    from lib.intelligence.scorecard import score_client
    from lib.intelligence.signals import (
        get_active_signals,
        get_signal_history,
    )
    from lib.query_engine import QueryEngine

    engine = QueryEngine(db_path) if db_path else QueryEngine()
    errors: list[StageError] = []

    result = {
        "client_id": client_id,
        "generated_at": datetime.now().isoformat(),
        "success": True,
        "errors": [],
        "scorecard": {},
        "active_signals": [],
        "signal_history": [],
        "trajectory": {},
        "proposals": [],
    }

    # Get scorecard
    try:
        result["scorecard"] = score_client(client_id, db_path)
    except Exception as e:
        logger.error(f"Failed to score client {client_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="client_intelligence",
                component="scorecard",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Get active signals
    try:
        result["active_signals"] = get_active_signals(
            entity_type="client", entity_id=client_id, db_path=db_path
        )
    except Exception as e:
        logger.error(f"Failed to get signals for client {client_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="client_intelligence",
                component="active_signals",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Get signal history
    try:
        result["signal_history"] = get_signal_history(
            entity_type="client", entity_id=client_id, db_path=db_path
        )
    except Exception as e:
        logger.error(f"Failed to get signal history for client {client_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="client_intelligence",
                component="signal_history",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Get trajectory
    try:
        result["trajectory"] = engine.client_trajectory(client_id)
    except Exception as e:
        logger.error(f"Failed to get trajectory for client {client_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="client_intelligence",
                component="trajectory",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    result["success"] = len(errors) == 0
    result["errors"] = [e.to_dict() for e in errors]
    return result


def get_person_intelligence(person_id: str, db_path: Path | None = None) -> dict:
    """
    Everything about one person. Errors tracked explicitly.
    """
    from lib.intelligence.scorecard import score_person
    from lib.intelligence.signals import get_active_signals, get_signal_history
    from lib.query_engine import QueryEngine

    engine = QueryEngine(db_path) if db_path else QueryEngine()
    errors: list[StageError] = []

    result = {
        "person_id": person_id,
        "generated_at": datetime.now().isoformat(),
        "success": True,
        "errors": [],
        "scorecard": {},
        "active_signals": [],
        "signal_history": [],
        "profile": {},
    }

    # Get scorecard
    try:
        result["scorecard"] = score_person(person_id, db_path)
    except Exception as e:
        logger.error(f"Failed to score person {person_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="person_intelligence",
                component="scorecard",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Get active signals
    try:
        result["active_signals"] = get_active_signals(
            entity_type="person", entity_id=person_id, db_path=db_path
        )
    except Exception as e:
        logger.error(f"Failed to get signals for person {person_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="person_intelligence",
                component="active_signals",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Get signal history
    try:
        result["signal_history"] = get_signal_history(
            entity_type="person", entity_id=person_id, db_path=db_path
        )
    except Exception as e:
        logger.error(f"Failed to get signal history for person {person_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="person_intelligence",
                component="signal_history",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Get profile
    try:
        result["profile"] = engine.person_operational_profile(person_id)
    except Exception as e:
        logger.error(f"Failed to get profile for person {person_id}: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="person_intelligence",
                component="profile",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    result["success"] = len(errors) == 0
    result["errors"] = [e.to_dict() for e in errors]
    return result


def get_portfolio_intelligence(db_path: Path | None = None) -> dict:
    """
    Portfolio-level view. Errors tracked explicitly.
    """
    from lib.intelligence.patterns import detect_all_patterns
    from lib.intelligence.proposals import (
        generate_proposals,
        rank_proposals,
    )
    from lib.intelligence.scorecard import score_portfolio
    from lib.intelligence.signals import detect_all_signals, get_signal_summary

    errors: list[StageError] = []

    result = {
        "generated_at": datetime.now().isoformat(),
        "success": True,
        "errors": [],
        "portfolio_score": {},
        "signal_summary": {},
        "structural_patterns": [],
        "top_proposals": [],
    }

    # Portfolio score
    try:
        result["portfolio_score"] = score_portfolio(db_path)
    except Exception as e:
        logger.error(f"Failed to score portfolio: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="portfolio_intelligence",
                component="portfolio_score",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Signal summary
    try:
        result["signal_summary"] = get_signal_summary(db_path)
    except Exception as e:
        logger.error(f"Failed to get signal summary: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="portfolio_intelligence",
                component="signal_summary",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Structural patterns only
    try:
        patterns = detect_all_patterns(db_path)
        result["structural_patterns"] = [
            p for p in patterns.get("patterns", []) if p.get("severity") == "structural"
        ]
    except Exception as e:
        logger.error(f"Failed to detect patterns: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="portfolio_intelligence",
                component="patterns",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    # Top 5 proposals
    try:
        signals = detect_all_signals(db_path, quick=True)
        patterns = detect_all_patterns(db_path)
        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        proposals = generate_proposals(signal_input, pattern_input, db_path)
        ranked = rank_proposals(proposals, db_path)
        result["top_proposals"] = [
            {"headline": p.headline, "urgency": p.urgency.value, "score": s.raw_score}
            for p, s in ranked[:5]
        ]
    except Exception as e:
        logger.error(f"Failed to generate proposals: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="portfolio_intelligence",
                component="proposals",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    result["success"] = len(errors) == 0
    result["errors"] = [e.to_dict() for e in errors]
    return result


def get_critical_items(db_path: Path | None = None) -> dict:
    """
    Just the IMMEDIATE urgency proposals. Errors tracked explicitly.
    Returns dict with success flag and items list, not bare list.
    """
    from lib.intelligence.patterns import detect_all_patterns
    from lib.intelligence.proposals import (
        ProposalUrgency,
        generate_proposals,
        rank_proposals,
    )
    from lib.intelligence.signals import detect_all_signals

    errors: list[StageError] = []
    result = {
        "success": True,
        "errors": [],
        "items": [],
        "generated_at": datetime.now().isoformat(),
    }

    try:
        # Run detection
        signals = detect_all_signals(db_path, quick=True)
        patterns = detect_all_patterns(db_path)

        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        # Generate and rank
        proposals = generate_proposals(signal_input, pattern_input, db_path)
        ranked = rank_proposals(proposals, db_path)

        # Filter to IMMEDIATE only
        result["items"] = [
            {
                "headline": p.headline,
                "entity": p.entity,
                "implied_action": p.implied_action,
                "evidence_count": len(p.evidence),
                "priority_score": s.raw_score,
            }
            for p, s in ranked
            if p.urgency == ProposalUrgency.IMMEDIATE
        ]

    except Exception as e:
        logger.error(f"Failed to get critical items: {e}", exc_info=True)
        errors.append(
            StageError(
                stage="critical_items",
                component="pipeline",
                error_type=type(e).__name__,
                message=str(e),
            )
        )

    result["success"] = len(errors) == 0
    result["errors"] = [e.to_dict() for e in errors]
    return result
