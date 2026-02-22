"""
Tests for CycleResult and PhaseResult dataclasses.

Covers:
- PhaseResult creation and tracking
- CycleResult aggregation
- Duration calculations
- Phase success/failure tracking
- Conversion to dictionaries
"""

from datetime import datetime, timedelta

import pytest

from lib.cycle_result import CycleResult, PhaseResult

# =============================================================================
# PHASERESULT TESTS
# =============================================================================


class TestPhaseResult:
    """Tests for PhaseResult dataclass."""

    def test_create_successful_phase_result(self):
        """Should create a successful phase result."""
        phase = PhaseResult(name="collect", success=True, duration_seconds=1.5, data={"items": 10})

        assert phase.name == "collect"
        assert phase.success is True
        assert phase.error is None
        assert phase.duration_seconds == 1.5
        assert phase.data == {"items": 10}

    def test_create_failed_phase_result(self):
        """Should create a failed phase result."""
        phase = PhaseResult(
            name="analyze", success=False, error="Database connection timeout", duration_seconds=5.0
        )

        assert phase.name == "analyze"
        assert phase.success is False
        assert phase.error == "Database connection timeout"
        assert phase.duration_seconds == 5.0

    def test_phase_result_defaults(self):
        """PhaseResult should have sensible defaults."""
        phase = PhaseResult(name="test", success=True)

        assert phase.error is None
        assert phase.duration_seconds == 0.0
        assert phase.data == {}

    def test_phase_result_with_complex_data(self):
        """PhaseResult should support complex data structures."""
        data = {
            "counters": {"processed": 100, "failed": 5},
            "items": [{"id": 1}, {"id": 2}],
            "nested": {"level": {"deep": "value"}},
        }
        phase = PhaseResult(name="normalize", success=True, data=data)

        assert phase.data == data


# =============================================================================
# CYCLERESULT TESTS
# =============================================================================


