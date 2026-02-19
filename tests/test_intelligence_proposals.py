"""
Tests for Intelligence Proposals Module.

Covers:
- Helper functions (headline, urgency, evidence formatting)
- Proposal assembly
- Deduplication and merging
- Full proposal generation
"""

import pytest
from pathlib import Path

from lib.intelligence.proposals import (
    ProposalType,
    ProposalUrgency,
    Proposal,
    PriorityScore,
    # Helper functions
    _generate_proposal_id,
    _format_evidence_item,
    _format_evidence,
    _generate_headline,
    _generate_summary,
    _generate_action,
    _determine_urgency,
    _determine_trend,
    _determine_confidence,
    # Assembly functions
    _assemble_client_proposal,
    _assemble_resource_proposal,
    _assemble_portfolio_proposal,
    _merge_proposals,
    # Main functions
    generate_proposals,
    generate_proposals_from_live_data,
    # Priority ranking
    _score_urgency,
    _score_impact,
    _score_recency,
    _score_confidence,
    compute_priority_score,
    rank_proposals,
    get_top_proposals,
    get_proposals_by_type,
    generate_daily_briefing,
)


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestHelperFunctions:
    """Tests for proposal helper functions."""

    def test_generate_proposal_id(self):
        """Proposal IDs should be unique and formatted correctly."""
        id1 = _generate_proposal_id()
        id2 = _generate_proposal_id()

        assert id1.startswith("prop_")
        assert id1 != id2  # Should be unique

    def test_format_evidence_item(self):
        """Evidence items should have correct structure."""
        item = _format_evidence_item(
            source="signal",
            source_id="sig_test",
            description="Test signal detected",
            data={"severity": "warning"}
        )

        assert item["source"] == "signal"
        assert item["source_id"] == "sig_test"
        assert item["description"] == "Test signal detected"
        assert item["data"]["severity"] == "warning"

    def test_format_evidence_with_scorecard(self):
        """Evidence formatting should include score data."""
        scorecard = {
            "composite_score": 45,
            "classification": "at_risk",
            "dimensions": {
                "engagement": {"score": 30},
                "delivery": {"score": 60},
            }
        }

        evidence = _format_evidence(scorecard=scorecard)

        assert len(evidence) >= 1
        assert any("45/100" in e["description"] for e in evidence)

    def test_format_evidence_with_signals(self):
        """Evidence formatting should include signal data."""
        signals = [
            {"signal_id": "sig_1", "evidence_text": "Communication dropped 40%", "severity": "warning"},
            {"signal_id": "sig_2", "evidence_text": "Payment overdue", "severity": "critical"},
        ]

        evidence = _format_evidence(signals=signals)

        assert len(evidence) == 2
        # Critical should come first (sorted by severity)
        assert evidence[0]["data"]["severity"] == "critical"

    def test_generate_headline_includes_entity_name(self):
        """Headlines should include entity name."""
        entity = {"type": "client", "id": "123", "name": "Acme Corp"}
        evidence = [
            {"source": "score", "source_id": "composite", "description": "Score: 28/100", "data": {}}
        ]

        headline = _generate_headline(ProposalType.CLIENT_RISK, entity, evidence)

        assert "Acme Corp" in headline

    def test_generate_headline_not_generic(self):
        """Headlines should not be generic placeholders."""
        entity = {"type": "client", "id": "123", "name": "Test Client"}
        evidence = [
            {"source": "signal", "source_id": "sig_1", "description": "Revenue down 30%", "data": {}}
        ]

        headline = _generate_headline(ProposalType.CLIENT_RISK, entity, evidence)

        # Should not be generic
        assert headline != "Alert"
        assert headline != "Attention needed"
        assert len(headline) > 20


