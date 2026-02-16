"""
Health Calculator - Compute client health scores.

Health score (0-100) based on:
- Task completion rate (30%)
- Overdue task count (25%)
- Recent activity/touchpoints (25%)
- Response time / commitment fulfillment (20%)
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from lib.state_store import get_store

logger = logging.getLogger(__name__)


@dataclass
class ClientHealth:
    client_id: str
    client_name: str
    health_score: int
    tier: str
    factors: dict
    trend: str  # 'improving', 'stable', 'declining'
    last_activity: str | None
    at_risk: bool


class HealthCalculator:
    """
    Computes and tracks client health scores.

    Health factors:
    - completion_rate: % of tasks completed on time
    - overdue_count: number of overdue tasks
    - activity_score: recent touchpoints (tasks, emails, meetings)
    - commitment_score: promises kept vs broken
    """

    # Health thresholds
    AT_RISK_THRESHOLD = 50
    WARNING_THRESHOLD = 70

    def __init__(self, store=None):
        self.store = store or get_store()

    def compute_health_score(self, client_id: str) -> ClientHealth:
        """
        Compute health score for a client.

        Returns ClientHealth with score breakdown.
        """
        client = self.store.get("clients", client_id)
        if not client:
            return ClientHealth(
                client_id=client_id,
                client_name="Unknown",
                health_score=0,
                tier="unknown",
                factors={},
                trend="unknown",
                last_activity=None,
                at_risk=True,
            )

        factors = {}

        # Factor 1: Task completion rate (25%)
        completion = self._get_completion_rate(client_id)
        factors["completion_rate"] = completion
        completion_score = min(100, completion * 100) * 0.25

        # Factor 2: Overdue tasks (20%)
        overdue = self._get_overdue_count(client_id)
        factors["overdue_count"] = overdue
        # 0 overdue = 100, each overdue -10 points
        overdue_score = max(0, 100 - (overdue * 10)) * 0.20

        # Factor 3: Recent activity (20%)
        activity = self._get_activity_score(client_id, days=30)
        factors["activity_score"] = activity
        activity_score = activity * 0.20

        # Factor 4: Commitment fulfillment (15%)
        commitment = self._get_commitment_score(client_id)
        factors["commitment_score"] = commitment
        commitment_score = commitment * 0.15

        # Factor 5: Project health via client_projects linkage (20%)
        project_health, project_details = self._get_project_health_score(client_id)
        factors["project_health"] = project_health
        factors["project_details"] = project_details
        project_score = project_health * 0.20

        # Total health score
        total_score = int(
            completion_score + overdue_score + activity_score + commitment_score + project_score
        )
        total_score = max(0, min(100, total_score))

        # Determine trend
        trend = self._compute_trend(client_id, total_score)

        # Get last activity
        last_activity = self._get_last_activity(client_id)

        health = ClientHealth(
            client_id=client_id,
            client_name=client.get("name", "Unknown"),
            health_score=total_score,
            tier=client.get("tier", "standard"),
            factors=factors,
            trend=trend,
            last_activity=last_activity,
            at_risk=total_score < self.AT_RISK_THRESHOLD,
        )

        # Log the health computation
        self._log_health(health)

        return health

    def _get_completion_rate(self, client_id: str) -> float:
        """Get task completion rate for client."""
        # Get tasks for this client in last 90 days
        tasks = self.store.query(
            """
            SELECT status FROM tasks
            WHERE client_id = ?
            AND created_at >= date('now', '-90 days')
        """,
            [client_id],
        )

        if not tasks:
            return 0.75  # Default for no data

        completed = sum(1 for t in tasks if t["status"] in ("done", "completed"))
        return completed / len(tasks) if tasks else 0.75

    def _get_overdue_count(self, client_id: str) -> int:
        """Count overdue tasks for client."""
        today = date.today().isoformat()
        overdue = self.store.query(
            """
            SELECT COUNT(*) as count FROM tasks
            WHERE client_id = ?
            AND status NOT IN ('done', 'completed', 'archived')
            AND due_date < ?
        """,
            [client_id, today],
        )

        return overdue[0]["count"] if overdue else 0

    def _get_activity_score(self, client_id: str, days: int = 30) -> int:
        """
        Score based on recent activity (0-100).

        Activity includes: tasks created, emails, meetings.
        """
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        # Count recent tasks
        tasks = self.store.query(
            """
            SELECT COUNT(*) as count FROM tasks
            WHERE client_id = ?
            AND created_at >= ?
        """,
            [client_id, cutoff],
        )
        task_count = tasks[0]["count"] if tasks else 0

        # Activity score: 10 points per task, max 100
        return min(100, task_count * 10)

    def _get_commitment_score(self, client_id: str) -> int:
        """
        Score based on commitment fulfillment (0-100).
        """
        # Get commitments scoped to this client or their tasks
        commitments = self.store.query(
            """
            SELECT c.status FROM commitments c
            WHERE (c.scope_ref_type = 'client' AND c.scope_ref_id = ?)
            OR (c.scope_ref_type = 'task' AND c.scope_ref_id IN (
                SELECT id FROM tasks WHERE client_id = ?
            ))
        """,
            [client_id, client_id],
        )

        if not commitments:
            return 75  # Default

        done = sum(1 for c in commitments if c["status"] in ("done", "fulfilled"))
        broken = sum(1 for c in commitments if c["status"] in ("broken", "missed"))
        total = len(commitments)

        if total == 0:
            return 75

        # Score: (done - broken*2) / total * 100
        return max(0, min(100, int((done - broken * 2) / total * 100 + 50)))

    def _get_project_health_score(self, client_id: str) -> tuple[int, dict]:
        """
        Get aggregated project health for a client via client_projects linkage.

        Returns (score 0-100, details dict).
        """
        # Try client_projects linkage first, fallback to direct client_id
        projects = self.store.query(
            """
            SELECT p.id, p.name, p.health, p.status, p.enrollment_status
            FROM projects p
            JOIN client_projects cp ON p.id = cp.project_id
            WHERE cp.client_id = ?
            AND p.status != 'archived'
            AND (p.enrollment_status IS NULL OR p.enrollment_status != 'archived')
        """,
            [client_id],
        )

        # Fallback: check direct client_id on projects
        if not projects:
            projects = self.store.query(
                """
                SELECT id, name, health, status, enrollment_status
                FROM projects
                WHERE client_id = ?
                AND status != 'archived'
                AND (enrollment_status IS NULL OR enrollment_status != 'archived')
            """,
                [client_id],
            )

        if not projects:
            return 75, {"project_count": 0, "has_blockers": False}

        # Map health values - handle both conventions
        health_map = {
            "green": 100,
            "on_track": 100,
            "yellow": 70,
            "at_risk": 70,
            "orange": 50,
            "red": 20,
            "off_track": 20,
        }
        health_scores = []

        for p in projects:
            health_val = p.get("health", "on_track") or "on_track"
            health_scores.append(health_map.get(health_val.lower(), 75))

        # Average health across projects
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 75

        # Compute task completion for these projects
        project_ids = [p["id"] for p in projects]
        if project_ids:
            placeholders = ",".join("?" * len(project_ids))
            task_stats = self.store.query(
                f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status IN ('done', 'completed') THEN 1 ELSE 0 END) as done
                FROM tasks
                WHERE project_id IN ({placeholders})
            """,
                project_ids,
            )

            if task_stats and task_stats[0]["total"]:
                total = task_stats[0]["total"]
                done = task_stats[0]["done"] or 0
                completion_rate = done / total if total > 0 else 0.5
                completion_modifier = (completion_rate - 0.5) * 20  # ±10 points
            else:
                completion_modifier = 0
        else:
            completion_modifier = 0

        score = int(max(0, min(100, avg_health + completion_modifier)))

        details = {
            "project_count": len(projects),
            "avg_project_health": round(avg_health, 1),
        }

        return score, details

    def _compute_trend(self, client_id: str, current_score: int) -> str:
        """Determine health trend based on history."""
        # Get last health log
        history = self.store.query(
            """
            SELECT health_score FROM client_health_log
            WHERE client_id = ?
            ORDER BY computed_at DESC
            LIMIT 5
        """,
            [client_id],
        )

        if len(history) < 2:
            return "stable"

        # Compare current to average of last 5
        avg_previous = sum(h["health_score"] for h in history) / len(history)

        if current_score > avg_previous + 5:
            return "improving"
        if current_score < avg_previous - 5:
            return "declining"
        return "stable"

    def _get_last_activity(self, client_id: str) -> str | None:
        """Get date of last activity for client."""
        result = self.store.query(
            """
            SELECT MAX(updated_at) as last FROM tasks
            WHERE client_id = ?
        """,
            [client_id],
        )

        return result[0]["last"] if result and result[0]["last"] else None

    def _log_health(self, health: ClientHealth):
        """Log health computation for trend tracking."""
        import uuid

        now = datetime.now().isoformat()

        self.store.insert(
            "client_health_log",
            {
                "id": f"health_{uuid.uuid4().hex[:12]}",
                "client_id": health.client_id,
                "health_score": health.health_score,
                "factors": json.dumps(health.factors),
                "computed_at": now,
            },
        )

    def get_client_activity(self, client_id: str, days: int = 30) -> dict:
        """Get detailed activity breakdown for a client."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        tasks_created = self.store.query(
            """
            SELECT COUNT(*) as count FROM tasks
            WHERE client_id = ? AND created_at >= ?
        """,
            [client_id, cutoff],
        )[0]["count"]

        tasks_completed = self.store.query(
            """
            SELECT COUNT(*) as count FROM tasks
            WHERE client_id = ? AND status IN ('done', 'completed')
            AND updated_at >= ?
        """,
            [client_id, cutoff],
        )[0]["count"]

        return {
            "client_id": client_id,
            "period_days": days,
            "tasks_created": tasks_created,
            "tasks_completed": tasks_completed,
            "activity_level": "high"
            if tasks_created > 10
            else "medium"
            if tasks_created > 3
            else "low",
        }

    def get_at_risk_clients(self, threshold: int = None) -> list[ClientHealth]:
        """Get all clients with health below threshold."""
        if threshold is None:
            threshold = self.AT_RISK_THRESHOLD

        clients = self.store.query("SELECT id FROM clients")
        at_risk = []

        for client in clients:
            health = self.compute_health_score(client["id"])
            if health.health_score < threshold:
                at_risk.append(health)

        # Sort by health (worst first)
        at_risk.sort(key=lambda h: h.health_score)

        return at_risk

    def get_client_summary(self, client_id: str) -> dict:
        """Get comprehensive summary for a client."""
        health = self.compute_health_score(client_id)
        activity = self.get_client_activity(client_id)

        # Get linked projects
        projects = self.store.query(
            """
            SELECT p.* FROM projects p
            JOIN client_projects cp ON p.id = cp.project_id
            WHERE cp.client_id = ?
        """,
            [client_id],
        )

        return {
            "client_id": client_id,
            "name": health.client_name,
            "tier": health.tier,
            "health": {
                "score": health.health_score,
                "trend": health.trend,
                "at_risk": health.at_risk,
                "factors": health.factors,
            },
            "activity": activity,
            "projects": len(projects),
            "last_activity": health.last_activity,
        }


# Test
if __name__ == "__main__":
    calc = HealthCalculator()

    logger.info("Testing HealthCalculator")
    logger.info("-" * 50)
    # Get a sample client
    from lib.state_store import get_store

    store = get_store()
    clients = store.query("SELECT id, name FROM clients LIMIT 3")

    for client in clients:
        health = calc.compute_health_score(client["id"])
        logger.info(f"\n{client['name']}:")
        logger.info(f"  Score: {health.health_score}")
        logger.info(f"  Trend: {health.trend}")
        logger.info(f"  At Risk: {health.at_risk}")
        logger.info(f"  Factors: {health.factors}")
