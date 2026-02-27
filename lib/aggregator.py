"""
Aggregator Module - Produces unified snapshot.json per MASTER_SPEC.md §15.3

Single artifact containing all dashboard data:
- meta: run metadata
- gates: pass/fail status
- queue: resolution queue items
- risks: ranked cross-domain risks
- domains: per-domain metrics
- deltas: changes since last run
- moves: exec recommendations (added by moves engine)
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from lib import paths

from .gates import GateEvaluator

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()
OUTPUT_PATH = paths.out_dir()

# Gate-to-domain mapping per §15.4
DOMAIN_GATES = {
    "delivery": {
        "blocking": ["data_integrity"],
        "quality": ["project_brand_required", "project_client_populated"],
    },
    "clients": {"blocking": ["data_integrity"], "quality": ["client_coverage"]},
    "cash": {
        "blocking": ["data_integrity", "finance_ar_clean"],
        "quality": ["finance_ar_coverage"],
    },
    "comms": {"blocking": ["data_integrity"], "quality": ["commitment_ready"]},
    "capacity": {"blocking": ["data_integrity", "capacity_baseline"], "quality": []},
}


class SnapshotAggregator:
    """Aggregates all data into unified snapshot.json."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.gate_evaluator = GateEvaluator(db_path)
        self.today = date.today()
        self._gates_cache = None

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _query_scalar(self, sql: str, params: tuple = ()) -> Any:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def generate(self, started_at: datetime = None) -> dict:
        """Generate complete snapshot."""
        started_at = started_at or datetime.now()

        # Evaluate gates first (needed for confidence labels)
        gates_result = self.gate_evaluator.evaluate_all()
        self._gates_cache = gates_result

        snapshot = {
            "meta": self._build_meta(started_at, gates_result),
            "gates": self._build_gates(gates_result),
            "queue": self._build_queue(),
            "risks": self._build_risks(gates_result),
            "domains": self._build_domains(gates_result),
            "deltas": self._build_deltas(),
        }

        snapshot["meta"]["finished_at"] = datetime.now().isoformat()
        snapshot["meta"]["duration_seconds"] = (datetime.now() - started_at).total_seconds()

        return snapshot

    def _build_meta(self, started_at: datetime, gates: dict) -> dict:
        """Build meta section."""
        blocking_failed = [
            g
            for domain in DOMAIN_GATES.values()
            for g in domain["blocking"]
            if not gates.get(g, False)
        ]

        # Determine confidence level
        if blocking_failed:
            confidence = "blocked"
        elif any(
            not gates.get(g, True) for domain in DOMAIN_GATES.values() for g in domain["quality"]
        ):
            confidence = "degraded"
        else:
            confidence = "healthy"

        # Map blocked gates to capabilities
        capability_map = {
            "data_integrity": "all",
            "capacity_baseline": "capacity_planning",
            "finance_ar_clean": "ar_tracking",
            "commitment_ready": "commitment_tracking",
        }
        blocked_capabilities = list({capability_map.get(g, g) for g in blocking_failed})

        return {
            "run_id": started_at.isoformat(),
            "started_at": started_at.isoformat(),
            "finished_at": None,  # Filled at end
            "duration_seconds": None,
            "confidence": confidence,
            "blocked_capabilities": blocked_capabilities,
        }

    def _build_gates(self, gates: dict) -> dict:
        """Build gates section."""
        items = []

        # Blocking gates
        blocking_gates = ["data_integrity", "finance_ar_clean", "capacity_baseline"]
        quality_gates = [
            ("client_coverage", 80.0),
            ("commitment_ready", 50.0),
            ("finance_ar_coverage", 95.0),
            ("project_brand_required", None),
            ("project_brand_consistency", None),
            ("project_client_populated", None),
            ("internal_project_client_null", None),
        ]

        for gate in blocking_gates:
            items.append(
                {
                    "name": gate,
                    "passed": gates.get(gate, False),
                    "blocking": True,
                    "value": None,
                    "target": None,
                }
            )

        for gate, target in quality_gates:
            value = gates.get(f"{gate}_pct") if target else None
            items.append(
                {
                    "name": gate,
                    "passed": gates.get(gate, False),
                    "blocking": False,
                    "value": round(value, 1) if value is not None else None,
                    "target": target,
                }
            )

        passed = sum(1 for i in items if i["passed"])

        return {
            "summary": {
                "passed": passed,
                "failed": len(items) - passed,
                "total": len(items),
            },
            "items": items,
        }

    def _build_queue(self) -> dict:
        """Build resolution queue section with entity names."""
        items = self._query_all("""
            SELECT
                rq.id,
                CASE rq.priority WHEN 1 THEN 'P1' WHEN 2 THEN 'P2' ELSE 'P3' END as priority,
                rq.issue_type,
                rq.entity_type,
                rq.entity_id,
                rq.context,
                rq.created_at,
                CASE
                    WHEN rq.entity_type = 'task' THEN t.title
                    WHEN rq.entity_type = 'project' THEN p.name
                    WHEN rq.entity_type = 'client' THEN c.name
                    WHEN rq.entity_type = 'invoice' THEN i.external_id
                    ELSE NULL
                END as entity_name
            FROM resolution_queue rq
            LEFT JOIN tasks t ON rq.entity_type = 'task' AND rq.entity_id = t.id
            LEFT JOIN projects p ON rq.entity_type = 'project' AND rq.entity_id = p.id
            LEFT JOIN clients c ON rq.entity_type = 'client' AND rq.entity_id = c.id
            LEFT JOIN invoices i ON rq.entity_type = 'invoice' AND rq.entity_id = i.id
            WHERE rq.resolved_at IS NULL
            ORDER BY rq.priority, rq.created_at
        """)

        p1_count = sum(1 for i in items if i.get("priority") == "P1")
        p2_count = sum(1 for i in items if i.get("priority") == "P2")

        # Format items for output
        formatted_items = []
        for item in items:
            entity_name = item.get("entity_name") or item["entity_id"][:12] + "..."
            formatted_items.append(
                {
                    "id": item["id"],
                    "priority": item.get("priority", "P2"),
                    "issue_type": item["issue_type"],
                    "entity_type": item["entity_type"],
                    "entity_id": item["entity_id"],
                    "entity_name": entity_name,
                    "summary": item.get("context")
                    or f"{item['issue_type'].replace('_', ' ')}: {entity_name}",
                    "created_at": item["created_at"],
                }
            )

        return {"p1_count": p1_count, "p2_count": p2_count, "items": formatted_items}

    def _get_domain_confidence(self, domain: str, gates: dict) -> str:
        """Get confidence label for domain based on gate status."""
        domain_gates = DOMAIN_GATES.get(domain, {"blocking": [], "quality": []})

        for gate in domain_gates["blocking"]:
            if not gates.get(gate, False):
                return "blocked"

        for gate in domain_gates["quality"]:
            if not gates.get(gate, False):
                return "degraded"

        return "reliable"

    def _get_confidence_note(self, domain: str, gates: dict) -> str | None:
        """Get human-readable note for degraded confidence."""
        confidence = self._get_domain_confidence(domain, gates)
        if confidence == "reliable":
            return None

        domain_gates = DOMAIN_GATES[domain]
        failed = [g for g in domain_gates["quality"] if not gates.get(g, False)]

        notes = {
            "client_coverage": f"Client coverage at {gates.get('client_coverage_pct', 0):.0f}%",
            "commitment_ready": f"Commitment extraction at {gates.get('commitment_ready_pct', 0):.0f}%",
            "finance_ar_coverage": "AR data incomplete",
            "project_brand_required": "Some projects missing brand",
        }

        return notes.get(failed[0]) if failed else "Data quality below threshold"

    def _build_risks(self, gates: dict) -> dict:
        """Build ranked risks section."""
        risks = []

        # Collect risks from each domain (skip blocked)
        for domain, collector in [
            ("delivery", self._collect_delivery_risks),
            ("clients", self._collect_client_risks),
            ("cash", self._collect_cash_risks),
            ("comms", self._collect_comms_risks),
            ("capacity", self._collect_capacity_risks),
        ]:
            confidence = self._get_domain_confidence(domain, gates)
            if confidence == "blocked":
                continue

            domain_risks = collector()
            for risk in domain_risks:
                risk["domain"] = domain
                risk["data_confidence"] = confidence
                if confidence == "degraded":
                    risk["confidence_note"] = self._get_confidence_note(domain, gates)
                    risk["score"] = risk.get("score", 50) * 0.8  # 20% penalty
                risks.append(risk)

        # Sort by score descending
        risks.sort(key=lambda r: -r.get("score", 0))

        # Assign ranks and limit to top 7
        for i, risk in enumerate(risks[:7]):
            risk["rank"] = i + 1
            risk["id"] = f"r-{i + 1:03d}"

        return {"items": risks[:7]}

    def _collect_delivery_risks(self) -> list[dict]:
        """Collect delivery domain risks."""
        risks = []
        today_str = self.today.isoformat()

        # Overdue tasks
        overdue = self._query_all(
            """
            SELECT id, title, due_date, priority,
                   julianday(?) - julianday(due_date) as days_overdue
            FROM tasks
            WHERE status != 'done'
            AND due_date IS NOT NULL
            AND due_date < ?
            ORDER BY days_overdue DESC
            LIMIT 5
        """,
            (today_str, today_str),
        )

        for task in overdue:
            score = 40 + min(task["days_overdue"] * 5, 25)
            if task.get("priority") in ("P1", "critical", "high"):
                score += 20

            risks.append(
                {
                    "type": "task_overdue",
                    "title": f"Task overdue: {task['title'][:50]}",
                    "driver": f"{int(task['days_overdue'])} days overdue",
                    "score": min(score, 100),
                    "entity_type": "task",
                    "entity_id": task["id"],
                    "drill_url": f"#domain/delivery?task={task['id']}",
                }
            )

        # Off-track projects
        off_track = self._query_all(
            """
            SELECT p.id, p.name,
                   COUNT(CASE WHEN t.due_date < ? AND t.status != 'done' THEN 1 END) as overdue_count
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id
            WHERE p.is_internal = 0
            GROUP BY p.id
            HAVING overdue_count >= 2
            LIMIT 3
        """,
            (today_str,),
        )

        for proj in off_track:
            risks.append(
                {
                    "type": "project_off_track",
                    "title": f"Project off track: {proj['name'][:40]}",
                    "driver": f"{proj['overdue_count']} overdue tasks",
                    "score": 60 + min(proj["overdue_count"] * 5, 20),
                    "entity_type": "project",
                    "entity_id": proj["id"],
                    "drill_url": f"#domain/delivery?project={proj['id']}",
                }
            )

        return risks

    def _collect_client_risks(self) -> list[dict]:
        """Collect client domain risks."""
        risks = []

        # Low health clients (would need health scores computed)
        # For now, use overdue task count as proxy
        at_risk = self._query_all("""
            SELECT c.id, c.name,
                   COUNT(CASE WHEN t.due_date < date('now') AND t.status != 'done' THEN 1 END) as overdue_count
            FROM clients c
            LEFT JOIN tasks t ON t.client_id = c.id
            GROUP BY c.id
            HAVING overdue_count >= 2
            ORDER BY overdue_count DESC
            LIMIT 3
        """)

        for client in at_risk:
            risks.append(
                {
                    "type": "client_health_drop",
                    "title": f"Client at risk: {client['name'][:40]}",
                    "driver": f"{client['overdue_count']} overdue deliverables",
                    "score": 45 + min(client["overdue_count"] * 10, 30),
                    "entity_type": "client",
                    "entity_id": client["id"],
                    "drill_url": f"#domain/clients/{client['id']}",
                }
            )

        return risks

    def _collect_cash_risks(self) -> list[dict]:
        """Collect cash/AR domain risks."""
        risks = []

        # Severe AR (90+ days)
        severe = self._query_all("""
            SELECT id, external_id, amount, client_id, client_name, due_date,
                   julianday(date('now')) - julianday(due_date) as days_overdue
            FROM invoices
            WHERE status IN ('sent', 'overdue')
            AND paid_date IS NULL
            AND due_date IS NOT NULL
            AND julianday(date('now')) - julianday(due_date) > 90
            ORDER BY amount DESC
            LIMIT 3
        """)

        for inv in severe:
            score = 70 + min(inv["amount"] * 0.001, 30)
            inv_label = inv.get("external_id") or inv["id"][:8]
            risks.append(
                {
                    "type": "ar_severe",
                    "title": f"Invoice {inv_label} 90+ days overdue",
                    "driver": f"${inv['amount']:,.0f} outstanding from {inv.get('client_name', 'Unknown')}",
                    "impact": inv["amount"],
                    "score": min(score, 100),
                    "entity_type": "invoice",
                    "entity_id": inv["id"],
                    "drill_url": f"#domain/cash?invoice={inv['id']}",
                }
            )

        # Concentration risk
        concentration = self._query_one("""
            SELECT
                MAX(client_total) as top_amount,
                SUM(amount) as total_ar,
                100.0 * MAX(client_total) / NULLIF(SUM(amount), 0) as top_share
            FROM (
                SELECT client_id, SUM(amount) as client_total, amount
                FROM invoices
                WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
                GROUP BY client_id
            )
        """)

        if concentration and concentration["top_share"] and concentration["top_share"] > 30:
            risks.append(
                {
                    "type": "ar_concentration",
                    "title": f"AR concentration risk: {concentration['top_share']:.0f}% single client",
                    "driver": f"Top client has ${concentration['top_amount']:,.0f} of ${concentration['total_ar']:,.0f}",
                    "score": 50 + (20 if concentration["top_share"] > 40 else 0),
                    "entity_type": "portfolio",
                    "entity_id": "ar_concentration",
                    "drill_url": "#domain/cash?view=concentration",
                }
            )

        return risks

    def _collect_comms_risks(self) -> list[dict]:
        """Collect comms domain risks."""
        risks = []

        # Untracked commitments
        untracked = (
            self._query_scalar("""
            SELECT COUNT(*) FROM commitments
            WHERE status = 'open' AND task_id IS NULL
        """)
            or 0
        )

        if untracked > 0:
            risks.append(
                {
                    "type": "commitment_untracked",
                    "title": f"{untracked} commitments without tasks",
                    "driver": "Promises/requests not being tracked",
                    "score": 55 + min(untracked * 5, 25),
                    "entity_type": "commitment_batch",
                    "entity_id": "untracked",
                    "drill_url": "#domain/comms?filter=untracked",
                }
            )

        return risks

    def _collect_capacity_risks(self) -> list[dict]:
        """Collect capacity domain risks."""
        risks = []

        # Check lane-based capacity if available
        try:
            lanes = self._query_all("""
                SELECT name, weekly_hours FROM lanes WHERE weekly_hours > 0
            """)
            for lane in lanes:
                if lane.get("weekly_hours", 0) > 50:
                    risks.append(
                        {
                            "domain": "capacity",
                            "risk": f"Lane '{lane['name']}' over-allocated at {lane['weekly_hours']}h/week",
                            "severity": "medium",
                            "entity": lane["name"],
                        }
                    )
        except sqlite3.OperationalError:
            pass  # Lanes table not yet created

        # Fall back to task-based capacity estimation
        try:
            overloaded = self._query_all("""
                SELECT assignee, COUNT(*) as task_count,
                       SUM(CASE WHEN status NOT IN ('done','complete','completed')
                                 AND due_date < date('now') THEN 1 ELSE 0 END) as overdue
                FROM tasks
                WHERE status NOT IN ('done','complete','completed')
                GROUP BY assignee
                HAVING task_count > 15 OR overdue > 5
            """)
            for person in overloaded:
                name = person.get("assignee", "Unknown")
                count = person.get("task_count", 0)
                overdue = person.get("overdue", 0)
                risks.append(
                    {
                        "domain": "capacity",
                        "risk": f"{name}: {count} active tasks ({overdue} overdue)",
                        "severity": "high" if overdue > 5 else "medium",
                        "entity": name,
                    }
                )
        except sqlite3.OperationalError as e:
            logger.debug(f"Task-based capacity check failed: {e}")

        return risks

    def _build_domains(self, gates: dict) -> dict:
        """Build per-domain metrics."""
        return {
            "delivery": self._build_delivery_metrics(gates),
            "clients": self._build_client_metrics(gates),
            "cash": self._build_cash_metrics(gates),
            "comms": self._build_comms_metrics(gates),
            "capacity": self._build_capacity_metrics(gates),
            "data": self._build_data_metrics(gates),
        }

    def _build_delivery_metrics(self, gates: dict) -> dict:
        today_str = self.today.isoformat()

        metrics = (
            self._query_one(
                """
            SELECT
                COUNT(DISTINCT CASE WHEN p.is_internal = 0 THEN p.id END) as total_projects,
                COUNT(CASE WHEN t.due_date < ? AND t.status != 'done' THEN 1 END) as overdue_tasks,
                COUNT(CASE WHEN t.project_link_status = 'unlinked' THEN 1 END) as unlinked_tasks,
                COUNT(CASE WHEN t.project_link_status = 'partial' THEN 1 END) as partial_tasks,
                COUNT(CASE WHEN t.due_date BETWEEN ? AND date(?, '+7 days') AND t.status != 'done' THEN 1 END) as due_7d_count
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
        """,
                (today_str, today_str, today_str),
            )
            or {}
        )

        confidence = self._get_domain_confidence("delivery", gates)
        overdue = metrics.get("overdue_tasks", 0)

        if confidence == "blocked":
            status = "blocked"
            driver = "Data integrity check failed"
        elif overdue > 5:
            status = "degraded"
            driver = f"{overdue} overdue tasks"
        else:
            status = "healthy"
            driver = "On track"

        return {
            "status": status,
            "driver": driver,
            "metrics": {
                "total_projects": metrics.get("total_projects", 0),
                "overdue_tasks": overdue,
                "unlinked_tasks": metrics.get("unlinked_tasks", 0),
                "partial_tasks": metrics.get("partial_tasks", 0),
                "due_7d_count": metrics.get("due_7d_count", 0),
            },
        }

    def _build_client_metrics(self, gates: dict) -> dict:
        metrics = (
            self._query_one("""
            SELECT COUNT(*) as total_clients FROM clients
        """)
            or {}
        )

        # Get client list with health indicators
        clients = self._query_all("""
            SELECT
                c.id,
                c.name,
                c.tier,
                c.health_score,
                COUNT(DISTINCT CASE WHEN t.due_date < date('now') AND t.status != 'done' THEN t.id END) as overdue_tasks,
                COUNT(DISTINCT t.id) as total_tasks,
                MAX(t.updated_at) as last_activity
            FROM clients c
            LEFT JOIN tasks t ON t.client_id = c.id
            GROUP BY c.id
            ORDER BY overdue_tasks DESC, c.name
            LIMIT 50
        """)

        # Calculate health for clients without stored score
        client_list = []
        at_risk_count = 0
        for client in clients:
            overdue = client.get("overdue_tasks", 0) or 0
            health = client.get("health_score")

            if health is None:
                # Simple health calculation: 100 - (overdue * 15), min 0
                health = max(0, 100 - (overdue * 15))

            if health < 50:
                at_risk_count += 1

            client_list.append(
                {
                    "id": client["id"],
                    "name": client["name"],
                    "tier": client.get("tier", "C"),
                    "health_score": round(health, 0),
                    "overdue_tasks": overdue,
                    "total_tasks": client.get("total_tasks", 0) or 0,
                    "status": "critical"
                    if health < 40
                    else "at_risk"
                    if health < 60
                    else "watch"
                    if health < 80
                    else "healthy",
                }
            )

        confidence = self._get_domain_confidence("clients", gates)

        if confidence == "blocked":
            status = "blocked"
            driver = "Data integrity check failed"
        elif at_risk_count > 0:
            status = "degraded"
            driver = f"{at_risk_count} clients at risk"
        elif confidence == "degraded":
            status = "degraded"
            driver = f"Client coverage at {gates.get('client_coverage_pct', 0):.0f}%"
        else:
            status = "healthy"
            driver = "No critical issues"

        return {
            "status": status,
            "driver": driver,
            "metrics": {
                "total_clients": metrics.get("total_clients", 0),
                "client_coverage_pct": gates.get("client_coverage_pct", 0),
                "at_risk_count": at_risk_count,
            },
            "clients": client_list,
        }

    def _build_cash_metrics(self, gates: dict) -> dict:
        ar = (
            self._query_one("""
            SELECT
                SUM(amount) as ar_total,
                SUM(CASE WHEN due_date >= date('now') THEN amount ELSE 0 END) as ar_current,
                SUM(CASE WHEN julianday(date('now')) - julianday(due_date) BETWEEN 1 AND 30 THEN amount ELSE 0 END) as ar_1_30,
                SUM(CASE WHEN julianday(date('now')) - julianday(due_date) BETWEEN 31 AND 60 THEN amount ELSE 0 END) as ar_31_60,
                SUM(CASE WHEN julianday(date('now')) - julianday(due_date) BETWEEN 61 AND 90 THEN amount ELSE 0 END) as ar_61_90,
                SUM(CASE WHEN julianday(date('now')) - julianday(due_date) > 90 THEN amount ELSE 0 END) as ar_90_plus,
                COUNT(CASE WHEN due_date IS NULL OR client_id IS NULL THEN 1 END) as ar_invalid_count
            FROM invoices
            WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
        """)
            or {}
        )

        confidence = self._get_domain_confidence("cash", gates)
        severe = ar.get("ar_90_plus", 0) or 0

        if confidence == "blocked":
            status = "blocked"
            driver = "AR data check failed"
        elif severe > 0:
            status = "degraded"
            driver = f"${severe:,.0f} in 90+ bucket"
        else:
            status = "healthy"
            driver = "AR healthy"

        return {
            "status": status,
            "driver": driver,
            "metrics": {
                "ar_total": ar.get("ar_total", 0) or 0,
                "ar_current": ar.get("ar_current", 0) or 0,
                "ar_1_30": ar.get("ar_1_30", 0) or 0,
                "ar_31_60": ar.get("ar_31_60", 0) or 0,
                "ar_61_90": ar.get("ar_61_90", 0) or 0,
                "ar_90_plus": severe,
                "ar_invalid_count": ar.get("ar_invalid_count", 0) or 0,
            },
        }

    def _build_comms_metrics(self, gates: dict) -> dict:
        metrics = (
            self._query_one("""
            SELECT
                COUNT(CASE WHEN processed = 0 THEN 1 END) as unprocessed,
                COUNT(*) as total
            FROM communications
        """)
            or {}
        )

        commitments = (
            self._query_one("""
            SELECT
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_count,
                COUNT(CASE WHEN status = 'open' AND task_id IS NULL THEN 1 END) as untracked
            FROM commitments
        """)
            or {}
        )

        confidence = self._get_domain_confidence("comms", gates)
        unprocessed = metrics.get("unprocessed", 0) or 0

        if confidence == "blocked":
            status = "blocked"
            driver = "Data integrity check failed"
        elif confidence == "degraded":
            status = "degraded"
            driver = f"Commitment extraction at {gates.get('commitment_ready_pct', 0):.0f}%"
        elif unprocessed > 10:
            status = "degraded"
            driver = f"{unprocessed} unprocessed communications"
        else:
            status = "healthy"
            driver = "Inbox manageable"

        return {
            "status": status,
            "driver": driver,
            "metrics": {
                "unprocessed": unprocessed,
                "commitments_open": commitments.get("open_count", 0) or 0,
                "commitments_untracked": commitments.get("untracked", 0) or 0,
            },
        }

    def _build_capacity_metrics(self, gates: dict) -> dict:
        confidence = self._get_domain_confidence("capacity", gates)

        # Simplified - would need full capacity tracking
        if confidence == "blocked":
            status = "blocked"
            driver = "Capacity baseline not set"
        else:
            status = "healthy"
            driver = "Capacity tracking pending"

        return {
            "status": status,
            "driver": driver,
            "metrics": {"lanes": [], "reality_gap_hours": 0},
        }

    def _build_data_metrics(self, gates: dict) -> dict:
        passed = sum(1 for k, v in gates.items() if isinstance(v, bool) and v)
        total = sum(1 for k, v in gates.items() if isinstance(v, bool))

        if not gates.get("data_integrity", False):
            status = "blocked"
            driver = "Data integrity failed"
        elif passed < total:
            status = "degraded"
            driver = f"{total - passed} gates failing"
        else:
            status = "healthy"
            driver = "All gates passing"

        return {
            "status": status,
            "driver": driver,
            "metrics": {
                "gates_passed": passed,
                "gates_failed": total - passed,
                "client_coverage_pct": gates.get("client_coverage_pct", 0),
                "commitment_ready_pct": gates.get("commitment_ready_pct", 0),
            },
        }

    def _build_deltas(self) -> dict:
        """Build deltas by comparing to previous snapshot."""
        prev_path = OUTPUT_PATH / "previous_snapshot.json"

        if not prev_path.exists():
            return {
                "gate_flips": [],
                "queue_p1": {"previous": None, "current": None, "delta": None},
                "queue_p2": {"previous": None, "current": None, "delta": None},
                "ar_total": {"previous": None, "current": None, "delta": None},
                "ar_severe": {"previous": None, "current": None, "delta": None},
                "overdue_count": {"previous": None, "current": None, "delta": None},
                "first_run": True,
            }

        try:
            with open(prev_path) as f:
                json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"first_run": True, "error": "Could not read previous snapshot"}

        # This will be populated after we have current values
        # For now, return empty - will be filled in by save()
        return {"pending": True}

    def save(self, snapshot: dict) -> Path:
        """Save snapshot and compute deltas."""
        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

        current_path = OUTPUT_PATH / "snapshot.json"
        prev_path = OUTPUT_PATH / "previous_snapshot.json"

        # Load previous for delta computation
        prev = None
        if prev_path.exists():
            try:
                with open(prev_path) as f:
                    prev = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not load previous snapshot: {e}")

        # Compute deltas
        if prev:
            prev_gates = {g["name"]: g["passed"] for g in prev.get("gates", {}).get("items", [])}
            curr_gates = {
                g["name"]: g["passed"] for g in snapshot.get("gates", {}).get("items", [])
            }

            gate_flips = []
            for gate, passed in curr_gates.items():
                prev_passed = prev_gates.get(gate)
                if prev_passed is not None and prev_passed != passed:
                    gate_flips.append({"gate": gate, "from": prev_passed, "to": passed})

            prev_queue = prev.get("queue", {})
            prev_domains = prev.get("domains", {})
            curr_domains = snapshot.get("domains", {})

            snapshot["deltas"] = {
                "gate_flips": gate_flips,
                "queue_p1": self._delta(prev_queue.get("p1_count"), snapshot["queue"]["p1_count"]),
                "queue_p2": self._delta(prev_queue.get("p2_count"), snapshot["queue"]["p2_count"]),
                "ar_total": self._delta(
                    prev_domains.get("cash", {}).get("metrics", {}).get("ar_total"),
                    curr_domains.get("cash", {}).get("metrics", {}).get("ar_total"),
                ),
                "ar_severe": self._delta(
                    prev_domains.get("cash", {}).get("metrics", {}).get("ar_90_plus"),
                    curr_domains.get("cash", {}).get("metrics", {}).get("ar_90_plus"),
                ),
                "overdue_count": self._delta(
                    prev_domains.get("delivery", {}).get("metrics", {}).get("overdue_tasks"),
                    curr_domains.get("delivery", {}).get("metrics", {}).get("overdue_tasks"),
                ),
                "first_run": False,
            }
        else:
            snapshot["deltas"] = {"first_run": True}

        # Rotate: current -> previous
        if current_path.exists():
            current_path.rename(prev_path)

        # Write new snapshot
        with open(current_path, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)

        return current_path

    def _delta(self, prev: Any, curr: Any) -> dict:
        if prev is None or curr is None:
            return {"previous": prev, "current": curr, "delta": None}
        return {"previous": prev, "current": curr, "delta": curr - prev}


def generate_snapshot() -> dict:
    """Convenience function to generate and save snapshot."""
    aggregator = SnapshotAggregator()
    snapshot = aggregator.generate()
    aggregator.save(snapshot)
    return snapshot


if __name__ == "__main__":
    snapshot = generate_snapshot()
    logger.info(json.dumps(snapshot, indent=2, default=str))
