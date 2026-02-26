"""
Tests for ImprovedCostCalculator — multi-factor cost proxies.

Brief 18 (ID), Task ID-2.1 + ID-6.1
"""

from datetime import datetime, timedelta

import pytest

from lib.intelligence.cost_proxies import (
    ImprovedCostCalculator,
    InvoiceData,
    TaskData,
    ThreadMetadata,
)


@pytest.fixture
def calc():
    return ImprovedCostCalculator()


def _task(status, days_old, assignee="person_1"):
    ref = datetime(2026, 4, 15, 12, 0)
    return TaskData(
        task_id=f"t_{status}_{days_old}",
        created_at=ref - timedelta(days=days_old),
        status=status,
        assignee_id=assignee,
    )


def _thread(msgs, depth, channel="email"):
    return ThreadMetadata(
        thread_id=f"th_{msgs}_{depth}",
        message_count=msgs,
        thread_depth=depth,
        channel=channel,
    )


class TestWeightedTaskAge:
    def test_completed_lower_weight(self, calc):
        ref = datetime(2026, 4, 15, 12, 0)
        tasks = [_task("completed", 10)]
        result = calc.calculate(tasks, [], [], InvoiceData(0, 0, 0), 0, ref)
        completed_score = result.weighted_task_age_sum

        tasks2 = [_task("overdue", 10)]
        result2 = calc.calculate(tasks2, [], [], InvoiceData(0, 0, 0), 0, ref)
        overdue_score = result2.weighted_task_age_sum

        assert overdue_score > completed_score

    def test_empty_tasks(self, calc):
        result = calc.calculate([], [], [], InvoiceData(0, 0, 0), 0)
        assert result.weighted_task_age_sum == 0.0

    def test_age_multiplied(self, calc):
        ref = datetime(2026, 4, 15, 12, 0)
        # Active task, 10 days old, weight 1.5 → 15
        tasks = [_task("active", 10)]
        result = calc.calculate(tasks, [], [], InvoiceData(0, 0, 0), 0, ref)
        assert result.weighted_task_age_sum == pytest.approx(15.0)


class TestAssigneeDiversity:
    def test_single_assignee(self, calc):
        result = calc.calculate([], ["p1"], [], InvoiceData(0, 0, 0), 0)
        assert result.assignee_diversity_factor == pytest.approx(2.5)

    def test_four_assignees(self, calc):
        result = calc.calculate([], ["p1", "p2", "p3", "p4"], [], InvoiceData(0, 0, 0), 0)
        # sqrt(4) * 2.5 = 5.0
        assert result.assignee_diversity_factor == pytest.approx(5.0)

    def test_no_assignees(self, calc):
        result = calc.calculate([], [], [], InvoiceData(0, 0, 0), 0)
        assert result.assignee_diversity_factor == 0.0


class TestCommunicationEffort:
    def test_single_email_thread(self, calc):
        threads = [_thread(msgs=3, depth=2, channel="email")]
        result = calc.calculate([], [], threads, InvoiceData(0, 0, 0), 0)
        # depth_factor = min(2, 10)/5 = 0.4
        # bucket for 3 msgs = 1.0
        # channel weight for email = 1.0
        # 0.4 * 1.0 * 1.0 = 0.4
        assert result.weighted_comm_effort == pytest.approx(0.4)

    def test_deep_slack_thread(self, calc):
        threads = [_thread(msgs=20, depth=15, channel="slack")]
        result = calc.calculate([], [], threads, InvoiceData(0, 0, 0), 0)
        # depth_factor = min(15, 10)/5 = 2.0
        # bucket for 20 msgs = 2.0
        # channel weight for slack = 0.8
        # 2.0 * 2.0 * 0.8 = 3.2
        assert result.weighted_comm_effort == pytest.approx(3.2)

    def test_asana_comment(self, calc):
        threads = [_thread(msgs=1, depth=1, channel="asana_comment")]
        result = calc.calculate([], [], threads, InvoiceData(0, 0, 0), 0)
        # depth_factor = 0.2, bucket = 0.5, channel = 0.6
        # 0.2 * 0.5 * 0.6 = 0.06
        assert result.weighted_comm_effort == pytest.approx(0.06)


class TestProjectOverhead:
    def test_single_project(self, calc):
        result = calc.calculate([], [], [], InvoiceData(0, 0, 0), 1)
        assert result.project_overhead == pytest.approx(10.0)

    def test_four_projects(self, calc):
        result = calc.calculate([], [], [], InvoiceData(0, 0, 0), 4)
        assert result.project_overhead == pytest.approx(20.0)  # sqrt(4)*10

    def test_no_projects(self, calc):
        result = calc.calculate([], [], [], InvoiceData(0, 0, 0), 0)
        assert result.project_overhead == 0.0


class TestInvoiceOverhead:
    def test_efficient_billing(self, calc):
        invoices = InvoiceData(2, 100000, 5.0)
        result = calc.calculate([], [], [], invoices, 0)
        # 2 / 100000 * 100 = 0.002
        assert result.invoice_overhead < 1.0

    def test_fragmented_billing(self, calc):
        invoices = InvoiceData(50, 500, 2.0)
        result = calc.calculate([], [], [], invoices, 0)
        # 50 / 500 * 100 = 10.0
        assert result.invoice_overhead == pytest.approx(10.0)

    def test_zero_amount(self, calc):
        invoices = InvoiceData(5, 0, 0)
        result = calc.calculate([], [], [], invoices, 0)
        # 5 / 1 * 100 = 500 → capped at 50
        assert result.invoice_overhead == 50.0

    def test_no_invoices(self, calc):
        invoices = InvoiceData(0, 0, 0)
        result = calc.calculate([], [], [], invoices, 0)
        assert result.invoice_overhead == 0.0


class TestTotalEffortScore:
    def test_complex_client(self, calc):
        ref = datetime(2026, 4, 15, 12, 0)
        tasks = [_task("overdue", 30, "p1"), _task("active", 10, "p2")]
        threads = [_thread(10, 5, "email"), _thread(3, 2, "slack")]
        invoices = InvoiceData(10, 50000, 3.0)
        result = calc.calculate(tasks, ["p1", "p2"], threads, invoices, 3, ref)

        assert result.total_effort_score > 0
        # Total should be sum of all components
        expected_total = (
            result.weighted_task_age_sum
            + result.assignee_diversity_factor
            + result.weighted_comm_effort
            + result.project_overhead
            + result.invoice_overhead
        )
        assert result.total_effort_score == pytest.approx(expected_total)

    def test_simple_client(self, calc):
        result = calc.calculate([], ["p1"], [], InvoiceData(1, 10000, 1.0), 1)
        assert result.total_effort_score > 0
        assert result.total_effort_score < 20  # Simple client = low score
