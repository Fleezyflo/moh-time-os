# IE-1.1: Cost-to-Serve Module

## Objective
Build `lib/intelligence/cost_to_serve.py` — compute the actual cost of serving each client by combining time tracking, task effort, communication overhead, and financial data from Xero.

## Context
Cost-to-serve is a core MASTER_SPEC DIRECTIVE but is NOT IMPLEMENTED. The data exists after Brief 9: time_blocks (calendar), tasks (Asana), communications (Gmail/Chat), invoices + line_items (Xero). This module connects them.

## Implementation

### Cost Formula
```
Client Cost = Direct Labor + Communication Overhead + Administrative Overhead

Direct Labor = Σ(time_blocks allocated to client × team_member hourly rate)
Communication Overhead = Σ(emails + chat messages × avg_cost_per_communication)
Administrative Overhead = Σ(internal meetings about client × attendee_count × hourly rate)
```

### Revenue Calculation
```
Client Revenue = Σ(invoices.total WHERE contact matches client) - Σ(credit_notes.total)
```

### Profitability
```
Client Profitability = Revenue - Total Cost
Margin % = (Revenue - Total Cost) / Revenue × 100
```

### Module Structure
```python
# lib/intelligence/cost_to_serve.py

class CostToServeAnalyzer:
    def compute_client_cost(self, client_id: str, period: DateRange) -> ClientCost:
        """Full cost breakdown for a single client."""
        ...

    def compute_all_clients(self, period: DateRange) -> list[ClientCost]:
        """Cost analysis for every active client."""
        ...

    def rank_by_profitability(self, period: DateRange) -> list[ClientProfitability]:
        """Ranked list from most to least profitable."""
        ...

@dataclass
class ClientCost:
    client_id: str
    client_name: str
    period: DateRange
    direct_labor_hours: float
    direct_labor_cost: float
    communication_count: int
    communication_cost: float
    meeting_hours: float
    meeting_cost: float
    total_cost: float
    revenue: float
    profit: float
    margin_pct: float
```

### Data Sources
- `time_blocks` → direct labor hours per client
- `tasks` → task assignments and completions per client project
- `communications` + `gmail_participants` → email/chat volume per client
- `calendar_events` + `calendar_attendees` → meetings per client
- `invoices` + `xero_line_items` → revenue per client
- `xero_credit_notes` → adjustments
- `xero_contacts` → client mapping to Xero

### Client Matching
Link Xero contacts to internal clients via:
1. Exact name match (client_name ↔ contact.name)
2. Domain match (from_domain ↔ contact.email domain)
3. Manual mapping table for edge cases

## Validation
- [ ] Cost computed for ≥90% of active clients
- [ ] Revenue matches Xero invoice totals
- [ ] Profitability rankings make business sense (spot-check with Molham)
- [ ] Edge cases handled: clients with no invoices, no meetings, no emails
- [ ] Tests with fixture data

## Files Created
- `lib/intelligence/cost_to_serve.py`
- `tests/test_cost_to_serve.py`

## Estimated Effort
Large — ~300 lines, complex cross-table joins and business logic
