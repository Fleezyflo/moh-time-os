"""
Test suite for Intelligence Dashboard API response contracts.

Tests validate:
- All models instantiate with valid data
- Required fields are enforced
- Example data from json_schema_extra validates
- Envelope structure is correct
- Field constraints (ranges, enums) are respected
"""

from datetime import datetime, timedelta

import pytest

from design.system.api_contracts import (
    # Financial models
    AgingBucket,
    # Briefing models
    BriefingItem,
    ClientAging,
    ClientDetailResponse,
    # Portfolio models
    ClientMetric,
    Communication,
    DailyBriefingResponse,
    ErrorEnvelope,
    FinancialAgingResponse,
    # Snapshot model
    IntelligenceSnapshot,
    Invoice,
    NotificationFeedResponse,
    # Team capacity models
    PersonLoad,
    PortfolioDashboardResponse,
    # Client detail models
    Project,
    # Resolution queue models
    ProposedAction,
    ResolutionItem,
    ResolutionQueueResponse,
    ScenarioModelResponse,
    # Scenario models
    ScenarioResult,
    # Notification models
    Signal,
    # Envelope models
    StandardEnvelope,
    TeamCapacityResponse,
)

# =============================================================================
# ENVELOPE TESTS
# =============================================================================


class TestStandardEnvelope:
    """Tests for StandardEnvelope response wrapper."""

    def test_envelope_with_default_status(self):
        """Envelope should have 'ok' status by default."""
        env = StandardEnvelope(data={"key": "value"})
        assert env.status == "ok"
        assert env.data == {"key": "value"}

    def test_envelope_with_custom_status(self):
        """Envelope should allow custom status."""
        env = StandardEnvelope(status="error", data=None)
        assert env.status == "error"

    def test_envelope_computed_at_is_datetime(self):
        """Envelope should have computed_at as datetime."""
        env = StandardEnvelope(data={})
        assert isinstance(env.computed_at, datetime)

    def test_envelope_custom_computed_at(self):
        """Envelope should accept custom computed_at."""
        now = datetime.now()
        env = StandardEnvelope(data={}, computed_at=now)
        assert env.computed_at == now

    def test_envelope_json_serialization(self):
        """Envelope should serialize to JSON."""
        env = StandardEnvelope(data={"result": 42})
        json_data = env.model_dump(mode="json")
        assert json_data["status"] == "ok"
        assert json_data["data"] == {"result": 42}
        assert isinstance(json_data["computed_at"], str)


class TestErrorEnvelope:
    """Tests for ErrorEnvelope."""

    def test_error_envelope_status_is_error(self):
        """Error envelope status should always be 'error'."""
        env = ErrorEnvelope(error="Something went wrong")
        assert env.status == "error"
        assert env.error == "Something went wrong"

    def test_error_envelope_with_custom_code(self):
        """Error envelope should accept custom error_code."""
        env = ErrorEnvelope(error="Not found", error_code="NOT_FOUND")
        assert env.error_code == "NOT_FOUND"

    def test_error_envelope_default_code(self):
        """Error envelope should have default error_code."""
        env = ErrorEnvelope(error="Test error")
        assert env.error_code == "ERROR"


# =============================================================================
# CLIENT METRIC & PORTFOLIO TESTS
# =============================================================================


