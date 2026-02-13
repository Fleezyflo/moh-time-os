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
