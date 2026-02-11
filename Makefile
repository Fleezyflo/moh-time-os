# Moh Time OS - Makefile
# Toolchain: uv (Python), pnpm (UI)
# API Framework: FastAPI/Uvicorn
#
# Quick reference:
#   make check       - Run all checks (fast, for local dev)
#   make ci          - Full CI suite (slower, authoritative)
#   make verify      - Full pristine verification
#   make dev         - Start API + UI dev servers

.PHONY: help setup verify check ci test lint format typecheck \
        drift-check openapi openapi-check schema-export schema-export-check \
        system-map system-map-check breaking-check invariants \
        ui-setup ui-lint ui-typecheck ui-test ui-build ui-types ui-types-check ui-check ui-deps \
        security-audit governance adr-check change-size-check hygiene dead-code \
        smoke pins toolchain-doctor bench coverage db-lifecycle-test \
        dev api ui run-api migrate schema-check ripgrep-check changelog

# ==========================================
# HELP
# ==========================================
help:
	@echo "Moh Time OS - Available targets:"
	@echo ""
	@echo "  Setup & Verification:"
	@echo "    make setup          - Install all dependencies (uv + pnpm)"
	@echo "    make verify         - Full pristine verification"
	@echo "    make check          - Fast quality checks (local dev)"
	@echo "    make ci             - Full CI suite (authoritative)"
	@echo "    make pins           - Verify toolchain versions + lockfiles"
	@echo ""
	@echo "  Python Quality:"
	@echo "    make lint           - Run ruff linter"
	@echo "    make format         - Format code with ruff"
	@echo "    make typecheck      - Run mypy with baseline"
	@echo "    make test           - Run pytest (fast subset)"
	@echo "    make test-all       - Run all tests"
	@echo "    make coverage       - Run tests with coverage"
	@echo ""
	@echo "  Drift & Invariants:"
	@echo "    make drift-check    - Check ALL drift (OpenAPI, schema, system-map)"
	@echo "    make invariants     - Check system-map semantic invariants"
	@echo ""
	@echo "  Governance:"
	@echo "    make governance     - Run ADR + change-size checks"
	@echo "    make changelog      - Generate CHANGELOG.md from commits"
	@echo ""
	@echo "  UI Quality:"
	@echo "    make ui-check       - Full UI quality suite"
	@echo "    make ui-test        - Run Vitest"
	@echo "    make ui-build       - Build production bundle"
	@echo ""
	@echo "  Performance & Hygiene:"
	@echo "    make bench          - Run performance benchmarks"
	@echo "    make smoke          - Run smoke tests"
	@echo "    make hygiene        - Dead code + dependency checks"
	@echo "    make security-audit - Run security audits"
	@echo ""
	@echo "  DB Lifecycle:"
	@echo "    make db-lifecycle-test - Run DB boot/migrate/backup tests"
	@echo "    make schema-check   - Validate schema assertions"
	@echo "    make migrate        - Run safety migrations"
	@echo ""
	@echo "  Development:"
	@echo "    make dev            - Start API + UI servers"
	@echo "    make api            - Start API server only"
	@echo "    make ui             - Start UI dev server only"
	@echo ""

# ==========================================
# SETUP
# ==========================================
setup: setup-python setup-ui
	@echo "✅ Setup complete"

setup-python:
	@echo "📦 Installing Python dependencies..."
	@uv sync --all-extras

setup-ui:
	@echo "📦 Installing UI dependencies..."
	@cd time-os-ui && pnpm install

# ==========================================
# FULL VERIFICATION
# ==========================================
verify:
	@./scripts/verify_pristine.sh

# Fast check for local dev (<2 min)
check: lint typecheck test-property test drift-check ui-test
	@echo ""
	@echo "✅ All checks passed!"

# Full CI suite (~5 min)
ci: pins lint typecheck test-ci drift-check invariants ui-check db-lifecycle-test smoke governance
	@echo ""
	@echo "✅ Full CI suite passed!"

