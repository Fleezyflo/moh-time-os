"""
Xero Operational Intelligence — AR summaries and outstanding invoices.

Extracted from legacy collectors/xero_ops.py for use by enrollment_detector
and other modules that need Xero AR data without a full collector sync.
"""

import logging
from datetime import date, datetime

from engine.xero_client import list_invoices

logger = logging.getLogger(__name__)


def get_outstanding_invoices() -> list:
    """Get all outstanding (unpaid) invoices."""
    try:
        invoices = list_invoices(status="AUTHORISED")
        outstanding = []

        for inv in invoices:
            if inv.get("Type") != "ACCREC":  # Only receivables
                continue

            amount_due = float(inv.get("AmountDue", 0))
            if amount_due <= 0:
                continue

            due_date = inv.get("DueDateString", "")
            contact = inv.get("Contact", {}).get("Name", "Unknown")
            inv_number = inv.get("InvoiceNumber", "")

            # Check if overdue
            is_overdue = False
            days_overdue = 0
            if due_date:
                try:
                    due_dt = datetime.strptime(due_date, "%Y-%m-%dT%H:%M:%S")
                    if due_dt.date() < date.today():
                        is_overdue = True
                        days_overdue = (date.today() - due_dt.date()).days
                except ValueError as e:
                    logger.warning(
                        "Invoice %s has unparseable due_date '%s': %s",
                        inv_number,
                        due_date,
                        e,
                    )

            outstanding.append(
                {
                    "number": inv_number,
                    "contact": contact,
                    "amount_due": amount_due,
                    "currency": inv.get("CurrencyCode", "AED"),
                    "due_date": due_date[:10] if due_date else None,
                    "is_overdue": is_overdue,
                    "days_overdue": days_overdue,
                }
            )

        # Sort by overdue first, then by amount
        outstanding.sort(key=lambda x: (-x["days_overdue"], -x["amount_due"]))
        return outstanding

    except (OSError, ValueError, KeyError) as e:
        logger.error("Error fetching invoices: %s", e)
        return []


def get_ar_summary() -> dict:
    """Get accounts receivable summary."""
    outstanding = get_outstanding_invoices()

    total_ar = sum(inv["amount_due"] for inv in outstanding)
    overdue = [inv for inv in outstanding if inv["is_overdue"]]
    total_overdue = sum(inv["amount_due"] for inv in overdue)

    return {
        "total_outstanding": len(outstanding),
        "total_ar": total_ar,
        "overdue_count": len(overdue),
        "overdue_amount": total_overdue,
        "invoices": outstanding,
        "overdue_invoices": overdue,
    }


def get_all_client_revenue() -> list:
    """Get all PAID invoices to calculate client revenue."""
    try:
        paid_invoices = list_invoices(status="PAID")
        authorised_invoices = list_invoices(status="AUTHORISED")

        all_invoices = paid_invoices + authorised_invoices
        revenue_by_client: dict[str, dict] = {}

        current_year = date.today().year
        prior_year = current_year - 1

        for inv in all_invoices:
            if inv.get("Type") != "ACCREC":
                continue

            contact = inv.get("Contact", {}).get("Name", "Unknown")
            total = float(inv.get("Total", 0) or inv.get("SubTotal", 0) or 0)

            if contact not in revenue_by_client:
                revenue_by_client[contact] = {
                    "contact": contact,
                    "lifetime_revenue": 0,
                    "prior_year_revenue": 0,
                    "ytd_revenue": 0,
                    "invoice_count": 0,
                }

            revenue_by_client[contact]["lifetime_revenue"] += total
            revenue_by_client[contact]["invoice_count"] += 1

            inv_date_str = inv.get("DateString", "") or inv.get("Date", "")
            if inv_date_str:
                try:
                    inv_date = datetime.strptime(inv_date_str[:10], "%Y-%m-%d")
                    if inv_date.year == current_year:
                        revenue_by_client[contact]["ytd_revenue"] += total
                    elif inv_date.year == prior_year:
                        revenue_by_client[contact]["prior_year_revenue"] += total
                except ValueError:
                    logger.debug("Cannot parse invoice date: %s", inv_date_str[:10])

        result = sorted(revenue_by_client.values(), key=lambda x: -x["lifetime_revenue"])
        return result

    except (OSError, ValueError, KeyError) as e:
        logger.error("Error fetching revenue data: %s", e)
        return []
