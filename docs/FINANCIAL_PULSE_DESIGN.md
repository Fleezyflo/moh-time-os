# MOH Time OS — Financial Pulse System Design

> **Version:** 1.0
> **Status:** Design Complete
> **Priority:** Layer 1 (build first)

---

## 1. Purpose

Give Moh a single view into hrmny's financial health:
- Revenue (invoiced, received, vs forecast)
- Receivables (who owes us, how healthy)
- Spend (overhead, fixed, variable)
- Salaries (payroll, headcount)

Not accounting. **Operator awareness.**

---

## 2. Core Questions This Answers

| Question | Answer Source |
|----------|---------------|
| "How much did we invoice this month?" | Xero invoices |
| "How much have we actually collected?" | Xero payments |
| "Are we on track vs forecast?" | Xero vs Forecast Sheet |
| "Who owes us money?" | Xero AR aging |
| "Is anyone dangerously overdue?" | AR health calculation |
| "What are we spending?" | Xero bills |
| "What's payroll this month?" | Forecast Sheet salaries |
| "What needs my attention?" | Alerts engine |

---

## 3. Data Sources

### 3.1 Xero (Financial Truth)

| Data | Endpoint | Refresh |
|------|----------|---------|
| Invoices (AR) | `/Invoices` | Hourly |
| Payments received | `/Payments` | Hourly |
| Bills (AP) | `/Invoices?where=Type=="ACCPAY"` | 4 hours |
| Contacts | `/Contacts` | Daily |
| Aged Receivables | `/Reports/AgedReceivablesByContact` | Daily |

### 3.2 Forecast Sheet (Projections + Salaries)

| Data | Range | Refresh |
|------|-------|---------|
| Revenue forecast by client | `Forecast!A5:BK100` | Daily |
| Salaries by employee | `Forecast!A225:BK350` | Daily |

### 3.3 Derived/Computed

| Metric | Calculation |
|--------|-------------|
| Revenue vs forecast variance | `(actual - forecast) / forecast` |
| Days overdue | `today - due_date` |
| AR aging buckets | Group by days overdue |
| Client health score | Weighted formula (see §6) |
| Attention priority | Weighted formula (see §7) |

---

## 4. Data Model

### 4.1 Entity Relationships

```
Client (from Xero + Sheets)
   │
   ├──→ Invoices (AR)
   │       └──→ Payments
   │
   ├──→ Projects (from Asana, linked later)
   │
   └──→ Revenue Forecast (from Sheets)

Supplier (from Xero)
   │
   └──→ Bills (AP)

Employee (from Sheets)
   │
   └──→ Salary entries by month
```

### 4.2 Database Schema