class TestUrgencyDetermination:
    """Tests for urgency determination logic."""

    def test_critical_signal_is_immediate(self):
        """CRITICAL signals should trigger IMMEDIATE urgency."""
        urgency = _determine_urgency(
            signal_severities=["critical"]
        )
        assert urgency == ProposalUrgency.IMMEDIATE

    def test_structural_pattern_is_immediate(self):
        """Structural patterns should trigger IMMEDIATE urgency."""
        urgency = _determine_urgency(
            pattern_severities=["structural"]
        )
        assert urgency == ProposalUrgency.IMMEDIATE

    def test_warning_signal_is_this_week(self):
        """WARNING signals should trigger THIS_WEEK urgency."""
        urgency = _determine_urgency(
            signal_severities=["warning"]
        )
        assert urgency == ProposalUrgency.THIS_WEEK

    def test_at_risk_score_is_this_week(self):
        """AT_RISK classification should trigger THIS_WEEK urgency."""
        urgency = _determine_urgency(
            score_classification="at_risk"
        )
        assert urgency == ProposalUrgency.THIS_WEEK

    def test_watch_only_is_monitor(self):
        """Only WATCH signals should trigger MONITOR urgency."""
        urgency = _determine_urgency(
            signal_severities=["watch"]
        )
        assert urgency == ProposalUrgency.MONITOR

    def test_no_signals_is_monitor(self):
        """No signals should default to MONITOR."""
        urgency = _determine_urgency()
        assert urgency == ProposalUrgency.MONITOR


class TestTrendDetermination:
    """Tests for trend determination."""

    def test_new_signals_trend_new(self):
        """Signals with eval count 1 should be 'new'."""
        signals = [
            {"signal_id": "sig_1", "evaluation_count": 1},
        ]
        trend = _determine_trend(signals)
        assert trend == "new"

    def test_recurring_signals_trend_stable(self):
        """Signals with low eval count should be 'stable'."""
        signals = [
            {"signal_id": "sig_1", "evaluation_count": 2},
            {"signal_id": "sig_2", "evaluation_count": 3},
        ]
        trend = _determine_trend(signals)
        assert trend == "stable"

    def test_high_eval_count_trend_escalating(self):
        """Signals with high eval count should be 'escalating'."""
        signals = [
            {"signal_id": "sig_1", "evaluation_count": 10},
            {"signal_id": "sig_2", "evaluation_count": 8},
        ]
        trend = _determine_trend(signals)
        assert trend == "escalating"

    def test_no_signals_trend_new(self):
        """No signals should default to 'new'."""
        trend = _determine_trend(None)
        assert trend == "new"


class TestConfidenceDetermination:
    """Tests for confidence level determination."""

    def test_multiple_evidence_high_confidence(self):
        """Multiple evidence sources should yield high confidence."""
        confidence = _determine_confidence(
            scorecard={"composite_score": 50},
            signals=[{"signal_id": "sig_1"}, {"signal_id": "sig_2"}],
            patterns=[{"pattern_id": "pat_1"}]
        )
        assert confidence == "high"

    def test_single_evidence_medium_confidence(self):
        """Single evidence source should yield medium confidence."""
        confidence = _determine_confidence(
            signals=[{"signal_id": "sig_1"}]
        )
        assert confidence == "medium"

    def test_no_evidence_low_confidence(self):
        """No evidence should yield low confidence."""
        confidence = _determine_confidence()
        assert confidence == "low"


# =============================================================================
# PROPOSAL ASSEMBLY TESTS
# =============================================================================

class TestProposalAssembly:
    """Tests for proposal assembly functions."""

    def test_client_proposal_has_required_fields(self):
        """Client proposals should have all required fields."""
        signals = [
            {"signal_id": "sig_1", "evidence_text": "Test signal", "severity": "warning"}
        ]

        prop = _assemble_client_proposal(
            client_id="client_123",
            client_name="Test Client",
            signals=signals
        )

        assert prop.id.startswith("prop_")
        assert prop.type == ProposalType.CLIENT_RISK
        assert prop.headline != ""
        assert prop.entity["id"] == "client_123"
        assert len(prop.evidence) > 0
        assert prop.implied_action != ""

    def test_resource_proposal_correct_type(self):
        """Resource proposals should have RESOURCE_RISK type."""
        prop = _assemble_resource_proposal(
            person_id="person_123",
            person_name="John Doe",
            signals=[{"signal_id": "sig_1", "severity": "warning"}]
        )

        assert prop.type == ProposalType.RESOURCE_RISK

    def test_portfolio_proposal_from_pattern(self):
        """Portfolio proposals should be created from patterns."""
        pattern = {
            "pattern_id": "pat_concentration",
            "pattern_name": "Revenue Concentration",
            "severity": "structural",
            "evidence_narrative": "Top 3 clients represent 60% of revenue",
            "implied_action": "Diversify portfolio",
            "entities_involved": [],
            "confidence": "high",
        }

        prop = _assemble_portfolio_proposal(pattern)

        assert prop.type == ProposalType.PORTFOLIO_RISK
        assert "pat_concentration" in prop.active_patterns


