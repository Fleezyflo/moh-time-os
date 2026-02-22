# DQ-3.1: Quality-Weighted Confidence

## Objective

Wire data quality scores into every intelligence output as a confidence modifier. A signal detected on high-quality data should have higher confidence than the same signal detected on sparse data.

## Dependencies

- DQ-1.1 (freshness tracker)
- DQ-2.1 (completeness scorer)
- Brief 18 ID-1.1 (correlation confidence already exists — this enhances it)

## Deliverables

### Confidence adjustment formula

For any intelligence output (signal, pattern, score, proposal):

```
adjusted_confidence = raw_confidence × quality_modifier

where quality_modifier = max(0.3, data_quality_score)
```

Floor of 0.3 ensures we never show zero confidence — even poor data can surface real issues.

### Integration points

1. **Signals** (`signals.py`): `DetectedSignal` gets a `data_quality` field. In `evaluate_signal()`, after detection, fetch entity quality score and multiply confidence.

2. **Patterns** (`patterns.py`): `PatternEvidence` gets a `data_quality` field. Pattern confidence adjusted by worst data quality score among involved entities.

3. **Proposals** (`proposals.py`): `Proposal` priority score adjusted by data quality. Low-quality proposals rank lower.

4. **Scorecards** (`scorecard.py`): Already has `data_completeness`. Ensure this now uses the DQ-2.1 quality scorer instead of the simplistic calculation.

5. **Entity Profiles** (ID-3.1): Profile includes `data_quality` section showing per-domain quality.

### New file: `lib/intelligence/confidence.py`

```python
class ConfidenceAdjuster:
    """Adjusts intelligence confidence based on data quality."""

    FLOOR = 0.3  # minimum confidence modifier

    def __init__(self, db_path: Path): ...

    def adjust_signal_confidence(self, signal: dict, entity_type: str, entity_id: str) -> dict:
        """Adjust signal confidence based on entity data quality."""

    def adjust_pattern_confidence(self, pattern: dict, entities: list[tuple[str,str]]) -> dict:
        """Adjust pattern confidence based on worst-entity data quality."""

    def adjust_proposal_priority(self, proposal: dict) -> dict:
        """Adjust proposal priority based on data quality of involved entities."""

    def get_confidence_context(self, entity_type: str, entity_id: str) -> dict:
        """Return quality context for an entity to include in API responses.
        Returns: { quality_score, freshness, domains, gaps, modifier }
        """
```

### Display in API

Every intelligence API response (from Brief 26) includes quality context:
```json
{
  "data": { ... },
  "meta": {
    "computed_at": "...",
    "data_quality": {
      "quality_score": 0.73,
      "confidence_modifier": 0.73,
      "stale_sources": ["calendar"],
      "gaps": ["No calendar events"]
    }
  }
}
```

## Validation

- Signal on high-quality entity has higher confidence than same signal on low-quality entity
- Pattern involving low-quality entity has reduced confidence
- Proposal priority drops proportionally with data quality
- Floor of 0.3 prevents zero confidence
- API responses include quality context
- Scorecard uses new quality scorer

## Estimated Effort

~200 lines
