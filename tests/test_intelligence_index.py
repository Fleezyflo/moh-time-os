"""
Tests for IntelligenceIndex — dashboard aggregation service.

Brief 12 (IX), Task IX-2.1
"""

import pytest

from lib.intelligence.intelligence_index import (
    ClientIntelligenceCard,
    CommandCenterView,
    DashboardIndex,
    FinancialOverview,
    IntelligenceIndex,
    ResolutionQueueItem,
    TeamCapacityCard,
    classify_attention_level,
    classify_capacity_status,
    classify_health,
)


class TestClassifyCapacityStatus:
    def test_overloaded(self):
        assert classify_capacity_status(115) == "overloaded"

    def test_busy(self):
        assert classify_capacity_status(90) == "busy"

    def test_normal(self):
        assert classify_capacity_status(60) == "normal"

    def test_underutilized(self):
        assert classify_capacity_status(30) == "underutilized"


class TestClassifyHealth:
    def test_excellent(self):
        assert classify_health(85) == "excellent"

    def test_good(self):
        assert classify_health(70) == "good"

    def test_fair(self):
        assert classify_health(55) == "fair"

    def test_poor(self):
        assert classify_health(40) == "poor"

    def test_critical(self):
        assert classify_health(20) == "critical"


class TestClassifyAttentionLevel:
    def test_urgent(self):
        assert classify_attention_level(25, 2, 5) == "urgent"

    def test_high(self):
        assert classify_attention_level(45, 1, 5) == "high"

    def test_elevated(self):
        assert classify_attention_level(60, 0, 15) == "elevated"

    def test_normal(self):
        assert classify_attention_level(80, 0, 5) == "normal"


@pytest.fixture
def index():
    return IntelligenceIndex()


@pytest.fixture
def sample_clients():
    return [
        {
            "entity_id": "c1",
            "entity_name": "Acme Corp",
            "health_score": 85,
            "trend_direction": "growing",
            "monthly_revenue": 30000,
            "monthly_cost": 15000,
            "revenue_tier": "platinum",
            "active_signals": 0,
            "critical_signals": 0,
            "days_since_review": 3,
        },
        {
            "entity_id": "c2",
            "entity_name": "Beta Inc",
            "health_score": 35,
            "trend_direction": "declining",
            "monthly_revenue": 10000,
            "monthly_cost": 7000,
            "revenue_tier": "silver",
            "active_signals": 3,
            "critical_signals": 1,
            "days_since_review": 25,
            "top_risk": "payment delays",
        },
        {
            "entity_id": "c3",
            "entity_name": "Gamma LLC",
            "health_score": 60,
            "trend_direction": "stable",
            "monthly_revenue": 20000,
            "monthly_cost": 12000,
            "revenue_tier": "gold",
            "active_signals": 1,
            "critical_signals": 0,
            "days_since_review": 10,
        },
    ]


class TestCommandCenter:
    def test_basic(self, index, sample_clients):
        signals = [
            {"severity": "CRITICAL"},
            {"severity": "WARNING"},
            {"severity": "WARNING"},
        ]
        cc = index.build_command_center(
            sample_clients,
            projects=[{"id": "p1"}, {"id": "p2"}],
            signals=signals,
            revenue_data={"total_monthly": 60000, "trend": "growing"},
            capacity_data={"avg_utilization": 72.5},
        )
        assert cc.total_clients == 3
        assert cc.total_projects == 2
        assert cc.active_signals == 3
        assert cc.critical_signals == 1
        assert cc.capacity_utilization_pct == 72.5
        assert cc.total_monthly_revenue == 60000
        assert cc.entities_declining == 1

    def test_agency_health_average(self, index, sample_clients):
        cc = index.build_command_center(sample_clients)
        expected = (85 + 35 + 60) / 3
        assert cc.agency_health_score == pytest.approx(expected)

    def test_attention_queue_size(self, index, sample_clients):
        cc = index.build_command_center(sample_clients)
        # c2 has health < 50, c2 also has critical_signals > 0
        assert cc.attention_queue_size == 1  # only c2 matches

    def test_empty_clients(self, index):
        cc = index.build_command_center([])
        assert cc.agency_health_score == 0.0
        assert cc.total_clients == 0

    def test_to_dict(self, index, sample_clients):
        cc = index.build_command_center(sample_clients)
        d = cc.to_dict()
        assert "agency_health_score" in d
        assert "generated_at" in d


class TestClientCards:
    def test_builds_cards(self, index, sample_clients):
        cards = index.build_client_cards(sample_clients)
        assert len(cards) == 3

    def test_sorted_by_health_ascending(self, index, sample_clients):
        cards = index.build_client_cards(sample_clients)
        assert cards[0].entity_id == "c2"  # health 35 (worst)
        assert cards[-1].entity_id == "c1"  # health 85 (best)

    def test_health_classification(self, index, sample_clients):
        cards = index.build_client_cards(sample_clients)
        card_map = {c.entity_id: c for c in cards}
        assert card_map["c1"].health_classification == "excellent"
        assert card_map["c2"].health_classification == "poor"

    def test_attention_level(self, index, sample_clients):
        cards = index.build_client_cards(sample_clients)
        card_map = {c.entity_id: c for c in cards}
        assert card_map["c2"].attention_level == "high"  # critical=1, health<50
        assert card_map["c1"].attention_level == "normal"

    def test_to_dict(self, index, sample_clients):
        cards = index.build_client_cards(sample_clients)
        d = cards[0].to_dict()
        assert "entity_id" in d
        assert "attention_level" in d


