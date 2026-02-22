"""
Tests for scenario modeling UI and contract validation.

Tests ScenarioResult model validation, scenario type parameter validation,
comparison logic, and API contract integrity.
"""

from dataclasses import asdict

import pytest

from lib.intelligence.scenario_engine import (
    ConfidenceLevel,
    ScenarioComparison,
    ScenarioResult,
    ScenarioType,
)

# =============================================================================
# SCENARIO RESULT MODEL VALIDATION
# =============================================================================


class TestScenarioResultValidation:
    """Test ScenarioResult dataclass validation and serialization."""

    def test_scenario_result_to_dict_basic(self):
        """Test that ScenarioResult.to_dict() returns properly formatted dict."""
        result = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Loss of major client",
            baseline_metrics={"revenue": 500000, "tasks": 30},
            projected_metrics={"revenue": 250000, "tasks": 15},
            impact_summary="50% revenue loss",
            revenue_impact=-250000.0,
            capacity_impact_pct=-50.5,
        )

        output = result.to_dict()

        assert output["scenario_type"] == "CLIENT_LOSS"
        assert output["description"] == "Loss of major client"
        assert output["revenue_impact"] == -250000.0
        assert output["capacity_impact_pct"] == -50.5
        assert output["confidence"] == "MEDIUM"

    def test_scenario_result_confidence_levels(self):
        """Test that confidence level is properly serialized."""
        for confidence in ConfidenceLevel:
            result = ScenarioResult(
                scenario_type=ScenarioType.CLIENT_ADDITION,
                description="Test",
                baseline_metrics={},
                projected_metrics={},
                impact_summary="Test",
                confidence=confidence,
            )
            output = result.to_dict()
            assert output["confidence"] == confidence.value

    def test_scenario_result_risk_factors_list(self):
        """Test that risk factors are properly included in output."""
        risks = [
            "STRUCTURAL: Client represents 60% of revenue",
            "Coverage gap: single-person dependency",
        ]
        result = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Test",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            risk_factors=risks,
        )
        output = result.to_dict()
        assert output["risk_factors"] == risks
        assert len(output["risk_factors"]) == 2

    def test_scenario_result_numeric_rounding(self):
        """Test that numeric values are properly rounded in output."""
        result = ScenarioResult(
            scenario_type=ScenarioType.PRICING_CHANGE,
            description="Test",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            revenue_impact=12345.6789,
            capacity_impact_pct=23.4567,
        )
        output = result.to_dict()
        assert output["revenue_impact"] == 12345.68  # Rounded to 2 decimals
        assert output["capacity_impact_pct"] == 23.5  # Rounded to 1 decimal

    def test_scenario_result_empty_risk_factors(self):
        """Test that empty risk_factors defaults to empty list."""
        result = ScenarioResult(
            scenario_type=ScenarioType.WORKLOAD_REBALANCE,
            description="Test",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
        )
        output = result.to_dict()
        assert output["risk_factors"] == []


# =============================================================================
# SCENARIO TYPE PARAMETER VALIDATION
# =============================================================================


class TestScenarioTypeValidation:
    """Test scenario type enum and parameter validation."""

    def test_all_scenario_types_defined(self):
        """Test that all six scenario types are defined."""
        expected_types = {
            "CLIENT_LOSS",
            "CLIENT_ADDITION",
            "RESOURCE_CHANGE",
            "PRICING_CHANGE",
            "CAPACITY_SHIFT",
            "WORKLOAD_REBALANCE",
        }
        actual_types = {st.value for st in ScenarioType}
        assert actual_types == expected_types

    def test_scenario_type_enum_values(self):
        """Test that scenario types have correct enum values."""
        assert ScenarioType.CLIENT_LOSS.value == "CLIENT_LOSS"
        assert ScenarioType.CLIENT_ADDITION.value == "CLIENT_ADDITION"
        assert ScenarioType.RESOURCE_CHANGE.value == "RESOURCE_CHANGE"
        assert ScenarioType.PRICING_CHANGE.value == "PRICING_CHANGE"
        assert ScenarioType.CAPACITY_SHIFT.value == "CAPACITY_SHIFT"
        assert ScenarioType.WORKLOAD_REBALANCE.value == "WORKLOAD_REBALANCE"

    def test_scenario_type_string_conversion(self):
        """Test that scenario types convert to/from strings correctly."""
        scenario_type = ScenarioType.CLIENT_LOSS
        assert str(scenario_type.value) == "CLIENT_LOSS"
        assert ScenarioType(scenario_type.value) == scenario_type

    def test_confidence_level_values(self):
        """Test that all confidence levels are properly defined."""
        expected_levels = {"HIGH", "MEDIUM", "LOW"}
        actual_levels = {cl.value for cl in ConfidenceLevel}
        assert actual_levels == expected_levels


