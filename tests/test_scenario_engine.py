"""
Tests for Scenario Modeling Engine

Covers:
- ScenarioEngine initialization
- All scenario types with various data conditions
- model_client_loss with high-revenue vs low-revenue clients
- model_client_addition with capacity surplus vs deficit
- model_resource_change all three types (leaves, added, reduced)
- model_pricing_change with price increases and decreases
- model_capacity_shift and model_workload_rebalance
- compare_scenarios with multiple scenarios
- Edge cases (no data, client not found, missing person)
- to_dict() serialization for all result types

Uses mocked query_engine and cost_engine to avoid live DB dependency.
Target: 25+ tests
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.intelligence.scenario_engine import (
    ConfidenceLevel,
    ScenarioComparison,
    ScenarioEngine,
    ScenarioResult,
    ScenarioType,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_query_engine():
    """Create a mock QueryEngine."""
    engine = MagicMock()
    return engine


@pytest.fixture
def mock_cost_engine():
    """Create a mock CostToServeEngine."""
    engine = MagicMock()
    return engine


@pytest.fixture
def scenario_engine(mock_query_engine, mock_cost_engine):
    """Create a ScenarioEngine with mocked dependencies."""
    with patch("lib.intelligence.scenario_engine.get_engine", return_value=mock_query_engine):
        with patch(
            "lib.intelligence.scenario_engine.CostToServeEngine", return_value=mock_cost_engine
        ):
            return ScenarioEngine()


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestScenarioEngineInit:
    """Test ScenarioEngine initialization."""

    def test_init_creates_engine(self, mock_query_engine, mock_cost_engine):
        """Engine initializes with get_engine and CostToServeEngine."""
        with patch("lib.intelligence.scenario_engine.get_engine", return_value=mock_query_engine):
            with patch(
                "lib.intelligence.scenario_engine.CostToServeEngine", return_value=mock_cost_engine
            ):
                engine = ScenarioEngine()
                assert engine.query_engine is not None
                assert engine.cost_engine is not None

    def test_init_with_explicit_db_path(self, mock_query_engine, mock_cost_engine):
        """Engine accepts optional db_path parameter."""
        db_path = Path("/tmp/test.db")
        with patch(
            "lib.intelligence.scenario_engine.get_engine", return_value=mock_query_engine
        ) as mock_get:
            with patch(
                "lib.intelligence.scenario_engine.CostToServeEngine", return_value=mock_cost_engine
            ) as mock_cost_get:
                ScenarioEngine(db_path)
                mock_get.assert_called_once_with(db_path)
                mock_cost_get.assert_called_once_with(db_path)

    def test_init_handles_file_not_found(self):
        """Engine raises FileNotFoundError if DB not found."""
        with patch(
            "lib.intelligence.scenario_engine.get_engine",
            side_effect=FileNotFoundError("DB not found"),
        ):
            with pytest.raises(FileNotFoundError):
                ScenarioEngine()


# =============================================================================
# CLIENT_LOSS SCENARIO TESTS
# =============================================================================


class TestModelClientLoss:
    """Test model_client_loss method."""

    def test_client_loss_high_revenue_client(self, scenario_engine, mock_query_engine):
        """Loss of high-revenue client is flagged as structural."""
        # High-revenue client (30% of portfolio)
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Major Client",
            "total_invoiced": 300000.0,
            "total_outstanding": 10000.0,
            "total_tasks": 200,
            "projects": [{"project_id": "p1", "project_name": "Project 1"}],
            "people_involved": [
                {"person_id": "p-1", "person_name": "Alice", "tasks_for_client": 50},
                {"person_id": "p-2", "person_name": "Bob", "tasks_for_client": 30},
            ],
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 300000.0, "total_tasks": 200},
            {"client_id": "cli-002", "total_invoiced": 400000.0, "total_tasks": 300},
            {"client_id": "cli-003", "total_invoiced": 300000.0, "total_tasks": 200},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [
                {"person_name": "Alice", "active_tasks": 50},
                {"person_name": "Bob", "active_tasks": 30},
                {"person_name": "Charlie", "active_tasks": 20},
            ],
            "total_people": 3,
            "total_active_tasks": 100,
        }

        result = scenario_engine.model_client_loss("cli-001")

        assert result is not None
        assert result.scenario_type == ScenarioType.CLIENT_LOSS
        assert result.baseline_metrics["revenue"] == 300000.0
        assert result.baseline_metrics["revenue_pct"] > 25  # Should be ~37.5%
        assert result.revenue_impact == -300000.0
        assert any("STRUCTURAL" in risk for risk in result.risk_factors)
        assert result.confidence == ConfidenceLevel.HIGH

    def test_client_loss_low_revenue_client(self, scenario_engine, mock_query_engine):
        """Loss of low-revenue client has lower risk profile."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-002",
            "client_name": "Small Client",
            "total_invoiced": 50000.0,
            "total_outstanding": 0,
            "total_tasks": 30,
            "projects": [{"project_id": "p1", "project_name": "Project 1"}],
            "people_involved": [
                {"person_id": "p-1", "person_name": "Alice", "tasks_for_client": 10},
            ],
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 500000.0, "total_tasks": 400},
            {"client_id": "cli-002", "total_invoiced": 50000.0, "total_tasks": 30},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [
                {"person_name": "Alice", "active_tasks": 50},
            ],
            "total_people": 1,
            "total_active_tasks": 50,
        }

        result = scenario_engine.model_client_loss("cli-002")

        assert result is not None
        assert result.baseline_metrics["revenue_pct"] < 15  # ~8.3%
        assert not any("STRUCTURAL" in risk for risk in result.risk_factors)

    def test_client_loss_missing_client_returns_none(self, scenario_engine, mock_query_engine):
        """Missing client returns None."""
        mock_query_engine.client_deep_profile.return_value = None

        result = scenario_engine.model_client_loss("cli-nonexistent")

        assert result is None

    def test_client_loss_handles_no_portfolio_data(self, scenario_engine, mock_query_engine):
        """Handles case when portfolio overview is unavailable."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test Client",
            "total_invoiced": 100000.0,
            "total_tasks": 50,
        }
        mock_query_engine.client_portfolio_overview.return_value = None

        result = scenario_engine.model_client_loss("cli-001")

        assert result is None

    def test_client_loss_to_dict_serialization(self, scenario_engine, mock_query_engine):
        """ScenarioResult.to_dict() serializes correctly."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test Client",
            "total_invoiced": 100000.0,
            "total_outstanding": 5000.0,
            "total_tasks": 50,
            "projects": [{"project_id": "p1"}],
            "people_involved": [
                {"person_id": "p-1", "person_name": "Alice", "tasks_for_client": 10}
            ],
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 100000.0, "total_tasks": 50},
            {"client_id": "cli-002", "total_invoiced": 400000.0, "total_tasks": 300},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [{"person_name": "Alice", "active_tasks": 50}],
            "total_people": 1,
            "total_active_tasks": 50,
        }

        result = scenario_engine.model_client_loss("cli-001")
        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["scenario_type"] == "CLIENT_LOSS"
        assert "baseline_metrics" in data
        assert "projected_metrics" in data
        assert data["revenue_impact"] == -100000.0

    def test_client_loss_exception_handling(self, scenario_engine, mock_query_engine):
        """Exceptions are logged and None returned."""
        mock_query_engine.client_deep_profile.side_effect = Exception("DB error")

        result = scenario_engine.model_client_loss("cli-001")

        assert result is None


