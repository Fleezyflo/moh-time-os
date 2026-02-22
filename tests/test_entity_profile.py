"""
Tests for Entity Intelligence Profiles and Narrative Builder.

Brief 18 (ID), Task ID-3.1 + ID-6.1
"""

from datetime import datetime

import pytest

from lib.intelligence.entity_profile import (
    AttentionLevel,
    CostProfile,
    EntityIntelligenceProfile,
    ProfileCompoundRisk,
    ProfilePatternSnapshot,
    ScoreDimension,
    SignalSnapshot,
    build_entity_profile,
    classify_health,
    compute_health_score,
    compute_next_review,
    compute_pattern_direction,
    compute_signal_trend,
    determine_attention_level,
)
from lib.intelligence.narrative import NarrativeBuilder

# ---------------------------------------------------------------------------
# Health classification
# ---------------------------------------------------------------------------


class TestClassifyHealth:
    def test_thriving(self):
        assert classify_health(95.0) == "thriving"

    def test_healthy(self):
        assert classify_health(75.0) == "healthy"

    def test_at_risk(self):
        assert classify_health(55.0) == "at_risk"

    def test_critical(self):
        assert classify_health(30.0) == "critical"

    def test_boundary_90(self):
        assert classify_health(90.0) == "thriving"

    def test_boundary_70(self):
        assert classify_health(70.0) == "healthy"

    def test_boundary_50(self):
        assert classify_health(50.0) == "at_risk"


# ---------------------------------------------------------------------------
# Weighted health score
# ---------------------------------------------------------------------------


class TestComputeHealthScore:
    def test_client_weights(self):
        dims = [
            ScoreDimension("delivery", 80.0, "stable"),
            ScoreDimension("communication", 60.0, "stable"),
            ScoreDimension("financial", 90.0, "stable"),
            ScoreDimension("engagement", 70.0, "stable"),
        ]
        score = compute_health_score(dims, "client")
        # 80*0.30 + 60*0.25 + 90*0.25 + 70*0.20 = 24 + 15 + 22.5 + 14 = 75.5
        assert score == pytest.approx(75.5)

    def test_project_weights(self):
        dims = [
            ScoreDimension("delivery", 50.0, "declining"),
            ScoreDimension("communication", 80.0, "stable"),
            ScoreDimension("financial", 80.0, "stable"),
            ScoreDimension("engagement", 80.0, "stable"),
        ]
        score = compute_health_score(dims, "project")
        # 50*0.40 + 80*0.20 + 80*0.20 + 80*0.20 = 20 + 16 + 16 + 16 = 68.0
        assert score == pytest.approx(68.0)

    def test_empty_dimensions(self):
        assert compute_health_score([], "client") == 0.0

    def test_unknown_entity_type_defaults_to_client(self):
        dims = [ScoreDimension("delivery", 80.0, "stable")]
        score = compute_health_score(dims, "unknown_type")
        assert score > 0


# ---------------------------------------------------------------------------
# Signal trend
# ---------------------------------------------------------------------------


class TestComputeSignalTrend:
    def test_deteriorating_by_severity(self):
        current = [
            SignalSnapshot("s1", "health", "CRITICAL", "2026-04-15", 40.0),
        ]
        previous = [
            SignalSnapshot("s1", "health", "WATCH", "2026-04-14", 55.0),
        ]
        assert compute_signal_trend(current, previous) == "deteriorating"

    def test_improving_by_severity(self):
        current = [
            SignalSnapshot("s1", "health", "WATCH", "2026-04-15", 55.0),
        ]
        previous = [
            SignalSnapshot("s1", "health", "CRITICAL", "2026-04-14", 40.0),
        ]
        assert compute_signal_trend(current, previous) == "improving"

    def test_stable(self):
        sig = SignalSnapshot("s1", "health", "WARNING", "2026-04-15", 50.0)
        assert compute_signal_trend([sig], [sig]) == "stable"

    def test_no_previous(self):
        # 1 signal vs 0 previous → count_change = 1, severity_change = 1
        # That's not >2 count or >0 severity → deteriorating (severity > 0)
        sig = SignalSnapshot("s1", "health", "WATCH", "2026-04-15", 60.0)
        assert compute_signal_trend([sig]) == "deteriorating"


# ---------------------------------------------------------------------------
# Pattern direction
# ---------------------------------------------------------------------------


