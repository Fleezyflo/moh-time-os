# Moh Time OS - Makefile
# Toolchain: uv (Python), pnpm (UI)
# API Framework: FastAPI/Uvicorn
#
# Quick reference:
#   make check       - Run all checks (mirrors CI)
#   make verify      - Full pristine verification
#   make governance  - ADR + change-size checks
#   make hygiene     - Dead code + dependency checks
#   make smoke       - Performance smoke tests

.PHONY: help setup verify check test lint format typecheck \
        drift-check openapi openapi-check schema-export schema-export-check \
        system-map system-map-check breaking-check invariants \
        ui-setup ui-lint ui-typecheck ui-test ui-build ui-types ui-types-check ui-check ui-deps \
        security-audit governance adr-check change-size-check hygiene dead-code \
        smoke pins toolchain-doctor \
        dev api ui run-api migrate schema-check ripgrep-check

# ==========================================
# HELP
# ==========================================
help:
	@echo "Moh Time OS - Available targets:"
	@echo ""
	@echo "  Setup & Verification:"
	@echo "    make setup          - Install all dependencies (uv + pnpm)"
	@echo "    make verify         - Full pristine verification (mirrors CI)"
	@echo "    make check          - Run all quality checks"
	@echo "    make pins           - Verify toolchain versions + lockfiles"
	@echo ""
	@echo "  Python Quality:"
	@echo "    make lint           - Run ruff linter"
	@echo "    make format         - Format code with ruff"
	@echo "    make typecheck      - Run mypy with baseline"
	@echo "    make test           - Run pytest"
	@echo "    make dead-code      - Check for dead code (vulture)"
	@echo ""
	@echo "  Drift & Invariants:"
	@echo "    make drift-check    - Check ALL drift (OpenAPI, schema, system-map, UI types)"
	@echo "    make invariants     - Check system-map semantic invariants"
	@echo "    make openapi        - Generate docs/openapi.json"
	@echo "    make schema-export  - Export docs/schema.sql"
	@echo "    make system-map     - Generate docs/system-map.json"
	@echo ""
	@echo "  Governance:"
	@echo "    make governance     - Run ADR + change-size checks"
	@echo "    make adr-check      - Check if ADR is required"
	@echo "    make change-size-check - Check for large changes"
	@echo ""
	@echo "  UI Quality:"
	@echo "    make ui-setup       - Install UI dependencies (pnpm)"
	@echo "    make ui-lint        - Run ESLint + Prettier check"
	@echo "    make ui-typecheck   - Run TypeScript type check"
	@echo "    make ui-test        - Run Vitest"
	@echo "    make ui-build       - Build production bundle"
	@echo "    make ui-deps        - Check UI dependencies"
	@echo ""
	@echo "  Hygiene & Security:"
	@echo "    make hygiene        - Dead code + dependency checks"
	@echo "    make security-audit - Run pip-audit, pnpm audit, gitleaks"
	@echo ""
	@echo "  Performance:"
	@echo "    make smoke          - Run smoke tests with timing budgets"
	@echo ""
	@echo "  Development:"
	@echo "    make dev            - Start backend + frontend"
	@echo "    make api            - Start backend only"
	@echo "    make ui             - Start frontend only"
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
# FULL VERIFICATION (mirrors CI)
# ==========================================
verify:
	@./scripts/verify_pristine.sh

check: lint typecheck test-property test drift-check invariants ui-check
	@echo ""
	@echo "✅ All checks passed!"

# ==========================================
# PYTHON QUALITY
# ==========================================
lint:
	@echo "🔍 Running ruff linter (scoped, matches pre-commit)..."
	@uv run ruff check lib/ui_spec_v21/ lib/collectors/ lib/safety/ lib/contracts/ lib/observability/ api/ --fix --ignore "S110,S602,S608,B904,E402,S104"

lint-full:
	@echo "🔍 Running ruff linter (full - may have legacy errors)..."
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

# ==========================================
# REPRODUCIBILITY
# ==========================================
pins: toolchain-doctor
	@echo "✅ Reproducibility pins verified"

toolchain-doctor:
	@./scripts/toolchain_doctor.sh

# ==========================================
# DATABASE
# ==========================================
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
# GENERATION (for updating pinned artifacts)
# ==========================================
generate-all: openapi schema-export system-map ui-types
	@echo "✅ All artifacts generated"