class TestTeamCapacity:
    def test_builds_cards(self, index):
        members = [
            {
                "person_id": "m1",
                "person_name": "Alice",
                "utilization_pct": 95,
                "active_tasks": 12,
                "overdue_tasks": 2,
                "meeting_hours_week": 15,
            },
            {
                "person_id": "m2",
                "person_name": "Bob",
                "utilization_pct": 50,
                "active_tasks": 5,
                "overdue_tasks": 0,
                "meeting_hours_week": 8,
            },
        ]
        cards = index.build_team_capacity(members)
        assert len(cards) == 2

    def test_sorted_by_utilization_desc(self, index):
        members = [
            {"person_id": "m1", "utilization_pct": 50},
            {"person_id": "m2", "utilization_pct": 120},
        ]
        cards = index.build_team_capacity(members)
        assert cards[0].person_id == "m2"  # highest utilization first

    def test_overload_warning(self, index):
        members = [
            {"person_id": "m1", "utilization_pct": 115},
        ]
        cards = index.build_team_capacity(members)
        assert cards[0].overload_warning is True
        assert cards[0].capacity_status == "overloaded"

    def test_to_dict(self, index):
        members = [{"person_id": "m1", "utilization_pct": 70}]
        cards = index.build_team_capacity(members)
        d = cards[0].to_dict()
        assert "capacity_status" in d


class TestFinancialOverview:
    def test_basic(self, index, sample_clients):
        fo = index.build_financial_overview(sample_clients)
        assert fo.total_monthly_revenue == 60000
        assert fo.total_monthly_cost == 34000
        assert fo.portfolio_margin_pct == pytest.approx(43.33, abs=0.1)

    def test_at_risk_revenue(self, index, sample_clients):
        fo = index.build_financial_overview(sample_clients)
        # c2 has health < 50 AND declining → at_risk
        assert fo.at_risk_revenue == 10000

    def test_growing_revenue(self, index, sample_clients):
        fo = index.build_financial_overview(sample_clients)
        assert fo.growing_revenue == 30000  # c1 is growing

    def test_concentration(self, index, sample_clients):
        fo = index.build_financial_overview(sample_clients)
        assert fo.concentration_hhi > 0
        assert fo.top_client_pct == pytest.approx(50.0)

    def test_revenue_by_client_sorted(self, index, sample_clients):
        fo = index.build_financial_overview(sample_clients)
        revenues = [r["monthly_revenue"] for r in fo.revenue_by_client]
        assert revenues == sorted(revenues, reverse=True)

    def test_empty(self, index):
        fo = index.build_financial_overview([])
        assert fo.total_monthly_revenue == 0.0

    def test_concentration_alert(self, index):
        clients = [
            {
                "entity_id": "c1",
                "monthly_revenue": 90000,
                "monthly_cost": 50000,
                "health_score": 80,
                "trend_direction": "stable",
            },
            {
                "entity_id": "c2",
                "monthly_revenue": 10000,
                "monthly_cost": 5000,
                "health_score": 80,
                "trend_direction": "stable",
            },
        ]
        fo = index.build_financial_overview(clients)
        alert_types = [a["type"] for a in fo.alerts]
        assert "concentration_risk" in alert_types

    def test_to_dict(self, index, sample_clients):
        fo = index.build_financial_overview(sample_clients)
        d = fo.to_dict()
        assert "revenue_by_client" in d
        assert "concentration_hhi" in d


class TestResolutionQueue:
    def test_builds_queue(self, index):
        items = [
            {
                "item_id": "r1",
                "entity_type": "client",
                "entity_id": "c1",
                "severity": "WARNING",
                "description": "Payment overdue",
                "status": "pending",
            },
            {
                "item_id": "r2",
                "entity_type": "client",
                "entity_id": "c2",
                "severity": "CRITICAL",
                "description": "Contract expiring",
                "status": "pending",
            },
        ]
        queue = index.build_resolution_queue(items)
        assert len(queue) == 2
        # CRITICAL should be first
        assert queue[0].item_id == "r2"

    def test_status_filter(self, index):
        items = [
            {
                "item_id": "r1",
                "status": "pending",
                "entity_type": "client",
                "entity_id": "c1",
                "severity": "WARNING",
            },
            {
                "item_id": "r2",
                "status": "approved",
                "entity_type": "client",
                "entity_id": "c2",
                "severity": "WARNING",
            },
        ]
        queue = index.build_resolution_queue(items, status_filter="pending")
        assert len(queue) == 1
        assert queue[0].item_id == "r1"

    def test_to_dict(self, index):
        items = [
            {
                "item_id": "r1",
                "entity_type": "client",
                "entity_id": "c1",
                "severity": "WARNING",
                "status": "pending",
            },
        ]
        queue = index.build_resolution_queue(items)
        d = queue[0].to_dict()
        assert "severity" in d
        assert "status" in d


class TestFullIndex:
    def test_builds_all_views(self, index, sample_clients):
        dashboard = index.build_full_index(
            clients=sample_clients,
            projects=[{"id": "p1"}],
            team_members=[{"person_id": "m1", "utilization_pct": 70}],
            resolution_items=[
                {
                    "item_id": "r1",
                    "entity_type": "client",
                    "entity_id": "c1",
                    "severity": "WARNING",
                    "status": "pending",
                },
            ],
        )
        assert dashboard.command_center.total_clients == 3
        assert len(dashboard.client_cards) == 3
        assert len(dashboard.team_capacity) == 1
        assert len(dashboard.resolution_queue) == 1
        assert dashboard.generated_at != ""

    def test_to_dict(self, index, sample_clients):
        dashboard = index.build_full_index(clients=sample_clients)
        d = dashboard.to_dict()
        assert "command_center" in d
        assert "client_cards" in d
        assert "financial_overview" in d
        assert "generated_at" in d

    def test_empty_index(self, index):
        dashboard = index.build_full_index(clients=[])
        assert dashboard.command_center.total_clients == 0
        assert len(dashboard.client_cards) == 0
