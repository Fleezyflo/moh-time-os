# ID-2.1: Improved Cost-to-Serve Proxies
> Brief: Intelligence Depth & Cross-Domain Synthesis | Phase: 2 | Sequence: 2.1 | Status: PENDING

## Objective

Replace overly simplistic cost-to-serve proxies with improved formulas that capture communication complexity, project diversity, task aging, and invoice overhead. Current formula is static: `effort_score = (active_tasks × 2) + (overdue_tasks × 3) + (completed_tasks × 0.5)`, and `avg_task_duration` is hardcoded to 0.0. These need richer signals.

## Implementation

### Improved Cost Proxies

**Task Age as Effort Proxy:**
- Weight by task status: completed tasks (1.0x), active tasks (1.5x), overdue tasks (2.0x)
- `weighted_task_age_sum = Σ(max(0, today - created_at).days × status_weight)`

**Assignee Diversity Factor:**
- Accounts for context-switching cost when many people work on same client
- `assignee_diversity_factor = sqrt(distinct_assignees_per_client) × 2.5`

**Communication Effort Weighting:**
- Thread depth (how deeply nested) × message count bucketing × channel weight
- Threads: 1 message (0.5), 2-5 (1.0), 6-15 (1.5), 16+ (2.0)
- Channel weights: email (1.0), slack (0.8), asana_comment (0.6)
- `weighted_comm_effort = Σ(thread_depth_factor × depth_bucket × channel_weight)`

**Project Scope Factor:**
- Multiple projects = higher context-switching cost
- `project_overhead = sqrt(project_count) × 10`

**Invoice Complexity:**
- More line items, more invoices issued = higher accounting overhead
- `invoice_overhead = (invoice_count / max(total_invoiced_amount, 1)) × 100`

### New Formula

```
effort_score = weighted_task_age_sum + assignee_diversity_factor + weighted_comm_effort + project_overhead + invoice_overhead
```

### New File: `lib/intelligence/cost_proxies.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

@dataclass
class TaskData:
    """Aggregated task data for a client."""
    task_id: str
    created_at: datetime
    status: str  # 'completed' | 'active' | 'overdue' | 'backlog'
    assignee_id: str


@dataclass
class ThreadMetadata:
    """Communication thread metadata."""
    thread_id: str
    message_count: int
    thread_depth: int
    channel: str  # 'email' | 'slack' | 'asana_comment'


@dataclass
class InvoiceData:
    """Invoice aggregates for a client."""
    invoice_count: int
    total_invoiced_amount: float
    avg_line_items_per_invoice: float


@dataclass
class CostComponents:
    """Breakdown of cost factors for inspection."""
    weighted_task_age_sum: float
    assignee_diversity_factor: float
    weighted_comm_effort: float
    project_overhead: float
    invoice_overhead: float
    total_effort_score: float


class ImprovedCostCalculator:
    """Computes improved cost-to-serve effort score with multiple proxies."""

    def __init__(self):
        pass

    def calculate(
        self,
        tasks: List[TaskData],
        assignees: List[str],
        threads: List[ThreadMetadata],
        invoices: InvoiceData,
        project_count: int,
        reference_date: Optional[datetime] = None
    ) -> CostComponents:
        """
        Calculate improved cost-to-serve effort score.
        
        Args:
            tasks: All tasks associated with the client
            assignees: List of distinct assignee IDs
            threads: Communication threads
            invoices: Invoice metadata
            project_count: Number of projects for this client
            reference_date: Date for age calculations (default: today)
            
        Returns:
            CostComponents with total_effort_score
        """

    def _weighted_task_age_sum(
        self,
        tasks: List[TaskData],
        reference_date: datetime
    ) -> float:
        """Sum of task ages weighted by status."""

    def _assignee_diversity_factor(
        self,
        assignees: List[str]
    ) -> float:
        """Context-switching cost from diverse team."""

    def _weighted_communication_effort(
        self,
        threads: List[ThreadMetadata]
    ) -> float:
        """Communication cost from thread depth and volume."""

    def _get_message_depth_bucket(self, message_count: int) -> float:
        """Map message count to effort multiplier."""

    def _get_channel_weight(self, channel: str) -> float:
        """Weight for communication channel type."""

    def _project_overhead(self, project_count: int) -> float:
        """Overhead from managing multiple projects."""

    def _invoice_overhead(self, invoices: InvoiceData) -> float:
        """Accounting complexity from invoicing."""
