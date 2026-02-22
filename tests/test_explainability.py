"""
Tests for IntelligenceExplainer — output explanations.

Brief 28 (IO), Task IO-2.1
"""

import pytest

from lib.intelligence.explainability import (
    Explanation,
    ExplanationFactor,
    IntelligenceExplainer,
)


@pytest.fixture
def explainer():
    return IntelligenceExplainer()


class TestExplainHealthScore:
    def test_basic_explanation(self, explainer):
        dims = [
            {"dimension": "delivery", "score": 80, "trend": "stable"},
            {"dimension": "communication", "score": 70, "trend": "improving"},
            {"dimension": "financial", "score": 90, "trend": "stable"},
        ]
        weights = {"delivery": 0.4, "communication": 0.3, "financial": 0.3}

        result = explainer.explain_health_score("Acme Corp", 80.0, dims, weights)
        assert result.output_type == "health_score"
        assert result.output_value == 80.0
        assert len(result.factors) == 3
        assert "Acme Corp" in result.summary

    def test_factors_sorted_by_contribution(self, explainer):
        dims = [
            {"dimension": "delivery", "score": 80, "trend": "stable"},
            {"dimension": "communication", "score": 70, "trend": "stable"},
        ]
        weights = {"delivery": 0.7, "communication": 0.3}

        result = explainer.explain_health_score("Test", 77.0, dims, weights)
        assert result.factors[0].contribution >= result.factors[1].contribution

    def test_to_dict(self, explainer):
        dims = [{"dimension": "delivery", "score": 80, "trend": "stable"}]
        weights = {"delivery": 0.5}
        result = explainer.explain_health_score("Test", 80.0, dims, weights)
        d = result.to_dict()
        assert "factors" in d
        assert "summary" in d


class TestExplainSignal:
    def test_basic_signal(self, explainer):
        result = explainer.explain_signal(
            signal_type="health_declining",
            severity="warning",
            entity_name="Acme Corp",
            trigger_value=45.0,
            threshold=50.0,
        )
        assert result.output_type == "signal"
        assert "WARNING" in result.summary
        assert "health_declining" in result.summary

    def test_with_contributing_data(self, explainer):
        contributing = [
            {"description": "Revenue dropped 20%", "weight": 0.4, "value": -20},
            {"description": "3 overdue tasks", "weight": 0.3, "value": 3},
        ]
        result = explainer.explain_signal(
            signal_type="health_declining",
            severity="critical",
            entity_name="Test",
            trigger_value=30.0,
            threshold=40.0,
            contributing_data=contributing,
        )
        assert len(result.factors) == 3  # threshold + 2 contributing


class TestExplainAttentionLevel:
    def test_urgent_with_critical_signal(self, explainer):
        signals = [{"severity": "CRITICAL", "signal_type": "health_declining"}]
        result = explainer.explain_attention_level("urgent", "Acme", "critical", signals, [])
        assert any("CRITICAL" in f.description for f in result.factors)

    def test_stable_no_signals(self, explainer):
        result = explainer.explain_attention_level("stable", "Acme", "healthy", [], [])
        assert any("STABLE" in f.description for f in result.factors)

    def test_elevated_with_warnings(self, explainer):
        signals = [
            {"severity": "WARNING", "signal_type": "overdue"},
            {"severity": "WARNING", "signal_type": "comm_drop"},
        ]
        result = explainer.explain_attention_level("elevated", "Acme", "at_risk", signals, [])
        assert any("WARNING" in f.description for f in result.factors)


class TestExplainRecommendation:
    def test_basic_recommendation(self, explainer):
        result = explainer.explain_recommendation(
            "Schedule check-in: health trending downward",
            ["Health score declining for 3 weeks", "No recent communication"],
        )
        assert result.output_type == "recommendation"
        assert len(result.factors) == 2

    def test_empty_conditions(self, explainer):
        result = explainer.explain_recommendation("Continue monitoring", [])
        assert len(result.factors) == 0


class TestExplanationFactor:
    def test_to_dict(self):
        f = ExplanationFactor(
            factor_type="threshold",
            description="Test factor",
            contribution=0.7,
            value=42,
            comparison="above 30",
        )
        d = f.to_dict()
        assert d["contribution"] == 0.7
        assert d["value"] == 42
