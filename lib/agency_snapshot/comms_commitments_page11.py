"""
Comms/Commitments Command Engine - Page 11 LOCKED SPEC (v1)

Relationship Inbox with Consequence: not email, but ranked consequence threads + breach queue.

Hard rule: no mailbox scrolling. Default surface is ranked moves + threads + breach queue.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from lib import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()


# ==============================================================================
# ENUMS & TYPES (per spec)
# ==============================================================================


class Mode(StrEnum):
    OPS_HEAD = "Ops Head"
    CO_FOUNDER = "Co-Founder"
    ARTIST = "Artist"


class Horizon(StrEnum):
    NOW = "NOW"
    TODAY = "TODAY"
    THIS_WEEK = "THIS WEEK"


class Direction(StrEnum):
    """Thread direction per §6.2"""

    INBOUND_WAITING_US = "INBOUND_WAITING_US"
    OUTBOUND_WAITING_THEM = "OUTBOUND_WAITING_THEM"
    MIXED = "MIXED"


class RiskBand(StrEnum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class DeadlineState(StrEnum):
    """Commitment deadline state per §6.4"""

    OVERDUE = "OVERDUE"
    DUE_SOON = "DUE_SOON"  # ≤72h
    FAR = "FAR"
    NO_DEADLINE = "NO_DEADLINE"


class MoveType(StrEnum):
    """Move types per Zone C (immutable)"""

    RESPONSE_BREACH_RESCUE = "RESPONSE_BREACH_RESCUE"
    VIP_ESCALATION = "VIP_ESCALATION"
    COMMITMENT_REPAIR = "COMMITMENT_REPAIR"
    DEADLINE_CLARIFICATION = "DEADLINE_CLARIFICATION"
    SCOPE_APPROVAL_UNBLOCK = "SCOPE_APPROVAL_UNBLOCK"
    WAITING_ON_THEM_NUDGE = "WAITING_ON_THEM_NUDGE"
    UNKNOWN_TRIAGE = "UNKNOWN_TRIAGE"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class ActionRisk(StrEnum):
    AUTO = "auto"
    PROPOSE = "propose"
    APPROVAL = "approval"


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class ThreadUnit:
    """Per §3.1"""

    thread_id: str
    client_id: str | None
    client_name: str | None
    subject: str
    counterparty: str
    age_hours: float
    last_received_at: str
    direction: Direction
    expected_response_by: str | None
    response_deadline_source: str  # explicit|inferred|none
    risk_band: RiskBand
    score: float
    confidence: Confidence
    why_low: list[str]
    evidence_ids: list[str]
    linked_commitments: list[str]
    linked_tasks: list[dict]
    why_surfaced: str
    is_vip: bool = False
    tier: str | None = None


@dataclass
class CommitmentUnit:
    """Per §3.2"""

    commitment_id: str
    client_id: str | None
    client_name: str | None
    text: str
    type: str  # promise|request
    status: str  # open|broken|fulfilled|cancelled
    deadline: str | None
    deadline_state: DeadlineState
    confidence: float
    confidence_band: Confidence
    source_thread_id: str | None
    risk_band: RiskBand
    consequence_at: str | None
    why_low: list[str]
    speaker: str | None = None
    target: str | None = None
    created_at: str | None = None


# ==============================================================================
# ENGINE
# ==============================================================================


class CommsCommitmentsPage11Engine:
    """
    Generates Comms/Commitments Command snapshot per Page 11 LOCKED SPEC.

    Scoring formula (§7.1):
    BaseScore = w_I*Impact + w_U*Urgency + w_C*Controllability + w_Q*Confidence
    Weights: w_I=0.35, w_U=0.30, w_C=0.20, w_Q=0.15
    """

    # Hard caps per §11.2
    MAX_MOVES = 7
    MAX_THREADS = 25
    MAX_LADDER = 5
    MAX_DRAWER_TIMELINE = 6
    MAX_DRAWER_COMMITMENTS = 5
    MAX_DRAWER_WORK = 3
    MAX_DRAWER_ACTIONS = 4
    MAX_DRAWER_EVIDENCE = 3
    MAX_DRAWER_RELATED = 3

    # Scoring weights per §7.1 (LOCKED)
    W_I = 0.35  # Impact
    W_U = 0.30  # Urgency
    W_C = 0.20  # Controllability
    W_Q = 0.15  # Confidence

    # Mode multipliers per §7.2 (LOCKED)
    MODE_MULTIPLIERS = {
        Mode.OPS_HEAD: {
            MoveType.RESPONSE_BREACH_RESCUE: 1.20,
            MoveType.SCOPE_APPROVAL_UNBLOCK: 1.15,
            MoveType.WAITING_ON_THEM_NUDGE: 1.05,
        },
        Mode.CO_FOUNDER: {
            MoveType.VIP_ESCALATION: 1.25,
            MoveType.COMMITMENT_REPAIR: 1.20,
            MoveType.RESPONSE_BREACH_RESCUE: 1.15,  # churn-sensitive
        },
        Mode.ARTIST: {
            MoveType.VIP_ESCALATION: 1.25,  # stakeholder/reputation
            MoveType.COMMITMENT_REPAIR: 1.10,
            MoveType.WAITING_ON_THEM_NUDGE: 0.95,
        },
    }

    def __init__(
        self,
        db_path: Path = DB_PATH,
        mode: Mode = Mode.OPS_HEAD,
        horizon: Horizon = Horizon.TODAY,
    ):
        self.db_path = db_path
        self.mode = mode
        self.horizon = horizon
        self.now = datetime.now()
        self.today = date.today()

        # Trust state
        self.data_integrity = True
        self.commitment_ready = True
        self.commitment_ready_pct = 100.0
        self.client_coverage = True
        self.client_coverage_pct = 100.0
        self.comms_body_coverage = 100.0
        self.comms_link_coverage = 100.0
        self.delta_available = False

        # Our email domains (for direction detection)
        self.our_domains = ["hrmny.co", "hrmny.ae", "harmonydigital.co"]

        # Cache
        self._threads_cache: dict[str, ThreadUnit] = {}
        self._commitments_cache: dict[str, CommitmentUnit] = {}

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

    def _query_scalar(self, sql: str, params: tuple = ()) -> Any:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    # ==========================================================================
    # TRUST & GATES (§2)
    # ==========================================================================

    def load_trust_state(self):
        """Load trust state from gates or compute."""
        try:
            from lib.gates import evaluate_gates

            gates = evaluate_gates()

            self.data_integrity = gates.get("data_integrity", True)
            self.commitment_ready_pct = gates.get("commitment_ready_pct", 100.0)
            self.commitment_ready = self.commitment_ready_pct >= 50
            self.client_coverage_pct = gates.get("client_coverage_pct", 100.0)
            self.client_coverage = self.client_coverage_pct >= 80
        except Exception as e:
            logger.warning(f"Could not evaluate gates: {e}")

        # Compute comms coverage
        total_comms = self._query_scalar("SELECT COUNT(*) FROM communications") or 0
        if total_comms > 0:
            with_body = (
                self._query_scalar("""
                SELECT COUNT(*) FROM communications
                WHERE body_text IS NOT NULL AND LENGTH(body_text) >= 50
            """)
                or 0
            )
            self.comms_body_coverage = (with_body / total_comms) * 100

            linked = (
                self._query_scalar("""
                SELECT COUNT(*) FROM communications
                WHERE client_id IS NOT NULL
            """)
                or 0
            )
            self.comms_link_coverage = (linked / total_comms) * 100

        # Check delta availability
        try:
            self.delta_available = False  # Not implemented yet
        except Exception as e:
            logger.debug(f"Delta check failed: {e}")
            self.delta_available = False

    def _get_overall_confidence(self) -> tuple[Confidence, list[str]]:
        """Get overall page confidence."""
        why_low = []

        if not self.commitment_ready:
            why_low.append(f"Commitment ready {self.commitment_ready_pct:.0f}% < 50%")
        if not self.client_coverage:
            why_low.append(f"Client coverage {self.client_coverage_pct:.0f}% < 80%")
        if self.comms_body_coverage < 30:
            why_low.append(f"Body coverage {self.comms_body_coverage:.0f}% < 30%")

        if len(why_low) >= 2:
            return Confidence.LOW, why_low[:3]
        if len(why_low) == 1:
            return Confidence.MED, why_low
        return Confidence.HIGH, []

    # ==========================================================================
    # THREAD BUILDING (§3.1, §6)
    # ==========================================================================

    def build_threads(self) -> list[ThreadUnit]:
        """Build all ThreadUnits from communications."""
        # Get all threads (grouped by thread_id)
        threads_data = self._query_all("""
            SELECT
                COALESCE(thread_id, id) as thread_id,
                MAX(id) as latest_id,
                MAX(client_id) as client_id,
                MAX(subject) as subject,
                MAX(from_email) as from_email,
                MAX(from_domain) as from_domain,
                MAX(from_name) as from_name,
                MAX(received_at) as last_received_at,
                MAX(COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24)) as age_hours,
                MAX(expected_response_by) as expected_response_by,
                MAX(response_deadline) as response_deadline,
                MAX(requires_response) as requires_response,
                MAX(is_vip) as is_vip,
                MAX(stakeholder_tier) as stakeholder_tier,
                MAX(is_important) as is_important,
                MAX(priority) as priority,
                COUNT(*) as msg_count,
                GROUP_CONCAT(id) as evidence_ids
            FROM communications
            WHERE processed = 0 OR received_at > datetime('now', '-7 days')
            GROUP BY COALESCE(thread_id, id)
            ORDER BY last_received_at DESC
            LIMIT 100
        """)

        threads = []
        for td in threads_data:
            thread = self._build_thread_unit(td)
            if thread:
                threads.append(thread)
                self._threads_cache[thread.thread_id] = thread

        return threads

    def _build_thread_unit(self, data: dict) -> ThreadUnit | None:
        """Build a single ThreadUnit."""
        thread_id = data.get("thread_id")
        if not thread_id:
            return None

        client_id = data.get("client_id")
        client_name = None
        tier = None

        if client_id:
            client = self._query_one(
                "SELECT name, tier FROM clients WHERE id = ?", (client_id,)
            )
            if client:
                client_name = client.get("name")
                tier = client.get("tier")

        # Determine counterparty
        from_email = data.get("from_email", "")
        from_name = data.get("from_name", "")
        from_domain = data.get("from_domain", "")
        counterparty = from_name or from_email or from_domain or "Unknown"

        # Compute direction per §6.2
        direction = self._compute_direction(data)

        # Derive expected_response_by per §6.1
        expected_response_by, deadline_source = self._derive_expected_response_by(
            data, direction, tier
        )

        # Compute risk band per §6.3
        age_hours = data.get("age_hours") or 0
        is_vip = data.get("is_vip") or data.get("stakeholder_tier") == "VIP"

        # Link commitments
        linked_commitments = self._get_linked_commitments(thread_id)
        has_overdue_commitment = any(
            c.due_at_state == DeadlineState.OVERDUE
            for c in [self._commitments_cache.get(cid) for cid in linked_commitments]
            if c
        )

        risk_band = self._compute_thread_risk_band(
            direction,
            expected_response_by,
            age_hours,
            is_vip,
            data.get("is_important"),
            data.get("requires_response"),
            has_overdue_commitment,
        )

        # Compute confidence per §6.6
        confidence, why_low = self._compute_thread_confidence(
            data, direction, client_id
        )

        # Get linked tasks
        linked_tasks = self._get_linked_tasks(thread_id, client_id)

        # Compute score
        score = self._compute_thread_score(
            direction,
            expected_response_by,
            age_hours,
            is_vip,
            confidence,
            client_id,
            tier,
        )

        # Generate why_surfaced
        why_surfaced = self._generate_why_surfaced(
            direction, risk_band, expected_response_by, age_hours
        )

        return ThreadUnit(
            thread_id=thread_id,
            client_id=client_id,
            client_name=client_name,
            subject=data.get("subject", "No subject")[:100],
            counterparty=counterparty[:50],
            age_hours=round(age_hours, 1),
            last_received_at=data.get("last_received_at", ""),
            direction=direction,
            expected_response_by=expected_response_by,
            response_deadline_source=deadline_source,
            risk_band=risk_band,
            score=score,
            confidence=confidence,
            why_low=why_low,
            evidence_ids=(data.get("evidence_ids") or "").split(",")[:10],
            linked_commitments=linked_commitments,
            linked_tasks=linked_tasks,
            why_surfaced=why_surfaced,
            is_vip=is_vip,
            tier=tier,
        )

    def _compute_direction(self, data: dict) -> Direction:
        """Compute direction per §6.2."""
        from_domain = data.get("from_domain", "") or ""
        from_email = data.get("from_email", "") or ""

        # Check if from us
        is_from_us = any(
            d in from_domain.lower() or d in from_email.lower()
            for d in self.our_domains
        )

        if is_from_us:
            return Direction.OUTBOUND_WAITING_THEM
        if from_domain or from_email:
            return Direction.INBOUND_WAITING_US

        return Direction.MIXED

    def _derive_expected_response_by(
        self, data: dict, direction: Direction, tier: str | None
    ) -> tuple[str | None, str]:
        """Derive expected_response_by per §6.1."""
        # 1. Check explicit expected_response_by
        if data.get("expected_response_by"):
            return data["expected_response_by"], "explicit"

        # 2. Check response_deadline
        if data.get("response_deadline"):
            return data["response_deadline"], "explicit"

        # 3. Infer based on requires_response and direction
        if data.get("requires_response") and direction == Direction.INBOUND_WAITING_US:
            received = data.get("last_received_at")
            if received:
                try:
                    recv_dt = datetime.fromisoformat(received.replace("Z", "+00:00"))
                    # Tier A/VIP: +24h, others: +48h
                    hours = 24 if (tier == "A" or data.get("is_vip")) else 48
                    deadline = recv_dt.replace(tzinfo=None) + timedelta(hours=hours)
                    return deadline.isoformat(), "inferred"
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse last_received_at: {e}")

        return None, "none"

    def _compute_thread_risk_band(
        self,
        direction: Direction,
        expected_response_by: str | None,
        age_hours: float,
        is_vip: bool,
        is_important: bool,
        requires_response: bool,
        has_overdue_commitment: bool,
    ) -> RiskBand:
        """Compute thread risk band per §6.3."""
        # HIGH conditions
        if direction == Direction.INBOUND_WAITING_US and expected_response_by:
            try:
                exp_dt = datetime.fromisoformat(
                    expected_response_by.replace("Z", "+00:00")
                )
                if exp_dt.replace(tzinfo=None) < self.now:
                    return RiskBand.HIGH
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not parse expected_response_by: {e}")

        if is_vip and age_hours > 24 and direction == Direction.INBOUND_WAITING_US:
            return RiskBand.HIGH

        if has_overdue_commitment:
            return RiskBand.HIGH

        if is_important and requires_response:
            return RiskBand.HIGH

        # MED conditions
        if direction == Direction.INBOUND_WAITING_US and age_hours > 48:
            return RiskBand.MED

        if expected_response_by:
            try:
                exp_dt = datetime.fromisoformat(
                    expected_response_by.replace("Z", "+00:00")
                )
                hours_until = (
                    exp_dt.replace(tzinfo=None) - self.now
                ).total_seconds() / 3600
                if 0 < hours_until <= 12:
                    return RiskBand.MED
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not parse expected_response_by for risk band: {e}")

        if direction == Direction.OUTBOUND_WAITING_THEM and age_hours > 96:
            return RiskBand.MED

        return RiskBand.LOW

    def _compute_thread_confidence(
        self, data: dict, direction: Direction, client_id: str | None
    ) -> tuple[Confidence, list[str]]:
        """Compute thread confidence per §6.6."""
        why_low = []

        # Check body_text
        has_body = self._query_one(
            """
            SELECT 1 FROM communications
            WHERE (thread_id = ? OR id = ?)
            AND body_text IS NOT NULL AND LENGTH(body_text) >= 50
            LIMIT 1
        """,
            (data.get("thread_id"), data.get("latest_id")),
        )

        if not has_body:
            why_low.append("body_text missing")

        # Check client link
        if not client_id:
            why_low.append("client unlinked")

        # Check direction
        if direction == Direction.MIXED:
            why_low.append("direction ambiguous")

        if len(why_low) >= 2:
            return Confidence.LOW, why_low[:3]
        if len(why_low) == 1:
            return Confidence.MED, why_low
        return Confidence.HIGH, []

    def _get_linked_commitments(self, thread_id: str) -> list[str]:
        """Get commitment IDs linked to thread."""
        rows = self._query_all(
            """
            SELECT c.commitment_id FROM commitments c
            JOIN communications comm ON c.source_id = comm.id
            WHERE comm.thread_id = ? OR comm.id = ?
        """,
            (thread_id, thread_id),
        )
        return [r["id"] for r in rows]

    def _get_linked_tasks(self, thread_id: str, client_id: str | None) -> list[dict]:
        """Get tasks linked to thread or client."""
        tasks = []

        # Direct link via linked_task_id
        direct = self._query_all(
            """
            SELECT DISTINCT t.id as task_id, t.title, t.due_date, t.project_id
            FROM communications c
            JOIN tasks t ON c.linked_task_id = t.id
            WHERE (c.thread_id = ? OR c.commitment_id = ?)
            LIMIT 3
        """,
            (thread_id, thread_id),
        )
        tasks.extend(direct)

        # Client link (get risky tasks)
        if client_id and len(tasks) < 3:
            client_tasks = self._query_all(
                """
                SELECT t.id as task_id, t.title, t.due_date, t.project_id
                FROM tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE p.client_id = ?
                AND t.status NOT IN ('done', 'completed')
                AND t.due_date < date('now', '+7 days')
                AND t.due_date >= '2026-01-01'
                ORDER BY t.due_date ASC
                LIMIT ?
            """,
                (client_id, 3 - len(tasks)),
            )
            tasks.extend(client_tasks)

        return [
            {
                "task_id": t["task_id"],
                "title": t["title"],
                "due_date": t.get("due_date"),
                "project_id": t.get("project_id"),
            }
            for t in tasks[:3]
        ]

    def _compute_thread_score(
        self,
        direction: Direction,
        expected_response_by: str | None,
        age_hours: float,
        is_vip: bool,
        confidence: Confidence,
        client_id: str | None,
        tier: str | None,
    ) -> float:
        """Compute thread score per §7.1."""
        # Impact (0-1)
        impact = 0.5
        if is_vip:
            impact += 0.3
        if tier == "A":
            impact += 0.2
        elif tier == "B":
            impact += 0.1
        if direction == Direction.INBOUND_WAITING_US:
            impact += 0.1
        impact = min(1.0, impact)

        # Urgency (0-1) - inverse time to consequence
        urgency = 0.3
        if expected_response_by:
            try:
                exp_dt = datetime.fromisoformat(
                    expected_response_by.replace("Z", "+00:00")
                )
                hours_until = (
                    exp_dt.replace(tzinfo=None) - self.now
                ).total_seconds() / 3600
                if hours_until <= 0:
                    urgency = 1.0  # Overdue
                elif hours_until <= 4:
                    urgency = 0.9
                elif hours_until <= 12:
                    urgency = 0.7
                elif hours_until <= 24:
                    urgency = 0.5
                else:
                    urgency = 0.3
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not parse expected_response_by for urgency: {e}")
        elif age_hours > 72:
            urgency = 0.6
        elif age_hours > 48:
            urgency = 0.4

        # Controllability (0-1)
        controllability = 0.7
        if direction == Direction.INBOUND_WAITING_US:
            controllability = 0.9  # We can respond
        elif direction == Direction.OUTBOUND_WAITING_THEM:
            controllability = 0.5  # We can nudge

        # Confidence factor
        conf_factor = {
            Confidence.HIGH: 1.0,
            Confidence.MED: 0.8,
            Confidence.LOW: 0.6,
        }.get(confidence, 0.7)

        return (
            self.W_I * impact
            + self.W_U * urgency
            + self.W_C * controllability
            + self.W_Q * conf_factor
        )

    def _generate_why_surfaced(
        self,
        direction: Direction,
        risk_band: RiskBand,
        expected_response_by: str | None,
        age_hours: float,
    ) -> str:
        """Generate 1-line reason for surfacing."""
        reasons = []

        if risk_band == RiskBand.HIGH:
            reasons.append("High risk")

        if direction == Direction.INBOUND_WAITING_US:
            reasons.append("Waiting on us")
            if expected_response_by:
                try:
                    exp_dt = datetime.fromisoformat(
                        expected_response_by.replace("Z", "+00:00")
                    )
                    if exp_dt.replace(tzinfo=None) < self.now:
                        reasons.append("Response overdue")
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(
                        f"Could not parse expected_response_by for reasons: {e}"
                    )
        elif direction == Direction.OUTBOUND_WAITING_THEM:
            if age_hours > 72:
                reasons.append("Stalled >72h")

        return "; ".join(reasons[:2]) if reasons else "Active thread"

    # ==========================================================================
    # COMMITMENT BUILDING (§3.2, §6.4-6.5)
    # ==========================================================================

    def build_commitments(self) -> list[CommitmentUnit]:
        """Build all CommitmentUnits."""
        rows = self._query_all("""
            SELECT
                c.*,
                CASE WHEN c.scope_ref_type = 'client' THEN c.scope_ref_id ELSE NULL END as client_id,
                cl.name as client_name
            FROM commitments c
            LEFT JOIN clients cl ON c.scope_ref_type = 'client' AND c.scope_ref_id = cl.id
            WHERE c.status IN ('open', 'broken')
            ORDER BY c.due_at ASC NULLS LAST
        """)

        commitments = []
        for row in rows:
            cu = self._build_commitment_unit(row)
            if cu:
                commitments.append(cu)
                self._commitments_cache[cu.commitment_id] = cu

        return commitments

    def _build_commitment_unit(self, data: dict) -> CommitmentUnit | None:
        """Build a single CommitmentUnit."""
        commitment_id = data.get("commitment_id")
        if not commitment_id:
            return None

        # Compute deadline state per §6.4
        deadline = data.get("due_at")
        deadline_state = self._compute_deadline_state(deadline)

        # Compute confidence band
        raw_confidence = data.get("confidence", 0.5) or 0.5
        if raw_confidence >= 0.7:
            confidence_band = Confidence.HIGH
        elif raw_confidence >= 0.4:
            confidence_band = Confidence.MED
        else:
            confidence_band = Confidence.LOW

        # Compute risk band per §6.5
        status = data.get("status", "open")
        risk_band = self._compute_commitment_risk_band(
            status, deadline_state, confidence_band
        )

        # Compute consequence_at
        consequence_at = (
            deadline
            if deadline_state in [DeadlineState.OVERDUE, DeadlineState.DUE_SOON]
            else None
        )

        # Build why_low
        why_low = []
        if confidence_band == Confidence.LOW:
            why_low.append("Low extraction confidence")
        if not self.commitment_ready:
            why_low.append("Commitment data degraded")

        return CommitmentUnit(
            commitment_id=commitment_id,
            client_id=data.get("client_id"),
            client_name=data.get("client_name"),
            text=data.get("commitment_text", "")[:200],
            type=data.get("type", "promise"),
            status=status,
            deadline=deadline,
            deadline_state=deadline_state,
            confidence=raw_confidence,
            confidence_band=confidence_band,
            source_thread_id=data.get("source_thread_id"),
            risk_band=risk_band,
            consequence_at=consequence_at,
            why_low=why_low,
            speaker=data.get("speaker"),
            target=data.get("target"),
            created_at=data.get("created_at"),
        )

    def _compute_deadline_state(self, deadline: str | None) -> DeadlineState:
        """Compute deadline state per §6.4."""
        if not deadline:
            return DeadlineState.NO_DEADLINE

        try:
            dl_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            hours_until = (dl_dt.replace(tzinfo=None) - self.now).total_seconds() / 3600

            if hours_until < 0:
                return DeadlineState.OVERDUE
            if hours_until <= 72:
                return DeadlineState.DUE_SOON
            return DeadlineState.FAR
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not parse deadline: {e}")
            return DeadlineState.NO_DEADLINE

    def _compute_commitment_risk_band(
        self, status: str, deadline_state: DeadlineState, confidence_band: Confidence
    ) -> RiskBand:
        """Compute commitment risk band per §6.5."""
        # HIGH conditions
        if status == "broken":
            return RiskBand.HIGH
        if status == "open" and deadline_state == DeadlineState.OVERDUE:
            return RiskBand.HIGH
        if (
            deadline_state == DeadlineState.DUE_SOON
            and confidence_band == Confidence.HIGH
        ):
            return RiskBand.HIGH

        # MED conditions
        if status == "open" and deadline_state == DeadlineState.DUE_SOON:
            return RiskBand.MED

        return RiskBand.LOW

    # ==========================================================================
    # TILES (§4 Zone B)
    # ==========================================================================

    def build_tiles(
        self, threads: list[ThreadUnit], commitments: list[CommitmentUnit]
    ) -> dict:
        """Build status tiles per Zone B."""
        # High-risk threads
        high_risk = [t for t in threads if t.risk_band == RiskBand.HIGH]
        next_consequence = None
        for t in high_risk:
            if t.expected_response_by:
                try:
                    exp_dt = datetime.fromisoformat(
                        t.expected_response_by.replace("Z", "+00:00")
                    )
                    hours = (
                        exp_dt.replace(tzinfo=None) - self.now
                    ).total_seconds() / 3600
                    if next_consequence is None or hours < next_consequence:
                        next_consequence = hours
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(
                        f"Could not parse expected_response_by for consequence: {e}"
                    )

        # Overdue commitments
        overdue = [c for c in commitments if c.due_at_state == DeadlineState.OVERDUE]
        top_overdue_client = overdue[0].client_name if overdue else None

        # Waiting on us
        waiting_us = [t for t in threads if t.direction == Direction.INBOUND_WAITING_US]
        oldest_age = max((t.age_hours for t in waiting_us), default=0)

        # Waiting on them
        waiting_them = [
            t for t in threads if t.direction == Direction.OUTBOUND_WAITING_THEM
        ]
        stalled = [t for t in waiting_them if t.age_hours > 72]

        return {
            "high_risk_threads": {
                "count": len(high_risk),
                "next_consequence_hours": round(next_consequence, 1)
                if next_consequence
                else None,
            },
            "overdue_commitments": {
                "count": len(overdue),
                "top_client": top_overdue_client,
            },
            "waiting_on_us": {
                "count": len(waiting_us),
                "oldest_age_hours": round(oldest_age, 1),
            },
            "waiting_on_them": {
                "count": len(waiting_them),
                "stalled_over_72h": len(stalled),
            },
        }

    # ==========================================================================
    # MOVES (§4 Zone C)
    # ==========================================================================

    def build_moves(
        self, threads: list[ThreadUnit], commitments: list[CommitmentUnit]
    ) -> list[dict]:
        """Build relationship moves per Zone C (max 7)."""
        moves = []

        # Generate moves from threads
        for t in threads[:20]:
            move = self._generate_thread_move(t)
            if move:
                moves.append(move)

        # Generate moves from commitments
        for c in commitments[:10]:
            move = self._generate_commitment_move(c)
            if move:
                moves.append(move)

        # Score and rank
        for m in moves:
            base_score = m["score"]
            multiplier = self.MODE_MULTIPLIERS.get(self.mode, {}).get(m["type"], 1.0)
            if not self.commitment_ready and m["type"] == MoveType.COMMITMENT_REPAIR:
                multiplier *= 0.80
            m["score"] = base_score * multiplier

        # Sort and filter by horizon eligibility
        moves.sort(key=lambda x: x["score"], reverse=True)
        eligible = [m for m in moves if self._is_move_eligible(m)]

        return eligible[: self.MAX_MOVES]

    def _generate_thread_move(self, thread: ThreadUnit) -> dict | None:
        """Generate a move from a thread."""
        # Determine move type
        if (
            thread.risk_band == RiskBand.HIGH
            and thread.direction == Direction.INBOUND_WAITING_US
        ):
            move_type = MoveType.RESPONSE_BREACH_RESCUE
            label = f"Rescue response: {thread.subject[:30]}"
            action = {
                "risk": "propose",
                "label": "Draft reply",
                "payload": {"thread_id": thread.thread_id},
            }
        elif thread.is_vip:
            move_type = MoveType.VIP_ESCALATION
            label = f"VIP attention: {thread.counterparty}"
            action = {
                "risk": "approval",
                "label": "Draft VIP response",
                "payload": {"thread_id": thread.thread_id},
            }
        elif (
            thread.direction == Direction.OUTBOUND_WAITING_THEM
            and thread.age_hours > 72
        ):
            move_type = MoveType.WAITING_ON_THEM_NUDGE
            label = f"Nudge: {thread.counterparty} ({thread.age_hours:.0f}h)"
            action = {
                "risk": "propose",
                "label": "Draft nudge",
                "payload": {"thread_id": thread.thread_id},
            }
        elif not thread.client_id:
            move_type = MoveType.UNKNOWN_TRIAGE
            label = f"Triage: {thread.subject[:30]}"
            action = {
                "risk": "auto",
                "label": "Link to client",
                "payload": {"thread_id": thread.thread_id},
            }
        else:
            return None  # Not a move-worthy thread

        # Calculate time to consequence
        ttc = None
        if thread.expected_response_by:
            try:
                exp_dt = datetime.fromisoformat(
                    thread.expected_response_by.replace("Z", "+00:00")
                )
                ttc = (exp_dt.replace(tzinfo=None) - self.now).total_seconds() / 3600
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(
                    f"Could not parse expected_response_by for time to consequence: {e}"
                )

        return {
            "move_id": f"move-thread-{thread.thread_id}",
            "type": move_type,
            "label": label,
            "client_id": thread.client_id,
            "thread_id": thread.thread_id,
            "commitment_id": None,
            "score": thread.score,
            "time_to_consequence_hours": ttc,
            "confidence": thread.confidence,
            "why_low": thread.why_low,
            "primary_action": action,
            "secondary_actions": [],
            "evidence_ids": thread.evidence_ids[:5],
        }

    def _generate_commitment_move(self, commit: CommitmentUnit) -> dict | None:
        """Generate a move from a commitment."""
        if commit.risk_band != RiskBand.HIGH:
            return None

        move_type = MoveType.COMMITMENT_REPAIR
        label = f"Repair: {commit.text[:30]}"

        if commit.deadline_state == DeadlineState.OVERDUE:
            action = {
                "risk": "approval",
                "label": "Draft admission/update",
                "payload": {"commitment_id": commit.commitment_id},
            }
        else:
            action = {
                "risk": "propose",
                "label": "Clarify deadline",
                "payload": {"commitment_id": commit.commitment_id},
            }

        # Time to consequence
        ttc = None
        if commit.deadline:
            try:
                dl_dt = datetime.fromisoformat(commit.deadline.replace("Z", "+00:00"))
                ttc = (dl_dt.replace(tzinfo=None) - self.now).total_seconds() / 3600
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"Could not parse commitment deadline for TTC: {e}")

        # Score based on urgency and confidence
        urgency = 1.0 if commit.deadline_state == DeadlineState.OVERDUE else 0.7
        impact = 0.8 if commit.client_id else 0.5
        controllability = 0.6
        conf_factor = {
            Confidence.HIGH: 1.0,
            Confidence.MED: 0.8,
            Confidence.LOW: 0.6,
        }.get(commit.confidence_band, 0.7)

        score = (
            self.W_I * impact
            + self.W_U * urgency
            + self.W_C * controllability
            + self.W_Q * conf_factor
        )

        return {
            "move_id": f"move-commit-{commit.commitment_id}",
            "type": move_type,
            "label": label,
            "client_id": commit.client_id,
            "thread_id": commit.source_thread_id,
            "commitment_id": commit.commitment_id,
            "score": score,
            "time_to_consequence_hours": ttc,
            "confidence": commit.confidence_band,
            "why_low": commit.why_low,
            "primary_action": action,
            "secondary_actions": [],
            "evidence_ids": [commit.commitment_id],
        }

    def _is_move_eligible(self, move: dict) -> bool:
        """Check move eligibility per §5."""
        ttc = move.get("time_to_consequence_hours")

        if self.horizon == Horizon.NOW:
            return ttc is None or ttc <= 12
        if self.horizon == Horizon.TODAY:
            return ttc is None or ttc <= 24
        return True  # THIS WEEK - all eligible

    # ==========================================================================
    # LADDERS (§8)
    # ==========================================================================

    def build_ladders(
        self, threads: list[ThreadUnit], commitments: list[CommitmentUnit]
    ) -> dict:
        """Build right column ladders per §8."""
        return {
            "overdue_commitments": self._build_overdue_ladder(commitments),
            "silence": self._build_silence_ladder(threads),
            "vip": self._build_vip_ladder(threads),
        }

    def _build_overdue_ladder(self, commitments: list[CommitmentUnit]) -> list[dict]:
        """Overdue commitments ladder per §8.1 (max 5)."""
        overdue = [c for c in commitments if c.due_at_state == DeadlineState.OVERDUE]

        # Sort by most overdue first
        def overdue_hours(c):
            if c.due_at:
                try:
                    dl_dt = datetime.fromisoformat(c.due_at.replace("Z", "+00:00"))
                    return (
                        self.now - dl_dt.replace(tzinfo=None)
                    ).total_seconds() / 3600
                except (ValueError, TypeError, AttributeError):
                    pass
            return 0

        overdue.sort(key=overdue_hours, reverse=True)

        return [
            {
                "commitment_id": c.commitment_id,
                "client_id": c.client_id,
                "client_name": c.client_name or "Unknown",
                "commitment_text": c.text[:50],
                "overdue_hours": round(overdue_hours(c), 1),
                "confidence": c.confidence_band.value,
                "primary_action": {
                    "risk": "propose",
                    "label": "Address breach",
                    "payload": {"commitment_id": c.commitment_id},
                },
            }
            for c in overdue[: self.MAX_LADDER]
        ]

    def _build_silence_ladder(self, threads: list[ThreadUnit]) -> list[dict]:
        """Silence ladder per §8.2 (max 5)."""
        # Filter: inbound waiting us
        candidates = [t for t in threads if t.direction == Direction.INBOUND_WAITING_US]

        # Sort by response breach or age
        def sort_key(t):
            if t.expected_response_by:
                try:
                    exp_dt = datetime.fromisoformat(
                        t.expected_response_by.replace("Z", "+00:00")
                    )
                    overdue = (
                        self.now - exp_dt.replace(tzinfo=None)
                    ).total_seconds() / 3600
                    return (1, overdue)  # Overdue first
                except (ValueError, TypeError, AttributeError):
                    pass
            return (0, t.age_hours)

        candidates.sort(key=sort_key, reverse=True)

        return [
            {
                "thread_id": t.thread_id,
                "client_id": t.client_id,
                "subject": t.subject[:40],
                "age_hours": t.age_hours,
                "expected_response_by": t.expected_response_by,
                "risk_band": t.risk_band.value,
            }
            for t in candidates[: self.MAX_LADDER]
        ]

    def _build_vip_ladder(self, threads: list[ThreadUnit]) -> list[dict]:
        """VIP ladder per §8.3 (max 5)."""
        vip = [t for t in threads if t.is_vip]

        # Sort by risk then urgency
        def sort_key(t):
            risk_order = {RiskBand.HIGH: 0, RiskBand.MED: 1, RiskBand.LOW: 2}
            return (risk_order.get(t.risk_band, 2), -t.score)

        vip.sort(key=sort_key)

        return [
            {
                "thread_id": t.thread_id,
                "client_id": t.client_id,
                "subject": t.subject[:40],
                "risk_band": t.risk_band.value,
                "expected_response_by": t.expected_response_by,
            }
            for t in vip[: self.MAX_LADDER]
        ]

    # ==========================================================================
    # DRAWER (§9)
    # ==========================================================================

    def build_thread_room(self, thread_id: str) -> dict | None:
        """Build Thread Room drawer per §9.1."""
        thread = self._threads_cache.get(thread_id)
        if not thread:
            # Try to build it
            data = self._query_one(
                """
                SELECT
                    COALESCE(thread_id, id) as thread_id,
                    id as latest_id,
                    client_id, subject, from_email, from_domain, from_name,
                    received_at as last_received_at,
                    COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) as age_hours,
                    expected_response_by, response_deadline, requires_response,
                    is_vip, stakeholder_tier, is_important, priority, id as evidence_ids
                FROM communications
                WHERE thread_id = ? OR id = ?
                ORDER BY received_at DESC
                LIMIT 1
            """,
                (thread_id, thread_id),
            )
            if not data:
                return None
            thread = self._build_thread_unit(data)
            if not thread:
                return None

        # Build timeline (max 6)
        timeline = self._query_all(
            """
            SELECT id as comm_id, from_email as "from", to_emails as "to",
                   received_at, COALESCE(snippet, SUBSTR(body_text, 1, 150)) as excerpt
            FROM communications
            WHERE thread_id = ? OR id = ?
            ORDER BY received_at DESC
            LIMIT ?
        """,
            (thread_id, thread_id, self.MAX_DRAWER_TIMELINE),
        )

        # Build consequence
        risk_reason = (
            "No deadline"
            if not thread.expected_response_by
            else (
                "Response overdue"
                if thread.risk_band == RiskBand.HIGH
                else "Response due soon"
            )
        )

        # Build linked commitments (max 5)
        linked_commits = []
        for cid in thread.linked_commitments[: self.MAX_DRAWER_COMMITMENTS]:
            commit = self._commitments_cache.get(cid)
            if commit:
                linked_commits.append(
                    {
                        "commitment_id": cid,
                        "status": commit.status,
                        "due_at": commit.deadline,
                        "confidence": commit.confidence,
                    }
                )

        # Build actions (max 4)
        actions = []
        if thread.direction == Direction.INBOUND_WAITING_US:
            actions.append(
                {
                    "risk": "propose",
                    "label": "Draft reply",
                    "idempotency_key": f"action-{thread_id}-reply",
                    "payload": {"thread_id": thread_id},
                    "why": "Response needed",
                }
            )
        actions.append(
            {
                "risk": "auto",
                "label": "Create follow-up task",
                "idempotency_key": f"action-{thread_id}-task",
                "payload": {"thread_id": thread_id},
                "why": "Track internally",
            }
        )
        if thread.direction == Direction.OUTBOUND_WAITING_THEM:
            actions.append(
                {
                    "risk": "propose",
                    "label": "Draft nudge",
                    "idempotency_key": f"action-{thread_id}-nudge",
                    "payload": {"thread_id": thread_id},
                    "why": "Follow up",
                }
            )

        # Summary
        summary = f"Thread with {thread.counterparty}"
        if thread.client_name:
            summary += f" ({thread.client_name})"
        summary += f". {thread.why_surfaced}."
        if thread.expected_response_by:
            summary += f" Response expected by {thread.expected_response_by[:10]}."

        return {
            "summary": summary,
            "timeline": [
                {
                    "comm_id": t["comm_id"],
                    "from": t["from"] or "",
                    "to": t["to"] or "",
                    "received_at": t["received_at"],
                    "excerpt": (t.get("excerpt") or "")[:150],
                }
                for t in timeline
            ],
            "consequence": {
                "expected_response_by": thread.expected_response_by,
                "risk_reason": risk_reason,
            },
            "linked_commitments": linked_commits,
            "linked_work": thread.linked_tasks[: self.MAX_DRAWER_WORK],
            "actions": actions[: self.MAX_DRAWER_ACTIONS],
            "reason": f"{self.horizon.value} | {thread.direction.value} | risk={thread.risk_band.value} | driver=Comms",
        }

    def build_commitment_room(self, commitment_id: str) -> dict | None:
        """Build Commitment Room drawer per §9.2."""
        commit = self._commitments_cache.get(commitment_id)
        if not commit:
            data = self._query_one(
                """
                SELECT c.*, cl.name as client_name, comm.thread_id as source_thread_id
                FROM commitments c
                LEFT JOIN clients cl ON c.client_id = cl.id
                LEFT JOIN communications comm ON c.source_id = comm.id
                WHERE c.commitment_id = ?
            """,
                (commitment_id,),
            )
            if not data:
                return None
            commit = self._build_commitment_unit(data)
            if not commit:
                return None

        # Build evidence (max 3)
        evidence = self._query_all(
            """
            SELECT comm.id as comm_id, comm.thread_id,
                   COALESCE(comm.snippet, SUBSTR(comm.body_text, 1, 150)) as excerpt
            FROM communications comm
            WHERE comm.id = (SELECT source_id FROM commitments WHERE id = ?)
            LIMIT ?
        """,
            (commitment_id, self.MAX_DRAWER_EVIDENCE),
        )

        # Related threads (max 3)
        related = []
        if commit.source_thread_id:
            thread = self._threads_cache.get(commit.source_thread_id)
            if thread:
                related.append(
                    {
                        "thread_id": thread.thread_id,
                        "subject": thread.subject,
                        "risk_band": thread.risk_band.value,
                    }
                )

        # Actions (max 4)
        actions = [
            {
                "risk": "propose",
                "label": "Draft response",
                "idempotency_key": f"action-{commitment_id}-respond",
                "payload": {"commitment_id": commitment_id},
                "why": "Address commitment",
            },
            {
                "risk": "auto",
                "label": "Create internal task",
                "idempotency_key": f"action-{commitment_id}-task",
                "payload": {"commitment_id": commitment_id},
                "why": "Track fulfillment",
            },
        ]
        if commit.deadline_state == DeadlineState.OVERDUE:
            actions.insert(
                0,
                {
                    "risk": "approval",
                    "label": "Draft admission",
                    "idempotency_key": f"action-{commitment_id}-admit",
                    "payload": {"commitment_id": commitment_id},
                    "why": "Acknowledge breach",
                },
            )

        # Summary
        summary = f"{commit.type.title()} by {commit.speaker or 'unknown'} to {commit.target or 'unknown'}. "
        summary += f"Status: {commit.status}. "
        if commit.deadline_state == DeadlineState.OVERDUE:
            summary += "OVERDUE."
        elif commit.deadline:
            summary += f"Due: {commit.deadline[:10]}."

        return {
            "summary": summary,
            "details": {
                "commitment_text": commit.text,
                "type": commit.type,
                "speaker": commit.speaker,
                "target": commit.target,
                "created_at": commit.created_at,
                "due_at": commit.deadline,
                "status": commit.status,
                "confidence": commit.confidence,
            },
            "evidence": [
                {
                    "comm_id": e["comm_id"],
                    "thread_id": e["thread_id"],
                    "excerpt": (e.get("excerpt") or "")[:150],
                }
                for e in evidence
            ],
            "related_threads": related[: self.MAX_DRAWER_RELATED],
            "actions": actions[: self.MAX_DRAWER_ACTIONS],
            "reason": f"{commit.deadline_state.value} | status={commit.status} | confidence={commit.confidence_band.value}",
        }

    # ==========================================================================
    # MAIN GENERATE (§11)
    # ==========================================================================

    def generate(self) -> dict:
        """Generate complete comms_commitments snapshot per §11."""
        self.load_trust_state()

        # Build commitments first (needed for thread linking)
        commitments = self.build_commitments()

        # Build threads
        threads = self.build_threads()

        # Rank threads by score
        threads.sort(key=lambda t: t.score, reverse=True)
        threads = threads[: self.MAX_THREADS]

        # Build tiles
        tiles = self.build_tiles(threads, commitments)

        # Build moves
        moves = self.build_moves(threads, commitments)

        # Build ladders
        ladders = self.build_ladders(threads, commitments)

        # Build drawers for surfaced threads and commitments
        drawer_threads = {}
        for t in threads[:15]:
            room = self.build_thread_room(t.thread_id)
            if room:
                drawer_threads[f"thread:{t.thread_id}"] = room

        drawer_commitments = {}
        for c in commitments[:10]:
            room = self.build_commitment_room(c.commitment_id)
            if room:
                drawer_commitments[f"commitment:{c.commitment_id}"] = room

        # Get overall confidence
        confidence, why_low = self._get_overall_confidence()

        return {
            "meta": {
                "generated_at": self.now.isoformat(),
                "mode": self.mode.value,
                "horizon": self.horizon.value,
                "trust": {
                    "data_integrity": self.data_integrity,
                    "commitment_ready": self.commitment_ready,
                    "client_coverage": self.client_coverage,
                    "comms_body_coverage": round(self.comms_body_coverage, 1),
                    "comms_link_coverage": round(self.comms_link_coverage, 1),
                    "delta_available": self.delta_available,
                    "confidence": confidence.value,
                    "why_low": why_low,
                },
            },
            "tiles": tiles,
            "moves": [
                {
                    "move_id": m["move_id"],
                    "type": m["type"].value,
                    "label": m["label"],
                    "client_id": m["client_id"],
                    "thread_id": m.get("thread_id"),
                    "commitment_id": m.get("commitment_id"),
                    "score": round(m["score"], 3),
                    "time_to_consequence_hours": m.get("time_to_consequence_hours"),
                    "confidence": m["confidence"].value
                    if isinstance(m["confidence"], Confidence)
                    else m["confidence"],
                    "why_low": m["why_low"],
                    "primary_action": m["primary_action"],
                    "secondary_actions": m["secondary_actions"],
                    "evidence_ids": m["evidence_ids"],
                }
                for m in moves
            ],
            "threads": [
                {
                    "thread_id": t.thread_id,
                    "client_id": t.client_id,
                    "client_name": t.client_name,
                    "subject": t.subject,
                    "counterparty": t.counterparty,
                    "direction": t.direction.value,
                    "last_received_at": t.last_received_at,
                    "age_hours": t.age_hours,
                    "expected_response_by": t.expected_response_by,
                    "response_deadline_source": t.response_deadline_source,
                    "risk_band": t.risk_band.value,
                    "score": round(t.score, 3),
                    "confidence": t.confidence.value,
                    "why_low": t.why_low,
                    "linked_commitments": t.linked_commitments,
                    "linked_tasks": t.linked_tasks,
                    "why_surfaced": t.why_surfaced,
                    "primary_action": {
                        "risk": "propose"
                        if t.direction == Direction.INBOUND_WAITING_US
                        else "auto",
                        "label": "Draft reply"
                        if t.direction == Direction.INBOUND_WAITING_US
                        else "View thread",
                        "idempotency_key": f"action-{t.thread_id}-primary",
                        "payload": {"thread_id": t.thread_id},
                        "why": t.why_surfaced,
                    },
                }
                for t in threads
            ],
            "ladders": ladders,
            "drawer": {
                "threads": drawer_threads,
                "commitments": drawer_commitments,
            },
        }


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import json

    engine = CommsCommitmentsPage11Engine()
    snapshot = engine.generate()
    logger.info(json.dumps(snapshot, indent=2, default=str))
