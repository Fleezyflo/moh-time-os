"""
Query Engine Tests — Task 3.1

Tests for lib/query_engine.py cross-entity intelligence queries.
"""

import pytest
from pathlib import Path

from lib.query_engine import QueryEngine, get_engine

DB_PATH = Path(__file__).parent.parent / "data" / "moh_time_os.db"


@pytest.fixture
def engine():
    """Get a QueryEngine instance."""
    return QueryEngine(DB_PATH)


class TestQueryEngineInit:
    """Test QueryEngine initialization."""

    def test_init_with_valid_path(self):
        """Engine initializes with valid database path."""
        engine = QueryEngine(DB_PATH)
        assert engine.db_path == DB_PATH

    def test_init_with_invalid_path(self):
        """Engine raises error with invalid path."""
        with pytest.raises(FileNotFoundError):
            QueryEngine(Path("/nonexistent/db.sqlite"))

    def test_get_engine_convenience(self):
        """get_engine() convenience function works."""
        engine = get_engine(DB_PATH)
        assert isinstance(engine, QueryEngine)


class TestPortfolioQueries:
    """Test portfolio-level queries."""

    def test_client_portfolio_overview_returns_list(self, engine):
        """client_portfolio_overview returns a list of dicts."""
        result = engine.client_portfolio_overview()
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)

    def test_client_portfolio_overview_has_expected_keys(self, engine):
        """Portfolio overview contains expected fields."""
        result = engine.client_portfolio_overview()
        expected_keys = {"client_id", "client_name", "project_count", "total_tasks"}
        assert expected_keys.issubset(result[0].keys())

    def test_client_portfolio_overview_ordering(self, engine):
        """Portfolio can be ordered by different columns."""
        by_tasks = engine.client_portfolio_overview(order_by="total_tasks", desc=True)
        by_revenue = engine.client_portfolio_overview(order_by="ytd_revenue", desc=True)

        # Both should return results
        assert len(by_tasks) > 0
        assert len(by_revenue) > 0

    def test_resource_load_distribution_returns_list(self, engine):
        """resource_load_distribution returns people with loads."""
        result = engine.resource_load_distribution()
        assert isinstance(result, list)
        # Should have some people with tasks
        assert any(p["assigned_tasks"] > 0 for p in result)

    def test_resource_load_has_load_score(self, engine):
        """Resource load includes computed load_score."""
        result = engine.resource_load_distribution()
        if result:
            assert "load_score" in result[0]
            assert 0 <= result[0]["load_score"] <= 100

    def test_portfolio_structural_risks_returns_list(self, engine):
        """portfolio_structural_risks returns risk dicts."""
        result = engine.portfolio_structural_risks()
        assert isinstance(result, list)
        # Risks should have required structure
        for risk in result:
            assert "entity_type" in risk
            assert "risk_type" in risk
            assert "severity" in risk
            assert risk["severity"] in ("HIGH", "MEDIUM", "LOW")


