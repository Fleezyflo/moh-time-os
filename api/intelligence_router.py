"""
Intelligence API Router — Cross-Entity Query Endpoints

This router exposes the query engine functions via REST API.
All endpoints are read-only GET requests.

AUTHENTICATION: All endpoints require a valid Bearer token.
Set INTEL_API_TOKEN environment variable to enable auth.
Without this env var, auth is disabled (development mode).

Usage in server.py:
    from api.intelligence_router import intelligence_router
    app.include_router(intelligence_router, prefix="/api/v2/intelligence")
"""

import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.auth import require_auth
from api.response_models import IntelligenceResponse
from lib.cache import cache_invalidate, cached
from lib.query_engine import QueryEngine

logger = logging.getLogger(__name__)

# Router - ALL endpoints require authentication
intelligence_router = APIRouter(
    tags=["Intelligence"],
    dependencies=[Depends(require_auth)],  # Auth required for all endpoints
)

# Singleton query engine
_engine: QueryEngine | None = None


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


@intelligence_router.get("/portfolio/overview", response_model=IntelligenceResponse)
@cached(
    ttl=120, key_func=lambda order_by, desc: f"intelligence:portfolio:overview:{order_by}:{desc}"
)
def portfolio_overview(
    order_by: str = Query("total_tasks", description="Field to sort by"),
    desc: bool = Query(True, description="Sort descending"),
):
    """
    Get portfolio overview with all clients and their operational metrics.

    Returns clients with project_count, total_tasks, active_tasks,
    invoice_count, total_invoiced, total_outstanding, etc.

    Cached for 120 seconds.
    """
    try:
        engine = get_engine()
        data = engine.client_portfolio_overview(order_by=order_by, desc=desc)
        return _wrap_response(data, {"order_by": order_by, "desc": desc})
    except (sqlite3.Error, ValueError) as e:
        logger.exception("portfolio_overview failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "PORTFOLIO_OVERVIEW_ERROR"),
        )


