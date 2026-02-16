"""
Time OS V5 — Xero Integration Models

Models for Xero invoices, payments, and sync state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .base import BaseModel, generate_id, now_iso

# =============================================================================
# XERO ENUMS
# =============================================================================


class InvoiceType(StrEnum):
    """Type of invoice."""

    ADVANCE = "advance"
    PROGRESS = "progress"
    FINAL = "final"
    RETAINER = "retainer"
    OTHER = "other"


class InvoiceStatus(StrEnum):
    """Xero invoice status."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUTHORISED = "AUTHORISED"
    PAID = "PAID"
    VOIDED = "VOIDED"
    DELETED = "DELETED"


class AgingBucket(StrEnum):
    """AR aging bucket."""

    PAID = "paid"
    NO_DUE_DATE = "no_due_date"
    CURRENT = "current"
    DAYS_1_30 = "1-30"
    DAYS_31_60 = "31-60"
    DAYS_61_90 = "61-90"
    DAYS_90_PLUS = "90+"


# =============================================================================
# XERO INVOICE
# =============================================================================


@dataclass
class XeroInvoice(BaseModel):
    """Xero invoice entity."""

    xero_invoice_id: str = ""

    # Invoice details
    invoice_number: str | None = None
    reference: str | None = None

    contact_id: str | None = None  # Xero contact ID
    client_id: str | None = None  # Our client ID

    # Type (detected)
    invoice_type: InvoiceType = InvoiceType.OTHER
    type_detection_method: str | None = None

    # Link to our entities
    project_id: str | None = None
    retainer_cycle_id: str | None = None

    # Financials
    subtotal: float | None = None
    tax: float | None = None
    total: float = 0.0
    currency: str = "AED"

    amount_due: float | None = None
    amount_paid: float = 0.0

    # Dates
    date_issued: str | None = None
    due_date: str | None = None
    fully_paid_date: str | None = None

    # Status
    status: InvoiceStatus | None = None

    # Sync
    synced_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("xinv")
        if isinstance(self.invoice_type, str):
            self.invoice_type = InvoiceType(self.invoice_type)
        if isinstance(self.status, str):
            self.status = InvoiceStatus(self.status)

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def days_overdue(self) -> int:
        """Calculate days overdue (0 if not overdue)."""
        if not self.due_date:
            return 0
        if self.status in (InvoiceStatus.PAID, InvoiceStatus.VOIDED):
            return 0

        try:
            due = datetime.fromisoformat(self.due_date[:10])
            today = datetime.now().date()
            if today > due.date():
                return (today - due.date()).days
            return 0
        except (ValueError, TypeError):
            return 0

    @property
    def aging_bucket(self) -> AgingBucket:
        """Get AR aging bucket."""
        if self.status in (InvoiceStatus.PAID, InvoiceStatus.VOIDED):
            return AgingBucket.PAID
        if not self.due_date:
            return AgingBucket.NO_DUE_DATE

        days = self.days_overdue

        if days == 0:
            return AgingBucket.CURRENT
        if days <= 30:
            return AgingBucket.DAYS_1_30
        if days <= 60:
            return AgingBucket.DAYS_31_60
        if days <= 90:
            return AgingBucket.DAYS_61_90
        return AgingBucket.DAYS_90_PLUS

    @property
    def is_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.status == InvoiceStatus.PAID

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        return self.days_overdue > 0

    @property
    def outstanding_amount(self) -> float:
        """Get outstanding amount."""
        return self.amount_due if self.amount_due is not None else (self.total - self.amount_paid)


# =============================================================================
# XERO PAYMENT
# =============================================================================


@dataclass
class XeroPayment(BaseModel):
    """Xero payment entity."""

    xero_payment_id: str = ""

    invoice_id: str | None = None  # Our invoice ID
    xero_invoice_id: str | None = None  # Xero invoice ID

    amount: float = 0.0
    currency: str = "AED"

    payment_date: str = ""

    # Timing relative to due date
    days_after_due: int | None = None  # Negative = early, positive = late

    # Sync
    synced_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = generate_id("xpmt")

    @property
    def is_early(self) -> bool:
        """Check if payment was early (before due date)."""
        return self.days_after_due is not None and self.days_after_due < 0

    @property
    def is_ontime(self) -> bool:
        """Check if payment was on time (on or before due date)."""
        return self.days_after_due is not None and self.days_after_due <= 0

    @property
    def is_late(self) -> bool:
        """Check if payment was late (after due date)."""
        return self.days_after_due is not None and self.days_after_due > 0


# =============================================================================
# XERO SYNC STATE
# =============================================================================


@dataclass
class XeroSyncState:
    """Xero sync state (singleton)."""

    id: str = "singleton"
    last_sync_at: str | None = None
    last_modified_since: str | None = None

    contacts_synced: int = 0
    invoices_synced: int = 0
    quotes_synced: int = 0
    payments_synced: int = 0

    errors: str | None = None  # JSON array of recent errors
    updated_at: str = field(default_factory=now_iso)

    def record_sync(
        self, contacts: int = 0, invoices: int = 0, quotes: int = 0, payments: int = 0
    ) -> None:
        """Record a sync operation."""
        self.last_sync_at = now_iso()
        self.contacts_synced += contacts
        self.invoices_synced += invoices
        self.quotes_synced += quotes
        self.payments_synced += payments
        self.updated_at = now_iso()

    def record_error(self, error: str) -> None:
        """Record a sync error."""
        from .base import json_dumps_safe, json_loads_safe

        errors = json_loads_safe(self.errors) or []
        errors.append({"error": error, "timestamp": now_iso()})
        # Keep last 10 errors
        self.errors = json_dumps_safe(errors[-10:])
        self.updated_at = now_iso()
