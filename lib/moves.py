"""
Exec Moves Engine - Per MASTER_SPEC.md §18

Transforms snapshot state into 3 prioritized actions with rationale,
confidence, and drill-down. Bridges observation to execution.
"""

import json
import logging
import sqlite3
from datetime import date
from pathlib import Path

from lib import paths

logger = logging.getLogger(__name__)


DB_PATH = paths.db_path()

# Gate-to-domain mapping (duplicated from aggregator for independence)
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

DOMAIN_PRIORITY = {"cash": 10, "delivery": 8, "clients": 7, "comms": 5, "capacity": 4}


class MovesEngine:
    """Generate exec moves from snapshot."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.today = date.today()

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

    def _get_domain_confidence(self, domain: str, gates: dict) -> str:
        """Get confidence label for domain."""
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
        domain_gates = DOMAIN_GATES[domain]
        failed = [g for g in domain_gates["quality"] if not gates.get(g, False)]

        notes = {
            "client_coverage": "Client coverage incomplete",
            "commitment_ready": "Commitment extraction incomplete",
            "finance_ar_coverage": "AR data incomplete",
            "project_brand_required": "Some projects missing brand",
        }

        return notes.get(failed[0]) if failed else None

    def generate(self, snapshot: dict, max_moves: int = 3) -> list[dict]:
        """
        Generate top N moves from snapshot.

        Pipeline:
        1. Determine domain confidence from gates
        2. Collect candidate moves from non-blocked domains
        3. Tag moves with confidence labels
        4. Score and rank candidates
        5. Dedupe by entity
        6. Return top N
        """
        # Extract gate status
        gates = {g["name"]: g["passed"] for g in snapshot.get("gates", {}).get("items", [])}

        candidates = []

        # Collect from each domain generator
        domain_generators = [
            ("cash", self._generate_cash_moves),
            ("delivery", self._generate_delivery_moves),
            ("clients", self._generate_client_moves),
            ("comms", self._generate_comms_moves),
            ("capacity", self._generate_capacity_moves),
        ]

        for domain, generator in domain_generators:
            confidence = self._get_domain_confidence(domain, gates)

            # Blocked domains generate NO moves
            if confidence == "blocked":
                continue

            domain_moves = generator(snapshot)

            # Tag each move
            for move in domain_moves:
                move["domain"] = domain
                move["data_confidence"] = confidence
                if confidence == "degraded":
                    move["confidence_note"] = self._get_confidence_note(domain, gates)

            candidates.extend(domain_moves)

        # Score all candidates
        for move in candidates:
            move["score"] = self._calc_score(move, snapshot)

        # Sort by score descending
        candidates.sort(key=lambda m: -m["score"])

        # Dedupe by entity
        seen = set()
        final = []
        for move in candidates:
            key = f"{move.get('entity_type', '')}:{move.get('entity_id', '')}"
            if key not in seen:
                final.append(move)
                seen.add(key)
            if len(final) >= max_moves:
                break

        # Assign ranks and IDs
        for i, move in enumerate(final):
            move["rank"] = i + 1
            move["id"] = f"m-{i + 1:03d}"

        return final

    def _calc_score(self, move: dict, snapshot: dict) -> float:
        """
        Score a move 0-100:
        - Impact magnitude (40%)
        - Action confidence (30%)
        - Urgency (20%)
        - Domain priority (10%)
        """
        score = 0

        # Impact (0-40)
        impact = move.get("impact", {})
        if impact.get("domain") == "cash":
            amount = abs(impact.get("delta", 0))
            score += min(amount / 1000, 40)
        else:
            score += 20 if impact.get("delta") else 10

        # Action confidence (0-30)
        score += move.get("confidence", 0.5) * 30

        # Urgency (0-20)
        urgency = move.get("urgency", 0.5)
        score += urgency * 20

        # Domain priority (0-10)
        domain = move.get("domain", "")
        score += DOMAIN_PRIORITY.get(domain, 3)

        base_score = min(score, 100)

        # Data confidence penalty
        if move.get("data_confidence") == "degraded":
            return base_score * 0.8

        return base_score

    def _generate_cash_moves(self, snapshot: dict) -> list[dict]:
        """Generate cash/AR moves."""
        moves = []
        cash = snapshot.get("domains", {}).get("cash", {}).get("metrics", {})

        # Move: Chase severe AR
        if cash.get("ar_90_plus", 0) > 0:
            invoice = self._query_one("""
                SELECT i.id, i.external_id as invoice_number, i.amount, i.due_date,
                       c.id as client_id, c.name as client_name
                FROM invoices i
                LEFT JOIN clients c ON i.client_id = c.id
                WHERE i.status IN ('sent', 'overdue')
                AND i.paid_date IS NULL
                AND julianday(date('now')) - julianday(i.due_date) > 90
                ORDER BY i.amount DESC
                LIMIT 1
            """)

            if invoice:
                moves.append(
                    {
                        "title": f"Chase {invoice['client_name'] or 'Unknown'} invoice #{invoice['invoice_number']}",
                        "rationale": f"90+ days overdue (${invoice['amount']:,.0f}), largest severe AR",
                        "confidence": 0.85,
                        "urgency": 0.9,
                        "impact": {
                            "domain": "cash",
                            "metric": "ar_90_plus",
                            "delta": -invoice["amount"],
                        },
                        "action_type": "communication",
                        "entity_type": "invoice",
                        "entity_id": invoice["id"],
                        "suggested_action": {
                            "type": "email",
                            "subject": f"Invoice #{invoice['invoice_number']} — Past Due",
                            "template": "ar_followup_90",
                        },
                        "drill_url": f"#domain/cash?invoice={invoice['id']}",
                        "approval_options": [
                            "send_email",
                            "create_task",
                            "copy_to_clipboard",
                            "dismiss",
                        ],
                    }
                )

        # Move: Address invalid AR
        if cash.get("ar_invalid_count", 0) > 0:
            moves.append(
                {
                    "title": f"Fix {cash['ar_invalid_count']} invalid AR records",
                    "rationale": "Missing due_date or client blocks accurate aging",
                    "confidence": 0.9,
                    "urgency": 0.7,
                    "impact": {
                        "domain": "cash",
                        "metric": "ar_invalid_count",
                        "delta": -cash["ar_invalid_count"],
                    },
                    "action_type": "data_fix",
                    "entity_type": "invoice_batch",
                    "entity_id": "invalid_ar",
                    "suggested_action": {"type": "review", "filter": "invalid"},
                    "drill_url": "#queue?filter=ar_missing",
                    "approval_options": ["open_queue", "dismiss"],
                }
            )

        return moves

    def _generate_delivery_moves(self, snapshot: dict) -> list[dict]:
        """Generate delivery moves."""
        moves = []
        delivery = snapshot.get("domains", {}).get("delivery", {}).get("metrics", {})

        # Move: Clear overdue tasks
        overdue_count = delivery.get("overdue_tasks", 0)
        if overdue_count > 3:
            oldest = self._query_one("""
                SELECT id, title, due_date, project_id,
                       julianday(date('now')) - julianday(due_date) as days_overdue
                FROM tasks
                WHERE status != 'done'
                AND due_date < date('now')
                ORDER BY due_date ASC
                LIMIT 1
            """)

            moves.append(
                {
                    "title": f"Triage {overdue_count} overdue tasks",
                    "rationale": f"Oldest is {int(oldest['days_overdue']) if oldest else '?'} days overdue — batch review needed",
                    "confidence": 0.8,
                    "urgency": 0.8,
                    "impact": {
                        "domain": "delivery",
                        "metric": "overdue_tasks",
                        "delta": -overdue_count,
                    },
                    "action_type": "review",
                    "entity_type": "task_batch",
                    "entity_id": "overdue_triage",
                    "suggested_action": {"type": "batch_review", "filter": "overdue"},
                    "drill_url": "#domain/delivery?filter=overdue",
                    "approval_options": ["open_review", "create_task", "dismiss"],
                }
            )

        # Move: Fix unlinked tasks
        unlinked = delivery.get("unlinked_tasks", 0)
        if unlinked > 10:
            moves.append(
                {
                    "title": f"Link {unlinked} orphan tasks to projects",
                    "rationale": "Unlinked tasks break client attribution and reporting",
                    "confidence": 0.75,
                    "urgency": 0.5,
                    "impact": {
                        "domain": "delivery",
                        "metric": "unlinked_tasks",
                        "delta": -unlinked,
                    },
                    "action_type": "data_fix",
                    "entity_type": "task_batch",
                    "entity_id": "unlinked",
                    "drill_url": "#queue?filter=task_unlinked",
                    "approval_options": ["open_queue", "dismiss"],
                }
            )

        return moves

    def _generate_client_moves(self, snapshot: dict) -> list[dict]:
        """Generate client moves."""
        moves = []

        # Find at-risk clients (using overdue as proxy for health)
        at_risk = self._query_one("""
            SELECT c.id, c.name,
                   COUNT(CASE WHEN t.due_date < date('now') AND t.status != 'done' THEN 1 END) as overdue
            FROM clients c
            LEFT JOIN tasks t ON t.client_id = c.id
            GROUP BY c.id
            HAVING overdue >= 3
            ORDER BY overdue DESC
            LIMIT 1
        """)

        if at_risk:
            moves.append(
                {
                    "title": f"Check in with {at_risk['name']}",
                    "rationale": f"{at_risk['overdue']} overdue deliverables — relationship may be strained",
                    "confidence": 0.7,
                    "urgency": 0.7,
                    "impact": {
                        "domain": "clients",
                        "metric": "at_risk_clients",
                        "delta": -1,
                    },
                    "action_type": "outreach",
                    "entity_type": "client",
                    "entity_id": at_risk["id"],
                    "suggested_action": {
                        "type": "schedule_call",
                        "subject": f"Quick sync — {at_risk['name']}",
                    },
                    "drill_url": f"#domain/clients/{at_risk['id']}",
                    "approval_options": ["schedule_call", "create_task", "dismiss"],
                }
            )

        return moves

    def _generate_comms_moves(self, snapshot: dict) -> list[dict]:
        """Generate comms moves."""
        moves = []
        comms = snapshot.get("domains", {}).get("comms", {}).get("metrics", {})

        # Move: Track untracked commitments
        untracked = comms.get("commitments_untracked", 0)
        if untracked > 0:
            commitment = self._query_one("""
                SELECT c.id, c.text, c.deadline, c.speaker, c.target,
                       cl.name as client_name
                FROM commitments c
                LEFT JOIN clients cl ON c.client_id = cl.id
                WHERE c.status = 'open' AND c.task_id IS NULL
                ORDER BY c.deadline ASC NULLS LAST
                LIMIT 1
            """)

            if commitment:
                moves.append(
                    {
                        "title": f'Create task for: "{commitment["text"][:40]}..."',
                        "rationale": f"Commitment to {commitment['client_name'] or 'unknown'}, deadline {commitment['deadline'] or 'unset'}",
                        "confidence": 0.85,
                        "urgency": 0.8 if commitment["deadline"] else 0.5,
                        "impact": {
                            "domain": "comms",
                            "metric": "commitments_untracked",
                            "delta": -1,
                        },
                        "action_type": "task",
                        "entity_type": "commitment",
                        "entity_id": commitment["id"],
                        "suggested_action": {
                            "type": "create_task",
                            "title": commitment["text"][:80],
                            "due_date": commitment["deadline"],
                            "link_commitment": commitment["id"],
                        },
                        "drill_url": f"#domain/comms?commitment={commitment['id']}",
                        "approval_options": ["create_task", "dismiss", "snooze"],
                    }
                )

        # Move: Process inbox
        unprocessed = comms.get("unprocessed", 0)
        if unprocessed > 5:
            moves.append(
                {
                    "title": f"Process {unprocessed} unread communications",
                    "rationale": "Inbox backlog building — may contain commitments or urgent items",
                    "confidence": 0.7,
                    "urgency": 0.6,
                    "impact": {
                        "domain": "comms",
                        "metric": "unprocessed",
                        "delta": -unprocessed,
                    },
                    "action_type": "review",
                    "entity_type": "communication_batch",
                    "entity_id": "inbox",
                    "drill_url": "#domain/comms?filter=unprocessed",
                    "approval_options": ["open_inbox", "dismiss"],
                }
            )

        return moves

    def _generate_capacity_moves(self, snapshot: dict) -> list[dict]:
        """Generate capacity moves."""
        moves = []
        capacity = snapshot.get("domains", {}).get("capacity", {}).get("metrics", {})

        # Move: Address reality gap
        gap = capacity.get("reality_gap_hours", 0)
        if gap > 8:
            moves.append(
                {
                    "title": f"Cut scope: {gap}h gap this week",
                    "rationale": "Demand exceeds available hours — defer or delegate tasks",
                    "confidence": 0.75,
                    "urgency": 0.9,
                    "impact": {
                        "domain": "capacity",
                        "metric": "reality_gap_hours",
                        "delta": -gap,
                    },
                    "action_type": "decision",
                    "entity_type": "capacity",
                    "entity_id": "reality_gap",
                    "drill_url": "#domain/capacity",
                    "approval_options": ["open_review", "dismiss"],
                }
            )

        return moves


def generate_moves(snapshot: dict, max_moves: int = 3) -> list[dict]:
    """Convenience function to generate moves."""
    engine = MovesEngine()
    return engine.generate(snapshot, max_moves)


def add_moves_to_snapshot(snapshot: dict) -> dict:
    """Add moves to existing snapshot."""
    moves = generate_moves(snapshot)
    snapshot["moves"] = moves
    return snapshot


if __name__ == "__main__":
    # Load snapshot from file or generate
    snapshot_path = paths.out_dir() / "snapshot.json"

    if snapshot_path.exists():
        with open(snapshot_path) as f:
            snapshot = json.load(f)
    else:
        from .aggregator import generate_snapshot

        snapshot = generate_snapshot()

    moves = generate_moves(snapshot)
    logger.info(json.dumps(moves, indent=2, default=str))