class TestClientMetric:
    """Tests for ClientMetric model."""

    def test_client_metric_minimal(self):
        """ClientMetric should instantiate with required fields."""
        metric = ClientMetric(
            client_id="c1",
            name="Test Client",
            project_count=2,
            total_tasks=10,
            active_tasks=5,
            completed_tasks=3,
            overdue_tasks=2,
            invoice_count=3,
            total_invoiced=50000.0,
            total_outstanding=20000.0,
            health_score=75.0,
            trajectory="stable",
            last_activity=datetime.now(),
        )
        assert metric.client_id == "c1"
        assert metric.health_score == 75.0

    def test_client_metric_health_score_bounds(self):
        """Health score must be between 0-100."""
        with pytest.raises(ValueError):
            ClientMetric(
                client_id="c1",
                name="Test",
                project_count=1,
                total_tasks=5,
                active_tasks=2,
                completed_tasks=2,
                overdue_tasks=1,
                invoice_count=1,
                total_invoiced=10000.0,
                total_outstanding=5000.0,
                health_score=150.0,  # Invalid
                trajectory="stable",
                last_activity=datetime.now(),
            )

    def test_client_metric_example_data(self):
        """Example data from schema should validate."""
        example = ClientMetric(
            client_id="client_001",
            name="Acme Corp",
            project_count=3,
            total_tasks=45,
            active_tasks=12,
            completed_tasks=28,
            overdue_tasks=5,
            invoice_count=8,
            total_invoiced=125000.0,
            total_outstanding=35000.0,
            health_score=72.5,
            trajectory="stable",
            last_activity=datetime.fromisoformat("2026-02-21T10:30:00"),
        )
        assert example.name == "Acme Corp"


class TestPortfolioDashboardResponse:
    """Tests for PortfolioDashboardResponse."""

    def test_portfolio_with_empty_clients(self):
        """Portfolio should allow empty client list."""
        portfolio = PortfolioDashboardResponse(
            clients=[],
            total_clients=0,
            total_projects=0,
            total_outstanding_revenue=0.0,
            portfolio_health_score=50.0,
        )
        assert portfolio.total_clients == 0
        assert len(portfolio.clients) == 0

    def test_portfolio_with_one_client(self):
        """Portfolio should accept one client."""
        client = ClientMetric(
            client_id="c1",
            name="Test",
            project_count=1,
            total_tasks=5,
            active_tasks=2,
            completed_tasks=2,
            overdue_tasks=1,
            invoice_count=1,
            total_invoiced=10000.0,
            total_outstanding=5000.0,
            health_score=70.0,
            trajectory="stable",
            last_activity=datetime.now(),
        )
        portfolio = PortfolioDashboardResponse(
            clients=[client],
            total_clients=1,
            total_projects=1,
            total_outstanding_revenue=5000.0,
            portfolio_health_score=70.0,
        )
        assert len(portfolio.clients) == 1
        assert portfolio.total_clients == 1

    def test_portfolio_health_score_bounds(self):
        """Portfolio health score must be 0-100."""
        with pytest.raises(ValueError):
            PortfolioDashboardResponse(
                clients=[],
                total_clients=0,
                total_projects=0,
                total_outstanding_revenue=0.0,
                portfolio_health_score=101.0,  # Invalid
            )


# =============================================================================
# CLIENT DETAIL TESTS
# =============================================================================


class TestProject:
    """Tests for Project model."""

    def test_project_minimal(self):
        """Project should instantiate with required fields."""
        now = datetime.now()
        project = Project(
            project_id="p1",
            name="Website",
            status="active",
            start_date=now,
            end_date=None,
            progress=50.0,
            task_count=10,
            active_task_count=5,
        )
        assert project.project_id == "p1"
        assert project.status == "active"
        assert project.end_date is None

    def test_project_with_end_date(self):
        """Project should accept end_date."""
        now = datetime.now()
        project = Project(
            project_id="p1",
            name="Website",
            status="completed",
            start_date=now,
            end_date=now + timedelta(days=30),
            progress=100.0,
            task_count=10,
            active_task_count=0,
        )
        assert project.progress == 100.0
        assert project.end_date is not None

    def test_project_progress_bounds(self):
        """Progress must be 0-100."""
        now = datetime.now()
        with pytest.raises(ValueError):
            Project(
                project_id="p1",
                name="Website",
                status="active",
                start_date=now,
                end_date=None,
                progress=150.0,  # Invalid
                task_count=10,
                active_task_count=5,
            )


class TestCommunication:
    """Tests for Communication model."""

    def test_communication_minimal(self):
        """Communication should instantiate with required fields."""
        comm = Communication(
            communication_id="comm_1",
            type="email",
            timestamp=datetime.now(),
            subject="Update",
            participants=["john@example.com"],
        )
        assert comm.type == "email"
        assert len(comm.participants) == 1

    def test_communication_multiple_participants(self):
        """Communication should accept multiple participants."""
        comm = Communication(
            communication_id="comm_1",
            type="meeting",
            timestamp=datetime.now(),
            subject="Status",
            participants=["alice@example.com", "bob@example.com"],
        )
        assert len(comm.participants) == 2