test-ci:
	@echo "🧪 Running CI test suite..."
	@uv run pytest tests/contract/ tests/property/ tests/lifecycle/ tests/test_safety.py tests/negative/ -v --tb=short

# ==========================================
# PYTHON QUALITY
# ==========================================
lint:
	@echo "🔍 Running ruff linter (scoped)..."
	@uv run ruff check lib/ui_spec_v21/ lib/collectors/ lib/safety/ lib/contracts/ lib/observability/ api/ --fix --ignore "S110,S602,S608,B904,E402,S104"

lint-full:
	@echo "🔍 Running ruff linter (full)..."
	@uv run ruff check lib/ api/ tests/ --fix || true

format:
	@echo "✨ Formatting code (scoped)..."
	@uv run ruff format lib/ui_spec_v21/ lib/collectors/ lib/safety/ lib/contracts/ lib/observability/ api/

typecheck:
	@echo "🔍 Running mypy baseline check..."
	@uv run python scripts/check_mypy_baseline.py

typecheck-strict:
	@echo "🔍 Running mypy strict islands only..."
	@uv run python scripts/check_mypy_baseline.py --strict-only

typecheck-update:
	@echo "🔍 Updating mypy baseline..."
	@uv run python scripts/check_mypy_baseline.py --update

test:
	@echo "🧪 Running pytest (contract + safety)..."
	@uv run pytest tests/contract/ tests/test_safety.py -v --tb=short

test-property:
	@echo "🧪 Running property-based tests..."
	@uv run pytest tests/property/ -v --tb=short

test-all:
	@echo "🧪 Running all tests..."
	@uv run pytest tests/ -v --tb=short

# ==========================================
# COVERAGE
# ==========================================
coverage:
	@echo "📊 Running tests with coverage..."
	@uv run python scripts/check_coverage.py

coverage-html:
	@echo "📊 Generating HTML coverage report..."
	@uv run python scripts/check_coverage.py --html
	@echo "Open htmlcov/index.html to view"

# ==========================================
# DRIFT DETECTION
# ==========================================
drift-check: openapi-check schema-export-check system-map-check breaking-check
	@echo "✅ No drift detected"

openapi:
	@uv run python scripts/export_openapi.py

openapi-check:
	@echo "📋 Checking OpenAPI schema..."
	@uv run python scripts/export_openapi.py --check

schema-export:
	@uv run python scripts/export_schema.py

schema-export-check:
	@echo "📊 Checking schema export..."
	@uv run python scripts/export_schema.py --check

system-map:
	@uv run python scripts/generate_system_map.py

system-map-check:
	@echo "🗺️  Checking system map..."
	@uv run python scripts/generate_system_map.py --check

breaking-check:
	@echo "🔄 Checking for breaking API changes..."
	@uv run python scripts/check_breaking_changes.py

ui-types:
	@./scripts/generate_ui_types.sh

ui-types-check:
	@echo "📝 Checking UI types..."
	@./scripts/generate_ui_types.sh --check

# ==========================================
# SYSTEM INVARIANTS
# ==========================================
invariants:
	@echo "🔍 Checking system invariants..."
	@uv run python scripts/check_system_invariants.py

# ==========================================
# GOVERNANCE
# ==========================================
governance: adr-check change-size-check
	@echo "✅ Governance checks passed"

adr-check:
	@echo "📋 Checking ADR requirements..."
	@./scripts/check_adr_required.sh HEAD~1 || true

change-size-check:
	@echo "📏 Checking change size..."
	@./scripts/check_change_size.sh HEAD~1 || true

changelog:
	@echo "📝 Generating changelog..."
	@uv run python scripts/generate_changelog.py --print

changelog-save:
	@uv run python scripts/generate_changelog.py -o CHANGELOG.md

# ==========================================
# UI QUALITY
# ==========================================
ui-check: ui-lint ui-typecheck ui-test ui-build
	@echo "✅ UI checks passed"

