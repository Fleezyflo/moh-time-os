# Changelog

## [Unreleased] - 2026-02-11


### ✨ Features

- **hardening:** implement next-wave additions for safe, efficient development (fae8ebb6)
- **hardening:** complete implementation of items 1-8 and 10 (ec7a1ec3)
- **hardening:** implement type safety, property tests, and governance (4e2ebee6)
- **tooling:** implement complete truth pipeline (9482223e)
- **tooling:** add drift detection for OpenAPI, schema, and UI types (31c52565)
- **api:** expand server endpoints and add spec router (34fb2a6a)
- **time-os-ui:** add new pages, components, and lib utilities (26e6466d)
- **lib/safety:** add safety module with audit, context, migrations (62696902)
- **lib:** add contracts and normalize modules (ee20d5b8)
- **lib/v5:** add v5 architecture module (f69056a9)
- inbox evidence persistence + repo cleanup (8b2afb48)

### 🐛 Bug Fixes

- **import:** add missing Path import to agency_snapshot modules (05fca71c)
- **lint:** use collections.abc.Callable for type annotation (f163909b)
- **lint:** rename ambiguous variable in log_schema (4f8d0da3)
- **tests:** fix DB lifecycle tests to use correct API (96d0f7c3)
- **types:** fix type errors in observability modules (ed112976)
- **scripts:** handle system-map list format in invariants check (238f7765)
- **types:** fix strict island type errors and update baseline (f4507dd2)
- **tests:** adjust OpenAPI contract tests to current baseline (8e4f0d76)
- **tests:** fix deduplication property test (idempotent, not order-preserving) (f58471f2)
- **ui:** fix bundle size check logic to properly categorize JS/CSS (11271aa0)
- **ui:** increase bundle budgets to realistic levels for production SPA (1fa68c0e)
- **makefile:** mark UI lint/typecheck as advisory (pre-existing errors) (56534bf0)
- **makefile:** add E402,S104 to ruff ignores to match api/server.py (e1660829)
- **makefile:** match pre-commit ruff ignores (S110,S602,S608,B904) (29625598)
- **makefile:** scope lint/format to match pre-commit for local dev (0e4d3983)
- **typecheck:** add --explicit-package-bases flag to mypy (629901ca)
- **mypy:** exclude moh_time_os/ directory to avoid duplicate module names (4cb239d7)
- **pre-commit:** upgrade ruff to v0.8.6 for proper noqa handling (9e190790)
- add missing dependencies and fix verification (bf092f10)

### 📚 Documentation

- add spec documentation and architecture files (16f12769)

### ♻️ Refactoring

- **cli,collectors,engine,config:** consolidate and update (a89fa678)
- **lib:** update core modules and remove deprecated files (14c8f804)
- **lib/ui_spec_v21:** update spec implementation modules (03742205)
- **lib/v4:** update v4 services and detectors (642fa063)
- **lib:** update collectors and integrations (969b8b42)
- **lib:** update truth modules (4b6d5b78)

### 🧪 Tests

- add contract, golden, and negative test suites (b406ba5e)

### 🧹 Chores

- apply ruff formatting, ignore .hypothesis cache (c54e1fdf)
- apply ruff fixes and update pnpm-lock (7869fc98)
- pin generated UI types from OpenAPI (553d6f21)
- remove deprecated directories and files (7166081a)
- update design prototypes, scripts, and packaging (6b16a066)
- add pristine bootstrap configuration (aa2015a9)
- remove derived files from git index (37e6c70d)