# =============================================================================
# CLIENT_ADDITION SCENARIO TESTS
# =============================================================================


class TestModelClientAddition:
    """Test model_client_addition method."""

    def test_client_addition_with_capacity_surplus(self, scenario_engine, mock_query_engine):
        """Adding client with surplus capacity has low risk."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 500000.0, "total_tasks": 200},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [
                {"person_name": "Alice", "active_tasks": 10},
                {"person_name": "Bob", "active_tasks": 15},
            ],
            "total_people": 2,
            "total_active_tasks": 25,
            "people_available": 2,
            "people_overloaded": 0,
        }

        result = scenario_engine.model_client_addition(
            estimated_revenue=100000.0, estimated_tasks=30, team_size=1
        )

        assert result is not None
        assert result.scenario_type == ScenarioType.CLIENT_ADDITION
        assert result.revenue_impact == 100000.0
        assert result.projected_metrics["hiring_needed"] == 0
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_client_addition_with_capacity_deficit(self, scenario_engine, mock_query_engine):
        """Adding client without available capacity flags hiring need."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 500000.0, "total_tasks": 200},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [
                {"person_name": "Alice", "active_tasks": 50},
                {"person_name": "Bob", "active_tasks": 45},
            ],
            "total_people": 2,
            "total_active_tasks": 95,
            "people_available": 0,
            "people_overloaded": 2,
        }

        result = scenario_engine.model_client_addition(
            estimated_revenue=150000.0, estimated_tasks=50, team_size=2
        )

        assert result is not None
        assert result.projected_metrics["hiring_needed"] == 2
        assert any("Capacity deficit" in risk for risk in result.risk_factors)

    def test_client_addition_large_task_volume(self, scenario_engine, mock_query_engine):
        """Large task volume relative to team size is flagged."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 100000.0, "total_tasks": 50},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [
                {"person_name": "Alice", "active_tasks": 25},
            ],
            "total_people": 1,
            "total_active_tasks": 25,
            "people_available": 1,
            "people_overloaded": 0,
        }

        result = scenario_engine.model_client_addition(
            estimated_revenue=50000.0,
            estimated_tasks=100,  # Very high task volume
            team_size=1,
        )

        assert result is not None
        assert any("High task volume" in risk for risk in result.risk_factors)

    def test_client_addition_no_portfolio_data(self, scenario_engine, mock_query_engine):
        """Handles missing portfolio data."""
        mock_query_engine.client_portfolio_overview.return_value = None
        mock_query_engine.team_capacity_overview.return_value = {
            "total_people": 1,
            "total_active_tasks": 20,
            "people_available": 1,
            "people_overloaded": 0,
        }

        result = scenario_engine.model_client_addition(100000.0, 30)

        assert result is None

    def test_client_addition_no_team_capacity(self, scenario_engine, mock_query_engine):
        """Handles missing team capacity data."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 500000.0, "total_tasks": 200},
        ]
        mock_query_engine.team_capacity_overview.return_value = None

        result = scenario_engine.model_client_addition(100000.0, 30)

        assert result is None

    def test_client_addition_to_dict(self, scenario_engine, mock_query_engine):
        """ScenarioResult.to_dict() works for client addition."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 500000.0, "total_tasks": 200},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [{"person_name": "Alice", "active_tasks": 20}],
            "total_people": 1,
            "total_active_tasks": 20,
            "people_available": 1,
            "people_overloaded": 0,
        }

        result = scenario_engine.model_client_addition(100000.0, 30)
        data = result.to_dict()

        assert data["scenario_type"] == "CLIENT_ADDITION"
        assert data["revenue_impact"] == 100000.0


# =============================================================================
# RESOURCE_CHANGE SCENARIO TESTS
# =============================================================================


class TestModelResourceChange:
    """Test model_resource_change method."""

    def test_resource_leaves_high_load(self, scenario_engine, mock_query_engine):
        """Person leaving with high load has high risk."""
        mock_query_engine.resource_load_distribution.return_value = [
            {"person_id": "p-1", "person_name": "Alice", "active_tasks": 40},
            {"person_id": "p-2", "person_name": "Bob", "active_tasks": 20},
        ]

        mock_query_engine.person_operational_profile.return_value = {
            "person_id": "p-1",
            "person_name": "Alice",
            "active_tasks": 40,
            "projects": [
                {"project_id": "proj-1", "project_name": "Project 1"},
                {"project_id": "proj-2", "project_name": "Project 2"},
                {"project_id": "proj-3", "project_name": "Project 3"},
            ],
            "clients": [
                {"client_id": "cli-1", "client_name": "Client 1"},
                {"client_id": "cli-2", "client_name": "Client 2"},
            ],
        }

        mock_query_engine.team_capacity_overview.return_value = {
            "total_people": 2,
            "total_active_tasks": 60,
            "people_overloaded": 1,
            "people_available": 0,
        }

        result = scenario_engine.model_resource_change("Alice", "leaves")

        assert result is not None
        assert result.scenario_type == ScenarioType.RESOURCE_CHANGE
        assert result.baseline_metrics["active_tasks"] == 40
        assert result.projected_metrics["team_size_after"] == 1
        assert any("High load departure" in risk for risk in result.risk_factors)
        assert result.confidence == ConfidenceLevel.HIGH

    def test_resource_added_capacity_gain(self, scenario_engine, mock_query_engine):
        """Adding resource shows capacity gain."""
        mock_query_engine.resource_load_distribution.return_value = [
            {"person_id": "p-1", "person_name": "Alice", "active_tasks": 20},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "total_people": 1,
            "total_active_tasks": 20,
            "people_available": 0,
            "people_overloaded": 1,
        }

        result = scenario_engine.model_resource_change("Charlie", "added")

        assert result is not None
        assert result.scenario_type == ScenarioType.RESOURCE_CHANGE
        assert result.projected_metrics["team_size_after"] == 2
        assert result.projected_metrics["estimated_capacity_gain"] == 20

    def test_resource_reduced_hours_impact(self, scenario_engine, mock_query_engine):
        """Reducing person's hours shows capacity loss."""
        mock_query_engine.resource_load_distribution.return_value = [
            {"person_id": "p-1", "person_name": "Alice", "active_tasks": 30},
        ]

        mock_query_engine.person_operational_profile.return_value = {
            "person_id": "p-1",
            "person_name": "Alice",
            "active_tasks": 30,
            "projects": [
                {"project_id": "proj-1", "project_name": "Project 1"},
            ],
            "clients": [
                {"client_id": "cli-1", "client_name": "Client 1"},
            ],
        }

        mock_query_engine.team_capacity_overview.return_value = {
            "total_people": 1,
            "total_active_tasks": 30,
        }

        result = scenario_engine.model_resource_change("Alice", "reduced")

        assert result is not None
        assert "Capacity reduction" in result.impact_summary
        assert result.projected_metrics["tasks_freed"] > 0

    def test_resource_change_person_not_found(self, scenario_engine, mock_query_engine):
        """Missing person returns None."""
        mock_query_engine.resource_load_distribution.return_value = []

        result = scenario_engine.model_resource_change("Unknown", "leaves")

        assert result is None

    def test_resource_change_invalid_type(self, scenario_engine, mock_query_engine):
        """Invalid change_type returns None."""
        mock_query_engine.resource_load_distribution.return_value = [
            {"person_id": "p-1", "person_name": "Alice", "active_tasks": 20},
        ]

        result = scenario_engine.model_resource_change("Alice", "invalid")

        assert result is None

    def test_resource_leaves_to_dict(self, scenario_engine, mock_query_engine):
        """ScenarioResult.to_dict() works for resource leaves."""
        mock_query_engine.resource_load_distribution.return_value = [
            {"person_id": "p-1", "person_name": "Alice", "active_tasks": 30},
        ]

        mock_query_engine.person_operational_profile.return_value = {
            "person_id": "p-1",
            "person_name": "Alice",
            "active_tasks": 30,
            "projects": [{"project_id": "p1", "project_name": "P1"}],
            "clients": [{"client_id": "c1", "client_name": "C1"}],
        }

        mock_query_engine.team_capacity_overview.return_value = {
            "total_people": 2,
            "total_active_tasks": 60,
        }

        result = scenario_engine.model_resource_change("Alice", "leaves")
        data = result.to_dict()

        assert data["scenario_type"] == "RESOURCE_CHANGE"
        assert "baseline_metrics" in data


