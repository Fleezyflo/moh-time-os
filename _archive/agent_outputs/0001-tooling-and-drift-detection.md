# ADR-0001: Tooling and Drift Detection Architecture

**Status**: Accepted  
**Date**: 2026-02-11  
**Author**: Agent (via recovery session)  

## Context

The repository lacked systematic drift detection between:
- API contracts (OpenAPI) and UI type definitions
- Database schema definitions and actual migrations
- Collector outputs and storage tables
- System components and documentation

This led to silent inconsistencies where changes in one layer weren't reflected in dependent layers.

## Decision

Implement a "truth pipeline" with pinned artifacts and automated drift checks:

1. **OpenAPI Pinning**: Generate `docs/openapi.json` from FastAPI app; CI fails if stale.
2. **Schema Pinning**: Generate `docs/schema.sql` from migrations; CI fails if stale.
3. **System Map**: Generate `docs/system-map.json` mapping collectors→DB→API→UI.
4. **UI Types**: Generate TypeScript types from OpenAPI; CI fails if stale.
5. **Mypy Baseline**: Track type errors in `.mypy-baseline.txt`; CI fails if baseline grows.

## Consequences

### Positive
- All contract drifts are caught in CI
- Regeneration is one command (`make generate-all`)
- Changes to one layer force updates to dependent layers
- Type safety improves over time via baseline burn-down

### Negative
- More artifacts to commit and maintain
- Breaking changes require explicit regeneration
- CI runs take longer (drift checks)

## Alternatives Considered

1. **Runtime validation only**: Rejected because drift is caught too late.
2. **Manual documentation**: Rejected because it drifts immediately.
3. **No type checking**: Rejected because it hides structural bugs.

## References

- Commit: 9482223 (implement complete truth pipeline)
- Makefile targets: `drift-check`, `openapi`, `schema-export`, `ui-types`
