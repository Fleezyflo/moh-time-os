"""
CollisionDetector -- detects days where open time cannot absorb work due.

Two detection paths:
- Path A (Molham): uses time_blocks for precise available minutes
- Path B (team members): available_minutes = 480 - meeting_minutes
  where meetings come from events JOIN calendar_attendees

Fires when weighted_ratio > 2.0 OR available_minutes = 0 with tasks due.
"""

import logging
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .task_weight import TaskWeightEngine

logger = logging.getLogger(__name__)

WORKING_DAY_MINUTES = 480  # 8 hours
COLLISION_RATIO_THRESHOLD = 2.0
HORIZON_BUSINESS_DAYS = 10
MOVEABLE_BUFFER_DAYS = 2


@dataclass
class CollisionFinding:
    """A single day's collision for one person."""

    date: str
    person: str
    person_email: str | None
    available_minutes: int
    tasks_due: int
    weighted_total: float
    weighted_ratio: float
    meetings: list[dict[str, Any]] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    moveable_tasks: list[dict[str, Any]] = field(default_factory=list)
    path: str = "A"  # A = time_blocks, B = calendar estimate


def _get_business_days(start: date, count: int) -> list[date]:
    """Return next `count` business days starting from `start` (inclusive)."""
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:  # Monday=0 through Friday=4
            days.append(current)
        current += timedelta(days=1)
    return days


