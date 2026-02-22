"""
Time OS V5 — Issues API

REST endpoints for issue management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...database import Database, get_db
from ...models import ResolutionMethod
from ...resolution.resolution_service import ResolutionService

router = APIRouter(prefix="/issues", tags=["issues"])


# =============================================================================
# Response Models
# =============================================================================


class SignalBalanceResponse(BaseModel):
    """Signal balance summary."""

    negative_count: int
    negative_magnitude: float
    neutral_count: int
    positive_count: int
    positive_magnitude: float
    net_score: float


class IssueResponse(BaseModel):
    """Issue response model."""

    id: str
    issue_type: str
    issue_subtype: str
    scope_type: str
    scope_id: str
    scope_name: str | None = None
    client_id: str | None = None
    client_name: str | None = None
    headline: str
    description: str | None = None
    severity: str
    priority_score: float
    trajectory: str
    signal_count: int
    signal_balance: SignalBalanceResponse
    recommended_action: str | None = None
    recommended_owner_role: str | None = None
    recommended_urgency: str | None = None
    state: str
    detected_at: str
    surfaced_at: str | None = None
    resolved_at: str | None = None
    regression_count: int = 0


class IssueListResponse(BaseModel):
    """Issue list response."""

    items: list[IssueResponse]
    total: int
    has_more: bool


class IssueSignalResponse(BaseModel):
    """Signal contributing to an issue."""

    id: str
    signal_type: str
    signal_category: str
    valence: int
    magnitude: float
    effective_magnitude: float
    entity_type: str
    entity_id: str
    entity_name: str | None = None
    status: str
    occurred_at: str
    detected_at: str


# =============================================================================
# Dependency
# =============================================================================


def get_database() -> Database:
    """Get database instance."""
    return get_db()


# =============================================================================
# List Endpoints
# =============================================================================


@router.get("", response_model=IssueListResponse)
async def list_issues(
    state: str | None = Query(None, description="Filter by state"),
    severity: str | None = Query(None, description="Filter by severity"),
    issue_type: str | None = Query(None, description="Filter by issue type"),
    client_id: str | None = Query(None, description="Filter by client"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Database = Depends(get_database),
):
    """
    List issues with filtering and pagination.

    Default: returns surfaced issues ordered by priority.
    """
    conditions = []
    params = []

    if state:
        conditions.append("i.state = ?")
        params.append(state)
    else:
        # Default: show active issues
        conditions.append("i.state IN ('surfaced', 'acknowledged', 'addressing')")

    if severity:
        conditions.append("i.severity = ?")
        params.append(severity)

    if issue_type:
        conditions.append("i.issue_type = ?")
        params.append(issue_type)

    if client_id:
        conditions.append("i.scope_client_id = ?")
        params.append(client_id)

    where = " AND ".join(conditions) if conditions else "1=1"

    # Get total count
    total = db.fetch_value(
        f"""
        SELECT COUNT(*) FROM issues_v5 i WHERE {where}
    """,
        tuple(params),
    )

    # Get items
    params.extend([limit, offset])
    rows = db.fetch_all(
        f"""
        SELECT
            i.*,
            c.name as client_name
        FROM issues_v5 i
        LEFT JOIN clients c ON i.scope_client_id = c.id
        WHERE {where}
        ORDER BY i.priority_score DESC, i.detected_at DESC
        LIMIT ? OFFSET ?
    """,
        tuple(params),
    )

    items = []
    for row in rows:
        items.append(_issue_row_to_response(row, db))

    return IssueListResponse(
        items=items, total=total or 0, has_more=(offset + limit) < (total or 0)
    )


# =============================================================================
# Detail Endpoints
# =============================================================================


@router.get("/{issue_id}", response_model=IssueResponse)
async def get_issue(issue_id: str, db: Database = Depends(get_database)):
    """Get a single issue with full details."""
    row = db.fetch_one(
        """
        SELECT
            i.*,
            c.name as client_name
        FROM issues_v5 i
        LEFT JOIN clients c ON i.scope_client_id = c.id
        WHERE i.id = ?
    """,
        (issue_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Issue not found")

    return _issue_row_to_response(row, db)


@router.get("/{issue_id}/signals", response_model=list[IssueSignalResponse])
async def get_issue_signals(issue_id: str, db: Database = Depends(get_database)):
    """Get all signals contributing to an issue."""
    import json

    # Get issue
    issue = db.fetch_one("SELECT signal_ids FROM issues_v5 WHERE id = ?", (issue_id,))
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    signal_ids = json.loads(issue["signal_ids"] or "[]")
    if not signal_ids:
        return []

    placeholders = ",".join(["?" for _ in signal_ids])
    rows = db.fetch_all(
        f"""
        SELECT * FROM signals_v5_computed
        WHERE id IN ({placeholders})
        ORDER BY detected_at DESC
    """,
        tuple(signal_ids),
    )

    signals = []
    for row in rows:
        signals.append(
            IssueSignalResponse(
                id=row["id"],
                signal_type=row["signal_type"],
                signal_category=row["signal_category"],
                valence=row["valence"],
                magnitude=row["magnitude"],
                effective_magnitude=row["effective_magnitude"] or row["magnitude"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                entity_name=_get_entity_name(db, row["entity_type"], row["entity_id"]),
                status=row["status"],
                occurred_at=row["occurred_at"],
                detected_at=row["detected_at"],
            )
        )

    return signals


# =============================================================================
# Action Endpoints
# =============================================================================


@router.post("/{issue_id}/acknowledge")
async def acknowledge_issue(
    issue_id: str,
    user_id: str = Query(..., description="User acknowledging"),
    db: Database = Depends(get_database),
):
    """Mark an issue as acknowledged (user has seen it)."""
    service = ResolutionService(db)

    if not service.acknowledge_issue(issue_id, user_id):
        raise HTTPException(status_code=400, detail="Cannot acknowledge issue")

    return {"status": "acknowledged", "issue_id": issue_id}


@router.post("/{issue_id}/address")
async def start_addressing_issue(
    issue_id: str,
    user_id: str | None = Query(None),
    db: Database = Depends(get_database),
):
    """Mark an issue as being addressed."""
    service = ResolutionService(db)

    if not service.start_addressing(issue_id, user_id):
        raise HTTPException(status_code=400, detail="Cannot start addressing issue")

    return {"status": "addressing", "issue_id": issue_id}


@router.post("/{issue_id}/resolve")
async def resolve_issue(
    issue_id: str,
    user_id: str | None = Query(None),
    notes: str | None = Query(None),
    db: Database = Depends(get_database),
):
    """Manually resolve an issue."""
    service = ResolutionService(db)

    if not service.resolve_issue(issue_id, ResolutionMethod.MANUAL, user_id, notes):
        raise HTTPException(status_code=400, detail="Cannot resolve issue")

    return {"status": "resolved", "issue_id": issue_id}


@router.post("/{issue_id}/dismiss")
async def dismiss_issue(
    issue_id: str,
    user_id: str = Query(...),
    reason: str | None = Query(None),
    db: Database = Depends(get_database),
):
    """Dismiss an issue as not relevant (false positive)."""
    service = ResolutionService(db)

    if not service.dismiss_issue(issue_id, user_id, reason):
        raise HTTPException(status_code=400, detail="Cannot dismiss issue")

    return {"status": "dismissed", "issue_id": issue_id}


# =============================================================================
# Helpers
# =============================================================================


def _issue_row_to_response(row: dict, db: Database) -> IssueResponse:
    """Convert database row to response model."""
    import json

    signal_ids = json.loads(row.get("signal_ids") or "[]")

    # Get scope name
    scope_name = _get_scope_name(db, row["scope_type"], row["scope_id"])

    return IssueResponse(
        id=row["id"],
        issue_type=row["issue_type"],
        issue_subtype=row["issue_subtype"],
        scope_type=row["scope_type"],
        scope_id=row["scope_id"],
        scope_name=scope_name,
        client_id=row.get("scope_client_id"),
        client_name=row.get("client_name"),
        headline=row["headline"],
        description=row.get("description"),
        severity=row["severity"],
        priority_score=row["priority_score"] or 0,
        trajectory=row.get("trajectory") or "stable",
        signal_count=len(signal_ids),
        signal_balance=SignalBalanceResponse(
            negative_count=row.get("balance_negative_count") or 0,
            negative_magnitude=row.get("balance_negative_magnitude") or 0,
            neutral_count=row.get("balance_neutral_count") or 0,
            positive_count=row.get("balance_positive_count") or 0,
            positive_magnitude=row.get("balance_positive_magnitude") or 0,
            net_score=row.get("balance_net_score") or 0,
        ),
        recommended_action=row.get("recommended_action"),
        recommended_owner_role=row.get("recommended_owner_role"),
        recommended_urgency=row.get("recommended_urgency"),
        state=row["state"],
        detected_at=row["detected_at"],
        surfaced_at=row.get("surfaced_at"),
        resolved_at=row.get("resolved_at"),
        regression_count=row.get("regression_count") or 0,
    )


def _get_scope_name(db: Database, scope_type: str, scope_id: str) -> str | None:
    """Get display name for scope."""
    table_map = {
        "task": ("tasks_v5", "title"),
        "project": ("projects_v5", "name"),
        "retainer": ("retainers", "name"),
        "brand": ("brands", "name"),
        "client": ("clients", "name"),
    }

    if scope_type not in table_map:
        return None

    table, col = table_map[scope_type]
    row = db.fetch_one(f"SELECT {col} as name FROM {table} WHERE id = ?", (scope_id,))  # nosec B608 — table/col from validated table_map
    return row["name"] if row else None


def _get_entity_name(db: Database, entity_type: str, entity_id: str) -> str | None:
    """Get display name for entity."""
    return _get_scope_name(db, entity_type, entity_id)
