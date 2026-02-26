"""
Client 360 Engine - Page 10 LOCKED SPEC (v1)

Agency Relationship Command: every client's relationship posture across
Delivery + Comms + Cash + Commitments with drill-down.

Per spec §10, snapshot structure: meta, tiles, portfolio, moves, right_column, drawer
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from lib import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()


# ==============================================================================
# ENUMS & TYPES (per §2 LOCKED)
# ==============================================================================


class Mode(StrEnum):
    OPS_HEAD = "Ops Head"
    CO_FOUNDER = "Co-Founder"
    ARTIST = "Artist"


class Horizon(StrEnum):
    NOW = "NOW"
    TODAY = "TODAY"
    THIS_WEEK = "THIS WEEK"


class Posture(StrEnum):
    """Client posture quadrant per §5.1"""

    PROTECT = "PROTECT"  # high health, high value
    WATCH = "WATCH"  # stable but drifting
    INTERVENE = "INTERVENE"  # at-risk and valuable
    CONTAIN = "CONTAIN"  # low value, noisy


class TopDriver(StrEnum):
    """Primary driver labels per §5.2"""

    DELIVERY = "Delivery"
    CASH = "Cash"
    COMMS = "Comms"
    COMMITMENTS = "Commitments"
    UNKNOWN = "Unknown"


class Trend(StrEnum):
    """Trend direction per §2.4"""

    IMPROVING = "improving"
    FLAT = "flat"
    WORSENING = "worsening"
    WORSENING_FAST = "worsening_fast"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class MoveType(StrEnum):
    """Move types per Zone D (immutable)"""

    DELIVERY_STABILIZATION = "DELIVERY_STABILIZATION"
    CASH_UNBLOCK = "CASH_UNBLOCK"
    COMMS_RESCUE = "COMMS_RESCUE"
    COMMITMENT_REPAIR = "COMMITMENT_REPAIR"
    STAKEHOLDER_ALIGNMENT = "STAKEHOLDER_ALIGNMENT"
    CHURN_PREVENTION = "CHURN_PREVENTION"
    UNKNOWN_CLIENT_TRIAGE = "UNKNOWN_CLIENT_TRIAGE"


class ActionRisk(StrEnum):
    AUTO = "auto"
    PROPOSE = "propose"
    APPROVAL = "approval"


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class DomainScore:
    """Individual domain score with confidence"""

    score: float = 100.0
    confidence: Confidence = Confidence.HIGH
    why_low: list[str] = field(default_factory=list)


@dataclass
class HealthBreakdown:
    """Per §6 deterministic thresholds"""

    delivery: DomainScore = field(default_factory=DomainScore)
    cash: DomainScore = field(default_factory=DomainScore)
    responsiveness: DomainScore = field(default_factory=DomainScore)
    commitments: DomainScore = field(default_factory=DomainScore)


@dataclass
class ClientPortfolioItem:
    """Portfolio item per §10.1"""

    client_id: str
    client_name: str
    tier: str | None
    health_score: float
    posture: Posture
    top_driver: TopDriver
    value_score: float
    severe_ar_total: float
    next_break_at: str | None
    trend: Trend | None
    confidence: Confidence
    why_low: list[str]


@dataclass
class Move:
    """Move card per §10.1"""

    move_id: str
    type: MoveType
    label: str
    client_id: str | None
    score: float
    time_to_consequence_hours: float | None
    confidence: Confidence
    why_low: list[str]
    primary_action: dict
    secondary_actions: list[dict]
    evidence_ids: list[str]


# ==============================================================================
# ENGINE
# ==============================================================================


class Client360Page10Engine:
    """
    Generates Client 360 snapshot per Page 10 LOCKED SPEC.

    Health score formula (§2.2):
    HealthScore = clamp(0..100, w_D*Delivery + w_C*Cash + w_R*Responsiveness + w_K*Commitments)

    Base weights (locked): w_D=0.35, w_C=0.30, w_R=0.20, w_K=0.15
    """

    # Hard caps per §10.2
    MAX_PORTFOLIO = 25
    MAX_MOVES = 7
    MAX_DRIFTS = 5
    MAX_SILENCE = 5
    MAX_SEVERE_AR = 5
    MAX_BREAKS_NEXT = 3
    MAX_DELIVERY_PROJECTS = 3
    MAX_COMMS_THREADS = 5
    MAX_COMMITMENTS = 5
    MAX_DRAWER_ACTIONS = 4

    # Base weights per §2.2 (LOCKED)
    W_D = 0.35  # Delivery
    W_C = 0.30  # Cash
    W_R = 0.20  # Responsiveness
    W_K = 0.15  # Commitments

    # Tier thresholds per §2.3 (LOCKED)
    TIER_THRESHOLDS = {
        "A": {"at_risk_health": 80, "severe_ar_threshold": 0},
        "B": {"at_risk_health": 70, "severe_ar_threshold": 25000},
        "C": {"at_risk_health": 60, "severe_ar_threshold": 50000},
    }

    # Mode multipliers per §7.6 (LOCKED)
    MODE_MULTIPLIERS = {
        Mode.OPS_HEAD: {
            MoveType.DELIVERY_STABILIZATION: 1.20,
            MoveType.COMMS_RESCUE: 1.05,
            MoveType.CASH_UNBLOCK: 1.05,
        },
        Mode.CO_FOUNDER: {
            MoveType.CASH_UNBLOCK: 1.25,
            MoveType.CHURN_PREVENTION: 1.20,
            MoveType.STAKEHOLDER_ALIGNMENT: 1.10,
        },
        Mode.ARTIST: {
            MoveType.STAKEHOLDER_ALIGNMENT: 1.20,
            MoveType.DELIVERY_STABILIZATION: 1.15,  # capacity/cadence
            MoveType.CASH_UNBLOCK: 0.95,
        },
    }

    # Move score weights per §7.3 (LOCKED)
    W_I = 0.40  # Impact
    W_U = 0.25  # Urgency
    W_C = 0.20  # Controllability
    W_Q = 0.15  # Confidence

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

        # Trust state (set externally or computed)
        self.data_integrity = True
        self.client_coverage = True
        self.client_coverage_pct = 100.0
        self.commitment_ready = True
        self.commitment_ready_pct = 100.0
        self.finance_ar_coverage = True
        self.finance_ar_coverage_pct = 100.0
        self.delta_available = False

        # Cache
        self._clients_cache: dict[str, dict] = {}
        self._scores_cache: dict[str, tuple[HealthBreakdown, float]] = {}

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
    # TRUST & GATES (§1.2)
    # ==========================================================================

    def load_trust_state(self):
        """Load trust state from gates table or compute."""
        from lib.gates import evaluate_gates

        gates = evaluate_gates()

        self.data_integrity = gates.get("data_integrity", True)
        self.client_coverage_pct = gates.get("client_coverage_pct", 100.0)
        self.client_coverage = self.client_coverage_pct >= 80
        self.commitment_ready_pct = gates.get("commitment_ready_pct", 100.0)
        self.commitment_ready = self.commitment_ready_pct >= 50
        self.finance_ar_coverage_pct = gates.get("finance_ar_coverage_pct", 100.0)
        self.finance_ar_coverage = self.finance_ar_coverage_pct >= 95

        # Check if we have delta data (≥2 snapshots)
        try:
            snapshot_count = (
                self._query_scalar("""
                SELECT COUNT(DISTINCT date(generated_at)) FROM
                (SELECT generated_at FROM snapshots ORDER BY generated_at DESC LIMIT 2)
            """)
                or 0
            )
            self.delta_available = snapshot_count >= 2
        except sqlite3.Error as e:
            # Table may not exist yet
            logger.debug(f"Could not check snapshot count: {e}")
            self.delta_available = False

    def _compute_confidence(self, domain: str) -> tuple[Confidence, list[str]]:
        """Compute confidence for a domain."""
        why_low = []

        if domain == "cash" and not self.finance_ar_coverage:
            why_low.append(f"AR coverage {self.finance_ar_coverage_pct:.0f}% < 95%")
        if domain == "commitments" and not self.commitment_ready:
            why_low.append(f"Commitment ready {self.commitment_ready_pct:.0f}% < 50%")
        if domain == "responsiveness":
            # Check comms linking
            pass

        if len(why_low) >= 2:
            return Confidence.LOW, why_low
        if len(why_low) == 1:
            return Confidence.MED, why_low
        return Confidence.HIGH, []

    def _get_overall_confidence(self, breakdown: HealthBreakdown) -> tuple[Confidence, list[str]]:
        """Get overall client confidence from domain confidences."""
        why_low = []
        low_count = 0
        med_count = 0

        for domain in [
            breakdown.delivery,
            breakdown.cash,
            breakdown.responsiveness,
            breakdown.commitments,
        ]:
            if domain.confidence == Confidence.LOW:
                low_count += 1
                why_low.extend(domain.why_low[:1])
            elif domain.confidence == Confidence.MED:
                med_count += 1

        if low_count >= 2:
            return Confidence.LOW, why_low[:3]
        if low_count >= 1 or med_count >= 2:
            return Confidence.MED, why_low[:2]
        return Confidence.HIGH, []

    # ==========================================================================
    # DOMAIN SCORES (§6 LOCKED)
    # ==========================================================================

    def compute_delivery_health(self, client_id: str) -> DomainScore:
        """
        DeliveryHealth per §6.1:
        - Start at 100
        - Subtract 40 if any project RED
        - Subtract 15 if any project YELLOW
        - Subtract 5 per overdue task beyond threshold (cap 30)
        - Floor at 0
        """
        score = 100.0
        why_low = []

        # Get projects linked to client
        projects = self._query_all(
            """
            SELECT p.id, p.name, p.status,
                   (SELECT COUNT(*) FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.status NOT IN ('done', 'completed')
                    AND t.due_date < date('now')
                    AND t.due_date >= '2026-01-01') as overdue_count,
                   (SELECT COUNT(*) FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.status NOT IN ('done', 'completed')) as active_count
            FROM projects p
            WHERE p.client_id = ? AND p.is_internal = 0 AND p.status = 'active'
        """,
            (client_id,),
        )

        if not projects:
            # No delivery data - check if internal only
            internal = self._query_one(
                """
                SELECT COUNT(*) as c FROM projects WHERE client_id = ? AND is_internal = 1
            """,
                (client_id,),
            )
            if internal and internal["c"] > 0:
                return DomainScore(100.0, Confidence.HIGH, [])
            # Unknown delivery
            return DomainScore(100.0, Confidence.MED, ["No linked projects"])

        total_overdue = 0
        has_red = False
        has_yellow = False

        for p in projects:
            overdue = p.get("overdue_count", 0)
            p.get("active_count", 0)

            # Determine project status (RED/YELLOW/GREEN)
            if overdue >= 3:
                has_red = True
            elif overdue >= 1:
                has_yellow = True

            total_overdue += overdue

        # Apply penalties
        if has_red:
            score -= 40
        if has_yellow:
            score -= 15

        # Overdue task penalty (cap at 30)
        overdue_penalty = min(total_overdue * 5, 30)
        score -= overdue_penalty

        score = max(0.0, score)

        conf, conf_why = self._compute_confidence("delivery")
        why_low.extend(conf_why)

        return DomainScore(score, conf, why_low)

    def compute_cash_health(self, client_id: str) -> DomainScore:
        """
        CashHealth per §6.2:
        - If no outstanding valid AR: 100
        - Else: 100*current_pct + 50*moderate_pct + 0*severe_pct

        Valid AR only (excludes invalid invoices).
        """
        why_low = []

        # Get valid AR by bucket
        ar_data = self._query_one(
            """
            SELECT
                COALESCE(SUM(CASE WHEN aging_bucket = 'current' THEN amount ELSE 0 END), 0) as current,
                COALESCE(SUM(CASE WHEN aging_bucket IN ('1-30', '31-60') THEN amount ELSE 0 END), 0) as moderate,
                COALESCE(SUM(CASE WHEN aging_bucket IN ('61-90', '90+') THEN amount ELSE 0 END), 0) as severe,
                COALESCE(SUM(amount), 0) as total
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL

        """,
            (client_id,),
        )

        if not ar_data or ar_data["total"] == 0:
            # No AR = healthy
            conf, conf_why = self._compute_confidence("cash")
            return DomainScore(100.0, conf, conf_why)

        total = ar_data["total"]
        current_pct = ar_data["current"] / total if total > 0 else 1.0
        moderate_pct = ar_data["moderate"] / total if total > 0 else 0.0
        severe_pct = ar_data["severe"] / total if total > 0 else 0.0

        # Formula: 100*current + 50*moderate + 0*severe
        score = 100 * current_pct + 50 * moderate_pct + 0 * severe_pct
        score = max(0.0, min(100.0, score))

        conf, conf_why = self._compute_confidence("cash")
        why_low.extend(conf_why)

        return DomainScore(score, conf, why_low)

    def compute_responsiveness_health(self, client_id: str) -> DomainScore:
        """
        ResponsivenessHealth per §6.5:
        - Start at 100
        - For each high-risk thread (cap 5):
          - Subtract 20 if expected_response_by missed
          - Else subtract 10 if age_hours > 72
        - Floor at 0
        """
        score = 100.0
        why_low = []

        # Get high-risk comm threads for client
        # Note: communications table has no client_id, using subject match instead
        threads = self._query_all(
            """
            SELECT
                c.id,
                c.subject,
                (julianday('now') - julianday(c.received_at)) * 24 as age_hours,
                c.response_deadline as expected_response_by,
                c.requires_response
            FROM communications c
            WHERE c.processed = 0
            AND c.requires_response = 1
            ORDER BY c.received_at DESC
            LIMIT 5
        """,
            (),
        )

        if not threads:
            # No comms data - could be fine or missing
            why_low.append("No linked comm threads")
            return DomainScore(100.0, Confidence.MED, why_low)

        for t in threads:
            age_hours = t.get("age_hours", 0) or 0
            expected_by = t.get("expected_response_by")

            # Check SLA breach
            if expected_by:
                try:
                    exp_dt = datetime.fromisoformat(expected_by.replace("Z", "+00:00"))
                    if exp_dt.replace(tzinfo=None) < self.now:
                        score -= 20
                        continue
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse expected_by for SLA check: {e}")

            # Check age threshold
            if age_hours > 72:
                score -= 10

        score = max(0.0, score)

        conf, conf_why = self._compute_confidence("responsiveness")
        why_low.extend(conf_why)

        return DomainScore(score, conf, why_low)

    def compute_commitments_health(self, client_id: str) -> DomainScore:
        """
        CommitmentHealth per §6.6:
        - Start at 100
        - Subtract 30 if any breached commitment open
        - Subtract 10 per open commitment past deadline
        - Subtract 5 per deadline within 7 days (cap 20)
        """
        score = 100.0
        why_low = []

        # Get commitments (no client_id in table, using all open commitments)
        commitments = self._query_all(
            """
            SELECT
                commitment_id as id,
                status,
                due_at as deadline,
                (julianday(due_at) - julianday('now')) as days_to_deadline
            FROM commitments
            WHERE status NOT IN ('fulfilled', 'closed')
            LIMIT 10
        """,
            (),
        )

        if not commitments:
            conf, conf_why = self._compute_confidence("commitments")
            return DomainScore(100.0, conf, conf_why)

        has_breached = False
        past_deadline_count = 0
        upcoming_count = 0

        for c in commitments:
            status = c.get("status", "")
            days_to = c.get("days_to_deadline")

            if status == "broken":
                has_breached = True

            if days_to is not None:
                if days_to < 0:
                    past_deadline_count += 1
                elif days_to <= 7:
                    upcoming_count += 1

        # Apply penalties
        if has_breached:
            score -= 30

        score -= past_deadline_count * 10
        score -= min(upcoming_count * 5, 20)  # cap at 20

        score = max(0.0, score)

        conf, conf_why = self._compute_confidence("commitments")
        why_low.extend(conf_why)

        # If commitment_ready=false, reduce confidence
        if not self.commitment_ready:
            return DomainScore(score, Confidence.LOW, why_low + ["Commitment data incomplete"])

        return DomainScore(score, conf, why_low)

    def compute_health_score(self, client_id: str) -> tuple[HealthBreakdown, float]:
        """
        Compute overall HealthScore per §2.2:
        HealthScore = clamp(0..100, w_D*Delivery + w_C*Cash + w_R*Responsiveness + w_K*Commitments)
        """
        if client_id in self._scores_cache:
            return self._scores_cache[client_id]

        breakdown = HealthBreakdown(
            delivery=self.compute_delivery_health(client_id),
            cash=self.compute_cash_health(client_id),
            responsiveness=self.compute_responsiveness_health(client_id),
            commitments=self.compute_commitments_health(client_id),
        )

        # Weighted sum
        health = (
            self.W_D * breakdown.delivery.score
            + self.W_C * breakdown.cash.score
            + self.W_R * breakdown.responsiveness.score
            + self.W_K * breakdown.commitments.score
        )
        health = max(0.0, min(100.0, health))

        self._scores_cache[client_id] = (breakdown, health)
        return breakdown, health

    # ==========================================================================
    # CLASSIFICATIONS (§5 LOCKED)
    # ==========================================================================

    def compute_value_score(self, client_id: str) -> float:
        """
        ValueScore per §6.4:
        - AR magnitude (normalized)
        - Tier weighting: A +0.2, B +0.1, C +0.0
        - Optional: retainer flag
        """
        # Get client tier
        client = self._query_one("SELECT tier FROM clients WHERE id = ?", (client_id,))
        tier = client.get("tier", "C") if client else "C"
        tier_bonus = {"A": 0.2, "B": 0.1, "C": 0.0}.get(tier, 0.0)

        # Get valid AR total
        ar = self._query_one(
            """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL

        """,
            (client_id,),
        )
        ar_total = ar.get("total", 0) if ar else 0

        # Get max AR across all clients for normalization
        max_ar = (
            self._query_scalar("""
            SELECT MAX(total) FROM (
                SELECT client_id, SUM(amount) as total
                FROM invoices
                WHERE status IN ('sent', 'overdue')
                AND payment_date IS NULL

                GROUP BY client_id
            )
        """)
            or 1
        )

        ar_normalized = ar_total / max_ar if max_ar > 0 else 0

        # Check for active retainer
        retainer = self._query_one(
            """
            SELECT 1 FROM projects
            WHERE client_id = ? AND type = 'retainer' AND status = 'active'
            LIMIT 1
        """,
            (client_id,),
        )
        retainer_bonus = 0.1 if retainer else 0

        value = ar_normalized * 0.5 + tier_bonus + retainer_bonus
        return max(0.0, min(1.0, value))

    def determine_posture(self, health_score: float, value_score: float, tier: str) -> Posture:
        """
        Posture quadrant per §5.1:
        - PROTECT: high health (≥80), high value (≥0.7)
        - WATCH: stable but showing drift
        - INTERVENE: at-risk and valuable
        - CONTAIN: low value, noisy
        """
        is_at_risk = self._is_at_risk(health_score, tier)
        is_high_value = value_score >= 0.7
        is_med_value = value_score >= 0.4

        if not is_at_risk and is_high_value:
            return Posture.PROTECT
        if is_at_risk and (is_high_value or is_med_value):
            return Posture.INTERVENE
        if not is_at_risk:
            return Posture.WATCH
        return Posture.CONTAIN

    def _is_at_risk(self, health_score: float, tier: str) -> bool:
        """Check if client is at-risk per §2.3 tier thresholds."""
        thresholds = self.TIER_THRESHOLDS.get(tier, self.TIER_THRESHOLDS["C"])
        return health_score < thresholds["at_risk_health"]

    def determine_top_driver(self, breakdown: HealthBreakdown) -> TopDriver:
        """
        Top driver per §5.2:
        Exactly one label - the domain with highest normalized risk contribution.
        """
        # Calculate risk contribution (100 - score) * weight
        contributions = {
            TopDriver.DELIVERY: (100 - breakdown.delivery.score) * self.W_D,
            TopDriver.CASH: (100 - breakdown.cash.score) * self.W_C,
            TopDriver.COMMS: (100 - breakdown.responsiveness.score) * self.W_R,
            TopDriver.COMMITMENTS: (100 - breakdown.commitments.score) * self.W_K,
        }

        # Find max contribution
        max_driver = max(contributions, key=contributions.get)

        # If all scores are high (low contribution), return Unknown
        if contributions[max_driver] < 5:
            return TopDriver.UNKNOWN

        return max_driver

    def get_severe_ar_total(self, client_id: str) -> float:
        """Get severe AR total (61+) per §6.3."""
        result = self._query_one(
            """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM invoices
            WHERE client_id = ?
            AND aging_bucket IN ('61-90', '90+')
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL

        """,
            (client_id,),
        )
        return result.get("total", 0) if result else 0

    # ==========================================================================
    # PORTFOLIO (§3 Zone C)
    # ==========================================================================

    def get_eligible_clients(self) -> list[str]:
        """Get eligible clients (linked, non-internal)."""
        rows = self._query_all("""
            SELECT DISTINCT c.id
            FROM clients c
            WHERE EXISTS (
                SELECT 1 FROM projects p
                WHERE p.client_id = c.id
                AND p.is_internal = 0
            )
            OR EXISTS (
                SELECT 1 FROM invoices i
                WHERE i.client_id = c.id

            )
        """)
        return [r["id"] for r in rows]

    def build_portfolio(self) -> list[ClientPortfolioItem]:
        """Build portfolio heatstrip per Zone C (max 25)."""
        client_ids = self.get_eligible_clients()
        items = []

        for cid in client_ids:
            client = self._query_one(
                """
                SELECT id, name, tier FROM clients WHERE id = ?
            """,
                (cid,),
            )
            if not client:
                continue

            breakdown, health = self.compute_health_score(cid)
            value = self.compute_value_score(cid)
            tier = client.get("tier", "C") or "C"
            posture = self.determine_posture(health, value, tier)
            top_driver = self.determine_top_driver(breakdown)
            severe_ar = self.get_severe_ar_total(cid)
            confidence, why_low = self._get_overall_confidence(breakdown)

            # Get next break
            next_break = self._get_next_break_at(cid)

            items.append(
                ClientPortfolioItem(
                    client_id=cid,
                    client_name=client.get("name", ""),
                    tier=tier,
                    health_score=round(health, 1),
                    posture=posture,
                    top_driver=top_driver,
                    value_score=round(value, 3),
                    severe_ar_total=severe_ar,
                    next_break_at=next_break,
                    trend=None,  # Requires delta tracking
                    confidence=confidence,
                    why_low=why_low,
                )
            )

        # Sort by client_risk_score per §7.1
        items.sort(key=lambda x: self._compute_risk_score(x), reverse=True)

        return items[: self.MAX_PORTFOLIO]

    def _compute_risk_score(self, item: ClientPortfolioItem) -> float:
        """
        Client risk score per §7.1:
        client_risk_score = (1 - HealthScore/100) * (0.7 + 0.3*ValueScore) * ConfidenceScalar
        """
        conf_scalar = {Confidence.HIGH: 1.0, Confidence.MED: 0.8, Confidence.LOW: 0.6}
        return (
            (1 - item.health_score / 100)
            * (0.7 + 0.3 * item.value_score)
            * conf_scalar.get(item.confidence, 1.0)
        )

    def _get_next_break_at(self, client_id: str) -> str | None:
        """Get ISO timestamp of next consequence."""
        # Check overdue tasks
        task = self._query_one(
            """
            SELECT MIN(due_date) as next
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
            AND t.status NOT IN ('done', 'completed')
            AND t.due_date >= date('now')
            AND t.due_date >= '2026-01-01'
        """,
            (client_id,),
        )

        if task and task.get("next"):
            next_val = task["next"]
            # Only append time if not already present
            if "T" not in next_val:
                next_val += "T23:59:59"
            return next_val

        # Check commitment deadlines
        commit = self._query_one(
            """
            SELECT MIN(deadline) as next
            FROM commitments
            WHERE client_id = ?
            AND status = 'open'
            AND deadline >= date('now')
        """,
            (client_id,),
        )

        if commit and commit.get("next"):
            return commit["next"]

        return None

    # ==========================================================================
    # TILES (§3 Zone B)
    # ==========================================================================

    def build_tiles(self, portfolio: list[ClientPortfolioItem]) -> dict:
        """Build status tiles per Zone B."""
        # At-risk clients
        at_risk = [
            p for p in portfolio if p.posture == Posture.INTERVENE or p.posture == Posture.CONTAIN
        ]
        at_risk_count = len(at_risk)

        # Top driver for at-risk
        if at_risk:
            driver_counts = {}
            for p in at_risk:
                driver_counts[p.top_driver] = driver_counts.get(p.top_driver, 0) + 1
            top_driver = max(driver_counts, key=driver_counts.get)
        else:
            top_driver = TopDriver.UNKNOWN

        # Revenue at risk (severe AR from at-risk clients)
        revenue_at_risk = sum(p.severe_ar_total for p in at_risk)

        # Relationship drift (worsening_fast count)
        worsening_fast = [p for p in portfolio if p.trend == Trend.WORSENING_FAST]

        # Silence breaches
        silence_count = self._count_silence_breaches()

        return {
            "at_risk_count": {
                "count": at_risk_count,
                "top_driver": top_driver.value,
            },
            "revenue_at_risk": {
                "amount": revenue_at_risk,
                "currency": "AED",
                "why": f"Severe AR from {at_risk_count} at-risk clients",
            },
            "relationship_drift": {
                "worsening_fast": len(worsening_fast),
                "delta_badge": None,
            },
            "silence_breaches": {
                "count": silence_count,
                "threshold": "72h or SLA breach",
            },
        }

    def _count_silence_breaches(self) -> int:
        """Count high-risk silence per §5.3."""
        result = self._query_one("""
            SELECT COUNT(*) as c
            FROM communications
            WHERE processed = 0
            AND (
                (expected_response_by IS NOT NULL AND datetime(expected_response_by) < datetime('now'))
                OR COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) > 72
            )
            AND (requires_response = 1 OR from_domain IS NOT NULL)
        """)
        return result.get("c", 0) if result else 0

    # ==========================================================================
    # MOVES (§3 Zone D)
    # ==========================================================================

    def build_moves(self, portfolio: list[ClientPortfolioItem]) -> list[dict]:
        """Build relationship moves per Zone D (max 7)."""
        moves = []

        # Generate candidate moves from portfolio
        for p in portfolio:
            if p.posture in [Posture.INTERVENE, Posture.CONTAIN]:
                move = self._generate_move_for_client(p)
                if move:
                    moves.append(move)

        # Add cross-client moves (unknown triage, etc.)
        unlinked_moves = self._generate_unlinked_triage_moves()
        moves.extend(unlinked_moves)

        # Score and rank moves
        scored = []
        for m in moves:
            base_score = self._score_move(m)
            # Apply mode multipliers
            multiplier = self.MODE_MULTIPLIERS.get(self.mode, {}).get(m["type"], 1.0)
            if not self.commitment_ready and m["type"] == MoveType.COMMITMENT_REPAIR:
                multiplier *= 0.80
            m["score"] = base_score * multiplier
            scored.append(m)

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Apply horizon eligibility filter
        eligible = [m for m in scored if self._is_move_eligible(m)]

        return eligible[: self.MAX_MOVES]

    def _generate_move_for_client(self, p: ClientPortfolioItem) -> dict | None:
        """Generate a move for an at-risk client."""
        move_type = self._map_driver_to_move_type(p.top_driver)

        # Build action based on type
        if move_type == MoveType.DELIVERY_STABILIZATION:
            label = f"Stabilize delivery for {p.client_name}"
            action = {
                "risk": "propose",
                "label": "Review blocked tasks",
                "payload": {"client_id": p.client_id},
            }
        elif move_type == MoveType.CASH_UNBLOCK:
            label = f"Unblock cash for {p.client_name}"
            action = {
                "risk": "propose",
                "label": "Draft collection email",
                "payload": {"client_id": p.client_id},
            }
        elif move_type == MoveType.COMMS_RESCUE:
            label = f"Rescue comms for {p.client_name}"
            action = {
                "risk": "propose",
                "label": "Draft response",
                "payload": {"client_id": p.client_id},
            }
        elif move_type == MoveType.COMMITMENT_REPAIR:
            label = f"Repair commitment for {p.client_name}"
            action = {
                "risk": "approval",
                "label": "Acknowledge breach",
                "payload": {"client_id": p.client_id},
            }
        else:
            label = f"Prevent churn for {p.client_name}"
            action = {
                "risk": "propose",
                "label": "Schedule check-in",
                "payload": {"client_id": p.client_id},
            }
            move_type = MoveType.CHURN_PREVENTION

        # Calculate time to consequence
        ttc = None
        if p.next_break_at:
            try:
                break_dt = datetime.fromisoformat(p.next_break_at.replace("Z", "+00:00"))
                ttc = (break_dt.replace(tzinfo=None) - self.now).total_seconds() / 3600
            except (ValueError, TypeError, AttributeError) as e:
                # next_break_at is computed internally - malformed value indicates bug
                logger.warning(f"Invalid next_break_at value '{p.next_break_at}': {e}")

        return {
            "move_id": f"move-{p.client_id}-{move_type.value.lower()}",
            "type": move_type,
            "label": label,
            "client_id": p.client_id,
            "score": 0.0,  # Computed later
            "time_to_consequence_hours": ttc,
            "confidence": p.confidence,
            "why_low": p.why_low,
            "primary_action": action,
            "secondary_actions": [],
            "evidence_ids": [p.client_id],
        }

    def _map_driver_to_move_type(self, driver: TopDriver) -> MoveType:
        """Map top driver to move type."""
        mapping = {
            TopDriver.DELIVERY: MoveType.DELIVERY_STABILIZATION,
            TopDriver.CASH: MoveType.CASH_UNBLOCK,
            TopDriver.COMMS: MoveType.COMMS_RESCUE,
            TopDriver.COMMITMENTS: MoveType.COMMITMENT_REPAIR,
            TopDriver.UNKNOWN: MoveType.UNKNOWN_CLIENT_TRIAGE,
        }
        return mapping.get(driver, MoveType.CHURN_PREVENTION)

    def _generate_unlinked_triage_moves(self) -> list[dict]:
        """Generate triage moves for unlinked clients/comms."""
        moves = []

        # Check for unlinked comms
        unlinked = self._query_all("""
            SELECT id, subject, from_email as from_address
            FROM communications
            WHERE client_id IS NULL
            AND processed = 0
            ORDER BY received_at DESC
            LIMIT 3
        """)

        for u in unlinked[:2]:
            moves.append(
                {
                    "move_id": f"move-triage-{u['id']}",
                    "type": MoveType.UNKNOWN_CLIENT_TRIAGE,
                    "label": f"Triage unknown: {u.get('subject', 'No subject')[:40]}",
                    "client_id": None,
                    "score": 0.0,
                    "time_to_consequence_hours": None,
                    "confidence": Confidence.LOW,
                    "why_low": ["Client unknown"],
                    "primary_action": {
                        "risk": "auto",
                        "label": "Link to client",
                        "payload": {"comm_id": u["id"]},
                    },
                    "secondary_actions": [],
                    "evidence_ids": [u["id"]],
                }
            )

        return moves

    def _score_move(self, move: dict) -> float:
        """
        Score move per §7.3:
        MoveScore = w_I*Impact + w_U*Urgency + w_C*Controllability + w_Q*Confidence
        """
        # Impact (0-1): based on move type and client value
        impact_map = {
            MoveType.CHURN_PREVENTION: 0.9,
            MoveType.CASH_UNBLOCK: 0.85,
            MoveType.DELIVERY_STABILIZATION: 0.8,
            MoveType.COMMITMENT_REPAIR: 0.75,
            MoveType.COMMS_RESCUE: 0.7,
            MoveType.STAKEHOLDER_ALIGNMENT: 0.65,
            MoveType.UNKNOWN_CLIENT_TRIAGE: 0.5,
        }
        impact = impact_map.get(move["type"], 0.5)

        # Urgency (0-1): based on time to consequence
        ttc = move.get("time_to_consequence_hours")
        if ttc is not None and ttc > 0:
            if ttc <= 4:
                urgency = 1.0
            elif ttc <= 24:
                urgency = 0.8
            elif ttc <= 72:
                urgency = 0.6
            else:
                urgency = 0.4
        else:
            urgency = 0.5

        # Controllability (0-1): based on action risk
        risk = move.get("primary_action", {}).get("risk", "propose")
        controllability = {"auto": 0.9, "propose": 0.7, "approval": 0.5}.get(risk, 0.7)

        # Confidence (0-1)
        conf = move.get("confidence", Confidence.HIGH)
        conf_score = {
            Confidence.HIGH: 1.0,
            Confidence.MED: 0.7,
            Confidence.LOW: 0.4,
        }.get(conf, 0.7)

        return (
            self.W_I * impact
            + self.W_U * urgency
            + self.W_C * controllability
            + self.W_Q * conf_score
        )

    def _is_move_eligible(self, move: dict) -> bool:
        """Check move eligibility per §7.2."""
        ttc = move.get("time_to_consequence_hours")

        if self.horizon == Horizon.NOW:
            # Must be actionable within 12h
            return ttc is None or ttc <= 12
        if self.horizon == Horizon.TODAY:
            # Resolves breach before EOD
            return ttc is None or ttc <= 24
        # THIS WEEK
        return ttc is None or ttc <= 168

    # ==========================================================================
    # RIGHT COLUMN (§3 Zone E)
    # ==========================================================================

    def build_right_column(self, portfolio: list[ClientPortfolioItem]) -> dict:
        """Build right column per Zone E."""
        return {
            "top_drifts": self._build_top_drifts(portfolio),
            "silence_ladder": self._build_silence_ladder(),
            "severe_ar_ladder": self._build_severe_ar_ladder(portfolio),
        }

    def _build_top_drifts(self, portfolio: list[ClientPortfolioItem]) -> list[dict]:
        """Top drifts per §3 Zone E (max 5)."""
        # For now, use clients with low health as proxy for drift
        drifting = [p for p in portfolio if p.health_score < 75]
        drifting.sort(key=lambda x: x.health_score)

        return [
            {
                "client_id": p.client_id,
                "text": f"{p.client_name}: {p.top_driver.value} risk",
                "impact": round((100 - p.health_score) / 100, 2),
            }
            for p in drifting[: self.MAX_DRIFTS]
        ]

    def _build_silence_ladder(self) -> list[dict]:
        """Silence ladder per §3 Zone E (max 5)."""
        threads = self._query_all(
            """
            SELECT
                c.id as thread_id,
                c.client_id,
                c.subject,
                COALESCE(c.age_hours, (julianday('now') - julianday(c.received_at)) * 24) as age_hours,
                c.expected_response_by,
                CASE
                    WHEN c.expected_response_by IS NOT NULL
                         AND datetime(c.expected_response_by) < datetime('now') THEN 'HIGH'
                    WHEN COALESCE(c.age_hours, (julianday('now') - julianday(c.received_at)) * 24) > 72 THEN 'MED'
                    ELSE 'LOW'
                END as risk
            FROM communications c
            WHERE c.processed = 0
            AND (c.requires_response = 1 OR c.from_domain IS NOT NULL)
            ORDER BY
                CASE WHEN c.expected_response_by IS NOT NULL
                     AND datetime(c.expected_response_by) < datetime('now') THEN 0 ELSE 1 END,
                COALESCE(c.age_hours, (julianday('now') - julianday(c.received_at)) * 24) DESC
            LIMIT ?
        """,
            (self.MAX_SILENCE,),
        )

        return [
            {
                "thread_id": t["thread_id"],
                "client_id": t["client_id"],
                "subject": t.get("subject", "")[:50],
                "age_hours": round(t.get("age_hours") or 0, 1),
                "expected_response_by": t.get("expected_response_by"),
                "risk": t.get("risk", "LOW"),
            }
            for t in threads
        ]

    def _build_severe_ar_ladder(self, portfolio: list[ClientPortfolioItem]) -> list[dict]:
        """Severe AR ladder per §3 Zone E (max 5)."""
        with_ar = [p for p in portfolio if p.severe_ar_total > 0]
        with_ar.sort(key=lambda x: x.severe_ar_total, reverse=True)

        return [
            {
                "client_id": p.client_id,
                "client_name": p.client_name,
                "severe_total": p.severe_ar_total,
                "currency": "AED",
                "confidence": p.confidence.value,
            }
            for p in with_ar[: self.MAX_SEVERE_AR]
        ]

    # ==========================================================================
    # DRAWER - CLIENT ROOM (§9)
    # ==========================================================================

    def build_client_room(self, client_id: str) -> dict | None:
        """Build client room drawer per §9."""
        client = self._query_one("SELECT * FROM clients WHERE id = ?", (client_id,))
        if not client:
            return None

        breakdown, health = self.compute_health_score(client_id)
        value = self.compute_value_score(client_id)
        tier = client.get("tier", "C") or "C"
        posture = self.determine_posture(health, value, tier)
        top_driver = self.determine_top_driver(breakdown)
        confidence, why_low = self._get_overall_confidence(breakdown)

        # Get next break
        next_break = self._get_next_break_at(client_id)

        return {
            "summary": self._build_room_summary(client, health, posture, top_driver, next_break),
            "health_breakdown": {
                "delivery": {
                    "score": round(breakdown.delivery.score, 1),
                    "confidence": breakdown.delivery.confidence.value,
                    "why_low": breakdown.delivery.why_low,
                },
                "cash": {
                    "score": round(breakdown.cash.score, 1),
                    "confidence": breakdown.cash.confidence.value,
                    "why_low": breakdown.cash.why_low,
                },
                "responsiveness": {
                    "score": round(breakdown.responsiveness.score, 1),
                    "confidence": breakdown.responsiveness.confidence.value,
                    "why_low": breakdown.responsiveness.why_low,
                },
                "commitments": {
                    "score": round(breakdown.commitments.score, 1),
                    "confidence": breakdown.commitments.confidence.value,
                    "why_low": breakdown.commitments.why_low,
                },
            },
            "breaks_next": self._build_breaks_next(client_id),
            "delivery_projects": self._build_delivery_projects(client_id),
            "cash_bucket_strip": self._build_cash_bucket_strip(client_id),
            "comms_threads": self._build_comms_threads(client_id),
            "commitments": self._build_commitments_list(client_id),
            "actions": self._build_room_actions(client_id, top_driver),
            "reason": f"{self.horizon.value} | driver={top_driver.value} | trend=unknown",
        }

    def _build_room_summary(
        self,
        client: dict,
        health: float,
        posture: Posture,
        top_driver: TopDriver,
        next_break: str | None,
    ) -> str:
        """Build 2-3 sentence summary per §9.1."""
        name = client.get("name", "Unknown")
        tier = client.get("tier", "C")

        health_desc = "healthy" if health >= 80 else "at-risk" if health < 60 else "moderate"

        summary = f"{name} (Tier {tier}) is {health_desc} with health score {health:.0f}. "
        summary += f"Primary posture: {posture.value}. "

        if top_driver != TopDriver.UNKNOWN:
            summary += f"Key driver: {top_driver.value}."

        if next_break:
            summary += f" Next break: {next_break[:10]}."

        return summary

    def _build_breaks_next(self, client_id: str) -> list[dict]:
        """Build breaks_next per §9.1 (max 3)."""
        breaks = []

        # Check overdue/upcoming tasks
        tasks = self._query_all(
            """
            SELECT t.id, t.title, t.due_date, p.name as project_name
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
            AND t.status NOT IN ('done', 'completed')
            AND t.due_date >= '2026-01-01'
            ORDER BY t.due_date ASC
            LIMIT 2
        """,
            (client_id,),
        )

        for t in tasks:
            breaks.append(
                {
                    "type": "delivery",
                    "at": t.get("due_date"),
                    "text": f"Task: {t.get('title', '')[:40]}",
                    "why": f"Project: {t.get('project_name', '')}",
                    "primary_action": {
                        "risk": "auto",
                        "label": "Open task",
                        "payload": {"task_id": t["id"]},
                    },
                }
            )

        # Check commitment deadlines
        commits = self._query_all(
            """
            SELECT id, text, deadline
            FROM commitments
            WHERE client_id = ?
            AND status = 'open'
            AND deadline IS NOT NULL
            ORDER BY deadline ASC
            LIMIT 1
        """,
            (client_id,),
        )

        for c in commits:
            breaks.append(
                {
                    "type": "commitment",
                    "at": c.get("deadline"),
                    "text": f"Commitment: {c.get('text', '')[:40]}",
                    "why": "Open commitment approaching deadline",
                    "primary_action": {
                        "risk": "propose",
                        "label": "Review commitment",
                        "payload": {"commitment_id": c["id"]},
                    },
                }
            )

        return breaks[: self.MAX_BREAKS_NEXT]

    def _build_delivery_projects(self, client_id: str) -> list[dict]:
        """Build delivery projects per §9.1 (max 3)."""
        projects = self._query_all(
            """
            SELECT
                p.id as project_id,
                p.name,
                CASE
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 3 THEN 'RED'
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 1 THEN 'YELLOW'
                    ELSE 'GREEN'
                END as status
            FROM projects p
            WHERE p.client_id = ?
            AND p.is_internal = 0
            AND p.status = 'active'
            ORDER BY
                CASE
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 3 THEN 0
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 1 THEN 1
                    ELSE 2
                END
            LIMIT ?
        """,
            (client_id, self.MAX_DELIVERY_PROJECTS),
        )

        result = []
        for p in projects:
            # Get breaks_next for this project
            breaks = self._query_all(
                """
                SELECT id as task_id, title, due_date
                FROM tasks
                WHERE project_id = ?
                AND status NOT IN ('done', 'completed')
                AND due_date >= '2026-01-01'
                ORDER BY due_date ASC
                LIMIT 2
            """,
                (p["project_id"],),
            )

            result.append(
                {
                    "project_id": p["project_id"],
                    "name": p["name"],
                    "status": p["status"],
                    "slip_risk": 0.5
                    if p["status"] == "RED"
                    else 0.2
                    if p["status"] == "YELLOW"
                    else 0.0,
                    "breaks_next": [
                        {
                            "task_id": b["task_id"],
                            "title": b["title"],
                            "due_at": b.get("due_date"),
                        }
                        for b in breaks
                    ],
                }
            )

        return result

    def _build_cash_bucket_strip(self, client_id: str) -> dict:
        """Build cash bucket strip per §9.1."""
        result = self._query_one(
            """
            SELECT
                COALESCE(SUM(CASE WHEN aging_bucket = 'current' THEN amount ELSE 0 END), 0) as current,
                COALESCE(SUM(CASE WHEN aging_bucket = '1-30' THEN amount ELSE 0 END), 0) as "1-30",
                COALESCE(SUM(CASE WHEN aging_bucket = '31-60' THEN amount ELSE 0 END), 0) as "31-60",
                COALESCE(SUM(CASE WHEN aging_bucket = '61-90' THEN amount ELSE 0 END), 0) as "61-90",
                COALESCE(SUM(CASE WHEN aging_bucket = '90+' THEN amount ELSE 0 END), 0) as "90+"
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL

        """,
            (client_id,),
        )

        # Get next due
        next_due = self._query_one(
            """
            SELECT MIN(due_date) as next_due_at
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL
        """,
            (client_id,),
        )

        return {
            "current": result.get("current", 0) if result else 0,
            "1-30": result.get("1-30", 0) if result else 0,
            "31-60": result.get("31-60", 0) if result else 0,
            "61-90": result.get("61-90", 0) if result else 0,
            "90+": result.get("90+", 0) if result else 0,
            "next_due_at": next_due.get("next_due_at") if next_due else None,
        }

    def _build_comms_threads(self, client_id: str) -> list[dict]:
        """Build comms threads per §9.1 (max 5)."""
        threads = self._query_all(
            """
            SELECT
                id as thread_id,
                subject,
                COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) as age_hours,
                expected_response_by,
                CASE
                    WHEN expected_response_by IS NOT NULL
                         AND datetime(expected_response_by) < datetime('now') THEN 'HIGH'
                    WHEN COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) > 72 THEN 'MED'
                    ELSE 'LOW'
                END as risk
            FROM communications
            WHERE client_id = ?
            AND processed = 0
            ORDER BY received_at DESC
            LIMIT ?
        """,
            (client_id, self.MAX_COMMS_THREADS),
        )

        return [
            {
                "thread_id": t["thread_id"],
                "subject": t.get("subject", "")[:50],
                "age_hours": round(t.get("age_hours") or 0, 1),
                "expected_response_by": t.get("expected_response_by"),
                "risk": t.get("risk", "LOW"),
            }
            for t in threads
        ]

    def _build_commitments_list(self, client_id: str) -> list[dict]:
        """Build commitments list per §9.1 (max 5)."""
        commits = self._query_all(
            """
            SELECT
                id as commitment_id,
                text,
                status,
                deadline,
                confidence
            FROM commitments
            WHERE client_id = ?
            ORDER BY
                CASE status WHEN 'broken' THEN 0 WHEN 'open' THEN 1 ELSE 2 END,
                deadline ASC
            LIMIT ?
        """,
            (client_id, self.MAX_COMMITMENTS),
        )

        return [
            {
                "commitment_id": c["commitment_id"],
                "text": c.get("text", "")[:60],
                "status": c.get("status", "open"),
                "deadline": c.get("deadline"),
                "confidence": c.get("confidence", 0.5),
            }
            for c in commits
        ]

    def _build_room_actions(self, client_id: str, top_driver: TopDriver) -> list[dict]:
        """Build room actions per §9.1 (max 4)."""
        actions = []

        # Primary action based on top driver
        if top_driver == TopDriver.DELIVERY:
            actions.append(
                {
                    "risk": "auto",
                    "label": "Open Delivery Command",
                    "idempotency_key": f"action-{client_id}-delivery",
                    "payload": {"view": "delivery", "client": client_id},
                    "why": "Delivery is primary risk driver",
                }
            )
        elif top_driver == TopDriver.CASH:
            actions.append(
                {
                    "risk": "propose",
                    "label": "Draft collection email",
                    "idempotency_key": f"action-{client_id}-collection",
                    "payload": {"action": "draft_collection", "client": client_id},
                    "why": "Cash is primary risk driver",
                }
            )
        elif top_driver == TopDriver.COMMS:
            actions.append(
                {
                    "risk": "propose",
                    "label": "Draft response",
                    "idempotency_key": f"action-{client_id}-respond",
                    "payload": {"action": "draft_response", "client": client_id},
                    "why": "Comms responsiveness is primary risk driver",
                }
            )
        elif top_driver == TopDriver.COMMITMENTS:
            actions.append(
                {
                    "risk": "approval",
                    "label": "Review commitment breach",
                    "idempotency_key": f"action-{client_id}-commitment",
                    "payload": {"action": "review_commitment", "client": client_id},
                    "why": "Commitment breach detected",
                }
            )

        # Secondary actions
        actions.append(
            {
                "risk": "auto",
                "label": "View client profile",
                "idempotency_key": f"action-{client_id}-profile",
                "payload": {"view": "client", "client": client_id},
                "why": "Standard context action",
            }
        )

        actions.append(
            {
                "risk": "propose",
                "label": "Schedule check-in",
                "idempotency_key": f"action-{client_id}-checkin",
                "payload": {"action": "schedule_checkin", "client": client_id},
                "why": "Proactive relationship maintenance",
            }
        )

        return actions[: self.MAX_DRAWER_ACTIONS]

    # ==========================================================================
    # SELECTED CLIENT (UI-expected format)
    # ==========================================================================

    def build_selected_client(self, client_id: str) -> dict | None:
        """
        Build selected client data in the format the UI expects.

        UI expects:
        - header.owner, header.brands_count, header.active_projects_count
        - summary_sentence
        - confidence.why_low
        - scores (delivery, finance, responsiveness, commitments, capacity)
        - key_drivers
        - delivery_exposure.projects
        """
        client = self._query_one("SELECT * FROM clients WHERE id = ?", (client_id,))
        if not client:
            return None

        breakdown, health = self.compute_health_score(client_id)
        value = self.compute_value_score(client_id)
        tier = client.get("tier", "C") or "C"
        self.determine_posture(health, value, tier)
        top_driver = self.determine_top_driver(breakdown)
        confidence, why_low = self._get_overall_confidence(breakdown)
        self._get_next_break_at(client_id)

        # Get owner (most common assignee on client's active tasks)
        owner = self._query_one(
            """
            SELECT t.assignee as name, COUNT(*) as cnt
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
              AND p.is_internal = 0
              AND t.assignee IS NOT NULL
              AND t.assignee != 'unassigned'
              AND t.status NOT IN ('done', 'completed')
            GROUP BY t.assignee
            ORDER BY cnt DESC
            LIMIT 1
        """,
            (client_id,),
        )
        owner_name = owner.get("name", "--") if owner else "--"

        # Get brands count
        brands_count = (
            self._query_scalar(
                """
            SELECT COUNT(DISTINCT brand_id)
            FROM projects
            WHERE client_id = ? AND brand_id IS NOT NULL AND is_internal = 0
        """,
                (client_id,),
            )
            or 0
        )

        # Get active projects count
        active_projects_count = (
            self._query_scalar(
                """
            SELECT COUNT(*)
            FROM projects
            WHERE client_id = ? AND is_internal = 0 AND status = 'active'
        """,
                (client_id,),
            )
            or 0
        )

        # Build summary sentence
        name = client.get("name", "Unknown")
        health_desc = "healthy" if health >= 80 else "at-risk" if health < 60 else "moderate"
        summary_sentence = f"{name} is {health_desc} with health score {health:.0f}. Primary driver: {top_driver.value}."

        # Build key drivers from top_driver and breakdown
        key_drivers = self._build_key_drivers(client_id, breakdown, top_driver)

        # Build delivery exposure
        delivery_exposure = self._build_delivery_exposure(client_id)

        # Build cash exposure
        cash_exposure = self._build_cash_exposure(client_id)

        # Build comms
        comms = self._build_comms_section(client_id)

        # Build commitments
        commitments = self._build_commitments_section(client_id)

        # Build capacity
        capacity = self._build_capacity_section(client_id)

        # Build recent changes
        recent_change = self._build_recent_change(client_id)

        # Build actions
        actions = self._build_actions_section(client_id, top_driver)

        return {
            "client_id": client_id,
            "header": {
                "owner": owner_name,
                "brands_count": brands_count,
                "active_projects_count": active_projects_count,
            },
            "summary_sentence": summary_sentence,
            "confidence": {
                "level": confidence.value,
                "why_low": why_low,
            },
            "scores": {
                "delivery": round(breakdown.delivery.score, 1),
                "finance": round(breakdown.cash.score, 1),
                "responsiveness": round(breakdown.responsiveness.score, 1),
                "commitments": round(breakdown.commitments.score, 1),
                "capacity": 100.0,  # Capacity not computed per-client, default to 100
            },
            "key_drivers": key_drivers,
            "delivery_exposure": delivery_exposure,
            "cash_exposure": cash_exposure,
            "comms": comms,
            "commitments": commitments,
            "capacity": capacity,
            "recent_change": recent_change,
            "actions": actions,
        }

    def _build_key_drivers(
        self, client_id: str, breakdown: HealthBreakdown, top_driver: TopDriver
    ) -> list[dict]:
        """Build key drivers for selected client."""
        drivers = []

        # Add driver based on lowest scoring domain
        domain_scores = [
            ("Delivery", breakdown.delivery.score, "Review blocked tasks"),
            ("Cash", breakdown.cash.score, "Draft collection email"),
            ("Comms", breakdown.responsiveness.score, "Draft response"),
            ("Commitments", breakdown.commitments.score, "Review commitments"),
        ]

        # Sort by score ascending (lowest = most critical)
        domain_scores.sort(key=lambda x: x[1])

        for name, score, action_label in domain_scores[:3]:
            if score < 80:  # Only add if below healthy threshold
                drivers.append(
                    {
                        "title": f"{name} health at {score:.0f}%",
                        "primary_action": {"label": action_label},
                    }
                )

        return drivers[:5]

    def _build_delivery_exposure(self, client_id: str) -> dict:
        """Build delivery exposure for selected client."""
        projects = self._query_all(
            """
            SELECT
                p.id as project_id,
                p.name,
                CASE
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 3 THEN 'RED'
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 1 THEN 'YELLOW'
                    ELSE 'GREEN'
                END as status,
                (SELECT MIN(t.due_date) FROM tasks t
                 WHERE t.project_id = p.id
                 AND t.status NOT IN ('done', 'completed')
                 AND t.due_date >= date('now')
                 AND t.due_date >= '2026-01-01') as next_due
            FROM projects p
            WHERE p.client_id = ?
            AND p.is_internal = 0
            AND p.status = 'active'
            ORDER BY
                CASE
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 3 THEN 0
                    WHEN (SELECT COUNT(*) FROM tasks t
                          WHERE t.project_id = p.id
                          AND t.due_date < date('now')
                          AND t.due_date >= '2026-01-01'
                          AND t.status NOT IN ('done', 'completed')) >= 1 THEN 1
                    ELSE 2
                END
            LIMIT 7
        """,
            (client_id,),
        )

        result = []
        for p in projects:
            # Calculate time to slip
            time_to_slip = None
            if p.get("next_due"):
                try:
                    due_dt = datetime.fromisoformat(p["next_due"])
                    time_to_slip = (due_dt - datetime.now()).total_seconds() / 3600
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse next_due for slip calc: {e}")

            # Calculate slip risk score
            slip_risk = 0.8 if p["status"] == "RED" else 0.4 if p["status"] == "YELLOW" else 0.1

            result.append(
                {
                    "project_id": p["project_id"],
                    "name": p["name"],
                    "status": p["status"],
                    "time_to_slip_hours": time_to_slip,
                    "slip_risk_score": slip_risk,
                }
            )

        return {"projects": result}

    def _build_cash_exposure(self, client_id: str) -> dict:
        """Build cash/AR exposure for selected client."""
        # Get AR by bucket
        buckets = self._query_one(
            """
            SELECT
                COALESCE(SUM(CASE WHEN aging_bucket = 'current' THEN amount ELSE 0 END), 0) as current,
                COALESCE(SUM(CASE WHEN aging_bucket = '1-30' THEN amount ELSE 0 END), 0) as "1-30",
                COALESCE(SUM(CASE WHEN aging_bucket = '31-60' THEN amount ELSE 0 END), 0) as "31-60",
                COALESCE(SUM(CASE WHEN aging_bucket = '61-90' THEN amount ELSE 0 END), 0) as "61-90",
                COALESCE(SUM(CASE WHEN aging_bucket = '90+' THEN amount ELSE 0 END), 0) as "90+",
                COALESCE(SUM(amount), 0) as total
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL
        """,
            (client_id,),
        )

        ar_total = buckets.get("total", 0) if buckets else 0

        # Get top overdue lines
        top_lines = self._query_all(
            """
            SELECT
                id as invoice_id,
                amount,
                CAST(julianday('now') - julianday(due_date) AS INTEGER) as days_overdue
            FROM invoices
            WHERE client_id = ?
            AND status IN ('sent', 'overdue')
            AND payment_date IS NULL
            AND due_date < date('now')
            ORDER BY days_overdue DESC
            LIMIT 5
        """,
            (client_id,),
        )

        return {
            "ar_total": ar_total,
            "buckets": {
                "current": buckets.get("current", 0) if buckets else 0,
                "1-30": buckets.get("1-30", 0) if buckets else 0,
                "31-60": buckets.get("31-60", 0) if buckets else 0,
                "61-90": buckets.get("61-90", 0) if buckets else 0,
                "90+": buckets.get("90+", 0) if buckets else 0,
            },
            "top_lines": [
                {
                    "invoice_id": line["invoice_id"],
                    "amount": line["amount"],
                    "days_overdue": max(0, line.get("days_overdue") or 0),
                }
                for line in top_lines
            ],
        }

    def _build_comms_section(self, client_id: str) -> dict:
        """Build comms/responsiveness section for selected client."""
        # Get counts
        counts = self._query_one(
            """
            SELECT
                COUNT(*) FILTER (WHERE requires_response = 1 AND processed = 0) as response_needed,
                COUNT(*) FILTER (
                    WHERE processed = 0
                    AND (
                        (expected_response_by IS NOT NULL AND datetime(expected_response_by) < datetime('now'))
                        OR COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) > 72
                    )
                ) as overdue
            FROM communications
            WHERE client_id = ?
        """,
            (client_id,),
        )

        # SQLite doesn't support FILTER - use CASE instead
        counts = self._query_one(
            """
            SELECT
                SUM(CASE WHEN requires_response = 1 AND processed = 0 THEN 1 ELSE 0 END) as response_needed,
                SUM(CASE WHEN processed = 0 AND (
                    (expected_response_by IS NOT NULL AND datetime(expected_response_by) < datetime('now'))
                    OR COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) > 72
                ) THEN 1 ELSE 0 END) as overdue
            FROM communications
            WHERE client_id = ?
        """,
            (client_id,),
        )

        # Get threads
        threads = self._query_all(
            """
            SELECT
                subject,
                COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) as age_hours,
                CASE
                    WHEN expected_response_by IS NOT NULL
                         AND datetime(expected_response_by) < datetime('now') THEN 'HIGH'
                    WHEN COALESCE(age_hours, (julianday('now') - julianday(received_at)) * 24) > 72 THEN 'MED'
                    ELSE 'LOW'
                END as risk,
                CASE WHEN expected_response_by IS NOT NULL
                     AND datetime(expected_response_by) < datetime('now') THEN 1 ELSE 0 END as sla_breach
            FROM communications
            WHERE client_id = ?
            AND processed = 0
            ORDER BY received_at DESC
            LIMIT 7
        """,
            (client_id,),
        )

        return {
            "response_needed": int(counts.get("response_needed") or 0) if counts else 0,
            "overdue": int(counts.get("overdue") or 0) if counts else 0,
            "threads": [
                {
                    "subject": t.get("subject", "")[:50],
                    "age_hours": t.get("age_hours") or 0,
                    "risk": t.get("risk", "LOW"),
                    "sla_breach": bool(t.get("sla_breach")),
                }
                for t in threads
            ],
        }

    def _build_commitments_section(self, client_id: str) -> dict:
        """Build commitments section for selected client."""
        # Get counts
        counts = self._query_one(
            """
            SELECT
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'open' AND deadline < date('now') THEN 1 ELSE 0 END) as overdue_open_count,
                SUM(CASE WHEN status = 'broken' AND created_at >= date('now', '-30 days') THEN 1 ELSE 0 END) as broken_30d_count
            FROM commitments
            WHERE client_id = ?
        """,
            (client_id,),
        )

        # Get items
        items = self._query_all(
            """
            SELECT
                text,
                deadline,
                status,
                CASE
                    WHEN status = 'broken' THEN 'HIGH'
                    WHEN deadline IS NOT NULL AND deadline < date('now') THEN 'HIGH'
                    WHEN deadline IS NOT NULL AND deadline <= date('now', '+7 days') THEN 'MED'
                    ELSE 'LOW'
                END as risk
            FROM commitments
            WHERE client_id = ?
            AND status IN ('open', 'broken')
            ORDER BY
                CASE status WHEN 'broken' THEN 0 ELSE 1 END,
                deadline ASC
            LIMIT 7
        """,
            (client_id,),
        )

        return {
            "open_count": int(counts.get("open_count") or 0) if counts else 0,
            "overdue_open_count": int(counts.get("overdue_open_count") or 0) if counts else 0,
            "broken_30d_count": int(counts.get("broken_30d_count") or 0) if counts else 0,
            "items": [
                {
                    "text": i.get("text", "")[:60],
                    "deadline": i.get("deadline"),
                    "status": i.get("status", "open"),
                    "risk": i.get("risk", "LOW"),
                }
                for i in items
            ],
        }

    def _build_capacity_section(self, client_id: str) -> dict:
        """Build capacity section for selected client."""
        # Count active and overdue tasks (real data, not fake hours)
        counts = self._query_one(
            """
            SELECT
                COUNT(*) as active_tasks,
                SUM(CASE WHEN t.due_date < date('now') AND t.due_date >= '2026-01-01' THEN 1 ELSE 0 END) as overdue_tasks,
                COUNT(DISTINCT t.assignee) as assignee_count
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
            AND p.is_internal = 0
            AND t.status NOT IN ('done', 'completed')
        """,
            (client_id,),
        )

        active = int(counts.get("active_tasks") or 0) if counts else 0
        overdue = int(counts.get("overdue_tasks") or 0) if counts else 0
        assignees = int(counts.get("assignee_count") or 0) if counts else 0

        return {
            "active_tasks": active,
            "overdue_tasks": overdue,
            "assignee_count": assignees,
            # Legacy fields for UI compatibility (will be removed)
            "hours_needed": None,
            "hours_available": None,
            "gap_hours": None,
        }

    def _build_actions_section(self, client_id: str, top_driver: TopDriver) -> list[dict]:
        """Build actions for selected client."""
        actions = []

        # Primary action based on driver
        driver_actions = {
            TopDriver.DELIVERY: {
                "label": "Review blocked tasks",
                "risk_level": "auto",
                "why": "Delivery is primary risk driver",
            },
            TopDriver.CASH: {
                "label": "Draft collection email",
                "risk_level": "propose",
                "why": "Cash is primary risk driver",
            },
            TopDriver.COMMS: {
                "label": "Draft response",
                "risk_level": "propose",
                "why": "Comms is primary risk driver",
            },
            TopDriver.COMMITMENTS: {
                "label": "Review commitments",
                "risk_level": "approval",
                "why": "Commitment breach detected",
            },
        }

        if top_driver in driver_actions:
            actions.append(driver_actions[top_driver])

        # Standard actions
        actions.extend(
            [
                {
                    "label": "View client profile",
                    "risk_level": "auto",
                    "why": "Standard context",
                },
                {
                    "label": "Schedule check-in",
                    "risk_level": "propose",
                    "why": "Proactive relationship",
                },
                {
                    "label": "View project timeline",
                    "risk_level": "auto",
                    "why": "Delivery visibility",
                },
            ]
        )

        return actions[:7]

    def _build_recent_change(self, client_id: str) -> list[dict]:
        """Build recent changes for selected client (last 24h)."""
        changes = []

        # 1. Health score delta (compare to 24h ago)
        health_delta = self._query_one(
            """
            SELECT
                (SELECT health_score FROM client_health_log
                 WHERE client_id = ? ORDER BY computed_at DESC LIMIT 1) as current,
                (SELECT health_score FROM client_health_log
                 WHERE client_id = ? AND computed_at < datetime('now', '-24 hours')
                 ORDER BY computed_at DESC LIMIT 1) as previous
        """,
            (client_id, client_id),
        )

        if health_delta and health_delta.get("current") and health_delta.get("previous"):
            delta = health_delta["current"] - health_delta["previous"]
            if delta != 0:
                direction = "improved" if delta > 0 else "declined"
                changes.append({"text": f"Health score {direction} by {abs(delta)} points"})

        # 2. Tasks added in last 24h
        new_tasks = self._query_one(
            """
            SELECT COUNT(*) as cnt
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
            AND t.created_at >= datetime('now', '-24 hours')
        """,
            (client_id,),
        )
        new_tasks_cnt = int(new_tasks.get("cnt") or 0) if new_tasks else 0
        if new_tasks_cnt > 0:
            changes.append({"text": f"{new_tasks_cnt} new task(s) added"})

        # 3. Tasks completed in last 24h
        completed = self._query_one(
            """
            SELECT COUNT(*) as cnt
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
            AND t.status IN ('done', 'completed')
            AND t.updated_at >= datetime('now', '-24 hours')
        """,
            (client_id,),
        )
        completed_cnt = int(completed.get("cnt") or 0) if completed else 0
        if completed_cnt > 0:
            changes.append({"text": f"{completed_cnt} task(s) completed"})

        # 4. Tasks became overdue in last 24h
        newly_overdue = self._query_one(
            """
            SELECT COUNT(*) as cnt
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.client_id = ?
            AND t.status NOT IN ('done', 'completed')
            AND t.due_date >= date('now', '-1 day')
            AND t.due_date < date('now')
        """,
            (client_id,),
        )
        overdue_cnt = int(newly_overdue.get("cnt") or 0) if newly_overdue else 0
        if overdue_cnt > 0:
            changes.append({"text": f"{overdue_cnt} task(s) became overdue"})

        # 5. New communications received
        new_comms = self._query_one(
            """
            SELECT COUNT(*) as cnt
            FROM communications
            WHERE client_id = ?
            AND received_at >= datetime('now', '-24 hours')
        """,
            (client_id,),
        )
        comms_cnt = int(new_comms.get("cnt") or 0) if new_comms else 0
        if comms_cnt > 0:
            changes.append({"text": f"{comms_cnt} new email(s) received"})

        # 6. Invoice changes (new or paid)
        invoice_changes = self._query_one(
            """
            SELECT
                SUM(CASE WHEN created_at >= datetime('now', '-24 hours') THEN 1 ELSE 0 END) as new_cnt,
                SUM(CASE WHEN payment_date >= date('now', '-1 day') THEN 1 ELSE 0 END) as paid_cnt
            FROM invoices
            WHERE client_id = ?
        """,
            (client_id,),
        )
        if invoice_changes:
            new_cnt = int(invoice_changes.get("new_cnt") or 0)
            paid_cnt = int(invoice_changes.get("paid_cnt") or 0)
            if new_cnt > 0:
                changes.append({"text": f"{new_cnt} new invoice(s) created"})
            if paid_cnt > 0:
                changes.append({"text": f"{paid_cnt} invoice(s) paid"})

        return changes[:5]  # Max 5 changes

    # ==========================================================================
    # MAIN GENERATE (§10)
    # ==========================================================================

    def generate(self) -> dict:
        """Generate complete client360 snapshot per §10."""
        self.load_trust_state()

        # Compute overall confidence
        why_low = []
        if not self.client_coverage:
            why_low.append(f"Client coverage {self.client_coverage_pct:.0f}% < 80%")
        if not self.commitment_ready:
            why_low.append(f"Commitment ready {self.commitment_ready_pct:.0f}% < 50%")
        if not self.finance_ar_coverage:
            why_low.append(f"AR coverage {self.finance_ar_coverage_pct:.0f}% < 95%")

        if len(why_low) >= 2:
            client360_confidence = Confidence.LOW
        elif len(why_low) == 1:
            client360_confidence = Confidence.MED
        else:
            client360_confidence = Confidence.HIGH

        # Build portfolio
        portfolio = self.build_portfolio()

        # Build tiles
        tiles = self.build_tiles(portfolio)

        # Build moves
        moves = self.build_moves(portfolio)

        # Build right column
        right_column = self.build_right_column(portfolio)

        # Build drawer (full client data for each portfolio client, same format as selected_client)
        drawer_clients = {}
        for p in portfolio:
            client_data = self.build_selected_client(p.client_id)
            if client_data:
                drawer_clients[f"client:{p.client_id}"] = client_data

        # Pre-select first portfolio item
        selected_client = (
            drawer_clients.get(f"client:{portfolio[0].client_id}") if portfolio else None
        )

        return {
            "meta": {
                "generated_at": self.now.isoformat(),
                "mode": self.mode.value,
                "horizon": self.horizon.value,
                "trust": {
                    "data_integrity": self.data_integrity,
                    "client_coverage": self.client_coverage,
                    "commitment_ready": self.commitment_ready,
                    "finance_ar_coverage": self.finance_ar_coverage,
                    "delta_available": self.delta_available,
                    "client360_confidence": client360_confidence.value,
                    "why_low": why_low[:3],
                },
            },
            "tiles": tiles,
            "portfolio": [
                {
                    "client_id": p.client_id,
                    "client_name": p.client_name,
                    "tier": p.tier,
                    "health_score": p.health_score,
                    "posture": p.posture.value,
                    "top_driver": p.top_driver.value,
                    "value_score": p.value_score,
                    "severe_ar_total": p.severe_ar_total,
                    "next_break_at": p.next_break_at,
                    "trend": p.trend.value if p.trend else None,
                    "confidence": p.confidence.value,
                    "why_low": p.why_low,
                }
                for p in portfolio
            ],
            "moves": [
                {
                    "move_id": m["move_id"],
                    "type": m["type"].value,
                    "label": m["label"],
                    "client_id": m["client_id"],
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
            "right_column": right_column,
            "drawer": {
                "clients": drawer_clients,
            },
            "selected_client": selected_client,
        }


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import json

    engine = Client360Page10Engine()
    snapshot = engine.generate()
    logger.info(json.dumps(snapshot, indent=2, default=str))
