# Development Rules

**Enforceable rules for agents and developers. CI blocks violations.**

---

## 1. New Code Must Be Typed

- **No `Any`** unless isolated in `lib/typing_hacks.py` with justification comment.
- **No untyped functions** in api/, lib/safety/, lib/contracts/, lib/observability/.
- Use `typing.cast()` for explicit type coercion; document why.

## 2. DB Changes Require Artifacts

Any change to database schema must update:
- [ ] `docs/schema.sql` — run `make schema-export`
- [ ] Migration file in `lib/migrations/` or `lib/v5/migrations/`
- [ ] Tests in `tests/contract/test_schema.py`

CI check: `make schema-export-check` fails if drift detected.

## 3. API Changes Require Artifacts

Any change to API endpoints must update:
- [ ] `docs/openapi.json` — run `make openapi`
- [ ] `time-os-ui/src/types/generated.ts` — run `make ui-types`
- [ ] Breaking changes require ADR (see ADR workflow)

CI check: `make drift-check` fails if drift detected.

## 4. New Modules Require Owner + Tests

Every new module in `lib/` must have:
- [ ] Docstring with purpose and owner
- [ ] Corresponding test file in `tests/`
- [ ] Entry in `docs/system-map.json` (auto-generated, but verify)

## 5. Collectors Must Register Outputs

Every collector in `lib/collectors/` must:
- [ ] Define `OUTPUT_TABLES` class attribute
- [ ] Register in `lib/collector_registry.py`
- [ ] Document in `docs/system-map.json`

## 6. Large Changes Require Rationale

PRs touching >50 files require:
- [ ] `large-change` label
- [ ] Summary in PR description explaining scope

PRs with >20 deletions require:
- [ ] Deletion rationale in commit message

## 7. No Silent Refactors

Changes to core modules require:
- [ ] ADR if architectural (see `docs/adr/`)
- [ ] Tests pass before and after
- [ ] Reviewer approval

Core modules: `lib/db.py`, `lib/safety/`, `api/server.py`, `lib/collectors/orchestrator.py`

---

## Quick Reference

```bash
# After DB changes
make schema-export

# After API changes
make openapi
make ui-types

# Before commit
make check

# Full verification
make verify
```

---

## Enforcement

These rules are enforced by:
- Pre-commit hooks (scoped lint)
- CI drift checks (OpenAPI, schema, system-map)
- CI mypy baseline (no new type errors)
- PR size guards (>50 files triggers review)
