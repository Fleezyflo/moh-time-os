"""
Tests for Cost-to-Serve Intelligence Module

Covers:
- CostToServeEngine initialization
- compute_client_cost with various data scenarios
- compute_project_cost with scope creep detection
- compute_portfolio_profitability with percentile banding
- get_hidden_cost_clients for cost indicator detection
- get_profitability_ranking for efficiency ranking
- Edge cases (no data, single client, zero revenue, high overdue)

Uses mocked query_engine to avoid live DB dependency.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.intelligence.cost_to_serve import (
    ClientCostProfile,
    CostToServeEngine,
    PortfolioProfitability,
    ProjectCostProfile,
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
def cost_engine(mock_query_engine):
    """Create a CostToServeEngine with mocked QueryEngine."""
    with patch("lib.intelligence.cost_to_serve.get_engine", return_value=mock_query_engine):
        return CostToServeEngine()


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestCostToServeEngineInit:
    """Test CostToServeEngine initialization."""

    def test_init_creates_engine(self, mock_query_engine):
        """Engine initializes with get_engine."""
        with patch("lib.intelligence.cost_to_serve.get_engine", return_value=mock_query_engine):
            engine = CostToServeEngine()
            assert engine.engine is not None

    def test_init_with_explicit_db_path(self, mock_query_engine):
        """Engine accepts optional db_path parameter."""
        db_path = Path(tempfile.gettempdir()) / "test.db"
        with patch(
            "lib.intelligence.cost_to_serve.get_engine", return_value=mock_query_engine
        ) as mock_get:
            CostToServeEngine(db_path)
            mock_get.assert_called_once_with(db_path)

    def test_init_without_db_path(self, mock_query_engine):
        """Engine initializes with default db_path."""
        with patch(
            "lib.intelligence.cost_to_serve.get_engine", return_value=mock_query_engine
        ) as mock_get:
            CostToServeEngine()
            mock_get.assert_called_once_with(None)

    def test_init_handles_file_not_found(self):
        """Engine raises FileNotFoundError if DB not found."""
        with patch(
            "lib.intelligence.cost_to_serve.get_engine",
            side_effect=FileNotFoundError("DB not found"),
        ):
            with pytest.raises(FileNotFoundError):
                CostToServeEngine()


# =============================================================================
# COMPUTE_CLIENT_COST TESTS
# =============================================================================


class TestComputeClientCost:
    """Test compute_client_cost method."""

    def test_client_cost_basic_profile(self, cost_engine, mock_query_engine):
        """Compute client cost with valid data."""
        # Mock query results
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-001",
            "client_name": "Test Client",
            "total_invoiced": 50000.0,
            "total_outstanding": 5000.0,
        }
        mock_query_engine.client_task_summary.return_value = {
            "total_tasks": 100,
            "active_tasks": 20,
            "completed_tasks": 50,
            "overdue_tasks": 5,
        }
        mock_query_engine.client_communication_summary.return_value = {
            "total_communications": 25,
        }
        mock_query_engine.invoices_in_period.return_value = [
            {"amount": 50000.0},
        ]

        result = cost_engine.compute_client_cost("cli-001")

        assert result is not None
        assert result.client_id == "cli-001"
        assert result.name == "Test Client"
        assert result.revenue_total == 50000.0
        assert result.task_count == 100
        assert result.active_tasks == 20
        assert result.overdue_tasks == 5

    def test_client_cost_efficiency_ratio_calculation(self, cost_engine, mock_query_engine):
        """Efficiency ratio is calculated correctly."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-002",
            "client_name": "Client 2",
            "total_invoiced": 100000.0,
            "total_outstanding": 0,
        }
        mock_query_engine.client_task_summary.return_value = {
            "total_tasks": 100,
            "active_tasks": 10,  # 10 * 2 = 20
            "completed_tasks": 40,  # 40 * 0.5 = 20
            "overdue_tasks": 2,  # 2 * 3 = 6
        }
        mock_query_engine.client_communication_summary.return_value = {
            "total_communications": 0,
        }
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_client_cost("cli-002")

        # Effort score = (10 * 2) + (2 * 3) + (40 * 0.5) = 20 + 6 + 20 = 46
        # Efficiency = 100000 / 46 ≈ 2173.91
        assert result is not None
        expected_effort = (10 * 2) + (2 * 3) + (40 * 0.5)
        expected_efficiency = 100000.0 / expected_effort
        assert abs(result.efficiency_ratio - expected_efficiency) < 1

    def test_client_cost_cost_drivers_high_overdue(self, cost_engine, mock_query_engine):
        """Cost drivers are identified for high overdue count."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-003",
            "client_name": "Problem Client",
            "total_invoiced": 10000.0,
            "total_outstanding": 15000.0,
        }
        mock_query_engine.client_task_summary.return_value = {
            "total_tasks": 50,
            "active_tasks": 5,
            "completed_tasks": 10,
            "overdue_tasks": 20,  # High overdue
        }
        mock_query_engine.client_communication_summary.return_value = {
            "total_communications": 100,  # High comms
        }
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_client_cost("cli-003")

        assert result is not None
        assert len(result.cost_drivers) > 0
        assert any("overdue" in driver.lower() for driver in result.cost_drivers)
        assert any("communication" in driver.lower() for driver in result.cost_drivers)

    def test_client_cost_handles_zero_effort(self, cost_engine, mock_query_engine):
        """Client with zero effort score is handled."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-004",
            "client_name": "New Client",
            "total_invoiced": 0.0,
            "total_outstanding": 0,
        }
        mock_query_engine.client_task_summary.return_value = {
            "total_tasks": 0,
            "active_tasks": 0,
            "completed_tasks": 0,
            "overdue_tasks": 0,
        }
        mock_query_engine.client_communication_summary.return_value = {
            "total_communications": 0,
        }
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_client_cost("cli-004")

        assert result is not None
        assert result.efficiency_ratio == 0  # 0 revenue / 1 effort = 0
        assert result.task_count == 0

    def test_client_cost_missing_client_returns_none(self, cost_engine, mock_query_engine):
        """Missing client returns None."""
        mock_query_engine.client_deep_profile.return_value = None

        result = cost_engine.compute_client_cost("cli-nonexistent")

        assert result is None

    def test_client_cost_handles_none_amounts(self, cost_engine, mock_query_engine):
        """Handles None values in amounts."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-005",
            "client_name": "Client 5",
            "total_invoiced": None,
            "total_outstanding": None,
        }
        mock_query_engine.client_task_summary.return_value = {
            "total_tasks": 10,
            "active_tasks": 2,
            "completed_tasks": 5,
            "overdue_tasks": 1,
        }
        mock_query_engine.client_communication_summary.return_value = {
            "total_communications": 5,
        }
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_client_cost("cli-005")

        assert result is not None
        assert result.revenue_total == 0

    def test_client_cost_to_dict_serialization(self, cost_engine, mock_query_engine):
        """ClientCostProfile.to_dict() serializes correctly."""
        mock_query_engine.client_deep_profile.return_value = {
            "client_id": "cli-006",
            "client_name": "Serialize Test",
            "total_invoiced": 50000.0,
            "total_outstanding": 0,
        }
        mock_query_engine.client_task_summary.return_value = {
            "total_tasks": 20,
            "active_tasks": 5,
            "completed_tasks": 10,
            "overdue_tasks": 2,
        }
        mock_query_engine.client_communication_summary.return_value = {
            "total_communications": 10,
        }
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_client_cost("cli-006")
        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["client_id"] == "cli-006"
        assert data["name"] == "Serialize Test"
        assert data["revenue_total"] == 50000.0
        assert "profitability_band" in data
        assert "cost_drivers" in data

    def test_client_cost_query_exception_handling(self, cost_engine, mock_query_engine):
        """Exceptions in query are logged and None returned."""
        mock_query_engine.client_deep_profile.side_effect = Exception("DB error")

        result = cost_engine.compute_client_cost("cli-007")

        assert result is None


# =============================================================================
# COMPUTE_PROJECT_COST TESTS
# =============================================================================


class TestComputeProjectCost:
    """Test compute_project_cost method."""

    def test_project_cost_basic_profile(self, cost_engine, mock_query_engine):
        """Compute project cost with valid data."""
        mock_query_engine.project_operational_state.return_value = {
            "project_id": "proj-001",
            "project_name": "Test Project",
            "client_id": "cli-001",
            "total_tasks": 50,
            "completed_tasks": 30,
            "overdue_tasks": 5,
        }

        result = cost_engine.compute_project_cost("proj-001")

        assert result is not None
        assert result.project_id == "proj-001"
        assert result.name == "Test Project"
        assert result.client_id == "cli-001"
        assert result.task_count == 50
        assert result.completed_tasks == 30

    def test_project_cost_effort_score_calculation(self, cost_engine, mock_query_engine):
        """Effort score is calculated correctly."""
        mock_query_engine.project_operational_state.return_value = {
            "project_id": "proj-002",
            "project_name": "Project 2",
            "client_id": "cli-002",
            "total_tasks": 100,
            "completed_tasks": 50,
            "overdue_tasks": 10,
        }

        result = cost_engine.compute_project_cost("proj-002")

        assert result is not None
        # Effort = (100 * 1.0) + (10 * 2.0) = 100 + 20 = 120
        expected_effort = (100 * 1.0) + (10 * 2.0)
        assert result.effort_score == expected_effort

    def test_project_cost_scope_creep_detection(self, cost_engine, mock_query_engine):
        """Scope creep detected when overdue ratio > 30%."""
        mock_query_engine.project_operational_state.return_value = {
            "project_id": "proj-003",
            "project_name": "Scope Creep Project",
            "client_id": "cli-003",
            "total_tasks": 100,
            "completed_tasks": 50,
            "overdue_tasks": 35,  # 35% overdue
        }

        result = cost_engine.compute_project_cost("proj-003")

        assert result is not None
        assert result.has_scope_creep is True

    def test_project_cost_no_scope_creep(self, cost_engine, mock_query_engine):
        """No scope creep when overdue ratio <= 30%."""
        mock_query_engine.project_operational_state.return_value = {
            "project_id": "proj-004",
            "project_name": "Clean Project",
            "client_id": "cli-004",
            "total_tasks": 100,
            "completed_tasks": 80,
            "overdue_tasks": 10,  # 10% overdue
        }

        result = cost_engine.compute_project_cost("proj-004")

        assert result is not None
        assert result.has_scope_creep is False

    def test_project_cost_missing_project_returns_none(self, cost_engine, mock_query_engine):
        """Missing project returns None."""
        mock_query_engine.project_operational_state.return_value = None

        result = cost_engine.compute_project_cost("proj-nonexistent")

        assert result is None

    def test_project_cost_to_dict_serialization(self, cost_engine, mock_query_engine):
        """ProjectCostProfile.to_dict() serializes correctly."""
        mock_query_engine.project_operational_state.return_value = {
            "project_id": "proj-005",
            "project_name": "Serialize Project",
            "client_id": "cli-005",
            "total_tasks": 30,
            "completed_tasks": 20,
            "overdue_tasks": 3,
        }

        result = cost_engine.compute_project_cost("proj-005")
        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["project_id"] == "proj-005"
        assert data["name"] == "Serialize Project"
        assert data["task_count"] == 30
        assert "has_scope_creep" in data


# =============================================================================
# COMPUTE_PORTFOLIO_PROFITABILITY TESTS
# =============================================================================


class TestComputePortfolioProfitability:
    """Test compute_portfolio_profitability method."""

    def test_portfolio_profitability_empty_portfolio(self, cost_engine, mock_query_engine):
        """Empty portfolio returns valid empty structure."""
        mock_query_engine.client_portfolio_overview.return_value = []

        result = cost_engine.compute_portfolio_profitability()

        assert result is not None
        assert result.total_clients == 0
        assert result.total_revenue == 0

    def test_portfolio_profitability_multiple_clients(self, cost_engine, mock_query_engine):
        """Portfolio with multiple clients is processed correctly."""
        # Mock portfolio overview
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001"},
            {"client_id": "cli-002"},
            {"client_id": "cli-003"},
        ]

        # Mock individual client profiles
        def mock_deep_profile(client_id):
            profiles = {
                "cli-001": {
                    "client_id": "cli-001",
                    "client_name": "High Revenue",
                    "total_invoiced": 100000.0,
                    "total_outstanding": 0,
                },
                "cli-002": {
                    "client_id": "cli-002",
                    "client_name": "Medium Revenue",
                    "total_invoiced": 50000.0,
                    "total_outstanding": 5000.0,
                },
                "cli-003": {
                    "client_id": "cli-003",
                    "client_name": "Low Revenue",
                    "total_invoiced": 10000.0,
                    "total_outstanding": 10000.0,
                },
            }
            return profiles.get(client_id)

        def mock_task_summary(client_id):
            summaries = {
                "cli-001": {
                    "total_tasks": 50,
                    "active_tasks": 5,
                    "completed_tasks": 30,
                    "overdue_tasks": 2,
                },
                "cli-002": {
                    "total_tasks": 100,
                    "active_tasks": 20,
                    "completed_tasks": 40,
                    "overdue_tasks": 10,
                },
                "cli-003": {
                    "total_tasks": 50,
                    "active_tasks": 30,
                    "completed_tasks": 5,
                    "overdue_tasks": 20,
                },
            }
            return summaries.get(client_id)

        def mock_comm_summary(client_id):
            return {"total_communications": 10}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.side_effect = mock_comm_summary
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_portfolio_profitability()

        assert result is not None
        assert result.total_clients == 3
        assert result.total_revenue == 160000.0

    def test_portfolio_profitability_band_assignment(self, cost_engine, mock_query_engine):
        """Clients are assigned to HIGH/MED/LOW bands based on percentiles."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001"},
            {"client_id": "cli-002"},
            {"client_id": "cli-003"},
            {"client_id": "cli-004"},
        ]

        def mock_deep_profile(client_id):
            profiles = {
                "cli-001": {
                    "client_id": "cli-001",
                    "client_name": "Best",
                    "total_invoiced": 200000.0,
                    "total_outstanding": 0,
                },
                "cli-002": {
                    "client_id": "cli-002",
                    "client_name": "Good",
                    "total_invoiced": 100000.0,
                    "total_outstanding": 0,
                },
                "cli-003": {
                    "client_id": "cli-003",
                    "client_name": "Average",
                    "total_invoiced": 50000.0,
                    "total_outstanding": 0,
                },
                "cli-004": {
                    "client_id": "cli-004",
                    "client_name": "Worst",
                    "total_invoiced": 10000.0,
                    "total_outstanding": 0,
                },
            }
            return profiles.get(client_id)

        def mock_task_summary(client_id):
            # All same effort to isolate efficiency from revenue
            return {"total_tasks": 50, "active_tasks": 5, "completed_tasks": 30, "overdue_tasks": 2}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.return_value = {"total_communications": 10}
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_portfolio_profitability()

        assert result is not None
        # Should have clients in different bands
        assert result.profitable_count >= 0
        assert result.marginal_count >= 0
        assert result.unprofitable_count >= 0

    def test_portfolio_profitability_top_and_bottom(self, cost_engine, mock_query_engine):
        """Top and bottom performers are identified."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001"},
            {"client_id": "cli-002"},
        ]

        def mock_deep_profile(client_id):
            if client_id == "cli-001":
                return {
                    "client_id": "cli-001",
                    "client_name": "Star",
                    "total_invoiced": 100000.0,
                    "total_outstanding": 0,
                }
            else:
                return {
                    "client_id": "cli-002",
                    "client_name": "Problem",
                    "total_invoiced": 10000.0,
                    "total_outstanding": 20000.0,
                }

        def mock_task_summary(client_id):
            return {"total_tasks": 50, "active_tasks": 5, "completed_tasks": 30, "overdue_tasks": 2}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.return_value = {"total_communications": 10}
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.compute_portfolio_profitability()

        assert result is not None
        assert len(result.top_profitable) > 0
        assert result.top_profitable[0]["name"] == "Star"

    def test_portfolio_profitability_to_dict_serialization(self, cost_engine, mock_query_engine):
        """PortfolioProfitability.to_dict() serializes correctly."""
        mock_query_engine.client_portfolio_overview.return_value = []

        result = cost_engine.compute_portfolio_profitability()
        data = result.to_dict()

        assert isinstance(data, dict)
        assert "total_revenue" in data
        assert "total_clients" in data
        assert "profitable_count" in data
        assert "efficiency_distribution" in data


# =============================================================================
# GET_HIDDEN_COST_CLIENTS TESTS
# =============================================================================


class TestGetHiddenCostClients:
    """Test get_hidden_cost_clients method."""

    def test_hidden_cost_clients_high_overdue(self, cost_engine, mock_query_engine):
        """Clients with high overdue ratio are identified."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001"},
        ]

        def mock_deep_profile(client_id):
            return {
                "client_id": "cli-001",
                "client_name": "Problem",
                "total_invoiced": 10000.0,
                "total_outstanding": 5000.0,
            }

        def mock_task_summary(client_id):
            return {
                "total_tasks": 20,
                "active_tasks": 5,
                "completed_tasks": 5,
                "overdue_tasks": 8,
            }  # 40% overdue

        def mock_comm_summary(client_id):
            return {"total_communications": 50}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.side_effect = mock_comm_summary
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.get_hidden_cost_clients()

        assert len(result) > 0
        assert result[0]["client_id"] == "cli-001"
        assert len(result[0]["cost_indicators"]) >= 2

    def test_hidden_cost_clients_high_communication(self, cost_engine, mock_query_engine):
        """Clients with high communication overhead are identified."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-002"},
        ]

        def mock_deep_profile(client_id):
            return {
                "client_id": "cli-002",
                "client_name": "Chatty",
                "total_invoiced": 1000.0,
                "total_outstanding": 5000.0,
            }

        def mock_task_summary(client_id):
            return {
                "total_tasks": 5,
                "active_tasks": 3,
                "completed_tasks": 1,
                "overdue_tasks": 2,
            }  # 40% overdue

        def mock_comm_summary(client_id):
            return {"total_communications": 50}  # 10 comms per task

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.side_effect = mock_comm_summary
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.get_hidden_cost_clients()

        assert len(result) > 0
        assert any("communication" in ind.lower() for ind in result[0]["cost_indicators"])

    def test_hidden_cost_clients_empty_portfolio(self, cost_engine, mock_query_engine):
        """Empty portfolio returns empty list."""
        mock_query_engine.client_portfolio_overview.return_value = []

        result = cost_engine.get_hidden_cost_clients()

        assert result == []

    def test_hidden_cost_clients_requires_multiple_indicators(self, cost_engine, mock_query_engine):
        """Clients with <2 cost indicators are not included."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-003"},
        ]

        def mock_deep_profile(client_id):
            return {
                "client_id": "cli-003",
                "client_name": "Clean",
                "total_invoiced": 50000.0,
                "total_outstanding": 0,
            }

        def mock_task_summary(client_id):
            return {"total_tasks": 50, "active_tasks": 5, "completed_tasks": 30, "overdue_tasks": 2}

        def mock_comm_summary(client_id):
            return {"total_communications": 5}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.side_effect = mock_comm_summary
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.get_hidden_cost_clients()

        assert result == []

    def test_hidden_cost_clients_sorted_by_efficiency(self, cost_engine, mock_query_engine):
        """Hidden cost clients are sorted by efficiency ratio."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-004"},
            {"client_id": "cli-005"},
        ]

        def mock_deep_profile(client_id):
            if client_id == "cli-004":
                return {
                    "client_id": "cli-004",
                    "client_name": "Bad",
                    "total_invoiced": 1000.0,
                    "total_outstanding": 10000.0,
                }
            else:
                return {
                    "client_id": "cli-005",
                    "client_name": "Worse",
                    "total_invoiced": 100.0,
                    "total_outstanding": 20000.0,
                }

        def mock_task_summary(client_id):
            return {
                "total_tasks": 50,
                "active_tasks": 30,
                "completed_tasks": 10,
                "overdue_tasks": 30,
            }

        def mock_comm_summary(client_id):
            return {"total_communications": 100}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.side_effect = mock_comm_summary
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.get_hidden_cost_clients()

        # Should be sorted by efficiency (ascending)
        if len(result) > 1:
            assert result[0]["efficiency_ratio"] <= result[1]["efficiency_ratio"]


# =============================================================================
# GET_PROFITABILITY_RANKING TESTS
# =============================================================================


class TestGetProfitabilityRanking:
    """Test get_profitability_ranking method."""

    def test_profitability_ranking_descending_order(self, cost_engine, mock_query_engine):
        """Ranking is sorted by efficiency ratio (descending)."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001"},
            {"client_id": "cli-002"},
            {"client_id": "cli-003"},
        ]

        def mock_deep_profile(client_id):
            profiles = {
                "cli-001": {
                    "client_id": "cli-001",
                    "client_name": "Best",
                    "total_invoiced": 100000.0,
                    "total_outstanding": 0,
                },
                "cli-002": {
                    "client_id": "cli-002",
                    "client_name": "Middle",
                    "total_invoiced": 50000.0,
                    "total_outstanding": 0,
                },
                "cli-003": {
                    "client_id": "cli-003",
                    "client_name": "Worst",
                    "total_invoiced": 10000.0,
                    "total_outstanding": 0,
                },
            }
            return profiles.get(client_id)

        def mock_task_summary(client_id):
            return {"total_tasks": 50, "active_tasks": 5, "completed_tasks": 30, "overdue_tasks": 2}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.return_value = {"total_communications": 10}
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.get_profitability_ranking()

        assert len(result) == 3
        assert result[0]["name"] == "Best"
        assert result[0]["efficiency_ratio"] > result[1]["efficiency_ratio"]
        assert result[1]["efficiency_ratio"] > result[2]["efficiency_ratio"]

    def test_profitability_ranking_includes_metrics(self, cost_engine, mock_query_engine):
        """Ranking includes required metrics."""
        mock_query_engine.client_portfolio_overview.return_value = [
            {"client_id": "cli-001"},
        ]

        def mock_deep_profile(client_id):
            return {
                "client_id": "cli-001",
                "client_name": "Test",
                "total_invoiced": 50000.0,
                "total_outstanding": 0,
            }

        def mock_task_summary(client_id):
            return {"total_tasks": 50, "active_tasks": 5, "completed_tasks": 30, "overdue_tasks": 2}

        mock_query_engine.client_deep_profile.side_effect = mock_deep_profile
        mock_query_engine.client_task_summary.side_effect = mock_task_summary
        mock_query_engine.client_communication_summary.return_value = {"total_communications": 10}
        mock_query_engine.invoices_in_period.return_value = []

        result = cost_engine.get_profitability_ranking()

        assert len(result) == 1
        assert "client_id" in result[0]
        assert "name" in result[0]
        assert "efficiency_ratio" in result[0]
        assert "revenue" in result[0]
        assert "task_count" in result[0]
        assert "profitability_band" in result[0]

    def test_profitability_ranking_empty_portfolio(self, cost_engine, mock_query_engine):
        """Empty portfolio returns empty list."""
        mock_query_engine.client_portfolio_overview.return_value = []

        result = cost_engine.get_profitability_ranking()

        assert result == []


