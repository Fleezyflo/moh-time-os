# ADR-0003: V5 init + orchestrator changes in this PR

## Status
Accepted

This PR changes `lib/v5/` (e.g. orchestrator + initialization tooling). Repo governance requires an ADR for V5 architecture changes.

## Decision
- Add/adjust V5 schema initialization tooling (scripts/init_v5_db.py) to reliably create required V5 tables.
- Update V5 orchestrator initialization/migration behavior to be more robust (e.g., executescript usage vs naive splitting) and reduce pipeline fragility.
- Keep behavior behind existing entrypoints/environment flags where applicable.

## Consequences
- CI governance gate is satisfied for `lib/v5/` changes.
- V5 initialization becomes more deterministic and less error-prone.
