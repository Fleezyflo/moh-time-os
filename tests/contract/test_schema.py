"""
Schema Tests — Validate Pydantic models for agency snapshot.

Per IMPLEMENTATION_PLAN_V4_FROZEN.md:
- All required fields must be present
- Missing sections = validation failure
- cash_ar: null must fail
- schema_version must match SCHEMA_VERSION constant

Per PAGE0_AGENCY_CONTROL_ROOM_SPEC.md:
- narrative, tiles, constraints, exceptions, drawers are REQUIRED (locked structure)
"""

import pytest
from pydantic import ValidationError

from lib.contracts.schema import (
    SCHEMA_VERSION,
    AgencySnapshotContract,
    DebtorEntry,
    HeatstripProject,
)


def make_valid_snapshot(**overrides):
    """
    Create a minimal valid snapshot with all required fields.

    Per Page 0 spec, required fields include:
    - meta, trust, narrative, tiles, heatstrip_projects, constraints, exceptions, drawers
    - Plus Page 1+ extensions: cash_ar, delivery_command, client_360, comms_commitments, capacity_command
    """
    base = {
        "meta": {
            "generated_at": "2024-01-01T00:00:00",
            "mode": "Ops Head",
            "horizon": "THIS_WEEK",
            "schema_version": SCHEMA_VERSION,
            "scope": {
                "lanes": [],
                "owners": [],
                "clients": [],
                "include_internal": False,
            },
        },
        "trust": {"coverage": {}, "partial_domains": [], "gate_states": {}},
        # Page 0 LOCKED STRUCTURE - ALL REQUIRED
        "narrative": {"first_to_break": None, "deltas": []},
        "tiles": {
            "delivery": {"badge": "GREEN", "summary": "OK", "cta": ""},
            "cash": {"badge": "GREEN", "summary": "OK", "cta": ""},
            "clients": {"badge": "GREEN", "summary": "OK", "cta": ""},
            "churn_x_money": {"badge": "GREEN", "summary": "OK", "cta": "", "top": []},
            "delivery_x_capacity": {
                "badge": "GREEN",
                "summary": "OK",
                "cta": "",
                "top": [],
            },
        },
        "heatstrip_projects": [],
        "constraints": [],
        "exceptions": [],
        "drawers": {},
        # Page 1+ Extensions - REQUIRED for full dashboard
        "cash_ar": {
            "tiles": {
                "valid_ar": {"AED": 0},
                "severe_ar": {"AED": 0},
                "badge": "GREEN",
                "summary": "No AR",
            },
            "debtors": [],
        },
        "delivery_command": {"portfolio": []},
        "client_360": {"portfolio": [], "at_risk_count": 0},
        "comms_commitments": {"threads": [], "commitments": []},
        "capacity_command": {"people_overview": []},
    }
    base.update(overrides)
    return base


