"""
Time OS V4 - Proposal Aggregator

Aggregates signals into proposals at the appropriate hierarchy level:
- Client level: For client-wide issues or when multiple brands affected
- Brand level: When multiple projects under one brand have issues
- Project/Retainer level: Most common, for localized project issues

Hierarchy: Client → Brand → Project/Retainer → Task → Signal
"""

import json
import logging
import os
import sqlite3
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")

# Legacy filter: tasks overdue more than this many days are considered archived/legacy
# Signals from these tasks are excluded from proposals to avoid noise pollution
LEGACY_OVERDUE_THRESHOLD_DAYS = 365


def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(db_path or DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def get_signal_hierarchy(signal: dict, cursor: sqlite3.Cursor) -> dict[str, Any]:
    """
    Get full hierarchy chain for a signal: task → project → brand → client

    Strategy:
    1. Try to get hierarchy from database (tasks → projects → clients)
    2. If missing, extract from signal's value field (project_id, client_id)
    3. Look up project/client by ID or name

    Args:
        signal: Signal dict with entity_ref_type, entity_ref_id, and value
        cursor: Database cursor

    Returns:
        {
            'task_id': str or None,
            'task_title': str or None,
            'task_assignee': str or None,
            'project_id': str or None,
            'project_name': str or None,
            'engagement_type': 'project' or 'retainer' or None,
            'brand_id': str or None,
            'brand_name': str or None,
            'client_id': str or None,
            'client_name': str or None,
            'client_tier': str or None
        }
    """
    entity_type = signal.get("entity_ref_type", "")
    entity_id = signal.get("entity_ref_id", "")

    # Parse signal value for fallback hierarchy data
    value = signal.get("value", {})
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            # Signal value is internal data - malformed indicates detector/storage bug
            logger.warning(
                f"Signal {signal.get('signal_id')} has invalid value JSON: {e}"
            )
            value = {}

    result = {
        "task_id": None,
        "task_title": None,
        "task_assignee": None,
        "project_id": None,
        "project_name": None,
        "engagement_type": None,
        "brand_id": None,
        "brand_name": None,
        "client_id": None,
        "client_name": None,
        "client_tier": None,
    }

    if entity_type == "task":
        # Get task details from tasks table
        # NOTE: tasks table uses 'project' column which may be either a project ID or name
        # Use subquery to find project by ID first, then by name (picking first match for duplicates)
        cursor.execute(
            """
            SELECT t.id, t.title, t.assignee, t.project,
                   p.id as proj_id, p.name as proj_name, p.engagement_type,
                   p.client_id as proj_client_id, p.brand_id as proj_brand_id,
                   c.id as client_id, c.name as client_name, c.tier,
                   b.id as brand_id, b.name as brand_name
            FROM tasks t
            LEFT JOIN projects p ON p.id = (
                SELECT COALESCE(
                    (SELECT id FROM projects WHERE id = t.project LIMIT 1),
                    (SELECT id FROM projects WHERE name = t.project LIMIT 1)
                )
            )
            LEFT JOIN clients c ON p.client_id = c.id
            LEFT JOIN brands b ON p.brand_id = b.id
            WHERE t.id = ?
        """,
            (entity_id,),
        )
        row = cursor.fetchone()
        if row:
            result["task_id"] = row["id"]
            result["task_title"] = row["title"]
            result["task_assignee"] = row["assignee"]
            result["project_id"] = row[
                "proj_id"
            ]  # Always use the actual project ID from projects table
            result["project_name"] = row["proj_name"]
            result["engagement_type"] = row["engagement_type"] or "project"
            result["client_id"] = row["client_id"]
            result["client_name"] = row["client_name"]
            result["client_tier"] = row["tier"]
            result["brand_id"] = row["brand_id"]
            result["brand_name"] = row["brand_name"]

        # FALLBACK: If no project from DB, try signal value field
        if not result["project_id"] and value:
            val_project_id = value.get("project_id")
            val_project_name = value.get("project_name")
            val_client_id = value.get("client_id")

            # Try to look up project by ID or name
            if val_project_id:
                cursor.execute(
                    """
                    SELECT p.id, p.name, p.engagement_type, p.client_id, p.brand_id,
                           c.id as client_id, c.name as client_name, c.tier,
                           b.id as brand_id, b.name as brand_name
                    FROM projects p
                    LEFT JOIN clients c ON p.client_id = c.id
                    LEFT JOIN brands b ON p.brand_id = b.id
                    WHERE p.id = ? OR p.name = ? OR p.name_normalized = ?
                """,
                    (
                        val_project_id,
                        val_project_id,
                        val_project_id.lower() if val_project_id else "",
                    ),
                )
                proj_row = cursor.fetchone()
                if proj_row:
                    result["project_id"] = proj_row["id"]
                    result["project_name"] = proj_row["name"]
                    result["engagement_type"] = proj_row["engagement_type"] or "project"
                    result["client_id"] = proj_row["client_id"]
                    result["client_name"] = proj_row["client_name"]
                    result["client_tier"] = proj_row["tier"]
                    result["brand_id"] = proj_row["brand_id"]
                    result["brand_name"] = proj_row["brand_name"]
                else:
                    # Project not in DB - use value data directly
                    result["project_id"] = val_project_id
                    result["project_name"] = val_project_name or val_project_id

            # Try to look up client if we have client_id from value
            if not result["client_id"] and val_client_id:
                cursor.execute(
                    """
                    SELECT id, name, tier FROM clients WHERE id = ?
                """,
                    (val_client_id,),
                )
                client_row = cursor.fetchone()
                if client_row:
                    result["client_id"] = client_row["id"]
                    result["client_name"] = client_row["name"]
                    result["client_tier"] = client_row["tier"]

        # Use task title from value if not in DB
        if not result["task_title"] and value.get("title"):
            result["task_title"] = value.get("title")
        if not result["task_assignee"] and value.get("owner"):
            result["task_assignee"] = value.get("owner")

    elif entity_type == "project":
        # Get project and chain to client with brand
        cursor.execute(
            """
            SELECT p.id, p.name, p.engagement_type, p.client_id, p.brand_id,
                   c.id as client_id, c.name as client_name, c.tier,
                   b.id as brand_id, b.name as brand_name
            FROM projects p
            LEFT JOIN clients c ON p.client_id = c.id
            LEFT JOIN brands b ON p.brand_id = b.id
            WHERE p.id = ?
        """,
            (entity_id,),
        )
        row = cursor.fetchone()
        if row:
            result["project_id"] = row["id"]
            result["project_name"] = row["name"]
            result["engagement_type"] = row["engagement_type"] or "project"
            result["client_id"] = row["client_id"]
            result["client_name"] = row["client_name"]
            result["client_tier"] = row["tier"]
            result["brand_id"] = row["brand_id"]
            result["brand_name"] = row["brand_name"]

    elif entity_type == "client":
        # Get client directly
        cursor.execute(
            """
            SELECT id, name, tier FROM clients WHERE id = ?
        """,
            (entity_id,),
        )
        row = cursor.fetchone()
        if row:
            result["client_id"] = row["id"]
            result["client_name"] = row["name"]
            result["client_tier"] = row["tier"]

    return result


def group_signals_by_scope(
    db_path: str = None, exclude_legacy: bool = True
) -> dict[tuple[str, str], list[dict]]:
    """
    Group all active signals by their appropriate scope (project/client).

    Args:
        db_path: Database path (optional)
        exclude_legacy: If True, exclude signals from tasks overdue > LEGACY_OVERDUE_THRESHOLD_DAYS

    Returns:
        Dict mapping (scope_level, scope_id) to list of signals with hierarchy
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # Get all active signals, optionally excluding legacy ones
        if exclude_legacy:
            # Exclude signals from tasks that are overdue > LEGACY_OVERDUE_THRESHOLD_DAYS
            cursor.execute(f"""
                SELECT s.signal_id, s.signal_type, s.entity_ref_type, s.entity_ref_id,
                       s.value, s.severity, s.detected_at, s.interpretation_confidence
                FROM signals s
                LEFT JOIN tasks t ON s.entity_ref_type = 'task' AND s.entity_ref_id = t.id
                WHERE s.status = 'active'
                  AND (
                    s.entity_ref_type != 'task'
                    OR t.id IS NULL
                    OR t.due_date IS NULL
                    OR julianday('now') - julianday(t.due_date) <= {LEGACY_OVERDUE_THRESHOLD_DAYS}
                  )
            """)
        else:
            cursor.execute("""
                SELECT signal_id, signal_type, entity_ref_type, entity_ref_id,
                       value, severity, detected_at, interpretation_confidence
                FROM signals
                WHERE status = 'active'
            """)

        # Group signals with their hierarchy
        grouped = defaultdict(list)

        for row in cursor.fetchall():
            signal = dict(row)
            hierarchy = get_signal_hierarchy(signal, cursor)
            signal["hierarchy"] = hierarchy

            # Determine scope key
            if hierarchy["project_id"]:
                # Group by project
                scope_key = ("project", hierarchy["project_id"])
            elif hierarchy["client_id"]:
                # Client-level signal (no project)
                scope_key = ("client", hierarchy["client_id"])
            else:
                # Orphan signal - skip
                continue

            grouped[scope_key].append(signal)

        return dict(grouped)

    finally:
        conn.close()


def determine_proposal_level(
    client_id: str, grouped_signals: dict, db_path: str = None
) -> str:
    """
    Determine whether to create client-level or project-level proposals.

    Rules:
    - If client has client-level signals (AR, health) → client proposal
    - If >3 projects under client have issues → client-level
    - Otherwise → project-level

    Returns: 'client' or 'project'
    """
    # Check for client-level signals
    has_client_signals = ("client", client_id) in grouped_signals

    # Count projects with issues for this client
    project_count = 0
    for (scope_level, _scope_id), signals in grouped_signals.items():
        if scope_level != "project":
            continue
        # Check if this project belongs to the client
        for sig in signals:
            hierarchy = sig.get("hierarchy", {})
            if hierarchy.get("client_id") == client_id:
                project_count += 1
                break

    # Decision logic
    if has_client_signals or project_count > 3:
        return "client"

    return "project"


def build_signal_summary(signals: list[dict]) -> dict[str, Any]:
    """
    Build a summary of signals for display.

    Returns:
        {
            'total': int,
            'by_category': {
                'overdue': int,
                'approaching': int,
                'blocked': int,
                'health': int,
                'financial': int,
                'process': int,
                'other': int
            },
            'assignee_distribution': {'name': count, ...},
            'worst_urgency': float
        }
    """
    try:
        from .proposal_scoring import compute_urgency_score
    except ImportError:
        from proposal_scoring import compute_urgency_score

    summary = {
        "total": len(signals),
        "by_category": {
            "overdue": 0,
            "approaching": 0,
            "blocked": 0,
            "health": 0,
            "financial": 0,
            "process": 0,
            "other": 0,
        },
        "assignee_distribution": defaultdict(int),
        "worst_urgency": 0,
    }

    for sig in signals:
        sig_type = sig.get("signal_type", "")

        # Categorize
        if "overdue" in sig_type:
            summary["by_category"]["overdue"] += 1
        elif "approaching" in sig_type:
            summary["by_category"]["approaching"] += 1
        elif "blocked" in sig_type:
            summary["by_category"]["blocked"] += 1
        elif "health" in sig_type or "relationship" in sig_type:
            summary["by_category"]["health"] += 1
        elif "ar_" in sig_type or "invoice" in sig_type:
            summary["by_category"]["financial"] += 1
        elif "violation" in sig_type or "quality" in sig_type:
            summary["by_category"]["process"] += 1
        else:
            summary["by_category"]["other"] += 1

        # Track assignee
        hierarchy = sig.get("hierarchy", {})
        assignee = hierarchy.get("task_assignee") or "Unassigned"
        summary["assignee_distribution"][assignee] += 1

        # Track worst urgency
        urgency = compute_urgency_score(sig)
        if urgency > summary["worst_urgency"]:
            summary["worst_urgency"] = urgency

    # Convert defaultdict to regular dict
    summary["assignee_distribution"] = dict(summary["assignee_distribution"])

    return summary


def get_affected_task_ids(signals: list[dict]) -> list[str]:
    """Extract unique task IDs from signals."""
    task_ids = set()
    for sig in signals:
        hierarchy = sig.get("hierarchy", {})
        task_id = hierarchy.get("task_id")
        if task_id:
            task_ids.add(task_id)
    return list(task_ids)


def get_scope_info(
    scope_level: str, scope_id: str, signals: list[dict], db_path: str = None
) -> dict[str, Any]:
    """
    Get detailed info about the scope (project/client).

    Returns:
        {
            'scope_level': str,
            'scope_id': str,
            'scope_name': str,
            'client_id': str,
            'client_name': str,
            'client_tier': str,
            'brand_id': str or None,
            'brand_name': str or None,
            'engagement_type': str or None,
            'project_value': float or None
        }
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        result = {
            "scope_level": scope_level,
            "scope_id": scope_id,
            "scope_name": None,
            "client_id": None,
            "client_name": None,
            "client_tier": None,
            "brand_id": None,
            "brand_name": None,
            "engagement_type": None,
            "project_value": None,
        }

        if scope_level == "project":
            cursor.execute(
                """
                SELECT p.id, p.name, p.engagement_type, p.value,
                       p.client_id, c.name as client_name, c.tier
                FROM projects p
                LEFT JOIN clients c ON p.client_id = c.id
                WHERE p.id = ?
            """,
                (scope_id,),
            )
            row = cursor.fetchone()
            if row:
                result["scope_name"] = row["name"]
                result["client_id"] = row["client_id"]
                result["client_name"] = row["client_name"]
                result["client_tier"] = row["tier"]
                result["brand_id"] = None  # No brand support yet
                result["brand_name"] = None
                result["engagement_type"] = row["engagement_type"] or "project"
                result["project_value"] = row["value"]

        elif scope_level == "client":
            cursor.execute(
                """
                SELECT id, name, tier FROM clients WHERE id = ?
            """,
                (scope_id,),
            )
            row = cursor.fetchone()
            if row:
                result["scope_name"] = row["name"]
                result["client_id"] = row["id"]
                result["client_name"] = row["name"]
                result["client_tier"] = row["tier"]

        # Fallback: get info from first signal's hierarchy
        if not result["scope_name"] and signals:
            first_hierarchy = signals[0].get("hierarchy", {})
            if scope_level == "project":
                result["scope_name"] = first_hierarchy.get("project_name", scope_id)
            result["client_id"] = result["client_id"] or first_hierarchy.get(
                "client_id"
            )
            result["client_name"] = result["client_name"] or first_hierarchy.get(
                "client_name"
            )
            result["client_tier"] = result["client_tier"] or first_hierarchy.get(
                "client_tier"
            )

        return result

    finally:
        conn.close()


# Test
if __name__ == "__main__":
    logger.info("Testing signal aggregation...")
    grouped = group_signals_by_scope()
    logger.info(f"Found {len(grouped)} scope groups")
    # Show sample
    for (scope_level, scope_id), signals in list(grouped.items())[:3]:
        summary = build_signal_summary(signals)
        logger.info(f"\n{scope_level}: {scope_id[:20]}...")
        logger.info(f"  Signals: {summary['total']}")
        logger.info(f"  Categories: {summary['by_category']}")
