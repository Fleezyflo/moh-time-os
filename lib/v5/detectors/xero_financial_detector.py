"""
Time OS V5 — Xero Financial Detector

Detects signals from Xero AR data (collected JSON).
"""

import logging
from datetime import datetime

from ..data_loader import get_data_loader
from ..database import Database
from ..models import Signal, SignalSource
from .base import SignalDetector

logger = logging.getLogger(__name__)


class XeroFinancialDetector(SignalDetector):
    """
    Detects signals from Xero invoice/AR data.

    Reads from out/xero-ar.json (collector output).

    Signal Types:
    - invoice_overdue_30: Invoice 31-60 days overdue
    - invoice_overdue_60: Invoice 61-90 days overdue
    - invoice_overdue_90: Invoice 90+ days overdue
    """

    detector_id = "xero_financial"
    detector_version = "5.0.0"
    signal_types = ["invoice_overdue_30", "invoice_overdue_60", "invoice_overdue_90"]

    def __init__(self, db: Database):
        super().__init__(db)
        self.loader = get_data_loader()

    def detect(self) -> list[Signal]:
        """Run detection and return signals."""
        self.log_detection_start()
        self.load_existing_signals()

        signals = []
        signals.extend(self._detect_overdue_invoices())

        self.log_detection_end(len(signals))
        return signals

    def _detect_overdue_invoices(self) -> list[Signal]:
        """Detect overdue invoices by aging bucket."""
        signals = []
        invoices = self.loader.get_overdue_invoices()

        for inv in invoices:
            inv_number = inv.get("number")
            if not inv_number:
                continue

            days_overdue = inv.get("days_overdue", 0)

            # Determine bucket and signal type
            if days_overdue >= 90:
                signal_type = "invoice_overdue_90"
                magnitude = 1.0
            elif days_overdue >= 60:
                signal_type = "invoice_overdue_60"
                magnitude = 0.8
            elif days_overdue >= 30:
                signal_type = "invoice_overdue_30"
                magnitude = 0.5
            else:
                # Under 30 days - skip for now
                continue

            # Skip if signal exists
            if self.signal_exists(signal_type, inv_number):
                continue

            amount = inv.get("amount_due", 0)

            # Get scope IDs
            scope = self.loader.get_scope_for_invoice(inv)

            signal = self.create_signal(
                signal_type=signal_type,
                valence=-1,
                magnitude=magnitude,
                entity_type="invoice",
                entity_id=inv_number,
                source_type=SignalSource.XERO,
                source_id=inv_number,
                value={
                    "invoice_number": inv_number,
                    "contact": inv.get("contact"),
                    "amount_due": amount,
                    "currency": inv.get("currency", "AED"),
                    "due_date": inv.get("due_date"),
                    "days_overdue": days_overdue,
                },
                occurred_at=datetime.fromisoformat(inv["due_date"])
                if inv.get("due_date")
                else datetime.now(),
                scope_client_id=scope.get("client_id"),
                detection_confidence=1.0,
                attribution_confidence=0.9 if scope.get("client_id") else 0.5,
            )

            signals.append(signal)
            self.log_signal(signal)

        logger.info(f"[{self.detector_id}] Detected {len(signals)} overdue invoices")
        return signals
