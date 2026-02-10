"""
API Endpoints — Spec Section 7

Implements all API endpoints for Time OS Client UI.
"""

import json
import logging
import sqlite3
from datetime import date, timedelta
from typing import Any

from .health import ar_overdue_pct, client_health, count_health_issues
from .inbox_lifecycle import InboxLifecycleManager
from .issue_lifecycle import AVAILABLE_ACTIONS, IssueState
from .time_utils import (
    DEFAULT_ORG_TZ,
    aging_bucket,
    client_status_boundaries,
    days_overdue,
    is_today_or_past,
    now_iso,
    window_start,
)

logger = logging.getLogger(__name__)


def safe_parse_evidence(
    evidence_raw: str | None, item_id: str = "unknown"
) -> dict[str, Any]:
    """
    Parse evidence JSON with strict error handling.

    Returns parsed evidence dict. On parse failure:
    - Logs error with item_id and raw length (not full content)
    - Returns minimal dict with meta.trust.data_integrity=False
    - Includes error message and debug info
    """
    if not evidence_raw:
        return {}

    try:
        return json.loads(evidence_raw)
    except json.JSONDecodeError as e:
        logger.error(
            f"JSON parse error for item {item_id}: "
            f"raw_length={len(evidence_raw)}, error={str(e)[:50]}"
        )
        return {
            "meta": {
                "trust": {
                    "data_integrity": False,
                    "errors": [f"evidence parse failed: {str(e)[:100]}"],
                    "debug": {
                        "raw_length": len(evidence_raw),
                        "raw_prefix": evidence_raw[:50]
                        if len(evidence_raw) > 50
                        else evidence_raw,
                    },
                }
            }
        }


# Client status values
CLIENT_STATUS_ACTIVE = "active"
CLIENT_STATUS_RECENTLY_ACTIVE = "recently_active"
CLIENT_STATUS_COLD = "cold"

# Include policy for client detail (spec 7.9)
CLIENT_INCLUDE_SECTIONS = {
    CLIENT_STATUS_ACTIVE: {"overview", "engagements", "financials", "signals", "team"},
    CLIENT_STATUS_RECENTLY_ACTIVE: {"financials", "brands", "last_invoices"},
    CLIENT_STATUS_COLD: {"financials"},
}

# Always-present base fields
CLIENT_BASE_FIELDS = {"id", "name", "status", "tier"}