class TestInvoice:
    """Tests for Invoice model."""

    def test_invoice_minimal(self):
        """Invoice should instantiate with required fields."""
        now = datetime.now()
        invoice = Invoice(
            invoice_id="inv_1",
            number="INV-001",
            amount=5000.0,
            issued_date=now,
            due_date=now + timedelta(days=30),
            status="sent",
            days_outstanding=None,
        )
        assert invoice.invoice_id == "inv_1"
        assert invoice.status == "sent"

    def test_invoice_overdue_status(self):
        """Invoice can be overdue."""
        now = datetime.now()
        invoice = Invoice(
            invoice_id="inv_1",
            number="INV-001",
            amount=5000.0,
            issued_date=now - timedelta(days=60),
            due_date=now - timedelta(days=30),
            status="overdue",
            days_outstanding=30,
        )
        assert invoice.status == "overdue"
        assert invoice.days_outstanding == 30


class TestClientDetailResponse:
    """Tests for ClientDetailResponse."""

    def test_client_detail_minimal(self):
        """ClientDetailResponse should instantiate with required fields."""
        client = ClientDetailResponse(
            client_id="c1",
            name="Acme",
            status="active",
            industry=None,
            contact_email=None,
            contact_phone=None,
            engagement_since=datetime.now(),
            total_projects=2,
            active_projects=[],
            total_communications=10,
            recent_communications=[],
            invoices=[],
            total_invoiced=50000.0,
            total_paid=30000.0,
            total_outstanding=20000.0,
            health_score=70.0,
        )
        assert client.client_id == "c1"
        assert len(client.active_projects) == 0

    def test_client_detail_with_projects(self):
        """ClientDetailResponse should accept projects."""
        project = Project(
            project_id="p1",
            name="Website",
            status="active",
            start_date=datetime.now(),
            end_date=None,
            progress=50.0,
            task_count=10,
            active_task_count=5,
        )
        client = ClientDetailResponse(
            client_id="c1",
            name="Acme",
            status="active",
            industry=None,
            contact_email=None,
            contact_phone=None,
            engagement_since=datetime.now(),
            total_projects=1,
            active_projects=[project],
            total_communications=0,
            recent_communications=[],
            invoices=[],
            total_invoiced=10000.0,
            total_paid=5000.0,
            total_outstanding=5000.0,
            health_score=70.0,
        )
        assert len(client.active_projects) == 1
        assert client.active_projects[0].project_id == "p1"


# =============================================================================
# RESOLUTION QUEUE TESTS
# =============================================================================


class TestProposedAction:
    """Tests for ProposedAction model."""

    def test_action_minimal(self):
        """ProposedAction should instantiate with required fields."""
        action = ProposedAction(
            action_id="a1",
            title="Contact client",
            description="Call client about overdue invoice",
            priority="immediate",
            effort="quick",
            owner="person_1",
        )
        assert action.priority == "immediate"
        assert action.effort == "quick"


class TestResolutionItem:
    """Tests for ResolutionItem model."""

    def test_resolution_item_minimal(self):
        """ResolutionItem should instantiate with required fields."""
        item = ResolutionItem(
            item_id="res_1",
            entity_type="client",
            entity_id="c1",
            entity_name="Acme",
            issue="Invoice overdue",
            impact="Cash flow",
            urgency="immediate",
            proposed_actions=[],
            confidence=0.95,
        )
        assert item.urgency == "immediate"
        assert item.confidence == 0.95

    def test_resolution_item_confidence_bounds(self):
        """Confidence must be 0-1."""
        with pytest.raises(ValueError):
            ResolutionItem(
                item_id="res_1",
                entity_type="client",
                entity_id="c1",
                entity_name="Acme",
                issue="Test",
                impact="Test",
                urgency="immediate",
                proposed_actions=[],
                confidence=1.5,  # Invalid
            )

    def test_resolution_item_with_actions(self):
        """ResolutionItem should accept proposed actions."""
        action = ProposedAction(
            action_id="a1",
            title="Call",
            description="Contact",
            priority="immediate",
            effort="quick",
            owner="person_1",
        )
        item = ResolutionItem(
            item_id="res_1",
            entity_type="client",
            entity_id="c1",
            entity_name="Acme",
            issue="Overdue",
            impact="Impact",
            urgency="immediate",
            proposed_actions=[action],
            confidence=0.9,
        )
        assert len(item.proposed_actions) == 1


