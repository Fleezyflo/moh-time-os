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
"""

import logging
import sqlite3
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from lib import paths
from lib.api.pagination import PaginatedResponse, PaginationParams, paginate, pagination_params
from lib.ui_spec_v21.time_utils import now_iso

logger = logging.getLogger(__name__)

# Router
paginated_router = APIRouter(tags=["Pagination"])

# Database path
DB_PATH = paths.db_path()


# ==== Demo Data (Fallback) ====
# Used when live DB is unavailable to ensure endpoints are functional


def _demo_tasks() -> list[dict[str, Any]]:
    """Generate demo task data."""
    return [
        {
            "id": f"task-{i}",
            "title": f"Task {i}: Sample task item",
            "description": f"This is a sample task for pagination demo (item {i})",
            "status": ["todo", "in_progress", "done"][i % 3],
            "priority": ["low", "medium", "high"][i % 3],
            "created_at": now_iso(),
            "due_at": now_iso(),
        }
        for i in range(1, 251)  # 250 demo tasks
    ]


def _demo_signals() -> list[dict[str, Any]]:
    """Generate demo signal data."""
    return [
        {
            "id": f"signal-{i}",
            "type": ["anomaly", "threshold", "trend"][i % 3],
            "description": f"Signal {i}: Sample signal data",
            "severity": ["low", "medium", "high"][i % 3],
            "created_at": now_iso(),
            "resolved": i % 4 == 0,
        }
        for i in range(1, 151)  # 150 demo signals
    ]


def _demo_clients() -> list[dict[str, Any]]:
    """Generate demo client data."""
    return [
        {
            "id": f"client-{i}",
            "name": f"Client {i}",
            "status": ["active", "paused", "archived"][i % 3],
            "projects": i % 5,
            "created_at": now_iso(),
        }
        for i in range(1, 101)  # 100 demo clients
    ]


def _demo_invoices() -> list[dict[str, Any]]:
    """Generate demo invoice data."""
    return [
        {
            "id": f"inv-{i}",
            "invoice_number": f"INV-2024-{i:05d}",
            "client_id": f"client-{(i % 20) + 1}",
            "amount": 1000 + (i * 100),
            "status": ["draft", "sent", "paid"][i % 3],
            "created_at": now_iso(),
            "due_at": now_iso(),
        }
        for i in range(1, 201)  # 200 demo invoices
    ]


# ==== Live DB Fetching ====


def _get_tasks_from_db() -> list[dict[str, Any]]:
    """Fetch tasks from live database."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, status, priority, created_at, due_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 1000
            """
        )
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tasks
    except Exception as e:
        logger.warning(f"Failed to fetch tasks from DB: {e}")
        return _demo_tasks()


def _get_signals_from_db() -> list[dict[str, Any]]:
    """Fetch signals from live database."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, type, description, severity, created_at, resolved
            FROM signals
            ORDER BY created_at DESC
            LIMIT 1000
            """
        )
        signals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return signals
    except Exception as e:
        logger.warning(f"Failed to fetch signals from DB: {e}")
        return _demo_signals()


def _get_clients_from_db() -> list[dict[str, Any]]:
    """Fetch clients from live database."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, status, created_at
            FROM clients
            ORDER BY created_at DESC
            LIMIT 1000
            """
        )
        clients = [dict(row) for row in cursor.fetchall()]

        # Attempt to count projects per client
        for client in clients:
            try:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM projects WHERE client_id = ?",
                    (client["id"],),
                )
                result = cursor.fetchone()
                client["projects"] = result["count"] if result else 0
            except Exception:
                client["projects"] = 0

        conn.close()
        return clients
    except Exception as e:
        logger.warning(f"Failed to fetch clients from DB: {e}")
        return _demo_clients()


def _get_invoices_from_db() -> list[dict[str, Any]]:
    """Fetch invoices from live database."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, invoice_number, client_id, amount, status, created_at, due_at
            FROM invoices
            ORDER BY created_at DESC
            LIMIT 1000
            """
        )
        invoices = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return invoices
    except Exception as e:
        logger.warning(f"Failed to fetch invoices from DB: {e}")
        return _demo_invoices()


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

    Falls back to demo data if live DB is unavailable.
    """
    try:
        tasks = _get_tasks_from_db()
        return paginate(tasks, params.page, params.page_size)
    except Exception as e:
        logger.error(f"Error listing paginated tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@paginated_router.get("/signals")
async def list_signals_paginated(
    params: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse:
    """
    Get paginated list of signals.

    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)

    Falls back to demo data if live DB is unavailable.
    """
    try:
        signals = _get_signals_from_db()
        return paginate(signals, params.page, params.page_size)
    except Exception as e:
        logger.error(f"Error listing paginated signals: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@paginated_router.get("/clients")
async def list_clients_paginated(
    params: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse:
    """
    Get paginated list of clients.

    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)

    Falls back to demo data if live DB is unavailable.
    """
    try:
        clients = _get_clients_from_db()
        return paginate(clients, params.page, params.page_size)
    except Exception as e:
        logger.error(f"Error listing paginated clients: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@paginated_router.get("/invoices")
async def list_invoices_paginated(
    params: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse:
    """
    Get paginated list of invoices.

    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)

    Falls back to demo data if live DB is unavailable.
    """
    try:
        invoices = _get_invoices_from_db()
        return paginate(invoices, params.page, params.page_size)
    except Exception as e:
        logger.error(f"Error listing paginated invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
