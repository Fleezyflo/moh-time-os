"""
BottleneckDetector -- detects team members who are piling up AND not completing.

Fires when: active_tasks > 2 * median_active AND completed_5d < median_completed
Also fires when: overdue_tasks > 2 * median_overdue AND overdue_tasks > 3

Absence exclusion: members with 0 calendar events for 3+ consecutive business days
(via events JOIN calendar_attendees) are excluded from median calculations.
"""

import logging
import sqlite3
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

COMPLETION_WINDOW_DAYS = 5
ABSENCE_CONSECUTIVE_DAYS = 3
OVERDUE_MINIMUM = 3


def _business_days_ago(n: int) -> str:
    """Compute the date N business days ago."""
    current = date.today()
    counted = 0
    while counted < n:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            counted += 1
    return current.isoformat()


def _get_recent_business_days(n: int) -> list[str]:
    """Get the last N business days as ISO strings (most recent first)."""
    days: list[str] = []
    current = date.today()
    while len(days) < n:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current -= timedelta(days=1)
    return days


def _safe_median(values: list[int | float]) -> float:
    """Compute median, returning 0.0 for empty list."""
    if not values:
        return 0.0
    return float(statistics.median(values))


@dataclass
class MemberStats:
    """Stats for one team member."""

    name: str
    email: str | None
    active_tasks: int = 0
    completed_5d: int = 0
    overdue_tasks: int = 0
    is_absent: bool = False
    absence_since: str | None = None


@dataclass
class BottleneckFinding:
    """A single bottleneck detection for one team member."""

    member_name: str
    member_email: str | None
    active_tasks: int
    completed_5d: int
    overdue_tasks: int
    median_active: float
    median_completed: float
    median_overdue: float
    trigger: str  # "load_throughput" or "overdue_spike"
    breakdown_by_client: list[dict[str, Any]] = field(default_factory=list)
    overdue_items: list[dict[str, Any]] = field(default_factory=list)
    peers_with_shared_clients: list[dict[str, Any]] = field(default_factory=list)
    excluded_members: list[dict[str, Any]] = field(default_factory=list)