class CollisionDetector:
    """Detects days where available time cannot absorb task load."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.weight_engine = TaskWeightEngine(db_path)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def detect(self) -> list[CollisionFinding]:
        """Run collision detection for Molham (Path A) and team (Path B)."""
        findings: list[CollisionFinding] = []
        today = date.today()
        business_days = _get_business_days(today, HORIZON_BUSINESS_DAYS)

        conn = self._get_conn()
        try:
            # Path A: Molham (time_blocks)
            findings.extend(self._detect_path_a(conn, business_days))

            # Path B: Team members (calendar-based)
            findings.extend(self._detect_path_b(conn, business_days))
        finally:
            conn.close()

        return findings

    def _detect_path_a(
        self, conn: sqlite3.Connection, business_days: list[date]
    ) -> list[CollisionFinding]:
        """Path A: Molham -- uses time_blocks for available minutes."""
        findings: list[CollisionFinding] = []

        for day in business_days:
            day_str = day.isoformat()

            # Available minutes from unassigned, unprotected blocks
            cursor = conn.execute(
                """SELECT COALESCE(SUM(
                       (julianday(end_time) - julianday(start_time)) * 1440
                   ), 0) as available_min
                   FROM time_blocks
                   WHERE date = ? AND is_protected = 0 AND task_id IS NULL""",
                (day_str,),
            )
            row = cursor.fetchone()
            available_minutes = int(row["available_min"]) if row else 0

            # Tasks due on this day for Molham
            tasks = self._get_tasks_for_person(conn, day_str, "Molham Homsi")
            if not tasks:
                continue

            # Compute weighted total
            weights = self.weight_engine.get_weights_bulk(tasks)
            weighted_total = sum(w.weight_value for w in weights.values())

            # Compute ratio
            if available_minutes <= 0:
                weighted_ratio = float("inf") if tasks else 0.0
            else:
                weighted_ratio = weighted_total / (available_minutes / 60.0)

            # Check firing condition
            if weighted_ratio > COLLISION_RATIO_THRESHOLD or (
                available_minutes <= 0 and len(tasks) > 0
            ):
                # Get meetings for context
                meetings = self._get_meetings_for_person_day(conn, None, day_str, is_molham=True)

                # Identify moveable tasks
                moveable = [
                    t
                    for t in tasks
                    if t.get("due_date")
                    and t["due_date"] > (day + timedelta(days=MOVEABLE_BUFFER_DAYS)).isoformat()
                ]

                # Enrich tasks with weight info
                enriched_tasks = []
                for t in tasks:
                    tid = t.get("id", "")
                    w = weights.get(tid)
                    enriched_tasks.append(
                        {
                            **t,
                            "weight_class": w.weight_class if w else "standard",
                            "weight_value": w.weight_value if w else 1.0,
                        }
                    )

                findings.append(
                    CollisionFinding(
                        date=day_str,
                        person="Molham Homsi",
                        person_email=None,
                        available_minutes=available_minutes,
                        tasks_due=len(tasks),
                        weighted_total=weighted_total,
                        weighted_ratio=round(weighted_ratio, 2)
                        if weighted_ratio != float("inf")
                        else 999.0,
                        meetings=meetings,
                        tasks=enriched_tasks,
                        moveable_tasks=moveable,
                        path="A",
                    )
                )

        return findings

    def _detect_path_b(
        self, conn: sqlite3.Connection, business_days: list[date]
    ) -> list[CollisionFinding]:
        """Path B: Team members -- uses calendar events for available minutes."""
        findings: list[CollisionFinding] = []

        # Get all team members
        cursor = conn.execute("SELECT id, name, email FROM team_members")
        members = cursor.fetchall()

        for member in members:
            member_name = member["name"]
            member_email = member["email"]

            # Skip Molham (handled by Path A)
            if member_name and "molham" in member_name.lower():
                continue

            if not member_email:
                continue

            for day in business_days:
                day_str = day.isoformat()

                # Meeting minutes from events JOIN calendar_attendees
                meeting_minutes = self._get_meeting_minutes(conn, member_email, day_str)
                available_minutes = max(0, WORKING_DAY_MINUTES - meeting_minutes)

                # Tasks due for this member
                tasks = self._get_tasks_for_person(conn, day_str, member_name)
                if not tasks:
                    continue

                # Compute weighted total
                weights = self.weight_engine.get_weights_bulk(tasks)
                weighted_total = sum(w.weight_value for w in weights.values())

                # Compute ratio
                if available_minutes <= 0:
                    weighted_ratio = float("inf") if tasks else 0.0
                else:
                    weighted_ratio = weighted_total / (available_minutes / 60.0)

                # Check firing condition
                if weighted_ratio > COLLISION_RATIO_THRESHOLD or (
                    available_minutes <= 0 and len(tasks) > 0
                ):
                    meetings = self._get_meetings_for_person_day(
                        conn, member_email, day_str, is_molham=False
                    )
                    moveable = [
                        t
                        for t in tasks
                        if t.get("due_date")
                        and t["due_date"] > (day + timedelta(days=MOVEABLE_BUFFER_DAYS)).isoformat()
                    ]

                    enriched_tasks = []
                    for t in tasks:
                        tid = t.get("id", "")
                        w = weights.get(tid)
                        enriched_tasks.append(
                            {
                                **t,
                                "weight_class": w.weight_class if w else "standard",
                                "weight_value": w.weight_value if w else 1.0,
                            }
                        )

                    findings.append(
                        CollisionFinding(
                            date=day_str,
                            person=member_name,
                            person_email=member_email,
                            available_minutes=available_minutes,
                            tasks_due=len(tasks),
                            weighted_total=weighted_total,
                            weighted_ratio=round(weighted_ratio, 2)
                            if weighted_ratio != float("inf")
                            else 999.0,
                            meetings=meetings,
                            tasks=enriched_tasks,
                            moveable_tasks=moveable,
                            path="B",
                        )
                    )

        return findings

    def _get_tasks_for_person(
        self, conn: sqlite3.Connection, day_str: str, person_name: str
    ) -> list[dict[str, Any]]:
        """Get active tasks due on a specific day for a person."""
        cursor = conn.execute(
            """SELECT t.id, t.title, t.due_date, t.assignee, t.project_id,
                      p.name as project_name, p.client_id,
                      c.name as client_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               LEFT JOIN clients c ON p.client_id = c.id
               WHERE t.due_date = ?
                 AND t.assignee = ?
                 AND t.status IN ('active', 'in_progress')""",
            (day_str, person_name),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_meeting_minutes(self, conn: sqlite3.Connection, email: str, day_str: str) -> int:
        """Get total meeting minutes for a person on a day.

        Uses events JOIN calendar_attendees -- NEVER calendar_events.
        """
        cursor = conn.execute(
            """SELECT e.start_time, e.end_time
               FROM events e
               JOIN calendar_attendees ca ON ca.event_id = e.id
               WHERE ca.email = ?
                 AND date(e.start_time) = ?
                 AND e.status != 'cancelled'""",
            (email, day_str),
        )

        total_minutes = 0
        for row in cursor.fetchall():
            start = row["start_time"]
            end = row["end_time"]
            if start and end:
                try:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)
                    diff_minutes = int((end_dt - start_dt).total_seconds() / 60)
                    if diff_minutes > 0:
                        total_minutes += diff_minutes
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse event times: %s", e)
                    continue

        return total_minutes

    def _get_meetings_for_person_day(
        self,
        conn: sqlite3.Connection,
        email: str | None,
        day_str: str,
        is_molham: bool = False,
    ) -> list[dict[str, Any]]:
        """Get meeting details for a person on a day."""
        if is_molham:
            # Molham's meetings: look up from events for the day
            cursor = conn.execute(
                """SELECT e.id, e.title, e.start_time, e.end_time, e.location
                   FROM events e
                   WHERE date(e.start_time) = ?
                     AND e.status != 'cancelled'
                   ORDER BY e.start_time""",
                (day_str,),
            )
        else:
            cursor = conn.execute(
                """SELECT e.id, e.title, e.start_time, e.end_time, e.location
                   FROM events e
                   JOIN calendar_attendees ca ON ca.event_id = e.id
                   WHERE ca.email = ?
                     AND date(e.start_time) = ?
                     AND e.status != 'cancelled'
                   ORDER BY e.start_time""",
                (email, day_str),
            )

        return [dict(row) for row in cursor.fetchall()]

    def findings_to_dicts(self, findings: list[CollisionFinding]) -> list[dict[str, Any]]:
        """Serialize findings for storage."""
        return [asdict(f) for f in findings]
