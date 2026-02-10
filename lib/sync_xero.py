"""
Xero → Clients sync.

Imports contacts from Xero with AR data.
Uses existing xero_client from engine/.
"""

import logging
from datetime import date, datetime
from typing import Any

from engine.xero_client import list_contacts, list_invoices

from lib.entities import create_client, find_client, update_client
from lib.store import get_connection, now_iso

logger = logging.getLogger(__name__)

log = logging.getLogger("moh_time_os.sync_xero")


def calculate_ar_aging(invoices: list[dict], contact_id: str) -> dict[str, Any]:
    """
    Calculate AR aging for a contact from their invoices.

    Returns dict with:
    - ar_total: Total outstanding
    - ar_overdue: Amount overdue (>30 days)
    - ar_aging_bucket: 'current', '30', '60', '90+'
    - oldest_invoice_days: Days since oldest unpaid invoice
    """
    today = date.today()
    contact_invoices = [
        inv
        for inv in invoices
        if inv.get("Contact", {}).get("ContactID") == contact_id
        and inv.get("Status") == "AUTHORISED"
        and inv.get("Type") == "ACCREC"  # Accounts Receivable
    ]

    if not contact_invoices:
        return {
            "ar_total": 0,
            "ar_overdue": 0,
            "ar_aging_bucket": None,
            "oldest_invoice_days": 0,
        }

    ar_total = sum(inv.get("AmountDue", 0) for inv in contact_invoices)

    # Calculate aging
    oldest_days = 0
    ar_overdue = 0

    for inv in contact_invoices:
        due_date_str = inv.get("DueDateString")
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                days_past = (today - due_date).days

                if days_past > oldest_days:
                    oldest_days = days_past

                if days_past > 30:
                    ar_overdue += inv.get("AmountDue", 0)
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse invoice due date: {e}")

    # Determine bucket
    if oldest_days >= 90:
        bucket = "90+"
    elif oldest_days >= 60:
        bucket = "60"
    elif oldest_days >= 30:
        bucket = "30"
    elif oldest_days > 0:
        bucket = "current"
    else:
        bucket = "current"

    return {
        "ar_total": ar_total,
        "ar_overdue": ar_overdue,
        "ar_aging_bucket": bucket,
        "oldest_invoice_days": oldest_days,
    }


def sync_xero_clients() -> tuple[int, int, int, list[str]]:
    """
    Sync contacts from Xero to Clients table.

    Returns:
        (created, updated, skipped, errors)
    """
    log.info("Starting Xero sync...")

    created = 0
    updated = 0
    skipped = 0
    errors = []

    try:
        # Fetch all contacts (customers)
        log.info("Fetching Xero contacts...")
        contacts = list_contacts(is_customer=True)
        log.info(f"Found {len(contacts)} customer contacts")

        # Fetch all invoices for AR calculation
        log.info("Fetching invoices for AR data...")
        invoices = list_invoices(status="AUTHORISED")
        log.info(f"Found {len(invoices)} authorised invoices")

        for contact in contacts:
            try:
                contact_id = contact.get("ContactID")
                name = contact.get("Name", "").strip()

                if not name:
                    skipped += 1
                    continue

                # Calculate AR for this contact
                ar_data = calculate_ar_aging(invoices, contact_id)

                # Check if client exists (by xero_contact_id)
                existing = find_client(xero_id=contact_id)

                if existing:
                    # Update financial data only (don't overwrite tier, health, notes)
                    update_client(
                        existing.id,
                        ar_total=ar_data["ar_total"],
                        ar_overdue=ar_data["ar_overdue"],
                        ar_aging_bucket=ar_data["ar_aging_bucket"],
                        last_synced_at=now_iso(),
                    )
                    updated += 1
                else:
                    # Create new client
                    create_client(
                        name=name,
                        xero_contact_id=contact_id,
                        source="xero",
                        ar_total=ar_data["ar_total"],
                        ar_overdue=ar_data["ar_overdue"],
                        ar_aging_bucket=ar_data["ar_aging_bucket"],
                        type="agency_client",
                        last_synced_at=now_iso(),
                    )
                    created += 1

            except (KeyError, TypeError) as e:
                # Data format issue - skip this contact
                errors.append(f"{contact.get('Name', 'Unknown')}: {e}")
                log.debug(f"Skipping contact due to data issue: {e}")
            except Exception as e:
                errors.append(f"{contact.get('Name', 'Unknown')}: {e}")
                log.error(
                    f"Error syncing contact {contact.get('Name')}: {e}", exc_info=True
                )

        log.info(
            f"Xero sync complete: {created} created, {updated} updated, {skipped} skipped"
        )

    except ImportError as e:
        errors.append(f"Xero client not available: {e}")
        log.warning(f"Xero client not available: {e}")
    except Exception as e:
        errors.append(f"Sync failed: {e}")
        log.error(f"Xero sync failed: {e}", exc_info=True)

    return created, updated, skipped, errors


def get_ar_summary() -> dict[str, Any]:
    """Get summary of AR status across all clients."""
    with get_connection() as conn:
        total_ar = (
            conn.execute("SELECT SUM(financial_ar_total) FROM clients").fetchone()[0]
            or 0
        )

        overdue_ar = (
            conn.execute("SELECT SUM(financial_ar_overdue) FROM clients").fetchone()[0]
            or 0
        )

        clients_with_ar = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE financial_ar_total > 0"
        ).fetchone()[0]

        clients_overdue = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE financial_ar_overdue > 0"
        ).fetchone()[0]

        # Top 5 by AR
        top_ar = conn.execute("""
            SELECT name, financial_ar_total, financial_ar_aging_bucket
            FROM clients
            WHERE financial_ar_total > 0
            ORDER BY financial_ar_total DESC
            LIMIT 5
        """).fetchall()

    return {
        "total_ar": total_ar,
        "overdue_ar": overdue_ar,
        "clients_with_ar": clients_with_ar,
        "clients_overdue": clients_overdue,
        "top_ar": [{"name": r[0], "amount": r[1], "bucket": r[2]} for r in top_ar],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info("=== Xero → Clients Sync ===\n")
    created, updated, skipped, errors = sync_xero_clients()

    logger.info("\nResults:")
    logger.info(f"  Created: {created}")
    logger.info(f"  Updated: {updated}")
    logger.info(f"  Skipped: {skipped}")
    logger.info(f"  Errors: {len(errors)}")
    if errors:
        logger.info("\nErrors:")
        for e in errors[:10]:
            logger.info(f"  - {e}")
    logger.info("\n=== AR Summary ===")
    summary = get_ar_summary()
    logger.info(f"  Total AR: {summary['total_ar']:,.0f} AED")
    logger.info(f"  Overdue AR: {summary['overdue_ar']:,.0f} AED")
    logger.info(f"  Clients with AR: {summary['clients_with_ar']}")
    logger.info(f"  Clients overdue: {summary['clients_overdue']}")
    if summary["top_ar"]:
        logger.info("\n  Top by AR:")
        for c in summary["top_ar"]:
            logger.info(f"    - {c['name']}: {c['amount']:,.0f} AED ({c['bucket']})")
