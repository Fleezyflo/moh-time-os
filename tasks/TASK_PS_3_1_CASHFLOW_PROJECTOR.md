# PS-3.1: Cash Flow Projector

## Objective
Build a CashFlowProjector that combines AR aging, scheduled invoices, historical payment patterns, and known expenses to project daily cash position for the next 30/60/90 days. Flag dates where balance drops below safety threshold.

## Implementation

### CashFlowProjector (`lib/predictive/cashflow_projector.py`)
```python
class CashFlowProjector:
    """Probabilistic cash flow projection using payment pattern data."""

    def project(self, horizon_days: int = 90) -> CashFlowProjection:
        """
        Steps:
          1. Get current cash position (starting balance)
          2. Load AR aging buckets (outstanding invoices by age)
          3. For each outstanding invoice:
             - Look up client's historical days-to-pay distribution
             - Generate probabilistic payment date (weighted sample)
          4. Load scheduled invoices (upcoming milestones → invoice dates)
          5. Load known recurring expenses (salaries, rent, subscriptions)
          6. For each day in horizon:
             - Sum expected inflows (probabilistic invoice payments)
             - Sum expected outflows (expenses + scheduled payments)
             - Compute running balance
          7. Flag crunch dates (balance < safety_threshold)
        """

    def get_crunch_dates(self, safety_threshold: float = 50000.0) -> List[CrunchDate]:
        """Dates where projected balance drops below safety margin."""

    def scenario(self, adjustments: Dict) -> CashFlowProjection:
        """What-if: 'What if Client X pays 15 days late?' or 'What if we delay hiring?'"""
```

### Data Sources
```python
# From Xero collector (Brief 9)
outstanding_invoices = xero_collector.get_ar_aging()
payment_history = xero_collector.get_payment_history(client_id)

# Payment pattern per client
# e.g., Client A: mean=22 days, stddev=5 days
# e.g., Client B: mean=45 days, stddev=15 days
```

### Projection Output
```python
@dataclass
class DailyCashPosition:
    date: str
    opening_balance: float
    expected_inflows: float
    expected_outflows: float
    closing_balance: float
    inflow_sources: List[Dict]   # [{invoice_id, client, amount, probability}]
    outflow_items: List[Dict]    # [{category, description, amount}]
    is_below_threshold: bool

@dataclass
class CashFlowProjection:
    generated_at: str
    horizon_days: int
    starting_balance: float
    safety_threshold: float
    daily: List[DailyCashPosition]
    crunch_dates: List[CrunchDate]
    total_expected_inflows: float
    total_expected_outflows: float
    end_projected_balance: float
```

### API Endpoints
```
GET  /api/v2/predictive/cashflow?horizon=90&threshold=50000
GET  /api/v2/predictive/cashflow/crunch-dates
POST /api/v2/predictive/cashflow/scenario
```

## Validation
- [ ] Projection produces daily positions for requested horizon
- [ ] Payment timing uses per-client historical distribution
- [ ] Known expenses correctly deducted on scheduled dates
- [ ] Crunch dates correctly flagged below threshold
- [ ] What-if scenario correctly adjusts projections
- [ ] Zero outstanding invoices returns expense-only projection
- [ ] Starting balance matches current known position

## Files Created
- `lib/predictive/cashflow_projector.py`
- `tests/test_cashflow_projector.py`

## Estimated Effort
Large — ~600 lines