# =============================================================================
# PRICING_CHANGE SCENARIO TESTS
# =============================================================================


class TestModelPricingChange:
    """Test model_pricing_change method."""

    def test_pricing_increase_moderate(self, scenario_engine, mock_query_engine, mock_cost_engine):
        """Moderate price increase has reasonable risk."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test Client",
            "total_invoiced": 100000.0,
            "total_outstanding": 5000.0,
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 100000.0},
            {"client_id": "cli-002", "total_invoiced": 400000.0},
        ]

        mock_cost_engine.compute_client_cost.return_value = None

        result = scenario_engine.model_pricing_change("cli-001", 0.10)  # 10% increase

        assert result is not None
        assert result.scenario_type == ScenarioType.PRICING_CHANGE
        assert result.revenue_impact == 10000.0
        assert result.projected_metrics["new_revenue"] == 110000.0
        assert not any("Aggressive" in risk for risk in result.risk_factors)

    def test_pricing_increase_aggressive(
        self, scenario_engine, mock_query_engine, mock_cost_engine
    ):
        """Aggressive price increase is flagged as high risk."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test Client",
            "total_invoiced": 100000.0,
            "total_outstanding": 0,
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 100000.0},
        ]

        mock_cost_engine.compute_client_cost.return_value = None

        result = scenario_engine.model_pricing_change("cli-001", 0.30)  # 30% increase

        assert result is not None
        assert any("Aggressive" in risk for risk in result.risk_factors)
        assert any("churn" in risk.lower() for risk in result.risk_factors)

    def test_pricing_decrease_discount(self, scenario_engine, mock_query_engine, mock_cost_engine):
        """Price decrease shows margin compression risk."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test Client",
            "total_invoiced": 100000.0,
            "total_outstanding": 0,
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 100000.0},
        ]

        mock_cost_engine.compute_client_cost.return_value = None

        result = scenario_engine.model_pricing_change("cli-001", -0.20)  # 20% decrease

        assert result is not None
        assert result.revenue_impact == -20000.0
        assert any("discount" in risk.lower() for risk in result.risk_factors)

    def test_pricing_change_missing_client(self, scenario_engine, mock_query_engine):
        """Missing client returns None."""
        mock_query_engine.client_deep_profile.return_value = None

        result = scenario_engine.model_pricing_change("cli-nonexistent", 0.10)

        assert result is None

    def test_pricing_change_to_dict(self, scenario_engine, mock_query_engine, mock_cost_engine):
        """ScenarioResult.to_dict() works for pricing change."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test Client",
            "total_invoiced": 100000.0,
            "total_outstanding": 0,
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 100000.0},
        ]

        mock_cost_engine.compute_client_cost.return_value = None

        result = scenario_engine.model_pricing_change("cli-001", 0.15)
        data = result.to_dict()

        assert data["scenario_type"] == "PRICING_CHANGE"
        assert data["revenue_impact"] == 15000.0