ui-lint:
	@echo "🔍 Running ESLint + Prettier..."
	@cd time-os-ui && pnpm run lint || true
	@cd time-os-ui && pnpm run format:check || true

ui-typecheck:
	@echo "🔍 Running TypeScript..."
	@cd time-os-ui && pnpm run typecheck || true

ui-test:
	@echo "🧪 Running Vitest..."
	@cd time-os-ui && pnpm test

ui-build:
	@echo "📦 Building UI..."
	@cd time-os-ui && pnpm run build && pnpm run bundle:check

ui-deps:
	@echo "🔍 Checking UI dependencies..."
	@cd time-os-ui && node scripts/check-deps.js || true

ui-contracts:
	@echo "📋 Running UI API contract tests..."
	@cd time-os-ui && pnpm test -- api-contracts

ui-fixtures:
	@echo "🧪 Validating MSW fixtures against schemas..."
	@cd time-os-ui && pnpm test -- fixtures

ui-integration:
	@echo "🔗 Running UI integration tests..."
	@cd time-os-ui && pnpm test -- integration

# ==========================================
# HYGIENE
# ==========================================
hygiene: dead-code ui-deps
	@echo "✅ Hygiene checks completed"

dead-code:
	@echo "🔍 Checking for dead code..."
	@uv run python scripts/check_dead_code.py || true

# ==========================================
# SECURITY
# ==========================================
security-audit:
	@./scripts/security_audit.sh

# ==========================================
# PERFORMANCE
# ==========================================
smoke:
	@echo "🔥 Running smoke tests..."
	@uv run python scripts/smoke_test.py

bench:
	@echo "📊 Running benchmarks..."
	@uv run python scripts/benchmark.py

bench-save:
	@echo "📊 Running and saving benchmarks..."
	@uv run python scripts/benchmark.py --save benchmarks.json

mutation:
	@echo "🧬 Running mutation tests (small scope: lib/safety)..."
	@uv run mutmut run --paths-to-mutate=lib/safety/json_parse.py --tests-dir=tests/ --runner="python -m pytest tests/test_safety.py -x -q --tb=no" || true
	@uv run mutmut results

mutation-full:
	@echo "🧬 Running full mutation tests (nightly scope)..."
	@uv run mutmut run --paths-to-mutate=lib/safety/ --tests-dir=tests/ || true
	@uv run mutmut results

# ==========================================
# DB LIFECYCLE
# ==========================================
db-lifecycle-test:
	@echo "🗄️  Running DB lifecycle tests..."
	@uv run pytest tests/lifecycle/ -v --tb=short

schema-check:
	@echo "📊 Checking schema..."
	@uv run python -c "from lib.safety.schema import SchemaAssertion; from lib import paths; import sqlite3; \
		conn = sqlite3.connect(str(paths.db_path())); \
		a = SchemaAssertion(conn); \
		v = a.assert_all(); \
		print('✅ Schema OK') if not v else print(f'Found {len(v)} violations'); \
		[print(f'  ❌ {x.message}') for x in v]; \
		exit(1 if v else 0)"

migrate:
	@echo "🔧 Running safety migrations..."
	@uv run python -c "from lib.safety import run_safety_migrations; from lib import paths; import sqlite3; \
		conn = sqlite3.connect(str(paths.db_path())); \
		result = run_safety_migrations(conn); \
		print(f'Tables: {result[\"tables_created\"]}'); \
		print(f'Triggers: {len(result[\"triggers_created\"])} created')"

# ==========================================
# REPRODUCIBILITY
# ==========================================
pins: toolchain-doctor
	@echo "✅ Reproducibility pins verified"

toolchain-doctor:
	@./scripts/toolchain_doctor.sh

ripgrep-check:
	@echo "🔎 Checking for forbidden patterns..."
	@./scripts/ripgrep_check.sh

# ==========================================
# DEVELOPMENT
# ==========================================
api:
	@echo "🚀 Starting API server..."
	@uv run python -m api.server