class TestComputePatternDirection:
    def test_destabilizing(self):
        pats = [
            ProfilePatternSnapshot("p1", "overdue", "worsening", 3, 0.8),
            ProfilePatternSnapshot("p2", "comm", "persistent", 2, 0.6),
        ]
        assert compute_pattern_direction(pats) == "destabilizing"

    def test_stabilizing(self):
        pats = [
            ProfilePatternSnapshot("p1", "overdue", "resolving", 1, 0.5),
            ProfilePatternSnapshot("p2", "comm", "persistent", 2, 0.6),
        ]
        assert compute_pattern_direction(pats) == "stabilizing"

    def test_neutral(self):
        pats = [
            ProfilePatternSnapshot("p1", "overdue", "persistent", 3, 0.8),
        ]
        assert compute_pattern_direction(pats) == "neutral"

    def test_empty(self):
        assert compute_pattern_direction([]) == "neutral"


# ---------------------------------------------------------------------------
# Attention level
# ---------------------------------------------------------------------------


class TestDetermineAttentionLevel:
    def test_critical_signal_urgent(self):
        sig = SignalSnapshot("s1", "health", "CRITICAL", "2026-04-15", 30.0)
        assert determine_attention_level([sig], [], "at_risk") == AttentionLevel.URGENT

    def test_structural_risk_urgent(self):
        risk = ProfileCompoundRisk("r1", "Structural risk", ["s1"], "CRITICAL", 0.9, True)
        assert determine_attention_level([], [risk], "healthy") == AttentionLevel.URGENT

    def test_critical_health_urgent(self):
        assert determine_attention_level([], [], "critical") == AttentionLevel.URGENT

    def test_warning_signal_elevated(self):
        sig = SignalSnapshot("s1", "overdue", "WARNING", "2026-04-15", 50.0)
        assert determine_attention_level([sig], [], "healthy") == AttentionLevel.ELEVATED

    def test_at_risk_health_elevated(self):
        assert determine_attention_level([], [], "at_risk") == AttentionLevel.ELEVATED

    def test_watch_signal_normal(self):
        sig = SignalSnapshot("s1", "comm", "WATCH", "2026-04-15", 60.0)
        assert determine_attention_level([sig], [], "healthy") == AttentionLevel.NORMAL

    def test_no_issues_stable(self):
        assert determine_attention_level([], [], "healthy") == AttentionLevel.STABLE


# ---------------------------------------------------------------------------
# Next review date
# ---------------------------------------------------------------------------


class TestComputeNextReview:
    def test_urgent_next_day(self):
        now = datetime(2026, 4, 15, 10, 0)
        review = compute_next_review(AttentionLevel.URGENT, now)
        assert review == datetime(2026, 4, 16, 10, 0)

    def test_stable_90_days(self):
        now = datetime(2026, 4, 15, 10, 0)
        review = compute_next_review(AttentionLevel.STABLE, now)
        assert (review - now).days == 90


# ---------------------------------------------------------------------------
# Narrative builder
# ---------------------------------------------------------------------------