# =============================================================================
# CAPACITY_SHIFT AND WORKLOAD_REBALANCE TESTS
# =============================================================================


class TestModelCapacityShift:
    """Test model_capacity_shift method."""

    def test_capacity_shift_increase(self, scenario_engine, mock_query_engine):
        """Capacity shift increase is projected correctly."""
        mock_query_engine.team_capacity_overview.return_value = {
            "total_active_tasks": 100,
            "total_weekly_hours": 200,
        }
        mock_query_engine.resource_load_distribution.return_value = []

        result = scenario_engine.model_capacity_shift("development", 40.0)

        assert result is not None
        assert result.scenario_type == ScenarioType.CAPACITY_SHIFT
        # 100 tasks / 200 hours = 0.5 tasks/hour; 40h * 0.5 = 20 tasks
        assert result.projected_metrics["tasks_shift"] == 20.0

    def test_capacity_shift_decrease(self, scenario_engine, mock_query_engine):
        """Capacity shift decrease is projected correctly."""
        mock_query_engine.team_capacity_overview.return_value = {
            "total_active_tasks": 100,
            "total_weekly_hours": 200,
        }
        mock_query_engine.resource_load_distribution.return_value = []

        result = scenario_engine.model_capacity_shift("operations", -32.0)

        assert result is not None
        # 100 tasks / 200 hours = 0.5 tasks/hour; -32h * 0.5 = -16 tasks
        assert result.projected_metrics["tasks_shift"] == -16.0