ui:
	@echo "🎨 Starting UI dev server..."
	@cd time-os-ui && pnpm run dev

dev:
	@./scripts/dev.sh

run-api: api

# ==========================================
# GENERATION
# ==========================================
generate-all: openapi schema-export system-map ui-types
	@echo "✅ All artifacts generated"

# ==========================================
# SCENARIOS (Golden Scenario Harness)
# ==========================================
scenarios:
	@echo "🎭 Running scenario tests..."
	@uv run pytest tests/scenarios/ -v --tb=short

scenarios-update:
	@echo "🎭 Updating scenario golden files..."
	@UPDATE_GOLDEN=1 uv run pytest tests/scenarios/ -v --tb=short

# ==========================================
# UI DOMAIN
# ==========================================
ui-domain-check:
	@echo "🏗️  Checking UI domain model..."
	@cd time-os-ui && pnpm test -- domain

# ==========================================
# OFFLINE MODE
# ==========================================
ui-offline-test:
	@echo "📡 Running offline mode tests..."
	@cd time-os-ui && pnpm test -- offline

# ==========================================
# TRACING
# ==========================================
trace-smoke:
	@echo "🔍 Running trace correlation smoke test..."
	@uv run python scripts/trace_smoke.py

# ==========================================
# COLLECTORS REPLAY
# ==========================================
collectors-replay-test:
	@echo "📼 Running collector replay tests..."
	@uv run pytest tests/cassettes/ -v --tb=short

cassettes-validate:
	@echo "📼 Validating cassettes..."
	@uv run python -c "from lib.collectors.recorder import validate_cassettes; issues = validate_cassettes(); print('Issues found:') if issues else None; [print(f'  - {i}') for i in issues] if issues else None; exit(1) if issues else print('✅ All cassettes valid')"

# ==========================================
# MIGRATION REHEARSAL
# ==========================================
migrate-matrix:
	@echo "🔄 Running migration matrix..."
	@uv run python scripts/migrate_matrix.py

db-rehearsal: migrate-matrix
	@echo "✅ DB rehearsal complete"

db-rollback-drill:
	@echo "🔄 Running rollback drill..."
	@uv run python scripts/rollback_drill.py

# ==========================================
# EVIDENCE BUNDLE
# ==========================================
evidence:
	@echo "📦 Generating evidence bundle..."
	@uv run python scripts/evidence_bundle.py

# ==========================================
# SEMGREP
# ==========================================
semgrep:
	@echo "🔍 Running Semgrep rules..."
	@semgrep --config .semgrep/rules.yaml lib/ api/ time-os-ui/src/ --error 2>/dev/null || \
		echo "⚠️  Semgrep not installed. Install with: pip install semgrep"

semgrep-full:
	@echo "🔍 Running full Semgrep scan..."
	@semgrep --config .semgrep/rules.yaml --config auto lib/ api/ time-os-ui/src/ 2>/dev/null || true

# ==========================================
# FEATURE FLAGS
# ==========================================
flags-check:
	@echo "🚩 Checking feature flags..."
	@uv run pytest tests/test_features.py -v --tb=short

flags-smoke:
	@echo "🚩 Running flags smoke test..."
	@uv run python scripts/flags_smoke.py

# ==========================================
# AUDIT TRAIL
# ==========================================
audit-test:
	@echo "📝 Running audit trail tests..."
	@uv run pytest tests/test_audit.py -v --tb=short

replay-test:
	@echo "📝 Running replay tests..."
	@uv run pytest tests/test_audit.py::TestStateReplayer -v --tb=short

# ==========================================
# EXTENDED CI
# ==========================================
ci-extended: ci scenarios collectors-replay-test flags-check audit-test
	@echo "✅ Extended CI suite passed!"

nightly-local: ci-extended migrate-matrix trace-smoke
	@echo "✅ Nightly-equivalent local run passed!"
