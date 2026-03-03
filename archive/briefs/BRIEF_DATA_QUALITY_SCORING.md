# Brief 27: Data Quality Scoring
> **Status:** DESIGNED | **Priority:** P1 | **Prefix:** DQ

## Problem

Intelligence modules compute scores, detect signals, and fire patterns — but they operate on whatever data exists without knowing how good that data is. A client with only 3 tasks and no communication history gets the same confidence treatment as a client with 200 tasks and 18 months of email. This produces misleading intelligence: a client might score "healthy" simply because there's no data showing problems.

The system already has `data_completeness` as a float in score_history, but it's computed simplistically (fraction of non-null dimension scores). There's no per-collector freshness tracking, no completeness scoring per data domain, and no quality gates that degrade confidence.

## Dependencies

- **Requires:** Brief 9 (Collectors) — must know what data SHOULD exist per collector
- **Enhances:** Brief 18 (Intelligence Depth) — confidence scoring should incorporate data quality
- **Feeds into:** Brief 26 (Intelligence API) — quality metadata in every response

## Scope

Build a data quality scoring layer that answers three questions for any entity:
1. **What data exists?** (completeness)
2. **How fresh is it?** (freshness)
3. **How reliable is it?** (consistency)

The quality score feeds INTO intelligence as a confidence modifier — low quality data produces lower-confidence intelligence outputs.

## Architecture

```
Collectors → Raw Data → Quality Scorer → Quality Metadata
                                              ↓
Intelligence Modules → Raw Intelligence → Confidence Adjuster → Final Intelligence
                                              ↑
                                        Quality Metadata
```

## Tasks

| Task | Title | Est. Lines |
|------|-------|------------|
| DQ-1.1 | Collector Freshness Tracker | ~200 |
| DQ-2.1 | Entity Completeness Scorer | ~300 |
| DQ-3.1 | Quality-Weighted Confidence | ~200 |
| DQ-4.1 | Quality Dashboard & Alerts | ~200 |
| DQ-5.1 | Quality Validation | ~300 |

## Estimated Effort

~1,200 lines. 5 tasks. Medium.

## Success Criteria

- Every entity has a data quality score (0.0-1.0)
- Every intelligence output includes quality-adjusted confidence
- Stale collectors surface as signals
- Molham can see at a glance which entities have poor data coverage
- Intelligence confidence degrades gracefully with data quality