```sql
-- Clients (reconciled from Xero contacts + Sheets)
CREATE TABLE clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    xero_contact_id TEXT UNIQUE,
    type TEXT CHECK(type IN ('retainer', 'project', 'prospect', 'inactive')),
    payment_terms_days INTEGER DEFAULT 30,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Invoices from Xero
CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    xero_id TEXT UNIQUE NOT NULL,
    client_id TEXT REFERENCES clients(id),
    invoice_number TEXT,
    reference TEXT,
    amount REAL NOT NULL,
    amount_due REAL NOT NULL,
    amount_paid REAL DEFAULT 0,
    currency TEXT DEFAULT 'AED',
    status TEXT CHECK(status IN ('DRAFT', 'SUBMITTED', 'AUTHORISED', 'PAID', 'VOIDED', 'DELETED')),
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    fully_paid_date TEXT,
    line_items_json TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Payments from Xero
CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    xero_id TEXT UNIQUE NOT NULL,
    invoice_id TEXT REFERENCES invoices(id),
    client_id TEXT REFERENCES clients(id),
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'AED',
    payment_date TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

-- Bills (AP) from Xero
CREATE TABLE bills (
    id TEXT PRIMARY KEY,
    xero_id TEXT UNIQUE NOT NULL,
    supplier_name TEXT NOT NULL,
    supplier_xero_id TEXT,
    amount REAL NOT NULL,
    amount_due REAL NOT NULL,
    currency TEXT DEFAULT 'AED',
    status TEXT,
    category TEXT,
    bill_date TEXT NOT NULL,
    due_date TEXT,
    paid_date TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Salaries from Forecast Sheet
CREATE TABLE salaries (
    id TEXT PRIMARY KEY,
    employee_name TEXT NOT NULL,
    title TEXT,
    department TEXT,
    amount REAL NOT NULL,
    month TEXT NOT NULL,  -- YYYY-MM
    is_active INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(employee_name, month)
);

-- Revenue forecasts from Forecast Sheet
CREATE TABLE revenue_forecast (
    id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    engagement_type TEXT,  -- retainer, project
    month TEXT NOT NULL,  -- YYYY-MM
    amount REAL NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(client_name, month)
);

-- Daily financial snapshots (for trends)
CREATE TABLE financial_snapshots (
    id TEXT PRIMARY KEY,
    snapshot_date TEXT UNIQUE NOT NULL,
    total_invoiced_mtd REAL,
    total_received_mtd REAL,
    total_outstanding REAL,
    ar_current REAL,
    ar_1_30 REAL,
    ar_31_60 REAL,
    ar_61_90 REAL,
    ar_90_plus REAL,
    total_spend_mtd REAL,
    total_salaries REAL,
    created_at INTEGER NOT NULL
);

-- Client financial health (computed)
CREATE TABLE client_health (
    client_id TEXT REFERENCES clients(id),
    computed_date TEXT NOT NULL,
    total_outstanding REAL,
    days_oldest_invoice INTEGER,
    avg_days_to_pay REAL,
    health_score REAL,
    risk_level TEXT CHECK(risk_level IN ('healthy', 'watch', 'at_risk', 'critical')),
    PRIMARY KEY(client_id, computed_date)
);

-- Alerts
CREATE TABLE alerts (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity TEXT CHECK(severity IN ('info', 'warning', 'critical')),
    entity_type TEXT,
    entity_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    context_json TEXT,
    priority_score REAL,
    status TEXT DEFAULT 'new' CHECK(status IN ('new', 'acknowledged', 'resolved', 'dismissed')),
    created_at INTEGER NOT NULL,
    acknowledged_at INTEGER,
    resolved_at INTEGER
);

-- Sync status tracking
CREATE TABLE sync_status (
    source TEXT PRIMARY KEY,
    last_sync_at INTEGER,
    last_success_at INTEGER,
    status TEXT DEFAULT 'unknown',
    error_message TEXT,
    records_synced INTEGER
);

-- Indexes
CREATE INDEX idx_invoices_client ON invoices(client_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_due_date ON invoices(due_date);
CREATE INDEX idx_payments_client ON payments(client_id);
CREATE INDEX idx_bills_date ON bills(bill_date);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_severity ON alerts(severity);
```

---

## 5. Metric Definitions

### 5.1 Revenue Metrics

| Metric | Definition |
|--------|------------|
| **Invoiced (MTD)** | Sum of `amount` for invoices where `invoice_date` is in current month |
| **Received (MTD)** | Sum of `amount` from payments where `payment_date` is in current month |
| **Forecast (MTD)** | Sum of `amount` from `revenue_forecast` for current month |
| **Variance** | `(Invoiced - Forecast) / Forecast * 100` |
| **Retainer Revenue** | Invoiced amount for clients with `type = 'retainer'` |
| **Project Revenue** | Invoiced amount for clients with `type = 'project'` |

### 5.2 Receivables Metrics