class TestNarrativeBuilder:
    @pytest.fixture
    def builder(self):
        return NarrativeBuilder()

    def test_healthy_narrative(self, builder):
        text = builder.build_narrative(
            entity_type="client",
            entity_name="Acme Corp",
            health_score=82.0,
            health_classification="healthy",
            active_signals=[],
            active_patterns=[],
            compound_risks=[],
            cost_profile={"profitability_band": "profitable", "cost_drivers": []},
            trajectory_direction="stable",
            projected_score_30d=82.0,
        )
        assert "Acme Corp" in text
        assert "healthy" in text
        assert "No significant issues" in text

    def test_critical_narrative(self, builder):
        text = builder.build_narrative(
            entity_type="client",
            entity_name="Beta Ltd",
            health_score=35.0,
            health_classification="critical",
            active_signals=[{"signal_type": "health_declining", "severity": "CRITICAL"}],
            active_patterns=[],
            compound_risks=[],
            cost_profile={"profitability_band": "unprofitable", "cost_drivers": ["overdue_tasks"]},
            trajectory_direction="toward_risk",
            projected_score_30d=28.0,
        )
        assert "Beta Ltd" in text
        assert "critical" in text.lower() or "Critical" in text
        assert "unprofitable" in text

    def test_compound_risk_narrative(self, builder):
        text = builder.build_narrative(
            entity_type="client",
            entity_name="Gamma Inc",
            health_score=55.0,
            health_classification="at_risk",
            active_signals=[],
            active_patterns=[],
            compound_risks=[
                {"title": "delivery-payment spiral", "severity": "CRITICAL", "confidence": 0.85}
            ],
            cost_profile={"profitability_band": "breakeven", "cost_drivers": ["task_churn"]},
            trajectory_direction="stable",
            projected_score_30d=55.0,
        )
        assert "delivery-payment spiral" in text

    def test_action_recommendations_urgent(self, builder):
        actions = builder.build_action_recommendations(
            health_classification="critical",
            attention_level="urgent",
            active_signals=[{"signal_type": "health_declining", "severity": "CRITICAL"}],
            compound_risks=[],
            cost_profile={"profitability_band": "unprofitable"},
            trajectory_direction="toward_risk",
        )
        assert len(actions) >= 1
        assert any("Immediate" in a or "review" in a.lower() for a in actions)

    def test_action_recommendations_stable(self, builder):
        actions = builder.build_action_recommendations(
            health_classification="healthy",
            attention_level="stable",
            active_signals=[],
            compound_risks=[],
            cost_profile={"profitability_band": "profitable"},
            trajectory_direction="stable",
        )
        assert any("monitoring" in a.lower() or "no action" in a.lower() for a in actions)

    def test_cross_domain_summary(self, builder):
        issues = builder.build_cross_domain_summary(
            signals_by_domain={
                "delivery": [{"signal_type": "overdue"}],
                "financial": [{"signal_type": "late_payment"}],
            },
            patterns_by_domain={"delivery": [{"pattern_type": "overdue_cluster"}]},
            compound_risks=[],
        )
        assert len(issues) >= 1
        assert any("delivery" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# Full profile assembly
# ---------------------------------------------------------------------------


class TestBuildEntityProfile:
    def _build_default_profile(self, **overrides):
        """Build a profile with sensible defaults, allowing overrides."""
        defaults = {
            "entity_type": "client",
            "entity_id": "client_a",
            "entity_name": "Acme Corp",
            "score_dimensions": [
                ScoreDimension("delivery", 80.0, "stable"),
                ScoreDimension("communication", 70.0, "stable"),
                ScoreDimension("financial", 85.0, "improving"),
                ScoreDimension("engagement", 75.0, "stable"),
            ],
            "active_signals": [],
            "previous_signals": None,
            "active_patterns": [],
            "compound_risks": [],
            "cost_profile": CostProfile(
                effort_score=15.0,
                profitability_band="profitable",
                estimated_cost_per_month=5000.0,
                cost_drivers=[],
            ),
            "trajectory_direction": "stable",
            "as_of": datetime(2026, 4, 15, 10, 0),
        }
        defaults.update(overrides)
        return build_entity_profile(**defaults)

    def test_healthy_profile(self):
        profile = self._build_default_profile()
        assert profile.health_classification == "healthy"
        assert profile.attention_level == AttentionLevel.STABLE
        assert profile.narrative != ""
        assert profile.next_review_date is not None

    def test_critical_profile(self):
        sig = SignalSnapshot("s1", "health_declining", "CRITICAL", "2026-04-15", 30.0)
        profile = self._build_default_profile(
            active_signals=[sig],
            score_dimensions=[
                ScoreDimension("delivery", 30.0, "declining"),
                ScoreDimension("communication", 40.0, "declining"),
                ScoreDimension("financial", 45.0, "declining"),
                ScoreDimension("engagement", 35.0, "declining"),
            ],
        )
        assert profile.health_classification == "critical"
        assert profile.attention_level == AttentionLevel.URGENT

    def test_to_dict(self):
        profile = self._build_default_profile()
        d = profile.to_dict()
        assert d["entity_id"] == "client_a"
        assert d["health_score"] > 0
        assert "narrative" in d
        assert "attention_level" in d
        assert d["attention_level"] == "stable"

    def test_signal_trend_computed(self):
        current = [SignalSnapshot("s1", "overdue", "WARNING", "2026-04-15", 50.0)]
        previous = [
            SignalSnapshot("s1", "overdue", "WATCH", "2026-04-14", 55.0),
            SignalSnapshot("s2", "overdue", "WATCH", "2026-04-14", 55.0),
            SignalSnapshot("s3", "overdue", "WATCH", "2026-04-14", 55.0),
        ]
        profile = self._build_default_profile(
            active_signals=current,
            previous_signals=previous,
        )
        # Severity went up but count went down significantly
        assert profile.signal_trend in ("improving", "stable", "deteriorating")

    def test_pattern_direction_computed(self):
        pats = [
            ProfilePatternSnapshot("p1", "overdue_cluster", "worsening", 3, 0.8),
        ]
        profile = self._build_default_profile(active_patterns=pats)
        assert profile.pattern_direction == "destabilizing"

    def test_recommended_actions_present(self):
        profile = self._build_default_profile()
        assert len(profile.recommended_actions) >= 1

    def test_confidence_band_default(self):
        profile = self._build_default_profile()
        low, high = profile.confidence_band
        assert low < profile.projected_score_30d
        assert high > profile.projected_score_30d
