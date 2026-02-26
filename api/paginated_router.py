"""
Paginated API Router — Heavy Endpoint Pagination

This router adds paginated versions of large endpoints that return
many items. Mount this on the main FastAPI app.

Usage in server.py:
    from api.paginated_router import paginated_router
    app.include_router(paginated_router, prefix="/api/v2/paginated")

Endpoints:
- GET /api/v2/paginated/tasks — Paginated task list
- GET /api/v2/paginated/signals — Paginated signals
- GET /api/v2/paginated/clients — Paginated client list
- GET /api/v2/paginated/invoices — Paginated invoice list

All endpoints query the live database. No fallback data — if the DB is
unreachable or the table is missing, the endpoint returns an error.
"""

import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from lib import paths
from lib.api.pagination import PaginatedResponse, PaginationParams, paginate, pagination_params

logger = logging.getLogger(__name__)

# Router
paginated_router = APIRouter(tags=["Pagination"])

# Database path
DB_PATH = paths.db_path()


# ==== Database Helpers ====


def _get_connection() -> sqlite3.Connection:
    """Get a DB connection or raise."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error("Failed to connect to database at %s: %s", DB_PATH, e)
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {e}",
        ) from e


def _query_table(
    table: str,
    columns: str,
    order_by: str = "created_at DESC",
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Query a table and return rows as dicts. Raises on failure."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # Table and column names are hardcoded strings from this file,
        # not user input — safe to use directly.
        cursor.execute(
            f"SELECT {columns} FROM {table} ORDER BY {order_by} LIMIT ?",  # noqa: S608
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        logger.error("Query failed on table '%s': %s", table, e)
        raise HTTPException(
            status_code=503,
            detail=f"Database query failed ({table}): {e}",
        ) from e
    finally:
        conn.close()


# ==== Live DB Fetching ====


def _get_tasks_from_db() -> list[dict[str, Any]]:
    """Fetch tasks from live database."""
    return _query_table(
        table="tasks",
        columns="id, title, description, status, priority, created_at, due_at",
    )


def _get_signals_from_db() -> list[dict[str, Any]]:
    """Fetch signals from live database."""
    return _query_table(
        table="signals",
        columns="id, type, description, severity, created_at, resolved",
    )


def _get_clients_from_db() -> list[dict[str, Any]]:
    """Fetch clients from live database with project counts."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.id, c.name, c.status, c.created_at,
                   COALESCE(p.project_count, 0) AS projects
            FROM clients c
            LEFT JOIN (
                SELECT client_id, COUNT(*) AS project_count
                FROM projects
                GROUP BY client_id
            ) p ON p.client_id = c.id
            ORDER BY c.created_at DESC
            LIMIT 1000
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        logger.error("Query failed on clients: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Database query failed (clients): {e}",
        ) from e
    finally:
        conn.close()


def _get_invoices_from_db() -> list[dict[str, Any]]:
    """Fetch invoices from live database."""
    return _query_table(
        table="invoices",
        columns="id, invoice_number, client_id, amount, status, created_at, due_at",
    )


# ==== Endpoints ====


@paginated_router.get("/tasks")
async def list_tasks_paginated(
    params: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse:
    """
    Get paginated list of tasks.

    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)

    Returns 503 if database is unavailable.
    """
    tasks = _get_tasks_from_db()
    return paginate(tasks, params.page, params.page_size)


@paginated_router.get("/signals")
async def list_signals_paginated(
    params: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse:
    """
    Get paginated list of signals.

    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)

    Returns 503 if database is unavailable.
    """
    signals = _get_signals_from_db()
    return paginate(signals, params.page, params.page_size)


@paginated_router.get("/clients")
async def list_clients_paginated(
    params: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse:
    """
    Get paginated list of clients.

    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)

    Returns 503 if database is unavailable.
    """
    clients = _get_clients_from_db()
    return paginate(clients, params.page, params.page_size)


@paginated_router.get("/invoices")
async def list_invoices_paginated(
    params: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse:
    """
    Get paginated list of invoices.

    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)

    Returns 503 if database is unavailable.
    """
    invoices = _get_invoices_from_db()
    return paginate(invoices, params.page, params.page_size)