| Metric | Definition |
|--------|------------|
| **Total Outstanding** | Sum of `amount_due` for invoices with `status IN ('AUTHORISED', 'SUBMITTED')` and `amount_due > 0` |
| **Current** | Outstanding where `due_date >= today` |
| **1-30 Days** | Outstanding where `due_date` is 1-30 days ago |
| **31-60 Days** | Outstanding where `due_date` is 31-60 days ago |
| **61-90 Days** | Outstanding where `due_date` is 61-90 days ago |
| **90+ Days** | Outstanding where `due_date` is >90 days ago |
| **AR Health %** | `(Current + 1-30) / Total Outstanding * 100` — higher is healthier |

### 5.3 Spend Metrics

| Metric | Definition |
|--------|------------|
| **Spend (MTD)** | Sum of `amount` for bills where `bill_date` is in current month |
| **Fixed Costs** | Bills with `category IN ('Rent', 'Salaries', 'Subscriptions', 'Insurance')` |
| **Variable Costs** | All other bills |

### 5.4 Salary Metrics

| Metric | Definition |
|--------|------------|
| **Monthly Payroll** | Sum of `amount` from salaries for current month where `is_active = 1` |
| **Headcount** | Count of distinct employees where `is_active = 1` and `amount > 0` for current month |

---

## 6. Client Health Score

```python
def calculate_client_health(client_id: str) -> dict:
    """
    Calculate financial health score for a client.
    Returns score 0-100 and risk level.
    """

    # Get client's outstanding invoices
    invoices = get_outstanding_invoices(client_id)

    if not invoices:
        return {"score": 100, "risk_level": "healthy", "reason": "No outstanding invoices"}

    # Factors
    total_outstanding = sum(i.amount_due for i in invoices)
    oldest_days = max((today() - i.due_date).days for i in invoices)

    # Get payment history
    payments = get_payments(client_id, months=12)
    if payments:
        avg_days_to_pay = average([p.days_from_invoice_to_payment for p in payments])
    else:
        avg_days_to_pay = 0

    # Score calculation (100 = perfect)
    score = 100

    # Deduct for overdue days
    if oldest_days > 0:
        score -= min(oldest_days * 0.5, 40)  # Max 40 point deduction

    # Deduct for amount at risk
    amount_overdue = sum(i.amount_due for i in invoices if i.days_overdue > 0)
    if amount_overdue > 100000:
        score -= 30
    elif amount_overdue > 50000:
        score -= 20
    elif amount_overdue > 20000:
        score -= 10

    # Deduct for slow payment history
    if avg_days_to_pay > 60:
        score -= 15
    elif avg_days_to_pay > 45:
        score -= 10
    elif avg_days_to_pay > 30:
        score -= 5

    score = max(0, score)

    # Risk level
    if score >= 80:
        risk_level = "healthy"
    elif score >= 60:
        risk_level = "watch"
    elif score >= 40:
        risk_level = "at_risk"
    else:
        risk_level = "critical"

    return {
        "score": score,
        "risk_level": risk_level,
        "total_outstanding": total_outstanding,
        "oldest_days_overdue": max(0, oldest_days),
        "avg_days_to_pay": avg_days_to_pay,
    }
```

---

## 7. Attention Items & Priority

### 7.1 Alert Types

| Type | Trigger | Default Severity |
|------|---------|------------------|
| `invoice_overdue_30` | Invoice >30 days past due | warning |
| `invoice_overdue_60` | Invoice >60 days past due | warning |
| `invoice_overdue_90` | Invoice >90 days past due | critical |
| `large_invoice_unpaid` | Invoice >50K AED unpaid >14 days | warning |
| `client_health_declining` | Client health score drops >20 points | warning |
| `client_at_risk` | Client health score <40 | critical |
| `no_payment_60_days` | Client hasn't paid in 60 days with outstanding | warning |
| `revenue_below_forecast` | MTD revenue >15% below forecast | warning |
| `cash_flow_negative` | MTD received < MTD spent | warning |

### 7.2 Priority Score Calculation

