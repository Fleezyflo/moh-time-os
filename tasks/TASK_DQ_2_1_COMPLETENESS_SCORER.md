# DQ-2.1: Entity Completeness Scorer

## Objective

Score how complete the data coverage is for each entity across all expected dimensions. A client should have tasks, communications, invoices, calendar events, and projects. If any dimension is missing, the completeness score drops and intelligence confidence should reflect that.

## What Exists

- `scoring.py` has `data_completeness` as a float in scorecard output — but it's just "fraction of non-null dimension scores"
- No per-domain completeness tracking exists
- No expectations model (what data SHOULD exist for a client)

## Deliverables

### New file: `lib/intelligence/data_quality.py`

```python
class DataExpectation:
    """What data we expect to exist for an entity type."""
    domain: str           # 'tasks', 'communications', 'invoices', 'calendar', 'projects'
    weight: float         # importance for completeness score (0.0-1.0)
    min_records: int      # minimum records expected for "complete"
    max_age_days: int     # max age of most recent record before "stale"

# Expected data domains per entity type
CLIENT_EXPECTATIONS = [
    DataExpectation("tasks", weight=0.25, min_records=1, max_age_days=30),
    DataExpectation("communications", weight=0.25, min_records=5, max_age_days=14),
    DataExpectation("invoices", weight=0.20, min_records=1, max_age_days=90),
    DataExpectation("calendar_events", weight=0.15, min_records=1, max_age_days=30),
    DataExpectation("projects", weight=0.15, min_records=1, max_age_days=90),
]

PROJECT_EXPECTATIONS = [
    DataExpectation("tasks", weight=0.40, min_records=1, max_age_days=14),
    DataExpectation("communications", weight=0.20, min_records=1, max_age_days=30),
    DataExpectation("team_members", weight=0.20, min_records=1, max_age_days=90),
    DataExpectation("milestones", weight=0.20, min_records=0, max_age_days=90),
]

PERSON_EXPECTATIONS = [
    DataExpectation("tasks", weight=0.35, min_records=1, max_age_days=14),
    DataExpectation("calendar_events", weight=0.25, min_records=1, max_age_days=7),
    DataExpectation("communications", weight=0.25, min_records=1, max_age_days=14),
    DataExpectation("projects", weight=0.15, min_records=1, max_age_days=30),
]


class DataQualityScorer:
    """Scores data completeness and quality per entity."""

    def __init__(self, db_path: Path): ...

    def score_entity(self, entity_type: str, entity_id: str) -> dict:
        """
        Returns:
        {
            "entity_type": "client",
            "entity_id": "abc",
            "overall_quality": 0.73,       # weighted average of domain scores
            "domains": {
                "tasks": { "score": 0.9, "record_count": 45, "newest_age_days": 2, "status": "good" },
                "communications": { "score": 0.8, "record_count": 120, "newest_age_days": 1, "status": "good" },
                "invoices": { "score": 0.4, "record_count": 1, "newest_age_days": 85, "status": "stale" },
                "calendar_events": { "score": 0.0, "record_count": 0, "newest_age_days": null, "status": "missing" },
                "projects": { "score": 1.0, "record_count": 3, "newest_age_days": 5, "status": "good" }
            },
            "gaps": ["No calendar events found", "Invoice data is stale (85 days old)"],
            "confidence_modifier": 0.73    # same as overall_quality — used to adjust intelligence confidence
        }
        """

    def score_all(self, entity_type: str) -> list[dict]:
        """Score all entities of a type. Returns list sorted by quality (worst first)."""

    def get_quality_summary(self) -> dict:
        """Portfolio-level data quality summary.
        Returns: { entity_type: { avg_quality, min_quality, entities_below_50pct, worst_entities } }
        """
```

### Domain score calculation

For each domain:
- `record_count >= min_records` AND `newest_age_days <= max_age_days` → score = 1.0
- `record_count >= min_records` AND `newest_age_days > max_age_days` → score = max(0.3, 1.0 - (age - max_age) / max_age)
- `record_count > 0` AND `< min_records` → score = record_count / min_records
- `record_count == 0` → score = 0.0

Overall quality = Σ(domain_score × domain_weight)

### Integration with intelligence scoring

In `lib/intelligence/scorecard.py`, `_build_scorecard()` currently computes `data_completeness` simplistically. Replace with a call to `DataQualityScorer.score_entity()` and use `overall_quality` as the `data_completeness` value. The `confidence_modifier` is stored alongside the score for downstream use.

## Validation

- Entity with full data coverage scores > 0.8
- Entity with no communications scores < 0.6
- Entity with zero records across all domains scores 0.0
- Score correctly weights domains by importance
- Stale data reduces domain score gradually
- Portfolio summary identifies worst entities
- Integration with scorecard replaces old data_completeness

## Estimated Effort

~300 lines
