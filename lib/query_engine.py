"""
Query Engine — Cross-Entity Intelligence Queries

Provides structured Python interface for querying across entity boundaries.
All functions return dicts/lists of dicts, never raw tuples.
Read-only — this module never writes to the database.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from lib import paths, safe_sql

logger = logging.getLogger(__name__)


def _resolve_db_path() -> Path:
    """
    Resolve database path, preferring paths.db_path() but falling back to project data.

    NOTE: This function probes the filesystem. Do NOT call at module import time
    to avoid determinism violations in tests.
    """
    # Try canonical path first
    canonical = paths.db_path()
    if canonical.exists():
        return canonical

    # Fall back to project data directory (for dev/test)
    project_db = paths.project_root() / "data" / "moh_time_os.db"
    if project_db.exists():
        return project_db

    # Return canonical even if it doesn't exist (will error on use)
    return canonical


# Lazy-initialized default path. Do NOT resolve at import time to avoid
# filesystem probes that break test determinism.
_default_db_path: Path | None = None


def get_default_db_path() -> Path:
    """Get the default database path, resolving lazily on first call."""
    global _default_db_path
    if _default_db_path is None:
        _default_db_path = _resolve_db_path()
    return _default_db_path


class QueryEngine:
    """
    Cross-entity query interface for operational intelligence.

    Usage:
        engine = QueryEngine(db_path)  # Explicit path required in tests
        clients = engine.client_portfolio_overview()
        profile = engine.client_deep_profile("client-id-123")
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize query engine with database path."""
        self.db_path = db_path if db_path is not None else get_default_db_path()
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get a read-only database connection."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a query and return list of dicts."""
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def _execute_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute a query and return single dict or None."""
        results = self._execute(sql, params)
        return results[0] if results else None

    # =========================================================================
    # PORTFOLIO-LEVEL QUERIES
    # =========================================================================

    # Pre-built SQL queries - NO dynamic interpolation, fully static strings
    # Each (column, direction) pair maps to a complete, safe SQL string
    _PORTFOLIO_QUERIES: dict[tuple[str, bool], str] = {
        (
            "client_name",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY client_name DESC",
        (
            "client_name",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY client_name ASC",
        (
            "project_count",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY project_count DESC",
        (
            "project_count",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY project_count ASC",
        (
            "total_tasks",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_tasks DESC",
        (
            "total_tasks",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_tasks ASC",
        (
            "active_tasks",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY active_tasks DESC",
        (
            "active_tasks",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY active_tasks ASC",
        (
            "invoice_count",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY invoice_count DESC",
        (
            "invoice_count",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY invoice_count ASC",
        (
            "total_invoiced",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_invoiced DESC",
        (
            "total_invoiced",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_invoiced ASC",
        (
            "total_paid",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_paid DESC",
        (
            "total_paid",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_paid ASC",
        (
            "total_outstanding",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_outstanding DESC",
        (
            "total_outstanding",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_outstanding ASC",
        (
            "entity_links_count",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY entity_links_count DESC",
        (
            "entity_links_count",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY entity_links_count ASC",
        (
            "ytd_revenue",
            True,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY ytd_revenue DESC",
        (
            "ytd_revenue",
            False,
        ): "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY ytd_revenue ASC",
    }
    _PORTFOLIO_DEFAULT_QUERY = "SELECT * FROM v_client_operational_profile WHERE project_count > 0 OR invoice_count > 0 ORDER BY total_tasks DESC"

    def client_portfolio_overview(
        self, order_by: str = "total_tasks", desc: bool = True
    ) -> list[dict]:
        """
        Every client with operational metrics.

        Returns list of client dicts with:
        - client_id, client_name, client_tier
        - project_count, total_tasks, active_tasks
        - invoice_count, total_invoiced, total_paid, total_outstanding
        - entity_links_count (communication volume proxy)

        Sortable by any metric via order_by parameter.
        SQL injection safe: uses pre-built static queries, no string interpolation.
        """
        # Lookup pre-built query - if not found, use safe default
        sql = self._PORTFOLIO_QUERIES.get((order_by, desc), self._PORTFOLIO_DEFAULT_QUERY)
        return self._execute(sql)

    def resource_load_distribution(self) -> list[dict]:
        """
        Every person with their load distribution.

        Returns list of person dicts with:
        - person_id, person_name, person_email, role
        - assigned_tasks, active_tasks, project_count
        - communication_links
        - computed: load_score (normalized 0-100)
        """
        sql = """
            SELECT
                *,
                CASE
                    WHEN (SELECT MAX(active_tasks) FROM v_person_load_profile) = 0 THEN 0
                    ELSE ROUND(100.0 * active_tasks /
                         (SELECT MAX(active_tasks) FROM v_person_load_profile), 1)
                END as load_score
            FROM v_person_load_profile
            WHERE assigned_tasks > 0
            ORDER BY active_tasks DESC
        """
        return self._execute(sql)

    def portfolio_structural_risks(
        self, overdue_threshold: int = 5, aging_threshold: int = 30
    ) -> list[dict]:
        """
        Identifies structural risks across the portfolio.

        Risk types:
        - OVERDUE_PROJECT: Projects with many overdue tasks
        - STALE_PROJECT: Projects with open tasks but no recent activity
        - OVERLOADED_PERSON: People with too many active tasks
        - AGING_INVOICE: Invoices past due threshold

        Returns list of risk dicts with:
        - entity_type, entity_id, entity_name
        - risk_type, severity (HIGH/MEDIUM/LOW), evidence
        """
        risks = []

        # Overdue projects
        overdue_sql = """
            SELECT project_id, project_name, client_name, overdue_tasks, total_tasks
            FROM v_project_operational_state
            WHERE overdue_tasks >= ?
            ORDER BY overdue_tasks DESC
        """
        for row in self._execute(overdue_sql, (overdue_threshold,)):
            severity = "HIGH" if row["overdue_tasks"] > 10 else "MEDIUM"
            risks.append(
                {
                    "entity_type": "project",
                    "entity_id": row["project_id"],
                    "entity_name": row["project_name"],
                    "risk_type": "OVERDUE_PROJECT",
                    "severity": severity,
                    "evidence": f"{row['overdue_tasks']} overdue of {row['total_tasks']} tasks",
                }
            )

        # Overloaded people
        overload_sql = """
            SELECT person_id, person_name, active_tasks, project_count
            FROM v_person_load_profile
            WHERE active_tasks > 20
            ORDER BY active_tasks DESC
        """
        for row in self._execute(overload_sql):
            severity = "HIGH" if row["active_tasks"] > 30 else "MEDIUM"
            risks.append(
                {
                    "entity_type": "person",
                    "entity_id": row["person_id"],
                    "entity_name": row["person_name"],
                    "risk_type": "OVERLOADED_PERSON",
                    "severity": severity,
                    "evidence": f"{row['active_tasks']} active tasks across {row['project_count']} projects",
                }
            )

        # Aging invoices
        aging_sql = """
            SELECT invoice_id, client_name, amount, due_date, aging_bucket
            FROM v_invoice_client_project
            WHERE invoice_status NOT IN ('paid', 'voided')
            AND due_date < date('now', ?)
            ORDER BY due_date ASC
        """
        for row in self._execute(aging_sql, (f"-{aging_threshold} days",)):
            risks.append(
                {
                    "entity_type": "invoice",
                    "entity_id": row["invoice_id"],
                    "entity_name": f"{row['client_name']} - {row['amount']}",
                    "risk_type": "AGING_INVOICE",
                    "severity": "HIGH" if row["aging_bucket"] in ("90+", "60-90") else "MEDIUM",
                    "evidence": f"Due: {row['due_date']}, bucket: {row['aging_bucket']}",
                }
            )

        return risks

    # =========================================================================
    # CLIENT-LEVEL QUERIES
    # =========================================================================

    def client_deep_profile(self, client_id: str) -> dict | None:
        """
        Complete operational profile for a single client.

        Returns dict with:
        - Basic info: client_id, client_name, tier
        - Financial: invoices, total_invoiced, outstanding, ytd_revenue
        - Operational: projects, tasks, active_tasks
        - Communication: entity_links_count
        - Projects list with task counts
        - People involved (via tasks)
        """
        # Base profile
        profile = self._execute_one(
            "SELECT * FROM v_client_operational_profile WHERE client_id = ?", (client_id,)
        )

        if not profile:
            return None

        # Add projects
        projects = self._execute(
            """
            SELECT project_id, project_name, project_status,
                   total_tasks, open_tasks, completed_tasks, overdue_tasks,
                   completion_rate_pct
            FROM v_project_operational_state
            WHERE client_id = ?
            ORDER BY total_tasks DESC
        """,
            (client_id,),
        )
        profile["projects"] = projects

        # Add people involved (via tasks)
        people = self._execute(
            """
            SELECT DISTINCT p.person_id, p.person_name, p.person_email, p.role,
                   COUNT(t.task_id) as tasks_for_client
            FROM v_person_load_profile p
            JOIN v_task_with_client t ON LOWER(t.assignee) = LOWER(p.person_name)
            WHERE t.client_id = ?
            GROUP BY p.person_id
            ORDER BY tasks_for_client DESC
        """,
            (client_id,),
        )
        profile["people_involved"] = people

        # Add recent invoices
        invoices = self._execute(
            """
            SELECT invoice_id, amount, currency, invoice_status, issue_date, due_date
            FROM v_invoice_client_project
            WHERE client_id = ?
            ORDER BY issue_date DESC
            LIMIT 10
        """,
            (client_id,),
        )
        profile["recent_invoices"] = invoices

        return profile

    def client_task_summary(self, client_id: str) -> dict:
        """
        Task metrics for a client.

        Returns dict with:
        - total_tasks, active_tasks, completed_tasks, overdue_tasks
        - completion_rate, tasks_by_status, tasks_by_assignee
        """
        tasks = self._execute(
            """
            SELECT task_id, task_title, task_status, task_priority,
                   due_date, assignee, project_name
            FROM v_task_with_client
            WHERE client_id = ?
        """,
            (client_id,),
        )

        if not tasks:
            return {"total_tasks": 0, "tasks": []}

        # Aggregate
        total = len(tasks)
        completed = sum(1 for t in tasks if t["task_status"] in ("done", "complete", "completed"))
        active = total - completed
        overdue = sum(
            1
            for t in tasks
            if t["due_date"]
            and t["due_date"] < "2026-02-13"
            and t["task_status"] not in ("done", "complete", "completed")
        )

        # By status
        by_status: dict[str, int] = {}
        for t in tasks:
            status = t["task_status"] or "unknown"
            by_status[status] = by_status.get(status, 0) + 1

        # By assignee
        by_assignee: dict[str, int] = {}
        for t in tasks:
            assignee = t["assignee"] or "unassigned"
            by_assignee[assignee] = by_assignee.get(assignee, 0) + 1

        return {
            "total_tasks": total,
            "active_tasks": active,
            "completed_tasks": completed,
            "overdue_tasks": overdue,
            "completion_rate": round(100 * completed / total, 1) if total > 0 else 0,
            "tasks_by_status": by_status,
            "tasks_by_assignee": by_assignee,
            "tasks": tasks[:50],  # Limit to 50 for API response
        }

    # =========================================================================
    # RESOURCE QUERIES
    # =========================================================================

    def person_operational_profile(self, person_id: str) -> dict | None:
        """
        Complete load profile for a person.

        Returns dict with:
        - Basic info: person_id, person_name, email, role
        - Load: assigned_tasks, active_tasks, project_count
        - Projects with task counts
        - Clients they work with
        """
        profile = self._execute_one(
            "SELECT * FROM v_person_load_profile WHERE person_id = ?", (person_id,)
        )

        if not profile:
            return None

        # Projects they're on
        projects = self._execute(
            """
            SELECT DISTINCT p.project_id, p.project_name, p.client_name,
                   COUNT(t.task_id) as tasks_on_project
            FROM v_project_operational_state p
            JOIN v_task_with_client t ON t.project_id = p.project_id
            WHERE LOWER(t.assignee) = LOWER(?)
            GROUP BY p.project_id
            ORDER BY tasks_on_project DESC
        """,
            (profile["person_name"],),
        )
        profile["projects"] = projects

        # Clients they work with
        clients = self._execute(
            """
            SELECT DISTINCT c.client_id, c.client_name,
                   COUNT(t.task_id) as tasks_for_client
            FROM v_client_operational_profile c
            JOIN v_task_with_client t ON t.client_id = c.client_id
            WHERE LOWER(t.assignee) = LOWER(?)
            GROUP BY c.client_id
            ORDER BY tasks_for_client DESC
        """,
            (profile["person_name"],),
        )
        profile["clients"] = clients

        return profile

    def team_capacity_overview(self) -> dict:
        """
        Team-wide capacity view.

        Returns dict with:
        - total_people, total_active_tasks
        - avg_tasks_per_person, max_tasks_per_person
        - people_overloaded (>20 active), people_available (<5 active)
        - distribution: list of people with their loads
        """
        people = self.resource_load_distribution()

        if not people:
            return {"total_people": 0, "distribution": []}

        total_tasks = sum(p["active_tasks"] for p in people)
        max_tasks = max(p["active_tasks"] for p in people)
        overloaded = [p for p in people if p["active_tasks"] > 20]
        available = [p for p in people if p["active_tasks"] < 5]

        return {
            "total_people": len(people),
            "total_active_tasks": total_tasks,
            "avg_tasks_per_person": round(total_tasks / len(people), 1),
            "max_tasks_per_person": max_tasks,
            "people_overloaded": len(overloaded),
            "people_available": len(available),
            "overloaded_names": [p["person_name"] for p in overloaded],
            "available_names": [p["person_name"] for p in available],
            "distribution": people,
        }

    # =========================================================================
    # PROJECT QUERIES
    # =========================================================================

    def project_operational_state(self, project_id: str) -> dict | None:
        """
        Current state of a project.

        Returns dict with:
        - Basic: project_id, project_name, status, client_name
        - Tasks: total, open, completed, overdue, completion_rate
        - People: assigned_people_count
        """
        return self._execute_one(
            "SELECT * FROM v_project_operational_state WHERE project_id = ?", (project_id,)
        )

    def projects_by_health(self, min_tasks: int = 1) -> list[dict]:
        """
        All projects ranked by health indicators.

        Returns projects with computed health score based on:
        - Completion rate (higher is better)
        - Overdue ratio (lower is better)

        health_score = completion_rate - (overdue_ratio * 50)
        """
        sql = """
            SELECT *,
                CASE
                    WHEN total_tasks = 0 THEN 50
                    ELSE ROUND(completion_rate_pct -
                         (50.0 * overdue_tasks / total_tasks), 1)
                END as health_score
            FROM v_project_operational_state
            WHERE total_tasks >= ?
            ORDER BY health_score DESC
        """
        return self._execute(sql, (min_tasks,))

    # =========================================================================
    # COMMUNICATION QUERIES
    # =========================================================================

    def client_communication_summary(self, client_id: str) -> dict:
        """
        Communication metrics for a client.

        Returns dict with:
        - total_links, by_type (message, calendar_event, etc.)
        - recent: last 10 communications
        """
        total = self._execute_one(
            """
            SELECT COUNT(*) as total FROM v_communication_client_link
            WHERE client_id = ?
        """,
            (client_id,),
        )

        by_type = self._execute(
            """
            SELECT artifact_type, COUNT(*) as count
            FROM v_communication_client_link
            WHERE client_id = ?
            GROUP BY artifact_type
            ORDER BY count DESC
        """,
            (client_id,),
        )

        recent = self._execute(
            """
            SELECT artifact_id, artifact_type, source_system, occurred_at, confidence
            FROM v_communication_client_link
            WHERE client_id = ?
            ORDER BY occurred_at DESC
            LIMIT 10
        """,
            (client_id,),
        )

        return {
            "total_communications": total["total"] if total else 0,
            "by_type": {row["artifact_type"]: row["count"] for row in by_type},
            "recent": recent,
        }

    # =========================================================================
    # FINANCIAL QUERIES
    # =========================================================================

    def invoice_aging_report(self) -> dict:
        """
        Invoice aging across all clients.

        Returns dict with:
        - total_outstanding, by_bucket (current, 30, 60, 90+)
        - clients_with_overdue: list of clients with overdue amounts
        """
        by_bucket = self._execute("""
            SELECT aging_bucket, COUNT(*) as count, SUM(amount) as total
            FROM v_invoice_client_project
            WHERE invoice_status NOT IN ('paid', 'voided')
            GROUP BY aging_bucket
        """)

        overdue_clients = self._execute("""
            SELECT client_id, client_name,
                   COUNT(*) as overdue_invoices,
                   SUM(amount) as overdue_amount
            FROM v_invoice_client_project
            WHERE invoice_status NOT IN ('paid', 'voided')
            AND aging_bucket IN ('30-60', '60-90', '90+')
            GROUP BY client_id
            ORDER BY overdue_amount DESC
        """)

        total = sum(row["total"] or 0 for row in by_bucket)

        return {
            "total_outstanding": total,
            "by_bucket": {row["aging_bucket"] or "unknown": row["total"] or 0 for row in by_bucket},
            "invoice_count_by_bucket": {
                row["aging_bucket"] or "unknown": row["count"] for row in by_bucket
            },
            "clients_with_overdue": overdue_clients,
        }

    # =========================================================================
    # TEMPORAL QUERIES — Time-windowed and trajectory analysis
    # =========================================================================

    def tasks_in_period(
        self, since: str | None = None, until: str | None = None, client_id: str | None = None
    ) -> list[dict]:
        """
        Tasks created within a time period.

        Args:
            since: Start date (ISO format, e.g., '2024-01-01')
            until: End date (ISO format)
            client_id: Optional filter by client

        Returns list of task dicts.
        """
        conditions = []
        params: list[Any] = []

        if since:
            conditions.append("created_at >= ?")
            params.append(since)
        if until:
            conditions.append("created_at < ?")
            params.append(until)
        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)

        where_clause = safe_sql.where_and(conditions)

        sql = safe_sql.select_with_join(
            "SELECT * FROM v_task_with_client\nWHERE ",
            where_clause if where_clause else "1=1",
            order_by="created_at DESC",
        )
        return self._execute(sql, tuple(params))

    def invoices_in_period(
        self, since: str | None = None, until: str | None = None, client_id: str | None = None
    ) -> list[dict]:
        """
        Invoices issued within a time period.

        Args:
            since: Start date (ISO format)
            until: End date (ISO format)
            client_id: Optional filter by client
        """
        conditions = []
        params: list[Any] = []

        if since:
            conditions.append("issue_date >= ?")
            params.append(since)
        if until:
            conditions.append("issue_date < ?")
            params.append(until)
        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)

        where_clause = safe_sql.where_and(conditions)

        sql = safe_sql.select_with_join(
            "SELECT * FROM v_invoice_client_project\nWHERE ",
            where_clause if where_clause else "1=1",
            order_by="issue_date DESC",
        )
        return self._execute(sql, tuple(params))

    def communications_in_period(
        self, since: str | None = None, until: str | None = None, client_id: str | None = None
    ) -> list[dict]:
        """
        Communications (via entity_links) within a time period.
        """
        conditions = []
        params: list[Any] = []

        if since:
            conditions.append("occurred_at >= ?")
            params.append(since)
        if until:
            conditions.append("occurred_at < ?")
            params.append(until)
        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)

        where_clause = safe_sql.where_and(conditions)

        sql = safe_sql.select_with_join(
            "SELECT * FROM v_communication_client_link\nWHERE ",
            where_clause if where_clause else "1=1",
            order_by="occurred_at DESC",
        )
        return self._execute(sql, tuple(params))

    def client_metrics_in_period(self, client_id: str, since: str, until: str) -> dict:
        """
        Compute operational metrics for a client within a specific period.

        Returns dict with:
        - tasks_created, tasks_completed
        - invoices_issued, amount_invoiced, amount_paid
        - communications_count
        """
        # Tasks
        tasks = self.tasks_in_period(since, until, client_id)
        tasks_created = len(tasks)
        tasks_completed = sum(
            1 for t in tasks if t.get("task_status") in ("done", "complete", "completed")
        )

        # Invoices
        invoices = self.invoices_in_period(since, until, client_id)
        invoices_issued = len(invoices)
        amount_invoiced = sum(i.get("amount", 0) or 0 for i in invoices)
        amount_paid = sum(
            i.get("amount", 0) or 0 for i in invoices if i.get("invoice_status") == "paid"
        )

        # Communications
        comms = self.communications_in_period(since, until, client_id)
        communications_count = len(comms)

        return {
            "client_id": client_id,
            "period_start": since,
            "period_end": until,
            "tasks_created": tasks_created,
            "tasks_completed": tasks_completed,
            "invoices_issued": invoices_issued,
            "amount_invoiced": amount_invoiced,
            "amount_paid": amount_paid,
            "communications_count": communications_count,
        }

    def compare_client_periods(
        self,
        client_id: str,
        period_a: tuple[str, str],  # (start, end) ISO dates
        period_b: tuple[str, str],
    ) -> dict:
        """
        Compare a client's operational metrics between two time periods.

        Returns:
        - period_a_metrics: metrics for first period
        - period_b_metrics: metrics for second period
        - deltas: difference (period_b - period_a) for each metric
        - pct_changes: percentage change for each metric
        """
        metrics_a = self.client_metrics_in_period(client_id, period_a[0], period_a[1])
        metrics_b = self.client_metrics_in_period(client_id, period_b[0], period_b[1])

        # Compute deltas
        numeric_keys = [
            "tasks_created",
            "tasks_completed",
            "invoices_issued",
            "amount_invoiced",
            "amount_paid",
            "communications_count",
        ]

        deltas = {}
        pct_changes = {}

        for key in numeric_keys:
            val_a = metrics_a.get(key, 0) or 0
            val_b = metrics_b.get(key, 0) or 0
            deltas[key] = val_b - val_a
            pct_changes[key] = round(100 * (val_b - val_a) / val_a, 1) if val_a > 0 else None

        return {
            "client_id": client_id,
            "period_a": {"start": period_a[0], "end": period_a[1], "metrics": metrics_a},
            "period_b": {"start": period_b[0], "end": period_b[1], "metrics": metrics_b},
            "deltas": deltas,
            "pct_changes": pct_changes,
        }

    def compare_portfolio_periods(
        self, period_a: tuple[str, str], period_b: tuple[str, str]
    ) -> list[dict]:
        """
        Compare all clients between two periods.

        Returns list of clients with their metrics in each period and deltas.
        """
        clients = self.client_portfolio_overview()
        results = []

        for client in clients:
            client_id = client["client_id"]
            comparison = self.compare_client_periods(client_id, period_a, period_b)
            comparison["client_name"] = client["client_name"]
            results.append(comparison)

        return results

    def client_trajectory(
        self, client_id: str, window_size_days: int = 30, num_windows: int = 6
    ) -> dict:
        """
        Compute metrics for N rolling windows, showing direction of travel.

        Returns:
        - windows: list of {period_start, period_end, metrics}
        - trends: computed trend (INCREASING/STABLE/DECLINING) for each metric
        """
        from datetime import datetime, timedelta

        # Calculate windows going back from today
        end_date = datetime.now()
        windows_data = []

        for i in range(num_windows):
            window_end = end_date - timedelta(days=i * window_size_days)
            window_start = window_end - timedelta(days=window_size_days)

            metrics = self.client_metrics_in_period(
                client_id, window_start.strftime("%Y-%m-%d"), window_end.strftime("%Y-%m-%d")
            )

            windows_data.insert(
                0,
                {
                    "period_start": window_start.strftime("%Y-%m-%d"),
                    "period_end": window_end.strftime("%Y-%m-%d"),
                    "metrics": metrics,
                },
            )

        # Compute trends for each metric
        numeric_keys = [
            "tasks_created",
            "tasks_completed",
            "invoices_issued",
            "amount_invoiced",
            "communications_count",
        ]

        trends = {}
        for key in numeric_keys:
            values = [w["metrics"].get(key, 0) or 0 for w in windows_data]
            trends[key] = _compute_trend(values)

        return {
            "client_id": client_id,
            "window_size_days": window_size_days,
            "num_windows": num_windows,
            "windows": windows_data,
            "trends": trends,
        }

    def portfolio_trajectory(
        self, window_size_days: int = 30, num_windows: int = 6, min_activity: int = 1
    ) -> list[dict]:
        """
        Trajectory for all clients. Enables: 'Which clients are trending down?'

        Args:
            window_size_days: Size of each window
            num_windows: Number of windows to analyze
            min_activity: Minimum total activity to include client
        """
        clients = self.client_portfolio_overview()
        results = []

        for client in clients:
            if client["total_tasks"] < min_activity and client["invoice_count"] < min_activity:
                continue

            trajectory = self.client_trajectory(client["client_id"], window_size_days, num_windows)
            trajectory["client_name"] = client["client_name"]
            results.append(trajectory)

        return results

    def person_load_in_period(self, person_name: str, since: str, until: str) -> dict:
        """
        Person's task load within a period.
        """
        tasks = self._execute(
            """
            SELECT * FROM v_task_with_client
            WHERE LOWER(assignee) = LOWER(?)
            AND created_at >= ? AND created_at < ?
        """,
            (person_name, since, until),
        )

        total = len(tasks)
        completed = sum(
            1 for t in tasks if t.get("task_status") in ("done", "complete", "completed")
        )

        return {
            "person_name": person_name,
            "period_start": since,
            "period_end": until,
            "tasks_assigned": total,
            "tasks_completed": completed,
            "completion_rate": round(100 * completed / total, 1) if total > 0 else 0,
        }

    def person_trajectory(
        self, person_id: str, window_size_days: int = 30, num_windows: int = 6
    ) -> dict:
        """
        Load and activity trajectory for a person.
        """
        from datetime import datetime, timedelta

        # Get person name
        profile = self.person_operational_profile(person_id)
        if not profile:
            return {"error": "Person not found"}

        person_name = profile["person_name"]

        # Calculate windows
        end_date = datetime.now()
        windows_data = []

        for i in range(num_windows):
            window_end = end_date - timedelta(days=i * window_size_days)
            window_start = window_end - timedelta(days=window_size_days)

            metrics = self.person_load_in_period(
                person_name, window_start.strftime("%Y-%m-%d"), window_end.strftime("%Y-%m-%d")
            )

            windows_data.insert(
                0,
                {
                    "period_start": window_start.strftime("%Y-%m-%d"),
                    "period_end": window_end.strftime("%Y-%m-%d"),
                    "metrics": metrics,
                },
            )

        # Compute trends
        trends = {
            "tasks_assigned": _compute_trend(
                [w["metrics"]["tasks_assigned"] for w in windows_data]
            ),
            "tasks_completed": _compute_trend(
                [w["metrics"]["tasks_completed"] for w in windows_data]
            ),
        }

        return {
            "person_id": person_id,
            "person_name": person_name,
            "window_size_days": window_size_days,
            "num_windows": num_windows,
            "windows": windows_data,
            "trends": trends,
        }


def _compute_trend(values: list[float]) -> dict:
    """
    Compute trend direction from a list of metric values over time windows.

    Args:
        values: List of metric values, oldest first

    Returns:
        dict with:
        - direction: 'increasing', 'stable', 'declining'
        - magnitude_pct: percentage change from first to last
        - confidence: 'high', 'medium', 'low' based on data quality
    """
    if not values or len(values) < 2:
        return {"direction": "stable", "magnitude_pct": 0, "confidence": "low"}

    # Filter out None values
    clean_values = [v for v in values if v is not None]
    if len(clean_values) < 2:
        return {"direction": "stable", "magnitude_pct": 0, "confidence": "low"}

    # Calculate trend
    first_val = clean_values[0]
    last_val = clean_values[-1]

    # Average of first half vs last half
    mid = len(clean_values) // 2
    first_half_avg = sum(clean_values[:mid]) / mid if mid > 0 else first_val
    second_half_avg = (
        sum(clean_values[mid:]) / (len(clean_values) - mid) if len(clean_values) > mid else last_val
    )

    # Calculate magnitude
    if first_half_avg > 0:
        magnitude_pct = round(100 * (second_half_avg - first_half_avg) / first_half_avg, 1)
    elif second_half_avg > 0:
        magnitude_pct = 100.0  # From 0 to something = 100% increase
    else:
        magnitude_pct = 0.0

    # Determine direction (threshold: 10% change)
    if magnitude_pct > 10:
        direction = "increasing"
    elif magnitude_pct < -10:
        direction = "declining"
    else:
        direction = "stable"

    # Confidence based on data completeness and consistency
    non_zero_count = sum(1 for v in clean_values if v > 0)
    if non_zero_count >= len(clean_values) * 0.8:
        confidence = "high"
    elif non_zero_count >= len(clean_values) * 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return {"direction": direction, "magnitude_pct": magnitude_pct, "confidence": confidence}


# Convenience function for one-off queries
def get_engine(db_path: Path | None = None) -> QueryEngine:
    """Get a QueryEngine instance."""
    return QueryEngine(db_path)
