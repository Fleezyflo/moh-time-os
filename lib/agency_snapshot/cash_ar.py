"""
Cash/AR Command Engine - Page 3 locked spec implementation.

Produces agency_snapshot.cash_ar per locked schema.

Key contracts (locked):
- Valid AR only drives metrics; invalid AR quarantined
- Cash Risk Score formula: 55% severe + 25% moderate + 10% overdue + 10% oldest
- Aging buckets: current, 1-30, 31-60, 61-90, 90+
- Portfolio max 12 (expand 30), invoices max 25, actions max 7/10
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from lib import paths

from .scoring import Horizon, Mode

logger = logging.getLogger(__name__)

DB_PATH = paths.db_path()


class RiskBand(Enum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class AgingBucket(Enum):
    CURRENT = "current"
    D1_30 = "1-30"
    D31_60 = "31-60"
    D61_90 = "61-90"
    D90_PLUS = "90+"


class ActionRiskLevel(Enum):
    AUTO = "auto"
    PROPOSE = "propose"
    APPROVAL = "approval"


@dataclass
class Invoice:
    invoice_id: str
    external_id: str | None
    amount: float
    currency: str
    issue_date: str | None
    due_date: str | None
    days_overdue: int
    aging_bucket: str | None
    status: str
    client_id: str | None
    client_name: str | None
    is_valid: bool = True
    invalid_reason: str | None = None


@dataclass
class ClientARData:
    client_id: str
    name: str
    tier: str
    valid_ar_total: float
    overdue_total: float
    bucket_totals: dict[str, float]
    worst_bucket: str
    oldest_days_overdue: int
    cash_risk_score: float
    risk_band: str
    trend: str | None
    confidence: str
    why_low: list[str]
    invoices: list[Invoice] = field(default_factory=list)
    invalid_items: list[dict] = field(default_factory=list)
    comms_context: list[dict] = field(default_factory=list)
    recent_change: list[dict] = field(default_factory=list)


@dataclass
class ARAction:
    action_id: str
    risk_level: str
    label: str
    entity_type: str
    entity_id: str
    idempotency_key: str
    payload: dict
    why: str


class CashAREngine:
    """
    Cash/AR Command Engine per Page 3 spec.

    Produces cash_ar snapshot section with:
    - Summary strip (valid AR, overdue, due soon, invalid excluded)
    - Risk waterfall (bucket breakdown)
    - Client portfolio (ranked tiles)
    - Selected client detail (AR room)
    - Global actions
    """

    # Hard caps per §2 (locked)
    MAX_PORTFOLIO_DEFAULT = 12
    MAX_PORTFOLIO_EXPANDED = 30
    MAX_INVOICES = 25
    MAX_INVALID = 10
    MAX_COMMS = 5
    MAX_RECENT_CHANGE = 5
    MAX_CLIENT_ACTIONS = 7
    MAX_GLOBAL_ACTIONS = 10

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

        # Trust state (set externally)
        self.data_integrity = True
        self.finance_ar_coverage_pct = 100.0
        self.finance_ar_clean = True
        self.last_finance_sync_at: str | None = None
        self.client_coverage_pct = 100.0

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

    def generate(self, selected_client_id: str | None = None, expanded: bool = False) -> dict:
        """
        Generate complete cash_ar section per §8 schema.

        Args:
            selected_client_id: Client to show in detail (defaults to top risk)
            expanded: Whether to show expanded portfolio (30 vs 12)
        """
        # Get all AR data
        all_invoices = self._get_all_ar_invoices()
        valid_invoices = [i for i in all_invoices if i.is_valid]
        invalid_invoices = [i for i in all_invoices if not i.is_valid]

        # Update trust metrics
        self._update_trust_metrics(all_invoices, invalid_invoices)

        # Build summary
        summary = self._build_summary(valid_invoices, invalid_invoices)

        # Build portfolio
        portfolio_limit = self.MAX_PORTFOLIO_EXPANDED if expanded else self.MAX_PORTFOLIO_DEFAULT
        portfolio = self._build_portfolio(valid_invoices, invalid_invoices, portfolio_limit)

        # Select client (default to highest risk)
        if not selected_client_id and portfolio:
            selected_client_id = portfolio[0].client_id

        selected_client = None
        if selected_client_id:
            selected_client = self._build_selected_client(
                selected_client_id, valid_invoices, invalid_invoices
            )

        # Build global actions
        global_actions = self._build_global_actions(valid_invoices, invalid_invoices, portfolio)

        return {
            "meta": {
                "generated_at": self.now.isoformat(),
                "mode": self.mode.value,
                "horizon": self.horizon.value,
                "trust": {
                    "data_integrity": self.data_integrity,
                    "finance_ar_coverage_pct": self.finance_ar_coverage_pct,
                    "finance_ar_clean": len(invalid_invoices) == 0,
                    "invalid_ar_count": len(invalid_invoices),
                    "invalid_ar_amount": sum(i.amount for i in invalid_invoices),
                    "last_finance_sync_at": self.last_finance_sync_at,
                },
            },
            "summary": summary,
            "portfolio": [self._client_to_dict(c) for c in portfolio],
            "selected_client": self._selected_client_to_dict(selected_client)
            if selected_client
            else None,
            "global_actions": [self._action_to_dict(a) for a in global_actions],
        }

    def _get_all_ar_invoices(self) -> list[Invoice]:
        """Get all AR invoices (valid + invalid) per §4.1."""
        rows = self._query_all("""
            SELECT
                i.id as invoice_id,
                i.external_id,
                i.amount,
                COALESCE(i.currency, 'AED') as currency,
                i.issue_date,
                i.due_date,
                i.status,
                i.client_id,
                COALESCE(c.name, i.client_name) as client_name,
                i.aging_bucket
            FROM invoices i
            LEFT JOIN clients c ON c.id = i.client_id
            WHERE i.status IN ('sent', 'overdue')
            AND i.payment_date IS NULL
            ORDER BY i.due_date ASC
        """)

        invoices = []
        for row in rows:
            # Compute days overdue per §4.2
            days_overdue = 0
            aging_bucket = None
            is_valid = True
            invalid_reason = None

            if row.get("due_date"):
                try:
                    due = datetime.strptime(row["due_date"][:10], "%Y-%m-%d").date()
                    days_overdue = (self.today - due).days
                    aging_bucket = self._compute_bucket(days_overdue)
                except (ValueError, TypeError):
                    is_valid = False
                    invalid_reason = "invalid_due_date"
            else:
                is_valid = False
                invalid_reason = "missing_due_date"

            if not row.get("client_id"):
                is_valid = False
                invalid_reason = invalid_reason or "missing_client_id"

            invoices.append(
                Invoice(
                    invoice_id=row["invoice_id"],
                    external_id=row.get("external_id"),
                    amount=row.get("amount") or 0,
                    currency=row.get("currency", "AED"),
                    issue_date=row.get("issue_date"),
                    due_date=row.get("due_date"),
                    days_overdue=days_overdue,
                    aging_bucket=aging_bucket,
                    status=row.get("status", "sent"),
                    client_id=row.get("client_id"),
                    client_name=row.get("client_name"),
                    is_valid=is_valid,
                    invalid_reason=invalid_reason,
                )
            )

        return invoices

    def _compute_bucket(self, days_overdue: int) -> str:
        """Compute aging bucket per §4.2 (locked)."""
        if days_overdue <= 0:
            return "current"
        if days_overdue <= 30:
            return "1-30"
        if days_overdue <= 60:
            return "31-60"
        if days_overdue <= 90:
            return "61-90"
        return "90+"

    def _update_trust_metrics(self, all_invoices: list[Invoice], invalid: list[Invoice]):
        """Update trust metrics based on AR data."""
        total = len(all_invoices)
        valid = total - len(invalid)

        if total > 0:
            self.finance_ar_coverage_pct = (valid / total) * 100
            self.finance_ar_clean = len(invalid) == 0
        else:
            self.finance_ar_coverage_pct = 100.0
            self.finance_ar_clean = True

    def _build_summary(self, valid: list[Invoice], invalid: list[Invoice]) -> dict:
        """Build summary strip per §8.1."""
        # Compute totals
        valid_ar_total = sum(i.amount for i in valid)
        overdue_total = sum(i.amount for i in valid if i.days_overdue > 0)
        due_soon_total = self._compute_due_soon_total(valid)

        # Bucket totals
        bucket_totals = {
            "current": 0.0,
            "1-30": 0.0,
            "31-60": 0.0,
            "61-90": 0.0,
            "90+": 0.0,
        }
        for inv in valid:
            if inv.aging_bucket and inv.aging_bucket in bucket_totals:
                bucket_totals[inv.aging_bucket] += inv.amount

        # Risk band per §5.2
        risk_score = self._compute_portfolio_risk_score(valid)
        risk_band = self._score_to_band(risk_score)

        # Top driver sentence
        top_driver = self._compute_top_driver(valid, bucket_totals, overdue_total, valid_ar_total)

        return {
            "valid_ar_total": valid_ar_total,
            "overdue_total": overdue_total,
            "due_soon_total": due_soon_total,
            "bucket_totals": bucket_totals,
            "risk_band": risk_band,
            "top_driver_sentence": top_driver,
        }

    def _compute_due_soon_total(self, valid: list[Invoice]) -> float:
        """Compute due soon total per horizon (§5.3 locked)."""
        due_soon = 0.0

        for inv in valid:
            if inv.days_overdue > 0:
                continue  # Already overdue, not "due soon"

            if not inv.due_date:
                continue

            try:
                due = datetime.strptime(inv.due_date[:10], "%Y-%m-%d").date()
                days_until = (due - self.today).days

                # Horizon gates per §5.3
                if (
                    self.horizon == Horizon.NOW
                    and days_until <= 0
                    or self.horizon == Horizon.TODAY
                    and days_until <= 1
                    or self.horizon == Horizon.THIS_WEEK
                    and days_until <= 7
                ):
                    due_soon += inv.amount
            except (ValueError, TypeError):
                pass

        return due_soon

    def _compute_portfolio_risk_score(self, valid: list[Invoice]) -> float:
        """Compute overall portfolio risk score (average of client scores)."""
        if not valid:
            return 0.0

        # Group by client and compute per-client scores
        by_client: dict[str, list[Invoice]] = {}
        for inv in valid:
            cid = inv.client_id or "unknown"
            if cid not in by_client:
                by_client[cid] = []
            by_client[cid].append(inv)

        if not by_client:
            return 0.0

        # Weight by AR amount
        total_ar = sum(i.amount for i in valid)
        if total_ar == 0:
            return 0.0

        weighted_score = 0.0
        for _client_id, invs in by_client.items():
            client_ar = sum(i.amount for i in invs)
            client_score = self._compute_client_risk_score(invs)
            weighted_score += client_score * (client_ar / total_ar)

        return weighted_score

    def _compute_client_risk_score(self, invoices: list[Invoice]) -> float:
        """
        Compute Client Cash Risk Score per §5.1 formula (locked).

        RiskScore = 100 * (
            0.55*severe_ratio +
            0.25*moderate_ratio +
            0.10*overdue_ratio +
            0.10*oldest_factor
        )
        """
        if not invoices:
            return 0.0

        T = sum(i.amount for i in invoices)  # total valid AR
        if T == 0:
            return 0.0

        C = sum(i.amount for i in invoices if i.aging_bucket == "current")  # current
        M = sum(i.amount for i in invoices if i.aging_bucket in ("1-30", "31-60"))  # moderate
        S = sum(i.amount for i in invoices if i.aging_bucket in ("61-90", "90+"))  # severe

        # Oldest days overdue
        oldest_days = max((i.days_overdue for i in invoices if i.days_overdue > 0), default=0)

        severe_ratio = S / T
        moderate_ratio = M / T
        overdue_ratio = (T - C) / T
        oldest_factor = min(1.0, oldest_days / 90)  # clamp to 1.0

        risk_score = 100 * (
            0.55 * severe_ratio
            + 0.25 * moderate_ratio
            + 0.10 * overdue_ratio
            + 0.10 * oldest_factor
        )

        return max(0.0, min(100.0, risk_score))  # clamp 0..100

    def _score_to_band(self, score: float) -> str:
        """Convert risk score to band per §5.2 (locked)."""
        if score >= 70:
            return "HIGH"
        if score >= 40:
            return "MED"
        return "LOW"

    def _compute_ar_trend(self, invoices: list[Invoice]) -> float | None:
        """
        Compute AR trend based on invoice aging velocity.
        Returns: float (-100 to +100) where positive = worsening, negative = improving
        None if insufficient data.
        """
        if not invoices:
            return None

        # Calculate weighted aging score
        # More weight to severely overdue invoices
        total_amount = sum(i.amount for i in invoices)
        if total_amount == 0:
            return None

        # Weighted average days overdue
        weighted_days = sum(i.amount * max(0, i.days_overdue) for i in invoices) / total_amount

        # Convert to trend score: 0 days = 0, 90+ days = +50
        # This is a proxy for trend since we don't have historical data
        trend = min(50, weighted_days / 1.8)  # Scale: 90 days -> 50

        # If most invoices are current, trend is negative (improving)
        current_pct = sum(i.amount for i in invoices if i.days_overdue <= 0) / total_amount

        if current_pct > 0.7:
            trend = -10  # Healthy, improving
        elif current_pct > 0.5:
            trend = 0  # Stable

        return round(trend, 1)

    def _compute_top_driver(
        self, valid: list[Invoice], buckets: dict, overdue: float, total: float
    ) -> str:
        """Compute top driver sentence for summary."""
        if total == 0:
            return "No AR outstanding."

        severe = buckets.get("61-90", 0) + buckets.get("90+", 0)
        severe_pct = (severe / total * 100) if total > 0 else 0

        if severe_pct >= 25:
            return f"AR risk is HIGH because AED {severe:,.0f} ({severe_pct:.0f}%) is 61+ days overdue."
        if overdue / total >= 0.5:
            return f"AR risk is MED because AED {overdue:,.0f} ({overdue / total * 100:.0f}%) is overdue."
        if buckets.get("90+", 0) > 0:
            return f"AR risk is MED because AED {buckets['90+']:,.0f} is 90+ days overdue."
        current = buckets.get("current", 0)
        return f"AR risk is LOW — AED {current:,.0f} ({current / total * 100:.0f}%) is current."

    def _build_portfolio(
        self, valid: list[Invoice], invalid: list[Invoice], limit: int
    ) -> list[ClientARData]:
        """Build ranked portfolio per §9.1 (locked ordering)."""
        # Group by client
        by_client: dict[str, dict] = {}

        for inv in valid:
            cid = inv.client_id
            if not cid:
                continue

            if cid not in by_client:
                by_client[cid] = {
                    "client_id": cid,
                    "name": inv.client_name or cid,
                    "invoices": [],
                    "invalid": [],
                }
            by_client[cid]["invoices"].append(inv)

        for inv in invalid:
            cid = inv.client_id or "unlinked"
            if cid not in by_client:
                by_client[cid] = {
                    "client_id": cid,
                    "name": inv.client_name or "Unlinked",
                    "invoices": [],
                    "invalid": [],
                }
            by_client[cid]["invalid"].append(inv)

        # Build ClientARData for each
        clients = []
        for cid, data in by_client.items():
            client = self._build_client_ar_data(
                cid, data["name"], data["invoices"], data["invalid"]
            )
            clients.append(client)

        # Sort per §9.1 (locked)
        # 1. Risk band: HIGH > MED > LOW
        # 2. cash_risk_score desc
        # 3. overdue_total desc
        # 4. oldest_days_overdue desc
        # 5. confidence: HIGH > MED > LOW
        band_order = {"HIGH": 0, "MED": 1, "LOW": 2}
        conf_order = {"HIGH": 0, "MED": 1, "LOW": 2}

        clients.sort(
            key=lambda c: (
                band_order.get(c.risk_band, 2),
                -c.cash_risk_score,
                -c.overdue_total,
                -c.oldest_days_overdue,
                conf_order.get(c.confidence, 2),
            )
        )

        return clients[:limit]

    def _build_client_ar_data(
        self,
        client_id: str,
        name: str,
        valid_invoices: list[Invoice],
        invalid_invoices: list[Invoice],
    ) -> ClientARData:
        """Build ClientARData for a single client."""
        # Get client tier
        tier = self._get_client_tier(client_id)

        # Compute totals
        valid_ar_total = sum(i.amount for i in valid_invoices)
        overdue_total = sum(i.amount for i in valid_invoices if i.days_overdue > 0)

        # Bucket totals
        bucket_totals = {
            "current": 0.0,
            "1-30": 0.0,
            "31-60": 0.0,
            "61-90": 0.0,
            "90+": 0.0,
        }
        for inv in valid_invoices:
            if inv.aging_bucket and inv.aging_bucket in bucket_totals:
                bucket_totals[inv.aging_bucket] += inv.amount

        # Worst bucket (largest by amount)
        worst_bucket = "none"
        worst_amount = 0.0
        for bucket, amount in bucket_totals.items():
            if amount > worst_amount:
                worst_amount = amount
                worst_bucket = bucket

        # Oldest days overdue
        oldest_days = max((i.days_overdue for i in valid_invoices if i.days_overdue > 0), default=0)

        # Risk score + band
        risk_score = self._compute_client_risk_score(valid_invoices)
        risk_band = self._score_to_band(risk_score)

        # Trend: Calculate based on invoice aging velocity
        # Positive = worsening (more overdue), Negative = improving
        trend = self._compute_ar_trend(valid_invoices)

        # Confidence per §6 (locked)
        confidence, why_low = self._compute_client_confidence(valid_invoices, invalid_invoices)

        return ClientARData(
            client_id=client_id,
            name=name,
            tier=tier,
            valid_ar_total=valid_ar_total,
            overdue_total=overdue_total,
            bucket_totals=bucket_totals,
            worst_bucket=worst_bucket,
            oldest_days_overdue=oldest_days,
            cash_risk_score=risk_score,
            risk_band=risk_band,
            trend=trend,
            confidence=confidence,
            why_low=why_low,
            invoices=valid_invoices,
            invalid_items=[
                {
                    "invoice_id": i.invoice_id,
                    "issue": i.invalid_reason,
                    "amount": i.amount,
                    "why": self._invalid_reason_text(i.invalid_reason),
                }
                for i in invalid_invoices
            ],
        )

    def _get_client_tier(self, client_id: str) -> str:
        """Get client tier from database."""
        row = self._query_one("SELECT tier FROM clients WHERE id = ?", (client_id,))
        return row.get("tier", "C") if row else "C"

    def _compute_client_confidence(
        self, valid: list[Invoice], invalid: list[Invoice]
    ) -> tuple[str, list[str]]:
        """
        Compute per-client confidence per §6 (locked).

        HIGH if:
          - data_integrity=true
          - finance_ar_coverage_pct >= 95%
          - 0 invalid AR AND at least 1 valid invoice OR zero finance items

        MED if:
          - finance_ar_coverage_pct 80-94% OR <= 2 invalid AR rows

        LOW otherwise (with why_low bullets)
        """
        why_low = []

        # Check data integrity
        if not self.data_integrity:
            why_low.append("Data integrity check failed")
            return "LOW", why_low[:3]

        # Check coverage
        if self.finance_ar_coverage_pct < 80:
            why_low.append("Finance coverage degraded")

        # Check invalid count
        invalid_count = len(invalid)
        if invalid_count > 2:
            # Categorize invalids
            missing_due = sum(1 for i in invalid if i.invalid_reason == "missing_due_date")
            missing_client = sum(1 for i in invalid if i.invalid_reason == "missing_client_id")

            if missing_due > 0:
                why_low.append(f"Invoices missing due dates ({missing_due})")
            if missing_client > 0:
                why_low.append(f"Invoices unlinked to clients ({missing_client})")

        # No finance source
        if not valid and not invalid:
            why_low.append("No finance source connected")

        # Determine level
        if (
            self.data_integrity
            and self.finance_ar_coverage_pct >= 95
            and invalid_count == 0
            and (len(valid) >= 1 or (len(valid) == 0 and invalid_count == 0))
        ):
            return "HIGH", []
        if self.finance_ar_coverage_pct >= 80 or invalid_count <= 2:
            return "MED", why_low[:3]
        return "LOW", why_low[:3]

    def _invalid_reason_text(self, reason: str | None) -> str:
        """Convert invalid reason to human text."""
        mapping = {
            "missing_due_date": "Invoice has no due date",
            "missing_client_id": "Invoice not linked to a client",
            "invalid_due_date": "Due date is invalid/unparseable",
            "unlinked_client": "Client identity not resolved",
        }
        return mapping.get(reason, "Unknown issue")

    def _build_selected_client(
        self,
        client_id: str,
        valid: list[Invoice],
        invalid: list[Invoice],
    ) -> ClientARData | None:
        """Build full detail for selected client (Client AR Room)."""
        # Filter invoices for this client
        client_valid = [i for i in valid if i.client_id == client_id]
        client_invalid = [i for i in invalid if i.client_id == client_id]

        if not client_valid and not client_invalid:
            return None

        # Get name
        name = (
            client_valid[0].client_name
            if client_valid
            else client_invalid[0].client_name
            if client_invalid
            else client_id
        )

        client = self._build_client_ar_data(client_id, name, client_valid, client_invalid)

        # Sort invoices per §9.2 (locked)
        # 1. bucket severity: 90+ > 61-90 > 31-60 > 1-30 > current
        # 2. days_overdue desc
        # 3. amount desc
        bucket_order = {
            "90+": 0,
            "61-90": 1,
            "31-60": 2,
            "1-30": 3,
            "current": 4,
            None: 5,
        }
        client.invoices.sort(
            key=lambda i: (
                bucket_order.get(i.aging_bucket, 5),
                -i.days_overdue,
                -i.amount,
            )
        )
        client.invoices = client.invoices[: self.MAX_INVOICES]

        # Cap invalid items
        client.invalid_items = client.invalid_items[: self.MAX_INVALID]

        # Add comms context
        client.comms_context = self._get_client_comms(client_id)[: self.MAX_COMMS]

        # Add recent change
        client.recent_change = self._get_client_recent_change(client_id)[: self.MAX_RECENT_CHANGE]

        return client

    def _get_client_comms(self, client_id: str) -> list[dict]:
        """Get payment-relevant comms threads for client."""
        rows = self._query_all(
            """
            SELECT
                c.id as thread_id,
                c.subject,
                c.created_at,
                c.response_deadline as expected_response_by
            FROM communications c
            WHERE c.client_id = ?
            AND (
                c.subject LIKE '%payment%' OR
                c.subject LIKE '%invoice%' OR
                c.subject LIKE '%overdue%' OR
                c.subject LIKE '%reminder%' OR
                c.requires_response = 1
            )
            ORDER BY c.response_deadline ASC NULLS LAST, c.created_at DESC
            LIMIT ?
        """,
            (client_id, self.MAX_COMMS),
        )

        comms = []
        for row in rows:
            age_hours = 0
            if row.get("created_at"):
                try:
                    created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                    age_hours = (self.now - created.replace(tzinfo=None)).total_seconds() / 3600
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse created_at: {e}")

            # Risk based on age and response deadline
            risk = "LOW"
            if row.get("expected_response_by"):
                try:
                    deadline = datetime.fromisoformat(
                        row["expected_response_by"].replace("Z", "+00:00")
                    )
                    if deadline.replace(tzinfo=None) < self.now:
                        risk = "HIGH"
                    elif (deadline.replace(tzinfo=None) - self.now).total_seconds() < 24 * 3600:
                        risk = "MED"
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not parse expected_response_by: {e}")
            elif age_hours > 48:
                risk = "HIGH"
            elif age_hours > 24:
                risk = "MED"

            comms.append(
                {
                    "thread_id": row["thread_id"],
                    "subject": row.get("subject", ""),
                    "age_hours": round(age_hours, 1),
                    "expected_response_by": row.get("expected_response_by"),
                    "risk": risk,
                }
            )

        return comms

    def _get_client_recent_change(self, client_id: str) -> list[dict]:
        """Get recent AR changes for client based on invoice modifications."""
        changes = []

        # Query for recently modified invoices for this client
        rows = self._query_all(
            """
            SELECT id, amount, status, due_date, updated_at
            FROM invoices
            WHERE client_id = ?
            AND updated_at >= datetime('now', '-7 days')
            ORDER BY updated_at DESC
            LIMIT 5
        """,
            (client_id,),
        )

        for row in rows:
            changes.append(
                {
                    "invoice_id": row["id"],
                    "amount": row["amount"],
                    "status": row["status"],
                    "due_date": row["due_date"],
                    "updated_at": row["updated_at"],
                    "change_type": "status_change" if row["status"] == "paid" else "update",
                }
            )

        return changes

    def _build_global_actions(
        self,
        valid: list[Invoice],
        invalid: list[Invoice],
        portfolio: list[ClientARData],
    ) -> list[ARAction]:
        """Build global actions per §7 (locked risk model)."""
        actions = []

        # Actions for overdue valid AR
        overdue = [i for i in valid if i.days_overdue > 0]
        overdue.sort(key=lambda i: (-i.days_overdue, -i.amount))

        for inv in overdue[:3]:
            actions.append(
                ARAction(
                    action_id=f"reminder_{inv.invoice_id}",
                    risk_level="propose",
                    label="Send payment reminder email",
                    entity_type="invoice",
                    entity_id=inv.invoice_id,
                    idempotency_key=f"reminder_{inv.invoice_id}_{self.today.isoformat()}",
                    payload={
                        "invoice_id": inv.invoice_id,
                        "client_id": inv.client_id,
                        "amount": inv.amount,
                        "days_overdue": inv.days_overdue,
                        "action": "send_reminder",
                    },
                    why=f"AED {inv.amount:,.0f} is {inv.days_overdue}d overdue",
                )
            )

        # Actions for severely overdue (escalation)
        severe = [i for i in valid if i.days_overdue > 60]
        for inv in severe[:2]:
            actions.append(
                ARAction(
                    action_id=f"escalate_{inv.invoice_id}",
                    risk_level="propose",
                    label="Escalate to owner / schedule follow-up",
                    entity_type="invoice",
                    entity_id=inv.invoice_id,
                    idempotency_key=f"escalate_{inv.invoice_id}_{self.today.isoformat()}",
                    payload={
                        "invoice_id": inv.invoice_id,
                        "client_id": inv.client_id,
                        "amount": inv.amount,
                        "days_overdue": inv.days_overdue,
                        "action": "escalate",
                    },
                    why=f"AED {inv.amount:,.0f} is {inv.days_overdue}d overdue (severe)",
                )
            )

        # Actions for invalid AR
        for inv in invalid[:2]:
            actions.append(
                ARAction(
                    action_id=f"fix_{inv.invoice_id}",
                    risk_level="auto",
                    label=f"Create resolution item: {inv.invalid_reason}",
                    entity_type="invoice",
                    entity_id=inv.invoice_id,
                    idempotency_key=f"fix_{inv.invoice_id}_{inv.invalid_reason}",
                    payload={
                        "invoice_id": inv.invoice_id,
                        "issue": inv.invalid_reason,
                        "amount": inv.amount,
                        "action": "create_resolution",
                    },
                    why=self._invalid_reason_text(inv.invalid_reason),
                )
            )

        # Cap at max
        return actions[: self.MAX_GLOBAL_ACTIONS]

    def _build_client_actions(self, client: ClientARData) -> list[ARAction]:
        """Build actions for a specific client per §7."""
        actions = []

        # Overdue invoices
        overdue_invs = [i for i in client.invoices if i.days_overdue > 0]

        for inv in overdue_invs[:2]:
            actions.append(
                ARAction(
                    action_id=f"reminder_{inv.invoice_id}",
                    risk_level="propose",
                    label="Send payment reminder email",
                    entity_type="invoice",
                    entity_id=inv.invoice_id,
                    idempotency_key=f"reminder_{inv.invoice_id}_{self.today.isoformat()}",
                    payload={
                        "invoice_id": inv.invoice_id,
                        "client_id": client.client_id,
                        "amount": inv.amount,
                        "days_overdue": inv.days_overdue,
                        "action": "send_reminder",
                    },
                    why=f"AED {inv.amount:,.0f} is {inv.days_overdue}d overdue",
                )
            )

        # Escalation for severe
        severe_invs = [i for i in overdue_invs if i.days_overdue > 60]
        if severe_invs:
            actions.append(
                ARAction(
                    action_id=f"escalate_{client.client_id}",
                    risk_level="propose",
                    label="Escalate to owner / schedule follow-up",
                    entity_type="client",
                    entity_id=client.client_id,
                    idempotency_key=f"escalate_{client.client_id}_{self.today.isoformat()}",
                    payload={
                        "client_id": client.client_id,
                        "severe_amount": sum(i.amount for i in severe_invs),
                        "action": "escalate",
                    },
                    why=f"AED {sum(i.amount for i in severe_invs):,.0f} is 61+ days overdue",
                )
            )

        # Due soon nudge
        due_soon = [i for i in client.invoices if i.days_overdue <= 0 and i.days_overdue >= -7]
        if due_soon:
            actions.append(
                ARAction(
                    action_id=f"nudge_{client.client_id}",
                    risk_level="propose",
                    label="Pre-due nudge (friendly reminder)",
                    entity_type="client",
                    entity_id=client.client_id,
                    idempotency_key=f"nudge_{client.client_id}_{self.today.isoformat()}",
                    payload={
                        "client_id": client.client_id,
                        "due_soon_amount": sum(i.amount for i in due_soon),
                        "action": "nudge",
                    },
                    why=f"AED {sum(i.amount for i in due_soon):,.0f} due within 7 days",
                )
            )

        # Fix invalid items
        for item in client.invalid_items[:2]:
            actions.append(
                ARAction(
                    action_id=f"fix_{item['invoice_id']}",
                    risk_level="auto",
                    label=f"Create resolution item: {item['issue']}",
                    entity_type="invoice",
                    entity_id=item["invoice_id"],
                    idempotency_key=f"fix_{item['invoice_id']}_{item['issue']}",
                    payload={
                        "invoice_id": item["invoice_id"],
                        "issue": item["issue"],
                        "action": "create_resolution",
                    },
                    why=item["why"],
                )
            )

        return actions[: self.MAX_CLIENT_ACTIONS]

    def _client_to_dict(self, client: ClientARData) -> dict:
        """Convert ClientARData to portfolio dict."""
        return {
            "client_id": client.client_id,
            "name": client.name,
            "tier": client.tier,
            "valid_ar_total": client.valid_ar_total,
            "overdue_total": client.overdue_total,
            "worst_bucket": client.worst_bucket,
            "oldest_days_overdue": client.oldest_days_overdue,
            "cash_risk_score": round(client.cash_risk_score, 1),
            "risk_band": client.risk_band,
            "trend": client.trend,
            "confidence": client.confidence,
            "why_low": client.why_low,
        }

    def _selected_client_to_dict(self, client: ClientARData) -> dict:
        """Convert ClientARData to selected_client dict per §8.1."""
        actions = self._build_client_actions(client)

        return {
            "client_id": client.client_id,
            "header": {
                "tier": client.tier,
            },
            "confidence": {
                "level": client.confidence,
                "why_low": client.why_low,
            },
            "ar_snapshot": {
                "valid_ar_total": client.valid_ar_total,
                "overdue_total": client.overdue_total,
                "bucket_totals": client.bucket_totals,
                "oldest_days_overdue": client.oldest_days_overdue,
            },
            "top_invoices": [
                {
                    "invoice_id": i.invoice_id,
                    "external_id": i.external_id,
                    "amount": i.amount,
                    "currency": i.currency,
                    "issue_date": i.issue_date,
                    "due_date": i.due_date,
                    "days_overdue": i.days_overdue,
                    "aging_bucket": i.aging_bucket,
                    "status": i.status,
                }
                for i in client.invoices
            ],
            "invalid_missing": client.invalid_items,
            "comms_context": client.comms_context,
            "recent_change": client.recent_change,
            "actions": [self._action_to_dict(a) for a in actions],
        }

    def _action_to_dict(self, action: ARAction) -> dict:
        """Convert ARAction to dict."""
        return {
            "action_id": action.action_id,
            "risk_level": action.risk_level,
            "label": action.label,
            "entity_type": action.entity_type,
            "entity_id": action.entity_id,
            "idempotency_key": action.idempotency_key,
            "payload": action.payload,
            "why": action.why,
        }


def generate_cash_ar(
    mode: str = "Ops Head",
    horizon: str = "TODAY",
    selected_client_id: str | None = None,
    expanded: bool = False,
) -> dict:
    """Convenience function to generate cash_ar section."""
    from .scoring import Horizon, Mode

    mode_enum = Mode(mode) if mode in [m.value for m in Mode] else Mode.OPS_HEAD
    horizon_enum = Horizon(horizon) if horizon in [h.value for h in Horizon] else Horizon.TODAY

    engine = CashAREngine(mode=mode_enum, horizon=horizon_enum)
    return engine.generate(selected_client_id=selected_client_id, expanded=expanded)


if __name__ == "__main__":
    logger.info("Generating Cash/AR Command snapshot...")
    result = generate_cash_ar()

    logger.info("\nSummary:")
    summary = result.get("summary", {})
    logger.info(f"  Valid AR: AED {summary.get('valid_ar_total', 0):,.2f}")
    logger.info(f"  Overdue: AED {summary.get('overdue_total', 0):,.2f}")
    logger.info(f"  Risk Band: {summary.get('risk_band', 'N/A')}")
    logger.info(f"  {summary.get('top_driver_sentence', '')}")
    logger.info(f"\nPortfolio ({len(result.get('portfolio', []))} clients):")
    for c in result.get("portfolio", [])[:5]:
        logger.info(
            f"  {c['name']}: AED {c['valid_ar_total']:,.0f} | Score: {c['cash_risk_score']:.0f} | {c['risk_band']}"
        )
    logger.info(f"\nGlobal Actions ({len(result.get('global_actions', []))}):")
    for a in result.get("global_actions", [])[:3]:
        logger.info(f"  [{a['risk_level']}] {a['label']} - {a['why']}")
