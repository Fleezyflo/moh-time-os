"""
Tests for CompletenessScorer — data completeness evaluation.

Brief 27 (DQ), Task DQ-2.1
"""

import pytest

from lib.intelligence.completeness_scorer import (
    CompletenessScorer,
    FieldCompleteness,
)


@pytest.fixture
def scorer():
    return CompletenessScorer()


class TestScoreEntity:
    def test_fully_complete_client(self, scorer):
        fields = {
            "name": "Acme Corp",
            "health_score": 85,
            "revenue": 50000,
            "active_projects": 3,
            "last_communication": "2026-02-20",
            "satisfaction_score": 4.5,
            "contract_end": "2026-12-31",
            "primary_contact": "Jane",
            "industry": "tech",
        }
        score = scorer.score_entity("client", "c1", fields, ["harvest", "email", "project_mgmt"])
        assert score.overall_score >= 0.99
        assert score.required_score == 1.0
        assert score.optional_score == 1.0
        assert score.source_coverage == 1.0
        assert score.missing_required == []
        assert score.missing_optional == []

    def test_missing_required_fields(self, scorer):
        fields = {"name": "Acme Corp"}  # Missing health_score, revenue, active_projects
        score = scorer.score_entity("client", "c1", fields)
        assert score.required_score == pytest.approx(0.25)  # 1/4
        assert len(score.missing_required) == 3
        assert "health_score" in score.missing_required

    def test_missing_optional_fields(self, scorer):
        fields = {
            "name": "Acme",
            "health_score": 80,
            "revenue": 30000,
            "active_projects": 2,
        }
        score = scorer.score_entity("client", "c1", fields)
        assert score.required_score == 1.0
        assert score.optional_score == 0.0  # All optional missing
        # Overall = 0.7 * 1.0 + 0.3 * 0.0 = 0.7
        assert score.overall_score == pytest.approx(0.7)

    def test_none_values_count_as_missing(self, scorer):
        fields = {
            "name": "Acme",
            "health_score": None,
            "revenue": 30000,
            "active_projects": 2,
        }
        score = scorer.score_entity("client", "c1", fields)
        assert "health_score" in score.missing_required

    def test_source_coverage(self, scorer):
        fields = {"name": "Acme", "health_score": 80, "revenue": 30000, "active_projects": 2}
        # Client expects harvest, email, project_mgmt (3 sources)
        score = scorer.score_entity("client", "c1", fields, ["harvest"])
        assert score.source_coverage == pytest.approx(1 / 3, abs=0.01)
        assert "email" in score.missing_sources
        assert "project_mgmt" in score.missing_sources

    def test_unknown_entity_type(self, scorer):
        fields = {"name": "Unknown"}
        score = scorer.score_entity("widget", "w1", fields)
        # No expected fields → everything is 1.0
        assert score.required_score == 1.0
        assert score.optional_score == 1.0

    def test_to_dict(self, scorer):
        fields = {"name": "Acme", "health_score": 80, "revenue": 30000, "active_projects": 2}
        score = scorer.score_entity("client", "c1", fields)
        d = score.to_dict()
        assert "overall_score" in d
        assert "missing_required" in d
        assert "source_coverage" in d


class TestProjectCompleteness:
    def test_project_complete(self, scorer):
        fields = {
            "name": "Website Redesign",
            "client_id": "c1",
            "status": "active",
            "budget": 50000,
            "deadline": "2026-06-01",
            "team_members": 5,
            "hours_logged": 120,
            "completion_pct": 45,
            "scope_changes": 2,
        }
        score = scorer.score_entity("project", "p1", fields, ["harvest", "project_mgmt"])
        assert score.overall_score >= 0.99
        assert score.source_coverage == 1.0


class TestScoreBatch:
    def test_batch_scoring(self, scorer):
        entities = [
            {
                "entity_type": "client",
                "entity_id": "c1",
                "fields": {"name": "A", "health_score": 80, "revenue": 30000, "active_projects": 2},
            },
            {
                "entity_type": "client",
                "entity_id": "c2",
                "fields": {"name": "B"},
            },
        ]
        scores = scorer.score_batch(entities)
        assert len(scores) == 2
        # Sorted by overall_score ascending
        assert scores[0].overall_score <= scores[1].overall_score

    def test_batch_empty(self, scorer):
        scores = scorer.score_batch([])
        assert scores == []


class TestGapReport:
    def test_gap_report(self, scorer):
        entities = [
            {
                "entity_type": "client",
                "entity_id": "c1",
                "fields": {"name": "A", "health_score": 80, "revenue": 30000, "active_projects": 2},
            },
            {
                "entity_type": "client",
                "entity_id": "c2",
                "fields": {"name": "B"},
            },
        ]
        scores = scorer.score_batch(entities)
        report = scorer.get_gap_report(scores)
        assert report["total_entities"] == 2
        assert report["avg_completeness"] > 0
        assert report["missing_required_count"] >= 1
        assert "health_score" in report["common_missing_fields"]

    def test_gap_report_empty(self, scorer):
        report = scorer.get_gap_report([])
        assert report["total_entities"] == 0
        assert report["avg_completeness"] == 0.0


class TestFieldCompleteness:
    def test_to_dict(self):
        f = FieldCompleteness(
            field_name="revenue",
            is_present=True,
            is_required=True,
            value_quality="good",
        )
        d = f.to_dict()
        assert d["field_name"] == "revenue"
        assert d["is_present"] is True