class TestCycleResult:
    """Tests for CycleResult dataclass."""

    def test_create_cycle_result(self):
        """Should create a cycle result with phases."""
        now = datetime.now()
        phases = [
            PhaseResult("collect", True, duration_seconds=1.0),
            PhaseResult("analyze", True, duration_seconds=2.0),
        ]

        cycle = CycleResult(
            cycle_number=1, started_at=now, completed_at=now + timedelta(seconds=3), phases=phases
        )

        assert cycle.cycle_number == 1
        assert cycle.started_at == now
        assert len(cycle.phases) == 2
        assert cycle.overall_success is True
        assert cycle.error is None

    def test_cycle_duration_calculation(self):
        """Duration property should calculate elapsed time."""
        now = datetime.now()
        cycle = CycleResult(
            cycle_number=1, started_at=now, completed_at=now + timedelta(seconds=5.5)
        )

        assert cycle.duration_seconds == pytest.approx(5.5, abs=0.1)

    def test_failed_phases_property(self):
        """failed_phases should return names of failed phases."""
        phases = [
            PhaseResult("collect", True),
            PhaseResult("analyze", False, error="Error 1"),
            PhaseResult("reason", False, error="Error 2"),
            PhaseResult("execute", True),
        ]

        cycle = CycleResult(
            cycle_number=1, started_at=datetime.now(), completed_at=datetime.now(), phases=phases
        )

        failed = cycle.failed_phases
        assert len(failed) == 2
        assert "analyze" in failed
        assert "reason" in failed
        assert "collect" not in failed

    def test_succeeded_phases_property(self):
        """succeeded_phases should return names of successful phases."""
        phases = [
            PhaseResult("collect", True),
            PhaseResult("analyze", False),
            PhaseResult("reason", True),
        ]

        cycle = CycleResult(
            cycle_number=1, started_at=datetime.now(), completed_at=datetime.now(), phases=phases
        )

        succeeded = cycle.succeeded_phases
        assert len(succeeded) == 2
        assert "collect" in succeeded
        assert "reason" in succeeded

    def test_cycle_result_to_dict(self):
        """to_dict should produce valid dictionary representation."""
        now = datetime.now()
        phases = [
            PhaseResult("collect", True, duration_seconds=1.0, data={"items": 10}),
            PhaseResult("analyze", False, error="timeout", duration_seconds=5.0),
        ]

        cycle = CycleResult(
            cycle_number=5,
            started_at=now,
            completed_at=now + timedelta(seconds=6),
            phases=phases,
            overall_success=False,
            error="Analyze phase timed out",
        )

        result_dict = cycle.to_dict()

        assert result_dict["cycle_number"] == 5
        assert result_dict["overall_success"] is False
        assert result_dict["error"] == "Analyze phase timed out"
        assert len(result_dict["phases"]) == 2
        assert result_dict["failed_phases"] == ["analyze"]
        assert result_dict["succeeded_phases"] == ["collect"]
        assert "duration_seconds" in result_dict

    def test_cycle_result_isoformat_timestamps(self):
        """to_dict should have ISO format timestamps."""
        now = datetime.now()
        cycle = CycleResult(cycle_number=1, started_at=now, completed_at=now + timedelta(seconds=1))

        result_dict = cycle.to_dict()

        # Should be able to parse back to datetime
        started = datetime.fromisoformat(result_dict["started_at"])
        completed = datetime.fromisoformat(result_dict["completed_at"])

        assert started == now
        assert completed > now

    def test_all_phases_succeeded(self):
        """Should track when all phases succeed."""
        phases = [PhaseResult(f"phase{i}", True) for i in range(5)]

        cycle = CycleResult(
            cycle_number=1,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            phases=phases,
            overall_success=True,
        )

        assert len(cycle.succeeded_phases) == 5
        assert len(cycle.failed_phases) == 0
        assert cycle.overall_success is True

    def test_mixed_success_failure(self):
        """Should handle mixed success and failure phases."""
        phases = [
            PhaseResult("collect", True, duration_seconds=1.0),
            PhaseResult("normalize", True, duration_seconds=2.0),
            PhaseResult("analyze", False, error="DB error", duration_seconds=3.0),
            PhaseResult("reason", False, error="skipped", duration_seconds=0.0),
            PhaseResult("execute", True, duration_seconds=0.5),
        ]

        cycle = CycleResult(
            cycle_number=10,
            started_at=datetime.now(),
            completed_at=datetime.now() + timedelta(seconds=6.5),
            phases=phases,
            overall_success=False,
        )

        assert len(cycle.phases) == 5
        assert len(cycle.succeeded_phases) == 3
        assert len(cycle.failed_phases) == 2
        assert cycle.overall_success is False

    def test_cycle_result_with_no_phases(self):
        """Should handle cycle with no phases."""
        cycle = CycleResult(cycle_number=1, started_at=datetime.now(), completed_at=datetime.now())

        assert len(cycle.phases) == 0
        assert len(cycle.succeeded_phases) == 0
        assert len(cycle.failed_phases) == 0

    def test_cycle_result_partial_data(self):
        """to_dict should include phase data if present."""
        phases = [
            PhaseResult("collect", True, data={"sources": 5, "items_collected": 1000}),
            PhaseResult("analyze", False, error="memory error"),
        ]

        cycle = CycleResult(
            cycle_number=1, started_at=datetime.now(), completed_at=datetime.now(), phases=phases
        )

        result_dict = cycle.to_dict()
        phase_dicts = result_dict["phases"]

        # Collect phase should have name, success, and error fields in dict
        assert phase_dicts[0]["name"] == "collect"
        assert phase_dicts[0]["success"] is True
        assert phase_dicts[0]["error"] is None

        # Analyze phase should show error
        assert phase_dicts[1]["name"] == "analyze"
        assert phase_dicts[1]["success"] is False
        assert phase_dicts[1]["error"] == "memory error"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestCycleResultIntegration:
    """Integration tests for CycleResult usage patterns."""

    def test_building_cycle_result_incrementally(self):
        """Should be able to build cycle result incrementally."""
        cycle = CycleResult(cycle_number=1, started_at=datetime.now(), completed_at=datetime.now())

        # Add phases one by one
        cycle.phases.append(PhaseResult("phase1", True))
        cycle.phases.append(PhaseResult("phase2", False, error="err"))
        cycle.phases.append(PhaseResult("phase3", True))

        assert len(cycle.phases) == 3
        assert len(cycle.failed_phases) == 1
        assert cycle.failed_phases[0] == "phase2"

    def test_cycle_result_serialization_deserialization(self):
        """Should support JSON serialization via to_dict."""
        import json

        now = datetime.now()
        phases = [
            PhaseResult("collect", True, duration_seconds=1.5),
            PhaseResult("analyze", False, error="Error", duration_seconds=2.0),
        ]

        cycle = CycleResult(
            cycle_number=42,
            started_at=now,
            completed_at=now + timedelta(seconds=3.5),
            phases=phases,
            overall_success=False,
        )

        # Convert to dict and serialize
        dict_repr = cycle.to_dict()
        json_str = json.dumps(dict_repr)

        # Should not raise
        assert len(json_str) > 0

        # Deserialize back
        loaded = json.loads(json_str)
        assert loaded["cycle_number"] == 42
        assert len(loaded["phases"]) == 2
        assert loaded["overall_success"] is False
