"""
Tests for DecisionJournal — persistent decision logging and queries.

Brief 22 (SM), Task SM-1.1
"""

from datetime import datetime
from pathlib import Path

import pytest

from lib.intelligence.decision_journal import Decision, DecisionJournal


@pytest.fixture
def journal(tmp_path):
    db_path = tmp_path / "test_decisions.db"
    return DecisionJournal(db_path=db_path)


class TestRecord:
    def test_record_creates_decision(self, journal):
        d = journal.record(
            decision_type="signal_dismiss",
            entity_type="client",
            entity_id="client_a",
            action_taken="dismissed_overdue_signal",
            context_snapshot={"health_score": 72},
            source="user",
        )
        assert d.id is not None
        assert d.decision_type == "signal_dismiss"
        assert d.entity_type == "client"
        assert d.entity_id == "client_a"
        assert d.action_taken == "dismissed_overdue_signal"
        assert d.context_snapshot == {"health_score": 72}
        assert d.source == "user"
        assert d.created_at != ""

    def test_record_default_source(self, journal):
        d = journal.record(
            decision_type="auto_escalate",
            entity_type="project",
            entity_id="proj_1",
            action_taken="escalated_to_warning",
        )
        assert d.source == "system"

    def test_record_empty_context(self, journal):
        d = journal.record(
            decision_type="review",
            entity_type="client",
            entity_id="c1",
            action_taken="reviewed",
        )
        assert d.context_snapshot == {}


class TestRecordOutcome:
    def test_updates_outcome(self, journal):
        d = journal.record(
            decision_type="signal_dismiss",
            entity_type="client",
            entity_id="c1",
            action_taken="dismissed",
        )
        journal.record_outcome(d.id, "signal_cleared_naturally", 0.8)
        decisions = journal.get_decisions_for_entity("client", "c1")
        assert len(decisions) == 1
        assert decisions[0].outcome == "signal_cleared_naturally"
        assert decisions[0].outcome_score == pytest.approx(0.8)

    def test_outcome_without_score(self, journal):
        d = journal.record(
            decision_type="review",
            entity_type="client",
            entity_id="c1",
            action_taken="reviewed",
        )
        journal.record_outcome(d.id, "no_change_needed")
        decisions = journal.get_decisions_for_entity("client", "c1")
        assert decisions[0].outcome == "no_change_needed"
        assert decisions[0].outcome_score is None


class TestQueryDecisions:
    def test_get_by_entity(self, journal):
        journal.record("dismiss", "client", "a", "dismissed")
        journal.record("dismiss", "client", "b", "dismissed")
        journal.record("escalate", "client", "a", "escalated")

        results = journal.get_decisions_for_entity("client", "a")
        assert len(results) == 2

    def test_get_by_type(self, journal):
        journal.record("dismiss", "client", "a", "dismissed")
        journal.record("dismiss", "client", "b", "dismissed")
        journal.record("escalate", "client", "a", "escalated")

        results = journal.get_decisions_by_type("dismiss")
        assert len(results) == 2

    def test_get_by_type_empty(self, journal):
        results = journal.get_decisions_by_type("nonexistent")
        assert len(results) == 0

    def test_limit(self, journal):
        for i in range(10):
            journal.record("review", "client", "a", f"action_{i}")
        results = journal.get_decisions_for_entity("client", "a", limit=5)
        assert len(results) == 5


class TestActionDistribution:
    def test_distribution(self, journal):
        journal.record("dismiss", "client", "a", "dismissed")
        journal.record("dismiss", "client", "b", "dismissed")
        journal.record("escalate", "client", "c", "escalated")

        dist = journal.get_action_distribution()
        assert dist["dismiss"] == 2
        assert dist["escalate"] == 1

    def test_distribution_by_entity_type(self, journal):
        journal.record("dismiss", "client", "a", "dismissed")
        journal.record("dismiss", "project", "p1", "dismissed")

        dist = journal.get_action_distribution(entity_type="client")
        assert dist.get("dismiss", 0) == 1

    def test_distribution_empty(self, journal):
        dist = journal.get_action_distribution()
        assert dist == {}


class TestEffectivenessReport:
    def test_report_with_outcomes(self, journal):
        d1 = journal.record("dismiss", "client", "a", "dismissed")
        journal.record_outcome(d1.id, "cleared", 0.8)
        d2 = journal.record("escalate", "client", "b", "escalated")
        journal.record_outcome(d2.id, "resolved", 0.9)

        report = journal.get_effectiveness_report()
        assert report["total_decisions"] == 2
        assert report["with_outcome"] == 2
        assert report["outcome_rate"] == pytest.approx(1.0)
        assert report["avg_outcome_score"] == pytest.approx(0.85)
        assert "dismiss" in report["by_type"]
        assert "escalate" in report["by_type"]

    def test_report_empty(self, journal):
        report = journal.get_effectiveness_report()
        assert report["total_decisions"] == 0
        assert report["outcome_rate"] == 0.0

    def test_report_partial_outcomes(self, journal):
        d1 = journal.record("dismiss", "client", "a", "dismissed")
        journal.record_outcome(d1.id, "cleared", 0.7)
        journal.record("review", "client", "b", "reviewed")  # no outcome

        report = journal.get_effectiveness_report()
        assert report["total_decisions"] == 2
        assert report["with_outcome"] == 1
        assert report["outcome_rate"] == pytest.approx(0.5)


class TestDecisionToDict:
    def test_to_dict(self, journal):
        d = journal.record(
            decision_type="review",
            entity_type="client",
            entity_id="c1",
            action_taken="reviewed",
            context_snapshot={"score": 85},
        )
        as_dict = d.to_dict()
        assert as_dict["decision_type"] == "review"
        assert as_dict["context_snapshot"] == {"score": 85}
        assert "id" in as_dict
