# CS-5.2: Xero Collector Expansion

## Objective
Expand `lib/collectors/xero.py` from ~30% to ≥85% API coverage. Pull line items, tax breakdowns, contact details, credit notes, bills, bank transactions, and tax rates.

## Context
Current Xero collector (311 lines) pulls invoices with summary fields. Missing: line item detail (what exactly was billed), tax breakdowns (compliance), contact enrichment (client financial profile), credit notes (adjustments), bank transactions (cash flow), and tax rates (rate calculations). This data is critical for cost-to-serve analysis (Brief 11).

## Implementation

### New Data to Pull

1. **Invoice Line Items** — `invoice.LineItems[]` → store in `xero_line_items` with description, quantity, unit_amount, line_amount, tax_type, tax_amount, account_code, tracking
2. **Contact Details** — `GET /Contacts` → store in `xero_contacts` with email, phone, account_number, tax_number, is_supplier, is_customer, default_currency, outstanding/overdue balances
3. **Credit Notes** — `GET /CreditNotes` → store in `xero_credit_notes` with contact, date, status, total, remaining_credit, allocated
4. **Bank Transactions** — `GET /BankTransactions` → store in `xero_bank_transactions` with type (RECEIVE/SPEND), contact, date, total, reference
5. **Tax Rates** — `GET /TaxRates` → store in `xero_tax_rates` with effective rate and status
6. **Bills (Accounts Payable)** — Bills are invoices with `Type=ACCPAY` — already in invoices table but ensure `type` column distinguishes them

### Line Item Parsing
```python
for item in invoice.get("LineItems", []):
    store_line_item(
        invoice_id=invoice["InvoiceID"],
        description=item.get("Description"),
        quantity=item.get("Quantity"),
        unit_amount=item.get("UnitAmount"),
        line_amount=item.get("LineAmount"),
        tax_type=item.get("TaxType"),
        tax_amount=item.get("TaxAmount"),
        account_code=item.get("AccountCode"),
        tracking_category=item.get("Tracking", [{}])[0].get("Name"),
        tracking_option=item.get("Tracking", [{}])[0].get("Option"),
    )
```

### Incremental Sync
- Use `If-Modified-Since` header on all Xero endpoints
- Track `last_synced` timestamp per entity type
- Xero rate limit: 60 calls/minute — respect via resilience layer (CS-2.1)

## Validation
- [ ] Line items stored for all invoices with non-empty LineItems
- [ ] Contact details enriched with financial profile (balances, supplier/customer flags)
- [ ] Credit notes captured with allocation status
- [ ] Bank transactions stored with type and reference
- [ ] Tax rates table populated
- [ ] Bills (ACCPAY) distinguished from receivable invoices
- [ ] Incremental sync via If-Modified-Since reduces API calls

## Files Modified
- `lib/collectors/xero.py` — expand with new endpoints + line item parsing

## Estimated Effort
Medium — ~200 lines added, mostly new endpoint calls + data mapping