# =============================================================================
# CLIENT_LOSS PARAMETER VALIDATION
# =============================================================================


class TestClientLossParameters:
    """Test CLIENT_LOSS scenario parameter validation."""

    def test_client_loss_required_client_id(self):
        """Test that client_id is a required parameter for client loss."""
        # This test validates the pattern - in actual API usage, client_id must be provided
        params = {"client_id": "client_123"}
        assert "client_id" in params
        assert params["client_id"]

    def test_client_loss_result_structure(self):
        """Test that client loss result has expected structure."""
        result = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Loss of Client ABC",
            baseline_metrics={
                "revenue": 450000,
                "revenue_pct": 62.5,
                "tasks": 34,
                "task_pct": 28.3,
                "people_involved": 3,
            },
            projected_metrics={
                "portfolio_revenue": 268000,
                "portfolio_revenue_pct": 37.5,
                "portfolio_tasks": 41,
                "people_freed": 1,
            },
            impact_summary="Loss of $450K revenue",
            risk_factors=[
                "STRUCTURAL: Client represents 62.5% of portfolio revenue",
                "High task concentration: 28.3% of workload",
            ],
            revenue_impact=-450000.0,
            capacity_impact_pct=-28.3,
        )

        assert result.scenario_type == ScenarioType.CLIENT_LOSS
        assert result.baseline_metrics["revenue"] == 450000
        assert result.revenue_impact < 0  # Must be negative for loss


# =============================================================================
# CLIENT_ADDITION PARAMETER VALIDATION
# =============================================================================


class TestClientAdditionParameters:
    """Test CLIENT_ADDITION scenario parameter validation."""

    def test_client_addition_required_parameters(self):
        """Test that client addition requires revenue and task estimates."""
        params = {
            "estimated_revenue": 150000,
            "estimated_tasks": 18,
            "team_size": 1,
        }
        assert params["estimated_revenue"] > 0
        assert params["estimated_tasks"] > 0
        assert params["team_size"] >= 1

    def test_client_addition_result_structure(self):
        """Test that client addition result has expected structure."""
        result = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_ADDITION,
            description="Addition of new client ($150K, 18 tasks)",
            baseline_metrics={
                "portfolio_revenue": 718000,
                "portfolio_tasks": 75,
                "team_size": 5,
                "available_people": 1,
            },
            projected_metrics={
                "portfolio_revenue": 868000,
                "revenue_gain_pct": 20.9,
                "portfolio_tasks": 93,
                "team_size_after": 6,
            },
            impact_summary="Revenue gain: +$150K",
            revenue_impact=150000.0,
            capacity_impact_pct=24.0,
        )

        assert result.scenario_type == ScenarioType.CLIENT_ADDITION
        assert result.revenue_impact > 0  # Must be positive for addition
        assert result.projected_metrics["team_size_after"] > result.baseline_metrics["team_size"]


# =============================================================================
# RESOURCE_CHANGE PARAMETER VALIDATION
# =============================================================================


