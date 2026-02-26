"""
Spec-Compliant API Router — CLIENT-UI-SPEC-v2.9.md

This router implements the API endpoints defined in the spec using
the ui_spec_v21 modules. Mount this on the main FastAPI app.

Usage in server.py:
    from api.spec_router import spec_router
    app.include_router(spec_router, prefix="/api/v2")
"""

import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from api.response_models import (
    ClientIndexResponse,
    DetailResponse,
    EngagementListResponse,
    FixDataResponse,
    HealthResponse,
    InboxCountsResponse,
    InboxRecentResponse,
    InboxResponse,
    IntelligenceResponse,
    InvoiceListResponse,
    ListResponse,
    MutationResponse,
    SignalListResponse,
    TeamInvolvementResponse,
)
from lib import paths
from lib.ui_spec_v21.endpoints import (
    ClientEndpoints,
    FinancialsEndpoints,
    InboxEndpoints,
)
from lib.ui_spec_v21.inbox_lifecycle import InboxLifecycleManager
from lib.ui_spec_v21.issue_lifecycle import (
    AVAILABLE_ACTIONS,
    IssueLifecycleManager,
    IssueState,
)
from lib.ui_spec_v21.time_utils import now_iso

# Import safety modules
try:
    from lib.safety import WriteContext, generate_request_id, get_git_sha

    SAFETY_ENABLED = True
except ImportError:
    SAFETY_ENABLED = False
    WriteContext = None

logger = logging.getLogger(__name__)

# Router
spec_router = APIRouter(tags=["Spec v2.9"])

# Database path
DB_PATH = paths.db_path()


def get_db() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db_with_context(
    actor: str,
    request_id: str | None = None,
    source: str = "api",
) -> Generator[sqlite3.Connection, None, None]:
    """
    Get database connection with write context for attributed writes.

    Usage:
        with get_db_with_context(actor="user123", request_id="req-xxx") as conn:
            conn.execute("UPDATE ...")
            conn.commit()
    """
    conn = get_db()
    try:
        if SAFETY_ENABLED and WriteContext:
            with WriteContext(conn, actor=actor, source=source, request_id=request_id):
                yield conn
        else:
            yield conn
    finally:
        conn.close()


def get_request_id(
    x_request_id: str | None = Header(None, alias="X-Request-Id"),
) -> str:
    """Get or generate request ID from header."""
    if x_request_id:
        return x_request_id
    if SAFETY_ENABLED:
        return generate_request_id()
    return f"req-{now_iso()}"


# ==== Request/Response Models ====


class InboxActionRequest(BaseModel):
    action: str
    assign_to: str | None = None
    snooze_days: int | None = None
    link_engagement_id: str | None = None
    select_candidate_id: str | None = None
    note: str | None = None


class IssueTransitionRequest(BaseModel):
    action: str
    assigned_to: str | None = None
    snooze_days: int | None = None
    note: str | None = None


# ==== Client Endpoints (§7.1-7.3, 7.9) ====


@spec_router.get("/clients", response_model=ClientIndexResponse)
async def get_clients(
    status: str | None = Query(None, description="Filter by status: active|recently_active|cold"),
    tier: str | None = Query(None, description="Filter by tier"),
    has_issues: bool | None = Query(None, description="Filter clients with open issues"),
    has_overdue_ar: bool | None = Query(None, description="Filter clients with overdue AR"),
):
    """
    GET /api/v2/clients

    Spec: 7.1 Client Index
    """
    conn = get_db()
    try:
        endpoints = ClientEndpoints(conn)
        filters: dict[str, str | bool] = {}
        if status:
            filters["status"] = status
        if tier:
            filters["tier"] = tier
        if has_issues:
            filters["has_issues"] = has_issues
        if has_overdue_ar:
            filters["has_overdue_ar"] = has_overdue_ar

        return endpoints.get_clients(filters)
    finally:
        conn.close()


@spec_router.get("/clients/{client_id}", response_model=DetailResponse)
async def get_client_detail(
    client_id: str,
    include: str | None = Query(None, description="Comma-separated sections to include"),
):
    """
    GET /api/v2/clients/:id

    Spec: 7.2 Active Client Detail, 7.9 Include Policy
    """
    conn = get_db()
    try:
        endpoints = ClientEndpoints(conn)
        include_sections = include.split(",") if include else None
        result, error_code = endpoints.get_client_detail(client_id, include_sections)
        if error_code:
            detail = result.get("error", "Error") if result else "Error"
            raise HTTPException(status_code=error_code, detail=detail)
        if not result:
            raise HTTPException(status_code=404, detail="Client not found")
        return result
    finally:
        conn.close()


