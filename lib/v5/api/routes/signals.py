"""
Time OS V5 — Signals API

REST endpoints for signal queries.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...database import Database, get_db
from ...services.signal_service import SignalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

# =============================================================================
# Response Models
# =============================================================================


class SignalResponse(BaseModel):
    """Signal response model."""

    id: str
    signal_type: str
    signal_category: str
    valence: int
    magnitude: float
    effective_magnitude: float
    entity_type: str
    entity_id: str
    entity_name: str | None = None
    source_type: str
    source_excerpt: str | None = None
    value: dict[str, Any] = {}
    status: str
    occurred_at: str
    detected_at: str
    # Scope names
    client_name: str | None = None
    project_name: str | None = None


class SignalSummary(BaseModel):
    """Summary counts for signal list."""

    total: int
    by_valence: dict[str, int]
    by_category: dict[str, dict[str, int]]


class SignalListResponse(BaseModel):
    """Signal list response."""

    items: list[SignalResponse]
    total: int
    summary: SignalSummary
    has_more: bool


class ClientSignalSummaryResponse(BaseModel):
    """Client signal summary."""

    client_id: str
    client_name: str | None = None
    days: int
    totals: dict[str, int]
    by_category: dict[str, dict[str, int]]
    net_count: int
    trend: str  # improving, stable, worsening


# =============================================================================
# Dependency
# =============================================================================


def get_database() -> Database:
    """Get database instance."""
    return get_db()


# =============================================================================
# List Endpoints
# =============================================================================


@router.get("", response_model=SignalListResponse)
async def list_signals(
    status: str | None = Query("active"),
    valence: int | None = Query(None, description="-1, 0, or 1"),
    category: str | None = Query(None),
    client_id: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    days: int = Query(7, description="Signals from last N days"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Database = Depends(get_database),
):
    """List signals with filtering."""

    SignalService(db)

    # Build conditions
    conditions = [f"detected_at > datetime('now', '-{days} days')"]
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)

    if valence is not None:
        conditions.append("valence = ?")
        params.append(valence)

    if category:
        conditions.append("signal_category = ?")
        params.append(category)

    if client_id:
        conditions.append("scope_client_id = ?")
        params.append(client_id)

    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)

    if entity_id:
        conditions.append("entity_id = ?")
        params.append(entity_id)

    where = " AND ".join(conditions)

    # Get total count
    total = db.fetch_value(
        f"""
        SELECT COUNT(*) FROM signals_v5 WHERE {where}
    """,
        tuple(params),
    )

    # Get summary counts
    summary_rows = db.fetch_all(
        f"""
        SELECT
            valence,
            signal_category,
            COUNT(*) as count
        FROM signals_v5
        WHERE {where}
        GROUP BY valence, signal_category
    """,
        tuple(params),
    )

    by_valence = {"negative": 0, "neutral": 0, "positive": 0}
    by_category = {}

    for row in summary_rows:
        v = row["valence"]
        cat = row["signal_category"]
        cnt = row["count"]

        if v == -1:
            by_valence["negative"] += cnt
        elif v == 0:
            by_valence["neutral"] += cnt
        else:
            by_valence["positive"] += cnt

        if cat not in by_category:
            by_category[cat] = {"negative": 0, "neutral": 0, "positive": 0}

        if v == -1:
            by_category[cat]["negative"] += cnt
        elif v == 0:
            by_category[cat]["neutral"] += cnt
        else:
            by_category[cat]["positive"] += cnt

    # Get items
    params.extend([limit, offset])
    rows = db.fetch_all(
        f"""
        SELECT s.*,
               s.magnitude * CASE
                   WHEN julianday('now') - julianday(s.detected_at) > 365 THEN 0.1
                   WHEN julianday('now') - julianday(s.detected_at) > 180 THEN 0.25
                   WHEN julianday('now') - julianday(s.detected_at) > 90 THEN 0.5
                   WHEN julianday('now') - julianday(s.detected_at) > 30 THEN 0.8
                   ELSE 1.0
               END as effective_magnitude,
               c.name as client_name,
               p.name as project_name
        FROM signals_v5 s
        LEFT JOIN clients c ON s.scope_client_id = c.id
        LEFT JOIN projects_v5 p ON s.scope_project_id = p.id
        WHERE {where}
        ORDER BY s.detected_at DESC
        LIMIT ? OFFSET ?
    """,
        tuple(params),
    )

    items = []
    for row in rows:
        items.append(_signal_row_to_response(row, db))

    return SignalListResponse(
        items=items,
        total=total or 0,
        summary=SignalSummary(
            total=total or 0, by_valence=by_valence, by_category=by_category
        ),
        has_more=(offset + limit) < (total or 0),
    )


# =============================================================================
# Detail Endpoints
# =============================================================================


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: str, db: Database = Depends(get_database)):
    """Get a single signal with full details."""
    row = db.fetch_one(
        """
        SELECT s.*,
               s.magnitude * CASE
                   WHEN julianday('now') - julianday(s.detected_at) > 365 THEN 0.1
                   WHEN julianday('now') - julianday(s.detected_at) > 180 THEN 0.25
                   WHEN julianday('now') - julianday(s.detected_at) > 90 THEN 0.5
                   WHEN julianday('now') - julianday(s.detected_at) > 30 THEN 0.8
                   ELSE 1.0
               END as effective_magnitude,
               c.name as client_name,
               p.name as project_name
        FROM signals_v5 s
        LEFT JOIN clients c ON s.scope_client_id = c.id
        LEFT JOIN projects_v5 p ON s.scope_project_id = p.id
        WHERE s.id = ?
    """,
        (signal_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    return _signal_row_to_response(row, db)


# =============================================================================
# Summary Endpoints
# =============================================================================


@router.get("/summary/client/{client_id}", response_model=ClientSignalSummaryResponse)
async def get_client_signal_summary(
    client_id: str, days: int = Query(30), db: Database = Depends(get_database)
):
    """
    Get signal summary for a client.

    Returns counts by category and valence, plus trend.
    """
    service = SignalService(db)

    # Get client name
    client = db.fetch_one("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = client["name"] if client else None

    # Get summary
    summary = service.get_signal_summary(client_id, days)

    # Determine trend (compare first half vs second half of period)
    half_days = days // 2

    first_half = db.fetch_one(
        f"""
        SELECT
            SUM(CASE WHEN valence = -1 THEN 1 ELSE 0 END) as negative,
            SUM(CASE WHEN valence = 1 THEN 1 ELSE 0 END) as positive
        FROM signals_v5
        WHERE scope_client_id = ?
          AND detected_at > datetime('now', '-{days} days')
          AND detected_at <= datetime('now', '-{half_days} days')
    """,
        (client_id,),
    )

    second_half = db.fetch_one(
        f"""
        SELECT
            SUM(CASE WHEN valence = -1 THEN 1 ELSE 0 END) as negative,
            SUM(CASE WHEN valence = 1 THEN 1 ELSE 0 END) as positive
        FROM signals_v5
        WHERE scope_client_id = ?
          AND detected_at > datetime('now', '-{half_days} days')
    """,
        (client_id,),
    )

    # Calculate trend
    first_net = (first_half["positive"] or 0) - (first_half["negative"] or 0)
    second_net = (second_half["positive"] or 0) - (second_half["negative"] or 0)

    if second_net > first_net + 2:
        trend = "improving"
    elif second_net < first_net - 2:
        trend = "worsening"
    else:
        trend = "stable"

    return ClientSignalSummaryResponse(
        client_id=client_id,
        client_name=client_name,
        days=days,
        totals=summary["totals"],
        by_category=summary["by_category"],
        net_count=summary["net_count"],
        trend=trend,
    )


# =============================================================================
# Helpers
# =============================================================================


def _signal_row_to_response(row: dict, db: Database) -> SignalResponse:
    """Convert database row to response model."""
    import json

    # Parse value_json
    value = {}
    if row.get("value_json"):
        try:
            value = json.loads(row["value_json"])
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Could not parse value_json: {e}")

    # Get entity name
    entity_name = _get_entity_name(db, row["entity_type"], row["entity_id"])

    return SignalResponse(
        id=row["id"],
        signal_type=row["signal_type"],
        signal_category=row["signal_category"],
        valence=row["valence"],
        magnitude=row["magnitude"],
        effective_magnitude=row.get("effective_magnitude") or row["magnitude"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        entity_name=entity_name,
        source_type=row["source_type"],
        source_excerpt=row.get("source_excerpt"),
        value=value,
        status=row["status"],
        occurred_at=row["occurred_at"],
        detected_at=row["detected_at"],
        client_name=row.get("client_name"),
        project_name=row.get("project_name"),
    )


def _get_entity_name(db: Database, entity_type: str, entity_id: str) -> str | None:
    """Get display name for entity."""
    table_map = {
        "task": ("tasks_v5", "title"),
        "project": ("projects_v5", "name"),
        "retainer": ("retainers", "name"),
        "brand": ("brands", "name"),
        "client": ("clients", "name"),
        "invoice": ("xero_invoices", "invoice_number"),
    }

    if entity_type not in table_map:
        return None

    table, col = table_map[entity_type]
    row = db.fetch_one(f"SELECT {col} as name FROM {table} WHERE id = ?", (entity_id,))
    return row["name"] if row else None