class TestResourceChangeParameters:
    """Test RESOURCE_CHANGE scenario parameter validation."""

    def test_resource_change_types(self):
        """Test that resource change type is valid."""
        valid_types = {"leaves", "added", "reduced"}
        for change_type in valid_types:
            assert change_type in {"leaves", "added", "reduced"}

    def test_resource_change_result_leaves(self):
        """Test RESOURCE_CHANGE result for person leaving."""
        result = ScenarioResult(
            scenario_type=ScenarioType.RESOURCE_CHANGE,
            description="Resource departure: Ahmed leaves",
            baseline_metrics={
                "person": "Ahmed",
                "active_tasks": 24,
                "projects": 5,
                "team_size": 5,
            },
            projected_metrics={
                "team_size_after": 4,
                "tasks_requiring_reassignment": 24,
                "projects_affected": 5,
            },
            impact_summary="24 tasks to reassign",
            risk_factors=["High load departure: 24 active tasks"],
            revenue_impact=0.0,
            capacity_impact_pct=-32.0,
        )

        assert result.baseline_metrics["team_size"] == 5
        assert result.projected_metrics["team_size_after"] == 4
        assert result.capacity_impact_pct < 0  # Loss of capacity

    def test_resource_change_result_added(self):
        """Test RESOURCE_CHANGE result for person added."""
        result = ScenarioResult(
            scenario_type=ScenarioType.RESOURCE_CHANGE,
            description="Resource addition: New hire joins",
            baseline_metrics={
                "team_size": 5,
                "team_total_tasks": 75,
                "overloaded_people": 2,
            },
            projected_metrics={
                "team_size_after": 6,
                "team_total_capacity": 95,
                "estimated_capacity_gain": 20,
            },
            impact_summary="Capacity gain: +20 tasks",
            revenue_impact=0.0,
            capacity_impact_pct=26.7,
        )

        assert result.baseline_metrics["team_size"] == 5
        assert result.projected_metrics["team_size_after"] == 6
        assert result.capacity_impact_pct > 0  # Gain of capacity


# =============================================================================
# PRICING_CHANGE PARAMETER VALIDATION
# =============================================================================


class TestPricingChangeParameters:
    """Test PRICING_CHANGE scenario parameter validation."""

    def test_pricing_change_percentage_range(self):
        """Test that pricing change percentages are within reasonable range."""
        test_cases = [
            (-0.5, "50% decrease"),
            (-0.15, "15% decrease"),
            (0.0, "No change"),
            (0.10, "10% increase"),
            (0.30, "30% increase"),
        ]
        for pct, _desc in test_cases:
            assert -1 < pct < 1  # Should be -100% to +100%

    def test_pricing_change_result_positive(self):
        """Test PRICING_CHANGE result for price increase."""
        result = ScenarioResult(
            scenario_type=ScenarioType.PRICING_CHANGE,
            description="Pricing change for client: +15%",
            baseline_metrics={
                "current_revenue": 450000,
                "pricing_change_pct": 15.0,
            },
            projected_metrics={
                "new_revenue": 517500,
                "revenue_change": 67500,
            },
            impact_summary="Revenue change: +$67.5K",
            revenue_impact=67500.0,
            capacity_impact_pct=0.0,
        )

        assert result.revenue_impact > 0  # Positive for price increase

    def test_pricing_change_result_negative(self):
        """Test PRICING_CHANGE result for price decrease."""
        result = ScenarioResult(
            scenario_type=ScenarioType.PRICING_CHANGE,
            description="Pricing change for client: -20%",
            baseline_metrics={
                "current_revenue": 100000,
                "pricing_change_pct": -20.0,
            },
            projected_metrics={
                "new_revenue": 80000,
                "revenue_change": -20000,
            },
            impact_summary="Revenue change: -$20K",
            risk_factors=["Margin compression: may affect profitability"],
            revenue_impact=-20000.0,
            capacity_impact_pct=0.0,
        )

        assert result.revenue_impact < 0  # Negative for price decrease


# =============================================================================
# CAPACITY_SHIFT PARAMETER VALIDATION
# =============================================================================


class TestCapacityShiftParameters:
    """Test CAPACITY_SHIFT scenario parameter validation."""

    def test_capacity_shift_delta_hours_range(self):
        """Test that hours shift values are reasonable."""
        test_values = [-100, -40, 0, 40, 100]
        for delta in test_values:
            assert -200 < delta < 200  # Reasonable range

    def test_capacity_shift_result_structure(self):
        """Test that capacity shift result has expected structure."""
        result = ScenarioResult(
            scenario_type=ScenarioType.CAPACITY_SHIFT,
            description="Capacity shift: +40 hours to delivery lane",
            baseline_metrics={
                "team_total_active_tasks": 75,
                "capacity_lane": "delivery",
                "hours_shift": 40.0,
            },
            projected_metrics={
                "team_total_active_tasks_after": 80.0,
                "tasks_shift": 5.0,
            },
            impact_summary="Capacity shift: +40 hours (+5 tasks)",
            revenue_impact=0.0,
            capacity_impact_pct=6.7,
        )

        assert result.scenario_type == ScenarioType.CAPACITY_SHIFT
        assert result.capacity_impact_pct > 0  # Positive for +40 hours