class TestClientQueries:
    """Test client-level queries."""

    @pytest.fixture
    def sample_client_id(self, engine):
        """Get a client ID that has data."""
        clients = engine.client_portfolio_overview()
        # Find a client with projects
        for c in clients:
            if c["project_count"] > 0:
                return c["client_id"]
        return clients[0]["client_id"] if clients else None

    def test_client_deep_profile_returns_dict(self, engine, sample_client_id):
        """client_deep_profile returns a dict for valid client."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.client_deep_profile(sample_client_id)
        assert isinstance(result, dict)
        assert result["client_id"] == sample_client_id

    def test_client_deep_profile_has_nested_data(self, engine, sample_client_id):
        """client_deep_profile includes projects, people, invoices."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.client_deep_profile(sample_client_id)
        assert "projects" in result
        assert "people_involved" in result
        assert "recent_invoices" in result
        assert isinstance(result["projects"], list)

    def test_client_deep_profile_nonexistent(self, engine):
        """client_deep_profile returns None for nonexistent client."""
        result = engine.client_deep_profile("nonexistent-id-12345")
        assert result is None

    def test_client_task_summary_returns_dict(self, engine, sample_client_id):
        """client_task_summary returns task metrics."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.client_task_summary(sample_client_id)
        assert isinstance(result, dict)
        assert "total_tasks" in result
        assert "tasks_by_status" in result


class TestResourceQueries:
    """Test resource/person queries."""

    @pytest.fixture
    def sample_person_id(self, engine):
        """Get a person ID that has tasks."""
        people = engine.resource_load_distribution()
        for p in people:
            if p["assigned_tasks"] > 0:
                return p["person_id"]
        return people[0]["person_id"] if people else None

    def test_person_operational_profile_returns_dict(self, engine, sample_person_id):
        """person_operational_profile returns dict for valid person."""
        if not sample_person_id:
            pytest.skip("No people with tasks")

        result = engine.person_operational_profile(sample_person_id)
        assert isinstance(result, dict)
        assert result["person_id"] == sample_person_id

    def test_person_operational_profile_has_projects(self, engine, sample_person_id):
        """Person profile includes their projects."""
        if not sample_person_id:
            pytest.skip("No people with tasks")

        result = engine.person_operational_profile(sample_person_id)
        assert "projects" in result
        assert "clients" in result

    def test_person_operational_profile_nonexistent(self, engine):
        """person_operational_profile returns None for nonexistent person."""
        result = engine.person_operational_profile("nonexistent-id-12345")
        assert result is None

    def test_team_capacity_overview_returns_dict(self, engine):
        """team_capacity_overview returns capacity metrics."""
        result = engine.team_capacity_overview()
        assert isinstance(result, dict)
        assert "total_people" in result
        assert "total_active_tasks" in result
        assert "distribution" in result


class TestProjectQueries:
    """Test project queries."""

    @pytest.fixture
    def sample_project_id(self, engine):
        """Get a project ID that has tasks."""
        projects = engine.projects_by_health(min_tasks=1)
        return projects[0]["project_id"] if projects else None

    def test_project_operational_state_returns_dict(self, engine, sample_project_id):
        """project_operational_state returns dict for valid project."""
        if not sample_project_id:
            pytest.skip("No projects with tasks")

        result = engine.project_operational_state(sample_project_id)
        assert isinstance(result, dict)
        assert result["project_id"] == sample_project_id

    def test_project_operational_state_nonexistent(self, engine):
        """project_operational_state returns None for nonexistent project."""
        result = engine.project_operational_state("nonexistent-id-12345")
        assert result is None

    def test_projects_by_health_returns_list(self, engine):
        """projects_by_health returns sorted list."""
        result = engine.projects_by_health(min_tasks=1)
        assert isinstance(result, list)

    def test_projects_by_health_has_score(self, engine):
        """Projects have computed health_score."""
        result = engine.projects_by_health(min_tasks=1)
        if result:
            assert "health_score" in result[0]


class TestCommunicationQueries:
    """Test communication queries."""

    @pytest.fixture
    def client_with_comms(self, engine):
        """Get a client ID that has communications."""
        # Find a client with entity_links
        clients = engine.client_portfolio_overview()
        for c in clients:
            if c.get("entity_links_count", 0) > 0:
                return c["client_id"]
        return None

    def test_client_communication_summary_returns_dict(self, engine, client_with_comms):
        """client_communication_summary returns metrics dict."""
        if not client_with_comms:
            pytest.skip("No clients with communications")

        result = engine.client_communication_summary(client_with_comms)
        assert isinstance(result, dict)
        assert "total_communications" in result
        assert "by_type" in result
        assert "recent" in result


class TestFinancialQueries:
    """Test financial queries."""

    def test_invoice_aging_report_returns_dict(self, engine):
        """invoice_aging_report returns aging metrics."""
        result = engine.invoice_aging_report()
        assert isinstance(result, dict)
        assert "total_outstanding" in result
        assert "by_bucket" in result
        assert "clients_with_overdue" in result

    def test_invoice_aging_by_bucket_is_dict(self, engine):
        """by_bucket is a dict mapping bucket to amount."""
        result = engine.invoice_aging_report()
        assert isinstance(result["by_bucket"], dict)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_result_handling(self, engine):
        """Queries handle empty results gracefully."""
        # Query for nonexistent data
        result = engine.client_task_summary("nonexistent-client")
        assert result["total_tasks"] == 0

    def test_no_sql_injection(self, engine):
        """Queries are parameterized (no SQL injection)."""
        # Attempt SQL injection via client_id
        malicious_id = "'; DROP TABLE clients; --"
        result = engine.client_deep_profile(malicious_id)
        # Should return None, not crash or execute injection
        assert result is None

        # Verify clients table still exists
        clients = engine.client_portfolio_overview()
        assert len(clients) > 0


class TestTemporalQueries:
    """Tests for time-windowed queries."""

    def test_tasks_in_period_returns_list(self, engine):
        """tasks_in_period returns list of tasks."""
        result = engine.tasks_in_period(since="2024-01-01", until="2025-01-01")
        assert isinstance(result, list)

    def test_tasks_in_period_filters_by_date(self, engine):
        """tasks_in_period correctly filters by date range."""
        all_tasks = engine.tasks_in_period()
        recent_tasks = engine.tasks_in_period(since="2025-01-01")

        # Recent should be subset of all
        assert len(recent_tasks) <= len(all_tasks)

    def test_invoices_in_period_returns_list(self, engine):
        """invoices_in_period returns list."""
        result = engine.invoices_in_period(since="2024-01-01")
        assert isinstance(result, list)

    def test_communications_in_period_returns_list(self, engine):
        """communications_in_period returns list."""
        result = engine.communications_in_period(since="2024-01-01")
        assert isinstance(result, list)


class TestPeriodComparison:
    """Tests for period comparison functions."""

    @pytest.fixture
    def sample_client_id(self, engine):
        """Get a client ID that has data."""
        clients = engine.client_portfolio_overview()
        for c in clients:
            if c["total_tasks"] > 5:
                return c["client_id"]
        return clients[0]["client_id"] if clients else None

    def test_client_metrics_in_period_returns_dict(self, engine, sample_client_id):
        """client_metrics_in_period returns metrics dict."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.client_metrics_in_period(
            sample_client_id,
            "2024-01-01",
            "2025-01-01"
        )
        assert isinstance(result, dict)
        assert "tasks_created" in result
        assert "invoices_issued" in result

    def test_compare_client_periods_returns_comparison(self, engine, sample_client_id):
        """compare_client_periods returns period comparison."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.compare_client_periods(
            sample_client_id,
            ("2024-01-01", "2024-06-30"),
            ("2024-07-01", "2024-12-31")
        )

        assert "period_a" in result
        assert "period_b" in result
        assert "deltas" in result
        assert "pct_changes" in result

    def test_compare_client_periods_deltas_are_correct(self, engine, sample_client_id):
        """Deltas are mathematically correct (b - a)."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.compare_client_periods(
            sample_client_id,
            ("2024-01-01", "2024-06-30"),
            ("2024-07-01", "2024-12-31")
        )

        a_tasks = result["period_a"]["metrics"]["tasks_created"]
        b_tasks = result["period_b"]["metrics"]["tasks_created"]

        assert result["deltas"]["tasks_created"] == b_tasks - a_tasks