class TestAgencySnapshotContract:
    """Test the top-level snapshot contract."""

    def test_valid_minimal_snapshot(self):
        """Minimal valid snapshot should pass."""
        snapshot = make_valid_snapshot()

        contract = AgencySnapshotContract.model_validate(snapshot)
        assert contract.meta.mode == "Ops Head"
        assert contract.meta.schema_version == SCHEMA_VERSION
        assert len(contract.heatstrip_projects) == 0
        # Verify Page 0 locked fields are present
        assert contract.narrative is not None
        assert contract.tiles is not None
        assert contract.constraints is not None
        assert contract.exceptions is not None
        assert contract.drawers is not None

    def test_missing_narrative_fails(self):
        """Missing narrative section must fail (Page 0 locked structure)."""
        snapshot = make_valid_snapshot()
        del snapshot["narrative"]

        with pytest.raises(ValidationError) as exc:
            AgencySnapshotContract.model_validate(snapshot)

        assert "narrative" in str(exc.value)

    def test_missing_tiles_fails(self):
        """Missing tiles section must fail (Page 0 locked structure)."""
        snapshot = make_valid_snapshot()
        del snapshot["tiles"]

        with pytest.raises(ValidationError) as exc:
            AgencySnapshotContract.model_validate(snapshot)

        assert "tiles" in str(exc.value)

    def test_missing_cash_ar_fails(self):
        """Missing cash_ar section must fail validation."""
        snapshot = make_valid_snapshot()
        del snapshot["cash_ar"]

        with pytest.raises(ValidationError) as exc:
            AgencySnapshotContract.model_validate(snapshot)

        assert "cash_ar" in str(exc.value)

    def test_null_cash_ar_fails(self):
        """cash_ar: null must fail validation."""
        snapshot = make_valid_snapshot(cash_ar=None)

        with pytest.raises(ValidationError) as exc:
            AgencySnapshotContract.model_validate(snapshot)

        assert (
            "cash_ar cannot be None" in str(exc.value)
            or "none is not an allowed" in str(exc.value).lower()
        )

    def test_null_heatstrip_fails(self):
        """heatstrip_projects: null must fail validation."""
        snapshot = make_valid_snapshot(heatstrip_projects=None)

        with pytest.raises(ValidationError):
            AgencySnapshotContract.model_validate(snapshot)

    def test_schema_version_mismatch_fails(self):
        """Snapshot with wrong schema_version must fail validation."""
        snapshot = make_valid_snapshot()
        snapshot["meta"]["schema_version"] = "1.0.0"  # Wrong version

        with pytest.raises(ValidationError) as exc:
            AgencySnapshotContract.model_validate(snapshot)

        assert "Schema version mismatch" in str(exc.value)
        assert "1.0.0" in str(exc.value)
        assert SCHEMA_VERSION in str(exc.value)

    def test_schema_version_correct_passes(self):
        """Snapshot with correct schema_version should pass."""
        snapshot = make_valid_snapshot()

        contract = AgencySnapshotContract.model_validate(snapshot)
        assert contract.meta.schema_version == SCHEMA_VERSION


class TestSchemaVersion:
    """Test schema version binding to UI spec."""

    def test_schema_version_is_2_9_0(self):
        """SCHEMA_VERSION must be exactly 2.9.0 (bound to UI spec)."""
        assert (
            SCHEMA_VERSION == "2.9.0"
        ), f"SCHEMA_VERSION must be '2.9.0' (UI spec version), got '{SCHEMA_VERSION}'"

    def test_schema_version_exported(self):
        """SCHEMA_VERSION must be importable from lib.contracts."""
        from lib.contracts import SCHEMA_VERSION as imported_version

        assert imported_version == "2.9.0"


class TestDebtorEntry:
    """Test debtor entry validation."""

    def test_valid_debtor(self):
        """Valid debtor entry should pass."""
        debtor = DebtorEntry(
            client_id="client-1",
            client_name="Acme Corp",
            currency="AED",
            total_valid_ar=10000.0,
            severe_ar=5000.0,
            aging_bucket="61-90",
            days_overdue_max=75,
            invoice_count=3,
            risk_score=0.7,
        )

        assert debtor.client_id == "client-1"
        assert debtor.risk_score == 0.7

    def test_risk_score_bounds(self):
        """Risk score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            DebtorEntry(
                client_id="client-1",
                client_name="Test",
                total_valid_ar=100,
                aging_bucket="current",
                risk_score=1.5,  # > 1.0
            )


class TestHeatstripProject:
    """Test heatstrip project validation."""

    def test_valid_project(self):
        """Valid heatstrip project should pass."""
        project = HeatstripProject(
            project_id="proj-1",
            name="Test Project",
            status="RED",
            slip_risk_score=0.8,
            time_to_slip_hours=24.0,
            top_driver="Overdue tasks",
            confidence="HIGH",
        )

        assert project.status == "RED"
        assert project.slip_risk_score == 0.8

    def test_invalid_status(self):
        """Invalid status should fail."""
        with pytest.raises(ValidationError):
            HeatstripProject(
                project_id="proj-1",
                name="Test",
                status="INVALID",  # Not in allowed values
            )
