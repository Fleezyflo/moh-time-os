"""
Delivery Engine - Slip Risk, Project Status, Critical Chain.

Per Page 0 §6.1 and Page 1 §6.
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from .scoring import Confidence, Domain, ScoredItem, clamp01

logger = logging.getLogger(__name__)


class ProjectStatus(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    PARTIAL = "PARTIAL"  # When gates fail


class TopDriver(Enum):
    DEADLINE = "Deadline"
    OVERDUE = "Overdue"  # Tasks past due date
    CAPACITY = "Capacity"
    BLOCKED = "Blocked"
    SCOPE = "Scope"
    COMMS = "Comms"
    UNKNOWN = "Unknown"


@dataclass
class SlipRiskResult:
    """Result of slip risk computation."""

    slip_risk_score: float  # 0..1
    deadline_pressure: float
    remaining_work_ratio: float
    capacity_gap_ratio: float
    blocking_severity: float
    top_drivers: list[str]  # Top 2 drivers


@dataclass
class ProjectDeliveryData:
    """Delivery data for a project."""

    project_id: str
    name: str
    owner: str | None
    lane: str | None
    client: str | None
    client_id: str | None = None  # For comms filtering
    is_internal: bool = False
    project_type: str = "project"  # "project" or "retainer"

    # Deadline
    deadline: datetime | None = None
    days_to_deadline: float | None = None
    time_to_slip_hours: float | None = None

    # Task metrics
    total_tasks: int = 0
    open_tasks: int = 0
    blocked_tasks: int = 0
    critical_tasks: int = 0
    blocked_critical_tasks: int = 0

    # Effort (hours)
    planned_effort_hours: float = 0
    open_effort_hours: float = 0
    hours_needed: float = 0
    hours_available: float = 0

    # Derived
    slip_risk: SlipRiskResult | None = None
    status: ProjectStatus = ProjectStatus.GREEN
    top_driver: TopDriver = TopDriver.UNKNOWN
    confidence: Confidence = Confidence.HIGH
    why_low: list[str] = field(default_factory=list)

    # Flags
    blocked_critical_path: bool = False
    dependency_breaker: bool = False
    velocity_negative: bool = False


@dataclass
class CriticalChainNode:
    """A node in the critical chain."""

    node_type: str  # "task", "blocker", "milestone"
    node_id: str
    label: str
    ttc_hours: float | None = None


@dataclass
class CriticalChain:
    """The critical dependency chain for a project."""

    nodes: list[CriticalChainNode]
    unlock_action: str | None = None


@dataclass
class BreakItem:
    """An item in 'Breaks Next' list."""

    text: str
    ttc_hours: float
    driver: str
    entity_type: str
    entity_id: str
    primary_action: dict[str, Any]


class DeliveryEngine:
    """
    Computes delivery metrics per Page 0 §6.1 and Page 1 §6.

    All formulas are locked per spec.
    """

    # Slip risk weights per Page 0 §6.1 (locked)
    W_DEADLINE_PRESSURE = 0.35
    W_REMAINING_WORK = 0.25
    W_CAPACITY_GAP = 0.25
    W_BLOCKING = 0.15

    # Runway for deadline pressure (14 days)
    DEADLINE_RUNWAY_DAYS = 14

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.today = date.today()
        self.now = datetime.now()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def compute_slip_risk(self, project: ProjectDeliveryData) -> SlipRiskResult:
        """
        Compute slip risk per Page 0 §6.1 (locked formula with overdue enhancement).

        Base formula:
        slip_risk = 0.35*deadline_pressure + 0.25*remaining_work_ratio
                  + 0.25*capacity_gap_ratio + 0.15*blocking_severity

        Enhanced: If no deadline, use overdue_severity as proxy for deadline_pressure.
        """
        # Deadline pressure - or overdue severity if no deadline
        if project.deadline is None or project.days_to_deadline is None:
            # No deadline - use overdue ratio as proxy
            overdue_count = self._count_overdue_tasks(project.project_id)
            if project.total_tasks > 0:
                overdue_ratio = overdue_count / project.total_tasks
                # If significant overdue, treat as deadline pressure
                deadline_pressure = clamp01(
                    overdue_ratio * 1.5
                )  # Scale up overdue impact
            else:
                deadline_pressure = 0.0
        else:
            # clamp01(1 - (days_to_deadline / 14))
            deadline_pressure = clamp01(
                1 - (project.days_to_deadline / self.DEADLINE_RUNWAY_DAYS)
            )

        # Remaining work ratio
        if project.planned_effort_hours > 0:
            remaining_work_ratio = clamp01(
                project.open_effort_hours / max(1, project.planned_effort_hours)
            )
        elif project.total_tasks > 0:
            # Fallback: task count ratio
            remaining_work_ratio = clamp01(
                project.open_tasks / max(1, project.total_tasks)
            )
        else:
            remaining_work_ratio = 0.0

        # Capacity gap ratio
        if project.hours_needed > 0:
            gap = project.hours_needed - project.hours_available
            capacity_gap_ratio = clamp01(gap / max(1, project.hours_needed))
        else:
            capacity_gap_ratio = 0.0

        # Blocking severity
        if project.critical_tasks > 0:
            blocking_severity = clamp01(
                project.blocked_critical_tasks / max(1, project.critical_tasks)
            )
        else:
            blocking_severity = 0.0

        # Compute slip risk
        slip_risk_score = (
            self.W_DEADLINE_PRESSURE * deadline_pressure
            + self.W_REMAINING_WORK * remaining_work_ratio
            + self.W_CAPACITY_GAP * capacity_gap_ratio
            + self.W_BLOCKING * blocking_severity
        )

        # Identify top 2 drivers
        driver_label = "Deadline pressure" if project.deadline else "Overdue tasks"
        drivers = [
            (deadline_pressure * self.W_DEADLINE_PRESSURE, driver_label),
            (remaining_work_ratio * self.W_REMAINING_WORK, "Remaining work"),
            (capacity_gap_ratio * self.W_CAPACITY_GAP, "Capacity gap"),
            (blocking_severity * self.W_BLOCKING, "Blocking"),
        ]
        drivers.sort(key=lambda x: -x[0])
        top_drivers = [d[1] for d in drivers[:2] if d[0] > 0]

        return SlipRiskResult(
            slip_risk_score=clamp01(slip_risk_score),
            deadline_pressure=deadline_pressure,
            remaining_work_ratio=remaining_work_ratio,
            capacity_gap_ratio=capacity_gap_ratio,
            blocking_severity=blocking_severity,
            top_drivers=top_drivers or ["No significant drivers"],
        )

    def _count_overdue_tasks(self, project_id: str) -> int:
        """Count overdue tasks for a project."""
        result = self._query_one(
            """
            SELECT COUNT(*) as count FROM tasks
            WHERE project_id = ?
            AND status NOT IN ('done', 'completed')
            AND due_date IS NOT NULL
            AND due_date < date('now')
        """,
            (project_id,),
        )
        return result.get("count", 0) if result else 0

    def compute_status(self, project: ProjectDeliveryData) -> ProjectStatus:
        """
        Compute project status per Page 0 §6.1 (locked).

        RED if any:
        - deadline exists and days_to_deadline < 0
        - slip_risk_score >= 0.75
        - blocked_critical_path=true
        - overdue_ratio >= 50% (added: significant overdue work)

        YELLOW if any:
        - deadline exists and days_to_deadline <= 7
        - slip_risk_score in [0.45, 0.75)
        - dependency_breaker=true (within horizon)
        - velocity trend negative
        - overdue_ratio >= 20% (added: notable overdue work)

        GREEN otherwise
        """
        slip_score = project.slip_risk.slip_risk_score if project.slip_risk else 0.0

        # Compute overdue ratio
        overdue_ratio = 0.0
        if project.total_tasks > 0:
            # Count overdue tasks (tasks where open and past due)
            overdue_count = self._count_overdue_tasks(project.project_id)
            overdue_ratio = overdue_count / project.total_tasks

        # RED conditions
        if (
            project.deadline
            and project.days_to_deadline is not None
            and project.days_to_deadline < 0
        ):
            return ProjectStatus.RED
        if slip_score >= 0.75:
            return ProjectStatus.RED
        if project.blocked_critical_path:
            return ProjectStatus.RED
        if overdue_ratio >= 0.5:  # 50%+ tasks overdue
            return ProjectStatus.RED

        # YELLOW conditions
        if (
            project.deadline
            and project.days_to_deadline is not None
            and project.days_to_deadline <= 7
        ):
            return ProjectStatus.YELLOW
        if 0.45 <= slip_score < 0.75:
            return ProjectStatus.YELLOW
        if project.dependency_breaker:
            return ProjectStatus.YELLOW
        if project.velocity_negative:
            return ProjectStatus.YELLOW
        if overdue_ratio >= 0.2:  # 20%+ tasks overdue
            return ProjectStatus.YELLOW

        return ProjectStatus.GREEN

    def determine_top_driver(self, project: ProjectDeliveryData) -> TopDriver:
        """Determine the primary driver of project risk."""
        # Check overdue tasks first - this is the most actionable driver
        if project.total_tasks > 0:
            overdue_count = self._count_overdue_tasks(project.project_id)
            overdue_ratio = overdue_count / project.total_tasks
            if overdue_ratio >= 0.5:  # 50%+ tasks overdue
                return TopDriver.OVERDUE

        if not project.slip_risk:
            return TopDriver.UNKNOWN

        sr = project.slip_risk

        # Find highest contributor among other factors
        drivers = [
            (sr.deadline_pressure * self.W_DEADLINE_PRESSURE, TopDriver.DEADLINE),
            (sr.capacity_gap_ratio * self.W_CAPACITY_GAP, TopDriver.CAPACITY),
            (sr.blocking_severity * self.W_BLOCKING, TopDriver.BLOCKED),
            (sr.remaining_work_ratio * self.W_REMAINING_WORK, TopDriver.SCOPE),
        ]
        drivers.sort(key=lambda x: -x[0])

        if drivers[0][0] > 0:
            return drivers[0][1]

        return TopDriver.UNKNOWN

    def get_project_data(self, project_id: str) -> ProjectDeliveryData | None:
        """Get delivery data for a single project."""
        project = self._query_one(
            """
            SELECT
                p.id, p.name, p.target_end_date, NULL as lane, NULL as owner,
                p.is_internal, p.engagement_type as project_type,
                c.name as client_name
            FROM projects p
            LEFT JOIN clients c ON p.client_id = c.id
            WHERE p.id = ?
        """,
            (project_id,),
        )

        if not project:
            return None

        return self._build_project_data(project)

    def get_portfolio(
        self,
        include_internal: bool = False,
        lanes: list[str] = None,
        owners: list[str] = None,
        clients: list[str] = None,
        limit: int = 25,
    ) -> list[ProjectDeliveryData]:
        """Get portfolio of projects for delivery command."""

        where_clauses = []
        params = []

        if not include_internal:
            where_clauses.append("p.is_internal = 0")

        if lanes:
            placeholders = ",".join("?" * len(lanes))
            where_clauses.append(f"NULL as lane IN ({placeholders})")
            params.extend(lanes)

        if owners:
            placeholders = ",".join("?" * len(owners))
            where_clauses.append(f"NULL as owner IN ({placeholders})")
            params.extend(owners)

        if clients:
            placeholders = ",".join("?" * len(clients))
            where_clauses.append(f"p.client_id IN ({placeholders})")
            params.extend(clients)

        # Exclude projects with past deadlines (more than 30 days ago)
        cutoff = (self.now - timedelta(days=30)).strftime("%Y-%m-%d")
        where_clauses.append(
            f"(p.target_end_date IS NULL OR p.target_end_date >= '{cutoff}')"
        )

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        projects = self._query_all(
            f"""
            SELECT
                p.id, p.name, p.target_end_date, NULL as lane, NULL as owner,
                p.is_internal, p.engagement_type as project_type,
                p.client_id,
                c.name as client_name
            FROM projects p
            LEFT JOIN clients c ON p.client_id = c.id
            WHERE {where_sql}
            ORDER BY p.target_end_date ASC NULLS LAST
            LIMIT ?
        """,
            tuple(params) + (limit * 2,),
        )  # Fetch more, will filter/rank later

        portfolio = []
        for proj in projects:
            data = self._build_project_data(proj)
            portfolio.append(data)

        return portfolio

    def _build_project_data(self, project: dict) -> ProjectDeliveryData:
        """Build ProjectDeliveryData from raw project row."""
        project_id = project["id"]

        # Parse deadline
        deadline = None
        days_to_deadline = None
        time_to_slip_hours = None

        if project.get("deadline"):
            try:
                deadline = datetime.fromisoformat(
                    project["deadline"].replace("Z", "+00:00")
                )
                delta = deadline - self.now
                days_to_deadline = delta.days + delta.seconds / 86400
                time_to_slip_hours = delta.total_seconds() / 3600
            except (ValueError, TypeError):
                pass

        # Get task metrics
        # Note: using 1 instead of effort_hours, blockers field instead of blocked
        task_metrics = (
            self._query_one(
                """
            SELECT
                COUNT(*) as total_tasks,
                COUNT(CASE WHEN status NOT IN ('done', 'completed') THEN 1 END) as open_tasks,
                COUNT(CASE WHEN blockers IS NOT NULL AND blockers != '' AND blockers != '[]' THEN 1 END) as blocked_tasks,
                COUNT(CASE WHEN priority >= 80 THEN 1 END) as critical_tasks,
                COUNT(CASE WHEN (blockers IS NOT NULL AND blockers != '' AND blockers != '[]') AND priority >= 80 THEN 1 END) as blocked_critical,
                COALESCE(SUM(1.0), 0) as planned_effort,
                COALESCE(SUM(CASE WHEN status NOT IN ('done', 'completed') THEN 1.0 ELSE 0 END), 0) as open_effort
            FROM tasks
            WHERE project_id = ? AND project_link_status = 'linked'
        """,
                (project_id,),
            )
            or {}
        )

        # Get capacity (simplified - would need more complex calculation)
        # For now, estimate based on lane allocation
        hours_needed = task_metrics.get("open_effort", 0)
        hours_available = 40  # Default weekly capacity, should come from capacity truth

        data = ProjectDeliveryData(
            project_id=project_id,
            name=project.get("name", "Unknown"),
            owner=project.get("owner"),
            lane=project.get("lane"),
            client=project.get("client_name"),
            client_id=project.get("client_id"),
            is_internal=bool(project.get("is_internal")),
            project_type=project.get("project_type", "project"),
            deadline=deadline,
            days_to_deadline=days_to_deadline,
            time_to_slip_hours=time_to_slip_hours,
            total_tasks=task_metrics.get("total_tasks", 0),
            open_tasks=task_metrics.get("open_tasks", 0),
            blocked_tasks=task_metrics.get("blocked_tasks", 0),
            critical_tasks=task_metrics.get("critical_tasks", 0),
            blocked_critical_tasks=task_metrics.get("blocked_critical", 0),
            planned_effort_hours=task_metrics.get("planned_effort", 0),
            open_effort_hours=task_metrics.get("open_effort", 0),
            hours_needed=hours_needed,
            hours_available=hours_available,
            blocked_critical_path=task_metrics.get("blocked_critical", 0) > 0,
        )

        # Compute slip risk
        data.slip_risk = self.compute_slip_risk(data)

        # Compute status
        data.status = self.compute_status(data)

        # Determine top driver
        data.top_driver = self.determine_top_driver(data)

        # Compute confidence
        data.confidence, data.why_low = self._compute_project_confidence(
            data, task_metrics
        )

        return data

    def _compute_project_confidence(
        self, project: ProjectDeliveryData, metrics: dict
    ) -> tuple:
        """Compute confidence for a project."""
        why_low = []

        # Check task coverage
        total = metrics.get("total_tasks", 0)
        if total == 0:
            why_low.append("No tasks linked to project")

        # Check due date coverage (simplified)
        # Would need additional query for due_date coverage

        # Check effort coverage
        if project.planned_effort_hours == 0 and total > 0:
            why_low.append("No effort estimates on tasks")

        if len(why_low) >= 2:
            return Confidence.LOW, why_low[:3]
        if len(why_low) == 1:
            return Confidence.MED, why_low

        return Confidence.HIGH, []

    def get_breaks_next(self, project_id: str, max_items: int = 3) -> list[BreakItem]:
        """Get 'Breaks Next' items for a project."""
        breaks = []
        today = self.today.isoformat()

        # Overdue tasks
        overdue = self._query_all(
            """
            SELECT id, title, due_date,
                   julianday(?) - julianday(due_date) as days_overdue
            FROM tasks
            WHERE project_id = ? AND status != 'done'
            AND due_date IS NOT NULL AND due_date < ?
            ORDER BY due_date ASC
            LIMIT 3
        """,
            (today, project_id, today),
        )

        for task in overdue:
            days = int(task.get("days_overdue", 0))
            breaks.append(
                BreakItem(
                    text=f"Overdue {days}d: {task['title'][:40]}",
                    ttc_hours=-days * 24,
                    driver="Deadline",
                    entity_type="task",
                    entity_id=task["id"],
                    primary_action={
                        "risk": "auto",
                        "label": "Update due date",
                        "payload": {"task_id": task["id"]},
                    },
                )
            )

        # Blocked tasks
        blocked = self._query_all(
            """
            SELECT id, title, blockers
            FROM tasks
            WHERE project_id = ? AND status NOT IN ('done', 'completed')
            AND blockers IS NOT NULL AND blockers != '' AND blockers != '[]'
            ORDER BY priority DESC
            LIMIT 3
        """,
            (project_id,),
        )

        for task in blocked:
            reason = task.get("blockers") or "Unknown blocker"
            # Try to parse blockers if it's JSON
            if reason.startswith("["):
                try:
                    import json

                    blockers_list = json.loads(reason)
                    reason = blockers_list[0] if blockers_list else "Unknown blocker"
                except (json.JSONDecodeError, TypeError, IndexError) as e:
                    logger.debug(f"Could not parse blockers JSON: {e}")
            breaks.append(
                BreakItem(
                    text=f"Blocked: {task['title'][:30]} ({reason[:20]})",
                    ttc_hours=0,  # Blocking is immediate
                    driver="Blocked",
                    entity_type="task",
                    entity_id=task["id"],
                    primary_action={
                        "risk": "auto",
                        "label": "Unblock",
                        "payload": {"task_id": task["id"]},
                    },
                )
            )

        # Sort by TTC and limit
        breaks.sort(key=lambda b: b.ttc_hours)
        return breaks[:max_items]

    def get_critical_chain(self, project_id: str) -> CriticalChain | None:
        """
        Get critical chain for a project per Page 1 §7.3.

        Pick exactly one chain: earliest end consequence → most blocked nodes → highest controllability.
        """
        # Get blocked tasks that are on critical path
        blocked_critical = self._query_all(
            """
            SELECT id, title, due_date, blockers, dependencies
            FROM tasks
            WHERE project_id = ? AND status NOT IN ('done', 'completed')
            AND blockers IS NOT NULL AND blockers != '' AND blockers != '[]'
            AND priority >= 80
            ORDER BY due_date ASC NULLS LAST
            LIMIT 1
        """,
            (project_id,),
        )

        if not blocked_critical:
            return None

        task = blocked_critical[0]
        nodes = []

        # Blocker node
        blocker_reason = task.get("blockers") or "Unknown"
        # Try to parse blockers if it's JSON
        if blocker_reason.startswith("["):
            try:
                import json

                blockers_list = json.loads(blocker_reason)
                blocker_reason = blockers_list[0] if blockers_list else "Unknown"
            except (json.JSONDecodeError, TypeError, IndexError) as e:
                logger.debug(f"Could not parse blockers JSON: {e}")
        nodes.append(
            CriticalChainNode(
                node_type="blocker",
                node_id=f"blocker_{task['id']}",
                label=blocker_reason[:30],
                ttc_hours=0,
            )
        )

        # Task node
        ttc = None
        if task.get("due_date"):
            try:
                due = datetime.fromisoformat(task["due_date"])
                ttc = (due - self.now).total_seconds() / 3600
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse due_date: {e}")

        nodes.append(
            CriticalChainNode(
                node_type="task",
                node_id=task["id"],
                label=task["title"][:30],
                ttc_hours=ttc,
            )
        )

        # Milestone (project deadline)
        project = self._query_one(
            "SELECT deadline FROM projects WHERE id = ?", (project_id,)
        )
        if project and project.get("deadline"):
            try:
                deadline = datetime.fromisoformat(project["deadline"])
                deadline_ttc = (deadline - self.now).total_seconds() / 3600
                nodes.append(
                    CriticalChainNode(
                        node_type="milestone",
                        node_id=f"deadline_{project_id}",
                        label="Project deadline",
                        ttc_hours=deadline_ttc,
                    )
                )
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse project deadline: {e}")

        return CriticalChain(
            nodes=nodes,
            unlock_action=f"Resolve: {blocker_reason[:20]}",
        )

    def project_to_scored_item(self, project: ProjectDeliveryData) -> ScoredItem:
        """Convert ProjectDeliveryData to ScoredItem for ranking."""
        # Compute impact from slip risk + status + differentiation factors
        slip_score = project.slip_risk.slip_risk_score if project.slip_risk else 0.0

        # Boost impact for Red/Yellow status
        if project.status == ProjectStatus.RED:
            impact = max(slip_score, 0.75)
        elif project.status == ProjectStatus.YELLOW:
            impact = max(slip_score, 0.5)
        else:
            impact = slip_score

        # Further boost if overdue
        if project.time_to_slip_hours is not None and project.time_to_slip_hours < 0:
            impact = max(impact, 0.8)

        # Compute urgency from TTC
        from .scoring import BaseScorer, clamp01

        urgency = BaseScorer.compute_urgency_from_ttc(project.time_to_slip_hours)

        # If no TTC, infer urgency from available data to differentiate
        if urgency == 0.0:
            # Use slip_risk.deadline_pressure if available
            if project.slip_risk and project.slip_risk.deadline_pressure > 0:
                urgency = project.slip_risk.deadline_pressure
            # Fallback: use task-based urgency calculation
            elif project.open_tasks > 0:
                # Higher urgency for more blocked/critical tasks
                blocked_ratio = project.blocked_tasks / max(project.open_tasks, 1)
                critical_ratio = project.critical_tasks / max(project.open_tasks, 1)
                work_ratio = (
                    project.open_effort_hours / max(project.planned_effort_hours, 1)
                    if project.planned_effort_hours
                    else 0.5
                )

                # Combine factors for inferred urgency (scale 0-0.8, leaving 0.8-1.0 for actual overdue)
                urgency = clamp01(
                    0.3
                    + (blocked_ratio * 0.2)
                    + (critical_ratio * 0.15)
                    + (work_ratio * 0.15)
                )

                # If project is RED with no deadline, assume moderate-high urgency
                if project.status == ProjectStatus.RED:
                    urgency = max(urgency, 0.6)
                elif project.status == ProjectStatus.YELLOW:
                    urgency = max(urgency, 0.4)

        # Controllability (1.0 if no blockers, reduced if blocked)
        controllability = 1.0 if not project.blocked_critical_path else 0.5

        return ScoredItem(
            entity_type="project",
            entity_id=project.project_id,
            domain=Domain.DELIVERY,
            impact=impact,
            urgency=urgency,
            controllability=controllability,
            confidence=project.confidence,
            time_to_consequence_hours=project.time_to_slip_hours,
            dependency_breaker=project.dependency_breaker,
            critical_path=project.status == ProjectStatus.RED,
            compounding_damage=project.status
            in (ProjectStatus.RED, ProjectStatus.YELLOW),
            title=project.name,
            top_driver=project.top_driver.value,
            why_low=project.why_low,
        )