# =============================================================================
# DEDUPLICATION TESTS
# =============================================================================

class TestDeduplication:
    """Tests for proposal merging and deduplication."""

    def test_merge_same_entity_proposals(self):
        """Multiple proposals for same entity should merge."""
        prop1 = Proposal(
            id="prop_1",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test 1",
            entity={"type": "client", "id": "123", "name": "Test"},
            summary="Summary 1",
            evidence=[{"source": "signal", "source_id": "sig_1", "description": "Test 1", "data": {}}],
            implied_action="Action 1",
            active_signals=["sig_1"],
        )

        prop2 = Proposal(
            id="prop_2",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.IMMEDIATE,
            headline="Test 2",
            entity={"type": "client", "id": "123", "name": "Test"},
            summary="Summary 2",
            evidence=[{"source": "signal", "source_id": "sig_2", "description": "Test 2", "data": {}}],
            implied_action="Action 2",
            active_signals=["sig_2"],
        )

        merged = _merge_proposals([prop1, prop2])

        assert len(merged) == 1
        # Should have higher urgency
        assert merged[0].urgency == ProposalUrgency.IMMEDIATE
        # Should have both signals
        assert "sig_1" in merged[0].active_signals
        assert "sig_2" in merged[0].active_signals
        # Should have all evidence
        assert len(merged[0].evidence) >= 2

    def test_different_entities_not_merged(self):
        """Proposals for different entities should not merge."""
        prop1 = Proposal(
            id="prop_1",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test 1",
            entity={"type": "client", "id": "123", "name": "Client A"},
            summary="Summary",
            evidence=[],
            implied_action="Action",
        )

        prop2 = Proposal(
            id="prop_2",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test 2",
            entity={"type": "client", "id": "456", "name": "Client B"},
            summary="Summary",
            evidence=[],
            implied_action="Action",
        )

        merged = _merge_proposals([prop1, prop2])

        assert len(merged) == 2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestProposalGeneration:
    """Integration tests for proposal generation."""

    @pytest.fixture
    def db_path(self, integration_db_path):
        """Use fixture DB for deterministic testing."""
        return integration_db_path

    def test_generate_proposals_structure(self, db_path):
        """generate_proposals_from_live_data should return valid structure."""
        result = generate_proposals_from_live_data(db_path)

        assert "generated_at" in result
        assert "total_proposals" in result
        assert "by_urgency" in result
        assert "by_type" in result
        assert "proposals" in result

        assert isinstance(result["proposals"], list)

    def test_proposals_have_evidence(self, db_path):
        """Generated proposals should have evidence."""
        result = generate_proposals_from_live_data(db_path)

        for prop in result["proposals"]:
            assert "evidence" in prop
            assert isinstance(prop["evidence"], list)

    def test_proposals_have_headlines(self, db_path):
        """Generated proposals should have non-empty headlines."""
        result = generate_proposals_from_live_data(db_path)

        for prop in result["proposals"]:
            assert "headline" in prop
            assert len(prop["headline"]) > 0

    def test_proposals_have_actions(self, db_path):
        """Generated proposals should have implied actions."""
        result = generate_proposals_from_live_data(db_path)

        for prop in result["proposals"]:
            assert "implied_action" in prop
            assert len(prop["implied_action"]) > 0

    def test_proposals_sorted_by_urgency(self, db_path):
        """Proposals should be sorted by urgency (IMMEDIATE first)."""
        result = generate_proposals_from_live_data(db_path)

        urgency_order = {"immediate": 0, "this_week": 1, "monitor": 2}

        urgencies = [urgency_order.get(p["urgency"], 3) for p in result["proposals"]]

        # Should be sorted
        assert urgencies == sorted(urgencies)

    def test_no_duplicate_entities(self, db_path):
        """Same entity should not have multiple proposals."""
        result = generate_proposals_from_live_data(db_path)

        seen_entities = set()
        for prop in result["proposals"]:
            entity_key = (prop["entity"]["type"], prop["entity"]["id"])
            assert entity_key not in seen_entities, f"Duplicate proposal for {entity_key}"
            seen_entities.add(entity_key)