class TestModelWorkloadRebalance:
    """Test model_workload_rebalance method."""

    def test_workload_rebalance_reduces_variance(self, scenario_engine, mock_query_engine):
        """Workload rebalance shows variance reduction."""
        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [
                {"person_name": "Alice", "active_tasks": 50},
                {"person_name": "Bob", "active_tasks": 5},
                {"person_name": "Charlie", "active_tasks": 10},
            ],
            "total_people": 3,
            "total_active_tasks": 65,
            "avg_tasks_per_person": round(65 / 3, 1),
            "max_tasks_per_person": 50,
            "people_overloaded": 1,
            "people_available": 1,
        }

        result = scenario_engine.model_workload_rebalance()

        assert result is not None
        assert result.scenario_type == ScenarioType.WORKLOAD_REBALANCE
        assert result.projected_metrics["overloaded_after_rebalance"] == 0
        assert "Variance reduction" in result.impact_summary

    def test_workload_rebalance_no_data(self, scenario_engine, mock_query_engine):
        """Handles missing team capacity data."""
        mock_query_engine.team_capacity_overview.return_value = None

        result = scenario_engine.model_workload_rebalance()

        assert result is None

    def test_workload_rebalance_empty_distribution(self, scenario_engine, mock_query_engine):
        """Handles empty distribution."""
        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [],
            "total_people": 0,
        }

        result = scenario_engine.model_workload_rebalance()

        assert result is None