class TestTrajectoryFunctions:
    """Tests for trajectory analysis functions."""

    @pytest.fixture
    def sample_client_id(self, engine):
        """Get a client ID that has data."""
        clients = engine.client_portfolio_overview()
        for c in clients:
            if c["total_tasks"] > 5:
                return c["client_id"]
        return clients[0]["client_id"] if clients else None

    def test_client_trajectory_returns_windows(self, engine, sample_client_id):
        """client_trajectory returns expected number of windows."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.client_trajectory(
            sample_client_id,
            window_size_days=30,
            num_windows=3
        )

        assert "windows" in result
        assert len(result["windows"]) == 3
        assert "trends" in result

    def test_client_trajectory_has_trends(self, engine, sample_client_id):
        """Trajectory includes trend analysis."""
        if not sample_client_id:
            pytest.skip("No clients with data")

        result = engine.client_trajectory(sample_client_id)

        assert "trends" in result
        for key in ["tasks_created", "communications_count"]:
            if key in result["trends"]:
                assert "direction" in result["trends"][key]
                assert result["trends"][key]["direction"] in ("increasing", "stable", "declining")

    def test_portfolio_trajectory_returns_list(self, engine):
        """portfolio_trajectory returns list of client trajectories."""
        result = engine.portfolio_trajectory(
            window_size_days=30,
            num_windows=3,
            min_activity=10
        )

        assert isinstance(result, list)
        if result:
            assert "client_name" in result[0]
            assert "trends" in result[0]


class TestTrendComputation:
    """Tests for _compute_trend function."""

    def test_compute_trend_increasing(self):
        """Steadily increasing values → increasing trend."""
        from lib.query_engine import _compute_trend

        values = [10, 20, 30, 40, 50]
        result = _compute_trend(values)

        assert result["direction"] == "increasing"
        assert result["magnitude_pct"] > 0

    def test_compute_trend_declining(self):
        """Steadily declining values → declining trend."""
        from lib.query_engine import _compute_trend

        values = [50, 40, 30, 20, 10]
        result = _compute_trend(values)

        assert result["direction"] == "declining"
        assert result["magnitude_pct"] < 0

    def test_compute_trend_stable(self):
        """Flat values → stable trend."""
        from lib.query_engine import _compute_trend

        values = [100, 102, 98, 101, 99]
        result = _compute_trend(values)

        assert result["direction"] == "stable"

    def test_compute_trend_empty_list(self):
        """Empty list returns stable with low confidence."""
        from lib.query_engine import _compute_trend

        result = _compute_trend([])

        assert result["direction"] == "stable"
        assert result["confidence"] == "low"

    def test_compute_trend_single_value(self):
        """Single value returns stable with low confidence."""
        from lib.query_engine import _compute_trend

        result = _compute_trend([42])

        assert result["direction"] == "stable"
        assert result["confidence"] == "low"

    def test_compute_trend_confidence_high(self):
        """Data with mostly non-zero values → high confidence."""
        from lib.query_engine import _compute_trend

        values = [10, 20, 30, 40, 50]
        result = _compute_trend(values)

        assert result["confidence"] == "high"

    def test_compute_trend_confidence_low(self):
        """Data with many zeros → low confidence."""
        from lib.query_engine import _compute_trend

        values = [0, 0, 0, 0, 10]
        result = _compute_trend(values)

        assert result["confidence"] == "low"