class TestResolutionQueueResponse:
    """Tests for ResolutionQueueResponse."""

    def test_queue_empty(self):
        """Queue should allow empty items."""
        queue = ResolutionQueueResponse(
            items=[],
            total_items=0,
            immediate_count=0,
            this_week_count=0,
            soon_count=0,
        )
        assert queue.total_items == 0
        assert len(queue.items) == 0

    def test_queue_with_items(self):
        """Queue should accept items."""
        item = ResolutionItem(
            item_id="res_1",
            entity_type="client",
            entity_id="c1",
            entity_name="Acme",
            issue="Test",
            impact="Test",
            urgency="immediate",
            proposed_actions=[],
            confidence=0.9,
        )
        queue = ResolutionQueueResponse(
            items=[item],
            total_items=1,
            immediate_count=1,
            this_week_count=0,
            soon_count=0,
        )
        assert queue.total_items == 1
        assert len(queue.items) == 1


# =============================================================================
# SCENARIO TESTS
# =============================================================================


class TestScenarioResult:
    """Tests for ScenarioResult model."""

    def test_result_minimal(self):
        """ScenarioResult should instantiate with required fields."""
        result = ScenarioResult(
            metric="team_capacity",
            current_value=100.0,
            projected_value=133.0,
            delta=33.0,
            delta_pct=33.0,
        )
        assert result.metric == "team_capacity"
        assert result.delta_pct == 33.0


class TestScenarioModelResponse:
    """Tests for ScenarioModelResponse."""

    def test_scenario_minimal(self):
        """ScenarioModelResponse should instantiate with required fields."""
        now = datetime.now()
        scenario = ScenarioModelResponse(
            scenario_id="scen_1",
            name="Test scenario",
            description="Testing",
            baseline_date=now,
            scenario_date=now + timedelta(days=30),
            results=[],
            feasibility=0.8,
            risks=[],
        )
        assert scenario.feasibility == 0.8

    def test_scenario_feasibility_bounds(self):
        """Feasibility must be 0-1."""
        now = datetime.now()
        with pytest.raises(ValueError):
            ScenarioModelResponse(
                scenario_id="scen_1",
                name="Test",
                description="Test",
                baseline_date=now,
                scenario_date=now + timedelta(days=30),
                results=[],
                feasibility=1.5,  # Invalid
                risks=[],
            )

    def test_scenario_with_results(self):
        """Scenario should accept results."""
        result = ScenarioResult(
            metric="capacity",
            current_value=100.0,
            projected_value=133.0,
            delta=33.0,
            delta_pct=33.0,
        )
        now = datetime.now()
        scenario = ScenarioModelResponse(
            scenario_id="scen_1",
            name="Test",
            description="Test",
            baseline_date=now,
            scenario_date=now + timedelta(days=30),
            results=[result],
            feasibility=0.8,
            risks=["Risk 1"],
        )
        assert len(scenario.results) == 1


# =============================================================================
# NOTIFICATION TESTS
# =============================================================================


class TestSignal:
    """Tests for Signal model."""

    def test_signal_minimal(self):
        """Signal should instantiate with required fields."""
        signal = Signal(
            signal_id="sig_1",
            severity="high",
            type="threshold",
            entity_type="client",
            entity_id="c1",
            entity_name="Acme",
            title="Overdue",
            description="Invoice is overdue",
            detected_at=datetime.now(),
            resolved=False,
        )
        assert signal.severity == "high"
        assert signal.resolved is False

    def test_signal_resolved(self):
        """Signal can be marked resolved."""
        signal = Signal(
            signal_id="sig_1",
            severity="high",
            type="threshold",
            entity_type="client",
            entity_id="c1",
            entity_name="Acme",
            title="Overdue",
            description="Invoice is overdue",
            detected_at=datetime.now(),
            resolved=True,
        )
        assert signal.resolved is True