# =============================================================================
# SCENARIO_COMPARISON TESTS
# =============================================================================


class TestCompareScenarios:
    """Test compare_scenarios method."""

    def test_compare_multiple_scenarios(self, scenario_engine):
        """Comparison identifies best and worst scenarios."""
        scenario1 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Lose Client A",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Revenue loss",
            risk_factors=["Risk 1"],
            confidence=ConfidenceLevel.HIGH,
            revenue_impact=-100000.0,
            capacity_impact_pct=-20.0,
        )

        scenario2 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_ADDITION,
            description="Add Client B",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Revenue gain",
            risk_factors=[],
            confidence=ConfidenceLevel.MEDIUM,
            revenue_impact=150000.0,
            capacity_impact_pct=25.0,
        )

        scenario3 = ScenarioResult(
            scenario_type=ScenarioType.PRICING_CHANGE,
            description="Price increase",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Moderate revenue gain",
            risk_factors=["Risk 1", "Risk 2", "Risk 3"],
            confidence=ConfidenceLevel.HIGH,
            revenue_impact=50000.0,
            capacity_impact_pct=0.0,
        )

        result = scenario_engine.compare_scenarios([scenario1, scenario2, scenario3])

        assert result is not None
        assert isinstance(result, ScenarioComparison)
        assert result.best_case_idx == 1  # scenario2 has best score
        assert result.worst_case_idx == 0  # scenario1 has worst score
        assert len(result.scenarios) == 3

    def test_compare_scenarios_single_scenario(self, scenario_engine):
        """Single scenario returns None."""
        scenario = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Test",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            confidence=ConfidenceLevel.MEDIUM,
        )

        result = scenario_engine.compare_scenarios([scenario])

        assert result is None

    def test_compare_scenarios_empty_list(self, scenario_engine):
        """Empty scenario list returns None."""
        result = scenario_engine.compare_scenarios([])

        assert result is None

    def test_compare_scenarios_to_dict(self, scenario_engine):
        """ScenarioComparison.to_dict() serializes correctly."""
        scenario1 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Scenario 1",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            confidence=ConfidenceLevel.HIGH,
            revenue_impact=-100000.0,
        )

        scenario2 = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_ADDITION,
            description="Scenario 2",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
            confidence=ConfidenceLevel.MEDIUM,
            revenue_impact=150000.0,
        )

        comparison = scenario_engine.compare_scenarios([scenario1, scenario2])
        data = comparison.to_dict()

        assert isinstance(data, dict)
        assert "scenarios" in data
        assert "best_case_idx" in data
        assert "worst_case_idx" in data
        assert len(data["scenarios"]) == 2


