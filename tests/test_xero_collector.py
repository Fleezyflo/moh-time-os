"""Tests for Xero collector — verifies invoice sync, date parsing, and status logic."""

from unittest.mock import MagicMock


def _make_xero_collector():
    """Create XeroCollector with mocked dependencies."""
    from lib.collectors.xero import XeroCollector

    store = MagicMock()
    store.query.return_value = []
    collector = XeroCollector(config={}, store=store)
    collector.circuit_breaker = MagicMock()
    collector.circuit_breaker.can_execute.return_value = True
    return collector


class TestParseXeroDate:
    """Tests for the parse_xero_date utility."""

    def test_epoch_format(self):
        from lib.collectors.xero import parse_xero_date

        result = parse_xero_date("/Date(1530489600000+0000)/")
        assert result == "2018-07-02"

    def test_iso_datetime_format(self):
        from lib.collectors.xero import parse_xero_date

        result = parse_xero_date("2018-05-30T00:00:00")
        assert result == "2018-05-30"

    def test_iso_date_format(self):
        from lib.collectors.xero import parse_xero_date

        result = parse_xero_date("2018-05-30")
        assert result == "2018-05-30"

    def test_none_input(self):
        from lib.collectors.xero import parse_xero_date

        assert parse_xero_date(None) is None

    def test_empty_string(self):
        from lib.collectors.xero import parse_xero_date

        assert parse_xero_date("") is None

    def test_invalid_format(self):
        from lib.collectors.xero import parse_xero_date

        assert parse_xero_date("not-a-date") is None


class TestDetermineInvoiceStatus:
    """Tests for invoice status determination."""

    def test_paid_status(self):
        collector = _make_xero_collector()
        assert collector._determine_invoice_status("PAID", 0, None) == "paid"

    def test_authorised_not_overdue(self):
        collector = _make_xero_collector()
        assert collector._determine_invoice_status("AUTHORISED", 100, "2099-12-31") == "sent"

    def test_authorised_overdue(self):
        collector = _make_xero_collector()
        assert collector._determine_invoice_status("AUTHORISED", 100, "2020-01-01") == "overdue"

    def test_authorised_no_due_date(self):
        collector = _make_xero_collector()
        assert collector._determine_invoice_status("AUTHORISED", 100, None) == "sent"

    def test_authorised_zero_amount_due(self):
        collector = _make_xero_collector()
        assert collector._determine_invoice_status("AUTHORISED", 0, "2020-01-01") == "sent"


class TestTransformLineItems:
    """Tests for line item transformation."""

    def test_basic_line_item(self):
        collector = _make_xero_collector()
        items = [
            {
                "Description": "Consulting",
                "Quantity": 10,
                "UnitAmount": 150,
                "LineAmount": 1500,
                "TaxType": "OUTPUT",
                "TaxAmount": 75,
                "AccountCode": "200",
            }
        ]
        result = collector._transform_line_items("inv_001", items)
        assert len(result) == 1
        assert result[0]["invoice_id"] == "inv_001"
        assert result[0]["description"] == "Consulting"
        assert result[0]["quantity"] == 10.0
        assert result[0]["line_amount"] == 1500.0

    def test_empty_line_items(self):
        collector = _make_xero_collector()
        result = collector._transform_line_items("inv_001", [])
        assert result == []

    def test_missing_fields_default_to_zero(self):
        collector = _make_xero_collector()
        items = [{"Description": "Minimal"}]
        result = collector._transform_line_items("inv_001", items)
        assert result[0]["quantity"] == 0.0
        assert result[0]["unit_amount"] == 0.0


class TestTransformContacts:
    """Tests for contact transformation."""

    def test_basic_contact(self):
        collector = _make_xero_collector()
        contacts = [
            {
                "ContactID": "c001",
                "Name": "Acme Corp",
                "EmailAddress": "billing@acme.com",
                "IsSupplier": False,
                "IsCustomer": True,
                "DefaultCurrency": "AED",
            }
        ]
        result = collector._transform_contacts(contacts)
        assert len(result) == 1
        assert result[0]["id"] == "c001"
        assert result[0]["name"] == "Acme Corp"
        assert result[0]["is_customer"] == 1
        assert result[0]["is_supplier"] == 0

    def test_empty_contacts(self):
        collector = _make_xero_collector()
        assert collector._transform_contacts([]) == []


class TestTransformCreditNotes:
    """Tests for credit note transformation."""

    def test_basic_credit_note(self):
        collector = _make_xero_collector()
        notes = [
            {
                "CreditNoteID": "cn001",
                "Contact": {"ContactID": "c001"},
                "Status": "AUTHORISED",
                "Total": 500,
                "CurrencyCode": "AED",
                "RemainingCredit": 200,
            }
        ]
        result = collector._transform_credit_notes(notes)
        assert len(result) == 1
        assert result[0]["id"] == "cn001"
        assert result[0]["total"] == 500.0
        assert result[0]["remaining_credit"] == 200.0


class TestFindClientId:
    """Tests for client matching logic."""

    def test_exact_match(self):
        collector = _make_xero_collector()
        collector.store.query.return_value = [{"id": "client_1"}]
        result = collector._find_client_id("Acme Corp")
        assert result == "client_1"

    def test_no_match_returns_none(self):
        collector = _make_xero_collector()
        collector.store.query.return_value = []
        result = collector._find_client_id("Unknown Corp")
        assert result is None


class TestSyncCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_sync_blocked_by_circuit_breaker(self):
        collector = _make_xero_collector()
        collector.circuit_breaker.can_execute.return_value = False
        collector.circuit_breaker.state = "open"
        result = collector.sync()
        assert "error" in result
        assert "Circuit breaker" in result["error"]
