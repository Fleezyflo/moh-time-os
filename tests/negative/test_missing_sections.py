"""
Negative Tests: Missing Sections

These tests verify that the schema validation REJECTS snapshots with missing sections.
This catches the exact bug we had: generator silently omitting sections.

Per IMPLEMENTATION_PLAN Amendment: Negative tests must FAIL on old broken behavior.
"""

import pytest
from pydantic import ValidationError

from lib.contracts import AgencySnapshotContract


class TestMissingSections:
    """Test that missing required sections cause validation failure."""

    def _base_snapshot(self) -> dict:
        """Base valid snapshot to mutate."""
        return {
            "meta": {
                "generated_at": "2026-02-09T14:00:00",
                "mode": "ops_head",
                "horizon": "this_week",
                "version": "1.0",
            },
            "trust": {"coverage": {}, "partial_domains": [], "gate_states": {}},
            "heatstrip_projects": [],
            "cash_ar": {
                "tiles": {
                    "valid_ar": {},
                    "severe_ar": {},
                    "badge": "GREEN",
                    "summary": "",
                },
                "debtors": [],
                "aging_distribution": [],
            },
            "delivery_command": {"portfolio": [], "selected_project": None},
            "client_360": {"portfolio": [], "at_risk_count": 0, "drawer": {}},
            "comms_commitments": {"threads": [], "commitments": [], "overdue_count": 0},
            "capacity_command": {
                "people_overview": [],
                "total_assigned": 0,
                "total_capacity": 0,
                "utilization_rate": 0,
                "drawer": {},
            },
        }

    def test_rejects_missing_cash_ar(self):
        """
        NEGATIVE: Snapshot without cash_ar section must fail validation.
        This catches the exact bug: generator silently omitting cash_ar.
        """
        snapshot = self._base_snapshot()
        del snapshot["cash_ar"]

        with pytest.raises(ValidationError) as exc_info:
            AgencySnapshotContract.model_validate(snapshot)

        assert "cash_ar" in str(exc_info.value)

    def test_rejects_null_cash_ar(self):
        """NEGATIVE: cash_ar: null must fail."""
        snapshot = self._base_snapshot()
        snapshot["cash_ar"] = None

        with pytest.raises(ValidationError):
            AgencySnapshotContract.model_validate(snapshot)

    def test_rejects_missing_delivery_command(self):
        """NEGATIVE: Missing delivery_command must fail."""
        snapshot = self._base_snapshot()
        del snapshot["delivery_command"]

        with pytest.raises(ValidationError) as exc_info:
            AgencySnapshotContract.model_validate(snapshot)

        assert "delivery_command" in str(exc_info.value)

    def test_rejects_missing_client_360(self):
        """NEGATIVE: Missing client_360 must fail."""
        snapshot = self._base_snapshot()
        del snapshot["client_360"]

        with pytest.raises(ValidationError) as exc_info:
            AgencySnapshotContract.model_validate(snapshot)

        assert "client_360" in str(exc_info.value)

    def test_rejects_missing_comms_commitments(self):
        """NEGATIVE: Missing comms_commitments must fail."""
        snapshot = self._base_snapshot()
        del snapshot["comms_commitments"]

        with pytest.raises(ValidationError) as exc_info:
            AgencySnapshotContract.model_validate(snapshot)

        assert "comms_commitments" in str(exc_info.value)

    def test_rejects_missing_capacity_command(self):
        """NEGATIVE: Missing capacity_command must fail."""
        snapshot = self._base_snapshot()
        del snapshot["capacity_command"]

        with pytest.raises(ValidationError) as exc_info:
            AgencySnapshotContract.model_validate(snapshot)

        assert "capacity_command" in str(exc_info.value)

    def test_rejects_missing_heatstrip_projects(self):
        """NEGATIVE: Missing heatstrip_projects must fail."""
        snapshot = self._base_snapshot()
        del snapshot["heatstrip_projects"]

        with pytest.raises(ValidationError) as exc_info:
            AgencySnapshotContract.model_validate(snapshot)

        assert "heatstrip_projects" in str(exc_info.value)

    def test_rejects_null_heatstrip_projects(self):
        """NEGATIVE: heatstrip_projects: null must fail."""
        snapshot = self._base_snapshot()
        snapshot["heatstrip_projects"] = None

        with pytest.raises(ValidationError):
            AgencySnapshotContract.model_validate(snapshot)