class TestProposalQuality:
    """Tests for proposal content quality."""

    @pytest.fixture
    def db_path(self, integration_db_path):
        """Use fixture DB for deterministic testing."""
        return integration_db_path

    def test_headlines_not_generic(self, db_path):
        """Headlines should not be generic placeholders."""
        result = generate_proposals_from_live_data(db_path)

        generic_phrases = ["Alert", "Warning", "Attention", "Issue detected"]

        for prop in result["proposals"][:5]:  # Check first 5
            headline = prop["headline"]
            # Headline should contain entity info, not just generic phrases
            is_only_generic = all(
                generic in headline and len(headline) < len(generic) + 20
                for generic in generic_phrases
            )
            assert not is_only_generic, f"Generic headline: {headline}"


# =============================================================================
# PRIORITY RANKING TESTS
# =============================================================================

class TestPriorityScoring:
    """Tests for priority scoring components."""

    def test_score_urgency_immediate_high(self):
        """IMMEDIATE urgency should score high."""
        prop = Proposal(
            id="test",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.IMMEDIATE,
            headline="Test",
            entity={"type": "client", "id": "1", "name": "Test"},
            summary="Test",
            evidence=[],
            implied_action="Test",
        )

        score = _score_urgency(prop)
        assert score == 100

    def test_score_urgency_monitor_low(self):
        """MONITOR urgency should score low."""
        prop = Proposal(
            id="test",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.MONITOR,
            headline="Test",
            entity={"type": "client", "id": "1", "name": "Test"},
            summary="Test",
            evidence=[],
            implied_action="Test",
        )

        score = _score_urgency(prop)
        assert score == 20

    def test_score_urgency_escalating_bonus(self):
        """Escalating trend should add bonus."""
        prop = Proposal(
            id="test",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test",
            entity={"type": "client", "id": "1", "name": "Test"},
            summary="Test",
            evidence=[],
            implied_action="Test",
            trend="escalating",
        )

        score = _score_urgency(prop)
        assert score == 70  # 60 base + 10 escalating

    def test_score_recency_new_high(self):
        """New proposals should score high."""
        prop = Proposal(
            id="test",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test",
            entity={"type": "client", "id": "1", "name": "Test"},
            summary="Test",
            evidence=[],
            implied_action="Test",
            trend="new",
        )

        score = _score_recency(prop)
        assert score == 100

    def test_score_recency_stable_low(self):
        """Stable proposals should score low."""
        prop = Proposal(
            id="test",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test",
            entity={"type": "client", "id": "1", "name": "Test"},
            summary="Test",
            evidence=[],
            implied_action="Test",
            trend="stable",
        )

        score = _score_recency(prop)
        assert score == 30

    def test_score_confidence_high(self):
        """High confidence should score 100."""
        prop = Proposal(
            id="test",
            type=ProposalType.CLIENT_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test",
            entity={"type": "client", "id": "1", "name": "Test"},
            summary="Test",
            evidence=[],
            implied_action="Test",
            confidence="high",
        )

        score = _score_confidence(prop)
        assert score == 100

    def test_score_impact_portfolio_always_high(self):
        """Portfolio proposals should always have high impact."""
        prop = Proposal(
            id="test",
            type=ProposalType.PORTFOLIO_RISK,
            urgency=ProposalUrgency.THIS_WEEK,
            headline="Test",
            entity={"type": "portfolio", "id": "portfolio", "name": "Portfolio"},
            summary="Test",
            evidence=[],
            implied_action="Test",
        )

        score = _score_impact(prop)
        assert score == 100