class BottleneckDetector:
    """Detects team members whose work is piling up and not getting done."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def detect(self) -> list[BottleneckFinding]:
        """Run bottleneck detection across all team members."""
        conn = self._get_conn()
        today = date.today()
        window_start = _business_days_ago(COMPLETION_WINDOW_DAYS)

        try:
            # Get all team members
            cursor = conn.execute("SELECT id, name, email FROM team_members")
            members = cursor.fetchall()

            if not members:
                return []

            # Collect stats for each member
            all_stats: list[MemberStats] = []
            for member in members:
                stats = self._compute_member_stats(
                    conn, member["name"], member["email"], today, window_start
                )
                all_stats.append(stats)

            # Identify absent members
            absent_members = [s for s in all_stats if s.is_absent]
            active_members = [s for s in all_stats if not s.is_absent]

            if not active_members:
                return []

            # Compute medians from active (non-absent) members
            median_active = _safe_median([s.active_tasks for s in active_members])
            median_completed = _safe_median([s.completed_5d for s in active_members])
            median_overdue = _safe_median([s.overdue_tasks for s in active_members])

            # Build excluded list for findings
            excluded_list = [
                {"name": s.name, "absence_since": s.absence_since} for s in absent_members
            ]

            # Detect bottlenecks
            findings: list[BottleneckFinding] = []
            for stats in active_members:
                trigger = self._check_triggers(
                    stats, median_active, median_completed, median_overdue
                )
                if trigger is None:
                    continue

                # Get breakdown by client
                breakdown = self._get_client_breakdown(conn, stats.name)

                # Get overdue items
                overdue_items = self._get_overdue_items(conn, stats.name, today)

                # Get peers with shared clients
                peers = self._get_peers(conn, stats.name)

                findings.append(
                    BottleneckFinding(
                        member_name=stats.name,
                        member_email=stats.email,
                        active_tasks=stats.active_tasks,
                        completed_5d=stats.completed_5d,
                        overdue_tasks=stats.overdue_tasks,
                        median_active=round(median_active, 1),
                        median_completed=round(median_completed, 1),
                        median_overdue=round(median_overdue, 1),
                        trigger=trigger,
                        breakdown_by_client=breakdown,
                        overdue_items=overdue_items,
                        peers_with_shared_clients=peers,
                        excluded_members=excluded_list,
                    )
                )

            return findings

        finally:
            conn.close()

    def _compute_member_stats(
        self,
        conn: sqlite3.Connection,
        name: str,
        email: str | None,
        today: date,
        window_start: str,
    ) -> MemberStats:
        """Compute task stats for one team member."""
        stats = MemberStats(name=name, email=email)

        # Active tasks
        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE assignee = ? AND status IN ('active', 'in_progress')""",
            (name,),
        )
        row = cursor.fetchone()
        stats.active_tasks = row["cnt"] if row else 0

        # Completed in window
        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE assignee = ? AND status = 'done' AND updated_at > ?""",
            (name, window_start),
        )
        row = cursor.fetchone()
        stats.completed_5d = row["cnt"] if row else 0

        # Overdue tasks
        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE assignee = ?
                 AND status IN ('active', 'in_progress')
                 AND due_date < ?
                 AND due_date IS NOT NULL""",
            (name, today.isoformat()),
        )
        row = cursor.fetchone()
        stats.overdue_tasks = row["cnt"] if row else 0

        # Check absence: 0 calendar events for 3+ consecutive business days
        # Uses events JOIN calendar_attendees -- NEVER calendar_events
        if email:
            recent_days = _get_recent_business_days(ABSENCE_CONSECUTIVE_DAYS)
            if recent_days:
                earliest = recent_days[-1]  # oldest
                latest = recent_days[0]  # most recent
                cursor = conn.execute(
                    """SELECT COUNT(*) as event_count
                       FROM events e
                       JOIN calendar_attendees ca ON ca.event_id = e.id
                       WHERE ca.email = ?
                         AND date(e.start_time) >= ?
                         AND date(e.start_time) <= ?""",
                    (email, earliest, latest),
                )
                row = cursor.fetchone()
                event_count = row["event_count"] if row else 0

                if event_count == 0 and stats.completed_5d == 0:
                    stats.is_absent = True
                    stats.absence_since = earliest

        return stats

    def _check_triggers(
        self,
        stats: MemberStats,
        median_active: float,
        median_completed: float,
        median_overdue: float,
    ) -> str | None:
        """Check if bottleneck triggers fire. Returns trigger name or None."""
        # Trigger 1: high load + low throughput
        if median_active > 0 and stats.active_tasks > 2 * median_active:
            if stats.completed_5d < median_completed:
                return "load_throughput"

        # Trigger 2: overdue spike
        if median_overdue > 0 and stats.overdue_tasks > 2 * median_overdue:
            if stats.overdue_tasks > OVERDUE_MINIMUM:
                return "overdue_spike"

        return None

    def _get_client_breakdown(
        self, conn: sqlite3.Connection, assignee: str
    ) -> list[dict[str, Any]]:
        """Get task count by client for this person."""
        cursor = conn.execute(
            """SELECT c.id as client_id, c.name as client_name, COUNT(*) as task_count
               FROM tasks t
               JOIN projects p ON t.project_id = p.id
               JOIN clients c ON p.client_id = c.id
               WHERE t.assignee = ?
                 AND t.status IN ('active', 'in_progress')
               GROUP BY c.id
               ORDER BY task_count DESC""",
            (assignee,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_overdue_items(
        self, conn: sqlite3.Connection, assignee: str, today: date
    ) -> list[dict[str, Any]]:
        """Get overdue task details for this person."""
        cursor = conn.execute(
            """SELECT t.id, t.title, t.due_date, c.name as client_name, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               LEFT JOIN clients c ON p.client_id = c.id
               WHERE t.assignee = ?
                 AND t.status IN ('active', 'in_progress')
                 AND t.due_date < ?
                 AND t.due_date IS NOT NULL
               ORDER BY t.due_date""",
            (assignee, today.isoformat()),
        )
        items = []
        for row in cursor.fetchall():
            item = dict(row)
            due = item.get("due_date")
            if due:
                try:
                    item["days_overdue"] = (today - date.fromisoformat(due[:10])).days
                except (ValueError, TypeError):
                    item["days_overdue"] = None
            items.append(item)
        return items

    def _get_peers(self, conn: sqlite3.Connection, assignee: str) -> list[dict[str, Any]]:
        """Get peers who share clients with this person."""
        # Find clients this person works on
        cursor = conn.execute(
            """SELECT DISTINCT p.client_id
               FROM tasks t
               JOIN projects p ON t.project_id = p.id
               WHERE t.assignee = ?
                 AND t.status IN ('active', 'in_progress')
                 AND p.client_id IS NOT NULL""",
            (assignee,),
        )
        client_ids = [row["client_id"] for row in cursor.fetchall()]

        if not client_ids:
            return []

        peers: dict[str, dict[str, Any]] = {}
        for cid in client_ids:
            cursor = conn.execute(
                """SELECT t.assignee, c.name as client_name,
                          COUNT(*) as task_count
                   FROM tasks t
                   JOIN projects p ON t.project_id = p.id
                   JOIN clients c ON p.client_id = c.id
                   WHERE p.client_id = ?
                     AND t.assignee != ?
                     AND t.assignee IS NOT NULL
                     AND t.status IN ('active', 'in_progress')
                   GROUP BY t.assignee, c.name""",
                (cid, assignee),
            )
            for row in cursor.fetchall():
                peer_name = row["assignee"]
                if peer_name not in peers:
                    peers[peer_name] = {"name": peer_name, "shared_clients": []}
                peers[peer_name]["shared_clients"].append(
                    {
                        "client_name": row["client_name"],
                        "task_count": row["task_count"],
                    }
                )

        return list(peers.values())

    def findings_to_dicts(self, findings: list[BottleneckFinding]) -> list[dict[str, Any]]:
        """Serialize findings for storage."""
        return [asdict(f) for f in findings]
