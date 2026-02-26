"""
Tests for BehavioralPatternAnalyzer — pattern discovery and context hints.

Brief 22 (SM), Task SM-4.1
"""

import pytest

from lib.intelligence.behavioral_patterns import (
    BehavioralPattern,
    BehavioralPatternAnalyzer,
    ContextHint,
)
from lib.intelligence.decision_journal import DecisionJournal


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_patterns.db"


@pytest.fixture
def journal(db_path):
    return DecisionJournal(db_path=db_path)


@pytest.fixture
def analyzer(db_path):
    return BehavioralPatternAnalyzer(db_path=db_path)


def _seed_decisions(journal):
    """Seed with representative decision data."""
    # Frequent dismiss pattern for client_a
    for _i in range(5):
        d = journal.record("signal_dismiss", "client", "client_a", "dismissed_overdue")
        journal.record_outcome(d.id, "signal_returned", 0.3)

    # Escalation pattern for client_b
    for _i in range(4):
        journal.record("signal_escalate", "client", "client_b", "escalated_to_warning")

    # Successful reviews for client_c
    for _i in range(3):
        d = journal.record("review", "client", "client_c", "scheduled_check_in")
        journal.record_outcome(d.id, "health_improved", 0.9)

    # Mixed actions for project
    d = journal.record("signal_dismiss", "project", "proj_1", "dismissed_low_priority")
    journal.record_outcome(d.id, "no_change", 0.5)
    d = journal.record("review", "project", "proj_1", "reviewed_scope")
    journal.record_outcome(d.id, "scope_adjusted", 0.8)


class TestDiscoverPatterns:
    def test_finds_frequent_actions(self, journal, analyzer):
        _seed_decisions(journal)
        patterns = analyzer.discover_patterns(min_frequency=3)
        frequent = [p for p in patterns if p.pattern_type == "frequent_action"]
        assert len(frequent) > 0
        # client_a dismissed 5 times
        dismiss_pattern = [p for p in frequent if "dismissed_overdue" in p.description]
        assert len(dismiss_pattern) > 0
        assert dismiss_pattern[0].frequency >= 5

    def test_finds_entity_preferences(self, journal, analyzer):
        _seed_decisions(journal)
        patterns = analyzer.discover_patterns(min_frequency=3)
        prefs = [p for p in patterns if p.pattern_type == "entity_preference"]
        # client_a has 5/14 decisions (~36%) → should be flagged
        if prefs:
            assert prefs[0].entity_id == "client_a"

    def test_finds_escalation_patterns(self, journal, analyzer):
        _seed_decisions(journal)
        patterns = analyzer.discover_patterns(min_frequency=3)
        escalations = [p for p in patterns if p.pattern_type == "escalation_pattern"]
        assert len(escalations) > 0
        assert escalations[0].entity_id == "client_b"

    def test_empty_journal(self, journal, analyzer):
        patterns = analyzer.discover_patterns()
        assert patterns == []

    def test_min_frequency_filter(self, journal, analyzer):
        journal.record("dismiss", "client", "c1", "dismissed")
        journal.record("dismiss", "client", "c1", "dismissed")
        # Only 2 occurrences, min_frequency=3 should filter it out
        patterns = analyzer.discover_patterns(min_frequency=3)
        frequent = [p for p in patterns if p.pattern_type == "frequent_action"]
        assert len(frequent) == 0

    def test_patterns_sorted_by_confidence(self, journal, analyzer):
        _seed_decisions(journal)
        patterns = analyzer.discover_patterns(min_frequency=2)
        if len(patterns) > 1:
            for i in range(len(patterns) - 1):
                assert patterns[i].confidence >= patterns[i + 1].confidence


class TestContextHints:
    def test_hints_for_known_entity(self, journal, analyzer):
        _seed_decisions(journal)
        hints = analyzer.generate_context_hints(
            entity_type="client",
            entity_id="client_a",
            decision_type="signal_dismiss",
        )
        assert len(hints) > 0
        # Should include a "past_action" hint
        past_hints = [h for h in hints if h.hint_type == "past_action"]
        assert len(past_hints) > 0

    def test_hints_for_unknown_entity(self, journal, analyzer):
        hints = analyzer.generate_context_hints(
            entity_type="client",
            entity_id="unknown_entity",
        )
        assert len(hints) > 0
        assert "No prior decisions" in hints[0].message

    def test_effectiveness_hints(self, journal, analyzer):
        _seed_decisions(journal)
        hints = analyzer.generate_context_hints(
            entity_type="client",
            entity_id="client_c",
            decision_type="review",
        )
        # Should include an effectiveness hint since reviews have outcomes
        eff_hints = [h for h in hints if h.hint_type == "effectiveness"]
        assert len(eff_hints) > 0

    def test_hint_limit(self, journal, analyzer):
        _seed_decisions(journal)
        hints = analyzer.generate_context_hints(
            entity_type="client",
            entity_id="client_a",
            limit=2,
        )
        assert len(hints) <= 2

    def test_hints_sorted_by_relevance(self, journal, analyzer):
        _seed_decisions(journal)
        hints = analyzer.generate_context_hints(
            entity_type="client",
            entity_id="client_a",
        )
        if len(hints) > 1:
            for i in range(len(hints) - 1):
                assert hints[i].relevance >= hints[i + 1].relevance


class TestActionEffectiveness:
    def test_effectiveness_with_outcomes(self, journal, analyzer):
        _seed_decisions(journal)
        results = analyzer.get_action_effectiveness(decision_type="signal_dismiss")
        assert len(results) > 0
        # Find the dismissed_overdue action (5 uses from client_a)
        overdue_eff = [r for r in results if r.action_taken == "dismissed_overdue"]
        assert len(overdue_eff) == 1
        assert overdue_eff[0].total_uses >= 5
        assert overdue_eff[0].outcomes_recorded >= 5

    def test_effectiveness_all_types(self, journal, analyzer):
        _seed_decisions(journal)
        results = analyzer.get_action_effectiveness()
        types = {r.decision_type for r in results}
        assert "signal_dismiss" in types

    def test_effectiveness_empty(self, journal, analyzer):
        results = analyzer.get_action_effectiveness()
        assert results == []

    def test_effectiveness_to_dict(self, journal, analyzer):
        _seed_decisions(journal)
        results = analyzer.get_action_effectiveness()
        if results:
            d = results[0].to_dict()
            assert "decision_type" in d
            assert "success_rate" in d
            assert "avg_outcome_score" in d


class TestDecisionDistribution:
    def test_distribution(self, journal, analyzer):
        _seed_decisions(journal)
        dist = analyzer.get_decision_distribution()
        assert dist["total_decisions"] > 0
        assert "signal_dismiss" in dist["by_type"]
        assert "system" in dist["by_source"]

    def test_distribution_empty(self, journal, analyzer):
        dist = analyzer.get_decision_distribution()
        assert dist["total_decisions"] == 0


class TestDataclassToDict:
    def test_behavioral_pattern_to_dict(self):
        p = BehavioralPattern(
            pattern_type="frequent_action",
            description="Test pattern",
            frequency=5,
            confidence=0.85,
        )
        d = p.to_dict()
        assert d["pattern_type"] == "frequent_action"
        assert d["confidence"] == 0.85

    def test_context_hint_to_dict(self):
        h = ContextHint(
            hint_type="past_action",
            message="Test hint",
            relevance=0.7,
            source_decision_ids=["d1", "d2"],
        )
        d = h.to_dict()
        assert d["hint_type"] == "past_action"
        assert d["source_decisions"] == 2
