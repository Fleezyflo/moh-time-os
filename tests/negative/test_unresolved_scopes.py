"""
Negative Tests: Unresolved Scopes

These tests verify that invariants REJECT commitments with no resolution AND no reason.
This catches: lazy resolver returning None without explanation.

Per IMPLEMENTATION_PLAN Amendment 2: Unknown scope types must fail fast.
Per IMPLEMENTATION_PLAN: Unknowns fail loudly (resolved=False, unresolved_reason=...).
"""

import pytest

from lib.contracts import InvariantViolation, enforce_invariants_strict
from lib.contracts.predicates import NormalizedData


class TestUnresolvedScopes:
    """Test that invariants fail on invalid resolution states."""

    def test_rejects_none_without_reason(self):
        """
        NEGATIVE: resolved_client_id=None WITHOUT unresolved_reason must fail.
        No silent None values allowed.
        """
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {
                        "commitment_id": "cmt-1",
                        "content": "Will deliver by Friday",
                        "scope_ref_type": "project",
                        "scope_ref_id": "proj-123",
                        "resolved_client_id": None,  # Not resolved
                        "unresolved_reason": None,  # No reason - BAD
                    }
                ],
                "threads": [],
            },
            "cash_ar": {"debtors": [], "tiles": {}},
            "heatstrip_projects": [],
            "delivery_command": {"portfolio": []},
            "client_360": {"portfolio": [], "at_risk_count": 0},
            "capacity_command": {"people_overview": []},
        }
        normalized = NormalizedData()

        with pytest.raises(InvariantViolation) as exc_info:
            enforce_invariants_strict(snapshot, normalized)

        assert "cmt-1" in str(exc_info.value)
        assert "no resolution AND no reason" in str(exc_info.value)

    def test_rejects_multiple_unresolved_without_reason(self):
        """
        NEGATIVE: Multiple commitments without resolution reason must all be reported.
        """
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {
                        "commitment_id": "cmt-1",
                        "resolved_client_id": None,
                        "unresolved_reason": None,
                    },
                    {
                        "commitment_id": "cmt-2",
                        "resolved_client_id": None,
                        "unresolved_reason": None,
                    },
                    {
                        "commitment_id": "cmt-3",
                        "resolved_client_id": "client-123",  # This one is resolved
                        "unresolved_reason": None,
                    },
                ],
                "threads": [],
            },
            "cash_ar": {"debtors": [], "tiles": {}},
            "heatstrip_projects": [],
            "delivery_command": {"portfolio": []},
            "client_360": {"portfolio": [], "at_risk_count": 0},
            "capacity_command": {"people_overview": []},
        }
        normalized = NormalizedData()

        with pytest.raises(InvariantViolation) as exc_info:
            enforce_invariants_strict(snapshot, normalized)

        error_msg = str(exc_info.value)
        assert "cmt-1" in error_msg
        assert "cmt-2" in error_msg
        assert "cmt-3" not in error_msg  # Should not be in error

    def test_allows_unresolved_with_reason(self):
        """
        POSITIVE: resolved_client_id=None WITH unresolved_reason is valid.
        """
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {
                        "commitment_id": "cmt-1",
                        "resolved_client_id": None,
                        "unresolved_reason": "Project not linked to any client",
                    }
                ],
                "threads": [],
            },
            "cash_ar": {"debtors": [], "tiles": {}},
            "heatstrip_projects": [],
            "delivery_command": {"portfolio": []},
            "client_360": {"portfolio": [], "at_risk_count": 0},
            "capacity_command": {"people_overview": []},
        }
        normalized = NormalizedData()

        # Should NOT raise
        enforce_invariants_strict(snapshot, normalized)

    def test_allows_resolved_commitment(self):
        """
        POSITIVE: resolved_client_id present is valid (no reason needed).
        """
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {
                        "commitment_id": "cmt-1",
                        "resolved_client_id": "client-abc",
                        "unresolved_reason": None,
                    }
                ],
                "threads": [],
            },
            "cash_ar": {"debtors": [], "tiles": {}},
            "heatstrip_projects": [],
            "delivery_command": {"portfolio": []},
            "client_360": {"portfolio": [], "at_risk_count": 0},
            "capacity_command": {"people_overview": []},
        }
        normalized = NormalizedData()

        # Should NOT raise
        enforce_invariants_strict(snapshot, normalized)

    def test_rejects_unknown_scope_ref_type(self):
        """
        NEGATIVE: Unknown scope_ref_type must fail (Amendment 2).
        """
        snapshot = {
            "comms_commitments": {
                "commitments": [
                    {
                        "commitment_id": "cmt-1",
                        "scope_ref_type": "unknown_type",  # Invalid type
                        "scope_ref_id": "xyz",
                        "resolved_client_id": "client-1",
                        "unresolved_reason": None,
                    }
                ],
                "threads": [],
            },
            "cash_ar": {"debtors": [], "tiles": {}},
            "heatstrip_projects": [],
            "delivery_command": {"portfolio": []},
            "client_360": {"portfolio": [], "at_risk_count": 0},
            "capacity_command": {"people_overview": []},
        }
        normalized = NormalizedData()

        with pytest.raises(InvariantViolation) as exc_info:
            enforce_invariants_strict(snapshot, normalized)

        assert "unknown_type" in str(exc_info.value)