class ClientEndpoints:
    """
    Client API endpoints.

    Spec: 7.1, 7.2, 7.3, 7.9
    """

    def __init__(self, conn: sqlite3.Connection, org_tz: str = DEFAULT_ORG_TZ):
        self.conn = conn
        self.org_tz = org_tz

    def get_client_status(self, client_id: str) -> str:
        """
        Compute client status from invoice history.

        Spec: 6.1 Client Status Logic
        """
        boundaries = client_status_boundaries(self.org_tz)

        cursor = self.conn.execute(
            """
            SELECT MAX(issue_date) FROM invoices
            WHERE client_id = ? AND status != 'voided'
        """,
            (client_id,),
        )
        row = cursor.fetchone()

        if not row or not row[0]:
            return CLIENT_STATUS_COLD

        last_invoice = date.fromisoformat(row[0])

        if last_invoice >= boundaries["active_cutoff"]:
            return CLIENT_STATUS_ACTIVE
        if last_invoice >= boundaries["recently_active_cutoff"]:
            return CLIENT_STATUS_RECENTLY_ACTIVE
        return CLIENT_STATUS_COLD

    def get_clients(self, filters: dict | None = None) -> dict[str, Any]:
        """
        GET /api/clients

        Spec: 7.1 Client Index
        """
        filters = filters or {}
        boundaries = client_status_boundaries(self.org_tz)

        result = {
            "active": [],
            "recently_active": [],
            "cold": [],
            "counts": {"active": 0, "recently_active": 0, "cold": 0},
        }

        # Get all clients with invoice data
        cursor = self.conn.execute("""
            SELECT c.id, c.name, c.tier,
                   MAX(i.issue_date) as last_invoice_date,
                   MIN(i.issue_date) as first_invoice_date
            FROM clients c
            LEFT JOIN invoices i ON c.id = i.client_id AND i.status != 'voided'
            GROUP BY c.id
            ORDER BY c.name
        """)

        for row in cursor.fetchall():
            client_id, name, tier, last_inv, first_inv = row

            # Determine status
            if last_inv:
                last_date = date.fromisoformat(last_inv)
                if last_date >= boundaries["active_cutoff"]:
                    status = CLIENT_STATUS_ACTIVE
                elif last_date >= boundaries["recently_active_cutoff"]:
                    status = CLIENT_STATUS_RECENTLY_ACTIVE
                else:
                    status = CLIENT_STATUS_COLD
            else:
                status = CLIENT_STATUS_COLD

            # Apply filters
            if (
                filters.get("status")
                and filters["status"] != "all"
                and status != filters["status"]
            ):
                continue

            if filters.get("tier") and tier != filters["tier"]:
                continue

            # Build client data based on status
            client_data = self._build_client_card(
                client_id, name, tier, status, last_inv, first_inv
            )

            # Apply additional filters
            if filters.get("has_issues") and not client_data.get(
                "open_issues_high_critical"
            ):
                continue

            if (
                filters.get("has_overdue_ar")
                and not client_data.get("ar_overdue", 0) > 0
            ):
                continue

            result[status].append(client_data)
            result["counts"][status] += 1

        return result

    def _build_client_card(
        self,
        client_id: str,
        name: str,
        tier: str,
        status: str,
        last_inv: str | None,
        first_inv: str | None,
    ) -> dict[str, Any]:
        """Build client card data based on status."""
        base = {
            "id": client_id,
            "name": name,
            "tier": tier or "none",
            "status": status,
            "last_invoice_date": last_inv,
            "first_invoice_date": first_inv,
        }

        if status == CLIENT_STATUS_ACTIVE:
            # Get financial metrics
            financials = self._get_client_financials(client_id)

            # Get health score
            issues = self._get_open_issues(client_id)
            health_count = count_health_issues(issues)
            health = client_health(
                financials["ar_outstanding"], financials["ar_overdue"], health_count
            )

            base.update(
                {
                    "health_score": health.score,
                    "health_label": "provisional",
                    "issued_ytd": financials["issued_ytd"],
                    "issued_year": financials["issued_prior_year"],
                    "paid_ytd": financials["paid_ytd"],
                    "paid_year": financials["paid_prior_year"],
                    "ar_outstanding": financials["ar_outstanding"],
                    "ar_overdue": financials["ar_overdue"],
                    "ar_overdue_pct": ar_overdue_pct(
                        financials["ar_outstanding"], financials["ar_overdue"]
                    ),
                    "open_issues_high_critical": health_count,
                }
            )

        elif status == CLIENT_STATUS_RECENTLY_ACTIVE:
            financials = self._get_client_financials(client_id)
            base.update(
                {
                    "issued_last_12m": financials.get("issued_last_12m", 0),
                    "issued_prev_12m": financials.get("issued_prev_12m", 0),
                    "paid_last_12m": financials.get("paid_last_12m", 0),
                    "paid_prev_12m": financials.get("paid_prev_12m", 0),
                    "issued_lifetime": financials["issued_lifetime"],
                    "paid_lifetime": financials["paid_lifetime"],
                }
            )

        else:  # cold
            financials = self._get_client_financials(client_id)
            base.update(
                {
                    "issued_lifetime": financials["issued_lifetime"],
                    "paid_lifetime": financials["paid_lifetime"],
                }
            )

        return base

    def get_client_detail(
        self, client_id: str, include: list[str] | None = None
    ) -> tuple[dict | None, int | None]:
        """
        GET /api/clients/:id

        Spec: 7.2, 7.9 Include Policy

        Returns (data, error_code) - error_code is 403/400 if include forbidden/invalid
        """
        # Get client
        cursor = self.conn.execute(
            "SELECT id, name, tier FROM clients WHERE id = ?", (client_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None, 404

        client_id, name, tier = row
        status = self.get_client_status(client_id)

        # Base fields always returned
        result = {
            "id": client_id,
            "name": name,
            "tier": tier or "none",
            "status": status,
        }

        allowed_sections = CLIENT_INCLUDE_SECTIONS.get(status, set())

        # Validate include param
        if include is not None:
            if not include:  # Empty include
                return {
                    "error": "invalid_include",
                    "message": "Include parameter cannot be empty",
                }, 400

            for section in include:
                if (
                    section not in allowed_sections
                    and section not in CLIENT_BASE_FIELDS
                ):
                    return {
                        "error": "forbidden_section",
                        "message": f"Cannot include '{section}' for {status} client",
                        "allowed_includes": list(allowed_sections),
                    }, 403

            # Return only requested sections
            sections_to_include = set(include) & allowed_sections
        else:
            # No include param: return union shape with null for excluded
            sections_to_include = allowed_sections

        # Build sections
        if status == CLIENT_STATUS_ACTIVE:
            if "overview" in sections_to_include:
                result["overview"] = self._get_overview(client_id)
            else:
                result["overview"] = None

            if "engagements" in sections_to_include:
                result["engagements"] = self._get_engagements(client_id)
            else:
                result["engagements"] = None

            if "financials" in sections_to_include:
                result["financials"] = self._get_client_financials(client_id)
            else:
                result["financials"] = None

            if "signals" in sections_to_include:
                result["signals"] = self._get_signals_summary(client_id)
            else:
                result["signals"] = None

            if "team" in sections_to_include:
                result["team"] = self._get_team(client_id)
            else:
                result["team"] = None

            # Health always included for active
            financials = self._get_client_financials(client_id)
            issues = self._get_open_issues(client_id)
            health = client_health(
                financials["ar_outstanding"],
                financials["ar_overdue"],
                count_health_issues(issues),
            )
            result["health_score"] = health.score
            result["health_label"] = "provisional"

        elif status == CLIENT_STATUS_RECENTLY_ACTIVE:
            financials = self._get_client_financials(client_id)
            result.update(
                {
                    "issued_lifetime": financials["issued_lifetime"],
                    "paid_lifetime": financials["paid_lifetime"],
                    "last_invoice_date": self._get_last_invoice_date(client_id),
                    "first_invoice_date": self._get_first_invoice_date(client_id),
                    "brands": self._get_brands(client_id),
                    "last_invoices": self._get_last_invoices(client_id, limit=5),
                    # Excluded sections
                    "health_score": None,
                    "overview": None,
                    "engagements": None,
                    "signals": None,
                    "team": None,
                }
            )

        else:  # cold
            financials = self._get_client_financials(client_id)
            result.update(
                {
                    "issued_lifetime": financials["issued_lifetime"],
                    "paid_lifetime": financials["paid_lifetime"],
                }
            )

        return result, None

    def get_client_snapshot(
        self,
        client_id: str,
        inbox_item_id: str | None = None,
        issue_id: str | None = None,
    ) -> tuple[dict | None, int | None]:
        """
        GET /api/clients/:id/snapshot

        Spec: 7.3 Client Snapshot (Cold clients from Inbox)
        """
        if not inbox_item_id and not issue_id:
            return {
                "error": "missing_param",
                "message": "inbox_item_id or issue_id required",
            }, 400

        # Get client
        cursor = self.conn.execute(
            "SELECT id, name, tier FROM clients WHERE id = ?", (client_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None, 404

        client_id, name, tier = row
        status = self.get_client_status(client_id)
        financials = self._get_client_financials(client_id)

        result = {
            "id": client_id,
            "name": name,
            "status": status,
            "issued_lifetime": financials["issued_lifetime"],
            "paid_lifetime": financials["paid_lifetime"],
            "last_invoice_date": self._get_last_invoice_date(client_id),
            "first_invoice_date": self._get_first_invoice_date(client_id),
            "context": {},
            "related_signals": [],
        }

        # Build context (inbox_item_id takes precedence per spec)
        if inbox_item_id:
            cursor = self.conn.execute(
                "SELECT * FROM inbox_items_v29 WHERE id = ?", (inbox_item_id,)
            )
            item = cursor.fetchone()
            if item:
                item_dict = dict(item)
                result["context"]["source"] = "inbox_item"
                result["context"]["inbox_item"] = {
                    "id": item_dict["id"],
                    "type": item_dict["type"],
                    "title": item_dict["title"],
                    "evidence": safe_parse_evidence(
                        item_dict["evidence"], item_dict["id"]
                    ),
                    "actions": self._get_inbox_actions(item_dict["type"]),
                }

                if item_dict.get("underlying_issue_id"):
                    issue = self._get_issue(item_dict["underlying_issue_id"])
                    if issue:
                        result["context"]["issue"] = issue

        elif issue_id:
            issue = self._get_issue(issue_id)
            if issue:
                result["context"]["source"] = "issue"
                result["context"]["issue"] = issue

        # Get related signals (max 5, last 90 days)
        result["related_signals"] = self._get_related_signals(
            client_id, issue_id, limit=5, days=90
        )

        return result, None

    def _get_client_financials(self, client_id: str) -> dict[str, Any]:
        """Get financial summary for client."""
        from datetime import date

        today = date.today()
        year_start = date(today.year, 1, 1)
        prior_year = today.year - 1
        last_12m = today - timedelta(days=365)
        prev_12m_start = today - timedelta(days=730)
        prev_12m_end = today - timedelta(days=366)

        # Issued metrics
        cursor = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN strftime('%Y', issue_date) = ? THEN amount ELSE 0 END) as issued_prior_year,
                SUM(CASE WHEN issue_date >= ? THEN amount ELSE 0 END) as issued_ytd,
                SUM(CASE WHEN issue_date >= ? THEN amount ELSE 0 END) as issued_last_12m,
                SUM(CASE WHEN issue_date BETWEEN ? AND ? THEN amount ELSE 0 END) as issued_prev_12m,
                SUM(amount) as issued_lifetime
            FROM invoices
            WHERE client_id = ? AND status != 'voided'
        """,
            (
                str(prior_year),
                year_start.isoformat(),
                last_12m.isoformat(),
                prev_12m_start.isoformat(),
                prev_12m_end.isoformat(),
                client_id,
            ),
        )
        issued = cursor.fetchone()

        # Paid metrics - matched to issue year (paid for invoices issued in that period)
        cursor = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN strftime('%Y', issue_date) = ? AND status = 'paid' THEN amount ELSE 0 END) as paid_prior_year,
                SUM(CASE WHEN issue_date >= ? AND status = 'paid' THEN amount ELSE 0 END) as paid_ytd,
                SUM(CASE WHEN issue_date >= ? AND status = 'paid' THEN amount ELSE 0 END) as paid_last_12m,
                SUM(CASE WHEN issue_date BETWEEN ? AND ? AND status = 'paid' THEN amount ELSE 0 END) as paid_prev_12m,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_lifetime
            FROM invoices
            WHERE client_id = ?
        """,
            (
                str(prior_year),
                year_start.isoformat(),
                last_12m.isoformat(),
                prev_12m_start.isoformat(),
                prev_12m_end.isoformat(),
                client_id,
            ),
        )
        paid = cursor.fetchone()

        # AR metrics
        cursor = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN status IN ('sent', 'overdue') THEN amount ELSE 0 END) as ar_outstanding,
                SUM(CASE WHEN status = 'overdue' THEN amount ELSE 0 END) as ar_overdue
            FROM invoices
            WHERE client_id = ?
        """,
            (client_id,),
        )
        ar = cursor.fetchone()

        return {
            "finance_calc_version": "v1",
            "prior_year": prior_year,
            "issued_prior_year": issued[0] or 0,
            "issued_ytd": issued[1] or 0,
            "issued_last_12m": issued[2] or 0,
            "issued_prev_12m": issued[3] or 0,
            "issued_lifetime": issued[4] or 0,
            "paid_prior_year": paid[0] or 0,
            "paid_ytd": paid[1] or 0,
            "paid_last_12m": paid[2] or 0,
            "paid_prev_12m": paid[3] or 0,
            "paid_lifetime": paid[4] or 0,
            "ar_outstanding": ar[0] or 0,
            "ar_overdue": ar[1] or 0,
        }

    def _get_open_issues(self, client_id: str) -> list[dict]:
        """Get open issues for client."""
        cursor = self.conn.execute(
            """
            SELECT id, type, state, severity, suppressed
            FROM issues_v29
            WHERE client_id = ?
            AND state IN ('surfaced', 'acknowledged', 'addressing',
                         'awaiting_resolution', 'regressed')
        """,
            (client_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_overview(self, client_id: str) -> dict[str, Any]:
        """Get overview section for active client."""
        return {
            "top_issues": self._get_top_issues(client_id, limit=5),
            "recent_positive_signals": self._get_recent_positive_signals(
                client_id, limit=3
            ),
        }

    def _get_top_issues(self, client_id: str, limit: int = 5) -> list[dict]:
        """Get top issues sorted by severity."""
        cursor = self.conn.execute(
            """
            SELECT id, type, state, severity, title, evidence, created_at
            FROM issues_v29
            WHERE client_id = ?
            AND severity IN ('high', 'critical')
            AND state IN ('surfaced', 'acknowledged', 'addressing',
                         'awaiting_resolution', 'regressed')
            AND suppressed = 0
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 5
                    WHEN 'high' THEN 4
                END DESC,
                created_at ASC
            LIMIT ?
        """,
            (client_id, limit),
        )

        issues = []
        for row in cursor.fetchall():
            issue = dict(row)
            issue["evidence"] = safe_parse_evidence(
                issue["evidence"], issue.get("id", "unknown")
            )
            issue["available_actions"] = AVAILABLE_ACTIONS.get(
                IssueState(issue["state"]), []
            )
            issues.append(issue)

        return issues

    def _get_recent_positive_signals(
        self, client_id: str, limit: int = 3
    ) -> list[dict]:
        """Get recent positive signals."""
        cursor = self.conn.execute(
            """
            SELECT id, source, summary, observed_at
            FROM signals_v29
            WHERE client_id = ?
            AND sentiment = 'good'
            AND dismissed_at IS NULL
            ORDER BY observed_at DESC
            LIMIT ?
        """,
            (client_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_engagements(self, client_id: str) -> dict[str, Any]:
        """Get engagements grouped by brand."""
        cursor = self.conn.execute(
            """
            SELECT b.id, b.name, e.id as eng_id, e.name as eng_name,
                   e.type, e.state
            FROM brands b
            LEFT JOIN engagements e ON b.id = e.brand_id
            WHERE b.client_id = ?
            ORDER BY b.name, e.name
        """,
            (client_id,),
        )

        brands = {}
        for row in cursor.fetchall():
            brand_id, brand_name = row[0], row[1]
            if brand_id not in brands:
                brands[brand_id] = {
                    "id": brand_id,
                    "name": brand_name,
                    "engagements": [],
                }

            if row[2]:  # Has engagement
                brands[brand_id]["engagements"].append(
                    {
                        "id": row[2],
                        "name": row[3],
                        "type": row[4],
                        "state": row[5],
                    }
                )

        return {"brands": list(brands.values())}

    def _get_signals_summary(self, client_id: str, days: int = 30) -> dict[str, Any]:
        """Get signals summary for client."""
        cutoff = window_start(self.org_tz, days)

        cursor = self.conn.execute(
            """
            SELECT sentiment, source, COUNT(*) as count
            FROM signals_v29
            WHERE client_id = ?
            AND observed_at >= ?
            AND dismissed_at IS NULL
            GROUP BY sentiment, source
        """,
            (client_id, cutoff.isoformat()),
        )

        summary = {"good": 0, "neutral": 0, "bad": 0, "by_source": {}}
        for row in cursor.fetchall():
            sentiment, source, count = row
            summary[sentiment] += count
            if source not in summary["by_source"]:
                summary["by_source"][source] = {"good": 0, "neutral": 0, "bad": 0}
            summary["by_source"][source][sentiment] = count

        return summary

    def _get_team(self, client_id: str) -> dict[str, Any]:
        """Get team involvement for client."""
        return {
            "involvement": [],
            "workload": [],
            "tardiness": [],
            "recent_activity": [],
        }

    def _get_brands(self, client_id: str) -> list[str]:
        """Get brand names for client."""
        cursor = self.conn.execute(
            "SELECT name FROM brands WHERE client_id = ?", (client_id,)
        )
        return [row[0] for row in cursor.fetchall()]

    def _get_last_invoices(self, client_id: str, limit: int = 5) -> list[dict]:
        """Get last N invoices."""
        cursor = self.conn.execute(
            """
            SELECT id, number, issue_date, amount, status
            FROM invoices
            WHERE client_id = ? AND status != 'voided'
            ORDER BY issue_date DESC
            LIMIT ?
        """,
            (client_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_last_invoice_date(self, client_id: str) -> str | None:
        """Get last invoice date."""
        cursor = self.conn.execute(
            """
            SELECT MAX(issue_date) FROM invoices
            WHERE client_id = ? AND status != 'voided'
        """,
            (client_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _get_first_invoice_date(self, client_id: str) -> str | None:
        """Get first invoice date."""
        cursor = self.conn.execute(
            """
            SELECT MIN(issue_date) FROM invoices
            WHERE client_id = ? AND status != 'voided'
        """,
            (client_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _get_issue(self, issue_id: str) -> dict | None:
        """
        Get issue by ID.

        v2.9: Includes available_actions per §7.6
        """
        cursor = self.conn.execute("SELECT * FROM issues_v29 WHERE id = ?", (issue_id,))
        row = cursor.fetchone()
        if not row:
            return None
        issue = dict(row)
        issue["evidence"] = safe_parse_evidence(
            issue["evidence"], issue.get("id", issue_id)
        )
        # v2.9: Include available_actions (§7.6)
        issue["available_actions"] = AVAILABLE_ACTIONS.get(
            IssueState(issue["state"]), []
        )
        return issue

    def _get_inbox_actions(self, item_type: str) -> list[str]:
        """Get available inbox actions for item type."""
        from .inbox_lifecycle import ACTIONS_BY_TYPE, InboxType

        try:
            return [a.value for a in ACTIONS_BY_TYPE.get(InboxType(item_type), [])]
        except ValueError:
            return []

    def _get_related_signals(
        self, client_id: str, issue_id: str | None, limit: int = 5, days: int = 90
    ) -> list[dict]:
        """Get related signals for snapshot."""
        cutoff = window_start(self.org_tz, days)

        # First try signals linked to issue
        if issue_id:
            cursor = self.conn.execute(
                """
                SELECT id, source, summary, sentiment, observed_at
                FROM signals_v29
                WHERE id IN (
                    SELECT signal_id FROM issue_signals WHERE issue_id = ?
                )
                ORDER BY observed_at DESC
                LIMIT ?
            """,
                (issue_id, limit),
            )
            signals = [dict(row) for row in cursor.fetchall()]
            if signals:
                return signals

        # Fallback to client signals
        cursor = self.conn.execute(
            """
            SELECT id, source, summary, sentiment, observed_at
            FROM signals_v29
            WHERE client_id = ?
            AND observed_at >= ?
            AND dismissed_at IS NULL
            ORDER BY observed_at DESC
            LIMIT ?
        """,
            (client_id, cutoff.isoformat(), limit),
        )

        return [dict(row) for row in cursor.fetchall()]


class FinancialsEndpoints:
    """
    Financials API endpoints.

    Spec: 7.5
    """

    def __init__(self, conn: sqlite3.Connection, org_tz: str = DEFAULT_ORG_TZ):
        self.conn = conn
        self.org_tz = org_tz

    def get_invoices(
        self, client_id: str, filters: dict | None = None
    ) -> dict[str, Any]:
        """
        GET /api/clients/:id/invoices

        Spec: 7.5 Invoice Aging Computation
        """
        filters = filters or {}

        cursor = self.conn.execute(
            """
            SELECT id, number, issue_date, due_date, amount, status
            FROM invoices
            WHERE client_id = ?
            ORDER BY issue_date DESC
        """,
            (client_id,),
        )

        invoices = []
        for row in cursor.fetchall():
            inv = dict(row)

            # Compute aging per spec 7.5
            inv["days_overdue"] = None
            inv["aging_bucket"] = None
            inv["status_inconsistent"] = False

            status = inv["status"]
            due_date_str = inv.get("due_date")

            if status == "overdue":
                if due_date_str:
                    due_date = date.fromisoformat(due_date_str)
                    days = days_overdue(due_date, self.org_tz)
                    inv["days_overdue"] = days
                    inv["aging_bucket"] = aging_bucket(days)
                else:
                    # due_date null → 90_plus fallback
                    inv["aging_bucket"] = "90_plus"

            elif status == "sent" and due_date_str:
                due_date = date.fromisoformat(due_date_str)
                if is_today_or_past(due_date, self.org_tz):
                    # Status inconsistent!
                    days = days_overdue(due_date, self.org_tz)
                    inv["days_overdue"] = days
                    inv["aging_bucket"] = aging_bucket(days)
                    inv["status_inconsistent"] = True
                else:
                    inv["aging_bucket"] = "current"

            # Apply status filter
            if (
                filters.get("status")
                and filters["status"] != "all"
                and status != filters["status"]
            ):
                continue

            invoices.append(inv)

        # Pagination
        page = filters.get("page", 1)
        limit = filters.get("limit", 10)
        start = (page - 1) * limit
        end = start + limit

        return {
            "invoices": invoices[start:end],
            "total": len(invoices),
            "page": page,
            "limit": limit,
        }

    def get_ar_aging(self, client_id: str) -> dict[str, Any]:
        """Get AR aging breakdown."""
        cursor = self.conn.execute(
            """
            SELECT due_date, amount, status
            FROM invoices
            WHERE client_id = ? AND status IN ('sent', 'overdue')
        """,
            (client_id,),
        )

        buckets = {
            "current": 0,
            "1_30": 0,
            "31_60": 0,
            "61_90": 0,
            "90_plus": 0,
        }
        total = 0

        for row in cursor.fetchall():
            due_date_str, amount, status = row
            total += amount

            if status == "sent":
                if due_date_str:
                    due_date = date.fromisoformat(due_date_str)
                    if is_today_or_past(due_date, self.org_tz):
                        days = days_overdue(due_date, self.org_tz)
                        bucket = aging_bucket(days)
                    else:
                        bucket = "current"
                else:
                    bucket = "current"
            else:  # overdue
                if due_date_str:
                    due_date = date.fromisoformat(due_date_str)
                    days = days_overdue(due_date, self.org_tz)
                    bucket = aging_bucket(days)
                else:
                    bucket = "90_plus"

            buckets[bucket] += amount

        # Convert to response format
        result_buckets = []
        for bucket, amount in buckets.items():
            pct = round(amount / total * 100) if total > 0 else 0
            result_buckets.append(
                {
                    "bucket": bucket,
                    "amount": amount,
                    "pct": pct,
                }
            )

        return {
            "total_outstanding": total,
            "buckets": result_buckets,
        }


class InboxEndpoints:
    """
    Inbox API endpoints.

    Spec: 7.10
    """

    def __init__(self, conn: sqlite3.Connection, org_tz: str = DEFAULT_ORG_TZ):
        self.conn = conn
        self.org_tz = org_tz
        self.lifecycle = InboxLifecycleManager(conn, org_tz)

    # Severity ordering for max comparison (§0.1)
    SEVERITY_ORDER = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}

    def _max_severity(self, sev1: str | None, sev2: str | None) -> str:
        """
        Return the higher severity between two values.

        v2.9: Used for Severity Sync Rule (§7.10)
        display_severity = max(inbox_items.severity, issues.severity)
        """
        ord1 = self.SEVERITY_ORDER.get(sev1, 0)
        ord2 = self.SEVERITY_ORDER.get(sev2, 0)
        if ord1 >= ord2:
            return sev1 or "info"
        return sev2 or "info"

    def _enrich_evidence(
        self, evidence: dict, item_type: str, signal_id: str | None, title: str
    ) -> dict:
        """
        Enrich minimal evidence to canonical format at response time.

        If evidence is already canonical (has 'version' key), return as-is.
        Otherwise, join communications table to build full evidence envelope.
        DB frozen: read-only enrichment, no writes.
        """
        # Already canonical
        if evidence.get("version"):
            return evidence

        # Can't enrich without signal_id
        if not signal_id:
            return {
                "version": "v1",
                "kind": "unknown",
                "display_text": title,
                "source_system": evidence.get("source", "unknown"),
                "source_id": "",
                "payload": evidence,
            }

        # Lookup communication for enrichment (includes body_text for drill-down)
        comm = self.conn.execute(
            """
            SELECT source, source_id, thread_id, from_email, subject, snippet,
                   received_at, created_at, priority, requires_response, body_text
            FROM communications WHERE id = ?
            """,
            (signal_id,),
        ).fetchone()

        if not comm:
            # Fallback: wrap minimal evidence
            return {
                "version": "v1",
                "kind": "flagged_signal",
                "display_text": title,
                "source_system": evidence.get("source", "unknown"),
                "source_id": signal_id,
                "payload": evidence,
            }

        (
            source,
            source_id,
            thread_id,
            from_email,
            subject,
            snippet,
            received_at,
            created_at,
            priority,
            requires_response,
            body_text,
        ) = comm

        # Build Gmail URL if thread_id available
        url = None
        if source == "gmail" and thread_id:
            url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"

        # Clean snippet: strip HTML, normalize whitespace
        # Priority: body_text (if exists and meaningful) > snippet (if different from subject)
        import re

        def _clean_text(text: str | None, subject: str | None) -> str | None:
            """Clean HTML and normalize text for display."""
            if not text:
                return None
            # Remove HTML tags (DOTALL for multiline tags)
            cleaned = re.sub(r"<[^>]*>", "", text, flags=re.DOTALL)
            # Remove broken/incomplete HTML tags (e.g., "<td style=...")
            cleaned = re.sub(r"<[^>]*$", "", cleaned)
            # Remove HTML entities
            cleaned = re.sub(r"&[a-zA-Z]+;|&#\d+;", " ", cleaned)
            # Remove URLs that dominate the snippet
            cleaned = re.sub(r"https?://\S+", "", cleaned)
            # Remove [image: ...] placeholders
            cleaned = re.sub(r"\[image:[^\]]*\]", "", cleaned)
            # Normalize whitespace
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            # Skip if empty or too short
            if len(cleaned) < 10:
                return None
            # Skip if it's mostly the same as subject
            if subject and cleaned.lower().startswith(subject.lower()[:30]):
                cleaned = cleaned[len(subject) :].strip() if subject else cleaned
                if len(cleaned) < 10:
                    return None
            # Truncate for display
            if len(cleaned) > 300:
                cleaned = cleaned[:300] + "..."
            return cleaned

        clean_snippet = None
        # Try body_text first (richer content)
        if body_text and len(body_text) >= 20:
            clean_snippet = _clean_text(body_text, subject)
        # Fall back to snippet if body_text not useful
        if not clean_snippet and snippet and snippet != subject:
            clean_snippet = _clean_text(snippet, subject)

        # Derive flagged reason from priority
        flagged_reason = None
        if priority and priority >= 90:
            flagged_reason = "High priority email requiring attention"
        elif priority and priority >= 80:
            flagged_reason = "Important email flagged for review"
        elif requires_response:
            flagged_reason = "Email requires response"

        # Preserve any existing drill-down enrichment from stored evidence
        existing_payload = (
            evidence.get("payload", {}) if isinstance(evidence, dict) else {}
        )
        drill_down_fields = {
            "entities": existing_payload.get("entities", []),
            "rationale": existing_payload.get("rationale"),
            "suggested_actions": existing_payload.get("suggested_actions", []),
            "thread_context": existing_payload.get("thread_context"),
            "enriched_at": existing_payload.get("enriched_at"),
        }

        return {
            "version": "v1",
            "kind": "gmail_thread" if source == "gmail" else source or "unknown",
            "url": url,
            "display_text": subject or title,
            "source_system": source or "unknown",
            "source_id": source_id or signal_id,
            "payload": {
                "thread_id": thread_id,
                "sender": from_email,
                "snippet": clean_snippet,
                "received_at": received_at or created_at,
                "flagged_reason": flagged_reason,
                # Drill-down context (populated by inbox_enricher)
                **drill_down_fields,
            },
        }

    def get_inbox(self, filters: dict | None = None) -> dict[str, Any]:
        """
        GET /api/inbox

        Spec: 7.10
        """
        filters = filters or {}

        # Build WHERE clause
        where = ["state IN ('proposed', 'snoozed')"]
        params = []

        if filters.get("type") and filters["type"] != "all":
            where.append("type = ?")
            params.append(filters["type"])

        if filters.get("severity"):
            where.append("severity = ?")
            params.append(filters["severity"])

        if filters.get("state") and filters["state"] in ("proposed", "snoozed"):
            where.append("state = ?")
            params.append(filters["state"])

        if filters.get("client_id"):
            where.append("client_id = ?")
            params.append(filters["client_id"])

        if filters.get("unread_only"):
            where.append("read_at IS NULL")

        where_clause = " AND ".join(where)

        # Default sort: severity desc, proposed_at asc, id asc
        order = """
            CASE severity
                WHEN 'critical' THEN 5
                WHEN 'high' THEN 4
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 2
                WHEN 'info' THEN 1
            END DESC,
            proposed_at ASC,
            id ASC
        """

        # Get items
        cursor = self.conn.execute(
            f"""
            SELECT * FROM inbox_items_v29
            WHERE {where_clause}
            ORDER BY {order}
        """,
            params,
        )

        items = []
        for row in cursor.fetchall():
            item = dict(row)

            # Parse evidence with trust tracking
            from lib.safety import TrustMeta, safe_json_loads

            trust = TrustMeta()
            evidence_raw = item.get("evidence")
            if evidence_raw:
                result = safe_json_loads(
                    evidence_raw,
                    default={},
                    item_id=item.get("id"),
                    field_name="evidence",
                )
                item["evidence"] = result.value
                if not result.success:
                    trust.add_parse_error(
                        "evidence", result.error or "Parse failed", len(evidence_raw)
                    )
                    trust.debug["evidence_raw"] = result.raw_value
            else:
                item["evidence"] = {}

            # Enrich minimal evidence to canonical format (DB frozen: read-only)
            item["evidence"] = self._enrich_evidence(
                item["evidence"],
                item.get("type", ""),
                item.get("underlying_signal_id"),
                item.get("title", ""),
            )

            # Add trust metadata if there were parse failures
            if not trust.data_integrity:
                item["meta"] = {"trust": trust.to_dict()}

            # v2.9: Compute attention_age_start_at (§0.5)
            # attention_age_start_at = resurfaced_at ?? proposed_at
            item["attention_age_start_at"] = item.get("resurfaced_at") or item.get(
                "proposed_at"
            )

            # Get client info
            if item["client_id"]:
                c = self.conn.execute(
                    "SELECT id, name FROM clients WHERE id = ?", (item["client_id"],)
                ).fetchone()
                if c:
                    item["client"] = {"id": c[0], "name": c[1]}

            # v2.9: Rename actions to available_actions (§7.10)
            item["available_actions"] = self.lifecycle.get_actions(item["type"])

            # Get issue_category, issue_state, and display_severity if type is issue
            if item["type"] == "issue" and item.get("underlying_issue_id"):
                iss = self.conn.execute(
                    "SELECT type, state, assigned_to, severity FROM issues_v29 WHERE id = ?",
                    (item["underlying_issue_id"],),
                ).fetchone()
                if iss:
                    item["issue_category"] = iss[0]
                    item["issue_state"] = iss[1]

                    # v2.9: Severity Sync Rule (§7.10)
                    # display_severity = max(inbox_items.severity, issues.severity)
                    issue_severity = iss[3]
                    item["display_severity"] = self._max_severity(
                        item.get("severity"), issue_severity
                    )

                    if iss[2]:
                        # Get assignee name
                        assignee = self.conn.execute(
                            "SELECT id, name FROM team_members WHERE id = ?", (iss[2],)
                        ).fetchone()
                        if assignee:
                            item["issue_assignee"] = {
                                "id": assignee[0],
                                "name": assignee[1],
                            }
            else:
                # Non-issue items: display_severity equals severity
                item["display_severity"] = item.get("severity")

            items.append(item)

        # Get counts
        counts = self._get_counts()

        return {
            "counts": counts,
            "items": items,
        }

    def get_recent(self, days: int = 7, filters: dict | None = None) -> dict[str, Any]:
        """
        GET /api/inbox/recent

        Spec: 7.10
        """
        filters = filters or {}
        cutoff = window_start(self.org_tz, days)

        where = ["state IN ('linked_to_issue', 'dismissed')", "resolved_at >= ?"]
        params = [cutoff.isoformat()]

        if filters.get("state"):
            where.append("state = ?")
            params.append(filters["state"])

        if filters.get("type") and filters["type"] != "all":
            where.append("type = ?")
            params.append(filters["type"])

        where_clause = " AND ".join(where)

        cursor = self.conn.execute(
            f"""
            SELECT * FROM inbox_items_v29
            WHERE {where_clause}
            ORDER BY resolved_at DESC
        """,
            params,
        )

        items = []
        for row in cursor.fetchall():
            item = dict(row)

            # Parse evidence with trust tracking
            from lib.safety import TrustMeta, safe_json_loads

            trust = TrustMeta()
            evidence_raw = item.get("evidence")
            if evidence_raw:
                result = safe_json_loads(
                    evidence_raw,
                    default={},
                    item_id=item.get("id"),
                    field_name="evidence",
                )
                item["evidence"] = result.value
                if not result.success:
                    trust.add_parse_error(
                        "evidence", result.error or "Parse failed", len(evidence_raw)
                    )
                    trust.debug["evidence_raw"] = result.raw_value
                    item["meta"] = {"trust": trust.to_dict()}
            else:
                item["evidence"] = {}

            item["available_actions"] = []  # v2.9: Read-only for terminal items
            items.append(item)

        return {
            "items": items,
            "total": len(items),
            "page": 1,
        }

    def _get_counts(self) -> dict[str, Any]:
        """
        Get inbox counts per §1.9 and §7.10.

        v2.9: unprocessed uses is_unprocessed() logic:
        is_unprocessed = read_at IS NULL OR read_at < resurfaced_at

        Includes by_severity and by_type breakdowns per §1.9.
        """
        from datetime import timedelta

        now = now_iso()
        one_day_later = (from_iso(now) + timedelta(days=1)).isoformat()
        week_ago = window_start(self.org_tz, 7)

        # v2.9: Updated unprocessed calculation per §0.5
        # is_unprocessed() = read_at IS NULL OR read_at < resurfaced_at
        cursor = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN state = 'proposed' THEN 1 ELSE 0 END) as needs_attention,
                SUM(CASE WHEN state = 'snoozed' THEN 1 ELSE 0 END) as snoozed,
                SUM(CASE WHEN state = 'snoozed' AND snooze_until <= ? THEN 1 ELSE 0 END) as snoozed_returning_soon,
                SUM(CASE WHEN state = 'proposed' AND (
                    read_at IS NULL OR
                    (resurfaced_at IS NOT NULL AND read_at < resurfaced_at)
                ) THEN 1 ELSE 0 END) as unprocessed
            FROM inbox_items_v29
        """,
            (one_day_later,),
        )
        row = cursor.fetchone()

        # Recently actioned
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) FROM inbox_items_v29
            WHERE state IN ('linked_to_issue', 'dismissed')
            AND resolved_at >= ?
        """,
            (week_ago.isoformat(),),
        )
        recently = cursor.fetchone()[0]

        # by_severity breakdown (§1.9) - only for needs_attention items
        cursor = self.conn.execute("""
            SELECT severity, COUNT(*) as count
            FROM inbox_items_v29
            WHERE state = 'proposed'
            GROUP BY severity
        """)
        by_severity = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        for sev_row in cursor.fetchall():
            if sev_row[0] in by_severity:
                by_severity[sev_row[0]] = sev_row[1]

        # by_type breakdown (§1.9) - only for needs_attention items
        cursor = self.conn.execute("""
            SELECT type, COUNT(*) as count
            FROM inbox_items_v29
            WHERE state = 'proposed'
            GROUP BY type
        """)
        by_type = {
            "issue": 0,
            "flagged_signal": 0,
            "orphan": 0,
            "ambiguous": 0,
        }
        for type_row in cursor.fetchall():
            if type_row[0] in by_type:
                by_type[type_row[0]] = type_row[1]

        return {
            "scope": "global",  # v2.9: Always global per §7.10
            "needs_attention": row[0] or 0,
            "snoozed": row[1] or 0,
            "snoozed_returning_soon": row[2] or 0,
            "recently_actioned": recently,
            "unprocessed": row[3] or 0,
            "unprocessed_scope": "proposed",  # v2.9: Clarify scope
            "by_severity": by_severity,
            "by_type": by_type,
        }

    def execute_action(
        self, item_id: str, action: str, payload: dict, user_id: str
    ) -> tuple[dict, int | None]:
        """
        POST /api/inbox/:id/action

        Spec: 7.10
        """
        result = self.lifecycle.execute_action(item_id, action, payload, user_id)

        if not result.success:
            return {"error": result.error}, 400

        response = {
            "success": True,
            "inbox_item_state": result.inbox_item_state,
        }

        if result.issue_id:
            response["issue_id"] = result.issue_id
        if result.resolved_at:
            response["resolved_at"] = result.resolved_at
        if result.snooze_until:
            response["snooze_until"] = result.snooze_until
        if result.suppression_key:
            response["suppression_key"] = result.suppression_key
        if result.actions:
            response["actions"] = result.actions
        if result.engagement_id:
            response["engagement_id"] = result.engagement_id
        if result.client_id:
            response["client_id"] = result.client_id
        if result.brand_id:
            response["brand_id"] = result.brand_id

        return response, None


# Import for circular dependency resolution
from .time_utils import from_iso  # noqa: E402