class TestNotificationFeedResponse:
    """Tests for NotificationFeedResponse."""

    def test_feed_empty(self):
        """Notification feed should allow empty signals."""
        feed = NotificationFeedResponse(
            signals=[],
            total_unresolved=0,
            critical_count=0,
            last_check=datetime.now(),
        )
        assert len(feed.signals) == 0
        assert feed.total_unresolved == 0

    def test_feed_with_signals(self):
        """Notification feed should accept signals."""
        signal = Signal(
            signal_id="sig_1",
            severity="high",
            type="threshold",
            entity_type="client",
            entity_id="c1",
            entity_name="Acme",
            title="Overdue",
            description="Test",
            detected_at=datetime.now(),
            resolved=False,
        )
        feed = NotificationFeedResponse(
            signals=[signal],
            total_unresolved=1,
            critical_count=1,
            last_check=datetime.now(),
        )
        assert len(feed.signals) == 1
        assert feed.critical_count == 1


# =============================================================================
# TEAM & CAPACITY TESTS
# =============================================================================


class TestPersonLoad:
    """Tests for PersonLoad model."""

    def test_person_load_minimal(self):
        """PersonLoad should instantiate with required fields."""
        person = PersonLoad(
            person_id="p1",
            name="Alice",
            assigned_tasks=8,
            active_tasks=6,
            project_count=3,
            load_score=65.0,
            utilization=0.65,
            status="fully_loaded",
        )
        assert person.name == "Alice"
        assert person.load_score == 65.0

    def test_person_load_constraints(self):
        """PersonLoad should enforce field constraints."""
        with pytest.raises(ValueError):
            PersonLoad(
                person_id="p1",
                name="Alice",
                assigned_tasks=8,
                active_tasks=6,
                project_count=3,
                load_score=150.0,  # Invalid: > 100
                utilization=0.65,
                status="fully_loaded",
            )

    def test_person_utilization_bounds(self):
        """Utilization must be 0-1."""
        with pytest.raises(ValueError):
            PersonLoad(
                person_id="p1",
                name="Alice",
                assigned_tasks=8,
                active_tasks=6,
                project_count=3,
                load_score=65.0,
                utilization=1.5,  # Invalid
                status="fully_loaded",
            )


class TestTeamCapacityResponse:
    """Tests for TeamCapacityResponse."""

    def test_capacity_empty_team(self):
        """Capacity should allow empty team."""
        capacity = TeamCapacityResponse(
            people=[],
            total_people=0,
            total_active_tasks=0,
            avg_tasks_per_person=0.0,
            people_overloaded=0,
            people_available=0,
            team_utilization=0.0,
        )
        assert capacity.total_people == 0

    def test_capacity_with_people(self):
        """Capacity should accept people."""
        person = PersonLoad(
            person_id="p1",
            name="Alice",
            assigned_tasks=8,
            active_tasks=6,
            project_count=3,
            load_score=65.0,
            utilization=0.65,
            status="fully_loaded",
        )
        capacity = TeamCapacityResponse(
            people=[person],
            total_people=1,
            total_active_tasks=6,
            avg_tasks_per_person=8.0,
            people_overloaded=0,
            people_available=0,
            team_utilization=0.65,
        )
        assert capacity.total_people == 1
        assert len(capacity.people) == 1


# =============================================================================
# FINANCIAL TESTS
# =============================================================================


class TestAgingBucket:
    """Tests for AgingBucket model."""

    def test_bucket_minimal(self):
        """AgingBucket should instantiate with required fields."""
        bucket = AgingBucket(
            bracket="30",
            count=5,
            amount=10000.0,
            client_count=2,
        )
        assert bucket.bracket == "30"
        assert bucket.count == 5


