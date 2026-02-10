"""
Time OS V5 — Health Dashboard API

REST endpoints for health monitoring.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...database import Database, get_db
from ...services.signal_service import SignalService

router = APIRouter(prefix="/health", tags=["health"])


# =============================================================================
# Response Models
# =============================================================================


class ClientHealthResponse(BaseModel):
    """Client health summary."""

    client_id: str
    client_name: str
    tier: str
    health_status: str
    health_score: float
    trajectory: str

    signal_summary: dict[str, dict[str, int]]
    active_issues_count: int
    ar_total: float
    ar_overdue: float

    engagement_trend: str
    last_meaningful_contact: str | None = None


class HealthDashboardResponse(BaseModel):
    """Overall health dashboard."""

    summary: dict[str, Any]
    at_risk_clients: list[ClientHealthResponse]
    healthy_clients_count: int
    total_ar: float
    total_ar_overdue: float
    active_issues_by_type: dict[str, int]


class ClientHealthTimelinePoint(BaseModel):
    """Point in health timeline."""

    date: str
    negative_magnitude: float
    positive_magnitude: float
    net_score: float
    issue_count: int


class ClientHealthTimelineResponse(BaseModel):
    """Client health timeline."""

    client_id: str
    client_name: str | None = None
    days: int
    points: list[ClientHealthTimelinePoint]


# =============================================================================
# Dependency
# =============================================================================


def get_database() -> Database:
    """Get database instance."""
    return get_db()


# =============================================================================
# Dashboard Endpoint
# =============================================================================


@router.get("/dashboard", response_model=HealthDashboardResponse)
async def get_health_dashboard(db: Database = Depends(get_database)):
    """Get overall health dashboard."""

    # Get clients by health status
    status_counts = db.fetch_all("""
        SELECT health_status, COUNT(*) as count
        FROM clients
        WHERE archived_at IS NULL
        GROUP BY health_status
    """)

    status_summary = {row["health_status"]: row["count"] for row in status_counts}
    healthy_count = status_summary.get("healthy", 0)

    # Get at-risk clients
    at_risk_rows = db.fetch_all("""
        SELECT c.*
        FROM clients c
        WHERE c.health_status IN ('at_risk', 'critical', 'cooling')
          AND c.archived_at IS NULL
        ORDER BY c.health_score ASC
        LIMIT 10
    """)

    at_risk_clients = []
    for row in at_risk_rows:
        client_health = await _build_client_health(db, row)
        at_risk_clients.append(client_health)

    # Get AR totals
    ar_row = db.fetch_one("""
        SELECT
            COALESCE(SUM(total), 0) as total_ar,
            COALESCE(SUM(CASE WHEN status NOT IN ('PAID', 'VOIDED') AND date(due_date) < date('now') THEN amount_due ELSE 0 END), 0) as total_overdue
        FROM xero_invoices
        WHERE status NOT IN ('PAID', 'VOIDED')
    """)

    total_ar = ar_row["total_ar"] if ar_row else 0
    total_ar_overdue = ar_row["total_overdue"] if ar_row else 0

    # Get active issues by type
    issue_type_rows = db.fetch_all("""
        SELECT issue_type, COUNT(*) as count
        FROM issues_v5
        WHERE state IN ('surfaced', 'acknowledged', 'addressing')
        GROUP BY issue_type
    """)

    issues_by_type = {row["issue_type"]: row["count"] for row in issue_type_rows}

    return HealthDashboardResponse(
        summary={
            "total_clients": sum(status_summary.values()),
            "by_status": status_summary,
        },
        at_risk_clients=at_risk_clients,
        healthy_clients_count=healthy_count,
        total_ar=total_ar,
        total_ar_overdue=total_ar_overdue,
        active_issues_by_type=issues_by_type,
    )


# =============================================================================
# Client Health Endpoint
# =============================================================================


@router.get("/client/{client_id}", response_model=ClientHealthResponse)
async def get_client_health(client_id: str, db: Database = Depends(get_database)):
    """Get detailed health for a specific client."""

    row = db.fetch_one("SELECT * FROM clients WHERE id = ?", (client_id,))

    if not row:
        raise HTTPException(status_code=404, detail="Client not found")

    return await _build_client_health(db, row)


# =============================================================================
# Client Timeline Endpoint
# =============================================================================


@router.get("/client/{client_id}/timeline", response_model=ClientHealthTimelineResponse)
async def get_client_health_timeline(
    client_id: str, days: int = Query(90), db: Database = Depends(get_database)
):
    """Get health timeline (signal balance over time)."""

    # Get client name
    client = db.fetch_one("SELECT name FROM clients WHERE id = ?", (client_id,))

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get daily signal aggregates
    rows = db.fetch_all(
        """
        SELECT
            date(detected_at) as date,
            SUM(CASE WHEN valence = -1 THEN magnitude ELSE 0 END) as negative_mag,
            SUM(CASE WHEN valence = 1 THEN magnitude ELSE 0 END) as positive_mag
        FROM signals_v5
        WHERE scope_client_id = ?
          AND detected_at > datetime('now', ?)
        GROUP BY date(detected_at)
        ORDER BY date(detected_at)
    """,
        (client_id, f"-{days} days"),
    )

    # Get daily issue counts
    issue_rows = db.fetch_all(
        """
        SELECT
            date(detected_at) as date,
            COUNT(*) as count
        FROM issues_v5
        WHERE scope_client_id = ?
          AND detected_at > datetime('now', ?)
        GROUP BY date(detected_at)
    """,
        (client_id, f"-{days} days"),
    )

    issue_counts = {r["date"]: r["count"] for r in issue_rows}

    points = []
    for row in rows:
        neg = row["negative_mag"] or 0
        pos = row["positive_mag"] or 0
        points.append(
            ClientHealthTimelinePoint(
                date=row["date"],
                negative_magnitude=neg,
                positive_magnitude=pos,
                net_score=pos - neg,
                issue_count=issue_counts.get(row["date"], 0),
            )
        )

    return ClientHealthTimelineResponse(
        client_id=client_id, client_name=client["name"], days=days, points=points
    )


# =============================================================================
# Helpers
# =============================================================================


async def _build_client_health(db: Database, client_row: dict) -> ClientHealthResponse:
    """Build client health response from row."""

    client_id = client_row["id"]

    # Get signal summary
    service = SignalService(db)
    signal_summary = service.get_signal_summary(client_id, 30)

    # Get active issues count
    issue_count = db.fetch_value(
        """
        SELECT COUNT(*) FROM issues_v5
        WHERE scope_client_id = ?
          AND state IN ('surfaced', 'acknowledged', 'addressing')
    """,
        (client_id,),
    )

    # Get AR
    ar_row = db.fetch_one(
        """
        SELECT
            COALESCE(SUM(total), 0) as total,
            COALESCE(SUM(CASE WHEN status NOT IN ('PAID', 'VOIDED') AND date(due_date) < date('now') THEN amount_due ELSE 0 END), 0) as overdue
        FROM xero_invoices
        WHERE client_id = ?
          AND status NOT IN ('PAID', 'VOIDED')
    """,
        (client_id,),
    )

    ar_total = ar_row["total"] if ar_row else 0
    ar_overdue = ar_row["overdue"] if ar_row else 0

    # Get last meaningful contact (last message or meeting)
    last_contact = db.fetch_one(
        """
        SELECT MAX(last_message_at) as last_message
        FROM gchat_sync_state
        WHERE client_id = ?
    """,
        (client_id,),
    )

    last_contact_date = last_contact["last_message"] if last_contact else None

    # Determine trajectory
    trajectory = _determine_client_trajectory(db, client_id)

    # Determine engagement trend
    engagement = _determine_engagement_trend(db, client_id)

    return ClientHealthResponse(
        client_id=client_id,
        client_name=client_row["name"],
        tier=client_row.get("tier") or "unclassified",
        health_status=client_row.get("health_status") or "healthy",
        health_score=client_row.get("health_score") or 100,
        trajectory=trajectory,
        signal_summary=signal_summary.get("by_category", {}),
        active_issues_count=issue_count or 0,
        ar_total=ar_total,
        ar_overdue=ar_overdue,
        engagement_trend=engagement,
        last_meaningful_contact=last_contact_date,
    )


def _determine_client_trajectory(db: Database, client_id: str) -> str:
    """Determine client health trajectory."""

    # Compare last 15 days vs previous 15 days
    recent = db.fetch_one(
        """
        SELECT
            SUM(CASE WHEN valence = -1 THEN magnitude ELSE 0 END) as neg,
            SUM(CASE WHEN valence = 1 THEN magnitude ELSE 0 END) as pos
        FROM signals_v5
        WHERE scope_client_id = ?
          AND detected_at > datetime('now', '-15 days')
    """,
        (client_id,),
    )

    older = db.fetch_one(
        """
        SELECT
            SUM(CASE WHEN valence = -1 THEN magnitude ELSE 0 END) as neg,
            SUM(CASE WHEN valence = 1 THEN magnitude ELSE 0 END) as pos
        FROM signals_v5
        WHERE scope_client_id = ?
          AND detected_at > datetime('now', '-30 days')
          AND detected_at <= datetime('now', '-15 days')
    """,
        (client_id,),
    )

    recent_net = (recent["pos"] or 0) - (recent["neg"] or 0)
    older_net = (older["pos"] or 0) - (older["neg"] or 0)

    if recent_net > older_net + 1:
        return "improving"
    if recent_net < older_net - 1:
        return "worsening"
    return "stable"


def _determine_engagement_trend(db: Database, client_id: str) -> str:
    """Determine client engagement trend."""

    # Compare message counts
    recent = db.fetch_value(
        """
        SELECT COUNT(*) FROM gchat_messages m
        JOIN gchat_sync_state s ON m.space_id = s.space_id
        WHERE s.client_id = ?
          AND m.created_at > datetime('now', '-15 days')
    """,
        (client_id,),
    )

    older = db.fetch_value(
        """
        SELECT COUNT(*) FROM gchat_messages m
        JOIN gchat_sync_state s ON m.space_id = s.space_id
        WHERE s.client_id = ?
          AND m.created_at > datetime('now', '-30 days')
          AND m.created_at <= datetime('now', '-15 days')
    """,
        (client_id,),
    )

    recent = recent or 0
    older = older or 0

    if older == 0:
        return "stable" if recent == 0 else "increasing"

    change_pct = (recent - older) / older

    if change_pct > 0.2:
        return "increasing"
    if change_pct < -0.2:
        return "decreasing"
    return "stable"