@spec_router.get("/clients/{client_id}/snapshot", response_model=DetailResponse)
async def get_client_snapshot(
    client_id: str,
    context_issue_id: str | None = Query(None),
    context_inbox_item_id: str | None = Query(None),
):
    """
    GET /api/v2/clients/:id/snapshot

    Spec: 7.3 Client Snapshot (Cold clients from Inbox)
    """
    conn = get_db()
    try:
        endpoints = ClientEndpoints(conn)
        result = endpoints.get_client_snapshot(
            client_id,
            context_issue_id=context_issue_id,
            context_inbox_item_id=context_inbox_item_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Client not found")
        return result
    finally:
        conn.close()


# ==== Financials Endpoints (§7.5) ====


@spec_router.get("/clients/{client_id}/invoices", response_model=InvoiceListResponse)
async def get_client_invoices(
    client_id: str,
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    """
    GET /api/v2/clients/:id/invoices

    Spec: 7.5 Financials
    """
    conn = get_db()
    try:
        endpoints = FinancialsEndpoints(conn)
        return endpoints.get_invoices(client_id, {"status": status, "page": page, "limit": limit})
    finally:
        conn.close()


@spec_router.get("/clients/{client_id}/ar-aging", response_model=DetailResponse)
async def get_client_ar_aging(client_id: str):
    """
    GET /api/v2/clients/:id/ar-aging

    Spec: 7.5 AR Aging Breakdown
    """
    conn = get_db()
    try:
        endpoints = FinancialsEndpoints(conn)
        return endpoints.get_ar_aging(client_id)
    finally:
        conn.close()


# ==== Inbox Endpoints (§7.10) ====


@spec_router.get("/inbox", response_model=InboxResponse)
async def get_inbox(
    state: str | None = Query(None, description="Filter by state: proposed|snoozed"),
    type: str | None = Query(
        None, description="Filter by type: issue|flagged_signal|orphan|ambiguous"
    ),
    severity: str | None = Query(None, description="Filter by severity"),
    client_id: str | None = Query(None, description="Filter by client"),
    unread_only: bool | None = Query(None, description="Only unread items"),
    sort: str | None = Query("severity", description="Sort by: severity|age|age_desc|client"),
):
    """
    GET /api/v2/inbox

    Spec: 7.10 Control Room Inbox

    Returns inbox items with counts. Counts are always global (ignore filters).
    """
    # Validate state param
    if state and state not in ("proposed", "snoozed"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_state",
                "message": "state must be 'proposed' or 'snoozed'",
            },
        )

    conn = get_db()
    try:
        endpoints = InboxEndpoints(conn)
        filters = {}
        if state:
            filters["state"] = state
        if type:
            filters["type"] = type
        if severity:
            filters["severity"] = severity
        if client_id:
            filters["client_id"] = client_id
        if unread_only:
            filters["unread_only"] = unread_only
        if sort:
            filters["sort"] = sort

        return endpoints.get_inbox(filters)
    finally:
        conn.close()


@spec_router.get("/inbox/recent", response_model=InboxRecentResponse)
async def get_inbox_recent(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    state: str | None = Query(
        None, description="Filter by terminal state: linked_to_issue|dismissed"
    ),
    type: str | None = Query(None, description="Filter by type"),
):
    """
    GET /api/v2/inbox/recent

    Spec: 7.10 Recently Actioned Tab
    """
    conn = get_db()
    try:
        endpoints = InboxEndpoints(conn)
        filters = {}
        if state:
            filters["state"] = state
        if type:
            filters["type"] = type

        return endpoints.get_recent(days, filters)
    finally:
        conn.close()


@spec_router.get("/inbox/counts", response_model=InboxCountsResponse)
async def get_inbox_counts():
    """
    GET /api/v2/inbox/counts

    Spec: 7.10 Recommended separate counts endpoint (cacheable)
    """
    conn = get_db()
    try:
        endpoints = InboxEndpoints(conn)
        return endpoints._get_counts()
    finally:
        conn.close()


@spec_router.post("/inbox/{item_id}/action", response_model=MutationResponse)
async def execute_inbox_action(
    item_id: str,
    request: InboxActionRequest,
    actor: str = Query(..., description="User ID performing the action"),
    request_id: str = Depends(get_request_id),
):
    """
    POST /api/v2/inbox/:id/action

    Spec: 7.10 Inbox Actions

    All writes are attributed via write_context and audited.
    """
    with get_db_with_context(actor=actor, request_id=request_id, source="api") as conn:
        endpoints = InboxEndpoints(conn)

        payload = {
            "assign_to": request.assign_to,
            "snooze_days": request.snooze_days,
            "link_engagement_id": request.link_engagement_id,
            "select_candidate_id": request.select_candidate_id,
            "note": request.note,
        }
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        result, error_code = endpoints.execute_action(item_id, request.action, payload, actor)

        if error_code:
            raise HTTPException(status_code=error_code, detail=result)

        conn.commit()

        # Add request_id to response for traceability
        if isinstance(result, dict):
            result["request_id"] = request_id

        return result


@spec_router.post("/inbox/{item_id}/read", response_model=MutationResponse)
async def mark_inbox_read(
    item_id: str,
    actor: str = Query(..., description="User ID marking as read"),
    request_id: str = Depends(get_request_id),
):
    """
    POST /api/v2/inbox/:id/read

    Spec: 1.10 Mark Read
    """
    with get_db_with_context(actor=actor, request_id=request_id, source="api") as conn:
        lifecycle = InboxLifecycleManager(conn)
        success = lifecycle.mark_read(item_id, actor)

        if not success:
            raise HTTPException(status_code=404, detail="Inbox item not found or already terminal")

        conn.commit()
        return {"success": True, "read_at": now_iso(), "request_id": request_id}


# ==== Issue Endpoints (§7.6) ====


@spec_router.get("/issues", response_model=ListResponse)
async def get_issues(
    client_id: str | None = Query(None, description="Filter by client"),
    state: str | None = Query(None, description="Filter by state"),
    severity: str | None = Query(None, description="Filter by severity"),
    include_snoozed: bool = Query(False, description="Include snoozed issues"),
    include_suppressed: bool = Query(False, description="Include suppressed issues"),
):
    """
    GET /api/v2/issues

    Spec: 7.6 Issues
    """
    conn = get_db()
    try:
        # Build query
        where = ["1=1"]
        params = []

        if client_id:
            where.append("client_id = ?")
            params.append(client_id)

        if state:
            where.append("state = ?")
            params.append(state)
        else:
            # Default: open states only
            if not include_snoozed:
                where.append("state != 'snoozed'")
            where.append("state NOT IN ('closed', 'regression_watch')")

        if severity:
            where.append("severity = ?")
            params.append(severity)

        if not include_suppressed:
            where.append("(suppressed = 0 OR suppressed IS NULL)")

        cursor = conn.execute(
            f"""
            SELECT * FROM issues_v29
            WHERE {" AND ".join(where)}
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 5
                    WHEN 'high' THEN 4
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 2
                    WHEN 'info' THEN 1
                END DESC,
                created_at ASC
        """,  # noqa: S608
            params,
        )

        issues = []
        for row in cursor.fetchall():
            issue = dict(row)
            # Add available_actions
            try:
                issue["available_actions"] = AVAILABLE_ACTIONS.get(IssueState(issue["state"]), [])
            except ValueError:
                issue["available_actions"] = []
            issues.append(issue)

        return {"items": issues, "total": len(issues)}
    finally:
        conn.close()


@spec_router.get("/issues/{issue_id}", response_model=DetailResponse)
async def get_issue(issue_id: str):
    """
    GET /api/v2/issues/:id

    Spec: 7.6 Issue Detail
    """
    conn = get_db()
    try:
        lifecycle = IssueLifecycleManager(conn)
        issue = lifecycle.get_issue(issue_id)

        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Add available_actions
        try:
            issue["available_actions"] = AVAILABLE_ACTIONS.get(IssueState(issue["state"]), [])
        except ValueError:
            issue["available_actions"] = []

        return issue
    finally:
        conn.close()


@spec_router.post("/issues/{issue_id}/transition", response_model=MutationResponse)
async def transition_issue(
    issue_id: str,
    request: IssueTransitionRequest,
    actor: str = Query(..., description="User ID performing the action"),
    request_id: str = Depends(get_request_id),
):
    """
    POST /api/v2/issues/:id/transition

    Spec: 7.6 Issue Transitions
    """
    with get_db_with_context(actor=actor, request_id=request_id, source="api") as conn:
        lifecycle = IssueLifecycleManager(conn)

        payload = {
            "assigned_to": request.assigned_to,
            "snooze_days": request.snooze_days,
            "note": request.note,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        success, error = lifecycle.transition(issue_id, request.action, actor, payload)

        if not success:
            raise HTTPException(
                status_code=400, detail={"error": "transition_failed", "message": error}
            )

        conn.commit()

        # Get updated issue
        issue = lifecycle.get_issue(issue_id)
        return {
            "success": True,
            "issue_id": issue_id,
            "new_state": issue["state"] if issue else None,
            "request_id": request_id,
        }


# ==== Signals Endpoints (§7.7) ====


@spec_router.get("/clients/{client_id}/signals", response_model=SignalListResponse)
async def get_client_signals(
    client_id: str,
    sentiment: str | None = Query(None, description="Filter: good|neutral|bad|all"),
    source: str | None = Query(None, description="Filter by source"),
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    GET /api/v2/clients/:id/signals

    Spec: 7.7 Signals
    """
    conn = get_db()
    try:
        import json

        from lib.ui_spec_v21.time_utils import DEFAULT_ORG_TZ, window_start

        cutoff = window_start(DEFAULT_ORG_TZ, days)

        # Build query
        where = ["client_id = ?", "observed_at >= ?"]
        params = [client_id, cutoff.isoformat()]

        if sentiment and sentiment != "all":
            where.append("sentiment = ?")
            params.append(sentiment)

        if source:
            where.append("source = ?")
            params.append(source)

        where_clause = " AND ".join(where)

        # Get summary
        cursor = conn.execute(
            f"""
            SELECT sentiment, source, COUNT(*) as count
            FROM signals_v29
            WHERE {where_clause.replace("sentiment = ?", "1=1").replace("source = ?", "1=1")}
            GROUP BY sentiment, source
        """,  # noqa: S608
            [client_id, cutoff.isoformat()],
        )

        summary = {"good": 0, "neutral": 0, "bad": 0, "by_source": {}}
        for row in cursor.fetchall():
            sent, src, count = row
            summary[sent] = summary.get(sent, 0) + count
            if src not in summary["by_source"]:
                summary["by_source"][src] = {"good": 0, "neutral": 0, "bad": 0}
            summary["by_source"][src][sent] = count

        # Get paginated signals
        offset = (page - 1) * limit
        cursor = conn.execute(
            f"""
            SELECT * FROM signals_v29
            WHERE {where_clause}
            ORDER BY observed_at DESC
            LIMIT ? OFFSET ?
        """,  # noqa: S608
            params + [limit, offset],
        )

        signals = []
        for row in cursor.fetchall():
            signal = dict(row)
            if signal.get("evidence"):
                try:
                    signal["evidence"] = json.loads(signal["evidence"])
                except (json.JSONDecodeError, TypeError) as e:
                    # Internal data - malformed evidence indicates storage issue
                    logger.warning(
                        f"Signal {signal.get('signal_id')} has invalid evidence JSON: {e}"
                    )
            signals.append(signal)

        # Get total
        cursor = conn.execute(
            f"""
            SELECT COUNT(*) FROM signals_v29 WHERE {where_clause}
        """,  # noqa: S608
            params,
        )
        total = cursor.fetchone()[0]

        return {"summary": summary, "signals": signals, "total": total, "page": page}
    finally:
        conn.close()


# ==== Team Endpoints (§7.8) ====


@spec_router.get("/clients/{client_id}/team", response_model=TeamInvolvementResponse)
async def get_client_team(client_id: str, days: int = Query(30, ge=1, le=365)):
    """
    GET /api/v2/clients/:id/team

    Spec: 7.8 Team
    """
    conn = get_db()
    try:
        from lib.ui_spec_v21.time_utils import DEFAULT_ORG_TZ, window_start

        window_start(DEFAULT_ORG_TZ, days)

        # Get team members involved with this client
        # This is a simplified query - actual implementation would join with tasks/engagements
        cursor = conn.execute(
            """
            SELECT DISTINCT tm.id, tm.name, tm.role, tm.email,
                   COUNT(CASE WHEN t.completed = 0 THEN 1 END) as open_tasks,
                   COUNT(CASE WHEN t.completed = 0 AND t.due_date < date('now') THEN 1 END) as overdue_tasks
            FROM team_members tm
            LEFT JOIN tasks t ON t.assignee_id = tm.id AND t.client_id = ?
            WHERE tm.client_id = ? OR t.client_id = ?
            GROUP BY tm.id
            ORDER BY tm.name
        """,
            (client_id, client_id, client_id),
        )

        involvement = []
        for row in cursor.fetchall():
            involvement.append(
                {
                    "user_id": row[0],
                    "name": row[1],
                    "role": row[2] or "Team Member",
                    "email": row[3],
                    "open_tasks": row[4] or 0,
                    "overdue_tasks": row[5] or 0,
                }
            )

        return {"involvement": involvement, "total": len(involvement)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/team", response_model=ListResponse)
async def get_team():
    """
    GET /api/v2/team

    Returns all team members with workload metrics.
    """
    conn = get_db()
    try:
        # Query people table (internal team members)
        cursor = conn.execute("""
            SELECT p.id, p.name, p.email, p.role, p.department, p.company,
                   p.type, p.client_id,
                   (SELECT COUNT(*) FROM tasks t WHERE t.assignee = p.name AND t.status NOT IN ('done', 'completed', 'archived')) as open_tasks,
                   (SELECT COUNT(*) FROM tasks t WHERE t.assignee = p.name AND t.status NOT IN ('done', 'completed', 'archived') AND t.due_date < date('now')) as overdue_tasks,
                   (SELECT COUNT(*) FROM tasks t WHERE t.assignee = p.name AND t.status NOT IN ('done', 'completed', 'archived') AND t.due_date = date('now')) as due_today,
                   (SELECT COUNT(*) FROM tasks t WHERE t.assignee = p.name AND t.status IN ('done', 'completed') AND t.completed_at >= date('now', '-7 days')) as completed_this_week,
                   (SELECT c.name FROM clients c WHERE c.id = p.client_id) as client_name
            FROM people p
            WHERE p.type = 'internal' OR p.company LIKE '%hrmny%'
            ORDER BY open_tasks DESC, p.name
            LIMIT 100
        """)

        items = []
        for row in cursor.fetchall():
            items.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "role": row[3],
                    "department": row[4],
                    "company": row[5],
                    "type": row[6] or "internal",
                    "client_id": row[7],
                    "open_tasks": row[8] or 0,
                    "overdue_tasks": row[9] or 0,
                    "due_today": row[10] or 0,
                    "completed_this_week": row[11] or 0,
                    "client_name": row[12],
                }
            )

        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


# ==== Engagement Endpoints (§7.4, §7.11) ====


@spec_router.get("/engagements", response_model=EngagementListResponse)
async def get_engagements(
    client_id: str | None = Query(None),
    state: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    GET /api/v2/engagements

    Spec: 7.4 Engagements
    """
    conn = get_db()
    try:
        from lib.ui_spec_v21.engagement_lifecycle import (
            AVAILABLE_ACTIONS,
            EngagementState,
        )

        where = ["1=1"]
        params: list = []

        if client_id:
            where.append("client_id = ?")
            params.append(client_id)

        if state:
            where.append("state = ?")
            params.append(state)

        if type:
            where.append("type = ?")
            params.append(type)

        where_clause = " AND ".join(where)

        cursor = conn.execute(
            f"""
            SELECT * FROM engagements
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """,  # noqa: S608
            params + [limit, offset],
        )

        engagements = []
        for row in cursor.fetchall():
            eng = dict(row)
            # Add available_actions
            try:
                eng["available_actions"] = AVAILABLE_ACTIONS.get(EngagementState(eng["state"]), [])
            except ValueError:
                eng["available_actions"] = []
            engagements.append(eng)

        # Get total count
        cursor = conn.execute(
            f"""
            SELECT COUNT(*) FROM engagements WHERE {where_clause}
        """,  # noqa: S608
            params,
        )
        total = cursor.fetchone()[0]

        return {
            "engagements": engagements,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/engagements/{engagement_id}", response_model=DetailResponse)
async def get_engagement(engagement_id: str):
    """
    GET /api/v2/engagements/:id

    Spec: 7.4 Engagement Detail
    """
    conn = get_db()
    try:
        from lib.ui_spec_v21.engagement_lifecycle import (
            AVAILABLE_ACTIONS,
            EngagementLifecycleManager,
            EngagementState,
        )

        lifecycle = EngagementLifecycleManager(conn)
        engagement = lifecycle.get_engagement(engagement_id)

        if not engagement:
            raise HTTPException(status_code=404, detail="Engagement not found")

        # Add available_actions
        try:
            engagement["available_actions"] = AVAILABLE_ACTIONS.get(
                EngagementState(engagement["state"]), []
            )
        except ValueError:
            engagement["available_actions"] = []

        # Add transition history
        engagement["transition_history"] = lifecycle.get_transition_history(engagement_id, limit=10)

        return engagement
    finally:
        conn.close()


class EngagementTransitionRequest(BaseModel):
    action: str
    note: str | None = None


@spec_router.post("/engagements/{engagement_id}/transition", response_model=MutationResponse)
async def transition_engagement(
    engagement_id: str, request: EngagementTransitionRequest, actor: str = Query("user")
):
    """
    POST /api/v2/engagements/:id/transition

    Spec: 7.11 Engagement Lifecycle Actions
    """
    conn = get_db()
    try:
        from lib.ui_spec_v21.engagement_lifecycle import EngagementLifecycleManager

        lifecycle = EngagementLifecycleManager(conn)
        result = lifecycle.execute_action(
            engagement_id=engagement_id,
            action=request.action,
            actor=actor,
            note=request.note,
        )

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        # Get updated engagement
        lifecycle.get_engagement(engagement_id)

        return {
            "success": True,
            "engagement_id": engagement_id,
            "previous_state": result.previous_state,
            "new_state": result.new_state,
            "transition_id": result.transition_id,
        }
    finally:
        conn.close()


# ==== Health Check ====


@spec_router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    conn = get_db()
    try:
        cursor = conn.execute("SELECT 1")
        cursor.fetchone()
        return {"status": "healthy", "spec_version": "v2.9", "timestamp": now_iso()}
    except (sqlite3.Error, ValueError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    finally:
        conn.close()


# ==== Scheduled Jobs ====


@spec_router.post("/jobs/snooze-expiry", response_model=MutationResponse)
async def run_snooze_expiry_job():
    """
    Run snooze expiry job.

    Spec: 6.5 Snooze Timer Execution

    Should be called hourly by a scheduler.
    """
    conn = get_db()
    try:
        # Inbox snooze expiry
        inbox_lifecycle = InboxLifecycleManager(conn)
        inbox_count = inbox_lifecycle.process_snooze_expiry()

        # Issue snooze expiry
        issue_lifecycle = IssueLifecycleManager(conn)
        issue_count = issue_lifecycle.process_snooze_expiry()

        conn.commit()

        return {
            "success": True,
            "inbox_items_resurfaced": inbox_count,
            "issues_resurfaced": issue_count,
            "timestamp": now_iso(),
        }
    finally:
        conn.close()


@spec_router.post("/jobs/regression-watch", response_model=MutationResponse)
async def run_regression_watch_job():
    """
    Run regression watch expiry job.

    Spec: 6.5 Regression Watch (90-day)

    Should be called daily by a scheduler.
    """
    conn = get_db()
    try:
        lifecycle = IssueLifecycleManager(conn)
        closed_count, regressed_count = lifecycle.process_regression_watch()

        conn.commit()

        return {
            "success": True,
            "issues_closed": closed_count,
            "issues_regressed": regressed_count,
            "timestamp": now_iso(),
        }
    finally:
        conn.close()


# ==== Alias Endpoints for Frontend Compatibility ====


@spec_router.get("/priorities", response_model=ListResponse)
async def get_priorities_v2(limit: int = Query(20), context: str | None = Query(None)):
    """
    GET /api/v2/priorities

    Alias to /api/priorities for frontend compatibility.
    """
    conn = get_db()
    try:
        # Query tasks ordered by priority (INTEGER 0-100)
        query = """
            SELECT t.id, t.title, t.status, t.priority, t.due_date, t.assignee,
                   t.project_id, p.name as project_name, t.client_id, c.name as client_name
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN clients c ON t.client_id = c.id
            WHERE t.status NOT IN ('done', 'completed', 'archived', 'cancelled')
            ORDER BY t.priority DESC, t.due_date ASC NULLS LAST
            LIMIT ?
        """
        cursor = conn.execute(query, (limit,))  # noqa: S608
        items = [dict(row) for row in cursor.fetchall()]
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("get_priorities_v2 failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/projects", response_model=ListResponse)
async def get_projects_v2(limit: int = Query(50), status: str | None = Query(None)):
    """
    GET /api/v2/projects

    Alias to /api/projects for frontend compatibility.
    """
    conn = get_db()
    try:
        where = ["1=1"]
        params: list[str | int] = []

        if status:
            where.append("p.status = ?")
            params.append(status)

        query = f"""
            SELECT p.id, p.name, p.status, p.client_id, c.name as client_name,
                   p.created_at, p.updated_at
            FROM projects p
            LEFT JOIN clients c ON p.client_id = c.id
            WHERE {" AND ".join(where)}
            ORDER BY p.updated_at DESC NULLS LAST
            LIMIT ?
        """  # noqa: S608
        params.append(limit)
        cursor = conn.execute(query, params)  # noqa: S608
        items = [dict(row) for row in cursor.fetchall()]
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("get_projects_v2 failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/events", response_model=ListResponse)
async def get_events_v2(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(50),
):
    """
    GET /api/v2/events

    Alias to /api/events for frontend compatibility.
    """
    conn = get_db()
    try:
        where = ["1=1"]
        params: list[str | int] = []

        if start_date:
            where.append("start_time >= ?")
            params.append(start_date)
        if end_date:
            where.append("start_time <= ?")
            params.append(end_date)

        query = f"""
            SELECT id, title, start_time, end_time, location, status, source
            FROM events
            WHERE {" AND ".join(where)}
            ORDER BY start_time ASC
            LIMIT ?
        """  # noqa: S608
        params.append(limit)
        cursor = conn.execute(query, params)  # noqa: S608
        items = [dict(row) for row in cursor.fetchall()]
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/invoices", response_model=ListResponse)
async def get_invoices_v2(
    status: str | None = Query(None),
    client_id: str | None = Query(None),
    limit: int = Query(50),
):
    """
    GET /api/v2/invoices

    Global invoices endpoint for frontend compatibility.
    """
    conn = get_db()
    try:
        where = ["1=1"]
        params: list[str | int] = []

        if status:
            where.append("status = ?")
            params.append(status)
        if client_id:
            where.append("client_id = ?")
            params.append(client_id)

        query = f"""
            SELECT id, source_id, client_id, client_name, status,
                   amount, currency, issue_date, due_date, payment_date
            FROM invoices
            WHERE {" AND ".join(where)}
            ORDER BY issue_date DESC NULLS LAST
            LIMIT ?
        """  # noqa: S608
        params.append(limit)
        cursor = conn.execute(query, params)  # noqa: S608
        items = [dict(row) for row in cursor.fetchall()]
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/proposals", response_model=ListResponse)
async def get_proposals_v2(
    limit: int = Query(20),
    status: str = Query("open"),
    days: int = Query(7),
    client_id: str | None = Query(None),
):
    """
    GET /api/v2/proposals
    """
    conn = get_db()
    try:
        # Query proposals_v4 table
        where = ["1=1"]
        params: list[str | int] = []

        if status:
            where.append("status = ?")
            params.append(status)

        if client_id:
            where.append("client_id = ?")
            params.append(client_id)

        query = f"""
            SELECT proposal_id, proposal_type, primary_ref_type, primary_ref_id,
                   headline, score, status, first_seen_at, last_seen_at,
                   client_id, client_name, client_tier, scope_level, scope_name
            FROM proposals_v4
            WHERE {" AND ".join(where)}
            ORDER BY score DESC
            LIMIT ?
        """  # noqa: S608
        params.append(limit)
        cursor = conn.execute(query, params)  # noqa: S608
        items = []
        for row in cursor.fetchall():
            item = dict(row)
            # Add required fields with defaults
            item["impact"] = {
                "severity": "medium",
                "signal_count": 1,
                "entity_type": item.get("primary_ref_type", ""),
            }
            item["occurrence_count"] = 1
            item["trend"] = "flat"
            item["ui_exposure_level"] = "normal"
            items.append(item)
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/watchers", response_model=ListResponse)
async def get_watchers_v2(hours: int = Query(24)):
    """
    GET /api/v2/watchers
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            SELECT w.watcher_id, w.issue_id, w.watch_type, w.triggered_at, w.trigger_count,
                   i.headline as issue_title, i.state, i.priority
            FROM watchers w
            LEFT JOIN issues i ON w.issue_id = i.issue_id
            WHERE w.triggered_at IS NOT NULL
            AND w.triggered_at >= datetime('now', '-' || ? || ' hours')
            ORDER BY w.triggered_at DESC
            LIMIT 20
        """,
            (hours,),
        )
        items = [dict(row) for row in cursor.fetchall()]
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("get_watchers_v2 failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/couplings", response_model=ListResponse)
async def get_couplings_v2(
    anchor_type: str | None = Query(None),
    anchor_id: str | None = Query(None),
):
    """
    GET /api/v2/couplings
    """
    conn = get_db()
    try:
        where = ["1=1"]
        params = []

        if anchor_type and anchor_id:
            where.append("anchor_ref_type = ? AND anchor_ref_id = ?")
            params.extend([anchor_type, anchor_id])

        cursor = conn.execute(
            f"""
            SELECT coupling_id, anchor_ref_type, anchor_ref_id, entity_refs,
                   coupling_type, strength, why, confidence
            FROM entity_links
            WHERE {" AND ".join(where)}
            ORDER BY strength DESC
            LIMIT 50
        """,  # noqa: S608
            params,
        )
        items = []
        # Import safe JSON parsing
        from lib.safety import TrustMeta, parse_json_field

        for row in cursor.fetchall():
            item = dict(row)
            trust = TrustMeta()

            # Parse JSON fields with trust tracking (no silent failures)
            item["entity_refs"] = parse_json_field(
                item,
                "entity_refs",
                default=[],
                trust=trust,
                item_id_field="coupling_id",
            )
            item["why"] = parse_json_field(
                item, "why", default={}, trust=trust, item_id_field="coupling_id"
            )

            # Add trust metadata if there were parse failures
            if not trust.data_integrity:
                item["meta"] = {"trust": trust.to_dict()}

            items.append(item)
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/fix-data", response_model=FixDataResponse)
async def get_fix_data_v2():
    """
    GET /api/v2/fix-data
    """
    conn = get_db()
    try:
        # Query identity conflicts
        cursor = conn.execute("""
            SELECT id, display_name, source, confidence_score
            FROM identities
            WHERE confidence_score < 0.8
            LIMIT 20
        """)
        identity_conflicts = [dict(row) for row in cursor.fetchall()]

        # Query ambiguous links
        cursor = conn.execute("""
            SELECT link_id AS id, from_artifact_id AS entity_id,
                   to_entity_type AS linked_type, to_entity_id AS linked_id,
                   confidence
            FROM entity_links
            WHERE confidence < 0.7
            LIMIT 20
        """)
        ambiguous_links = [dict(row) for row in cursor.fetchall()]

        return {
            "identity_conflicts": identity_conflicts,
            "ambiguous_links": ambiguous_links,
            "missing_mappings": [],
            "total": len(identity_conflicts) + len(ambiguous_links),
        }
    except (sqlite3.Error, ValueError) as e:
        logger.error("handler failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


# ==== Intelligence Endpoints ====
# These wire the intelligence layer into /api/v2/intelligence/*
# The UI expects all responses wrapped: {status, data, computed_at, params}


def _proposal_type_to_issue_type(proposal_type: str) -> str:
    """Map proposal_type from proposals_v4 to valid issues_v29 type."""
    mapping = {
        "risk": "risk",
        "opportunity": "financial",
        "request": "communication",
        "decision_needed": "schedule_delivery",
        "anomaly": "risk",
        "compliance": "risk",
    }
    return mapping.get(proposal_type, "risk")


def _intel_response(data: object, params: dict | None = None) -> dict:
    """Wrap intelligence data in the envelope the UI expects."""
    return {
        "status": "ok",
        "data": data,
        "computed_at": now_iso(),
        "params": params or {},
    }


def _intel_error(message: str, params: dict | None = None) -> dict:
    """Return an error envelope."""
    return {
        "status": "error",
        "data": None,
        "computed_at": now_iso(),
        "params": params or {},
        "error": message,
    }


@spec_router.get("/intelligence/critical", response_model=IntelligenceResponse)
async def get_critical_items():
    """
    GET /api/v2/intelligence/critical

    Returns IMMEDIATE urgency proposals for the Command Center.
    """
    try:
        from lib.intelligence.engine import get_critical_items as _get_critical

        items = _get_critical()
        return _intel_response(items)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence critical items error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/briefing", response_model=IntelligenceResponse)
async def get_briefing():
    """
    GET /api/v2/intelligence/briefing

    Returns daily briefing with proposals grouped by urgency and portfolio health.
    """
    try:
        from lib.intelligence.engine import generate_intelligence_snapshot

        snapshot = generate_intelligence_snapshot()

        proposals_data = snapshot.get("proposals", {})
        portfolio_score = snapshot.get("scores", {}).get("portfolio", {})

        # Shape the briefing to match the UI's Briefing type
        result = {
            "generated_at": snapshot.get("generated_at", now_iso()),
            "summary": {
                "total_proposals": proposals_data.get("total", 0),
                "immediate_count": len(proposals_data.get("by_urgency", {}).get("immediate", [])),
                "this_week_count": len(proposals_data.get("by_urgency", {}).get("this_week", [])),
                "monitor_count": len(proposals_data.get("by_urgency", {}).get("monitor", [])),
            },
            "critical_items": proposals_data.get("by_urgency", {}).get("immediate", []),
            "attention_items": proposals_data.get("by_urgency", {}).get("this_week", []),
            "watching": proposals_data.get("by_urgency", {}).get("monitor", []),
            "portfolio_health": {
                "overall_score": portfolio_score.get("composite_score", 0),
                "active_structural_patterns": len(
                    snapshot.get("patterns", {}).get("structural", [])
                ),
                "trend": "stable",
            },
            "top_proposal": (
                proposals_data.get("ranked", [{}])[0].get("headline", "")
                if proposals_data.get("ranked")
                else ""
            ),
        }
        return _intel_response(result)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence briefing error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/signals", response_model=IntelligenceResponse)
async def get_intelligence_signals(
    quick: bool = Query(True, description="Quick detection mode"),
):
    """
    GET /api/v2/intelligence/signals

    Runs signal detection and returns all detected signals.
    """
    try:
        from lib.intelligence.signals import detect_all_signals

        detection = detect_all_signals(quick=quick)
        signals = detection.get("signals", [])
        return _intel_response(
            {"signals": signals, "total_signals": len(signals)},
            params={"quick": quick},
        )
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence signals error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/signals/summary", response_model=IntelligenceResponse)
async def get_intelligence_signal_summary():
    """
    GET /api/v2/intelligence/signals/summary

    Returns aggregate signal counts by severity and entity type.
    """
    try:
        from lib.intelligence.signals import get_signal_summary

        summary = get_signal_summary()
        return _intel_response(summary)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence signal summary error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/signals/active", response_model=IntelligenceResponse)
async def get_intelligence_active_signals(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
):
    """
    GET /api/v2/intelligence/signals/active

    Returns currently active signals, optionally filtered by entity.
    """
    try:
        from lib.intelligence.signals import get_active_signals

        signals = get_active_signals(entity_type=entity_type, entity_id=entity_id)
        return _intel_response(signals, params={"entity_type": entity_type, "entity_id": entity_id})
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence active signals error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/signals/history", response_model=IntelligenceResponse)
async def get_intelligence_signal_history(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
):
    """
    GET /api/v2/intelligence/signals/history

    Returns signal history for a specific entity.
    """
    try:
        from lib.intelligence.signals import get_signal_history

        history = get_signal_history(entity_type=entity_type, entity_id=entity_id)
        # Apply limit
        limited = history[:limit] if isinstance(history, list) else history
        return _intel_response(
            limited,
            params={"entity_type": entity_type, "entity_id": entity_id, "limit": limit},
        )
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence signal history error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/patterns", response_model=IntelligenceResponse)
async def get_intelligence_patterns():
    """
    GET /api/v2/intelligence/patterns

    Detects and returns all active patterns.
    """
    try:
        from lib.intelligence.patterns import detect_all_patterns

        detection = detect_all_patterns()
        patterns = detection.get("patterns", [])
        return _intel_response(
            {"patterns": patterns, "total_detected": len(patterns)},
        )
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence patterns error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/patterns/catalog", response_model=IntelligenceResponse)
async def get_intelligence_pattern_catalog():
    """
    GET /api/v2/intelligence/patterns/catalog

    Returns the pattern library — all defined patterns with descriptions.
    """
    try:
        from lib.intelligence.patterns import PATTERN_LIBRARY

        catalog = []
        for pat_id, pat in PATTERN_LIBRARY.items():
            catalog.append(
                {
                    "id": pat_id,
                    "name": pat.name,
                    "type": pat.pattern_type.value
                    if hasattr(pat.pattern_type, "value")
                    else str(pat.pattern_type),
                    "severity": pat.severity.value
                    if hasattr(pat.severity, "value")
                    else str(pat.severity),
                    "description": pat.description,
                    "implied_action": pat.implied_action,
                }
            )
        return _intel_response(catalog)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence pattern catalog error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/proposals", response_model=IntelligenceResponse)
async def get_intelligence_proposals(
    limit: int = Query(20, ge=1, le=100),
    urgency: str | None = Query(None, description="Filter by urgency: immediate|this_week|monitor"),
):
    """
    GET /api/v2/intelligence/proposals

    Generates, ranks, and returns proposals.
    """
    try:
        from lib.intelligence.patterns import detect_all_patterns
        from lib.intelligence.proposals import generate_proposals, rank_proposals
        from lib.intelligence.signals import detect_all_signals

        signals = detect_all_signals(quick=True)
        patterns = detect_all_patterns()

        signal_input = {"signals": signals.get("signals", [])}
        pattern_input = {"patterns": patterns.get("patterns", [])}

        proposals = generate_proposals(signal_input, pattern_input)
        ranked = rank_proposals(proposals)

        results = []
        for p, s in ranked[:limit]:
            item = p.to_dict()
            item["priority_score"] = s.to_dict()
            if urgency and p.urgency.value != urgency:
                continue
            results.append(item)

        return _intel_response(results[:limit], params={"limit": limit, "urgency": urgency})
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence proposals error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/scores/client/{client_id}", response_model=IntelligenceResponse)
async def get_client_score(client_id: str):
    """
    GET /api/v2/intelligence/scores/client/:id

    Returns scorecard for a specific client.
    """
    try:
        from lib.intelligence.scorecard import score_client

        scorecard = score_client(client_id)
        scorecard["computed_at"] = now_iso()
        return _intel_response(scorecard)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence client score error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/scores/project/{project_id}", response_model=IntelligenceResponse)
async def get_project_score(project_id: str):
    """
    GET /api/v2/intelligence/scores/project/:id

    Returns scorecard for a specific project.
    """
    try:
        from lib.intelligence.scorecard import score_project

        scorecard = score_project(project_id)
        scorecard["computed_at"] = now_iso()
        return _intel_response(scorecard)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence project score error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/scores/person/{person_id}", response_model=IntelligenceResponse)
async def get_person_score(person_id: str):
    """
    GET /api/v2/intelligence/scores/person/:id

    Returns scorecard for a specific person.
    """
    try:
        from lib.intelligence.scorecard import score_person

        scorecard = score_person(person_id)
        scorecard["computed_at"] = now_iso()
        return _intel_response(scorecard)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence person score error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/scores/portfolio", response_model=IntelligenceResponse)
async def get_portfolio_score():
    """
    GET /api/v2/intelligence/scores/portfolio

    Returns scorecard for the entire portfolio.
    """
    try:
        from lib.intelligence.scorecard import score_portfolio

        scorecard = score_portfolio()
        scorecard["computed_at"] = now_iso()
        return _intel_response(scorecard)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence portfolio score error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/entity/client/{client_id}", response_model=IntelligenceResponse)
async def get_client_intelligence(client_id: str):
    """
    GET /api/v2/intelligence/entity/client/:id

    Deep dive: scorecard + signals + history + trajectory + proposals for a client.
    """
    try:
        from lib.intelligence.engine import get_client_intelligence as _get_client_intel

        intel = _get_client_intel(client_id)
        return _intel_response(intel)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence client entity error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/entity/person/{person_id}", response_model=IntelligenceResponse)
async def get_person_intelligence(person_id: str):
    """
    GET /api/v2/intelligence/entity/person/:id

    Deep dive: scorecard + signals + history + profile for a person.
    """
    try:
        from lib.intelligence.engine import get_person_intelligence as _get_person_intel

        intel = _get_person_intel(person_id)
        return _intel_response(intel)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence person entity error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/entity/portfolio", response_model=IntelligenceResponse)
async def get_portfolio_intelligence():
    """
    GET /api/v2/intelligence/entity/portfolio

    Portfolio-level: score + signal summary + structural patterns + top proposals.
    """
    try:
        from lib.intelligence.engine import get_portfolio_intelligence as _get_portfolio_intel

        intel = _get_portfolio_intel()
        return _intel_response(intel)
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence portfolio entity error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/projects/{project_id}/state", response_model=IntelligenceResponse)
async def get_project_state(project_id: str):
    """
    GET /api/v2/intelligence/projects/:id/state

    Returns operational state for a project.
    """
    try:
        from lib.query_engine import QueryEngine

        engine = QueryEngine()
        state = engine.project_operational_state(project_id)
        if not state:
            raise HTTPException(status_code=404, detail="Project not found")
        return _intel_response(state)
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence project state error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/clients/{client_id}/profile", response_model=IntelligenceResponse)
async def get_client_profile(client_id: str):
    """
    GET /api/v2/intelligence/clients/:id/profile

    Returns deep operational profile for a client.
    """
    try:
        from lib.query_engine import QueryEngine

        engine = QueryEngine()
        profile = engine.client_deep_profile(client_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Client not found")
        return _intel_response(profile)
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence client profile error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/team/{person_id}/profile", response_model=IntelligenceResponse)
async def get_person_profile(person_id: str):
    """
    GET /api/v2/intelligence/team/:id/profile

    Returns operational profile for a person.
    """
    try:
        from lib.query_engine import QueryEngine

        engine = QueryEngine()
        profile = engine.person_operational_profile(person_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Person not found")
        return _intel_response(profile)
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence person profile error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get(
    "/intelligence/clients/{client_id}/trajectory", response_model=IntelligenceResponse
)
async def get_client_trajectory(
    client_id: str,
    window_days: int = Query(30, ge=7, le=90),
    num_windows: int = Query(6, ge=2, le=12),
):
    """
    GET /api/v2/intelligence/clients/:id/trajectory

    Returns rolling-window metrics and trends for a client.
    """
    try:
        from lib.query_engine import QueryEngine

        engine = QueryEngine()
        trajectory = engine.client_trajectory(
            client_id, window_size_days=window_days, num_windows=num_windows
        )
        return _intel_response(
            trajectory,
            params={"window_days": window_days, "num_windows": num_windows},
        )
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence client trajectory error: {e}", exc_info=True)
        return _intel_error(str(e))


@spec_router.get("/intelligence/team/{person_id}/trajectory", response_model=IntelligenceResponse)
async def get_person_trajectory(
    person_id: str,
    window_days: int = Query(30, ge=7, le=90),
    num_windows: int = Query(6, ge=2, le=12),
):
    """
    GET /api/v2/intelligence/team/:id/trajectory

    Returns rolling-window load metrics and trends for a person.
    """
    try:
        from lib.query_engine import QueryEngine

        engine = QueryEngine()
        trajectory = engine.person_trajectory(
            person_id, window_size_days=window_days, num_windows=num_windows
        )
        return _intel_response(
            trajectory,
            params={"window_days": window_days, "num_windows": num_windows},
        )
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Intelligence person trajectory error: {e}", exc_info=True)
        return _intel_error(str(e))


# ==== Mutation Endpoints (Proposals, Watchers, Fix-Data, Issues) ====


class SnoozeRequest(BaseModel):
    days: int = 7


class DismissRequest(BaseModel):
    reason: str = "Dismissed by user"


class WatcherDismissRequest(BaseModel):
    actor: str = "system"


class WatcherSnoozeRequest(BaseModel):
    hours: int = 24
    actor: str = "system"


class FixDataResolveRequest(BaseModel):
    resolution: str = "manually_resolved"
    actor: str = "system"


class CreateIssueRequest(BaseModel):
    proposal_id: str
    actor: str = "system"


class IssueNoteRequest(BaseModel):
    text: str
    actor: str = "system"


class IssueResolveRequest(BaseModel):
    resolution: str = "manually_resolved"
    actor: str = "system"


class IssueStateChangeRequest(BaseModel):
    state: str
    reason: str | None = None
    actor: str = "system"


@spec_router.post("/proposals/{proposal_id}/snooze", response_model=MutationResponse)
async def snooze_proposal(proposal_id: str, request: SnoozeRequest):
    """
    POST /api/v2/proposals/:id/snooze

    Snooze a proposal for N days.
    """
    conn = get_db()
    try:
        from datetime import datetime, timedelta

        snooze_until = (datetime.now() + timedelta(days=request.days)).isoformat()
        cursor = conn.execute(
            "UPDATE proposals_v4 SET status = 'snoozed', snoozed_until = ? WHERE proposal_id = ?",
            (snooze_until, proposal_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proposal not found")
        conn.commit()
        return {"success": True, "proposal_id": proposal_id, "snoozed_until": snooze_until}
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Snooze proposal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.post("/proposals/{proposal_id}/dismiss", response_model=MutationResponse)
async def dismiss_proposal(proposal_id: str, request: DismissRequest):
    """
    POST /api/v2/proposals/:id/dismiss

    Dismiss a proposal.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE proposals_v4 SET status = 'dismissed', dismissed_reason = ? WHERE proposal_id = ?",
            (request.reason, proposal_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proposal not found")
        conn.commit()
        return {"success": True, "proposal_id": proposal_id}
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Dismiss proposal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.post("/watchers/{watcher_id}/dismiss", response_model=MutationResponse)
async def dismiss_watcher(watcher_id: str, request: WatcherDismissRequest):
    """
    POST /api/v2/watchers/:id/dismiss

    Dismiss a watcher.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE watchers SET active = 0, last_checked_at = ? WHERE watcher_id = ?",
            (now_iso(), watcher_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Watcher not found")
        conn.commit()
        return {"success": True, "watcher_id": watcher_id}
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Dismiss watcher error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.post("/watchers/{watcher_id}/snooze", response_model=MutationResponse)
async def snooze_watcher(watcher_id: str, request: WatcherSnoozeRequest):
    """
    POST /api/v2/watchers/:id/snooze

    Snooze a watcher for N hours.
    """
    conn = get_db()
    try:
        from datetime import datetime, timedelta

        snooze_until = (datetime.now() + timedelta(hours=request.hours)).isoformat()
        cursor = conn.execute(
            "UPDATE watchers SET next_check_at = ?, last_checked_at = ? WHERE watcher_id = ?",
            (snooze_until, now_iso(), watcher_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Watcher not found")
        conn.commit()
        return {"success": True, "watcher_id": watcher_id, "snoozed_until": snooze_until}
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Snooze watcher error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.post("/fix-data/{item_type}/{item_id}/resolve", response_model=MutationResponse)
async def resolve_fix_data(item_type: str, item_id: str, request: FixDataResolveRequest):
    """
    POST /api/v2/fix-data/:type/:id/resolve

    Resolve a fix-data item (identity conflict or ambiguous link).
    """
    conn = get_db()
    try:
        if item_type == "identity":
            cursor = conn.execute(
                "UPDATE identities SET confidence_score = 1.0 WHERE id = ?",
                (item_id,),
            )
        elif item_type == "link":
            cursor = conn.execute(
                "UPDATE entity_links SET confidence = 1.0, status = 'confirmed', confirmed_by = ?, confirmed_at = ? WHERE link_id = ?",
                (request.actor, now_iso(), item_id),
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown item_type: {item_type}")

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"{item_type} not found: {item_id}")
        conn.commit()
        return {"success": True, "item_type": item_type, "item_id": item_id}
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Resolve fix-data error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.post("/issues", response_model=MutationResponse)
async def create_issue_from_proposal(request: CreateIssueRequest):
    """
    POST /api/v2/issues

    Create an issue from a proposal.
    """
    conn = get_db()
    try:
        import json

        # Get proposal data
        cursor = conn.execute(
            "SELECT * FROM proposals_v4 WHERE proposal_id = ?",
            (request.proposal_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")

        proposal = dict(row)

        # Use IssueLifecycleManager to create issue with correct schema
        lifecycle = IssueLifecycleManager(conn)
        issue_id = lifecycle.create_issue(
            issue_type=_proposal_type_to_issue_type(proposal.get("proposal_type", "risk")),
            severity=proposal.get("severity", "medium"),
            title=proposal.get("headline", "Issue from proposal"),
            evidence={
                "source": "proposal",
                "proposal_id": request.proposal_id,
                "signal_ids": json.loads(proposal.get("signal_ids", "[]")),
            },
            client_id=proposal.get("client_id", "unknown"),
        )

        # Update proposal status to accepted
        conn.execute(
            "UPDATE proposals_v4 SET status = 'accepted' WHERE proposal_id = ?",
            (request.proposal_id,),
        )

        conn.commit()

        issue = lifecycle.get_issue(issue_id)
        return {
            "success": True,
            "issue": {
                "issue_id": issue_id,
                "headline": issue.get("title") if issue else proposal.get("headline"),
                "state": issue.get("state", "detected") if issue else "detected",
                "severity": issue.get("severity", "medium") if issue else "medium",
            },
        }
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Create issue error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.post("/issues/{issue_id}/notes", response_model=MutationResponse)
async def add_issue_note(issue_id: str, request: IssueNoteRequest):
    """
    POST /api/v2/issues/:id/notes

    Add a note to an issue.
    """
    conn = get_db()
    try:
        import uuid

        # Verify issue exists
        cursor = conn.execute("SELECT issue_id FROM issues_v29 WHERE issue_id = ?", (issue_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Issue not found")

        note_id = f"note-{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO item_history (id, item_id, timestamp, change, changed_by)
            VALUES (?, ?, ?, ?, ?)
        """,
            (note_id, issue_id, now_iso(), request.text, request.actor),
        )
        conn.commit()
        return {"success": True, "note_id": note_id}
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Add issue note error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


# ==== Issue Shape Compatibility Endpoints ====
# The UI calls PATCH /issues/:id/resolve and PATCH /issues/:id/state
# The backend has POST /issues/:id/transition — these aliases bridge the gap.


@spec_router.patch("/issues/{issue_id}/resolve", response_model=MutationResponse)
async def resolve_issue(issue_id: str, request: IssueResolveRequest):
    """
    PATCH /api/v2/issues/:id/resolve

    Resolves an issue. Translates to the existing transition logic.
    """
    conn = get_db()
    try:
        lifecycle = IssueLifecycleManager(conn)

        payload = {"note": request.resolution}
        success, error = lifecycle.transition(issue_id, "resolve", request.actor, payload)

        if not success:
            raise HTTPException(
                status_code=400, detail={"error": "resolve_failed", "message": error}
            )

        conn.commit()
        issue = lifecycle.get_issue(issue_id)
        return {
            "success": True,
            "issue_id": issue_id,
            "state": issue["state"] if issue else "resolved",
        }
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Resolve issue error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.patch("/issues/{issue_id}/state", response_model=MutationResponse)
async def change_issue_state(issue_id: str, request: IssueStateChangeRequest):
    """
    PATCH /api/v2/issues/:id/state

    Changes issue state. Maps to the existing transition logic.
    """
    conn = get_db()
    try:
        lifecycle = IssueLifecycleManager(conn)

        # Map state to action: the IssueLifecycleManager uses action names like
        # "resolve", "snooze", "reopen", "close", "acknowledge", "block"
        # The UI sends target state names. We map common states to actions.
        state_to_action = {
            "resolved": "resolve",
            "closed": "close",
            "open": "reopen",
            "monitoring": "acknowledge",
            "blocked": "block",
            "awaiting": "snooze",
        }
        action = state_to_action.get(request.state, request.state)

        payload = {}
        if request.reason:
            payload["note"] = request.reason

        success, error = lifecycle.transition(issue_id, action, request.actor, payload)

        if not success:
            raise HTTPException(
                status_code=400, detail={"error": "state_change_failed", "message": error}
            )

        conn.commit()
        issue = lifecycle.get_issue(issue_id)
        return {
            "success": True,
            "issue_id": issue_id,
            "state": issue["state"] if issue else request.state,
        }
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Change issue state error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()


@spec_router.get("/evidence/{entity_type}/{entity_id}", response_model=ListResponse)
async def get_evidence_v2(entity_type: str, entity_id: str):
    """
    GET /api/v2/evidence/{entity_type}/{entity_id}
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            SELECT e.id, e.artifact_id, e.excerpt_text, e.context_json, e.created_at,
                   a.source, a.type as artifact_type, a.occurred_at
            FROM item_history e
            LEFT JOIN communications a ON e.artifact_id = a.id
            WHERE e.item_type = ? AND e.item_id = ?
            ORDER BY e.created_at DESC
            LIMIT 20
        """,
            (entity_type, entity_id),
        )
        items = [dict(row) for row in cursor.fetchall()]
        return {"items": items, "total": len(items)}
    except (sqlite3.Error, ValueError) as e:
        logger.error("get_evidence_v2 failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()
