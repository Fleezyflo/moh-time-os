"""
Org Settings — Spec Section 0.1

Manages organization-level settings including timezone and currency.
"""

import logging
import sqlite3

from .time_utils import DEFAULT_ORG_TZ, validate_org_timezone

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_BASE_CURRENCY = "AED"

# Valid currency codes (ISO 4217)
VALID_CURRENCIES = frozenset(
    [
        "AED",
        "USD",
        "EUR",
        "GBP",
        "CHF",
        "JPY",
        "CNY",
        "HKD",
        "SGD",
        "AUD",
        "CAD",
        "INR",
        "SAR",
        "QAR",
        "KWD",
        "BHD",
        "OMR",
        "EGP",
        "JOD",
        "LBP",
    ]
)


class OrgSettings:
    """
    Organization settings container.

    Spec: 0.1 org.base_currency, org.timezone

    MVP: Single-currency, fixed timezone per org.
    """

    def __init__(
        self,
        timezone: str = DEFAULT_ORG_TZ,
        base_currency: str = DEFAULT_BASE_CURRENCY,
        finance_calc_version: str = "v1",
    ):
        # Validate timezone
        valid, reason = validate_org_timezone(timezone)
        if not valid:
            raise ValueError(reason)

        # Validate currency
        if base_currency not in VALID_CURRENCIES:
            raise ValueError(f"Invalid base currency: {base_currency}")

        self.timezone = timezone
        self.base_currency = base_currency
        self.finance_calc_version = finance_calc_version

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "timezone": self.timezone,
            "base_currency": self.base_currency,
            "finance_calc_version": self.finance_calc_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrgSettings":
        """Deserialize from dict."""
        return cls(
            timezone=data.get("timezone", DEFAULT_ORG_TZ),
            base_currency=data.get("base_currency", DEFAULT_BASE_CURRENCY),
            finance_calc_version=data.get("finance_calc_version", "v1"),
        )


def get_org_settings(conn) -> OrgSettings:
    """
    Load org settings from database.

    Args:
        conn: Database connection

    Returns:
        OrgSettings instance (defaults if table doesn't exist)
    """
    try:
        cursor = conn.execute("""
            SELECT timezone, base_currency, finance_calc_version
            FROM org_settings
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return OrgSettings(
                timezone=row[0] or DEFAULT_ORG_TZ,
                base_currency=row[1] or DEFAULT_BASE_CURRENCY,
                finance_calc_version=row[2] or "v1",
            )
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.debug(
            "get_org_settings: table missing or inaccessible, returning default settings: %s", e
        )

    return OrgSettings()  # Return defaults


def save_org_settings(conn, settings: OrgSettings) -> None:
    """
    Save org settings to database.

    Creates table if it doesn't exist.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS org_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            timezone TEXT NOT NULL DEFAULT 'Asia/Dubai',
            base_currency TEXT NOT NULL DEFAULT 'AED',
            finance_calc_version TEXT NOT NULL DEFAULT 'v1',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    from .time_utils import now_iso

    now = now_iso()

    conn.execute(
        """
        INSERT INTO org_settings (id, timezone, base_currency, finance_calc_version, created_at, updated_at)
        VALUES (1, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            timezone = excluded.timezone,
            base_currency = excluded.base_currency,
            finance_calc_version = excluded.finance_calc_version,
            updated_at = excluded.updated_at
    """,
        (
            settings.timezone,
            settings.base_currency,
            settings.finance_calc_version,
            now,
            now,
        ),
    )

    conn.commit()


def validate_invoice_currency(invoice_currency: str, org_settings: OrgSettings) -> tuple:
    """
    Validate invoice currency against org base currency.

    Spec: 0.1 Currency Handling (single-currency MVP)

    Args:
        invoice_currency: Currency code on invoice
        org_settings: Organization settings

    Returns:
        Tuple of (valid: bool, should_flag: bool, reason: str or None)
        - valid: True if currency is recognized
        - should_flag: True if currency differs from base (create DQ signal)
        - reason: Explanation if should_flag is True
    """
    if invoice_currency not in VALID_CURRENCIES:
        return False, True, f"Unknown currency: {invoice_currency}"

    if invoice_currency != org_settings.base_currency:
        return (
            True,
            True,
            f"Non-base currency: {invoice_currency} (base: {org_settings.base_currency})",
        )

    return True, False, None


def create_currency_mismatch_signal(
    invoice_id: str, invoice_currency: str, org_settings: OrgSettings
) -> dict:
    """
    Create a flagged signal for currency mismatch.

    Spec: 0.1 Multi-currency flagging

    Args:
        invoice_id: Invoice ID
        invoice_currency: Currency on invoice
        org_settings: Organization settings

    Returns:
        Signal dict for insertion
    """
    import uuid

    from .time_utils import now_iso

    return {
        "id": str(uuid.uuid4()),
        "source": "xero",
        "source_id": f"currency_mismatch_{invoice_id}",
        "client_id": None,  # To be filled by caller
        "sentiment": "bad",
        "signal_type": "invoice_currency_mismatch",
        "summary": f"Invoice {invoice_id} uses {invoice_currency} instead of {org_settings.base_currency}",
        "observed_at": now_iso(),
        "evidence": {
            "kind": "xero_invoice",
            "display_text": f"Invoice currency mismatch: {invoice_currency}",
            "url": None,
            "source_system": "xero",
            "source_id": invoice_id,
            "payload": {
                "invoice_id": invoice_id,
                "invoice_currency": invoice_currency,
                "base_currency": org_settings.base_currency,
            },
        },
    }


# SQL migration for org_settings table
ORG_SETTINGS_MIGRATION = """
-- Org Settings Table (Spec 0.1)
CREATE TABLE IF NOT EXISTS org_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    timezone TEXT NOT NULL DEFAULT 'Asia/Dubai',
    base_currency TEXT NOT NULL DEFAULT 'AED',
    finance_calc_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Insert default settings if not exists
INSERT OR IGNORE INTO org_settings (id, timezone, base_currency, finance_calc_version, created_at, updated_at)
VALUES (1, 'Asia/Dubai', 'AED', 'v1', datetime('now'), datetime('now'));
"""