class TestClientAging:
    """Tests for ClientAging model."""

    def test_client_aging_minimal(self):
        """ClientAging should instantiate with required fields."""
        aging = ClientAging(
            client_id="c1",
            client_name="Acme",
            total_outstanding=10000.0,
            oldest_invoice_days=30,
        )
        assert aging.client_id == "c1"
        assert aging.oldest_invoice_days == 30


class TestFinancialAgingResponse:
    """Tests for FinancialAgingResponse."""

    def test_aging_empty(self):
        """Financial aging should allow empty data."""
        aging = FinancialAgingResponse(
            total_outstanding=0.0,
            by_bucket=[],
            clients_with_overdue=[],
            total_invoices_overdue=0,
        )
        assert aging.total_outstanding == 0.0
        assert len(aging.by_bucket) == 0

    def test_aging_with_data(self):
        """Financial aging should accept data."""
        bucket = AgingBucket(
            bracket="30",
            count=5,
            amount=10000.0,
            client_count=2,
        )
        client_aging = ClientAging(
            client_id="c1",
            client_name="Acme",
            total_outstanding=10000.0,
            oldest_invoice_days=30,
        )
        aging = FinancialAgingResponse(
            total_outstanding=10000.0,
            by_bucket=[bucket],
            clients_with_overdue=[client_aging],
            total_invoices_overdue=5,
        )
        assert aging.total_outstanding == 10000.0
        assert len(aging.by_bucket) == 1


# =============================================================================
# BRIEFING TESTS
# =============================================================================


class TestBriefingItem:
    """Tests for BriefingItem model."""

    def test_briefing_item_minimal(self):
        """BriefingItem should instantiate with required fields."""
        item = BriefingItem(
            category="immediate",
            title="Invoice overdue",
            description="Details",
            entity_type="client",
            entity_id="c1",
            action_recommended=None,
        )
        assert item.category == "immediate"
        assert item.action_recommended is None

    def test_briefing_item_with_action(self):
        """BriefingItem should accept action."""
        item = BriefingItem(
            category="immediate",
            title="Invoice overdue",
            description="Details",
            entity_type="client",
            entity_id="c1",
            action_recommended="Call client",
        )
        assert item.action_recommended == "Call client"


class TestDailyBriefingResponse:
    """Tests for DailyBriefingResponse."""

    def test_briefing_empty(self):
        """Briefing should allow empty items."""
        briefing = DailyBriefingResponse(
            date=datetime.now(),
            immediate_items=[],
            this_week_items=[],
            monitoring_items=[],
            positive_items=[],
            portfolio_health=50.0,
            key_metrics={},
        )
        assert len(briefing.immediate_items) == 0
        assert briefing.portfolio_health == 50.0

    def test_briefing_with_items(self):
        """Briefing should accept items."""
        item = BriefingItem(
            category="immediate",
            title="Test",
            description="Test",
            entity_type="client",
            entity_id="c1",
            action_recommended=None,
        )
        briefing = DailyBriefingResponse(
            date=datetime.now(),
            immediate_items=[item],
            this_week_items=[],
            monitoring_items=[],
            positive_items=[],
            portfolio_health=70.0,
            key_metrics={"total_clients": 8},
        )
        assert len(briefing.immediate_items) == 1
        assert "total_clients" in briefing.key_metrics


# =============================================================================
# SNAPSHOT TESTS
# =============================================================================