class TestProposalRanking:
    """Tests for proposal ranking."""

    def test_rank_proposals_ordering(self):
        """Proposals should be ordered by priority score."""
        props = [
            Proposal(
                id="low",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.MONITOR,
                headline="Low",
                entity={"type": "client", "id": "1", "name": "Low"},
                summary="Test",
                evidence=[],
                implied_action="Test",
                trend="stable",
                confidence="low",
            ),
            Proposal(
                id="high",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.IMMEDIATE,
                headline="High",
                entity={"type": "client", "id": "2", "name": "High"},
                summary="Test",
                evidence=[],
                implied_action="Test",
                trend="new",
                confidence="high",
            ),
        ]

        ranked = rank_proposals(props)

        # High urgency should be first
        assert ranked[0][0].id == "high"
        assert ranked[1][0].id == "low"

    def test_rank_proposals_assigns_ranks(self):
        """Ranking should assign rank numbers."""
        props = [
            Proposal(
                id="a",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.IMMEDIATE,
                headline="A",
                entity={"type": "client", "id": "1", "name": "A"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
            Proposal(
                id="b",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.MONITOR,
                headline="B",
                entity={"type": "client", "id": "2", "name": "B"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
        ]

        ranked = rank_proposals(props)

        assert ranked[0][1].rank == 1
        assert ranked[1][1].rank == 2

    def test_get_top_proposals_limit(self):
        """get_top_proposals should return correct number."""
        props = [
            Proposal(
                id=f"prop_{i}",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.THIS_WEEK,
                headline=f"Prop {i}",
                entity={"type": "client", "id": str(i), "name": f"Client {i}"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            )
            for i in range(10)
        ]

        top5 = get_top_proposals(props, n=5)
        assert len(top5) == 5

        top3 = get_top_proposals(props, n=3)
        assert len(top3) == 3

    def test_get_proposals_by_type_filters(self):
        """get_proposals_by_type should filter correctly."""
        props = [
            Proposal(
                id="client",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.THIS_WEEK,
                headline="Client",
                entity={"type": "client", "id": "1", "name": "Client"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
            Proposal(
                id="resource",
                type=ProposalType.RESOURCE_RISK,
                urgency=ProposalUrgency.THIS_WEEK,
                headline="Resource",
                entity={"type": "person", "id": "1", "name": "Person"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
        ]

        client_only = get_proposals_by_type(props, ProposalType.CLIENT_RISK)
        assert len(client_only) == 1
        assert client_only[0][0].id == "client"


class TestDailyBriefing:
    """Tests for daily briefing generation."""

    def test_briefing_structure(self):
        """Daily briefing should have complete structure."""
        props = [
            Proposal(
                id="test",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.IMMEDIATE,
                headline="Test",
                entity={"type": "client", "id": "1", "name": "Test"},
                summary="Test",
                evidence=[{"source": "signal", "source_id": "sig_1", "description": "Test", "data": {}}],
                implied_action="Test",
            ),
        ]

        briefing = generate_daily_briefing(props)

        assert "generated_at" in briefing
        assert "summary" in briefing
        assert "critical_items" in briefing
        assert "attention_items" in briefing
        assert "watching" in briefing
        assert "portfolio_health" in briefing
        assert "top_proposal" in briefing

    def test_briefing_summary_counts(self):
        """Briefing summary should have correct counts."""
        props = [
            Proposal(
                id="imm",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.IMMEDIATE,
                headline="Immediate",
                entity={"type": "client", "id": "1", "name": "Imm"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
            Proposal(
                id="week",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.THIS_WEEK,
                headline="This Week",
                entity={"type": "client", "id": "2", "name": "Week"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
            Proposal(
                id="mon",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.MONITOR,
                headline="Monitor",
                entity={"type": "client", "id": "3", "name": "Mon"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
        ]

        briefing = generate_daily_briefing(props)

        assert briefing["summary"]["total_proposals"] == 3
        assert briefing["summary"]["immediate_count"] == 1
        assert briefing["summary"]["this_week_count"] == 1
        assert briefing["summary"]["monitor_count"] == 1

    def test_briefing_top_proposal(self):
        """Briefing should include top proposal headline."""
        props = [
            Proposal(
                id="test",
                type=ProposalType.CLIENT_RISK,
                urgency=ProposalUrgency.IMMEDIATE,
                headline="Most Important Issue",
                entity={"type": "client", "id": "1", "name": "Test"},
                summary="Test",
                evidence=[],
                implied_action="Test",
            ),
        ]

        briefing = generate_daily_briefing(props)

        assert briefing["top_proposal"] == "Most Important Issue"