```python
def calculate_priority(alert) -> float:
    """
    Calculate priority score 0-100 for an alert.
    Higher = more urgent = show first.
    """
    score = 0

    # Base by severity
    severity_base = {"info": 10, "warning": 40, "critical": 70}
    score += severity_base.get(alert.severity, 20)

    if alert.type.startswith("invoice_overdue"):
        invoice = get_invoice(alert.entity_id)

        # Amount factor
        if invoice.amount_due > 100000:
            score += 20
        elif invoice.amount_due > 50000:
            score += 15
        elif invoice.amount_due > 20000:
            score += 10

        # Time factor
        if invoice.days_overdue > 90:
            score += 15
        elif invoice.days_overdue > 60:
            score += 10

        # Relationship factor
        client = get_client(invoice.client_id)
        if client.type == "retainer":
            score += 5  # Retainer relationships are more valuable

    return min(score, 100)
```

---

## 8. Views / Output

### 8.1 Executive Summary (Primary View)

```
╔═══════════════════════════════════════════════════════════════════╗
║  FINANCIAL PULSE — January 2026                    as of 17:30    ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  REVENUE                │  RECEIVABLES           │  SPEND         ║
║  ───────────────────    │  ──────────────────    │  ───────────   ║
║  Invoiced:    847,000   │  Outstanding: 312,000  │  MTD: 234,000  ║
║  Received:    623,000   │  ├─ Current:  180,000  │  Fixed: 189K   ║
║  Forecast:    822,000   │  ├─ 1-30:      54,000  │  Variable: 45K ║
║  Variance:      +3.0%   │  ├─ 31-60:     24,000  │                ║
║                         │  ├─ 61-90:     32,000  │  SALARIES      ║
║  Retainer:      485K    │  └─ 90+:       22,000  │  ───────────   ║
║  Project:       362K    │                        │  Payroll: 298K ║
║                         │  AR Health:      75%   │  Headcount: 26 ║
║                         │                        │                ║
╠═══════════════════════════════════════════════════════════════════╣
║  ⚠️  2 ITEMS NEED ATTENTION                                        ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  1. [CRITICAL] GMG Everyday Goods — 54,000 AED overdue 67 days    ║
║     └─ Active retainer, last contact 12 days ago                  ║
║     └─ [View details] [Draft reminder] [Log call]                 ║
║                                                                   ║
║  2. [WARNING] Deliveroo — 78,000 AED due in 2 days                ║
║     └─ Project delivered, awaiting final sign-off                 ║
║     └─ [View details] [Check project status]                      ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### 8.2 Receivables Detail View

```
╔═══════════════════════════════════════════════════════════════════╗
║  RECEIVABLES DETAIL                                               ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  OUTSTANDING BY CLIENT                                            ║
║  ─────────────────────────────────────────────────────────────    ║
║  Client                 Outstanding    Oldest    Health    Status ║
║  ─────────────────────────────────────────────────────────────    ║
║  GMG Everyday Goods        95,463      67 days    42/100   ⚠️ Risk║
║  Deliveroo                 78,000       0 days    88/100   ✓      ║
║  Sun & Sand Sports         58,443      12 days    76/100   ✓      ║
║  Gargash Auto              34,000      23 days    71/100   Watch  ║
║  Five Guys                 22,000       5 days    92/100   ✓      ║
║  (12 more clients...)                                             ║
║                                                                   ║
║  [Filter: All | Overdue | At Risk]  [Sort: Amount | Age | Health] ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║  AGING BREAKDOWN                                                  ║
║  ─────────────────────────────────────────────────────────────    ║
║  Current   ████████████████████████████░░░░░░░░  180,000  (58%)   ║
║  1-30      ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░   54,000  (17%)   ║
║  31-60     ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   24,000   (8%)   ║
║  61-90     █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   32,000  (10%)   ║
║  90+       ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   22,000   (7%)   ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### 8.3 Client Financial Card (Drill-Down)