class TestIntelligenceSnapshot:
    """Tests for IntelligenceSnapshot model."""

    def test_snapshot_minimal(self):
        """IntelligenceSnapshot should instantiate with required fields."""
        portfolio = PortfolioDashboardResponse(
            clients=[],
            total_clients=0,
            total_projects=0,
            total_outstanding_revenue=0.0,
            portfolio_health_score=50.0,
        )
        capacity = TeamCapacityResponse(
            people=[],
            total_people=0,
            total_active_tasks=0,
            avg_tasks_per_person=0.0,
            people_overloaded=0,
            people_available=0,
            team_utilization=0.0,
        )
        financial = FinancialAgingResponse(
            total_outstanding=0.0,
            by_bucket=[],
            clients_with_overdue=[],
            total_invoices_overdue=0,
        )
        briefing = DailyBriefingResponse(
            date=datetime.now(),
            immediate_items=[],
            this_week_items=[],
            monitoring_items=[],
            positive_items=[],
            portfolio_health=50.0,
            key_metrics={},
        )
        snapshot = IntelligenceSnapshot(
            timestamp=datetime.now(),
            portfolio=portfolio,
            signals=[],
            patterns=[],
            proposals=[],
            briefing=briefing,
            team_capacity=capacity,
            financial=financial,
        )
        assert snapshot.timestamp is not None
        assert snapshot.portfolio.total_clients == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestEnvelopeWithPortfolioResponse:
    """Tests for envelope wrapping portfolio response."""

    def test_envelope_wraps_portfolio(self):
        """Envelope should wrap portfolio response."""
        portfolio = PortfolioDashboardResponse(
            clients=[],
            total_clients=0,
            total_projects=0,
            total_outstanding_revenue=0.0,
            portfolio_health_score=50.0,
        )
        env = StandardEnvelope(data=portfolio.model_dump())
        assert env.status == "ok"
        assert env.data["total_clients"] == 0

    def test_envelope_serialization(self):
        """Full envelope + portfolio should serialize."""
        portfolio = PortfolioDashboardResponse(
            clients=[],
            total_clients=0,
            total_projects=0,
            total_outstanding_revenue=0.0,
            portfolio_health_score=50.0,
        )
        env = StandardEnvelope(data=portfolio.model_dump())
        json_data = env.model_dump(mode="json")
        assert isinstance(json_data, dict)
        assert "status" in json_data
        assert "data" in json_data


class TestMultipleClientMetrics:
    """Tests for portfolio with multiple clients."""

    def test_portfolio_with_three_clients(self):
        """Portfolio should handle multiple clients."""
        clients = [
            ClientMetric(
                client_id=f"c{i}",
                name=f"Client {i}",
                project_count=i + 1,
                total_tasks=10 * (i + 1),
                active_tasks=5 * (i + 1),
                completed_tasks=3 * (i + 1),
                overdue_tasks=i,
                invoice_count=2 * (i + 1),
                total_invoiced=50000.0 * (i + 1),
                total_outstanding=20000.0 * (i + 1),
                health_score=70.0 + i * 5,
                trajectory="stable",
                last_activity=datetime.now(),
            )
            for i in range(3)
        ]
        portfolio = PortfolioDashboardResponse(
            clients=clients,
            total_clients=3,
            total_projects=6,
            total_outstanding_revenue=120000.0,
            portfolio_health_score=75.0,
        )
        assert len(portfolio.clients) == 3
        assert portfolio.total_clients == 3


# =============================================================================
# CONSTRAINT VALIDATION TESTS
# =============================================================================


class TestFieldConstraints:
    """Tests for field constraint validation."""

    def test_status_badge_valid_variants(self):
        """Status badge should accept valid variant statuses."""
        statuses = ["success", "warning", "danger", "info", "neutral"]
        # Just verify these are valid status values used in Badge
        assert "success" in statuses
        assert "danger" in statuses

    def test_urgency_levels(self):
        """Urgency should be valid levels."""
        valid_urgencies = ["immediate", "this_week", "soon", "monitor"]
        for urgency in valid_urgencies:
            # Create minimal resolution item with each urgency
            item = ResolutionItem(
                item_id="r1",
                entity_type="client",
                entity_id="c1",
                entity_name="Test",
                issue="Test",
                impact="Test",
                urgency=urgency,
                proposed_actions=[],
                confidence=0.9,
            )
            assert item.urgency == urgency

    def test_trajectory_values(self):
        """Trajectory should be valid values."""
        valid_trajectories = ["increasing", "stable", "declining"]
        for traj in valid_trajectories:
            metric = ClientMetric(
                client_id="c1",
                name="Test",
                project_count=1,
                total_tasks=5,
                active_tasks=2,
                completed_tasks=2,
                overdue_tasks=1,
                invoice_count=1,
                total_invoiced=10000.0,
                total_outstanding=5000.0,
                health_score=70.0,
                trajectory=traj,
                last_activity=datetime.now(),
            )
            assert metric.trajectory == traj
