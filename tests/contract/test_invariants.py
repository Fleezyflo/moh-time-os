"""
Invariant Tests — Validate semantic correctness checks.

Per IMPLEMENTATION_PLAN_V4_FROZEN.md Amendment 4:
- Invariants run in PRODUCTION, not just tests
- Cross-check: same metric computed two ways must match
"""

import pytest

from lib.contracts.invariants import (
    InvariantViolation,
    check_ar_totals_match,
    check_commitment_resolution_complete,
    check_heatstrip_subset_of_portfolio,
    check_no_orphan_commitments,
    enforce_invariants,
)
from lib.contracts.predicates import NormalizedData


class TestARTotalsInvariant:
    """Test AR totals cross-check invariant."""

    def test_passes_when_totals_match(self):
        """Passes when tiles total equals debtors total."""
        snapshot = {
            "cash_ar": {
                "tiles": {"valid_ar": {"AED": 10000.0}},
                "debtors": [
                    {"total_valid_ar": 6000.0},
                    {"total_valid_ar": 4000.0},
                ],
            }
        }
        normalized = NormalizedData()

        # Should not raise
        check_ar_totals_match(snapshot, normalized)

    def test_fails_when_totals_mismatch(self):
        """Fails when tiles total doesn't equal debtors total."""
        snapshot = {
            "cash_ar": {
                "tiles": {"valid_ar": {"AED": 10000.0}},
                "debtors": [
                    {"total_valid_ar": 5000.0},  # Only 5000, not 10000
                ],
            }
        }
        normalized = NormalizedData()

        with pytest.raises(InvariantViolation, match="AR totals mismatch"):
            check_ar_totals_match(snapshot, normalized)


class TestCommitmentResolutionInvariant:
    """Test commitment resolution completeness invariant."""

    def test_passes_when_all_resolved_or_have_reason(self):
        """Passes when all commitments are resolved or have unresolved_reason."""
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {"commitment_id": "c1", "resolved_client_id": "client-1"},
                    {
                        "commitment_id": "c2",
                        "resolved_client_id": None,
                        "unresolved_reason": "No match found",
                    },
                ]
            }
        }
        normalized = NormalizedData()

        # Should not raise
        check_commitment_resolution_complete(snapshot, normalized)

    def test_fails_when_none_without_reason(self):
        """Fails when commitment has None client_id AND None reason."""
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {
                        "commitment_id": "c1",
                        "resolved_client_id": None,
                        "unresolved_reason": None,  # BAD - no reason
                    },
                ]
            }
        }
        normalized = NormalizedData()

        with pytest.raises(InvariantViolation, match="no resolution AND no reason"):
            check_commitment_resolution_complete(snapshot, normalized)


class TestHeatstripSubsetInvariant:
    """Test heatstrip subset of portfolio invariant."""

    def test_passes_when_heatstrip_subset_of_portfolio(self):
        """Passes when all heatstrip projects exist in portfolio."""
        snapshot = {
            "delivery_command": {
                "portfolio": [
                    {"project_id": "proj-1"},
                    {"project_id": "proj-2"},
                    {"project_id": "proj-3"},
                ]
            },
            "heatstrip_projects": [
                {"project_id": "proj-1"},
                {"project_id": "proj-2"},
            ],
        }
        normalized = NormalizedData()

        # Should not raise
        check_heatstrip_subset_of_portfolio(snapshot, normalized)

    def test_fails_when_heatstrip_has_orphan(self):
        """Fails when heatstrip contains project not in portfolio."""
        snapshot = {
            "delivery_command": {
                "portfolio": [
                    {"project_id": "proj-1"},
                ]
            },
            "heatstrip_projects": [
                {"project_id": "proj-1"},
                {"project_id": "proj-999"},  # ORPHAN - not in portfolio
            ],
        }
        normalized = NormalizedData()

        with pytest.raises(InvariantViolation, match="not in portfolio"):
            check_heatstrip_subset_of_portfolio(snapshot, normalized)


class TestOrphanCommitmentsInvariant:
    """Test no orphan commitments invariant (Amendment 2)."""

    def test_passes_when_all_types_known(self):
        """Passes when all scope_ref_type values are known."""
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {"commitment_id": "c1", "scope_ref_type": "client"},
                    {"commitment_id": "c2", "scope_ref_type": "project"},
                    {"commitment_id": "c3", "scope_ref_type": "thread"},
                ]
            }
        }
        normalized = NormalizedData()

        # Should not raise
        check_no_orphan_commitments(snapshot, normalized)

    def test_fails_when_unknown_type(self):
        """Fails when commitment has unknown scope_ref_type."""
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {
                        "commitment_id": "c1",
                        "scope_ref_type": "unknown_type",  # BAD - unknown
                    },
                ]
            }
        }
        normalized = NormalizedData()

        with pytest.raises(InvariantViolation, match="unknown scope_ref_type"):
            check_no_orphan_commitments(snapshot, normalized)


class TestEnforceInvariants:
    """Test invariant enforcement."""

    def test_returns_violations_list(self):
        """Returns list of all violations."""
        snapshot = {
            "cash_ar": {
                "tiles": {"valid_ar": {"AED": 10000}},
                "debtors": [{"total_valid_ar": 5000}],  # Mismatch
            },
            "comms_commitments": {"commitments": []},
            "delivery_command": {"portfolio": []},
            "heatstrip_projects": [],
        }
        normalized = NormalizedData()

        violations = enforce_invariants(snapshot, normalized)
        assert len(violations) >= 1
        assert any("AR totals mismatch" in v for v in violations)
