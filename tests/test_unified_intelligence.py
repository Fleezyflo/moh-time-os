"""
Comprehensive tests for UnifiedIntelligenceLayer.

Tests cover:
- IntelligenceLayer instantiation and initialization
- Lazy initialization of sub-engines
- run_intelligence_cycle with all sub-engines mocked
- get_client_intelligence with mocked engines
- get_portfolio_dashboard with mocked data
- run_scenario delegation to ScenarioEngine
- Error handling and resilience
- Data class serialization (to_dict)
- All code rules enforcement

Target: 25+ tests
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from lib.intelligence.correlation_engine import HealthGrade, IntelligenceBrief
from lib.intelligence.unified_intelligence import (
    ClientIntelligence,
    IntelligenceCycleResult,
    IntelligenceLayer,
    PortfolioDashboard,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def intelligence_layer():
    """Create an IntelligenceLayer instance."""
    return IntelligenceLayer(db_path=None)


@pytest.fixture
def mock_pattern_results():
    """Mock pattern detection results."""
    return {
        "detected_at": datetime.now().isoformat(),
        "success": True,
        "total_detected": 3,
        "total_patterns": 10,
        "detection_errors": 0,
        "errors": [],
        "by_type": {
            "concentration": 1,
            "cascade": 1,
            "degradation": 1,
            "drift": 0,
            "correlation": 0,
        },
        "by_severity": {
            "structural": 2,
            "operational": 1,
            "informational": 0,
        },
        "patterns": [
            {
                "pattern_id": "pat_revenue_concentration",
                "pattern_name": "Revenue Concentration",
                "pattern_type": "concentration",
                "severity": "structural",
                "entities_involved": [{"type": "client", "id": "client_1"}],
                "metrics": {"top_1_share_pct": 35.0},
            },
            {
                "pattern_id": "pat_team_exhaustion",
                "pattern_name": "Team Exhaustion",
                "pattern_type": "degradation",
                "severity": "structural",
                "entities_involved": [{"type": "person", "id": "person_1"}],
                "metrics": {"avg_load_score": 85.0},
            },
            {
                "pattern_id": "pat_quality_degradation",
                "pattern_name": "Quality Degradation",
                "pattern_type": "degradation",
                "severity": "operational",
                "entities_involved": [],
                "metrics": {"clients_with_overdue": 5},
            },
        ],
    }


@pytest.fixture
def mock_cost_profile():
    """Mock client cost profile."""
    return {
        "client_id": "client_1",
        "name": "Client A",
        "revenue_total": 50000.0,
        "task_count": 25,
        "active_tasks": 5,
        "communication_count": 150,
        "overdue_tasks": 2,
        "avg_task_duration_days": 15.5,
        "efficiency_ratio": 0.75,
        "profitability_band": "HIGH",
        "cost_drivers": ["task_volume", "communication"],
    }


@pytest.fixture
def mock_trajectory():
    """Mock client trajectory."""
    return {
        "entity_id": "client_1",
        "entity_name": "Client A",
        "entity_type": "client",
        "metrics": {
            "revenue": {
                "direction": "rising",
                "slope": 500.0,
                "r_squared": 0.85,
                "confidence": "high",
            }
        },
        "projections": {},
        "velocity": None,
        "acceleration": None,
        "overall_health": "IMPROVING",
        "summary": "Client trajectory improving",
    }


@pytest.fixture
def mock_intelligence_brief():
    """Mock correlation engine brief."""
    brief = MagicMock(spec=IntelligenceBrief)
    brief.generated_at = datetime.now().isoformat()
    brief.pattern_results = {}
    brief.signal_results = {}
    brief.compound_risks = []
    brief.cross_domain_correlations = []
    brief.priority_actions = []
    brief.executive_summary = "Portfolio health stable"
    brief.health_grade = HealthGrade.B
    return brief


@pytest.fixture
def mock_portfolio_profitability():
    """Mock portfolio profitability."""
    mock = MagicMock()
    mock.to_dict.return_value = {
        "total_revenue": 500000.0,
        "total_clients": 10,
        "profitable_count": 7,
        "marginal_count": 2,
        "unprofitable_count": 1,
        "efficiency_distribution": {"HIGH": 7, "MED": 2, "LOW": 1},
        "top_profitable": [],
        "bottom_unprofitable": [],
    }
    mock.total_clients = 10
    mock.total_revenue = 500000.0
    mock.profitable_count = 7
    return mock


# =============================================================================
# TESTS: INSTANTIATION AND INITIALIZATION
# =============================================================================


def test_intelligence_layer_instantiation():
    """Test basic IntelligenceLayer instantiation."""
    layer = IntelligenceLayer()
    assert layer is not None
    assert layer.db_path is None


def test_intelligence_layer_with_db_path():
    """Test IntelligenceLayer instantiation with custom db_path."""
    db_path = Path("/tmp/test.db")
    layer = IntelligenceLayer(db_path=db_path)
    assert layer.db_path == db_path


def test_lazy_initialization_correlation_engine():
    """Test lazy initialization of correlation engine."""
    layer = IntelligenceLayer()

    # Engine should not be initialized yet
    assert layer._correlation_engine is None

    # Mock the engine initialization
    with patch("lib.intelligence.unified_intelligence.CorrelationEngine") as mock_engine_class:
        mock_engine_class.return_value = MagicMock()

        # Getting the engine should initialize it
        engine = layer._get_correlation_engine()
        assert engine is not None
        mock_engine_class.assert_called_once()


def test_lazy_initialization_cost_engine():
    """Test lazy initialization of cost engine."""
    layer = IntelligenceLayer()
    assert layer._cost_engine is None

    with patch("lib.intelligence.unified_intelligence.CostToServeEngine") as mock_engine:
        mock_engine.return_value = MagicMock()
        engine = layer._get_cost_engine()
        assert engine is not None
        mock_engine.assert_called_once()


def test_lazy_initialization_trajectory_engine():
    """Test lazy initialization of trajectory engine."""
    layer = IntelligenceLayer()
    assert layer._trajectory_engine is None

    with patch("lib.intelligence.unified_intelligence.TrajectoryEngine") as mock_engine:
        mock_engine.return_value = MagicMock()
        engine = layer._get_trajectory_engine()
        assert engine is not None
        mock_engine.assert_called_once()


def test_lazy_initialization_scenario_engine():
    """Test lazy initialization of scenario engine."""
    layer = IntelligenceLayer()
    assert layer._scenario_engine is None

    with patch("lib.intelligence.unified_intelligence.ScenarioEngine") as mock_engine:
        mock_engine.return_value = MagicMock()
        engine = layer._get_scenario_engine()
        assert engine is not None
        mock_engine.assert_called_once()


def test_lazy_initialization_caching():
    """Test that lazy initialization caches engines."""
    layer = IntelligenceLayer()

    with patch("lib.intelligence.unified_intelligence.CorrelationEngine") as mock_engine:
        mock_engine.return_value = MagicMock()

        engine1 = layer._get_correlation_engine()
        engine2 = layer._get_correlation_engine()

        # Should return same instance
        assert engine1 is engine2
        # Should only initialize once
        mock_engine.assert_called_once()


# =============================================================================
# TESTS: INTELLIGENCE CYCLE
# =============================================================================


def test_run_intelligence_cycle_success(intelligence_layer, mock_pattern_results):
    """Test successful intelligence cycle execution."""
    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.return_value = mock_pattern_results

        with patch.object(intelligence_layer, "_get_correlation_engine") as mock_corr:
            mock_brief = MagicMock(spec=IntelligenceBrief)
            mock_brief.generated_at = datetime.now().isoformat()
            mock_brief.pattern_results = {}
            mock_brief.signal_results = {}
            mock_brief.compound_risks = []
            mock_brief.cross_domain_correlations = []
            mock_brief.priority_actions = []
            mock_brief.executive_summary = "Test summary"
            mock_brief.health_grade = HealthGrade.B

            mock_engine = MagicMock()
            mock_engine.run_full_scan.return_value = mock_brief
            mock_corr.return_value = mock_engine

            with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
                mock_cost_obj = MagicMock()
                mock_cost_obj.compute_portfolio_profitability.return_value = None
                mock_cost.return_value = mock_cost_obj

                with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                    mock_traj_obj = MagicMock()
                    mock_traj_obj.portfolio_health_trajectory.return_value = []
                    mock_traj.return_value = mock_traj_obj

                    result = intelligence_layer.run_intelligence_cycle()

                    assert result is not None
                    assert isinstance(result, IntelligenceCycleResult)
                    assert result.timestamp is not None
                    assert result.health_grade == "B"
                    assert result.cycle_duration_ms >= 0


def test_run_intelligence_cycle_pattern_detection_error(intelligence_layer):
    """Test intelligence cycle handles pattern detection errors."""
    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.side_effect = Exception("Pattern detection failed")

        with patch.object(intelligence_layer, "_get_correlation_engine") as mock_corr:
            mock_brief = MagicMock(spec=IntelligenceBrief)
            mock_brief.health_grade = HealthGrade.B
            mock_brief.compound_risks = []
            mock_brief.cross_domain_correlations = []
            mock_brief.priority_actions = []

            mock_engine = MagicMock()
            mock_engine.run_full_scan.return_value = mock_brief
            mock_corr.return_value = mock_engine

            with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
                mock_cost_obj = MagicMock()
                mock_cost_obj.compute_portfolio_profitability.return_value = None
                mock_cost.return_value = mock_cost_obj

                with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                    mock_traj_obj = MagicMock()
                    mock_traj_obj.portfolio_health_trajectory.return_value = []
                    mock_traj.return_value = mock_traj_obj

                    result = intelligence_layer.run_intelligence_cycle()

                    # Should handle error gracefully
                    assert result is not None
                    assert isinstance(result, IntelligenceCycleResult)
                    assert "error" in result.pattern_results


def test_run_intelligence_cycle_correlation_error(intelligence_layer):
    """Test intelligence cycle handles correlation engine errors."""
    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.return_value = {"patterns": []}

        with patch.object(intelligence_layer, "_get_correlation_engine") as mock_corr:
            mock_corr.side_effect = Exception("Correlation failed")

            with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
                mock_cost_obj = MagicMock()
                mock_cost_obj.compute_portfolio_profitability.return_value = None
                mock_cost.return_value = mock_cost_obj

                with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                    mock_traj_obj = MagicMock()
                    mock_traj_obj.portfolio_health_trajectory.return_value = []
                    mock_traj.return_value = mock_traj_obj

                    result = intelligence_layer.run_intelligence_cycle()

                    # Should handle error gracefully
                    assert result is not None
                    assert "error" in result.correlation_brief


def test_run_intelligence_cycle_all_components_mocked(
    intelligence_layer,
    mock_pattern_results,
    mock_portfolio_profitability,
):
    """Test intelligence cycle with all components mocked."""
    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.return_value = mock_pattern_results

        with patch.object(intelligence_layer, "_get_correlation_engine") as mock_corr:
            mock_brief = MagicMock(spec=IntelligenceBrief)
            mock_brief.generated_at = datetime.now().isoformat()
            mock_brief.pattern_results = {}
            mock_brief.signal_results = {}
            mock_brief.compound_risks = []
            mock_brief.cross_domain_correlations = []
            mock_brief.priority_actions = []
            mock_brief.executive_summary = "Test"
            mock_brief.health_grade = HealthGrade.A

            mock_engine = MagicMock()
            mock_engine.run_full_scan.return_value = mock_brief
            mock_corr.return_value = mock_engine

            with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
                mock_cost_obj = MagicMock()
                mock_cost_obj.compute_portfolio_profitability.return_value = (
                    mock_portfolio_profitability
                )
                mock_cost.return_value = mock_cost_obj

                with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                    traj_obj = MagicMock()
                    traj_obj.to_dict.return_value = {"entity_id": "test"}
                    mock_traj_obj = MagicMock()
                    mock_traj_obj.portfolio_health_trajectory.return_value = [traj_obj]
                    mock_traj.return_value = mock_traj_obj

                    result = intelligence_layer.run_intelligence_cycle()

                    assert result.health_grade == "A"
                    assert result.portfolio_profitability["total_revenue"] == 500000.0
                    assert len(result.trajectory_results) == 1


# =============================================================================
# TESTS: CLIENT INTELLIGENCE
# =============================================================================


def test_get_client_intelligence_success(intelligence_layer, mock_cost_profile):
    """Test successful client intelligence retrieval."""
    client_id = "client_1"

    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.return_value = {"patterns": []}

        with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
            mock_cost_obj = MagicMock()
            mock_client_cost = MagicMock()
            mock_client_cost.to_dict.return_value = mock_cost_profile
            mock_client_cost.name = "Client A"
            mock_cost_obj.compute_client_cost.return_value = mock_client_cost
            mock_cost.return_value = mock_cost_obj

            with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                mock_traj_obj = MagicMock()
                mock_traj_obj.client_full_trajectory.return_value = None
                mock_traj.return_value = mock_traj_obj

                intel = intelligence_layer.get_client_intelligence(client_id)

                assert intel is not None
                assert isinstance(intel, ClientIntelligence)
                assert intel.client_id == client_id
                assert intel.name == "Client A"
                assert intel.cost_profile == mock_cost_profile


def test_get_client_intelligence_with_patterns(
    intelligence_layer,
    mock_cost_profile,
):
    """Test client intelligence includes patterns affecting client."""
    client_id = "client_1"

    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.return_value = {
            "patterns": [
                {
                    "pattern_id": "pat_1",
                    "pattern_name": "Test Pattern",
                    "severity": "structural",
                    "entities_involved": [{"type": "client", "id": client_id}],
                }
            ]
        }

        with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
            mock_cost_obj = MagicMock()
            mock_client_cost = MagicMock()
            mock_client_cost.to_dict.return_value = mock_cost_profile
            mock_client_cost.name = "Client A"
            mock_cost_obj.compute_client_cost.return_value = mock_client_cost
            mock_cost.return_value = mock_cost_obj

            with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                mock_traj_obj = MagicMock()
                mock_traj_obj.client_full_trajectory.return_value = None
                mock_traj.return_value = mock_traj_obj

                intel = intelligence_layer.get_client_intelligence(client_id)

                assert len(intel.patterns_affecting) == 1
                assert intel.patterns_affecting[0]["pattern_id"] == "pat_1"


def test_get_client_intelligence_error_handling(intelligence_layer):
    """Test client intelligence handles errors gracefully."""
    client_id = "client_1"

    with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
        mock_cost.side_effect = Exception("Cost engine failed")

        intel = intelligence_layer.get_client_intelligence(client_id)

        # Should still return ClientIntelligence
        assert intel is not None
        assert isinstance(intel, ClientIntelligence)
        assert intel.client_id == client_id


def test_client_intelligence_risk_computation(intelligence_layer, mock_cost_profile):
    """Test risk factor computation for client."""
    client_id = "client_1"

    # Create a low-efficiency profile to trigger risk
    low_efficiency_profile = mock_cost_profile.copy()
    low_efficiency_profile["efficiency_ratio"] = 0.3

    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.return_value = {"patterns": []}

        with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
            mock_cost_obj = MagicMock()
            mock_client_cost = MagicMock()
            mock_client_cost.to_dict.return_value = low_efficiency_profile
            mock_client_cost.name = "Client A"
            mock_cost_obj.compute_client_cost.return_value = mock_client_cost
            mock_cost.return_value = mock_cost_obj

            with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                mock_traj_obj = MagicMock()
                mock_traj_obj.client_full_trajectory.return_value = None
                mock_traj.return_value = mock_traj_obj

                intel = intelligence_layer.get_client_intelligence(client_id)

                assert "LOW_EFFICIENCY" in intel.risk_factors


def test_client_intelligence_overall_score(intelligence_layer, mock_cost_profile):
    """Test overall score computation for client."""
    client_id = "client_1"

    with patch("lib.intelligence.unified_intelligence.detect_all_patterns") as mock_patterns:
        mock_patterns.return_value = {"patterns": []}

        with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
            mock_cost_obj = MagicMock()
            mock_client_cost = MagicMock()
            mock_client_cost.to_dict.return_value = mock_cost_profile
            mock_client_cost.name = "Client A"
            mock_cost_obj.compute_client_cost.return_value = mock_client_cost
            mock_cost.return_value = mock_cost_obj

            with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                mock_traj_obj = MagicMock()
                mock_traj_obj.client_full_trajectory.return_value = None
                mock_traj.return_value = mock_traj_obj

                intel = intelligence_layer.get_client_intelligence(client_id)

                assert 0 <= intel.overall_score <= 100


# =============================================================================
# TESTS: PORTFOLIO DASHBOARD
# =============================================================================


def test_get_portfolio_dashboard_success(intelligence_layer, mock_portfolio_profitability):
    """Test successful portfolio dashboard generation."""
    with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
        mock_cost_obj = MagicMock()
        mock_cost_obj.compute_portfolio_profitability.return_value = mock_portfolio_profitability
        mock_cost.return_value = mock_cost_obj

        with patch.object(intelligence_layer, "_get_correlation_engine") as mock_corr:
            mock_brief = MagicMock(spec=IntelligenceBrief)
            mock_brief.health_grade = HealthGrade.B
            mock_brief.compound_risks = []
            mock_brief.priority_actions = []

            mock_engine = MagicMock()
            mock_engine.run_full_scan.return_value = mock_brief
            mock_corr.return_value = mock_engine

            with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                mock_traj_obj = MagicMock()
                mock_traj_obj.portfolio_health_trajectory.return_value = []
                mock_traj.return_value = mock_traj_obj

                dashboard = intelligence_layer.get_portfolio_dashboard()

                assert dashboard is not None
                assert isinstance(dashboard, PortfolioDashboard)
                assert dashboard.total_clients == 10
                assert dashboard.revenue_total == 500000.0
                assert dashboard.profitable_count == 7
                assert dashboard.health_grade == "B"


def test_get_portfolio_dashboard_with_declining_clients(
    intelligence_layer,
    mock_portfolio_profitability,
):
    """Test portfolio dashboard includes declining client count."""
    with patch.object(intelligence_layer, "_get_cost_engine") as mock_cost:
        mock_cost_obj = MagicMock()
        mock_cost_obj.compute_portfolio_profitability.return_value = mock_portfolio_profitability
        mock_cost.return_value = mock_cost_obj

        with patch.object(intelligence_layer, "_get_correlation_engine") as mock_corr:
            mock_brief = MagicMock(spec=IntelligenceBrief)
            mock_brief.health_grade = HealthGrade.C
            mock_brief.compound_risks = []
            mock_brief.priority_actions = []

            mock_engine = MagicMock()
            mock_engine.run_full_scan.return_value = mock_brief
            mock_corr.return_value = mock_engine

            with patch.object(intelligence_layer, "_get_trajectory_engine") as mock_traj:
                traj1 = MagicMock()
                traj1.overall_health = "DECLINING"
                traj2 = MagicMock()
                traj2.overall_health = "CRITICAL"

                mock_traj_obj = MagicMock()
                mock_traj_obj.portfolio_health_trajectory.return_value = [traj1, traj2]
                mock_traj.return_value = mock_traj_obj

                dashboard = intelligence_layer.get_portfolio_dashboard()

                assert dashboard.declining_count == 1
                assert dashboard.at_risk_count == 1


# =============================================================================
# TESTS: SCENARIO MODELING
# =============================================================================


def test_run_scenario_client_loss(intelligence_layer):
    """Test CLIENT_LOSS scenario execution."""
    client_id = "client_1"

    with patch.object(intelligence_layer, "_get_scenario_engine") as mock_scenario:
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "scenario_type": "CLIENT_LOSS",
            "description": "Test",
            "revenue_impact": -50000.0,
            "risk_factors": ["HIGH_DEPENDENCY"],
        }

        mock_engine = MagicMock()
        mock_engine.model_client_loss.return_value = mock_result
        mock_scenario.return_value = mock_engine

        result = intelligence_layer.run_scenario("CLIENT_LOSS", client_id=client_id)

        assert result["scenario_type"] == "CLIENT_LOSS"
        assert result["revenue_impact"] == -50000.0
        mock_engine.model_client_loss.assert_called_once_with(client_id)


def test_run_scenario_client_addition(intelligence_layer):
    """Test CLIENT_ADDITION scenario execution."""
    with patch.object(intelligence_layer, "_get_scenario_engine") as mock_scenario:
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "scenario_type": "CLIENT_ADDITION",
            "revenue_impact": 30000.0,
        }

        mock_engine = MagicMock()
        mock_engine.model_client_addition.return_value = mock_result
        mock_scenario.return_value = mock_engine

        result = intelligence_layer.run_scenario(
            "CLIENT_ADDITION",
            name="New Client",
            revenue=30000.0,
        )

        assert result["scenario_type"] == "CLIENT_ADDITION"
        mock_engine.model_client_addition.assert_called_once()


def test_run_scenario_resource_change(intelligence_layer):
    """Test RESOURCE_CHANGE scenario execution."""
    with patch.object(intelligence_layer, "_get_scenario_engine") as mock_scenario:
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "scenario_type": "RESOURCE_CHANGE",
            "capacity_impact_pct": -20.0,
        }

        mock_engine = MagicMock()
        mock_engine.model_resource_change.return_value = mock_result
        mock_scenario.return_value = mock_engine

        result = intelligence_layer.run_scenario(
            "RESOURCE_CHANGE",
            person_id="person_1",
            change_type="leaves",
        )

        assert result["scenario_type"] == "RESOURCE_CHANGE"
        mock_engine.model_resource_change.assert_called_once()


def test_run_scenario_invalid_type(intelligence_layer):
    """Test run_scenario with invalid scenario type."""
    with patch.object(intelligence_layer, "_get_scenario_engine") as mock_scenario:
        mock_engine = MagicMock()
        mock_scenario.return_value = mock_engine

        result = intelligence_layer.run_scenario("INVALID_TYPE")

        assert "error" in result
        assert "Unknown scenario type" in result["error"]


def test_run_scenario_missing_required_param(intelligence_layer):
    """Test run_scenario with missing required parameters."""
    with patch.object(intelligence_layer, "_get_scenario_engine") as mock_scenario:
        mock_engine = MagicMock()
        mock_scenario.return_value = mock_engine

        result = intelligence_layer.run_scenario("CLIENT_LOSS")

        assert "error" in result
        assert "client_id required" in result["error"]


def test_run_scenario_error_handling(intelligence_layer):
    """Test run_scenario error handling."""
    with patch.object(intelligence_layer, "_get_scenario_engine") as mock_scenario:
        mock_scenario.side_effect = Exception("Scenario engine failed")

        result = intelligence_layer.run_scenario("CLIENT_LOSS", client_id="client_1")

        assert "error" in result


# =============================================================================
# TESTS: DATA CLASS SERIALIZATION
# =============================================================================


def test_intelligence_cycle_result_to_dict():
    """Test IntelligenceCycleResult.to_dict() serialization."""
    result = IntelligenceCycleResult(
        timestamp="2024-01-01T00:00:00",
        health_grade="A",
        executive_summary="Test",
        cycle_duration_ms=1500,
    )

    data = result.to_dict()

    assert isinstance(data, dict)
    assert data["timestamp"] == "2024-01-01T00:00:00"
    assert data["health_grade"] == "A"
    assert data["cycle_duration_ms"] == 1500


def test_client_intelligence_to_dict():
    """Test ClientIntelligence.to_dict() serialization."""
    intel = ClientIntelligence(
        client_id="client_1",
        name="Client A",
        overall_score=75.5,
        recommendation="MAINTAIN_RELATIONSHIP",
    )

    data = intel.to_dict()

    assert isinstance(data, dict)
    assert data["client_id"] == "client_1"
    assert data["name"] == "Client A"
    assert data["overall_score"] == 75.5


def test_portfolio_dashboard_to_dict():
    """Test PortfolioDashboard.to_dict() serialization."""
    dashboard = PortfolioDashboard(
        total_clients=10,
        health_grade="B",
        revenue_total=500000.0,
        profitable_count=7,
    )

    data = dashboard.to_dict()

    assert isinstance(data, dict)
    assert data["total_clients"] == 10
    assert data["health_grade"] == "B"
    assert data["revenue_total"] == 500000.0


# =============================================================================
# TESTS: HELPER METHODS
# =============================================================================


def test_build_cycle_summary():
    """Test executive summary building."""
    layer = IntelligenceLayer()

    summary = layer._build_cycle_summary(
        pattern_results={"total_detected": 3},
        correlation_brief={"compound_risks": [{}, {}]},
        portfolio_profitability={"profitable_count": 7, "total_clients": 10},
        health_grade="B",
    )

    assert "3 patterns" in summary
    assert "2 compound risks" in summary
    assert "7/10 clients profitable" in summary


def test_compute_client_risk_factors():
    """Test client risk factor computation."""
    layer = IntelligenceLayer()

    risk_factors = layer._compute_client_risk_factors(
        cost_profile={"efficiency_ratio": 0.3, "profitability_band": "LOW"},
        trajectory={"overall_health": "DECLINING"},
        patterns_affecting=[{"severity": "structural"}],
    )

    assert "LOW_EFFICIENCY" in risk_factors
    assert "LOW_PROFITABILITY" in risk_factors
    assert "DECLINING_TREND" in risk_factors


def test_compute_client_score():
    """Test overall client score computation."""
    layer = IntelligenceLayer()

    score = layer._compute_client_score(
        cost_profile={"efficiency_ratio": 0.8},
        trajectory={"overall_health": "IMPROVING"},
        patterns_affecting=[],
    )

    assert 0 <= score <= 100
    assert score > 70  # Should be decent


def test_generate_client_recommendation_excellent():
    """Test recommendation generation for excellent client."""
    layer = IntelligenceLayer()

    rec = layer._generate_client_recommendation(
        cost_profile={},
        trajectory={},
        risk_factors=[],
        overall_score=85.0,
    )

    assert rec == "MAINTAIN_RELATIONSHIP"


def test_generate_client_recommendation_declining():
    """Test recommendation generation for declining client."""
    layer = IntelligenceLayer()

    rec = layer._generate_client_recommendation(
        cost_profile={},
        trajectory={},
        risk_factors=["DECLINING_TREND"],
        overall_score=65.0,
    )

    assert rec == "MONITOR_CLOSELY"


def test_generate_client_recommendation_poor():
    """Test recommendation generation for poor client."""
    layer = IntelligenceLayer()

    rec = layer._generate_client_recommendation(
        cost_profile={},
        trajectory={},
        risk_factors=["LOW_EFFICIENCY", "DECLINING_TREND"],
        overall_score=35.0,
    )

    assert rec == "REVIEW_ENGAGEMENT"
