# DQ-5.1: Data Quality Validation

## Objective

End-to-end test suite validating the entire data quality pipeline from freshness tracking through confidence adjustment.

## Test Files

### `tests/test_data_freshness.py` (~100 lines)
- record_sync persists correctly
- get_freshness returns accurate ages
- get_stale_sources identifies overdue collectors
- entity_freshness aggregates across sources
- failed sync recorded with error
- source_health computes failure rates

### `tests/test_data_quality.py` (~150 lines)
- Entity with full coverage scores > 0.8
- Entity with missing domain (no comms) scores < 0.7
- Entity with stale data scores lower than fresh
- Entity with zero records scores 0.0
- Domain weights sum to 1.0 per entity type
- score_all returns sorted list (worst first)
- quality_summary identifies worst entities correctly
- Each entity type has valid expectations defined

### `tests/test_confidence_adjuster.py` (~100 lines)
- High quality entity gets confidence × 1.0
- Low quality entity (0.3) gets confidence × 0.3
- Zero quality entity gets confidence × 0.3 (floor)
- Pattern confidence uses worst entity quality
- Proposal priority adjusts with quality
- API response includes quality context

### `tests/test_quality_signals.py` (~80 lines)
- data_source_stale fires for overdue collector
- entity_data_sparse fires for entity below threshold
- entity_data_degrading fires for quality drop
- Quality signals integrate into main intelligence phase
- No false positives on fresh, complete data

### Integration test: `tests/test_quality_pipeline.py` (~100 lines)
- Seed DB with varied quality data
- Run full intelligence phase
- Verify quality-adjusted confidence in scorecard output
- Verify stale source signal in intelligence events
- Verify sparse entity signal for low-coverage entity
- Verify quality overview API returns accurate data

## Validation

- All tests pass
- No test uses live DB
- Pipeline test exercises full quality → intelligence → API chain
- Edge cases covered: empty DB, single collector, entity with one domain only

## Estimated Effort

~530 lines across 5 test files
