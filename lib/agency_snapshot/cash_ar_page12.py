"""
Cash/AR Command Engine - Page 12 LOCKED SPEC (v1)

Money Reality + Next Cash Moves. Executive cash console, not accounting software.

Hard rule: no invoice list browsing. Default surface is ranked moves + top debtors + exceptions.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pathlib import Path
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


class AgingBucket(StrEnum):
    CURRENT = "current"
    DAYS_1_30 = "1-30"
    DAYS_31_60 = "31-60"
    DAYS_61_90 = "61-90"
    DAYS_90_PLUS = "90+"


class InvalidReason(StrEnum):
    MISSING_DUE = "MISSING_DUE"
    MISSING_CLIENT = "MISSING_CLIENT"
    NONE = "NONE"


class MoveType(StrEnum):
    """Move types per §4.3 (immutable)"""

    SEVERE_COLLECTION_PUSH = "SEVERE_COLLECTION_PUSH"
    PRE_DUE_SAVE = "PRE_DUE_SAVE"
    DISPUTE_RESOLUTION = "DISPUTE_RESOLUTION"
    CREDIT_RISK_ESCALATION = "CREDIT_RISK_ESCALATION"
    INVOICE_HYGIENE_FIX = "INVOICE_HYGIENE_FIX"
    PAYMENT_CONFIRMATION_CHASE = "PAYMENT_CONFIRMATION_CHASE"
    UNKNOWN_TRIAGE = "UNKNOWN_TRIAGE"


class RiskBand(StrEnum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class HealthBand(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class InvoiceUnit:
    """Per §4.1"""

    invoice_id: str
    client_id: str | None
    client_name: str | None
    amount: float
    currency: str
    status: str
    issue_date: str | None
    due_date: str | None
    days_overdue: int | None
    aging_bucket: str | None
    valid_ar: bool
    invalid_reason: InvalidReason
    confidence: Confidence
    why_low: list[str]


@dataclass
class DebtorUnit:
    """Per §4.2"""

    client_id: str
    client_name: str
    currency: str
    total_valid_ar: float
    severe_ar: float
    next_due_amount_7d: float
    oldest_overdue_days: int
    invoice_count_valid_ar: int
    invoice_count_overdue: int
    health_score: float | None
    health_band: HealthBand | None
    risk_band: RiskBand
    score: float
    confidence: Confidence
    why_low: list[str]


@dataclass
class MoneyMove:
    """Per §4.3"""

    move_id: str
    type: MoveType
    client_id: str | None
    client_name: str | None
    currency: str
    amount: float
    invoice_ids: list[str]
    time_to_consequence_hours: float | None
    score: float
    confidence: Confidence
    why_low: list[str]
    why_surfaced: str
    primary_action: dict
    secondary_actions: list[dict]
    evidence_invoice_units: list[dict]


# ==============================================================================
# ENGINE
# ==============================================================================


class CashARPage12Engine:
    """
    Generates Cash/AR Command snapshot per Page 12 LOCKED SPEC.

    Scoring formula (§7.1):
    BaseScore = w_I*Impact + w_U*Urgency + w_C*Controllability + w_Q*Confidence
    Weights: w_I=0.40, w_U=0.30, w_C=0.15, w_Q=0.15
    """

    # Hard caps per §11.2
    MAX_MOVES = 7
    MAX_DEBTORS = 25
    MAX_INVALID_AR_TOP = 5
    MAX_MONEY_X_CHURN = 5
    MAX_MOVE_INVOICES = 5
    MAX_DRAWER_ACTIONS = 4
    MAX_DEBTOR_INVOICES = 10

    # Scoring weights per §7.1 (LOCKED)
    W_I = 0.40  # Impact
    W_U = 0.30  # Urgency
    W_C = 0.15  # Controllability
    W_Q = 0.15  # Confidence

    # Mode multipliers per §7.2 (LOCKED)
    MODE_MULTIPLIERS = {
        Mode.OPS_HEAD: {
            MoveType.PRE_DUE_SAVE: 1.15,
            MoveType.INVOICE_HYGIENE_FIX: 1.10,
        },
        Mode.CO_FOUNDER: {
            MoveType.SEVERE_COLLECTION_PUSH: 1.20,
            MoveType.CREDIT_RISK_ESCALATION: 1.25,
        },
        Mode.ARTIST: {
            # All money moves ×0.90
        },
    }
    ARTIST_MULTIPLIER = 0.90

    # Client tier thresholds per §6.6 (LOCKED)
    TIER_THRESHOLDS = {
        "A": 100000,
        "B": 50000,
        "C": 20000,
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
        self.finance_ar_coverage = True
        self.finance_ar_coverage_pct = 100.0
        self.finance_ar_clean_count = 0
        self.finance_ar_clean_amount = 0.0
        self.currency_mixed = False
        self.currencies = []
        self.delta_available = False

        # Cache
        self._invoices_cache: list[InvoiceUnit] = []
        self._debtors_cache: dict[str, DebtorUnit] = {}

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
    # TRUST & GATES (§3)
    # ==========================================================================

    def load_trust_state(self):
        """Load trust state from gates or compute."""
        try:
            from lib.gates import evaluate_gates

            gates = evaluate_gates()
            self.data_integrity = gates.get("data_integrity", True)
            self.finance_ar_coverage_pct = gates.get("finance_ar_coverage_pct", 100.0)
            self.finance_ar_coverage = self.finance_ar_coverage_pct >= 95
        except ImportError:
            # Gates module not available - use defaults (optional dependency)
            logger.debug("Gates module not available, using default trust state")
        except Exception as e:
            # Gates evaluation failed - this indicates a real problem
            logger.warning(f"Gates evaluation failed, using defaults: {e}")

    def _compute_trust_from_invoices(self, valid: list[InvoiceUnit], invalid: list[InvoiceUnit]):
        """Update trust metrics from invoice data."""
        self.finance_ar_clean_count = len(invalid)
        self.finance_ar_clean_amount = sum(i.amount for i in invalid)

        total_ar = len(valid) + len(invalid)
        if total_ar > 0:
            self.finance_ar_coverage_pct = (len(valid) / total_ar) * 100
            self.finance_ar_coverage = self.finance_ar_coverage_pct >= 95

        # Check currency mix
        currencies = set()
        for i in valid:
            if i.currency:
                currencies.add(i.currency)
        self.currencies = list(currencies)
        self.currency_mixed = len(currencies) > 1

    def _get_overall_confidence(self) -> tuple[Confidence, list[str]]:
        """Get overall page confidence."""
        why_low = []

        if not self.finance_ar_coverage:
            why_low.append(f"AR coverage {self.finance_ar_coverage_pct:.0f}% < 95%")
        if self.finance_ar_clean_count > 0:
            why_low.append(f"{self.finance_ar_clean_count} invalid invoices")
        if self.currency_mixed:
            why_low.append("Mixed currencies")

        if len(why_low) >= 2:
            return Confidence.LOW, why_low[:3]
        if len(why_low) == 1:
            return Confidence.MED, why_low
        return Confidence.HIGH, []

    # ==========================================================================
    # INVOICE BUILDING (§1, §4.1, §6)
    # ==========================================================================

    def build_invoices(self) -> tuple[list[InvoiceUnit], list[InvoiceUnit]]:
        """Build all InvoiceUnits, split into valid and invalid."""
        rows = self._query_all("""
            SELECT
                i.id, i.client_id, i.client_name, i.amount, i.currency,
                i.status, i.issue_date, i.due_date, i.payment_date, i.aging_bucket,
                c.name as client_name_lookup
            FROM invoices i
            LEFT JOIN clients c ON i.client_id = c.id
            WHERE i.status IN ('sent', 'overdue')
            AND i.payment_date IS NULL
        """)

        valid = []
        invalid = []

        for row in rows:
            invoice = self._build_invoice_unit(row)
            self._invoices_cache.append(invoice)

            if invoice.valid_ar:
                valid.append(invoice)
            else:
                invalid.append(invoice)

        return valid, invalid

    def _build_invoice_unit(self, row: dict) -> InvoiceUnit:
        """Build a single InvoiceUnit with validity flags per §6.1-6.3."""
        invoice_id = row.get("id")
        client_id = row.get("client_id")
        due_date = row.get("due_date")
        amount = row.get("amount", 0) or 0
        currency = row.get("currency", "AED") or "AED"

        # Determine validity per §1.2-1.3
        has_due_date = due_date is not None and due_date != ""
        has_client = client_id is not None and client_id != ""
        valid_ar = has_due_date and has_client

        # Invalid reason per §6.1
        if not has_due_date:
            invalid_reason = InvalidReason.MISSING_DUE
        elif not has_client:
            invalid_reason = InvalidReason.MISSING_CLIENT
        else:
            invalid_reason = InvalidReason.NONE

        # Compute days_overdue per §6.2
        days_overdue = None
        if has_due_date:
            try:
                due_dt = date.fromisoformat(due_date)
                diff = (self.today - due_dt).days
                days_overdue = max(0, diff) if diff > 0 else 0
            except (ValueError, TypeError) as e:
                # Invalid date format from source data - data quality issue
                logger.warning(f"Invoice has invalid due_date '{due_date}': {e}")

        # Assign aging bucket per §6.3 (only for valid AR)
        aging_bucket = None
        if valid_ar and days_overdue is not None:
            aging_bucket = self._compute_bucket(days_overdue)

        # Confidence per §6.7
        why_low = []
        if not valid_ar:
            if not has_due_date:
                why_low.append("invoice missing due_date")
            if not has_client:
                why_low.append("invoice missing client_id")
            confidence = Confidence.LOW
        elif not row.get("client_name") and not row.get("client_name_lookup"):
            why_low.append("client record missing name")
            confidence = Confidence.MED
        else:
            confidence = Confidence.HIGH

        # Get client name
        client_name = row.get("client_name_lookup") or row.get("client_name")

        return InvoiceUnit(
            invoice_id=invoice_id,
            client_id=client_id,
            client_name=client_name,
            amount=amount,
            currency=currency,
            status=row.get("status", "sent"),
            issue_date=row.get("issue_date"),
            due_date=due_date,
            days_overdue=days_overdue,
            aging_bucket=aging_bucket,
            valid_ar=valid_ar,
            invalid_reason=invalid_reason,
            confidence=confidence,
            why_low=why_low,
        )

    def _compute_bucket(self, days_overdue: int) -> str:
        """Compute aging bucket per §1.4."""
        if days_overdue <= 0:
            return AgingBucket.CURRENT.value
        if days_overdue <= 30:
            return AgingBucket.DAYS_1_30.value
        if days_overdue <= 60:
            return AgingBucket.DAYS_31_60.value
        if days_overdue <= 90:
            return AgingBucket.DAYS_61_90.value
        return AgingBucket.DAYS_90_PLUS.value

    # ==========================================================================
    # TILES (§5 Zone B)
    # ==========================================================================

    def build_tiles(self, valid: list[InvoiceUnit], invalid: list[InvoiceUnit]) -> dict:
        """Build status tiles per Zone B."""
        # Valid AR by currency
        valid_by_currency = {}
        for i in valid:
            curr = i.currency or "AED"
            valid_by_currency[curr] = valid_by_currency.get(curr, 0) + i.amount

        # Severe AR (61+) by currency
        severe_by_currency = {}
        for i in valid:
            if i.aging_bucket in [
                AgingBucket.DAYS_61_90.value,
                AgingBucket.DAYS_90_PLUS.value,
            ]:
                curr = i.currency or "AED"
                severe_by_currency[curr] = severe_by_currency.get(curr, 0) + i.amount

        # Severe as % of valid
        severe_pct = {}
        for curr, severe in severe_by_currency.items():
            total = valid_by_currency.get(curr, 1)
            severe_pct[curr] = (severe / total) * 100 if total > 0 else 0

        # Invalid AR by reason
        invalid_by_reason = {
            InvalidReason.MISSING_DUE.value: {"count": 0, "amount_by_currency": {}},
            InvalidReason.MISSING_CLIENT.value: {"count": 0, "amount_by_currency": {}},
        }
        for i in invalid:
            reason = i.invalid_reason.value
            if reason in invalid_by_reason:
                invalid_by_reason[reason]["count"] += 1
                curr = i.currency or "AED"
                invalid_by_reason[reason]["amount_by_currency"][curr] = (
                    invalid_by_reason[reason]["amount_by_currency"].get(curr, 0) + i.amount
                )

        # Next 7 days at risk (current invoices due within 7 days)
        next_7d = {}
        for i in valid:
            if i.aging_bucket == AgingBucket.CURRENT.value and i.due_date:
                try:
                    due_dt = date.fromisoformat(i.due_date)
                    days_until = (due_dt - self.today).days
                    if 0 <= days_until <= 7:
                        curr = i.currency or "AED"
                        next_7d[curr] = next_7d.get(curr, 0) + i.amount
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse due_date for 7-day risk calc: {e}")

        return {
            "valid_ar": {"by_currency": valid_by_currency},
            "severe_ar": {
                "by_currency": severe_by_currency,
                "pct_of_valid": severe_pct,
            },
            "invalid_ar": {
                "count": len(invalid),
                "by_reason": invalid_by_reason,
            },
            "next_7d_at_risk": {"by_currency": next_7d},
        }

    # ==========================================================================
    # WATERFALL (§5 Zone E)
    # ==========================================================================

    def build_waterfall(self, valid: list[InvoiceUnit]) -> dict:
        """Build aging waterfall per currency."""
        waterfall = {}

        for i in valid:
            curr = i.currency or "AED"
            if curr not in waterfall:
                waterfall[curr] = {
                    "current": 0.0,
                    "1-30": 0.0,
                    "31-60": 0.0,
                    "61-90": 0.0,
                    "90+": 0.0,
                }

            bucket = i.aging_bucket
            if bucket == AgingBucket.CURRENT.value:
                waterfall[curr]["current"] += i.amount
            elif bucket == AgingBucket.DAYS_1_30.value:
                waterfall[curr]["1-30"] += i.amount
            elif bucket == AgingBucket.DAYS_31_60.value:
                waterfall[curr]["31-60"] += i.amount
            elif bucket == AgingBucket.DAYS_61_90.value:
                waterfall[curr]["61-90"] += i.amount
            elif bucket == AgingBucket.DAYS_90_PLUS.value:
                waterfall[curr]["90+"] += i.amount

        return {"by_currency": waterfall}

    # ==========================================================================
    # DEBTORS (§4.2, §5 Zone D)
    # ==========================================================================

    def build_debtors(self, valid: list[InvoiceUnit]) -> list[DebtorUnit]:
        """Build DebtorUnits (client rollups) per §4.2."""
        # Group by client
        by_client = {}
        for i in valid:
            cid = i.client_id
            if not cid:
                continue
            if cid not in by_client:
                by_client[cid] = []
            by_client[cid].append(i)

        debtors = []
        for client_id, invoices in by_client.items():
            debtor = self._build_debtor_unit(client_id, invoices)
            if debtor:
                debtors.append(debtor)
                self._debtors_cache[client_id] = debtor

        # Rank by risk and amount
        debtors.sort(
            key=lambda d: (
                0 if d.risk_band == RiskBand.HIGH else 1 if d.risk_band == RiskBand.MED else 2,
                -d.total_valid_ar,
            )
        )

        return debtors[: self.MAX_DEBTORS]

    def _build_debtor_unit(self, client_id: str, invoices: list[InvoiceUnit]) -> DebtorUnit | None:
        """Build a single DebtorUnit."""
        if not invoices:
            return None

        # Get client info
        client = self._query_one("SELECT name, tier FROM clients WHERE id = ?", (client_id,))
        client_name = client.get("name", "Unknown") if client else "Unknown"
        tier = client.get("tier", "C") if client else "C"

        # Get health if available
        health_score = None
        health_band = None
        # Try to get from client360 cache or compute
        # For now, health is optional

        # Compute totals
        currency = invoices[0].currency or "AED"
        total_valid_ar = sum(i.amount for i in invoices)

        severe_ar = sum(
            i.amount
            for i in invoices
            if i.aging_bucket in [AgingBucket.DAYS_61_90.value, AgingBucket.DAYS_90_PLUS.value]
        )

        # Next 7 days at risk
        next_due_7d = 0.0
        for i in invoices:
            if i.aging_bucket == AgingBucket.CURRENT.value and i.due_date:
                try:
                    due_dt = date.fromisoformat(i.due_date)
                    days_until = (due_dt - self.today).days
                    if 0 <= days_until <= 7:
                        next_due_7d += i.amount
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse due_date for debtor 7-day calc: {e}")

        # Oldest overdue
        overdue_invoices = [i for i in invoices if i.days_overdue and i.days_overdue > 0]
        oldest_overdue_days = max((i.days_overdue for i in overdue_invoices), default=0)

        # Compute risk band per §6.5
        risk_band = self._compute_debtor_risk_band(
            severe_ar, total_valid_ar, oldest_overdue_days, health_band, tier
        )

        # Compute score for ranking
        score = self._compute_debtor_score(
            severe_ar, total_valid_ar, oldest_overdue_days, next_due_7d, tier
        )

        # Confidence
        why_low = []
        if any(i.confidence == Confidence.LOW for i in invoices):
            why_low.append("Some invoices have low confidence")
        confidence = Confidence.LOW if why_low else Confidence.HIGH

        return DebtorUnit(
            client_id=client_id,
            client_name=client_name,
            currency=currency,
            total_valid_ar=total_valid_ar,
            severe_ar=severe_ar,
            next_due_amount_7d=next_due_7d,
            oldest_overdue_days=oldest_overdue_days,
            invoice_count_valid_ar=len(invoices),
            invoice_count_overdue=len(overdue_invoices),
            health_score=health_score,
            health_band=health_band,
            risk_band=risk_band,
            score=score,
            confidence=confidence,
            why_low=why_low,
        )

    def _compute_debtor_risk_band(
        self,
        severe_ar: float,
        total_valid_ar: float,
        oldest_overdue_days: int,
        health_band: HealthBand | None,
        tier: str,
    ) -> RiskBand:
        """Compute debtor risk band per §6.5."""
        # HIGH conditions
        if severe_ar > 0 and total_valid_ar > 0 and severe_ar / total_valid_ar >= 0.35:
            return RiskBand.HIGH
        if oldest_overdue_days >= 60:
            return RiskBand.HIGH
        if health_band == HealthBand.RED:
            threshold = self.TIER_THRESHOLDS.get(tier, 20000)
            if total_valid_ar >= threshold:
                return RiskBand.HIGH

        # MED conditions
        if severe_ar > 0:
            return RiskBand.MED
        if 30 <= oldest_overdue_days < 60:
            return RiskBand.MED

        return RiskBand.LOW

    def _compute_debtor_score(
        self,
        severe_ar: float,
        total_valid_ar: float,
        oldest_overdue_days: int,
        next_due_7d: float,
        tier: str,
    ) -> float:
        """Compute debtor score for ranking."""
        score = 0.0

        # Severe AR component
        if total_valid_ar > 0:
            score += (severe_ar / total_valid_ar) * 0.4

        # Oldest overdue component
        if oldest_overdue_days >= 90:
            score += 0.3
        elif oldest_overdue_days >= 60:
            score += 0.2
        elif oldest_overdue_days >= 30:
            score += 0.1

        # Total AR magnitude (normalized by tier threshold)
        threshold = self.TIER_THRESHOLDS.get(tier, 20000)
        score += min(total_valid_ar / threshold, 1.0) * 0.2

        # Next 7d risk
        if next_due_7d > 0:
            score += min(next_due_7d / threshold, 1.0) * 0.1

        return min(1.0, score)

    # ==========================================================================
    # MOVES (§4.3, §5 Zone C)
    # ==========================================================================

    def build_moves(
        self,
        valid: list[InvoiceUnit],
        invalid: list[InvoiceUnit],
        debtors: list[DebtorUnit],
    ) -> list[MoneyMove]:
        """Build MoneyMoves per §4.3 (max 7)."""
        moves = []

        # Severe collection push (61+ buckets)
        severe_invoices = [
            i
            for i in valid
            if i.aging_bucket in [AgingBucket.DAYS_61_90.value, AgingBucket.DAYS_90_PLUS.value]
        ]
        if severe_invoices:
            # Group by client
            by_client = {}
            for i in severe_invoices:
                cid = i.client_id or "unlinked"
                if cid not in by_client:
                    by_client[cid] = []
                by_client[cid].append(i)

            for cid, invs in sorted(by_client.items(), key=lambda x: -sum(i.amount for i in x[1]))[
                :3
            ]:
                move = self._create_move(
                    MoveType.SEVERE_COLLECTION_PUSH,
                    invs[: self.MAX_MOVE_INVOICES],
                    cid if cid != "unlinked" else None,
                )
                if move:
                    moves.append(move)

        # Pre-due save (current invoices due in 7 days)
        predue_invoices = []
        for i in valid:
            if i.aging_bucket == AgingBucket.CURRENT.value and i.due_date:
                try:
                    due_dt = date.fromisoformat(i.due_date)
                    days_until = (due_dt - self.today).days
                    if 0 <= days_until <= 7:
                        predue_invoices.append(i)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse due_date for predue calc: {e}")

        if predue_invoices:
            by_client = {}
            for i in predue_invoices:
                cid = i.client_id or "unlinked"
                if cid not in by_client:
                    by_client[cid] = []
                by_client[cid].append(i)

            for cid, invs in sorted(by_client.items(), key=lambda x: -sum(i.amount for i in x[1]))[
                :2
            ]:
                move = self._create_move(
                    MoveType.PRE_DUE_SAVE,
                    invs[: self.MAX_MOVE_INVOICES],
                    cid if cid != "unlinked" else None,
                )
                if move:
                    moves.append(move)

        # Invoice hygiene fix (invalid AR)
        if invalid:
            move = self._create_move(
                MoveType.INVOICE_HYGIENE_FIX, invalid[: self.MAX_MOVE_INVOICES], None
            )
            if move:
                moves.append(move)

        # Credit risk escalation (high AR + low health)
        for d in debtors[:5]:
            if d.risk_band == RiskBand.HIGH and d.health_band == HealthBand.RED:
                invs = [i for i in valid if i.client_id == d.client_id][: self.MAX_MOVE_INVOICES]
                move = self._create_move(MoveType.CREDIT_RISK_ESCALATION, invs, d.client_id)
                if move:
                    moves.append(move)

        # Score and rank moves
        for m in moves:
            base_score = self._score_move(m)
            # Apply mode multipliers
            multiplier = 1.0
            if self.mode == Mode.ARTIST:
                multiplier = self.ARTIST_MULTIPLIER
            else:
                multiplier = self.MODE_MULTIPLIERS.get(self.mode, {}).get(m.type, 1.0)
            m.score = base_score * multiplier

        # Sort by score and filter by horizon eligibility
        moves.sort(key=lambda m: m.score, reverse=True)
        eligible = [m for m in moves if self._is_move_eligible(m)]

        return eligible[: self.MAX_MOVES]

    def _create_move(
        self, move_type: MoveType, invoices: list[InvoiceUnit], client_id: str | None
    ) -> MoneyMove | None:
        """Create a MoneyMove from invoices."""
        if not invoices:
            return None

        # Get client name
        client_name = None
        if client_id:
            client = self._query_one("SELECT name FROM clients WHERE id = ?", (client_id,))
            client_name = client.get("name") if client else None

        # Compute totals
        amount = sum(i.amount for i in invoices)
        currency = invoices[0].currency or "AED"

        # Time to consequence per §6.4
        ttc = self._compute_time_to_consequence(invoices)

        # Why surfaced
        why_surfaced = self._generate_why_surfaced(move_type, invoices, amount, currency)

        # Confidence
        why_low = []
        if any(not i.valid_ar for i in invoices):
            why_low.append("Contains invalid invoices")
        if not client_id:
            why_low.append("Client unlinked")
        confidence = Confidence.LOW if why_low else Confidence.HIGH

        # Actions
        primary_action = self._generate_primary_action(move_type, client_id, invoices)
        secondary_actions = self._generate_secondary_actions(move_type, client_id, invoices)

        # Evidence
        evidence = [
            {
                "invoice_id": i.invoice_id,
                "amount": i.amount,
                "due_date": i.due_date,
                "aging_bucket": i.aging_bucket,
                "days_overdue": i.days_overdue,
                "valid_ar": i.valid_ar,
                "invalid_reason": i.invalid_reason.value,
            }
            for i in invoices[: self.MAX_MOVE_INVOICES]
        ]

        return MoneyMove(
            move_id=f"move-{move_type.value.lower()}-{client_id or 'unlinked'}",
            type=move_type,
            client_id=client_id,
            client_name=client_name,
            currency=currency,
            amount=amount,
            invoice_ids=[i.invoice_id for i in invoices],
            time_to_consequence_hours=ttc,
            score=0.0,  # Computed later
            confidence=confidence,
            why_low=why_low,
            why_surfaced=why_surfaced,
            primary_action=primary_action,
            secondary_actions=secondary_actions,
            evidence_invoice_units=evidence,
        )

    def _compute_time_to_consequence(self, invoices: list[InvoiceUnit]) -> float | None:
        """Compute time to consequence per §6.4."""
        min_hours = None

        for i in invoices:
            if i.due_date:
                try:
                    due_dt = datetime.fromisoformat(i.due_date + "T23:59:59")
                    hours = (due_dt - self.now).total_seconds() / 3600
                    if min_hours is None or hours < min_hours:
                        min_hours = hours
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse due_date for TTC calc: {e}")

        return round(min_hours, 1) if min_hours is not None else None

    def _generate_why_surfaced(
        self,
        move_type: MoveType,
        invoices: list[InvoiceUnit],
        amount: float,
        currency: str,
    ) -> str:
        """Generate why_surfaced line."""
        if move_type == MoveType.SEVERE_COLLECTION_PUSH:
            days = max((i.days_overdue or 0 for i in invoices), default=0)
            return f"Severe AR: {currency} {amount:,.0f} overdue {days}+ days"
        if move_type == MoveType.PRE_DUE_SAVE:
            return f"Pre-due: {currency} {amount:,.0f} due within 7 days"
        if move_type == MoveType.INVOICE_HYGIENE_FIX:
            return f"Invalid AR: {len(invoices)} invoices need fixing"
        if move_type == MoveType.CREDIT_RISK_ESCALATION:
            return f"Credit risk: {currency} {amount:,.0f} + client health concerns"
        return f"Money move: {currency} {amount:,.0f}"

    def _generate_primary_action(
        self, move_type: MoveType, client_id: str | None, invoices: list[InvoiceUnit]
    ) -> dict:
        """Generate primary action for move."""
        inv_ids = [i.invoice_id for i in invoices[:3]]

        if move_type == MoveType.SEVERE_COLLECTION_PUSH:
            return {
                "risk": "propose",
                "label": "Draft collection email",
                "idempotency_key": f"action-collect-{client_id or 'unlinked'}",
                "payload": {"client_id": client_id, "invoice_ids": inv_ids},
                "why": "Escalate overdue collection",
            }
        if move_type == MoveType.PRE_DUE_SAVE:
            return {
                "risk": "propose",
                "label": "Send payment reminder",
                "idempotency_key": f"action-remind-{client_id or 'unlinked'}",
                "payload": {"client_id": client_id, "invoice_ids": inv_ids},
                "why": "Prevent aging",
            }
        if move_type == MoveType.INVOICE_HYGIENE_FIX:
            return {
                "risk": "auto",
                "label": "Fix invoice metadata",
                "idempotency_key": f"action-fix-{inv_ids[0] if inv_ids else 'batch'}",
                "payload": {"invoice_ids": inv_ids},
                "why": "Complete missing data",
            }
        if move_type == MoveType.CREDIT_RISK_ESCALATION:
            return {
                "risk": "approval",
                "label": "Escalate credit risk",
                "idempotency_key": f"action-escalate-{client_id}",
                "payload": {"client_id": client_id, "invoice_ids": inv_ids},
                "why": "High AR + relationship risk",
            }
        return {
            "risk": "auto",
            "label": "Review invoices",
            "idempotency_key": f"action-review-{inv_ids[0] if inv_ids else 'batch'}",
            "payload": {"invoice_ids": inv_ids},
            "why": "Triage needed",
        }

    def _generate_secondary_actions(
        self, move_type: MoveType, client_id: str | None, invoices: list[InvoiceUnit]
    ) -> list[dict]:
        """Generate secondary actions."""
        actions = []

        actions.append(
            {
                "risk": "auto",
                "label": "Create follow-up task",
                "idempotency_key": f"action-task-{client_id or 'batch'}",
                "payload": {"client_id": client_id},
                "why": "Track internally",
            }
        )

        if client_id:
            actions.append(
                {
                    "risk": "propose",
                    "label": "Draft statement",
                    "idempotency_key": f"action-statement-{client_id}",
                    "payload": {"client_id": client_id},
                    "why": "Send account summary",
                }
            )

        return actions[:2]

    def _score_move(self, move: MoneyMove) -> float:
        """Score a move per §7.1."""
        # Impact (0-1)
        threshold = self.TIER_THRESHOLDS.get("C", 20000)  # Default threshold
        impact = min(move.amount / threshold, 1.0) * 0.7
        if move.type == MoveType.SEVERE_COLLECTION_PUSH:
            impact += 0.3
        elif move.type == MoveType.CREDIT_RISK_ESCALATION:
            impact += 0.2
        impact = min(1.0, impact)

        # Urgency (0-1)
        urgency = 0.0
        if move.time_to_consequence_hours is not None:
            ttc = move.time_to_consequence_hours
            if ttc <= 0:  # Overdue
                urgency = 1.0
            elif ttc <= 24:
                urgency = 0.8
            elif ttc <= 72:
                urgency = 0.6
            elif ttc <= 168:
                urgency = 0.4
            else:
                urgency = 0.2

        # Controllability (0-1)
        controllability = 0.7
        if move.client_id:
            controllability = 0.9
        if move.type == MoveType.INVOICE_HYGIENE_FIX:
            controllability = 0.95  # Easy to fix internally

        # Confidence
        conf_factor = {
            Confidence.HIGH: 1.0,
            Confidence.MED: 0.8,
            Confidence.LOW: 0.6,
        }.get(move.confidence, 0.7)

        return (
            self.W_I * impact
            + self.W_U * urgency
            + self.W_C * controllability
            + self.W_Q * conf_factor
        )

    def _is_move_eligible(self, move: MoneyMove) -> bool:
        """Check move eligibility per §8."""
        ttc = move.time_to_consequence_hours

        if self.horizon == Horizon.NOW:
            # Severe or due within 12h
            if move.type == MoveType.SEVERE_COLLECTION_PUSH:
                return True
            return ttc is not None and ttc <= 12
        if self.horizon == Horizon.TODAY:
            # Due today or 31-60+
            if move.type in [
                MoveType.SEVERE_COLLECTION_PUSH,
                MoveType.INVOICE_HYGIENE_FIX,
            ]:
                return True
            return ttc is not None and ttc <= 24
        # THIS WEEK
        return True

    # ==========================================================================
    # LADDERS (§5 Zone E)
    # ==========================================================================

    def build_ladders(self, invalid: list[InvoiceUnit], debtors: list[DebtorUnit]) -> dict:
        """Build right column ladders."""
        return {
            "invalid_ar_top": self._build_invalid_ladder(invalid),
            "money_x_churn": self._build_money_churn_ladder(debtors),
        }

    def _build_invalid_ladder(self, invalid: list[InvoiceUnit]) -> list[dict]:
        """Build invalid AR ladder (max 5)."""
        # Sort by amount desc
        invalid.sort(key=lambda i: -i.amount)

        return [
            {
                "invoice_id": i.invoice_id,
                "amount": i.amount,
                "currency": i.currency,
                "invalid_reason": i.invalid_reason.value,
                "primary_action": {
                    "risk": "auto",
                    "label": "Fix invoice",
                    "idempotency_key": f"action-fix-{i.invoice_id}",
                    "payload": {"invoice_id": i.invoice_id},
                    "why": f"Missing {i.invalid_reason.value.lower().replace('_', ' ')}",
                },
            }
            for i in invalid[: self.MAX_INVALID_AR_TOP]
        ]

    def _build_money_churn_ladder(self, debtors: list[DebtorUnit]) -> list[dict]:
        """Build money × churn ladder (max 5)."""
        # Only include debtors with health data and high risk
        candidates = [
            d for d in debtors if d.health_band == HealthBand.RED and d.risk_band == RiskBand.HIGH
        ]

        return [
            {
                "client_id": d.client_id,
                "client_name": d.client_name,
                "currency": d.currency,
                "total_valid_ar": d.total_valid_ar,
                "health_band": d.health_band.value if d.health_band else None,
                "why": f"High AR ({d.currency} {d.total_valid_ar:,.0f}) + RED health",
            }
            for d in candidates[: self.MAX_MONEY_X_CHURN]
        ]

    # ==========================================================================
    # DRAWER (§9)
    # ==========================================================================

    def build_move_room(self, move: MoneyMove) -> dict:
        """Build MoneyMove room drawer per §9.1."""
        # Get client context
        client_context = {}
        if move.client_id:
            client = self._query_one(
                """
                SELECT id, name, tier FROM clients WHERE id = ?
            """,
                (move.client_id,),
            )
            if client:
                client_context = {
                    "client_id": client["id"],
                    "name": client["name"],
                    "tier": client.get("tier"),
                    "health": "unavailable",  # Would need client360 integration
                }

        # Summary
        summary = f"{move.type.value.replace('_', ' ').title()}: {move.currency} {move.amount:,.0f}"
        if move.client_name:
            summary += f" from {move.client_name}"
        summary += f". {move.why_surfaced}"

        return {
            "summary": summary,
            "invoices": move.evidence_invoice_units,
            "client_context": client_context,
            "evidence": move.why_surfaced,
            "actions": [move.primary_action] + move.secondary_actions,
            "reason": f"{self.horizon.value} | {move.type.value} | driver=Cash",
        }

    def build_debtor_room(self, client_id: str) -> dict | None:
        """Build Debtor room drawer per §9.2."""
        debtor = self._debtors_cache.get(client_id)
        if not debtor:
            return None

        # Get invoices for this client
        invoices = [i for i in self._invoices_cache if i.client_id == client_id]

        # AR breakdown
        breakdown = {
            "current": sum(
                i.amount for i in invoices if i.aging_bucket == AgingBucket.CURRENT.value
            ),
            "1-30": sum(
                i.amount for i in invoices if i.aging_bucket == AgingBucket.DAYS_1_30.value
            ),
            "31-60": sum(
                i.amount for i in invoices if i.aging_bucket == AgingBucket.DAYS_31_60.value
            ),
            "61-90": sum(
                i.amount for i in invoices if i.aging_bucket == AgingBucket.DAYS_61_90.value
            ),
            "90+": sum(
                i.amount for i in invoices if i.aging_bucket == AgingBucket.DAYS_90_PLUS.value
            ),
        }

        # Top invoices (collapsed by default)
        top_invoices = sorted(invoices, key=lambda i: -i.amount)[: self.MAX_DEBTOR_INVOICES]

        # Invalid invoices
        invalid = [i for i in invoices if not i.valid_ar]

        # Summary
        summary = f"{debtor.client_name}: {debtor.currency} {debtor.total_valid_ar:,.0f} total AR. "
        if debtor.severe_ar > 0:
            summary += f"Severe: {debtor.currency} {debtor.severe_ar:,.0f}. "
        if debtor.oldest_overdue_days > 0:
            summary += f"Oldest overdue: {debtor.oldest_overdue_days} days."

        # Actions
        actions = [
            {
                "risk": "propose",
                "label": "Send statement",
                "idempotency_key": f"action-statement-{client_id}",
                "payload": {"client_id": client_id},
                "why": "Account summary",
            },
            {
                "risk": "auto",
                "label": "Create follow-up task",
                "idempotency_key": f"action-task-{client_id}",
                "payload": {"client_id": client_id},
                "why": "Track collection",
            },
        ]

        if debtor.severe_ar > 0:
            actions.insert(
                0,
                {
                    "risk": "propose",
                    "label": "Draft escalation",
                    "idempotency_key": f"action-escalate-{client_id}",
                    "payload": {"client_id": client_id},
                    "why": "Severe aging",
                },
            )

        return {
            "summary": summary,
            "breakdown": breakdown,
            "top_invoices": [
                {
                    "invoice_id": i.invoice_id,
                    "amount": i.amount,
                    "due_date": i.due_date,
                    "aging_bucket": i.aging_bucket,
                    "days_overdue": i.days_overdue,
                }
                for i in top_invoices
            ],
            "invalid": [
                {
                    "invoice_id": i.invoice_id,
                    "amount": i.amount,
                    "invalid_reason": i.invalid_reason.value,
                }
                for i in invalid[:5]
            ],
            "coupling": {
                "health_available": debtor.health_band is not None,
                "health_band": debtor.health_band.value if debtor.health_band else None,
            },
            "actions": actions[: self.MAX_DRAWER_ACTIONS],
            "reason": f"{self.horizon.value} | risk={debtor.risk_band.value} | AR={debtor.currency} {debtor.total_valid_ar:,.0f}",
        }

    def build_invoice_room(self, invoice_id: str) -> dict | None:
        """Build Invoice room drawer per §9.3."""
        invoice = next((i for i in self._invoices_cache if i.invoice_id == invoice_id), None)
        if not invoice:
            return None

        summary = f"Invoice {invoice_id}: {invoice.currency} {invoice.amount:,.0f}"
        if invoice.client_name:
            summary += f" from {invoice.client_name}"
        if invoice.valid_ar:
            summary += (
                f". {invoice.aging_bucket or 'current'}, {invoice.days_overdue or 0} days overdue."
            )
        else:
            summary += f". Invalid: {invoice.invalid_reason.value}"

        actions = []
        if not invoice.valid_ar:
            actions.append(
                {
                    "risk": "auto",
                    "label": "Fix metadata",
                    "idempotency_key": f"action-fix-{invoice_id}",
                    "payload": {"invoice_id": invoice_id},
                    "why": f"Missing {invoice.invalid_reason.value.lower().replace('_', ' ')}",
                }
            )
        else:
            actions.append(
                {
                    "risk": "propose",
                    "label": "Send reminder",
                    "idempotency_key": f"action-remind-{invoice_id}",
                    "payload": {"invoice_id": invoice_id},
                    "why": "Follow up on payment",
                }
            )

        return {
            "summary": summary,
            "fields": {
                "invoice_id": invoice.invoice_id,
                "client_id": invoice.client_id,
                "client_name": invoice.client_name,
                "amount": invoice.amount,
                "currency": invoice.currency,
                "status": invoice.status,
                "issue_date": invoice.issue_date,
                "due_date": invoice.due_date,
                "days_overdue": invoice.days_overdue,
                "aging_bucket": invoice.aging_bucket,
            },
            "validity": {
                "valid_ar": invoice.valid_ar,
                "invalid_reason": invoice.invalid_reason.value,
                "what_to_fix": invoice.why_low,
            },
            "actions": actions[: self.MAX_DRAWER_ACTIONS],
            "reason": f"Invoice | valid={invoice.valid_ar} | {invoice.aging_bucket or 'N/A'}",
        }

    # ==========================================================================
    # MAIN GENERATE (§11)
    # ==========================================================================

    def generate(self) -> dict:
        """Generate complete cash_ar snapshot per §11."""
        self.load_trust_state()

        # Build invoices
        valid, invalid = self.build_invoices()

        # Update trust from invoice data
        self._compute_trust_from_invoices(valid, invalid)

        # Build tiles
        tiles = self.build_tiles(valid, invalid)

        # Build waterfall
        waterfall = self.build_waterfall(valid)

        # Build debtors
        debtors = self.build_debtors(valid)

        # Build moves
        moves = self.build_moves(valid, invalid, debtors)

        # Build ladders
        ladders = self.build_ladders(invalid, debtors)

        # Build drawers
        drawer_moves = {}
        for m in moves:
            room = self.build_move_room(m)
            drawer_moves[f"move:{m.move_id}"] = room

        drawer_debtors = {}
        for d in debtors[:10]:
            room = self.build_debtor_room(d.client_id)
            if room:
                drawer_debtors[f"client:{d.client_id}"] = room

        drawer_invoices = {}
        for inv in invalid[:5]:
            room = self.build_invoice_room(inv.invoice_id)
            if room:
                drawer_invoices[f"invoice:{inv.invoice_id}"] = room

        # Get overall confidence
        confidence, why_low = self._get_overall_confidence()

        return {
            "meta": {
                "generated_at": self.now.isoformat(),
                "mode": self.mode.value,
                "horizon": self.horizon.value,
                "trust": {
                    "data_integrity": self.data_integrity,
                    "finance_ar_coverage": self.finance_ar_coverage,
                    "finance_ar_clean_count": self.finance_ar_clean_count,
                    "finance_ar_clean_amount": self.finance_ar_clean_amount,
                    "currency_mixed": self.currency_mixed,
                    "currencies": self.currencies,
                    "delta_available": self.delta_available,
                    "confidence": confidence.value,
                    "why_low": why_low,
                },
            },
            "tiles": tiles,
            "waterfall": waterfall,
            "moves": [
                {
                    "move_id": m.move_id,
                    "type": m.type.value,
                    "client_id": m.client_id,
                    "client_name": m.client_name,
                    "currency": m.currency,
                    "amount": m.amount,
                    "invoice_ids": m.invoice_ids[: self.MAX_MOVE_INVOICES],
                    "time_to_consequence_hours": m.time_to_consequence_hours,
                    "score": round(m.score, 3),
                    "confidence": m.confidence.value,
                    "why_low": m.why_low,
                    "why_surfaced": m.why_surfaced,
                    "primary_action": m.primary_action,
                    "secondary_actions": m.secondary_actions,
                    "evidence_invoice_units": m.evidence_invoice_units,
                }
                for m in moves
            ],
            "debtors": [
                {
                    "client_id": d.client_id,
                    "client_name": d.client_name,
                    "currency": d.currency,
                    "total_valid_ar": d.total_valid_ar,
                    "severe_ar": d.severe_ar,
                    "next_due_amount_7d": d.next_due_amount_7d,
                    "oldest_overdue_days": d.oldest_overdue_days,
                    "invoice_count_valid_ar": d.invoice_count_valid_ar,
                    "invoice_count_overdue": d.invoice_count_overdue,
                    "health_score": d.health_score,
                    "health_band": d.health_band.value if d.health_band else None,
                    "risk_band": d.risk_band.value,
                    "score": round(d.score, 3),
                    "primary_action": {
                        "risk": "propose",
                        "label": "View AR",
                        "idempotency_key": f"action-view-{d.client_id}",
                        "payload": {"client_id": d.client_id},
                        "why": "Review account",
                    },
                }
                for d in debtors
            ],
            "ladders": ladders,
            "drawer": {
                "moves": drawer_moves,
                "debtors": drawer_debtors,
                "invoices": drawer_invoices,
            },
        }


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import json

    engine = CashARPage12Engine()
    snapshot = engine.generate()
    logger.info(json.dumps(snapshot, indent=2, default=str))
