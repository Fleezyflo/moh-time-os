# ADR-0024: Route Canonicalization — Payload Normalization

## Status
Accepted

## Context
After route canonicalization (intelligence_router owns all intelligence routes, spec_router retains only `/patterns`), four payload mismatches remained between backend library return types and what the UI consumers expect:

1. Scorecard `dimensions`: backend returns `list[dict]`, UI expects `Record<string, {name, score, status}>`.
2. Scorecard `computed_at`: backend returns `scored_at`, UI expects `computed_at`.
3. Pattern fields: backend returns `pattern_name/pattern_type/entities_involved/operational_meaning`, UI expects `name/type/affected_entities/description`.
4. Signal history `limit`: `get_signal_history()` has no `limit` parameter, but the endpoint accepts one.

Affected trigger file: `api/spec_router.py` (removed stale `IntelligenceResponse` import, added pattern field normalization in `get_intelligence_patterns`).

## Decision
1. Add `_normalize_scorecard_dimensions()` to intelligence_router to convert the list-of-dicts to a keyed record at response time, applied in all 4 score handlers and 3 entity intelligence handlers.
2. Add `_patch_scorecard_computed_at()` and `_patch_portfolio_score_computed_at()` to inject `computed_at` from `scored_at` when missing.
3. Add field-alias normalization in spec_router's `get_intelligence_patterns` to map `pattern_name` → `name`, `pattern_type` → `type`, `entities_involved` → `affected_entities`, `operational_meaning` → `description`.
4. Replace `limit=limit` parameter pass-through with post-fetch slice (`data[:limit]`) for signal history.
5. Regenerate `docs/openapi.json` and `time-os-ui/src/types/generated.ts` to reflect the corrected `/patterns` operationId and response model.

## Consequences
- All intelligence API responses now match the shapes the UI already consumes. No frontend changes needed.
- Normalization happens at the handler level, not in the library functions, preserving library return types for other callers.
- The `limit` workaround fetches all signals then slices; acceptable for current data volumes but should be revisited if signal counts grow large.
- OpenAPI spec and generated types are now consistent with the actual route registrations.