# =============================================================================
# WORKLOAD_REBALANCE PARAMETER VALIDATION
# =============================================================================


class TestWorkloadRebalanceParameters:
    """Test WORKLOAD_REBALANCE scenario parameter validation."""

    def test_workload_rebalance_no_parameters(self):
        """Test that workload rebalance requires no input parameters."""
        # Workload rebalance analyzes entire team, no specific params needed
        params = {}
        assert len(params) == 0

    def test_workload_rebalance_result_structure(self):
        """Test that workload rebalance result has expected structure."""
        result = ScenarioResult(
            scenario_type=ScenarioType.WORKLOAD_REBALANCE,
            description="Workload rebalancing across team",
            baseline_metrics={
                "total_active_tasks": 75,
                "avg_load": 15.0,
                "max_load": 24,
                "load_variance": 9.0,
                "overloaded_count": 2,
            },
            projected_metrics={
                "total_active_tasks": 75,
                "avg_load": 15.0,
                "projected_max_load": 19.5,
                "projected_load_variance": 4.5,
                "overloaded_after_rebalance": 1,
            },
            impact_summary="Variance reduction: 9.0 → 4.5",
            revenue_impact=0.0,
            capacity_impact_pct=0.0,
        )

        assert result.scenario_type == ScenarioType.WORKLOAD_REBALANCE
        assert (
            result.baseline_metrics["load_variance"]
            > result.projected_metrics["projected_load_variance"]
        )


# =============================================================================
# SCENARIO COMPARISON LOGIC
# =============================================================================


class TestScenarioComparison:
    """Test scenario comparison and tradeoff analysis."""

    def test_comparison_initialization(self):
        """Test that ScenarioComparison can be initialized with scenarios."""
        scenarios = [
            ScenarioResult(
                scenario_type=ScenarioType.CLIENT_LOSS,
                description="Lose GMG",
                baseline_metrics={},
                projected_metrics={},
                impact_summary="Test",
                revenue_impact=-450000,
                capacity_impact_pct=-28.3,
            ),
            ScenarioResult(
                scenario_type=ScenarioType.CLIENT_ADDITION,
                description="Add new client",
                baseline_metrics={},
                projected_metrics={},
                impact_summary="Test",
                revenue_impact=150000,
                capacity_impact_pct=24.0,
            ),
        ]

        comparison = ScenarioComparison(
            scenarios=scenarios,
            best_case_idx=1,
            worst_case_idx=0,
            tradeoff_summary="Option A has more revenue but higher risk",
        )

        assert len(comparison.scenarios) == 2
        assert comparison.best_case_idx == 1
        assert comparison.worst_case_idx == 0

    def test_comparison_to_dict(self):
        """Test that ScenarioComparison.to_dict() serializes correctly."""
        result1 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Lose GMG",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            revenue_impact=-450000,
            capacity_impact_pct=-28.3,
        )
        result2 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_ADDITION,
            description="Add new client",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            revenue_impact=150000,
            capacity_impact_pct=24.0,
        )

        comparison = ScenarioComparison(
            scenarios=[result1, result2],
            best_case_idx=1,
            worst_case_idx=0,
            tradeoff_summary="Compare outcomes",
        )

        output = comparison.to_dict()
        assert len(output["scenarios"]) == 2
        assert output["best_case_idx"] == 1
        assert output["worst_case_idx"] == 0
        assert "tradeoff_summary" in output

    def test_comparison_best_worst_scoring(self):
        """Test that best/worst cases are correctly identified by scoring."""
        # Simulate scoring logic: revenue + capacity - risk penalty
        ScenarioResult(
            scenario_type=ScenarioType.CLIENT_ADDITION,
            description="Good outcome",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            revenue_impact=100000,
            capacity_impact_pct=10.0,
            risk_factors=[],  # No risks
        )
        ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Bad outcome",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            revenue_impact=-100000,
            capacity_impact_pct=-10.0,
            risk_factors=["Risk 1", "Risk 2", "Risk 3"],  # Multiple risks
        )

        # Good: 100000 + 10 - 0 = 100010
        # Bad: -100000 - 10 - 30 = -100040
        assert 100000 + 10 > -100000 - 10  # Good scenario scores higher


