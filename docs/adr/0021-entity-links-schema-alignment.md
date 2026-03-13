# ADR-0021: Entity Links Schema Alignment and API Column Corrections

## Status
Accepted

## Context
Multiple `entity_links` references in `api/server.py` used column names (`id`, `entity_id`, `entity_type`, `linked_id`) that do not exist in the corrected schema (`link_id`, `to_entity_id`, `to_entity_type`, `from_artifact_id`). The `get_fix_data()` endpoint also contained runtime `CREATE TABLE IF NOT EXISTS entity_links` DDL that conflicted with the authoritative definition in `lib/schema.py`.

Additionally, `api/spec_router.py` had two issues: the `/couplings` SELECT omitted three columns (`investigation_path`, `created_at`, `updated_at`) expected by the UI, and the `/intelligence/patterns` endpoint used the generic `IntelligenceResponse` instead of the typed `PatternDetectionResponse`, silently discarding detection error metadata.

## Decision
1. Remove runtime DDL for `entity_links` from `server.py` -- `lib/schema.py` owns all table definitions.
2. Correct all stale column references in `server.py` to match the `entity_links` schema.
3. Add missing columns to the `/couplings` SELECT in `spec_router.py`.
4. Wire `PatternDetectionResponse` into `/intelligence/patterns` and propagate detection health metadata.

## Consequences
- `resolve_fix_data_item()` link resolution will now match rows (was silently matching zero due to `WHERE id = ?` on a table with no `id` column).
- `get_evidence()` will return results instead of failing with `no such column`.
- `/couplings` response now includes `investigation_path`, `created_at`, `updated_at` matching the UI `Coupling` type.
- `/intelligence/patterns` surfaces `detection_success`, `detection_errors`, and `detection_error_details` to consumers.