```

### Modified: `lib/intelligence/cost_to_serve.py`

Replace old calculation:
```python
# Old (cost_to_serve.py):
effort_score = (client.active_tasks * 2) + (client.overdue_tasks * 3) + (client.completed_tasks * 0.5)
avg_task_duration = 0.0  # hardcoded

# New:
components = self.cost_calculator.calculate(
    tasks=task_list,
    assignees=assignees,
    threads=communication_threads,
    invoices=invoice_data,
    project_count=len(projects)
)
effort_score = components.total_effort_score
```

## Deepened Specifications

### Thread Depth Calculation

```python
def compute_thread_depth(messages: list[dict]) -> int:
    """
    Thread depth = maximum reply depth in a conversation thread.

    For email (from gmail sync):
      thread_depth = count of messages in thread with In-Reply-To header
      If thread has 1 message: depth=1
      If thread has back-and-forth: depth = number of messages

    For slack (from chat sync):
      thread_depth = thread_ts reply count (from Slack API)
      Main channel message with no replies: depth=1

    For asana_comment:
      thread_depth = number of comments on the task
      (Asana comments are flat, so depth = count)

    The thread_depth_factor in the formula is:
      thread_depth_factor = min(thread_depth, 10) / 5.0
      # Normalizes: depth 1 → 0.2, depth 5 → 1.0, depth 10+ → 2.0 (capped)

    Full communication effort formula per thread:
      effort = thread_depth_factor × depth_bucket × channel_weight

    Where depth_bucket is based on message_count (NOT thread_depth):
      1 message: 0.5
      2-5 messages: 1.0
      6-15 messages: 1.5
      16+ messages: 2.0
    """
```

### Invoice Overhead Edge Cases

```python
def _invoice_overhead(self, invoices: InvoiceData) -> float:
    """
    invoice_overhead = (invoice_count / max(total_invoiced_amount, 1)) × 100

    Edge cases:
      - total_invoiced_amount == 0: use denominator of 1 (prevents division by zero)
      - invoice_count == 0: overhead = 0 (no invoicing activity)
      - Very large amount with few invoices: low overhead (efficient billing)
      - Many small invoices: high overhead (fragmented billing)

    Cap: invoice_overhead maxes at 50.0 to prevent domination of total score.
    """
```

### Data Source Queries

```sql
-- Task data for a client
SELECT t.id AS task_id, t.created_at, t.status, t.assignee_id
FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE p.client_id = ?
  AND t.created_at >= date('now', '-90 days');

-- Communication threads for a client
SELECT ct.thread_id, ct.message_count, ct.channel, ct.thread_depth
FROM communication_threads ct
WHERE ct.entity_type = 'client' AND ct.entity_id = ?
  AND ct.last_message_at >= date('now', '-90 days');
-- Note: if communication_threads table doesn't exist, aggregate from
-- gmail_messages (group by thread_id), chat_messages (group by thread_ts)

-- Invoice data for a client
SELECT COUNT(*) as invoice_count,
       COALESCE(SUM(total_amount), 0) as total_invoiced_amount,
       AVG(line_item_count) as avg_line_items
FROM invoices
WHERE client_id = ?
  AND invoice_date >= date('now', '-90 days');

-- Project count for a client
SELECT COUNT(DISTINCT id) as project_count
FROM projects
WHERE client_id = ?
  AND status != 'archived';

-- Distinct assignees for a client
SELECT DISTINCT assignee_id
FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE p.client_id = ?
  AND t.status IN ('active', 'overdue', 'completed')
  AND t.created_at >= date('now', '-90 days');
```

## Validation

- [ ] Weighted task age incorporates both time and status correctly
- [ ] Assignee diversity factor increases with team size (non-linear due to sqrt)
- [ ] Communication effort buckets correctly categorize thread depths
- [ ] Channel weights reflect actual communication overhead (email > slack > comment)
- [ ] Project overhead grows with project count but sublinearly
- [ ] Invoice overhead scales with invoice frequency and amount
- [ ] Clients with long-running, diverse teams score higher than simple clients
- [ ] Cost profitability bands shift with new formula (profitability affected by higher costs)
- [ ] Performance: cost calculation < 50ms per client, < 5 seconds for 1000 clients

## Files Created
- New: `lib/intelligence/cost_proxies.py`

## Files Modified
- Modified: `lib/intelligence/cost_to_serve.py` (integrate improved calculator)

## Estimated Effort
~200 lines — proxy implementations, bucketing logic, math for each factor

