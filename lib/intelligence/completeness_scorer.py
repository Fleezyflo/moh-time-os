"""
Data Completeness Scorer — MOH TIME OS

Evaluates how complete the data is for each entity across expected fields
and sources. Identifies gaps and computes completeness scores.

Brief 27 (DQ), Task DQ-2.1
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Expected data fields by entity type
EXPECTED_FIELDS = {
    "client": {
        "required": [
            "name",
            "health_score",
            "revenue",
            "active_projects",
        ],
        "optional": [
            "last_communication",
            "satisfaction_score",
            "contract_end",
            "primary_contact",
            "industry",
        ],
    },
    "project": {
        "required": [
            "name",
            "client_id",
            "status",
            "budget",
        ],
        "optional": [
            "deadline",
            "team_members",
            "hours_logged",
            "completion_pct",
            "scope_changes",
        ],
    },
    "person": {
        "required": [
            "name",
            "role",
            "email",
        ],
        "optional": [
            "utilization",
            "active_projects",
            "last_activity",
            "capacity_hours",
        ],
    },
}

# Expected data sources by entity type
EXPECTED_SOURCES = {
    "client": ["harvest", "email", "project_mgmt"],
    "project": ["harvest", "project_mgmt"],
    "person": ["harvest", "email"],
}


@dataclass
class FieldCompleteness:
    """Completeness status for one field."""

    field_name: str
    is_present: bool
    is_required: bool
    value_quality: str = "unknown"  # 'good' | 'empty' | 'stale' | 'unknown'

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "is_present": self.is_present,
            "is_required": self.is_required,
            "value_quality": self.value_quality,
        }


@dataclass
class CompletenessScore:
    """Completeness assessment for an entity."""

    entity_type: str
    entity_id: str
    overall_score: float  # 0.0 to 1.0
    required_score: float  # Completeness of required fields only
    optional_score: float  # Completeness of optional fields
    source_coverage: float  # % of expected sources present
    fields: list[FieldCompleteness]
    missing_required: list[str]
    missing_optional: list[str]
    missing_sources: list[str]

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "overall_score": round(self.overall_score, 4),
            "required_score": round(self.required_score, 4),
            "optional_score": round(self.optional_score, 4),
            "source_coverage": round(self.source_coverage, 4),
            "missing_required": self.missing_required,
            "missing_optional": self.missing_optional,
            "missing_sources": self.missing_sources,
        }


class CompletenessScorer:
    """Evaluates data completeness for entities."""

    def __init__(
        self,
        expected_fields: dict[str, dict[str, list[str]]] | None = None,
        expected_sources: dict[str, list[str]] | None = None,
    ):
        self.expected_fields = expected_fields or EXPECTED_FIELDS
        self.expected_sources = expected_sources or EXPECTED_SOURCES

    def score_entity(
        self,
        entity_type: str,
        entity_id: str,
        present_fields: dict[str, Any],
        present_sources: list[str] | None = None,
    ) -> CompletenessScore:
        """
        Score completeness of an entity's data.

        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            present_fields: Dict of field_name -> value (None means field exists but empty)
            present_sources: List of data sources that have data for this entity
        """
        field_spec = self.expected_fields.get(entity_type, {"required": [], "optional": []})
        required = field_spec.get("required", [])
        optional = field_spec.get("optional", [])

        fields = []
        missing_required = []
        missing_optional = []

        # Check required fields
        for f in required:
            is_present = f in present_fields and present_fields[f] is not None
            quality = "good" if is_present else "empty"
            fields.append(
                FieldCompleteness(
                    field_name=f,
                    is_present=is_present,
                    is_required=True,
                    value_quality=quality,
                )
            )
            if not is_present:
                missing_required.append(f)

        # Check optional fields
        for f in optional:
            is_present = f in present_fields and present_fields[f] is not None
            quality = "good" if is_present else "empty"
            fields.append(
                FieldCompleteness(
                    field_name=f,
                    is_present=is_present,
                    is_required=False,
                    value_quality=quality,
                )
            )
            if not is_present:
                missing_optional.append(f)

        # Compute scores
        required_present = len(required) - len(missing_required)
        required_score = required_present / len(required) if required else 1.0

        optional_present = len(optional) - len(missing_optional)
        optional_score = optional_present / len(optional) if optional else 1.0

        # Overall: required fields weighted 70%, optional 30%
        overall = (required_score * 0.7) + (optional_score * 0.3)

        # Source coverage
        expected_src = self.expected_sources.get(entity_type, [])
        present_src = present_sources or []
        missing_sources = [s for s in expected_src if s not in present_src]
        source_coverage = (
            (len(expected_src) - len(missing_sources)) / len(expected_src) if expected_src else 1.0
        )

        return CompletenessScore(
            entity_type=entity_type,
            entity_id=entity_id,
            overall_score=overall,
            required_score=required_score,
            optional_score=optional_score,
            source_coverage=source_coverage,
            fields=fields,
            missing_required=missing_required,
            missing_optional=missing_optional,
            missing_sources=missing_sources,
        )

    def score_batch(
        self,
        entities: list[dict[str, Any]],
    ) -> list[CompletenessScore]:
        """
        Score completeness for a batch of entities.

        Each entity dict must have: entity_type, entity_id, fields, sources (optional)
        """
        results = []
        for entity in entities:
            score = self.score_entity(
                entity_type=entity["entity_type"],
                entity_id=entity["entity_id"],
                present_fields=entity.get("fields", {}),
                present_sources=entity.get("sources"),
            )
            results.append(score)

        results.sort(key=lambda s: s.overall_score)
        return results

    def get_gap_report(
        self,
        scores: list[CompletenessScore],
    ) -> dict[str, Any]:
        """Generate gap report from completeness scores."""
        total = len(scores)
        if total == 0:
            return {
                "total_entities": 0,
                "avg_completeness": 0.0,
                "fully_complete": 0,
                "missing_required_count": 0,
                "common_missing_fields": {},
            }

        avg = sum(s.overall_score for s in scores) / total
        fully_complete = sum(1 for s in scores if s.overall_score >= 0.99)
        missing_req = sum(1 for s in scores if s.missing_required)

        # Most commonly missing fields
        field_gaps: dict[str, int] = {}
        for s in scores:
            for f in s.missing_required:
                field_gaps[f] = field_gaps.get(f, 0) + 1
            for f in s.missing_optional:
                field_gaps[f] = field_gaps.get(f, 0) + 1

        sorted_gaps = sorted(field_gaps.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_entities": total,
            "avg_completeness": round(avg, 4),
            "fully_complete": fully_complete,
            "missing_required_count": missing_req,
            "common_missing_fields": dict(sorted_gaps[:10]),
        }
