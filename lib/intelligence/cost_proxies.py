"""
Improved Cost-to-Serve Proxies — MOH TIME OS

Replaces simplistic cost formula with multi-factor proxies:
- Weighted task age (status-based multipliers)
- Assignee diversity (context-switching cost)
- Communication effort (thread depth × volume × channel)
- Project scope overhead
- Invoice complexity

Brief 18 (ID), Task ID-2.1
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


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

    def to_dict(self) -> dict:
        return {
            "weighted_task_age_sum": round(self.weighted_task_age_sum, 2),
            "assignee_diversity_factor": round(self.assignee_diversity_factor, 2),
            "weighted_comm_effort": round(self.weighted_comm_effort, 2),
            "project_overhead": round(self.project_overhead, 2),
            "invoice_overhead": round(self.invoice_overhead, 2),
            "total_effort_score": round(self.total_effort_score, 2),
        }


# Status multipliers for task age weighting
STATUS_WEIGHTS = {
    "completed": 1.0,
    "active": 1.5,
    "overdue": 2.0,
    "backlog": 0.5,
}

# Channel weights for communication effort
CHANNEL_WEIGHTS = {
    "email": 1.0,
    "slack": 0.8,
    "asana_comment": 0.6,
}


class ImprovedCostCalculator:
    """Computes improved cost-to-serve effort score with multiple proxies."""

    def calculate(
        self,
        tasks: list[TaskData],
        assignees: list[str],
        threads: list[ThreadMetadata],
        invoices: InvoiceData,
        project_count: int,
        reference_date: datetime | None = None,
    ) -> CostComponents:
        """
        Calculate improved cost-to-serve effort score.

        Args:
            tasks: All tasks associated with the client.
            assignees: List of distinct assignee IDs.
            threads: Communication threads.
            invoices: Invoice metadata.
            project_count: Number of projects for this client.
            reference_date: Date for age calculations (default: now).

        Returns:
            CostComponents with total_effort_score.
        """
        if reference_date is None:
            reference_date = datetime.now()

        task_age = self._weighted_task_age_sum(tasks, reference_date)
        diversity = self._assignee_diversity_factor(assignees)
        comm = self._weighted_communication_effort(threads)
        proj = self._project_overhead(project_count)
        inv = self._invoice_overhead(invoices)

        total = task_age + diversity + comm + proj + inv

        return CostComponents(
            weighted_task_age_sum=task_age,
            assignee_diversity_factor=diversity,
            weighted_comm_effort=comm,
            project_overhead=proj,
            invoice_overhead=inv,
            total_effort_score=total,
        )

    def _weighted_task_age_sum(
        self,
        tasks: list[TaskData],
        reference_date: datetime,
    ) -> float:
        """Sum of task ages weighted by status."""
        total = 0.0
        for task in tasks:
            age_days = max(0, (reference_date - task.created_at).days)
            weight = STATUS_WEIGHTS.get(task.status, 1.0)
            total += age_days * weight
        return total

    def _assignee_diversity_factor(self, assignees: list[str]) -> float:
        """Context-switching cost from diverse team."""
        distinct = len({a for a in assignees if a})
        if distinct <= 0:
            return 0.0
        return math.sqrt(distinct) * 2.5

    def _weighted_communication_effort(
        self,
        threads: list[ThreadMetadata],
    ) -> float:
        """Communication cost from thread depth and volume."""
        total = 0.0
        for thread in threads:
            depth_factor = min(thread.thread_depth, 10) / 5.0
            bucket = self._get_message_depth_bucket(thread.message_count)
            channel_w = self._get_channel_weight(thread.channel)
            total += depth_factor * bucket * channel_w
        return total

    def _get_message_depth_bucket(self, message_count: int) -> float:
        """Map message count to effort multiplier."""
        if message_count <= 1:
            return 0.5
        if message_count <= 5:
            return 1.0
        if message_count <= 15:
            return 1.5
        return 2.0

    def _get_channel_weight(self, channel: str) -> float:
        """Weight for communication channel type."""
        return CHANNEL_WEIGHTS.get(channel, 1.0)

    def _project_overhead(self, project_count: int) -> float:
        """Overhead from managing multiple projects."""
        if project_count <= 0:
            return 0.0
        return math.sqrt(project_count) * 10

    def _invoice_overhead(self, invoices: InvoiceData) -> float:
        """
        Accounting complexity from invoicing.

        Formula: (invoice_count / max(total_invoiced_amount, 1)) × 100
        Capped at 50.0 to prevent domination of total score.
        """
        if invoices.invoice_count <= 0:
            return 0.0
        denominator = max(invoices.total_invoiced_amount, 1.0)
        overhead = (invoices.invoice_count / denominator) * 100
        return min(overhead, 50.0)