```
╔═══════════════════════════════════════════════════════════════════╗
║  CLIENT: GMG EVERYDAY GOODS                                       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  RELATIONSHIP                                                     ║
║  ─────────────────────────────────────────────────────────────    ║
║  Type:           Retainer                                         ║
║  Since:          March 2025                                       ║
║  Monthly Value:  95,463 AED                                       ║
║  Total LTV:      1,145,556 AED                                    ║
║                                                                   ║
║  FINANCIAL STATUS                               Health: 42/100 ⚠️  ║
║  ─────────────────────────────────────────────────────────────    ║
║  Outstanding:          95,463 AED                                 ║
║  Overdue:              54,000 AED (67 days)                       ║
║  Last Payment:         43 days ago (41,463 AED)                   ║
║  Payment Terms:        30 days                                    ║
║  Typical Behavior:     Pays in 35-45 days (slightly late)         ║
║                                                                   ║
║  OUTSTANDING INVOICES                                             ║
║  ─────────────────────────────────────────────────────────────    ║
║  INV-2024-0892    54,000 AED    Due: Nov 24    67 days overdue    ║
║  INV-2024-0923    41,463 AED    Due: Jan 15    Current            ║
║                                                                   ║
║  RECENT PAYMENTS                                                  ║
║  ─────────────────────────────────────────────────────────────    ║
║  Dec 18, 2025     41,463 AED    INV-2024-0856    Paid (38 days)   ║
║  Nov 15, 2025     95,463 AED    INV-2024-0821    Paid (42 days)   ║
║  Oct 12, 2025     95,463 AED    INV-2024-0789    Paid (35 days)   ║
║                                                                   ║
║  OPERATIONAL CONTEXT                                              ║
║  ─────────────────────────────────────────────────────────────    ║
║  Active Projects:      3 (Gulf Food Campaign, Ramadan, Retainer)  ║
║  Last Meeting:         12 days ago (Weekly Sync)                  ║
║  Next Meeting:         Tomorrow 11:00 AM (Weekly Sync)            ║
║  Last Email:           5 days ago (RE: Gulf Food deliverables)    ║
║                                                                   ║
║  RECOMMENDED ACTIONS                                              ║
║  ─────────────────────────────────────────────────────────────    ║
║  • Payment is late but within their typical pattern               ║
║  • Meeting tomorrow — good opportunity to mention invoice         ║
║  • Consider: Send gentle reminder before meeting                  ║
║                                                                   ║
║  [View All Invoices] [View Projects] [Draft Reminder] [Log Call]  ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 9. Sync Architecture

### 9.1 Collection Layer

```python
class XeroSyncer:
    """Handles all Xero data synchronization."""

    def sync_all(self):
        """Full sync - run hourly."""
        self.sync_invoices()
        self.sync_payments()
        self.sync_contacts()

    def sync_invoices(self):
        """Sync invoices from Xero."""
        # Get all non-voided invoices modified in last 7 days
        # Plus all outstanding regardless of modification
        invoices = xero_client.get_invoices(
            modified_since=days_ago(7),
            statuses=["AUTHORISED", "SUBMITTED", "PAID"]
        )

        for inv in invoices:
            self._upsert_invoice(inv)

        self._update_sync_status("xero_invoices", len(invoices))

    def sync_payments(self):
        """Sync payments from Xero."""
        payments = xero_client.get_payments(modified_since=days_ago(7))

        for pmt in payments:
            self._upsert_payment(pmt)
            self._update_invoice_paid_amount(pmt.invoice_id)

        self._update_sync_status("xero_payments", len(payments))

    def sync_contacts(self):
        """Sync contacts, reconcile with clients."""
        contacts = xero_client.get_contacts(is_customer=True)

        for contact in contacts:
            self._reconcile_client(contact)

        self._update_sync_status("xero_contacts", len(contacts))

    def sync_bills(self):
        """Sync bills/AP - run every 4 hours."""
        bills = xero_client.get_invoices(invoice_type="ACCPAY")

        for bill in bills:
            self._upsert_bill(bill)

        self._update_sync_status("xero_bills", len(bills))


