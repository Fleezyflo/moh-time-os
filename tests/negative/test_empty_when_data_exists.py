"""
Negative Tests: Empty Sections When Data Exists

These tests verify that predicates REJECT empty sections when source data exists.
This catches: heatstrip_projects: [] while portfolio has items.

Per IMPLEMENTATION_PLAN Amendment: Negative tests must FAIL on old broken behavior.
"""

import pytest

from lib.contracts import PredicateViolation, enforce_predicates_strict
from lib.contracts.predicates import NormalizedData


class TestEmptyWhenDataExists:
    """Test that predicates fail when sections are empty but data exists."""

    def test_rejects_empty_debtors_when_invoices_exist(self):
        """
        NEGATIVE: Empty debtors when unpaid invoices exist must fail.
        """
        normalized = NormalizedData(
            projects=[],
            clients=[],
            invoices=[
                {
                    "id": "inv1",
                    "status": "sent",
                    "payment_date": None,
                    "is_unpaid": True,
                },
                {
                    "id": "inv2",
                    "status": "overdue",
                    "payment_date": None,
                    "is_unpaid": True,
                },
            ],
            commitments=[],
            communications=[],
            people=[],
        )
        snapshot = {
            "cash_ar": {"debtors": []},  # Empty but invoices exist
            "heatstrip_projects": [],
            "comms_commitments": {"threads": [], "commitments": []},
            "capacity_command": {"people_overview": []},
        }

        with pytest.raises(PredicateViolation) as exc_info:
            enforce_predicates_strict(normalized, snapshot)

        assert "cash_ar.debtors" in str(exc_info.value)
        assert "unpaid_invoices=2" in str(exc_info.value)

    def test_rejects_empty_heatstrip_when_projects_exist(self):
        """
        NEGATIVE: Empty heatstrip when projects exist must fail.
        """
        normalized = NormalizedData(
            projects=[
                {"id": "p1", "name": "Project A", "status": "active"},
                {"id": "p2", "name": "Project B", "status": "active"},
            ],
            clients=[],
            invoices=[],
            commitments=[],
            communications=[],
            people=[],
        )
        snapshot = {
            "heatstrip_projects": [],  # Empty but projects exist
            "cash_ar": {"debtors": []},
            "comms_commitments": {"threads": [], "commitments": []},
            "capacity_command": {"people_overview": []},
        }

        with pytest.raises(PredicateViolation) as exc_info:
            enforce_predicates_strict(normalized, snapshot)

        assert "heatstrip_projects" in str(exc_info.value)
        assert "projects_count=2" in str(exc_info.value)

    def test_rejects_empty_threads_when_communications_exist(self):
        """
        NEGATIVE: Empty threads when communications exist must fail.
        """
        normalized = NormalizedData(
            projects=[],
            clients=[],
            invoices=[],
            commitments=[],
            communications=[
                {"id": "c1", "subject": "Email 1"},
                {"id": "c2", "subject": "Email 2"},
                {"id": "c3", "subject": "Email 3"},
            ],
            people=[],
        )
        snapshot = {
            "heatstrip_projects": [],
            "cash_ar": {"debtors": []},
            "comms_commitments": {"threads": [], "commitments": []},  # Empty threads
            "capacity_command": {"people_overview": []},
        }

        with pytest.raises(PredicateViolation) as exc_info:
            enforce_predicates_strict(normalized, snapshot)

        assert "comms_commitments.threads" in str(exc_info.value)
        assert "communications_count=3" in str(exc_info.value)

    def test_rejects_empty_people_when_assignments_exist(self):
        """
        NEGATIVE: Empty people_overview when people have assignments must fail.
        """
        normalized = NormalizedData(
            projects=[],
            clients=[],
            invoices=[],
            commitments=[],
            communications=[],
            people=[
                {"name": "Alice", "hours_assigned": 20.0},
                {"name": "Bob", "hours_assigned": 15.5},
            ],
        )
        snapshot = {
            "heatstrip_projects": [],
            "cash_ar": {"debtors": []},
            "comms_commitments": {"threads": [], "commitments": []},
            "capacity_command": {"people_overview": []},  # Empty
        }

        with pytest.raises(PredicateViolation) as exc_info:
            enforce_predicates_strict(normalized, snapshot)

        assert "capacity_command.people_overview" in str(exc_info.value)
        assert "people_with_assignments=2" in str(exc_info.value)

    def test_allows_empty_when_no_source_data(self):
        """
        POSITIVE: Empty sections are allowed when no source data exists.
        """
        normalized = NormalizedData(
            projects=[],
            clients=[],
            invoices=[],
            commitments=[],
            communications=[],
            people=[],
        )
        snapshot = {
            "heatstrip_projects": [],
            "cash_ar": {"debtors": []},
            "comms_commitments": {"threads": [], "commitments": []},
            "capacity_command": {"people_overview": []},
        }

        # Should NOT raise
        enforce_predicates_strict(normalized, snapshot)
