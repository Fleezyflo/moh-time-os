"""
DriftDetector -- detects clients with overdue tasks and zero completions.

Fires when: overdue_count > 0 AND completions_5d = 0
Task-to-client linking: tasks.project_id -> projects.client_id
Revenue queries use COALESCE with try/except for missing columns.
"""

import logging
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

COMPLETION_WINDOW_DAYS = 5
MEETING_STALE_DAYS = 21


def _business_days_ago(n: int) -> str:
    """Compute the date N business days ago."""
    current = date.today()
    counted = 0
    while counted < n:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            counted += 1
    return current.isoformat()


@dataclass
class DriftFinding:
    """A single client drift detection."""

    client_id: str
    client_name: str
    client_tier: str | None
    revenue_ytd: float | None
    revenue_lifetime: float | None
    financial_annual_value: float | None
    overdue_tasks: list[dict[str, Any]] = field(default_factory=list)
    overdue_count: int = 0
    completions_5d: int = 0
    assigned_team: list[dict[str, Any]] = field(default_factory=list)
    last_completion: dict[str, Any] | None = None
    last_meeting: dict[str, Any] | None = None
    days_since_last_meeting: int | None = None


class DriftDetector:
    """Detects clients whose tasks are past due and not moving."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def detect(self) -> list[DriftFinding]:
        """Run drift detection across all non-internal clients."""
        findings: list[DriftFinding] = []
        conn = self._get_conn()
        today = date.today()
        window_start = _business_days_ago(COMPLETION_WINDOW_DAYS)

        try:
            # Get all non-internal clients that have active projects
            cursor = conn.execute(
                """SELECT DISTINCT c.id, c.name, c.tier, c.financial_annual_value
                   FROM clients c
                   JOIN projects p ON p.client_id = c.id
                   WHERE p.is_internal != 1 AND p.status = 'active'"""
            )
            clients = cursor.fetchall()

            for client in clients:
                client_id = client["id"]
                client_name = client["name"]

                # Count overdue tasks for this client
                cursor = conn.execute(
                    """SELECT t.id, t.title, t.assignee, t.due_date
                       FROM tasks t
                       JOIN projects p ON t.project_id = p.id
                       WHERE p.client_id = ?
                         AND t.status IN ('active', 'in_progress')
                         AND t.due_date < ?
                         AND t.due_date IS NOT NULL""",
                    (client_id, today.isoformat()),
                )
                overdue_tasks = [dict(row) for row in cursor.fetchall()]
                overdue_count = len(overdue_tasks)

                if overdue_count == 0:
                    continue  # No overdue tasks = no drift

                # Count completions in last 5 business days
                cursor = conn.execute(
                    """SELECT COUNT(*) as completions
                       FROM tasks t
                       JOIN projects p ON t.project_id = p.id
                       WHERE p.client_id = ?
                         AND t.status = 'done'
                         AND t.updated_at > ?""",
                    (client_id, window_start),
                )
                completions_row = cursor.fetchone()
                completions_5d = completions_row["completions"] if completions_row else 0

                # Drift fires when overdue > 0 AND completions = 0
                if completions_5d > 0:
                    continue

                # Revenue data (graceful fallback for missing columns)
                revenue_ytd = None
                revenue_lifetime = None
                try:
                    cursor = conn.execute(
                        """SELECT COALESCE(ytd_revenue, 0) as ytd_rev,
                                  COALESCE(lifetime_revenue, 0) as lifetime_rev
                           FROM clients WHERE id = ?""",
                        (client_id,),
                    )
                    rev_row = cursor.fetchone()
                    if rev_row:
                        revenue_ytd = rev_row["ytd_rev"]
                        revenue_lifetime = rev_row["lifetime_rev"]
                except sqlite3.OperationalError:
                    # Revenue columns don't exist yet -- graceful fallback
                    logger.debug("Revenue columns not available for client %s", client_id)

                # Enrich overdue tasks with days_overdue
                for task in overdue_tasks:
                    due = task.get("due_date")
                    if due:
                        try:
                            days_overdue = (today - date.fromisoformat(due[:10])).days
                            task["days_overdue"] = days_overdue
                        except (ValueError, TypeError):
                            task["days_overdue"] = None

                # Assigned team members and their load
                cursor = conn.execute(
                    """SELECT t.assignee, COUNT(*) as active_count
                       FROM tasks t
                       JOIN projects p ON t.project_id = p.id
                       WHERE p.client_id = ?
                         AND t.status IN ('active', 'in_progress')
                         AND t.assignee IS NOT NULL
                       GROUP BY t.assignee""",
                    (client_id,),
                )
                assigned_team = []
                for row in cursor.fetchall():
                    # Get total active for this person
                    total_cursor = conn.execute(
                        """SELECT COUNT(*) as total
                           FROM tasks
                           WHERE assignee = ?
                             AND status IN ('active', 'in_progress')""",
                        (row["assignee"],),
                    )
                    total_row = total_cursor.fetchone()
                    assigned_team.append(
                        {
                            "name": row["assignee"],
                            "client_tasks": row["active_count"],
                            "total_active": total_row["total"] if total_row else 0,
                        }
                    )

                # Last completion for this client
                cursor = conn.execute(
                    """SELECT t.title, t.assignee, t.updated_at
                       FROM tasks t
                       JOIN projects p ON t.project_id = p.id
                       WHERE p.client_id = ?
                         AND t.status = 'done'
                       ORDER BY t.updated_at DESC
                       LIMIT 1""",
                    (client_id,),
                )
                last_comp_row = cursor.fetchone()
                last_completion = dict(last_comp_row) if last_comp_row else None

                # Last meeting (search by client name in event title)
                last_meeting = None
                days_since = None
                cursor = conn.execute(
                    """SELECT e.start_time, e.title
                       FROM events e
                       WHERE e.title LIKE '%' || ? || '%'
                       ORDER BY e.start_time DESC
                       LIMIT 1""",
                    (client_name,),
                )
                meeting_row = cursor.fetchone()
                if meeting_row and meeting_row["start_time"]:
                    last_meeting = dict(meeting_row)
                    try:
                        meeting_date = datetime.fromisoformat(meeting_row["start_time"]).date()
                        days_since = (today - meeting_date).days
                    except (ValueError, TypeError):
                        days_since = None

                findings.append(
                    DriftFinding(
                        client_id=client_id,
                        client_name=client_name,
                        client_tier=client["tier"],
                        revenue_ytd=revenue_ytd,
                        revenue_lifetime=revenue_lifetime,
                        financial_annual_value=client["financial_annual_value"],
                        overdue_tasks=overdue_tasks,
                        overdue_count=overdue_count,
                        completions_5d=completions_5d,
                        assigned_team=assigned_team,
                        last_completion=last_completion,
                        last_meeting=last_meeting,
                        days_since_last_meeting=days_since,
                    )
                )

        finally:
            conn.close()

        return findings

    def findings_to_dicts(self, findings: list[DriftFinding]) -> list[dict[str, Any]]:
        """Serialize findings for storage."""
        return [asdict(f) for f in findings]
