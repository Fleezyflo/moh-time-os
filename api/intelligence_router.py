"""
Intelligence API Router — Cross-Entity Query Endpoints

This router exposes the query engine functions via REST API.
All endpoints are read-only GET requests.

Usage in server.py:
    from api.intelligence_router import intelligence_router
    app.include_router(intelligence_router, prefix="/api/v2/intelligence")
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from lib.query_engine import QueryEngine

logger = logging.getLogger(__name__)

# Router
intelligence_router = APIRouter(tags=["Intelligence"])

# Singleton query engine
_engine: Optional[QueryEngine] = None


def get_engine() -> QueryEngine:
    """Get or create query engine instance."""
    global _engine
    if _engine is None:
        _engine = QueryEngine()
    return _engine


def _wrap_response(data: dict | list, params: dict | None = None) -> dict:
    """Wrap response in standard envelope."""
    return {
        "status": "ok",
        "data": data,
        "computed_at": datetime.now().isoformat(),
        "params": params or {},
    }


def _error_response(message: str, code: str = "ERROR") -> dict:
    """Create error response."""
    return {
        "status": "error",
        "error": message,
        "error_code": code,
    }


# =============================================================================
# PORTFOLIO ENDPOINTS
# =============================================================================


@intelligence_router.get("/portfolio/overview")
def portfolio_overview(
    order_by: str = Query("total_tasks", description="Field to sort by"),
    desc: bool = Query(True, description="Sort descending"),
):
    """
    Get portfolio overview with all clients and their operational metrics.

    Returns clients with project_count, total_tasks, active_tasks,
    invoice_count, total_invoiced, total_outstanding, etc.
    """
    try:
        engine = get_engine()
        data = engine.client_portfolio_overview(order_by=order_by, desc=desc)
        return _wrap_response(data, {"order_by": order_by, "desc": desc})
    except Exception as e:
        logger.exception("portfolio_overview failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/portfolio/risks")
def portfolio_risks(
    overdue_threshold: int = Query(5, description="Min overdue tasks to flag project"),
    aging_threshold: int = Query(30, description="Days overdue to flag invoice"),
):
    """
    Get structural risks across the portfolio.

    Returns risks categorized as OVERDUE_PROJECT, OVERLOADED_PERSON,
    AGING_INVOICE with severity (HIGH/MEDIUM/LOW) and evidence.
    """
    try:
        engine = get_engine()
        data = engine.portfolio_structural_risks(
            overdue_threshold=overdue_threshold,
            aging_threshold=aging_threshold,
        )
        return _wrap_response(
            data,
            {"overdue_threshold": overdue_threshold, "aging_threshold": aging_threshold},
        )
    except Exception as e:
        logger.exception("portfolio_risks failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/portfolio/trajectory")
def portfolio_trajectory(
    window_days: int = Query(30, description="Size of each time window in days"),
    num_windows: int = Query(6, description="Number of windows to analyze"),
    min_activity: int = Query(1, description="Minimum activity to include client"),
):
    """
    Get trajectory analysis for all clients.

    Shows direction of travel (increasing/stable/declining) for each client
    based on rolling time windows.
    """
    try:
        engine = get_engine()
        data = engine.portfolio_trajectory(
            window_size_days=window_days,
            num_windows=num_windows,
            min_activity=min_activity,
        )
        return _wrap_response(
            data,
            {
                "window_days": window_days,
                "num_windows": num_windows,
                "min_activity": min_activity,
            },
        )
    except Exception as e:
        logger.exception("portfolio_trajectory failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CLIENT ENDPOINTS
# =============================================================================


@intelligence_router.get("/clients/{client_id}/profile")
def client_profile(client_id: str):
    """
    Get deep operational profile for a client.

    Returns client info, financial metrics, projects list,
    people involved, and recent invoices.
    """
    try:
        engine = get_engine()
        data = engine.client_deep_profile(client_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Client not found")
        return _wrap_response(data, {"client_id": client_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("client_profile failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/clients/{client_id}/tasks")
def client_tasks(client_id: str):
    """
    Get task summary for a client.

    Returns total_tasks, active_tasks, completed_tasks, overdue_tasks,
    completion_rate, tasks_by_status, tasks_by_assignee.
    """
    try:
        engine = get_engine()
        data = engine.client_task_summary(client_id)
        return _wrap_response(data, {"client_id": client_id})
    except Exception as e:
        logger.exception("client_tasks failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/clients/{client_id}/communication")
def client_communication(
    client_id: str,
    since: Optional[str] = Query(None, description="Start date (ISO format)"),
    until: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """
    Get communication metrics for a client.

    Returns total_communications, by_type breakdown, and recent messages.
    """
    try:
        engine = get_engine()
        data = engine.client_communication_summary(client_id)
        return _wrap_response(data, {"client_id": client_id, "since": since, "until": until})
    except Exception as e:
        logger.exception("client_communication failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/clients/{client_id}/trajectory")
def client_trajectory(
    client_id: str,
    window_days: int = Query(30, description="Size of each time window in days"),
    num_windows: int = Query(6, description="Number of windows to analyze"),
):
    """
    Get trajectory analysis for a client.

    Shows metrics over rolling time windows with trend analysis
    (increasing/stable/declining) for each metric.
    """
    try:
        engine = get_engine()
        data = engine.client_trajectory(
            client_id,
            window_size_days=window_days,
            num_windows=num_windows,
        )
        return _wrap_response(
            data,
            {"client_id": client_id, "window_days": window_days, "num_windows": num_windows},
        )
    except Exception as e:
        logger.exception("client_trajectory failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/clients/{client_id}/compare")
def client_compare(
    client_id: str,
    period_a_start: str = Query(..., description="Period A start date (ISO)"),
    period_a_end: str = Query(..., description="Period A end date (ISO)"),
    period_b_start: str = Query(..., description="Period B start date (ISO)"),
    period_b_end: str = Query(..., description="Period B end date (ISO)"),
):
    """
    Compare a client's metrics between two time periods.

    Returns metrics for each period, deltas, and percentage changes.
    """
    try:
        engine = get_engine()
        data = engine.compare_client_periods(
            client_id,
            (period_a_start, period_a_end),
            (period_b_start, period_b_end),
        )
        return _wrap_response(
            data,
            {
                "client_id": client_id,
                "period_a": {"start": period_a_start, "end": period_a_end},
                "period_b": {"start": period_b_start, "end": period_b_end},
            },
        )
    except Exception as e:
        logger.exception("client_compare failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/clients/compare")
def clients_compare(
    period_a_start: str = Query(..., description="Period A start date (ISO)"),
    period_a_end: str = Query(..., description="Period A end date (ISO)"),
    period_b_start: str = Query(..., description="Period B start date (ISO)"),
    period_b_end: str = Query(..., description="Period B end date (ISO)"),
):
    """
    Compare all clients between two time periods.

    Returns list of clients with their metrics in each period and deltas.
    """
    try:
        engine = get_engine()
        data = engine.compare_portfolio_periods(
            (period_a_start, period_a_end),
            (period_b_start, period_b_end),
        )
        return _wrap_response(
            data,
            {
                "period_a": {"start": period_a_start, "end": period_a_end},
                "period_b": {"start": period_b_start, "end": period_b_end},
            },
        )
    except Exception as e:
        logger.exception("clients_compare failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TEAM ENDPOINTS
# =============================================================================


@intelligence_router.get("/team/distribution")
def team_distribution():
    """
    Get team load distribution.

    Returns list of people with assigned_tasks, active_tasks,
    project_count, and computed load_score (0-100).
    """
    try:
        engine = get_engine()
        data = engine.resource_load_distribution()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("team_distribution failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/team/capacity")
def team_capacity():
    """
    Get team capacity overview.

    Returns total_people, total_active_tasks, avg_tasks_per_person,
    people_overloaded, people_available, and full distribution.
    """
    try:
        engine = get_engine()
        data = engine.team_capacity_overview()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("team_capacity failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/team/{person_id}/profile")
def team_person_profile(person_id: str):
    """
    Get operational profile for a person.

    Returns person info, load metrics, projects they're on,
    and clients they work with.
    """
    try:
        engine = get_engine()
        data = engine.person_operational_profile(person_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Person not found")
        return _wrap_response(data, {"person_id": person_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("team_person_profile failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/team/{person_id}/trajectory")
def team_person_trajectory(
    person_id: str,
    window_days: int = Query(30, description="Size of each time window in days"),
    num_windows: int = Query(6, description="Number of windows to analyze"),
):
    """
    Get trajectory analysis for a person.

    Shows load and activity over rolling time windows with trend analysis.
    """
    try:
        engine = get_engine()
        data = engine.person_trajectory(
            person_id,
            window_size_days=window_days,
            num_windows=num_windows,
        )
        return _wrap_response(
            data,
            {"person_id": person_id, "window_days": window_days, "num_windows": num_windows},
        )
    except Exception as e:
        logger.exception("team_person_trajectory failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PROJECT ENDPOINTS
# =============================================================================


@intelligence_router.get("/projects/{project_id}/state")
def project_state(project_id: str):
    """
    Get operational state of a project.

    Returns project info, task metrics (total, open, completed, overdue),
    completion_rate_pct, and assigned people count.
    """
    try:
        engine = get_engine()
        data = engine.project_operational_state(project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return _wrap_response(data, {"project_id": project_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("project_state failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/projects/health")
def projects_health(
    min_tasks: int = Query(1, description="Minimum tasks to include project"),
):
    """
    Get all projects ranked by health score.

    health_score = completion_rate - (overdue_ratio * 50)
    Higher is healthier.
    """
    try:
        engine = get_engine()
        data = engine.projects_by_health(min_tasks=min_tasks)
        return _wrap_response(data, {"min_tasks": min_tasks})
    except Exception as e:
        logger.exception("projects_health failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FINANCIAL ENDPOINTS
# =============================================================================


@intelligence_router.get("/financial/aging")
def financial_aging():
    """
    Get invoice aging report.

    Returns total_outstanding, by_bucket breakdown (current, 30, 60, 90+),
    and list of clients with overdue amounts.
    """
    try:
        engine = get_engine()
        data = engine.invoice_aging_report()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("financial_aging failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# INTELLIGENCE LAYER ENDPOINTS (Scoring, Signals, Patterns, Proposals)
# =============================================================================


@intelligence_router.get("/snapshot")
def intelligence_snapshot():
    """
    Get complete intelligence snapshot.

    Runs the full intelligence pipeline:
    - Scores all entities
    - Detects all signals
    - Detects all patterns
    - Generates and ranks proposals
    - Produces daily briefing

    This is a heavy endpoint (~45s). Use targeted endpoints for faster responses.
    """
    try:
        from lib.intelligence import generate_intelligence_snapshot
        data = generate_intelligence_snapshot()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("intelligence_snapshot failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/critical")
def critical_items():
    """
    Get critical items only (IMMEDIATE urgency proposals).

    The "30-second scan" view — what needs attention right now.
    Faster than full snapshot.
    """
    try:
        from lib.intelligence import get_critical_items
        data = get_critical_items()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("critical_items failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/briefing")
def daily_briefing():
    """
    Get daily briefing summary.

    Returns structured briefing with:
    - Summary counts (immediate, this_week, monitor)
    - Critical items list
    - Attention items list
    - Watching items list
    - Portfolio health
    - Top proposal headline
    """
    try:
        from lib.intelligence import (
            detect_all_signals,
            detect_all_patterns,
            generate_proposals,
            generate_daily_briefing,
        )

        signals = detect_all_signals(quick=True)
        patterns = detect_all_patterns()

        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        proposals = generate_proposals(signal_input, pattern_input)
        briefing = generate_daily_briefing(proposals)

        return _wrap_response(briefing)
    except Exception as e:
        logger.exception("daily_briefing failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SIGNALS ENDPOINTS
# =============================================================================


@intelligence_router.get("/signals")
def list_signals(
    quick: bool = Query(True, description="Use quick mode (sample portfolio)"),
):
    """
    Detect all active signals.

    Returns signals with severity, entity, evidence, and implied action.
    """
    try:
        from lib.intelligence import detect_all_signals
        data = detect_all_signals(quick=quick)
        return _wrap_response(data, {"quick": quick})
    except Exception as e:
        logger.exception("list_signals failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/signals/summary")
def signals_summary():
    """
    Get signal summary (counts by severity and state).
    """
    try:
        from lib.intelligence.signals import get_signal_summary
        data = get_signal_summary()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("signals_summary failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/signals/active")
def active_signals(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
):
    """
    Get currently active signals from state tracking.
    """
    try:
        from lib.intelligence.signals import get_active_signals
        data = get_active_signals(entity_type=entity_type, entity_id=entity_id)
        return _wrap_response(data, {"entity_type": entity_type, "entity_id": entity_id})
    except Exception as e:
        logger.exception("active_signals failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/signals/history")
def signal_history(
    entity_type: str = Query(..., description="Entity type (client, project, person)"),
    entity_id: str = Query(..., description="Entity ID"),
    limit: int = Query(50, description="Max records to return"),
):
    """
    Get signal history for an entity.
    """
    try:
        from lib.intelligence.signals import get_signal_history
        data = get_signal_history(entity_type=entity_type, entity_id=entity_id, limit=limit)
        return _wrap_response(data, {"entity_type": entity_type, "entity_id": entity_id, "limit": limit})
    except Exception as e:
        logger.exception("signal_history failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/signals/export")
def export_signals():
    """
    Export all current signal detections as CSV for threshold tuning review.

    Returns CSV data with signal_id, severity, entity, metric,
    current_value, threshold_value, etc.
    """
    try:
        from lib.intelligence.signals import export_signals_for_review
        from fastapi.responses import PlainTextResponse

        csv_data = export_signals_for_review()
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=signals_export.csv"}
        )
    except Exception as e:
        logger.exception("export_signals failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/signals/thresholds")
def get_thresholds():
    """
    Get current threshold configuration for all signals.
    """
    try:
        from lib.intelligence.signals import load_thresholds
        data = load_thresholds()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("get_thresholds failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PATTERNS ENDPOINTS
# =============================================================================


@intelligence_router.get("/patterns")
def list_patterns():
    """
    Detect all active patterns.

    Returns structural patterns across entities:
    - Concentration (revenue, resource, communication)
    - Cascade (blast radius, dependency chains)
    - Degradation (quality, engagement erosion)
    - Drift (workload, ownership)
    - Correlation (load-quality, comm-payment)
    """
    try:
        from lib.intelligence import detect_all_patterns
        data = detect_all_patterns()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("list_patterns failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/patterns/catalog")
def pattern_catalog():
    """
    Get pattern library (all defined patterns with detection logic).
    """
    try:
        from lib.intelligence.patterns import PATTERN_LIBRARY

        catalog = []
        for pat_id, pat in PATTERN_LIBRARY.items():
            catalog.append({
                "id": pat.id,
                "name": pat.name,
                "description": pat.description,
                "type": pat.pattern_type.value,
                "severity": pat.severity.value,
                "entities_involved": pat.entities_involved,
                "implied_action": pat.implied_action,
            })

        return _wrap_response(catalog)
    except Exception as e:
        logger.exception("pattern_catalog failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PROPOSALS ENDPOINTS
# =============================================================================


@intelligence_router.get("/proposals")
def list_proposals(
    limit: int = Query(20, description="Max proposals to return"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (immediate, this_week, monitor)"),
):
    """
    Get ranked proposals.

    Returns proposals sorted by priority score with:
    - Headline, summary, entity
    - Evidence list
    - Implied action
    - Urgency and confidence
    """
    try:
        from lib.intelligence import (
            detect_all_signals,
            detect_all_patterns,
            generate_proposals,
            rank_proposals,
            get_top_proposals,
            ProposalUrgency,
        )

        signals = detect_all_signals(quick=True)
        patterns = detect_all_patterns()

        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        proposals = generate_proposals(signal_input, pattern_input)

        # Filter by urgency if specified
        if urgency:
            try:
                target_urgency = ProposalUrgency(urgency)
                proposals = [p for p in proposals if p.urgency == target_urgency]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid urgency: {urgency}")

        # Rank and limit
        top = get_top_proposals(proposals, n=limit)

        result = [
            {**p.to_dict(), "priority_score": s.to_dict()}
            for p, s in top
        ]

        return _wrap_response(result, {"limit": limit, "urgency": urgency})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("list_proposals failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SCORING ENDPOINTS
# =============================================================================


@intelligence_router.get("/scores/client/{client_id}")
def client_score(client_id: str):
    """
    Get scorecard for a client.

    Returns composite score and dimension scores:
    - Operational health
    - Financial health
    - Communication health
    - Engagement trajectory
    """
    try:
        from lib.intelligence import score_client
        data = score_client(client_id)
        return _wrap_response(data, {"client_id": client_id})
    except Exception as e:
        logger.exception("client_score failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/scores/project/{project_id}")
def project_score(project_id: str):
    """
    Get scorecard for a project.

    Returns composite score and dimension scores:
    - Velocity
    - Risk exposure
    - Team coverage
    - Scope control
    """
    try:
        from lib.intelligence import score_project
        data = score_project(project_id)
        return _wrap_response(data, {"project_id": project_id})
    except Exception as e:
        logger.exception("project_score failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/scores/person/{person_id}")
def person_score(person_id: str):
    """
    Get scorecard for a person.

    Returns composite score and dimension scores:
    - Load balance
    - Output consistency
    - Spread
    - Availability risk
    """
    try:
        from lib.intelligence import score_person
        data = score_person(person_id)
        return _wrap_response(data, {"person_id": person_id})
    except Exception as e:
        logger.exception("person_score failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/scores/portfolio")
def portfolio_score():
    """
    Get portfolio scorecard.

    Returns composite score and dimension scores:
    - Revenue concentration
    - Resource concentration
    - Client health distribution
    - Capacity utilization
    """
    try:
        from lib.intelligence import score_portfolio
        data = score_portfolio()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("portfolio_score failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SCORE HISTORY ENDPOINTS (Trend Analysis)
# =============================================================================


@intelligence_router.get("/scores/{entity_type}/{entity_id}/history")
def score_history(
    entity_type: str,
    entity_id: str,
    days: int = Query(30, description="Number of days of history"),
):
    """
    Get score history for an entity.

    Returns historical scores with trend analysis:
    - history: list of {date, score, classification}
    - trend: 'improving', 'declining', 'stable', or 'insufficient_data'
    - change_pct: percentage change over the period
    - current_score, period_high, period_low
    """
    valid_types = {"client", "project", "person", "portfolio"}
    if entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type. Must be one of: {valid_types}"
        )

    try:
        from lib.intelligence.scorecard import get_score_trend
        data = get_score_trend(entity_type, entity_id, days=days)
        return _wrap_response(data, {"entity_type": entity_type, "entity_id": entity_id, "days": days})
    except Exception as e:
        logger.exception("score_history failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/scores/history/summary")
def score_history_summary():
    """
    Get summary of score history data collection.

    Shows total records, breakdown by entity type, and recent recording activity.
    Useful for monitoring data health.
    """
    try:
        from lib.intelligence.scorecard import get_score_history_summary
        data = get_score_history_summary()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("score_history_summary failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.post("/scores/record")
def record_scores():
    """
    Record current scores for all entities.

    This endpoint triggers score recording for trend tracking.
    Should be called once per day (e.g., via cron).

    Returns counts of recorded scores by entity type.
    """
    try:
        from lib.intelligence.scorecard import record_all_scores
        data = record_all_scores()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("record_scores failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENTITY INTELLIGENCE ENDPOINTS (Deep Dive)
# =============================================================================


@intelligence_router.get("/entity/client/{client_id}")
def client_intelligence(client_id: str):
    """
    Get complete intelligence for a client.

    Returns everything the system knows:
    - Scorecard
    - Active signals
    - Signal history
    - Trajectory
    - Related proposals
    """
    try:
        from lib.intelligence import get_client_intelligence
        data = get_client_intelligence(client_id)
        return _wrap_response(data, {"client_id": client_id})
    except Exception as e:
        logger.exception("client_intelligence failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/entity/person/{person_id}")
def person_intelligence(person_id: str):
    """
    Get complete intelligence for a person.

    Returns everything the system knows:
    - Scorecard
    - Active signals
    - Signal history
    - Operational profile
    """
    try:
        from lib.intelligence import get_person_intelligence
        data = get_person_intelligence(person_id)
        return _wrap_response(data, {"person_id": person_id})
    except Exception as e:
        logger.exception("person_intelligence failed")
        raise HTTPException(status_code=500, detail=str(e))


@intelligence_router.get("/entity/portfolio")
def portfolio_intelligence():
    """
    Get portfolio-level intelligence.

    Lighter than full snapshot:
    - Portfolio score
    - Signal summary
    - Structural patterns
    - Top proposals
    """
    try:
        from lib.intelligence import get_portfolio_intelligence
        data = get_portfolio_intelligence()
        return _wrap_response(data)
    except Exception as e:
        logger.exception("portfolio_intelligence failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CHANGE DETECTION ENDPOINTS
# =============================================================================


@intelligence_router.get("/changes")
def detect_changes():
    """
    Run change detection and return delta report.

    Compares current state to last saved snapshot.
    Returns new/cleared signals, new proposals, score changes.
    """
    try:
        from lib.intelligence import generate_intelligence_snapshot, run_change_detection

        # Get current state
        snapshot = generate_intelligence_snapshot()

        # Run change detection
        changes = run_change_detection(snapshot)

        return _wrap_response({
            "changes": changes.to_dict(),
            "summary": changes.summary,
            "has_changes": changes.has_changes,
        })
    except Exception as e:
        logger.exception("detect_changes failed")
        raise HTTPException(status_code=500, detail=str(e))