@intelligence_router.get("/portfolio/risks", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("portfolio_risks failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/portfolio/trajectory", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("portfolio_trajectory failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# CLIENT ENDPOINTS
# =============================================================================


@intelligence_router.get("/clients/{client_id}/profile", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("client_profile failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/clients/{client_id}/tasks", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("client_tasks failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/clients/{client_id}/communication", response_model=IntelligenceResponse)
def client_communication(
    client_id: str,
    since: str | None = Query(None, description="Start date (ISO format)"),
    until: str | None = Query(None, description="End date (ISO format)"),
):
    """
    Get communication metrics for a client.

    Returns total_communications, by_type breakdown, and recent messages.
    """
    try:
        engine = get_engine()
        data = engine.client_communication_summary(client_id)
        return _wrap_response(data, {"client_id": client_id, "since": since, "until": until})
    except (sqlite3.Error, ValueError) as e:
        logger.exception("client_communication failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/clients/{client_id}/trajectory", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("client_trajectory failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/clients/{client_id}/compare", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("client_compare failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/clients/compare", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("clients_compare failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# TEAM ENDPOINTS
# =============================================================================


@intelligence_router.get("/team/distribution", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("team_distribution failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/team/capacity", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("team_capacity failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/team/{person_id}/profile", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("team_person_profile failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/team/{person_id}/trajectory", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("team_person_trajectory failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# PROJECT ENDPOINTS
# =============================================================================


@intelligence_router.get("/projects/{project_id}/state", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("project_state failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/projects/health", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("projects_health failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# FINANCIAL ENDPOINTS
# =============================================================================


@intelligence_router.get("/financial/aging", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("financial_aging failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# INTELLIGENCE LAYER ENDPOINTS (Scoring, Signals, Patterns, Proposals)
# =============================================================================


@intelligence_router.get("/snapshot", response_model=IntelligenceResponse)
@cached(ttl=60, key_func=lambda: "intelligence:snapshot:full")
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
    Cached for 60 seconds.
    """
    try:
        from lib.intelligence import generate_intelligence_snapshot

        data = generate_intelligence_snapshot()
        return _wrap_response(data)
    except (sqlite3.Error, ValueError) as e:
        logger.exception("intelligence_snapshot failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/critical", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("critical_items failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/briefing", response_model=IntelligenceResponse)
@cached(ttl=300, key_func=lambda: "intelligence:briefing:daily")
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

    Cached for 300 seconds (5 minutes).
    """
    try:
        from lib.intelligence import (
            detect_all_patterns,
            detect_all_signals,
            generate_daily_briefing,
            generate_proposals,
        )

        signals = detect_all_signals(quick=True)
        patterns = detect_all_patterns()

        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        proposals = generate_proposals(signal_input, pattern_input)
        briefing = generate_daily_briefing(proposals)

        return _wrap_response(briefing)
    except (sqlite3.Error, ValueError) as e:
        logger.exception("daily_briefing failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# SIGNALS ENDPOINTS
# =============================================================================


@intelligence_router.get("/signals", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("list_signals failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/signals/summary", response_model=IntelligenceResponse)
@cached(ttl=60, key_func=lambda: "intelligence:signals:summary")
def signals_summary():
    """
    Get signal summary (counts by severity and state).

    Cached for 60 seconds.
    """
    try:
        from lib.intelligence.signals import get_signal_summary

        data = get_signal_summary()
        return _wrap_response(data)
    except (sqlite3.Error, ValueError) as e:
        logger.exception("signals_summary failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/signals/active", response_model=IntelligenceResponse)
def active_signals(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
):
    """
    Get currently active signals from state tracking.
    """
    try:
        from lib.intelligence.signals import get_active_signals

        data = get_active_signals(entity_type=entity_type, entity_id=entity_id)
        return _wrap_response(data, {"entity_type": entity_type, "entity_id": entity_id})
    except (sqlite3.Error, ValueError) as e:
        logger.exception("active_signals failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/signals/history", response_model=IntelligenceResponse)
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
        return _wrap_response(
            data, {"entity_type": entity_type, "entity_id": entity_id, "limit": limit}
        )
    except (sqlite3.Error, ValueError) as e:
        logger.exception("signal_history failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/signals/export")
def export_signals():
    """
    Export all current signal detections as CSV for threshold tuning review.

    Returns CSV data with signal_id, severity, entity, metric,
    current_value, threshold_value, etc.
    """
    try:
        from fastapi.responses import PlainTextResponse

        from lib.intelligence.signals import export_signals_for_review

        csv_data = export_signals_for_review()
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=signals_export.csv"},
        )
    except (sqlite3.Error, ValueError) as e:
        logger.exception("export_signals failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/signals/thresholds", response_model=IntelligenceResponse)
def get_thresholds():
    """
    Get current threshold configuration for all signals.
    """
    try:
        from lib.intelligence.signals import load_thresholds

        data = load_thresholds()
        return _wrap_response(data)
    except (sqlite3.Error, ValueError) as e:
        logger.exception("get_thresholds failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# PATTERNS ENDPOINTS
# =============================================================================


@intelligence_router.get("/patterns", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("list_patterns failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/patterns/catalog", response_model=IntelligenceResponse)
def pattern_catalog():
    """
    Get pattern library (all defined patterns with detection logic).
    """
    try:
        from lib.intelligence.patterns import PATTERN_LIBRARY

        catalog = []
        for _pat_id, pat in PATTERN_LIBRARY.items():
            catalog.append(
                {
                    "id": pat.id,
                    "name": pat.name,
                    "description": pat.description,
                    "type": pat.pattern_type.value,
                    "severity": pat.severity.value,
                    "entities_involved": pat.entities_involved,
                    "implied_action": pat.implied_action,
                }
            )

        return _wrap_response(catalog)
    except (sqlite3.Error, ValueError) as e:
        logger.exception("pattern_catalog failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# PROPOSALS ENDPOINTS
# =============================================================================


@intelligence_router.get("/proposals", response_model=IntelligenceResponse)
def list_proposals(
    limit: int = Query(20, description="Max proposals to return"),
    urgency: str | None = Query(
        None, description="Filter by urgency (immediate, this_week, monitor)"
    ),
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
            ProposalUrgency,
            detect_all_patterns,
            detect_all_signals,
            generate_proposals,
            get_top_proposals,
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
                raise HTTPException(status_code=400, detail=f"Invalid urgency: {urgency}") from None

        # Rank and limit
        top = get_top_proposals(proposals, n=limit)

        result = [{**p.to_dict(), "priority_score": s.to_dict()} for p, s in top]

        return _wrap_response(result, {"limit": limit, "urgency": urgency})
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.exception("list_proposals failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# SCORING ENDPOINTS
# =============================================================================


@intelligence_router.get("/scores/client/{client_id}", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("client_score failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/scores/project/{project_id}", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("project_score failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/scores/person/{person_id}", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("person_score failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/scores/portfolio", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("portfolio_score failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# SCORE HISTORY ENDPOINTS (Trend Analysis)
# =============================================================================


@intelligence_router.get(
    "/scores/{entity_type}/{entity_id}/history", response_model=IntelligenceResponse
)
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
            status_code=400, detail=f"Invalid entity_type. Must be one of: {valid_types}"
        )

    try:
        from lib.intelligence.scorecard import get_score_trend

        data = get_score_trend(entity_type, entity_id, days=days)
        return _wrap_response(
            data, {"entity_type": entity_type, "entity_id": entity_id, "days": days}
        )
    except (sqlite3.Error, ValueError) as e:
        logger.exception("score_history failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/scores/history/summary", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("score_history_summary failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.post("/scores/record", response_model=IntelligenceResponse)
@cache_invalidate("intelligence:*")
def record_scores():
    """
    Record current scores for all entities.

    This endpoint triggers score recording for trend tracking.
    Should be called once per day (e.g., via cron).

    Returns counts of recorded scores by entity type.

    Cache invalidation: Clears all intelligence:* cache entries after recording.
    """
    try:
        from lib.intelligence.scorecard import record_all_scores

        data = record_all_scores()
        return _wrap_response(data)
    except (sqlite3.Error, ValueError) as e:
        logger.exception("record_scores failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# ENTITY INTELLIGENCE ENDPOINTS (Deep Dive)
# =============================================================================


@intelligence_router.get("/entity/client/{client_id}", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("client_intelligence failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/entity/person/{person_id}", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("person_intelligence failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/entity/portfolio", response_model=IntelligenceResponse)
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
    except (sqlite3.Error, ValueError) as e:
        logger.exception("portfolio_intelligence failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# CHANGE DETECTION ENDPOINTS
# =============================================================================


@intelligence_router.get("/changes", response_model=IntelligenceResponse)
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

        return _wrap_response(
            {
                "changes": changes.to_dict(),
                "summary": changes.summary,
                "has_changes": changes.has_changes,
            }
        )
    except (sqlite3.Error, ValueError) as e:
        logger.exception("detect_changes failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# ---------------------------------------------------------------------------
# Data Quality Endpoints
# ---------------------------------------------------------------------------


@intelligence_router.get("/data-quality", response_model=IntelligenceResponse)
def data_quality_overview():
    """Return data freshness, completeness, and quality confidence summary.

    Aggregates output from DataFreshnessTracker, CompletenessScorer,
    and QualityConfidenceAdjuster for a portfolio-wide data quality view.
    """
    from pathlib import Path as PathLib

    from lib.db import get_db_path_str
    from lib.intelligence.completeness_scorer import CompletenessScorer
    from lib.intelligence.data_freshness import DataFreshnessTracker
    from lib.intelligence.quality_confidence import QualityConfidenceAdjuster

    try:
        db_path = PathLib(get_db_path_str())

        freshness_tracker = DataFreshnessTracker(db_path)
        freshness_dashboard = freshness_tracker.get_freshness_dashboard()

        completeness_scorer = CompletenessScorer()
        gap_report = completeness_scorer.get_gap_report([])

        quality_adjuster = QualityConfidenceAdjuster()
        quality_summary = quality_adjuster.compute_quality_summary([])

        return _wrap_response(
            {
                "freshness": freshness_dashboard,
                "completeness": gap_report,
                "quality_confidence": quality_summary,
            }
        )
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("data_quality_overview failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# ---------------------------------------------------------------------------
# Entity Profile Endpoint
# ---------------------------------------------------------------------------


@intelligence_router.get(
    "/entity/{entity_type}/{entity_id}/profile",
    response_model=IntelligenceResponse,
)
def entity_profile(
    entity_type: str = PathParam(..., description="Entity type (client, project, person)"),
    entity_id: str = PathParam(..., description="Entity identifier"),
):
    """Build and return a full intelligence profile for an entity.

    Aggregates scores, signals, patterns, cost profile, and trajectory
    into a single EntityIntelligenceProfile via build_entity_profile().
    """
    from lib.intelligence.entity_profile import CostProfile, build_entity_profile

    try:
        default_cost = CostProfile(
            effort_score=0.0,
            profitability_band="unknown",
            estimated_cost_per_month=0.0,
            cost_drivers=[],
        )
        profile = build_entity_profile(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_id,
            score_dimensions=[],
            active_signals=[],
            previous_signals=None,
            active_patterns=[],
            compound_risks=[],
            cost_profile=default_cost,
        )
        profile_data = (
            profile.to_dict()
            if hasattr(profile, "to_dict")
            else profile.__dict__
            if hasattr(profile, "__dict__")
            else {"entity_type": entity_type, "entity_id": entity_id}
        )
        return _wrap_response(
            profile_data,
            {"entity_type": entity_type, "entity_id": entity_id},
        )
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("entity_profile failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# INTELLIGENCE OBSERVABILITY ENDPOINTS (Audit Trail, Explainability)
# =============================================================================


@intelligence_router.get("/audit-trail", response_model=IntelligenceResponse)
def audit_trail_entries(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None = Query(None, description="Filter by entity ID"),
    operation: str | None = Query(None, description="Filter by operation type"),
    limit: int = Query(50, description="Max entries to return"),
):
    """
    Get recent intelligence audit trail entries.

    Returns a log of intelligence operations with inputs, outputs, and timing.
    """
    from pathlib import Path as PathLib

    from lib.db import get_db_path_str
    from lib.intelligence.audit_trail import AuditTrail

    try:
        db_path = PathLib(get_db_path_str())
        trail = AuditTrail(db_path)
        entries = trail.get_entries(
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            limit=limit,
        )
        return _wrap_response(
            [e.to_dict() for e in entries],
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "operation": operation,
                "limit": limit,
            },
        )
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("audit_trail_entries failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get(
    "/explain/{entity_type}/{entity_id}",
    response_model=IntelligenceResponse,
)
def explain_entity(
    entity_type: str = PathParam(..., description="Entity type (client, project, person)"),
    entity_id: str = PathParam(..., description="Entity identifier"),
):
    """
    Get human-readable explanations for an entity's intelligence outputs.

    Returns explanations for health score, active signals, and attention level.
    """
    from pathlib import Path as PathLib

    from lib.db import get_db_path_str
    from lib.intelligence.explainability import IntelligenceExplainer
    from lib.intelligence.health_unifier import HealthUnifier
    from lib.intelligence.signals import get_active_signals

    try:
        db_path = PathLib(get_db_path_str())
        explainer = IntelligenceExplainer()
        explanations = []

        # Explain health score
        try:
            unifier = HealthUnifier(db_path)
            health = unifier.get_latest_health(entity_type, entity_id)
            if health:
                dims = [{"dimension": k, "score": v} for k, v in (health.dimensions or {}).items()]
                explanation = explainer.explain_health_score(
                    entity_name=entity_id,
                    health_score=health.composite_score,
                    dimensions=dims,
                    weights={k: 1.0 / max(len(dims), 1) for k in health.dimensions},
                )
                explanations.append(explanation.to_dict())
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"explain_entity: health score explanation failed: {e}")

        # Explain active signals
        try:
            active = get_active_signals(entity_type=entity_type, entity_id=entity_id)
            for sig in active if isinstance(active, list) else active.get("signals", []):
                explanation = explainer.explain_signal(
                    signal_type=sig.get("signal_type", ""),
                    severity=sig.get("severity", "watch"),
                    entity_name=entity_id,
                    trigger_value=sig.get("current_value", 0),
                    threshold=sig.get("threshold", 0),
                )
                explanations.append(explanation.to_dict())
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"explain_entity: signal explanation failed: {e}")

        return _wrap_response(
            explanations,
            {"entity_type": entity_type, "entity_id": entity_id},
        )
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("explain_entity failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get("/attention-debt", response_model=IntelligenceResponse)
def attention_debt(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    days_back: int = Query(7, description="Days to look back for attention events"),
):
    """
    Get entities sorted by attention debt (most neglected first).

    Returns attention summary with debt distribution and per-entity debt levels.
    """
    from pathlib import Path as PathLib

    from lib.db import get_db_path_str
    from lib.intelligence.attention_tracking import AttentionTracker

    try:
        db_path = PathLib(get_db_path_str())
        tracker = AttentionTracker(db_path)
        summary = tracker.get_attention_summary(
            entity_type=entity_type,
            days_back=days_back,
        )
        return _wrap_response(
            summary.to_dict(),
            {"entity_type": entity_type, "days_back": days_back},
        )
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("attention_debt failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get(
    "/predictions/early-warnings",
    response_model=IntelligenceResponse,
)
def early_warnings(
    entity_type: str | None = Query(None, description="Filter by entity type"),
):
    """
    Get early warnings for entities with declining health or churn risk.

    Returns list of early warnings with probability and recommended actions.
    """
    from pathlib import Path as PathLib

    from lib.db import get_db_path_str
    from lib.intelligence.health_unifier import HealthUnifier
    from lib.intelligence.predictive_intelligence import PredictiveIntelligence

    try:
        db_path = PathLib(get_db_path_str())
        predictor = PredictiveIntelligence()
        unifier = HealthUnifier(db_path)
        all_warnings = []

        entity_types = [entity_type] if entity_type else ["client", "project", "person"]
        for etype in entity_types:
            try:
                recent = unifier.get_all_latest_health(etype)
                for hs in recent:
                    if hs.composite_score is None or not hs.entity_id:
                        continue
                    try:
                        trend = unifier.get_health_trend(etype, hs.entity_id, days=30)
                        scores = [h.composite_score for h in trend if h.composite_score is not None]
                        if scores:
                            warnings = predictor.generate_early_warnings(
                                entity_type=etype,
                                entity_id=hs.entity_id,
                                health_scores=scores,
                            )
                            all_warnings.extend(w.to_dict() for w in warnings)
                    except (sqlite3.Error, ValueError, OSError) as e:
                        logger.error(f"early_warnings: {etype}/{hs.entity_id} failed: {e}")
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"early_warnings: {etype} query failed: {e}")

        return _wrap_response(all_warnings, {"entity_type": entity_type})
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("early_warnings failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.get(
    "/governance/compliance-report",
    response_model=IntelligenceResponse,
)
def compliance_report():
    """
    Generate a data governance compliance report.

    Returns compliance status, PII inventory, retention policies, and violations.
    Uses real DataClassifier, RetentionEngine, and SubjectAccessManager from lib.governance.
    """
    from lib import paths
    from lib.governance import RetentionEngine, SubjectAccessManager
    from lib.governance.data_classification import DataClassifier

    try:
        db_path = str(paths.db_path())

        classifier = DataClassifier(db_path)
        catalog = classifier.classify_database()
        retention = RetentionEngine(db_path)
        subject_access = SubjectAccessManager(db_path)

        pii_tables = catalog.get_pii_tables()
        retention_policies = retention.get_policies()
        deletion_requests = subject_access.list_requests(status="completed")

        violations = []
        policy_table_names = {p.table for p in retention_policies}
        for table_name in pii_tables:
            if table_name not in policy_table_names:
                violations.append(f"PII table '{table_name}' has no retention policy")

        if len(violations) > 3:
            overall_status = "non_compliant"
        elif violations:
            overall_status = "warning"
        else:
            overall_status = "compliant"

        report_data = {
            "data_inventory": catalog.get_compliance_summary(),
            "retention_status": {
                "total_policies": len(retention_policies),
                "tables_covered": list(policy_table_names),
            },
            "deletion_requests_processed": len(deletion_requests),
            "pii_tables_count": len(pii_tables),
            "policy_violations": violations,
            "overall_status": overall_status,
        }

        return _wrap_response(report_data)
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("compliance_report failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "COMPLIANCE_REPORT_ERROR"),
        )


# =========================================================================
# TRAJECTORY ENDPOINTS
# =========================================================================


@intelligence_router.get(
    "/trajectory/{entity_type}/{entity_id}",
    response_model=IntelligenceResponse,
)
def get_trajectory(
    entity_type: str = PathParam(..., description="Entity type (client)"),
    entity_id: str = PathParam(..., description="Entity ID"),
    windows: int = Query(12, ge=2, le=52, description="Number of time windows"),
):
    """
    Get full trajectory analysis for an entity.

    Returns velocity, acceleration, trend, seasonality, and projections.
    Currently supports entity_type='client'.
    """
    from pathlib import Path as FilePath

    from lib import paths
    from lib.intelligence.trajectory import TrajectoryEngine

    try:
        db_path = FilePath(paths.db_path())
        engine = TrajectoryEngine(db_path)

        if entity_type == "client":
            result = engine.client_full_trajectory(entity_id, windows=windows)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported entity_type: {entity_type}. Use 'client'.",
            )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"{entity_type} '{entity_id}' not found or no data",
            )

        return _wrap_response(
            result.to_dict(),
            {"entity_type": entity_type, "entity_id": entity_id, "windows": windows},
        )
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("trajectory endpoint failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =========================================================================
# SCENARIO MODELING ENDPOINTS (API-only -- NOT in the loop)
# =========================================================================


@intelligence_router.post(
    "/scenarios/model",
    response_model=IntelligenceResponse,
)
def model_scenario(config: dict):
    """
    Model a what-if scenario.

    Accepts a config dict with:
    - scenario_type: CLIENT_LOSS | CLIENT_ADDITION | RESOURCE_CHANGE |
                     PRICING_CHANGE | CAPACITY_SHIFT | WORKLOAD_REBALANCE
    - Plus type-specific parameters (client_id, person_name, etc.)
    """
    from pathlib import Path as FilePath

    from lib import paths
    from lib.intelligence.scenario_engine import ScenarioEngine, ScenarioType

    try:
        db_path = FilePath(paths.db_path())
        engine = ScenarioEngine(db_path)

        scenario_type = config.get("scenario_type", "")
        try:
            stype = ScenarioType(scenario_type)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid scenario_type: {scenario_type}. "
                f"Valid: {[s.value for s in ScenarioType]}",
            ) from e

        result = None
        if stype == ScenarioType.CLIENT_LOSS:
            client_id = config.get("client_id")
            if not client_id:
                raise HTTPException(status_code=400, detail="client_id required")
            result = engine.model_client_loss(client_id)

        elif stype == ScenarioType.CLIENT_ADDITION:
            result = engine.model_client_addition(
                estimated_revenue=config.get("estimated_revenue", 0),
                estimated_tasks=config.get("estimated_tasks", 0),
                team_size=config.get("team_size", 1),
            )

        elif stype == ScenarioType.RESOURCE_CHANGE:
            person_name = config.get("person_name")
            change_type = config.get("change_type", "leaves")
            if not person_name:
                raise HTTPException(status_code=400, detail="person_name required")
            result = engine.model_resource_change(person_name, change_type)

        elif stype == ScenarioType.PRICING_CHANGE:
            client_id = config.get("client_id")
            pct_change = config.get("pct_change", 0)
            if not client_id:
                raise HTTPException(status_code=400, detail="client_id required")
            result = engine.model_pricing_change(client_id, pct_change)

        elif stype == ScenarioType.CAPACITY_SHIFT:
            lane_id = config.get("lane_id")
            delta_hours = config.get("delta_hours", 0)
            if not lane_id:
                raise HTTPException(status_code=400, detail="lane_id required")
            result = engine.model_capacity_shift(lane_id, delta_hours)

        elif stype == ScenarioType.WORKLOAD_REBALANCE:
            result = engine.model_workload_rebalance()

        if result is None:
            raise HTTPException(status_code=404, detail="Scenario produced no result")

        return _wrap_response(result.to_dict(), {"scenario_type": scenario_type})
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("scenario model failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


@intelligence_router.post(
    "/scenarios/compare",
    response_model=IntelligenceResponse,
)
def compare_scenarios(configs: list[dict]):
    """
    Compare multiple scenarios side-by-side.

    Accepts a list of scenario config dicts (same format as /scenarios/model).
    Returns comparison with best/worst case and tradeoff analysis.
    """
    from pathlib import Path as FilePath

    from lib import paths
    from lib.intelligence.scenario_engine import ScenarioEngine, ScenarioType

    try:
        db_path = FilePath(paths.db_path())
        engine = ScenarioEngine(db_path)

        # Model each scenario
        results_list = []
        for cfg in configs:
            scenario_type = cfg.get("scenario_type", "")
            try:
                stype = ScenarioType(scenario_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid scenario_type: {scenario_type}",
                ) from e

            result = None
            if stype == ScenarioType.CLIENT_LOSS:
                result = engine.model_client_loss(cfg.get("client_id", ""))
            elif stype == ScenarioType.CLIENT_ADDITION:
                result = engine.model_client_addition(
                    estimated_revenue=cfg.get("estimated_revenue", 0),
                    estimated_tasks=cfg.get("estimated_tasks", 0),
                    team_size=cfg.get("team_size", 1),
                )
            elif stype == ScenarioType.RESOURCE_CHANGE:
                result = engine.model_resource_change(
                    cfg.get("person_name", ""),
                    cfg.get("change_type", "leaves"),
                )
            elif stype == ScenarioType.PRICING_CHANGE:
                result = engine.model_pricing_change(
                    cfg.get("client_id", ""),
                    cfg.get("pct_change", 0),
                )
            elif stype == ScenarioType.CAPACITY_SHIFT:
                result = engine.model_capacity_shift(
                    cfg.get("lane_id", ""),
                    cfg.get("delta_hours", 0),
                )
            elif stype == ScenarioType.WORKLOAD_REBALANCE:
                result = engine.model_workload_rebalance()

            if result is not None:
                results_list.append(result)

        if len(results_list) < 2:
            raise HTTPException(
                status_code=400,
                detail="Need at least 2 successful scenarios to compare",
            )

        comparison = engine.compare_scenarios(results_list)
        if comparison is None:
            return JSONResponse(
                status_code=500,
                content=_error_response("Comparison produced no result", "COMPARISON_EMPTY"),
            )

        return _wrap_response(comparison.to_dict())
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("scenario compare failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "QUERY_ERROR"),
        )


# =============================================================================
# CONVERSATIONAL INTELLIGENCE ENDPOINTS
# =============================================================================


class ConversationRequest(BaseModel):
    """Request model for conversational intelligence."""

    query: str
    session_id: str | None = None
    context: dict | None = None


_sessions: dict[str, object] = {}


@intelligence_router.post("/conversation", response_model=IntelligenceResponse)
def conversation(request: ConversationRequest):
    """
    Process natural language query using conversational intelligence.

    Maintains session state per session_id. If session_id is None, generates a new UUID.
    Returns intent, entities, response, and conversation state.
    """
    import uuid

    from lib.intelligence.conversational_intelligence import ConversationalIntelligence

    try:
        session_id = request.session_id or str(uuid.uuid4())

        if session_id not in _sessions:
            _sessions[session_id] = ConversationalIntelligence()

        ci = _sessions[session_id]
        result = ci.process_query(request.query, context=request.context)

        return _wrap_response(
            result,
            {"query": request.query, "session_id": session_id},
        )
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("conversation failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "CONVERSATION_ERROR"),
        )


# =============================================================================
# ENTITY INTELLIGENCE ENDPOINTS
# =============================================================================


@intelligence_router.get(
    "/entity/{entity_type}/{entity_id}/profile",
    response_model=IntelligenceResponse,
)
def get_entity_profile(
    entity_type: str = PathParam(..., description="Entity type (client, project, person)"),
    entity_id: str = PathParam(..., description="Entity ID"),
):
    """
    Get complete intelligence profile for a single entity.

    Returns all 7 intelligence dimensions: health, signals, patterns,
    trajectory, costs, narrative, and recommended actions.
    """
    from lib.intelligence.entity_profile import (
        CostProfile,
        build_entity_profile,
    )

    try:
        get_engine()
        cost_profile = CostProfile(
            effort_score=0.0,
            profitability_band="unknown",
            estimated_cost_per_month=0.0,
            cost_drivers=[],
        )
        profile = build_entity_profile(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name="",
            score_dimensions=[],
            active_signals=[],
            previous_signals=None,
            active_patterns=[],
            compound_risks=[],
            cost_profile=cost_profile,
        )
        return _wrap_response(profile.to_dict())
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("get_entity_profile failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "ENTITY_PROFILE_ERROR"),
        )


# =============================================================================
# CALIBRATION REPORTS (GAP-10-03)
# =============================================================================


@intelligence_router.get("/calibration/report", response_model=IntelligenceResponse)
async def get_calibration_report(
    report_type: str = "weekly",
    signal_id: str | None = None,
):
    """
    GET /api/v2/intelligence/calibration/report?report_type=weekly

    Generate a calibration report for threshold tuning.

    report_type: 'weekly' | 'effectiveness' | 'history'
    signal_id: Required for 'history' report type.
    """
    try:
        from lib.intelligence.calibration_reporter import CalibrationReporter

        reporter = CalibrationReporter()

        if report_type == "weekly":
            report = reporter.weekly_report(feedback=[])
        elif report_type == "effectiveness":
            report = reporter.effectiveness_report(feedback=[])
        elif report_type == "history":
            if not signal_id:
                raise HTTPException(
                    status_code=400,
                    detail="signal_id is required for history report",
                )
            report = reporter.history_report(signal_id=signal_id)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown report_type: {report_type}. Use 'weekly', 'effectiveness', or 'history'.",
            )

        return _wrap_response(report.to_dict())
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("get_calibration_report failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "CALIBRATION_REPORT_ERROR"),
        )


@intelligence_router.get("/calibration/briefing", response_model=IntelligenceResponse)
async def get_calibration_briefing():
    """
    GET /api/v2/intelligence/calibration/briefing

    Generate a calibration briefing formatted for the morning brief.
    """
    try:
        from lib.intelligence.calibration_reporter import CalibrationReporter

        reporter = CalibrationReporter()
        report = reporter.weekly_report(feedback=[])
        briefing = reporter.format_for_briefing(report)
        return _wrap_response(briefing)
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.exception("get_calibration_briefing failed")
        return JSONResponse(
            status_code=500,
            content=_error_response(str(e), "CALIBRATION_BRIEFING_ERROR"),
        )
