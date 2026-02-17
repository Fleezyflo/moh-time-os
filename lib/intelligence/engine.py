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
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# STAGE RUNNERS (with error isolation)
# =============================================================================


def _run_scoring_stage(db_path: Path | None = None) -> dict:
    """
    Run scoring. If any entity type fails, log the error and return partial results.
    Never crash the pipeline for a scoring failure.
    """
    from lib.intelligence.scorecard import (
        score_all_clients,
        score_all_persons,
        score_all_projects,
        score_portfolio,
    )

    results = {
        "clients": [],
        "projects": [],
        "persons": [],
        "portfolio": {},
    }

    # Score clients
    try:
        results["clients"] = score_all_clients(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for clients: {e}")
        results["clients"] = {"error": str(e)}

    # Score projects
    try:
        results["projects"] = score_all_projects(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for projects: {e}")
        results["projects"] = {"error": str(e)}

    # Score persons
    try:
        results["persons"] = score_all_persons(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for persons: {e}")
        results["persons"] = {"error": str(e)}

    # Score portfolio
    try:
        results["portfolio"] = score_portfolio(db_path)
    except Exception as e:
        logger.error(f"Scoring stage failed for portfolio: {e}")
        results["portfolio"] = {"error": str(e)}

    return results


def _run_signal_stage(db_path: Path | None = None) -> dict:
    """
    Run signal detection and state update. Isolated from scoring failures.
    """
    from lib.intelligence.signals import (
        detect_all_signals,
        get_active_signals,
        get_signal_summary,
        update_signal_state,
    )

    results = {
        "total_active": 0,
        "new": [],
        "ongoing": [],
        "escalated": [],
        "cleared": [],
        "by_severity": {"critical": [], "warning": [], "watch": []},
        "all_signals": [],
    }

    try:
        # Detect signals (quick mode for performance)
        detection = detect_all_signals(db_path, quick=True)
        detected_signals = detection.get("signals", [])
        results["all_signals"] = detected_signals

        # Update state
        state_update = update_signal_state(detected_signals, db_path)
        results["new"] = state_update.get("new_signals", [])
        results["ongoing"] = state_update.get("ongoing_signals", [])
        results["escalated"] = state_update.get("escalated_signals", [])
        results["cleared"] = state_update.get("cleared_signals", [])

        # Get summary
        summary = get_signal_summary(db_path)
        results["total_active"] = summary.get("total_active", 0)

        # Organize by severity
        for sig in detected_signals:
            sev = sig.get("severity", "watch")
            if sev in results["by_severity"]:
                results["by_severity"][sev].append(sig)

    except Exception as e:
        logger.error(f"Signal stage failed: {e}")
        results["error"] = str(e)

    return results


def _run_pattern_stage(
    db_path: Path | None = None, scores: dict = None, signals: dict = None
) -> dict:
    """
    Run pattern detection. Uses scores and signals as input.
    """
    from lib.intelligence.patterns import detect_all_patterns

    results = {
        "total_detected": 0,
        "structural": [],
        "operational": [],
        "informational": [],
        "all_patterns": [],
    }

    try:
        detection = detect_all_patterns(db_path)
        patterns = detection.get("patterns", [])
        results["all_patterns"] = patterns
        results["total_detected"] = len(patterns)

        # Organize by severity
        for pat in patterns:
            sev = pat.get("severity", "informational")
            if sev == "structural":
                results["structural"].append(pat)
            elif sev == "operational":
                results["operational"].append(pat)
            else:
                results["informational"].append(pat)

    except Exception as e:
        logger.error(f"Pattern stage failed: {e}")
        results["error"] = str(e)

    return results


def _run_proposal_stage(
    db_path: Path | None = None, scores: dict = None, signals: dict = None, patterns: dict = None
) -> dict:
    """
    Generate and rank proposals. Uses all prior stages as input.
    """
    from lib.intelligence.proposals import (
        Proposal,
        ProposalType,
        ProposalUrgency,
        generate_daily_briefing,
        generate_proposals,
        rank_proposals,
    )

    results = {
        "total": 0,
        "ranked": [],
        "by_urgency": {"immediate": [], "this_week": [], "monitor": []},
        "briefing": {},
    }

    try:
        # Build input for proposal generation
        signal_input = {
            "signals": signals.get("all_signals", []) if signals else [],
            "total_signals": len(signals.get("all_signals", [])) if signals else 0,
        }
        pattern_input = {
            "patterns": patterns.get("all_patterns", []) if patterns else [],
            "total_detected": len(patterns.get("all_patterns", [])) if patterns else 0,
        }

        # Generate proposals
        proposals = generate_proposals(signal_input, pattern_input, db_path)
        results["total"] = len(proposals)

        # Rank proposals
        ranked = rank_proposals(proposals, db_path)
        results["ranked"] = [{**p.to_dict(), "priority_score": s.to_dict()} for p, s in ranked]

        # Organize by urgency
        for prop in proposals:
            urgency = prop.urgency.value
            if urgency in results["by_urgency"]:
                results["by_urgency"][urgency].append(prop.to_dict())

        # Generate briefing
        results["briefing"] = generate_daily_briefing(proposals, db_path)

    except Exception as e:
        logger.error(f"Proposal stage failed: {e}")
        results["error"] = str(e)

    return results


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
            for _dim_name, dim_data in dims.items():
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
    8. Return complete snapshot
    """
    start_time = time.time()

    # Stage 1: Scoring
    scores = _run_scoring_stage(db_path)

    # Stage 2: Signal detection
    signals = _run_signal_stage(db_path)

    # Stage 3: Pattern detection
    patterns = _run_pattern_stage(db_path, scores, signals)

    # Stage 4: Proposal generation
    proposals = _run_proposal_stage(db_path, scores, signals, patterns)

    # Compute metadata
    end_time = time.time()
    generation_time = end_time - start_time

    return {
        "generated_at": datetime.now().isoformat(),
        "generation_time_seconds": round(generation_time, 2),
        "scores": scores,
        "signals": {
            "total_active": signals.get("total_active", 0),
            "new": signals.get("new", []),
            "ongoing": signals.get("ongoing", []),
            "escalated": signals.get("escalated", []),
            "cleared": signals.get("cleared", []),
            "by_severity": signals.get("by_severity", {}),
        },
        "patterns": {
            "total_detected": patterns.get("total_detected", 0),
            "structural": patterns.get("structural", []),
            "operational": patterns.get("operational", []),
            "informational": patterns.get("informational", []),
        },
        "proposals": {
            "total": proposals.get("total", 0),
            "ranked": proposals.get("ranked", []),
            "by_urgency": proposals.get("by_urgency", {}),
        },
        "briefing": proposals.get("briefing", {}),
        "meta": {
            "entities_scored": _count_entities(scores),
            "signals_evaluated": len(signals.get("all_signals", [])),
            "patterns_evaluated": patterns.get("total_detected", 0),
            "data_completeness": _compute_data_completeness(scores),
        },
    }


# =============================================================================
# TARGETED INTELLIGENCE FUNCTIONS
# =============================================================================


def get_client_intelligence(client_id: str, db_path: Path | None = None) -> dict:
    """
    Everything the system knows about one client:
    - Current scorecard
    - Active signals
    - Patterns involving this client
    - Open proposals
    - Historical signal timeline
    - Score trajectory

    This is the 'tell me everything about Client X' function.
    """
    from lib.intelligence.scorecard import score_client
    from lib.intelligence.signals import (
        detect_signals_for_entity,
        get_active_signals,
        get_signal_history,
    )
    from lib.query_engine import QueryEngine

    engine = QueryEngine(db_path) if db_path else QueryEngine()

    result = {
        "client_id": client_id,
        "generated_at": datetime.now().isoformat(),
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
        logger.warning(f"Failed to score client {client_id}: {e}")
        result["scorecard"] = {"error": str(e)}

    # Get active signals
    try:
        result["active_signals"] = get_active_signals(
            entity_type="client", entity_id=client_id, db_path=db_path
        )
    except Exception as e:
        logger.warning(f"Failed to get signals for client {client_id}: {e}")

    # Get signal history
    try:
        result["signal_history"] = get_signal_history(
            entity_type="client", entity_id=client_id, db_path=db_path
        )
    except Exception as e:
        logger.warning(f"Failed to get signal history for client {client_id}: {e}")

    # Get trajectory
    try:
        result["trajectory"] = engine.client_trajectory(client_id)
    except Exception as e:
        logger.warning(f"Failed to get trajectory for client {client_id}: {e}")

    return result


def get_person_intelligence(person_id: str, db_path: Path | None = None) -> dict:
    """
    Everything about one person: load, signals, blast radius, trajectory.
    """
    from lib.intelligence.scorecard import score_person
    from lib.intelligence.signals import get_active_signals, get_signal_history
    from lib.query_engine import QueryEngine

    engine = QueryEngine(db_path) if db_path else QueryEngine()

    result = {
        "person_id": person_id,
        "generated_at": datetime.now().isoformat(),
        "scorecard": {},
        "active_signals": [],
        "signal_history": [],
        "profile": {},
    }

    # Get scorecard
    try:
        result["scorecard"] = score_person(person_id, db_path)
    except Exception as e:
        logger.warning(f"Failed to score person {person_id}: {e}")
        result["scorecard"] = {"error": str(e)}

    # Get active signals
    try:
        result["active_signals"] = get_active_signals(
            entity_type="person", entity_id=person_id, db_path=db_path
        )
    except Exception as e:
        logger.warning(f"Failed to get signals for person {person_id}: {e}")

    # Get signal history
    try:
        result["signal_history"] = get_signal_history(
            entity_type="person", entity_id=person_id, db_path=db_path
        )
    except Exception as e:
        logger.warning(f"Failed to get signal history for person {person_id}: {e}")

    # Get profile
    try:
        result["profile"] = engine.person_operational_profile(person_id)
    except Exception as e:
        logger.warning(f"Failed to get profile for person {person_id}: {e}")

    return result


def get_portfolio_intelligence(db_path: Path | None = None) -> dict:
    """
    Portfolio-level view: aggregate health, concentration metrics,
    structural patterns, top proposals. Lighter than full snapshot.
    """
    from lib.intelligence.patterns import detect_all_patterns
    from lib.intelligence.proposals import (
        ProposalUrgency,
        generate_proposals,
        rank_proposals,
    )
    from lib.intelligence.scorecard import score_portfolio
    from lib.intelligence.signals import detect_all_signals, get_signal_summary

    result = {
        "generated_at": datetime.now().isoformat(),
        "portfolio_score": {},
        "signal_summary": {},
        "structural_patterns": [],
        "top_proposals": [],
    }

    # Portfolio score
    try:
        result["portfolio_score"] = score_portfolio(db_path)
    except Exception as e:
        logger.warning(f"Failed to score portfolio: {e}")
        result["portfolio_score"] = {"error": str(e)}

    # Signal summary
    try:
        result["signal_summary"] = get_signal_summary(db_path)
    except Exception as e:
        logger.warning(f"Failed to get signal summary: {e}")

    # Structural patterns only
    try:
        patterns = detect_all_patterns(db_path)
        result["structural_patterns"] = [
            p for p in patterns.get("patterns", []) if p.get("severity") == "structural"
        ]
    except Exception as e:
        logger.warning(f"Failed to detect patterns: {e}")

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
        logger.warning(f"Failed to generate proposals: {e}")

    return result


def get_critical_items(db_path: Path | None = None) -> list[dict]:
    """
    Just the IMMEDIATE urgency proposals. The '30-second scan' view.
    Runs full pipeline internally but only returns critical items.
    """
    from lib.intelligence.patterns import detect_all_patterns
    from lib.intelligence.proposals import (
        ProposalUrgency,
        generate_proposals,
        rank_proposals,
    )
    from lib.intelligence.signals import detect_all_signals

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
        critical = [
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

        return critical

    except Exception as e:
        logger.error(f"Failed to get critical items: {e}")
        return []
