"""
Tests for ConversationalIntelligence — NLQ interface.

Brief 25 (CI), Tasks CI-1.1 through CI-3.1
"""

import pytest

from lib.intelligence.conversational_intelligence import (
    INTENT_ACTION_REQUEST,
    INTENT_COMPARISON,
    INTENT_ENTITY_LOOKUP,
    INTENT_HISTORY_LOOKUP,
    INTENT_METRIC_QUERY,
    INTENT_PREDICTION,
    INTENT_RANKED_SUMMARY,
    INTENT_UNKNOWN,
    ConversationalIntelligence,
    ConversationState,
    CrossDomainSynthesizer,
    EntityResolver,
    classify_intent,
)


class TestClassifyIntent:
    def test_entity_lookup(self):
        result = classify_intent("How is Client Acme doing?")
        assert result.intent_type == INTENT_ENTITY_LOOKUP

    def test_entity_lookup_tell_me(self):
        result = classify_intent("Tell me about Project Alpha")
        assert result.intent_type == INTENT_ENTITY_LOOKUP

    def test_metric_query(self):
        result = classify_intent("What's my revenue this month?")
        assert result.intent_type == INTENT_METRIC_QUERY

    def test_comparison(self):
        result = classify_intent("Compare Client X and Client Y")
        assert result.intent_type == INTENT_COMPARISON

    def test_prediction(self):
        result = classify_intent("What if Client X leaves?")
        assert result.intent_type == INTENT_PREDICTION

    def test_action_request_email(self):
        result = classify_intent("Draft an email to Client Acme about the overdue invoice")
        assert result.intent_type == INTENT_ACTION_REQUEST
        assert result.extracted_action == "email"

    def test_action_request_meeting(self):
        result = classify_intent("Schedule a meeting with Client Beta")
        assert result.intent_type == INTENT_ACTION_REQUEST

    def test_history_lookup(self):
        result = classify_intent("What did I decide about Client X last time?")
        assert result.intent_type == INTENT_HISTORY_LOOKUP

    def test_ranked_summary(self):
        result = classify_intent("What should I worry about this week?")
        assert result.intent_type == INTENT_RANKED_SUMMARY

    def test_ranked_summary_priorities(self):
        result = classify_intent("What are the most urgent issues?")
        assert result.intent_type == INTENT_RANKED_SUMMARY

    def test_unknown(self):
        result = classify_intent("random gibberish xyzzy")
        assert result.intent_type == INTENT_UNKNOWN

    def test_empty_query(self):
        result = classify_intent("")
        assert result.intent_type == INTENT_UNKNOWN
        assert result.confidence == 0.0

    def test_extracts_timeframe(self):
        result = classify_intent("What's my revenue this month?")
        assert result.extracted_timeframe == "this_month"

    def test_extracts_metrics(self):
        result = classify_intent("What's my revenue and profit this quarter?")
        assert "revenue" in result.extracted_metrics
        assert "profit" in result.extracted_metrics

    def test_to_dict(self):
        result = classify_intent("How is Client Acme?")
        d = result.to_dict()
        assert "intent_type" in d
        assert "confidence" in d


class TestEntityResolver:
    @pytest.fixture
    def resolver(self):
        registry = [
            {"entity_type": "client", "entity_id": "c1", "entity_name": "Acme Corporation"},
            {"entity_type": "client", "entity_id": "c2", "entity_name": "Beta Industries"},
            {"entity_type": "project", "entity_id": "p1", "entity_name": "Brand Refresh"},
        ]
        return EntityResolver(registry)

    def test_exact_match(self, resolver):
        result = resolver.resolve("Acme Corporation")
        assert result is not None
        assert result.entity_id == "c1"
        assert result.match_method == "exact"
        assert result.match_confidence == 1.0

    def test_case_insensitive(self, resolver):
        result = resolver.resolve("acme corporation")
        assert result is not None
        assert result.entity_id == "c1"

    def test_partial_match(self, resolver):
        result = resolver.resolve("Acme")
        assert result is not None
        assert result.entity_id == "c1"
        assert result.match_method == "fuzzy"

    def test_no_match(self, resolver):
        result = resolver.resolve("Nonexistent Company")
        assert result is None

    def test_type_filter(self, resolver):
        result = resolver.resolve("Brand Refresh", entity_type="client")
        assert result is None  # It's a project, not a client

    def test_resolve_multiple(self, resolver):
        results = resolver.resolve_multiple(["Acme", "Beta"])
        assert len(results) == 2

    def test_empty_registry(self):
        resolver = EntityResolver([])
        result = resolver.resolve("Anything")
        assert result is None

    def test_to_dict(self, resolver):
        result = resolver.resolve("Acme Corporation")
        d = result.to_dict()
        assert "match_confidence" in d
        assert "match_method" in d


