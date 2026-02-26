"""
Xero Collector - Full invoice sync from Xero.

Syncs ALL invoices (PAID + AUTHORISED) to the invoices table,
enabling accurate financial calculations for YTD, prior year, and lifetime revenue.
"""

import logging
import re
from datetime import date, datetime

from lib.state_store import get_store
import sqlite3

logger = logging.getLogger(__name__)


def parse_xero_date(value: str | None) -> str | None:
    """
    Parse Xero date formats to ISO date string (YYYY-MM-DD).

    Handles:
    - /Date(1530489600000+0000)/ format (milliseconds since epoch)
    - 2018-05-30T00:00:00 format (ISO datetime)
    - 2018-05-30 format (ISO date)
    """
    if not value:
        return None

    # Try /Date(ms+tz)/ format
    match = re.match(r"/Date\((\d+)[+-]\d+\)/", value)
    if match:
        ms = int(match.group(1))
        dt = datetime.utcfromtimestamp(ms / 1000)
        return dt.strftime("%Y-%m-%d")

    # Try ISO datetime format
    if "T" in value:
        return value[:10]

    # Already ISO date
    if len(value) >= 10 and value[4] == "-":
        return value[:10]

    return None


class XeroCollector:
    """
    Collector that syncs full invoice history from Xero.

    Stores all PAID and AUTHORISED invoices in the invoices table,
    with proper client_id linking and status tracking.
    """

    def __init__(self, config: dict, store=None):
        self.config = config
        self.store = store or get_store()
        self.sync_interval = config.get("sync_interval", 3600)

    def should_sync(self) -> bool:
        """Always sync when called."""
        return True

    def _find_client_id(self, contact_name: str) -> str | None:
        """Find client ID by contact name with fuzzy matching."""
        # Try exact match first
        clients = self.store.query(
            "SELECT id FROM clients WHERE LOWER(name) = LOWER(?) LIMIT 1",
            [contact_name],
        )
        if clients:
            return clients[0]["id"]

        # Try normalized name match
        clients = self.store.query(
            "SELECT id FROM clients WHERE LOWER(name_normalized) = LOWER(?) LIMIT 1",
            [contact_name],
        )
        if clients:
            return clients[0]["id"]

        # Try partial match
        clients = self.store.query(
            """SELECT id FROM clients
               WHERE LOWER(name) LIKE LOWER(?)
               OR LOWER(?) LIKE '%' || LOWER(name) || '%'
               LIMIT 1""",
            [f"%{contact_name}%", contact_name],
        )
        if clients:
            return clients[0]["id"]

        return None

    def _determine_invoice_status(
        self, xero_status: str, amount_due: float, due_date_str: str | None
    ) -> str:
        """
        Determine invoice status for storage.

        Returns: 'paid', 'sent', or 'overdue'
        """
        if xero_status == "PAID":
            return "paid"

        # AUTHORISED invoice - check if overdue
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str[:10], "%Y-%m-%d").date()
                if due_date < date.today() and amount_due > 0:
                    return "overdue"
            except ValueError:
                pass

        return "sent"

    def _transform_line_items(self, invoice_id: str, line_items: list) -> list[dict]:
        """Transform Xero line items to xero_line_items table rows."""
        rows = []
        for item in line_items:
            rows.append(
                {
                    "invoice_id": invoice_id,
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0) or 0),
                    "unit_amount": float(item.get("UnitAmount", 0) or 0),
                    "line_amount": float(item.get("LineAmount", 0) or 0),
                    "tax_type": item.get("TaxType"),
                    "tax_amount": float(item.get("TaxAmount", 0) or 0),
                    "account_code": item.get("AccountCode"),
                    "tracking_category": item.get("TrackingCategory", {}).get("Name")
                    if item.get("TrackingCategory")
                    else None,
                    "tracking_option": item.get("TrackingOption", {}).get("Name")
                    if item.get("TrackingOption")
                    else None,
                }
            )
        return rows

    def _transform_contacts(self, contacts: list) -> list[dict]:
        """Transform Xero contacts to xero_contacts table rows."""
        rows = []
        now = datetime.now().isoformat()
        for contact in contacts:
            rows.append(
                {
                    "id": contact.get("ContactID"),
                    "name": contact.get("Name"),
                    "email": contact.get("EmailAddress"),
                    "phone": contact.get("Phones", [{}])[0].get("PhoneNumber")
                    if contact.get("Phones")
                    else None,
                    "account_number": contact.get("AccountNumber"),
                    "tax_number": contact.get("TaxNumber"),
                    "is_supplier": 1 if contact.get("IsSupplier") else 0,
                    "is_customer": 1 if contact.get("IsCustomer") else 0,
                    "default_currency": contact.get("DefaultCurrency"),
                    "outstanding_balance": float(
                        contact.get("SummaryDefault", {}).get("AccountsPayable", 0) or 0
                    )
                    if contact.get("IsSupplier")
                    else float(contact.get("SummaryDefault", {}).get("AccountsReceivable", 0) or 0),
                    "overdue_balance": None,  # Xero doesn't directly provide this per contact
                    "last_synced": now,
                }
            )
        return rows

    def _transform_credit_notes(self, credit_notes: list) -> list[dict]:
        """Transform Xero credit notes to xero_credit_notes table rows."""
        rows = []
        now = datetime.now().isoformat()
        for cn in credit_notes:
            contact = cn.get("Contact")
            contact_id = contact.get("ContactID") if contact else None
            rows.append(
                {
                    "id": cn.get("CreditNoteID"),
                    "contact_id": contact_id,
                    "date": parse_xero_date(cn.get("DateString") or cn.get("Date")),
                    "status": cn.get("Status"),
                    "total": float(cn.get("Total", 0) or 0),
                    "currency_code": cn.get("CurrencyCode"),
                    "remaining_credit": float(cn.get("RemainingCredit", 0) or 0),
                    "allocated_amount": None,  # Not directly in Xero response
                    "last_synced": now,
                }
            )
        return rows

    def _transform_bank_transactions(self, transactions: list) -> list[dict]:
        """Transform Xero bank transactions to xero_bank_transactions table rows."""
        rows = []
        now = datetime.now().isoformat()
        for txn in transactions:
            contact = txn.get("Contact")
            contact_id = contact.get("ContactID") if contact else None
            rows.append(
                {
                    "id": txn.get("BankTransactionID"),
                    "type": txn.get("Type"),  # ACCPAY or ACCREC
                    "contact_id": contact_id,
                    "date": parse_xero_date(txn.get("DateString") or txn.get("Date")),
                    "status": txn.get("Status"),
                    "total": float(txn.get("Total", 0) or 0),
                    "currency_code": txn.get("CurrencyCode"),
                    "reference": txn.get("Reference"),
                    "last_synced": now,
                }
            )
        return rows

    def _transform_tax_rates(self, tax_rates: list) -> list[dict]:
        """Transform Xero tax rates to xero_tax_rates table rows."""
        rows = []
        for rate in tax_rates:
            rows.append(
                {
                    "name": rate.get("Name"),
                    "tax_type": rate.get("TaxType"),
                    "effective_rate": float(rate.get("EffectiveRate", 0) or 0),
                    "status": rate.get("Status"),
                }
            )
        return rows

    def sync(self) -> dict:
        """
        Sync full invoice history and related data from Xero (~85% API coverage).

        Primary table:
        - invoices: ALL PAID and AUTHORISED invoices

        Secondary tables (non-blocking):
        - xero_line_items: line items from invoices
        - xero_contacts: customer/vendor contacts
        - xero_credit_notes: credit notes
        - xero_bank_transactions: bank transactions
        - xero_tax_rates: tax rate definitions

        Also updates client AR summary fields.
        """
        try:
            from engine.xero_client import (
                list_bank_transactions,
                list_contacts,
                list_credit_notes,
                list_invoices,
                list_tax_rates,
            )

            now = datetime.now().isoformat()
            today = date.today()

            # Fetch all invoices from Xero
            logger.info("Fetching PAID invoices from Xero...")
            paid_invoices = list_invoices(status="PAID")

            logger.info("Fetching AUTHORISED invoices from Xero...")
            authorised_invoices = list_invoices(status="AUTHORISED")

            all_invoices = paid_invoices + authorised_invoices
            logger.info(
                f"Total invoices to process: {len(all_invoices)} ({len(paid_invoices)} paid, {len(authorised_invoices)} authorised)"
            )

            # Fetch secondary data (non-blocking)
            try:
                logger.info("Fetching contacts from Xero...")
                all_contacts = list_contacts()
                logger.info(f"Found {len(all_contacts)} contacts")
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                logger.warning(f"Failed to fetch contacts: {e}")
                all_contacts = []

            try:
                logger.info("Fetching credit notes from Xero...")
                all_credit_notes = list_credit_notes()
                logger.info(f"Found {len(all_credit_notes)} credit notes")
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                logger.warning(f"Failed to fetch credit notes: {e}")
                all_credit_notes = []

            try:
                logger.info("Fetching bank transactions from Xero...")
                all_bank_transactions = list_bank_transactions()
                logger.info(f"Found {len(all_bank_transactions)} bank transactions")
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                logger.warning(f"Failed to fetch bank transactions: {e}")
                all_bank_transactions = []

            try:
                logger.info("Fetching tax rates from Xero...")
                all_tax_rates = list_tax_rates()
                logger.info(f"Found {len(all_tax_rates)} tax rates")
            except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                logger.warning(f"Failed to fetch tax rates: {e}")
                all_tax_rates = []

            # Clear old Xero invoices
            self.store.query("DELETE FROM invoices WHERE source = 'xero'")

            # Build client mapping cache
            client_cache = {}

            # Process and store invoices
            invoices_stored = 0
            clients_with_invoices = set()
            ar_by_client = {}  # client_id -> {total, overdue, max_days}

            for inv in all_invoices:
                # Skip non-receivables (bills, etc.)
                if inv.get("Type") != "ACCREC":
                    continue

                contact_name = inv.get("Contact", {}).get("Name", "Unknown")
                inv_number = inv.get("InvoiceNumber", f"INV-{invoices_stored}")
                xero_status = inv.get("Status", "AUTHORISED")

                # Get amounts
                total_amount = float(inv.get("Total", 0) or 0)
                amount_due = float(inv.get("AmountDue", 0) or 0)

                # Get dates (using proper parser for Xero formats)
                issue_date = parse_xero_date(inv.get("DateString") or inv.get("Date"))
                due_date = parse_xero_date(inv.get("DueDateString"))
                payment_date = parse_xero_date(inv.get("FullyPaidOnDate"))

                # Find or cache client ID
                if contact_name not in client_cache:
                    client_cache[contact_name] = self._find_client_id(contact_name)
                client_id = client_cache[contact_name]

                # Determine status
                status = self._determine_invoice_status(xero_status, amount_due, due_date)

                # Calculate days overdue for AR tracking
                days_overdue = 0
                if status == "overdue" and due_date:
                    try:
                        due_dt = datetime.strptime(due_date, "%Y-%m-%d").date()
                        days_overdue = (today - due_dt).days
                    except ValueError:
                        pass

                # Determine aging bucket
                if days_overdue >= 90:
                    aging = "90+"
                elif days_overdue >= 61:
                    aging = "61-90"
                elif days_overdue >= 31:
                    aging = "31-60"
                elif days_overdue >= 1:
                    aging = "1-30"
                else:
                    aging = "current"

                # Generate unique ID
                inv_id = f"xero_{inv_number.replace(' ', '_').replace('/', '-').replace('#', '')}"

                # Store invoice
                try:
                    self.store.insert(
                        "invoices",
                        {
                            "id": inv_id,
                            "source": "xero",
                            "external_id": inv_number,
                            "client_id": client_id,
                            "client_name": contact_name,
                            "amount": total_amount,  # Store full invoice amount, not just amount_due
                            "currency": inv.get("CurrencyCode", "AED"),
                            "issue_date": issue_date,
                            "due_date": due_date,
                            "status": status,
                            "aging_bucket": aging if status != "paid" else None,
                            "payment_date": payment_date,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    invoices_stored += 1

                    if client_id:
                        clients_with_invoices.add(client_id)

                        # Track AR for outstanding invoices
                        if status in ("sent", "overdue"):
                            if client_id not in ar_by_client:
                                ar_by_client[client_id] = {
                                    "total": 0,
                                    "overdue": 0,
                                    "max_days": 0,
                                }
                            ar_by_client[client_id]["total"] += amount_due
                            if status == "overdue":
                                ar_by_client[client_id]["overdue"] += amount_due
                                ar_by_client[client_id]["max_days"] = max(
                                    ar_by_client[client_id]["max_days"], days_overdue
                                )

                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    logger.warning(f"Failed to store invoice {inv_number}: {e}")

            # Update client AR fields
            ar_updated = 0
            for client_id, ar_data in ar_by_client.items():
                days = ar_data["max_days"]
                if days >= 90:
                    bucket = "90+"
                elif days >= 60:
                    bucket = "60"
                elif days >= 30:
                    bucket = "30"
                else:
                    bucket = "current"

                self.store.update(
                    "clients",
                    client_id,
                    {
                        "financial_ar_total": ar_data["total"],
                        "financial_ar_overdue": ar_data["overdue"],
                        "financial_ar_aging_bucket": bucket,
                        "updated_at": now,
                    },
                )
                ar_updated += 1

            # Clear AR for clients with no outstanding invoices
            for client_id in clients_with_invoices:
                if client_id not in ar_by_client:
                    self.store.update(
                        "clients",
                        client_id,
                        {
                            "financial_ar_total": 0,
                            "financial_ar_overdue": 0,
                            "financial_ar_aging_bucket": None,
                            "updated_at": now,
                        },
                    )

            # Store secondary tables (non-blocking)
            secondary_stats = {
                "line_items": 0,
                "contacts": 0,
                "credit_notes": 0,
                "bank_transactions": 0,
                "tax_rates": 0,
            }

            # Line items from invoices
            line_items_rows = []
            for inv in all_invoices:
                if inv.get("Type") != "ACCREC":
                    continue
                inv_number = inv.get("InvoiceNumber", f"INV-{invoices_stored}")
                inv_id = f"xero_{inv_number.replace(' ', '_').replace('/', '-').replace('#', '')}"
                line_items = inv.get("LineItems", [])
                if line_items:
                    rows = self._transform_line_items(inv_id, line_items)
                    line_items_rows.extend(rows)

            if line_items_rows:
                try:
                    stored = self.store.insert_many("xero_line_items", line_items_rows)
                    secondary_stats["line_items"] = stored
                    logger.info(f"Stored {stored} line items")
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    logger.warning(f"Failed to store line_items: {e}")

            # Contacts
            if all_contacts:
                try:
                    contacts_rows = self._transform_contacts(all_contacts)
                    stored = self.store.insert_many("xero_contacts", contacts_rows)
                    secondary_stats["contacts"] = stored
                    logger.info(f"Stored {stored} contacts")
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    logger.warning(f"Failed to store contacts: {e}")

            # Credit notes
            if all_credit_notes:
                try:
                    credit_notes_rows = self._transform_credit_notes(all_credit_notes)
                    stored = self.store.insert_many("xero_credit_notes", credit_notes_rows)
                    secondary_stats["credit_notes"] = stored
                    logger.info(f"Stored {stored} credit notes")
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    logger.warning(f"Failed to store credit_notes: {e}")

            # Bank transactions
            if all_bank_transactions:
                try:
                    bank_txn_rows = self._transform_bank_transactions(all_bank_transactions)
                    stored = self.store.insert_many("xero_bank_transactions", bank_txn_rows)
                    secondary_stats["bank_transactions"] = stored
                    logger.info(f"Stored {stored} bank transactions")
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    logger.warning(f"Failed to store bank_transactions: {e}")

            # Tax rates
            if all_tax_rates:
                try:
                    tax_rates_rows = self._transform_tax_rates(all_tax_rates)
                    stored = self.store.insert_many("xero_tax_rates", tax_rates_rows)
                    secondary_stats["tax_rates"] = stored
                    logger.info(f"Stored {stored} tax rates")
                except (sqlite3.Error, ValueError, OSError, KeyError) as e:
                    logger.warning(f"Failed to store tax_rates: {e}")

            return {
                "invoices_stored": invoices_stored,
                "paid_invoices": len(paid_invoices),
                "authorised_invoices": len(authorised_invoices),
                "clients_with_invoices": len(clients_with_invoices),
                "clients_ar_updated": ar_updated,
                "secondary": secondary_stats,
                "timestamp": now,
            }

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            logger.exception(f"Xero sync failed: {e}")
            return {"error": str(e), "synced": 0}


def sync():
    """Run Xero sync."""
    collector = XeroCollector({})
    return collector.sync()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = sync()
    print(f"Xero sync result: {result}")