class SheetsSyncer:
    """Handles Forecast Sheet synchronization."""

    def sync_all(self):
        """Full sync - run daily."""
        self.sync_revenue_forecast()
        self.sync_salaries()

    def sync_revenue_forecast(self):
        """Pull revenue forecast from Forecast sheet."""
        data = gog_client.get_sheet_range(
            FORECAST_SHEET_ID,
            "Forecast!A5:BK100"
        )

        for row in self._parse_revenue_rows(data):
            self._upsert_forecast(row)

    def sync_salaries(self):
        """Pull salary data from Forecast sheet."""
        data = gog_client.get_sheet_range(
            FORECAST_SHEET_ID,
            "Forecast!A225:BK350"
        )

        current_month = get_current_month()
        for row in self._parse_salary_rows(data, current_month):
            self._upsert_salary(row)
```

### 9.2 Sync Schedule

| Job | Frequency | Time | Notes |
|-----|-----------|------|-------|
| `xero_invoices` | Hourly | :00 | Core financial data |
| `xero_payments` | Hourly | :05 | Match with invoices |
| `xero_bills` | Every 4h | :10 | Spend tracking |
| `xero_contacts` | Daily | 06:00 | Client reconciliation |
| `sheets_forecast` | Daily | 06:15 | Revenue projections |
| `sheets_salaries` | Daily | 06:20 | Payroll data |
| `compute_health` | Daily | 06:30 | After all syncs |
| `compute_snapshot` | Daily | 06:45 | Daily snapshot |
| `evaluate_alerts` | Hourly | :30 | After invoice sync |

### 9.3 Error Handling & Degraded Mode

```python
class SyncHealth:
    """Track health of each data source."""

    STALE_THRESHOLDS = {
        "xero_invoices": timedelta(hours=2),
        "xero_payments": timedelta(hours=2),
        "xero_bills": timedelta(hours=6),
        "xero_contacts": timedelta(days=2),
        "sheets_forecast": timedelta(days=2),
        "sheets_salaries": timedelta(days=2),
    }

    def check_health(self) -> dict:
        """Return health status for all sources."""
        results = {}

        for source, threshold in self.STALE_THRESHOLDS.items():
            status = get_sync_status(source)

            is_stale = (
                status.last_success_at is None or
                now() - status.last_success_at > threshold
            )

            results[source] = {
                "status": "stale" if is_stale else "healthy",
                "last_sync": status.last_success_at,
                "error": status.error_message if status.status == "error" else None,
            }

        return results

    def get_dashboard_warning(self) -> str | None:
        """Return warning message if any source is unhealthy."""
        health = self.check_health()

        stale = [s for s, h in health.items() if h["status"] == "stale"]

        if not stale:
            return None

        if "xero_invoices" in stale:
            return "⚠️ Financial data may be stale. Last sync: " + \
                   format_time_ago(health["xero_invoices"]["last_sync"])

        return f"⚠️ Some data sources are stale: {', '.join(stale)}"
```

---

## 10. CLI / Debug Tools

```python
@cli.command()
def pulse():
    """Show financial pulse summary."""
    summary = get_financial_summary()
    render_pulse_view(summary)

@cli.command()
def receivables(client: str = None, status: str = "all"):
    """Show receivables detail."""
    data = get_receivables(client=client, status=status)
    render_receivables_view(data)

@cli.command()
def client(name: str):
    """Show client financial card."""
    client = find_client(name)
    card = get_client_financial_card(client.id)
    render_client_card(card)