class TestCrossDomainSynthesizer:
    @pytest.fixture
    def synth(self):
        return CrossDomainSynthesizer()

    def test_entity_lookup_healthy(self, synth):
        response = synth.synthesize_entity_lookup(
            entity_type="client",
            entity_id="c1",
            entity_name="Acme Corp",
            health_data={"score": 85},
            revenue_data={"monthly_revenue": 30000, "trend": "growing"},
            trajectory_data={"velocity": 3.5},
        )
        assert "Acme Corp" in response.headline
        assert "strong" in response.headline
        assert len(response.supporting_points) >= 2
        assert response.confidence > 0

    def test_entity_lookup_critical(self, synth):
        response = synth.synthesize_entity_lookup(
            entity_type="client",
            entity_id="c2",
            entity_name="Beta Inc",
            health_data={"score": 25},
            signal_data=[
                {"severity": "CRITICAL", "description": "payment 60 days overdue"},
                {"severity": "WARNING", "description": "engagement declining"},
            ],
            trajectory_data={"velocity": -8.0},
        )
        assert "critical" in response.headline.lower()
        assert len(response.open_items) == 2
        assert len(response.suggested_actions) > 0

    def test_metric_query(self, synth):
        response = synth.synthesize_metric_query(
            metrics=["revenue", "margin"],
            data={"revenue": 60000.0, "margin": 45.0},
        )
        assert len(response.supporting_points) == 2
        assert response.confidence > 0

    def test_ranked_summary(self, synth):
        queue = [
            {
                "entity_name": "Beta Inc",
                "entity_id": "c2",
                "urgency_level": "critical",
                "reason": "payment delays",
            },
            {
                "entity_name": "Gamma LLC",
                "entity_id": "c3",
                "urgency_level": "elevated",
                "reason": "stale review",
            },
        ]
        response = synth.synthesize_ranked_summary(queue)
        assert "Beta Inc" in response.headline
        assert len(response.supporting_points) == 2

    def test_ranked_summary_empty(self, synth):
        response = synth.synthesize_ranked_summary([])
        assert "clear" in response.headline.lower()

    def test_comparison(self, synth):
        a = {"entity_name": "Acme", "health_score": 85, "monthly_revenue": 30000}
        b = {"entity_name": "Beta", "health_score": 35, "monthly_revenue": 10000}
        response = synth.synthesize_comparison(a, b)
        assert "Acme" in response.headline
        assert len(response.supporting_points) >= 2

    def test_comparison_similar(self, synth):
        a = {"entity_name": "X", "health_score": 70}
        b = {"entity_name": "Y", "health_score": 72}
        response = synth.synthesize_comparison(a, b)
        assert "similarly" in response.headline

    def test_to_dict(self, synth):
        response = synth.synthesize_entity_lookup(
            "client",
            "c1",
            "Test",
            health_data={"score": 50},
        )
        d = response.to_dict()
        assert "headline" in d
        assert "sources" in d


class TestConversationState:
    def test_update_context(self):
        state = ConversationState()
        state.update_context(
            entity_type="client",
            entity_id="c1",
            entity_name="Acme",
            query="How is Acme?",
            intent="entity_lookup",
        )
        assert state.current_entity_id == "c1"
        assert state.current_entity_name == "Acme"
        assert len(state.query_history) == 1
        assert state.last_intent == "entity_lookup"

    def test_history_limit(self):
        state = ConversationState()
        for i in range(25):
            state.update_context(query=f"query {i}")
        assert len(state.query_history) == 20

    def test_to_dict(self):
        state = ConversationState()
        d = state.to_dict()
        assert "current_entity_id" in d
        assert "query_count" in d


class TestConversationalIntelligence:
    @pytest.fixture
    def ci(self):
        registry = [
            {"entity_type": "client", "entity_id": "c1", "entity_name": "Acme Corporation"},
            {"entity_type": "client", "entity_id": "c2", "entity_name": "Beta Industries"},
            {"entity_type": "project", "entity_id": "p1", "entity_name": "Brand Refresh"},
        ]
        return ConversationalIntelligence(entity_registry=registry)

    def test_entity_lookup_query(self, ci):
        result = ci.process_query(
            "How is Client Acme Corporation doing?",
            context={
                "entity_data": {
                    "health": {"score": 80},
                    "revenue": {"monthly_revenue": 25000, "trend": "stable"},
                },
            },
        )
        assert result["intent"]["intent_type"] == INTENT_ENTITY_LOOKUP
        assert len(result["entities"]) >= 1
        assert "response" in result

    def test_ranked_summary_query(self, ci):
        result = ci.process_query(
            "What should I focus on this week?",
            context={
                "attention_queue": [
                    {"entity_name": "Beta", "urgency_level": "high", "reason": "declining health"},
                ],
            },
        )
        assert result["intent"]["intent_type"] == INTENT_RANKED_SUMMARY
        assert "response" in result

    def test_action_request_creates_card(self, ci):
        result = ci.process_query(
            "Draft an email to Client Acme Corporation about the project update",
        )
        assert result["intent"]["intent_type"] == INTENT_ACTION_REQUEST
        assert "action" in result
        assert result["action"]["action_type"] == "email"

    def test_conversation_context_maintained(self, ci):
        # First query establishes context
        ci.process_query("How is Client Acme Corporation?")
        assert ci.state.current_entity_name == "Acme Corporation"

        # Second query uses context (no entity mentioned)
        ci.process_query("What about their invoices?")
        # Should use context entity
        assert ci.state.current_entity_id == "c1"

    def test_metric_query(self, ci):
        result = ci.process_query(
            "What's my revenue this month?",
            context={"metric_data": {"revenue": 60000.0}},
        )
        assert result["intent"]["intent_type"] == INTENT_METRIC_QUERY
        assert "response" in result

    def test_state_in_result(self, ci):
        result = ci.process_query("How is Client Acme Corporation?")
        assert "state" in result
        assert result["state"]["current_entity_id"] == "c1"