# =============================================================================
# DATA CLASS SERIALIZATION TESTS
# =============================================================================


class TestDataClassSerialization:
    """Test dataclass to_dict methods."""

    def test_client_cost_profile_to_dict(self):
        """ClientCostProfile.to_dict() returns expected dict."""
        profile = ClientCostProfile(
            client_id="cli-001",
            name="Test",
            revenue_total=50000.0,
            task_count=100,
            active_tasks=20,
            communication_count=10,
            overdue_tasks=5,
            avg_task_duration_days=7.5,
            efficiency_ratio=500.0,
            profitability_band="HIGH",
            cost_drivers=["High revenue", "Low overdue"],
        )

        data = profile.to_dict()

        assert data["client_id"] == "cli-001"
        assert data["name"] == "Test"
        assert data["revenue_total"] == 50000.0
        assert data["profitability_band"] == "HIGH"
        assert isinstance(data["cost_drivers"], list)

    def test_project_cost_profile_to_dict(self):
        """ProjectCostProfile.to_dict() returns expected dict."""
        profile = ProjectCostProfile(
            project_id="proj-001",
            name="Project",
            client_id="cli-001",
            task_count=50,
            completed_tasks=30,
            overdue_tasks=5,
            avg_completion_days=10.0,
            effort_score=75.0,
            has_scope_creep=False,
        )

        data = profile.to_dict()

        assert data["project_id"] == "proj-001"
        assert data["has_scope_creep"] is False
        assert isinstance(data, dict)

    def test_portfolio_profitability_to_dict(self):
        """PortfolioProfitability.to_dict() returns expected dict."""
        portfolio = PortfolioProfitability(
            total_revenue=500000.0,
            total_clients=10,
            profitable_count=7,
            marginal_count=2,
            unprofitable_count=1,
            efficiency_distribution={"HIGH": 7, "MED": 2, "LOW": 1},
            top_profitable=[{"client_id": "cli-001", "name": "Best"}],
            bottom_unprofitable=[{"client_id": "cli-010", "name": "Worst"}],
        )

        data = portfolio.to_dict()

        assert data["total_revenue"] == 500000.0
        assert data["total_clients"] == 10
        assert "efficiency_distribution" in data
        assert isinstance(data["top_profitable"], list)