@cli.command()
def alerts(status: str = "new", severity: str = None):
    """Show active alerts."""
    alerts = get_alerts(status=status, severity=severity)
    for alert in alerts:
        print(f"[{alert.severity.upper()}] {alert.title}")
        print(f"  {alert.description}")
        print()

@cli.command()
def sync(source: str = "all", verbose: bool = False):
    """Run sync for a data source."""
    if source == "all":
        run_all_syncs(verbose=verbose)
    else:
        run_sync(source, verbose=verbose)

@cli.command()
def health():
    """Show sync health status."""
    health = SyncHealth().check_health()
    for source, status in health.items():
        icon = "✓" if status["status"] == "healthy" else "⚠️"
        print(f"{icon} {source}: {status['status']}")
        if status["last_sync"]:
            print(f"   Last sync: {format_time_ago(status['last_sync'])}")
        if status["error"]:
            print(f"   Error: {status['error']}")

@cli.command()
def inspect_invoice(number: str):
    """Debug: show full invoice state."""
    invoice = find_invoice(number)
    print_json({
        "invoice": asdict(invoice),
        "client": asdict(get_client(invoice.client_id)),
        "payments": [asdict(p) for p in get_invoice_payments(invoice.id)],
        "computed": {
            "days_overdue": calculate_days_overdue(invoice),
            "health_impact": calculate_health_impact(invoice),
        }
    })
```

---

## 11. MVP Scope

### What ships first (MVP):

1. **Xero sync** — invoices, payments, contacts
2. **Receivables aging** — by client, by bucket
3. **Executive summary** — one view with key numbers
4. **Attention items** — overdue invoices only
5. **Client drill-down** — financial card view
6. **Basic CLI** — `pulse`, `receivables`, `client`, `sync`, `health`

### What comes in v1.1:

- Spend tracking (bills)
- Salary integration
- Revenue vs forecast comparison
- Historical trends
- More alert types

### What comes in v1.2:

- Project linking (invoice → project)
- Cash flow projection
- Concentration risk analysis
- Payment behavior prediction

---

## 12. File Structure

```
moh_time_os/
├── config/
│   ├── .credentials.json      # API keys (gitignored)
│   └── knowledge_base.json    # Cached KB
├── engine/
│   ├── xero_client.py         # Xero API client
│   ├── asana_client.py        # Asana API client
│   ├── gogcli.py              # Google API wrapper
│   ├── knowledge_base.py      # KB building
│   ├── financial_pulse.py     # NEW: Core pulse logic
│   ├── sync.py                # NEW: Sync orchestration
│   └── alerts.py              # NEW: Alert engine
├── cli/
│   ├── pulse.py               # NEW: Pulse CLI
│   └── ...
├── schema/
│   └── schema.sql             # Updated schema
├── out/
│   └── ...                    # Output files
└── docs/
    ├── FINANCIAL_PULSE_DESIGN.md  # This document
    └── ...
```

---

## 13. Implementation Order

1. **Schema** — Add new tables to schema.sql
2. **Xero Sync** — Invoices, payments, contacts
3. **Computations** — Aging, health scores
4. **Alerts** — Overdue detection
5. **CLI Views** — pulse, receivables, client
6. **Dashboard** — HTML/Canvas view (optional)

---

## 14. Open Questions

| Question | Decision Needed |
|----------|-----------------|
| Multi-currency? | Assume AED only for MVP, convert later |
| Credit notes? | Include as negative invoices |
| Retainers vs projects? | Tag clients by type, may need manual mapping initially |
| Invoice-project link? | Start with client-level, add project link in v1.1 |
| Payment terms? | Default 30 days, allow override per client |

---

## 15. Success Criteria

MVP is successful when Moh can:

1. Run `pulse` and see current financial state in 5 seconds
2. Know immediately who owes money and how late
3. Drill into any client and see full financial relationship
4. Trust the data is current (sync health visible)
5. Get alerted when something needs attention

---

*Design complete. Ready for implementation.*