# =============================================================================
# DATA CLASS TESTS
# =============================================================================


class TestScenarioResultDataClass:
    """Test ScenarioResult data class."""

    def test_scenario_result_defaults(self):
        """ScenarioResult uses sensible defaults."""
        result = ScenarioResult(
            scenario_type=ScenarioType.CLIENT_LOSS,
            description="Test",
            baseline_metrics={},
            projected_metrics={},
            impact_summary="Test",
        )

        assert result.confidence == ConfidenceLevel.MEDIUM
        assert result.revenue_impact == 0.0
        assert result.capacity_impact_pct == 0.0
        assert result.risk_factors == []

    def test_scenario_result_enum_values(self):
        """ScenarioType enum has all expected values."""
        expected_types = {
            ScenarioType.CLIENT_LOSS,
            ScenarioType.CLIENT_ADDITION,
            ScenarioType.RESOURCE_CHANGE,
            ScenarioType.PRICING_CHANGE,
            ScenarioType.CAPACITY_SHIFT,
            ScenarioType.WORKLOAD_REBALANCE,
        }

        assert len(ScenarioType) == 6
        for scenario_type in expected_types:
            assert scenario_type in ScenarioType

    def test_confidence_level_enum(self):
        """ConfidenceLevel enum has expected values."""
        assert ConfidenceLevel.HIGH.value == "HIGH"
        assert ConfidenceLevel.MEDIUM.value == "MEDIUM"
        assert ConfidenceLevel.LOW.value == "LOW"


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_client_loss_all_fields_optional(self, scenario_engine, mock_query_engine):
        """Handles client profile with missing optional fields."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test",
            # Missing total_invoiced, total_outstanding, etc.
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 0, "total_tasks": 0},
        ]

        mock_query_engine.team_capacity_overview.return_value = {
            "distribution": [],
            "total_people": 0,
            "total_active_tasks": 0,
        }

        result = scenario_engine.model_client_loss("cli-001")

        # Should still succeed with defaults
        assert result is not None

    def test_addition_zero_portfolio(self, scenario_engine, mock_query_engine):
        """Handles empty portfolio."""
        mock_query_engine.client_portfolio_overview.return_value = []
        mock_query_engine.team_capacity_overview.return_value = {
            "total_people": 1,
            "total_active_tasks": 20,
            "people_available": 0,
            "people_overloaded": 1,
        }

        result = scenario_engine.model_client_addition(100000.0, 30)

        assert result is not None
        assert result.projected_metrics["hiring_needed"] > 0

    def test_resource_change_single_person_team(self, scenario_engine, mock_query_engine):
        """Handles resource change in single-person team."""
        mock_query_engine.resource_load_distribution.return_value = [
            {"person_id": "p-1", "person_name": "Alice", "active_tasks": 40},
        ]

        mock_query_engine.person_operational_profile.return_value = {
            "person_id": "p-1",
            "person_name": "Alice",
            "active_tasks": 40,
            "projects": [{"project_id": "p1", "project_name": "P1"}],
            "clients": [{"client_id": "c1", "client_name": "C1"}],
        }

        mock_query_engine.team_capacity_overview.return_value = {
            "total_people": 1,
            "total_active_tasks": 40,
        }

        result = scenario_engine.model_resource_change("Alice", "leaves")

        assert result is not None
        assert any("Single-person team" in risk for risk in result.risk_factors)

    def test_pricing_change_zero_portfolio_revenue(
        self, scenario_engine, mock_query_engine, mock_cost_engine
    ):
        """Handles pricing change with zero portfolio baseline."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test",
            "total_invoiced": 100000.0,
            "total_outstanding": 0,
        }

        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001", "total_invoiced": 100000.0},
        ]

        # Mock cost profile as None instead of MagicMock
        mock_cost_engine.compute_client_cost.return_value = None

        result = scenario_engine.model_pricing_change("cli-001", 0.10)

        # Should handle gracefully
        assert result is not None
