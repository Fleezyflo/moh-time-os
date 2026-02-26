"""
Tests for expanded Xero Collector (CS-5.2).

Tests the ~85% API coverage implementation including:
- Line items extraction and transformation
- Contacts collection and transformation
- Credit notes collection and transformation
- Bank transactions collection and transformation
- Tax rates collection and transformation
- Multi-table storage in sync()

All tests use mocks - NO live API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.collectors.xero import XeroCollector, parse_xero_date
from lib.state_store import StateStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_store():
    """Mock StateStore for testing."""
    store = MagicMock(spec=StateStore)
    store.insert_many.return_value = 5
    store.insert.return_value = None
    store.update.return_value = None
    store.query.return_value = []
    return store


@pytest.fixture
def collector(mock_store):
    """Create a XeroCollector with mocked store."""
    config = {"sync_interval": 3600}
    collector = XeroCollector(config=config, store=mock_store)
    return collector


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================


@pytest.fixture
def mock_line_items():
    """Mock line items from an invoice."""
    return [
        {
            "Description": "Professional Services - Web Development",
            "Quantity": 40,
            "UnitAmount": 150.00,
            "LineAmount": 6000.00,
            "TaxType": "Tax on Sales",
            "TaxAmount": 600.00,
            "AccountCode": "200",
            "TrackingCategory": {"Name": "Project"},
            "TrackingOption": {"Name": "Website Redesign"},
        },
        {
            "Description": "Hosting and Maintenance",
            "Quantity": 1,
            "UnitAmount": 500.00,
            "LineAmount": 500.00,
            "TaxType": "Tax on Sales",
            "TaxAmount": 50.00,
            "AccountCode": "210",
            "TrackingCategory": None,
            "TrackingOption": None,
        },
    ]


@pytest.fixture
def mock_invoice_with_line_items():
    """Mock invoice with line items."""
    return {
        "InvoiceID": "inv_123",
        "InvoiceNumber": "INV-001",
        "Type": "ACCREC",
        "Status": "PAID",
        "Contact": {"ContactID": "cont_456", "Name": "ABC Corp"},
        "DateString": "/Date(1530489600000+0000)/",
        "DueDateString": "/Date(1530835200000+0000)/",
        "FullyPaidOnDate": "/Date(1531267200000+0000)/",
        "Total": 6550.00,
        "AmountDue": 0.00,
        "CurrencyCode": "AED",
        "LineItems": [
            {
                "Description": "Professional Services",
                "Quantity": 40,
                "UnitAmount": 150.00,
                "LineAmount": 6000.00,
                "TaxType": "Tax on Sales",
                "TaxAmount": 600.00,
                "AccountCode": "200",
                "TrackingCategory": {"Name": "Project"},
                "TrackingOption": {"Name": "Website"},
            },
            {
                "Description": "Hosting",
                "Quantity": 1,
                "UnitAmount": 500.00,
                "LineAmount": 500.00,
                "TaxType": "Tax on Sales",
                "TaxAmount": 50.00,
                "AccountCode": "210",
                "TrackingCategory": None,
                "TrackingOption": None,
            },
        ],
    }


@pytest.fixture
def mock_contacts():
    """Mock contacts from Xero."""
    return [
        {
            "ContactID": "cont_123",
            "Name": "ABC Corporation",
            "EmailAddress": "contact@abc.com",
            "Phones": [{"PhoneNumber": "+971501234567"}],
            "AccountNumber": "ACC-001",
            "TaxNumber": "123456789",
            "IsSupplier": False,
            "IsCustomer": True,
            "DefaultCurrency": "AED",
            "SummaryDefault": {
                "AccountsReceivable": 12500.00,
                "AccountsPayable": 0.00,
            },
        },
        {
            "ContactID": "cont_124",
            "Name": "XYZ Supplies Ltd",
            "EmailAddress": "sales@xyz.com",
            "Phones": [{"PhoneNumber": "+971509876543"}],
            "AccountNumber": "SUP-001",
            "TaxNumber": "987654321",
            "IsSupplier": True,
            "IsCustomer": False,
            "DefaultCurrency": "AED",
            "SummaryDefault": {
                "AccountsReceivable": 0.00,
                "AccountsPayable": 5000.00,
            },
        },
    ]


@pytest.fixture
def mock_credit_notes():
    """Mock credit notes from Xero."""
    return [
        {
            "CreditNoteID": "cn_123",
            "Contact": {"ContactID": "cont_123", "Name": "ABC Corporation"},
            "DateString": "/Date(1530489600000+0000)/",
            "Status": "AUTHORISED",
            "Total": 1000.00,
            "CurrencyCode": "AED",
            "RemainingCredit": 500.00,
        },
        {
            "CreditNoteID": "cn_124",
            "Contact": {"ContactID": "cont_125", "Name": "Another Client"},
            "DateString": "/Date(1531267200000+0000)/",
            "Status": "PAID",
            "Total": 2000.00,
            "CurrencyCode": "AED",
            "RemainingCredit": 0.00,
        },
    ]


@pytest.fixture
def mock_bank_transactions():
    """Mock bank transactions from Xero."""
    return [
        {
            "BankTransactionID": "bt_123",
            "Type": "ACCPAY",
            "Contact": {"ContactID": "cont_124", "Name": "XYZ Supplies"},
            "DateString": "/Date(1530489600000+0000)/",
            "Status": "AUTHORISED",
            "Total": 5000.00,
            "CurrencyCode": "AED",
            "Reference": "Payment for supplies",
        },
        {
            "BankTransactionID": "bt_124",
            "Type": "ACCREC",
            "Contact": {"ContactID": "cont_123", "Name": "ABC Corp"},
            "DateString": "/Date(1530835200000+0000)/",
            "Status": "PAID",
            "Total": 6550.00,
            "CurrencyCode": "AED",
            "Reference": "Invoice INV-001 payment",
        },
    ]


@pytest.fixture
def mock_tax_rates():
    """Mock tax rates from Xero."""
    return [
        {
            "Name": "Tax on Sales",
            "TaxType": "OUTPUT",
            "EffectiveRate": 0.05,
            "Status": "ACTIVE",
        },
        {
            "Name": "Tax on Purchases",
            "TaxType": "INPUT",
            "EffectiveRate": 0.05,
            "Status": "ACTIVE",
        },
        {
            "Name": "Tax Exempt",
            "TaxType": "EXEMPTION",
            "EffectiveRate": 0.0,
            "Status": "ACTIVE",
        },
    ]


# =============================================================================
# PARSE_XERO_DATE TESTS
# =============================================================================


class TestParseXeroDate:
    """Tests for parse_xero_date helper function."""

    def test_parse_xero_date_format(self):
        """Should parse /Date(ms+tz)/ format."""
        result = parse_xero_date("/Date(1530489600000+0000)/")
        assert result is not None
        assert len(result) == 10  # YYYY-MM-DD format

    def test_parse_iso_datetime_format(self):
        """Should parse ISO datetime format."""
        result = parse_xero_date("2018-07-01T00:00:00")
        assert result == "2018-07-01"

    def test_parse_iso_date_format(self):
        """Should parse ISO date format."""
        result = parse_xero_date("2018-07-01")
        assert result == "2018-07-01"

    def test_parse_none_value(self):
        """Should return None for None input."""
        result = parse_xero_date(None)
        assert result is None

    def test_parse_empty_string(self):
        """Should return None for empty string."""
        result = parse_xero_date("")
        assert result is None


# =============================================================================
# LINE ITEMS TRANSFORMATION TESTS
# =============================================================================


class TestTransformLineItems:
    """Tests for _transform_line_items method."""

    def test_transform_basic_line_item(self, collector):
        """Should correctly transform basic line item."""
        rows = collector._transform_line_items(
            "xero_INV-001",
            [
                {
                    "Description": "Service",
                    "Quantity": 10,
                    "UnitAmount": 100.00,
                    "LineAmount": 1000.00,
                    "TaxType": "Tax on Sales",
                    "TaxAmount": 50.00,
                    "AccountCode": "200",
                    "TrackingCategory": None,
                    "TrackingOption": None,
                }
            ],
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["invoice_id"] == "xero_INV-001"
        assert row["description"] == "Service"
        assert row["quantity"] == 10.0
        assert row["unit_amount"] == 100.0
        assert row["line_amount"] == 1000.0
        assert row["tax_type"] == "Tax on Sales"
        assert row["tax_amount"] == 50.0
        assert row["account_code"] == "200"

    def test_transform_multiple_line_items(self, collector, mock_line_items):
        """Should correctly transform multiple line items."""
        rows = collector._transform_line_items("xero_INV-001", mock_line_items)

        assert len(rows) == 2
        assert rows[0]["description"] == "Professional Services - Web Development"
        assert rows[0]["quantity"] == 40.0
        assert rows[0]["tracking_category"] == "Project"
        assert rows[0]["tracking_option"] == "Website Redesign"
        assert rows[1]["description"] == "Hosting and Maintenance"
        assert rows[1]["tracking_category"] is None

    def test_transform_line_items_with_missing_fields(self, collector):
        """Should handle missing fields gracefully."""
        rows = collector._transform_line_items(
            "xero_INV-001",
            [
                {
                    "Description": "Item",
                    "Quantity": None,
                    "UnitAmount": None,
                }
            ],
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["quantity"] == 0.0
        assert row["unit_amount"] == 0.0

    def test_transform_empty_line_items(self, collector):
        """Should return empty list for empty input."""
        rows = collector._transform_line_items("xero_INV-001", [])
        assert rows == []


# =============================================================================
# CONTACTS TRANSFORMATION TESTS
# =============================================================================


class TestTransformContacts:
    """Tests for _transform_contacts method."""

    def test_transform_customer_contact(self, collector):
        """Should correctly transform customer contact."""
        rows = collector._transform_contacts(
            [
                {
                    "ContactID": "cont_123",
                    "Name": "ABC Corp",
                    "EmailAddress": "contact@abc.com",
                    "Phones": [{"PhoneNumber": "+971501234567"}],
                    "AccountNumber": "ACC-001",
                    "TaxNumber": "123456789",
                    "IsSupplier": False,
                    "IsCustomer": True,
                    "DefaultCurrency": "AED",
                    "SummaryDefault": {
                        "AccountsReceivable": 12500.00,
                        "AccountsPayable": 0.00,
                    },
                }
            ]
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "cont_123"
        assert row["name"] == "ABC Corp"
        assert row["email"] == "contact@abc.com"
        assert row["phone"] == "+971501234567"
        assert row["is_customer"] == 1
        assert row["is_supplier"] == 0
        assert row["outstanding_balance"] == 12500.0

    def test_transform_supplier_contact(self, collector):
        """Should correctly transform supplier contact."""
        rows = collector._transform_contacts(
            [
                {
                    "ContactID": "cont_124",
                    "Name": "XYZ Supplies",
                    "EmailAddress": "sales@xyz.com",
                    "Phones": [{"PhoneNumber": "+971509876543"}],
                    "IsSupplier": True,
                    "IsCustomer": False,
                    "DefaultCurrency": "AED",
                    "SummaryDefault": {
                        "AccountsPayable": 5000.00,
                        "AccountsReceivable": 0.00,
                    },
                }
            ]
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["is_supplier"] == 1
        assert row["is_customer"] == 0
        assert row["outstanding_balance"] == 5000.0

    def test_transform_multiple_contacts(self, collector, mock_contacts):
        """Should correctly transform multiple contacts."""
        rows = collector._transform_contacts(mock_contacts)

        assert len(rows) == 2
        assert rows[0]["name"] == "ABC Corporation"
        assert rows[0]["is_customer"] == 1
        assert rows[1]["name"] == "XYZ Supplies Ltd"
        assert rows[1]["is_supplier"] == 1

    def test_transform_contact_with_no_phone(self, collector):
        """Should handle missing phone gracefully."""
        rows = collector._transform_contacts(
            [
                {
                    "ContactID": "cont_125",
                    "Name": "No Phone Corp",
                    "EmailAddress": "test@example.com",
                    "Phones": [],
                    "IsCustomer": True,
                    "IsSupplier": False,
                }
            ]
        )

        assert len(rows) == 1
        assert rows[0]["phone"] is None


# =============================================================================
# CREDIT NOTES TRANSFORMATION TESTS
# =============================================================================


class TestTransformCreditNotes:
    """Tests for _transform_credit_notes method."""

    def test_transform_credit_note(self, collector):
        """Should correctly transform credit note."""
        rows = collector._transform_credit_notes(
            [
                {
                    "CreditNoteID": "cn_123",
                    "Contact": {"ContactID": "cont_123"},
                    "DateString": "/Date(1530489600000+0000)/",
                    "Status": "AUTHORISED",
                    "Total": 1000.00,
                    "CurrencyCode": "AED",
                    "RemainingCredit": 500.00,
                }
            ]
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "cn_123"
        assert row["contact_id"] == "cont_123"
        assert row["date"] is not None
        assert row["status"] == "AUTHORISED"
        assert row["total"] == 1000.0
        assert row["remaining_credit"] == 500.0

    def test_transform_multiple_credit_notes(self, collector, mock_credit_notes):
        """Should correctly transform multiple credit notes."""
        rows = collector._transform_credit_notes(mock_credit_notes)

        assert len(rows) == 2
        assert rows[0]["status"] == "AUTHORISED"
        assert rows[1]["status"] == "PAID"

    def test_transform_credit_note_with_no_contact(self, collector):
        """Should handle missing contact gracefully."""
        rows = collector._transform_credit_notes(
            [
                {
                    "CreditNoteID": "cn_124",
                    "Contact": None,
                    "DateString": "/Date(1530489600000+0000)/",
                    "Status": "PAID",
                    "Total": 2000.00,
                }
            ]
        )

        assert len(rows) == 1
        assert rows[0]["contact_id"] is None


# =============================================================================
# BANK TRANSACTIONS TRANSFORMATION TESTS
# =============================================================================


class TestTransformBankTransactions:
    """Tests for _transform_bank_transactions method."""

    def test_transform_bank_transaction(self, collector):
        """Should correctly transform bank transaction."""
        rows = collector._transform_bank_transactions(
            [
                {
                    "BankTransactionID": "bt_123",
                    "Type": "ACCPAY",
                    "Contact": {"ContactID": "cont_124"},
                    "DateString": "/Date(1530489600000+0000)/",
                    "Status": "AUTHORISED",
                    "Total": 5000.00,
                    "CurrencyCode": "AED",
                    "Reference": "Payment for supplies",
                }
            ]
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "bt_123"
        assert row["type"] == "ACCPAY"
        assert row["contact_id"] == "cont_124"
        assert row["date"] is not None
        assert row["total"] == 5000.0
        assert row["reference"] == "Payment for supplies"

    def test_transform_multiple_bank_transactions(self, collector, mock_bank_transactions):
        """Should correctly transform multiple transactions."""
        rows = collector._transform_bank_transactions(mock_bank_transactions)

        assert len(rows) == 2
        assert rows[0]["type"] == "ACCPAY"
        assert rows[1]["type"] == "ACCREC"

    def test_transform_accrec_transaction(self, collector):
        """Should correctly identify ACCREC transactions."""
        rows = collector._transform_bank_transactions(
            [
                {
                    "BankTransactionID": "bt_124",
                    "Type": "ACCREC",
                    "Contact": {"ContactID": "cont_123"},
                    "DateString": "/Date(1530835200000+0000)/",
                    "Status": "PAID",
                    "Total": 6550.00,
                    "CurrencyCode": "AED",
                    "Reference": "Invoice payment",
                }
            ]
        )

        assert len(rows) == 1
        assert rows[0]["type"] == "ACCREC"


# =============================================================================
# TAX RATES TRANSFORMATION TESTS
# =============================================================================


class TestTransformTaxRates:
    """Tests for _transform_tax_rates method."""

    def test_transform_tax_rate(self, collector):
        """Should correctly transform tax rate."""
        rows = collector._transform_tax_rates(
            [
                {
                    "Name": "Tax on Sales",
                    "TaxType": "OUTPUT",
                    "EffectiveRate": 0.05,
                    "Status": "ACTIVE",
                }
            ]
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == "Tax on Sales"
        assert row["tax_type"] == "OUTPUT"
        assert row["effective_rate"] == 0.05
        assert row["status"] == "ACTIVE"

    def test_transform_multiple_tax_rates(self, collector, mock_tax_rates):
        """Should correctly transform multiple tax rates."""
        rows = collector._transform_tax_rates(mock_tax_rates)

        assert len(rows) == 3
        assert rows[0]["name"] == "Tax on Sales"
        assert rows[1]["name"] == "Tax on Purchases"
        assert rows[2]["name"] == "Tax Exempt"
        assert rows[2]["effective_rate"] == 0.0

    def test_transform_tax_rate_with_missing_fields(self, collector):
        """Should handle missing fields gracefully."""
        rows = collector._transform_tax_rates(
            [
                {
                    "Name": "Tax",
                    "TaxType": "OUTPUT",
                }
            ]
        )

        assert len(rows) == 1
        assert rows[0]["effective_rate"] == 0.0


# =============================================================================
# SYNC INTEGRATION TESTS
# =============================================================================


class TestSyncMultiTable:
    """Tests for sync method with multi-table storage."""

    @patch("engine.xero_client.list_tax_rates")
    @patch("engine.xero_client.list_bank_transactions")
    @patch("engine.xero_client.list_credit_notes")
    @patch("engine.xero_client.list_contacts")
    @patch("engine.xero_client.list_invoices")
    def test_sync_stores_all_secondary_tables(
        self,
        mock_list_invoices,
        mock_list_contacts,
        mock_list_credit_notes,
        mock_list_bank_transactions,
        mock_list_tax_rates,
    ):
        """Should store data in all secondary tables."""
        # Create collector with mock store
        mock_store = MagicMock(spec=StateStore)
        mock_store.insert_many.return_value = 5
        mock_store.insert.return_value = None
        mock_store.query.return_value = []
        collector = XeroCollector(config={}, store=mock_store)

        # Create test data
        invoice = {
            "InvoiceID": "inv_123",
            "InvoiceNumber": "INV-001",
            "Type": "ACCREC",
            "Status": "PAID",
            "Contact": {"ContactID": "cont_456", "Name": "ABC Corp"},
            "Date": "2018-07-01T00:00:00",
            "Total": 6550.0,
            "AmountDue": 0.0,
            "CurrencyCode": "AED",
            "LineItems": [],
        }

        # Setup mocks
        mock_list_invoices.return_value = [invoice]
        mock_list_contacts.return_value = []
        mock_list_credit_notes.return_value = []
        mock_list_bank_transactions.return_value = []
        mock_list_tax_rates.return_value = []

        # Run sync
        result = collector.sync()

        # Verify result structure
        assert "invoices_stored" in result
        assert "secondary" in result
        assert "timestamp" in result

        # Verify secondary stats exist
        secondary = result["secondary"]
        assert "line_items" in secondary
        assert "contacts" in secondary
        assert "credit_notes" in secondary
        assert "bank_transactions" in secondary
        assert "tax_rates" in secondary

    @patch("engine.xero_client.list_tax_rates")
    @patch("engine.xero_client.list_bank_transactions")
    @patch("engine.xero_client.list_credit_notes")
    @patch("engine.xero_client.list_contacts")
    @patch("engine.xero_client.list_invoices")
    def test_sync_handles_secondary_failures_gracefully(
        self,
        mock_list_invoices,
        mock_list_contacts,
        mock_list_credit_notes,
        mock_list_bank_transactions,
        mock_list_tax_rates,
    ):
        """Should not fail if secondary data fetch fails."""
        # Create collector with mock store
        mock_store = MagicMock(spec=StateStore)
        mock_store.insert.return_value = None
        mock_store.insert_many.return_value = 0
        mock_store.query.return_value = []
        collector = XeroCollector(config={}, store=mock_store)

        # Create minimal invoice
        invoice = {
            "InvoiceID": "inv_123",
            "InvoiceNumber": "INV-001",
            "Type": "ACCREC",
            "Status": "PAID",
            "Contact": {"ContactID": "cont_456", "Name": "ABC Corp"},
            "Date": "2018-07-01T00:00:00",
            "Total": 1000.0,
            "AmountDue": 0.0,
            "CurrencyCode": "AED",
            "LineItems": [],
        }

        # Setup mocks - only invoices work, others fail
        mock_list_invoices.return_value = [invoice]
        mock_list_contacts.side_effect = Exception("API error")
        mock_list_credit_notes.side_effect = Exception("API error")
        mock_list_bank_transactions.side_effect = Exception("API error")
        mock_list_tax_rates.side_effect = Exception("API error")

        # Run sync - should not raise
        result = collector.sync()

        # Should still have primary result
        assert "invoices_stored" in result or "error" not in result


# =============================================================================
# BACKWARD COMPATIBILITY TESTS
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing invoice sync."""

    @patch("engine.xero_client.list_tax_rates")
    @patch("engine.xero_client.list_bank_transactions")
    @patch("engine.xero_client.list_credit_notes")
    @patch("engine.xero_client.list_contacts")
    @patch("engine.xero_client.list_invoices")
    def test_sync_with_only_invoices(
        self,
        mock_list_invoices,
        mock_list_contacts,
        mock_list_credit_notes,
        mock_list_bank_transactions,
        mock_list_tax_rates,
    ):
        """Should work with only invoice data (backward compatible)."""
        # Create collector with mock store
        mock_store = MagicMock(spec=StateStore)
        mock_store.insert.return_value = None
        mock_store.insert_many.return_value = 0
        mock_store.query.return_value = []
        collector = XeroCollector(config={}, store=mock_store)

        # Create test invoice
        invoice = {
            "InvoiceID": "inv_123",
            "InvoiceNumber": "INV-001",
            "Type": "ACCREC",
            "Status": "PAID",
            "Contact": {"ContactID": "cont_456", "Name": "ABC Corp"},
            "Date": "2018-07-01T00:00:00",
            "Total": 1000.0,
            "AmountDue": 0.0,
            "CurrencyCode": "AED",
            "LineItems": [],
        }

        mock_list_invoices.return_value = [invoice]
        mock_list_contacts.return_value = []
        mock_list_credit_notes.return_value = []
        mock_list_bank_transactions.return_value = []
        mock_list_tax_rates.return_value = []

        result = collector.sync()

        # Should still return success structure
        assert "invoices_stored" in result
        assert "secondary" in result
        assert result["secondary"]["contacts"] == 0
        assert result["secondary"]["credit_notes"] == 0

    def test_parse_xero_date_with_all_formats(self):
        """Should parse all Xero date formats correctly."""
        # Test /Date format
        result = parse_xero_date("/Date(1530489600000+0000)/")
        assert result is not None
        assert len(result) == 10

        # Test ISO datetime
        assert parse_xero_date("2018-07-01T00:00:00") == "2018-07-01"

        # Test ISO date
        assert parse_xero_date("2018-07-01") == "2018-07-01"

        # Test None
        assert parse_xero_date(None) is None
