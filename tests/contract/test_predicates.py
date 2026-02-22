"""
Predicate Tests — Validate section existence rules.

Per IMPLEMENTATION_PLAN_V4_FROZEN.md:
- If data exists, section must exist
- Empty section when data exists = violation
"""

import pytest

from lib.contracts.predicates import (
    NormalizedData,
    PredicateViolation,
    cash_ar_debtors_must_exist,
    enforce_predicates,
    enforce_predicates_strict,
    heatstrip_must_exist,
)


class TestHeatstripPredicate:
    """Test heatstrip existence predicate."""

    def test_must_exist_when_projects_exist(self):
        """Heatstrip required if any project exists."""
        normalized = NormalizedData(projects=[{"project_id": "proj-1", "name": "Test"}])
        must_exist, reason = heatstrip_must_exist(normalized)

        assert must_exist is True
        assert "projects_count=1" in reason

    def test_not_required_when_no_projects(self):
        """Heatstrip not required if no projects."""
        normalized = NormalizedData(projects=[])
        must_exist, reason = heatstrip_must_exist(normalized)

        assert must_exist is False


class TestCashARDebtorsPredicate:
    """Test debtors existence predicate."""

    def test_must_exist_when_unpaid_invoices(self):
        """Debtors required if unpaid invoices exist."""
        # Create invoice with is_unpaid property (dict style)
        normalized = NormalizedData(invoices=[{"status": "sent", "payment_date": None}])
        must_exist, reason = cash_ar_debtors_must_exist(normalized)

        assert must_exist is True
        assert "unpaid_invoices=1" in reason

    def test_not_required_when_no_unpaid(self):
        """Debtors not required if no unpaid invoices."""
        normalized = NormalizedData(invoices=[{"status": "paid", "payment_date": "2024-01-01"}])
        must_exist, reason = cash_ar_debtors_must_exist(normalized)

        assert must_exist is False


class TestEnforcePredicates:
    """Test predicate enforcement."""

    def test_empty_list_when_all_pass(self):
        """Returns empty list when all predicates pass."""
        normalized = NormalizedData()
        snapshot = {
            "heatstrip_projects": [],
            "cash_ar": {"debtors": []},
            "comms_commitments": {"threads": []},
            "capacity_command": {"people_overview": []},
        }

        violations = enforce_predicates(normalized, snapshot)
        assert violations == []

    def test_catches_empty_section_when_data_exists(self):
        """Catches violation when section empty but data exists."""
        normalized = NormalizedData(projects=[{"project_id": "proj-1", "name": "Test"}])
        snapshot = {
            "heatstrip_projects": [],  # EMPTY when projects exist
            "cash_ar": {"debtors": []},
            "comms_commitments": {"threads": []},
            "capacity_command": {"people_overview": []},
        }

        violations = enforce_predicates(normalized, snapshot)
        assert len(violations) == 1
        assert "heatstrip_projects" in violations[0]

    def test_strict_mode_raises(self):
        """Strict mode raises on first violation."""
        normalized = NormalizedData(projects=[{"project_id": "proj-1", "name": "Test"}])
        snapshot = {
            "heatstrip_projects": [],  # EMPTY when projects exist
            "cash_ar": {"debtors": []},
            "comms_commitments": {"threads": []},
            "capacity_command": {"people_overview": []},
        }

        with pytest.raises(PredicateViolation):
            enforce_predicates_strict(normalized, snapshot)