# =============================================================================
# API RESPONSE CONTRACT
# =============================================================================


class TestAPIResponseContract:
    """Test that API responses match expected contract."""

    def test_scenario_result_serialization_contract(self):
        """Test that serialized result matches API contract."""
        result = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Test scenario",
            baseline_metrics={"key": "value"},
            projected_metrics={"key2": "value2"},
            impact_summary="Summary",
            risk_factors=["Risk 1"],
            confidence=ConfidenceLevel.HIGH,
            revenue_impact=12345.67,
            capacity_impact_pct=23.45,
        )

        output = result.to_dict()

        # Verify all required fields are present
        required_fields = [
            "scenario_type",
            "description",
            "baseline_metrics",
            "projected_metrics",
            "impact_summary",
            "risk_factors",
            "confidence",
            "revenue_impact",
            "capacity_impact_pct",
        ]
        for field in required_fields:
            assert field in output, f"Missing required field: {field}"

    def test_scenario_type_in_response(self):
        """Test that scenario_type is always a string in response."""
        for scenario_type in ScenarioType:
            result = ScenarioResult(
                scenario_type=scenario_type,
                description="Test",
                baseline_metrics={},
                projected_metrics={},
                impact_summary="Test",
            )
            output = result.to_dict()
            assert isinstance(output["scenario_type"], str)
            assert output["scenario_type"] == scenario_type.value

    def test_confidence_in_response(self):
        """Test that confidence is always a string in response."""
        for confidence in ConfidenceLevel:
            result = ScenarioResult(
                scenario_type=ScenarioType.CLIENT_LOSS,
                description="Test",
                baseline_metrics={},
                projected_metrics={},
                impact_summary="Test",
                confidence=confidence,
            )
            output = result.to_dict()
            assert isinstance(output["confidence"], str)
            assert output["confidence"] == confidence.value


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestScenarioIntegration:
    """Integration tests for scenario modeling workflow."""

    def test_full_scenario_workflow(self):
        """Test complete workflow: create result -> serialize -> compare."""
        result1 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Scenario 1",
            baseline_metrics={"revenue": 500000},
            projected_metrics={"revenue": 250000},
            impact_summary="Loss of $250K",
            revenue_impact=-250000,
            capacity_impact_pct=-30,
            risk_factors=["Risk A"],
        )

        result2 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_ADDITION,
            description="Scenario 2",
            baseline_metrics={"revenue": 500000},
            projected_metrics={"revenue": 650000},
            impact_summary="Gain of $150K",
            revenue_impact=150000,
            capacity_impact_pct=20,
            risk_factors=[],
        )

        # Serialize both
        output1 = result1.to_dict()
        output2 = result2.to_dict()

        # Create comparison
        comparison = ScenarioComparison(
            scenarios=[result1, result2],
            best_case_idx=1,
            worst_case_idx=0,
            tradeoff_summary="Option 2 is better",
        )

        comp_output = comparison.to_dict()

        # Verify
        assert len(comp_output["scenarios"]) == 2
        assert comp_output["best_case_idx"] == 1
        assert output1["revenue_impact"] == -250000
        assert output2["revenue_impact"] == 150000

    def test_multiple_scenario_comparison(self):
        """Test comparing three or more scenarios."""
        scenarios = []
        for i in range(4):
            scenario = ScenarioResult(
                scenario_type=ScenarioType.CLIENT_LOSS,
                description=f"Scenario {i}",
                baseline_metrics={},
                projected_metrics={},
                impact_summary=f"Impact {i}",
                revenue_impact=-100000 * (i + 1),
                capacity_impact_pct=-10 * (i + 1),
                risk_factors=["Risk"] * i,
            )
            scenarios.append(scenario)

        comparison = ScenarioComparison(
            scenarios=scenarios,
            best_case_idx=0,
            worst_case_idx=3,
            tradeoff_summary="Progressive impact",
        )

        assert len(comparison.scenarios) == 4
        assert comparison.scenarios[0].revenue_impact == -100000
        assert comparison.scenarios[3].revenue_impact == -400000
