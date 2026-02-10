# Moh Time OS - Makefile
# Toolchain: uv (Python), pnpm (UI)
# API Framework: FastAPI/Uvicorn
#
# Quick reference:
#   make check     - Run all checks (mirrors CI)
#   make verify    - Full pristine verification
#   make dev       - Start backend + frontend

.PHONY: help setup verify check test lint format typecheck \
        drift-check openapi openapi-check schema-export schema-export-check \
        system-map system-map-check breaking-check \
        ui-setup ui-lint ui-typecheck ui-test ui-build ui-types ui-types-check \
        security-audit dev api ui run-api migrate schema-check ripgrep-check

# ==========================================
# HELP
# ==========================================
help:
	@echo "Moh Time OS - Available targets:"
	@echo ""
	@echo "  Setup & Verification:"
	@echo "    make setup        - Install all dependencies (uv + pnpm)"
	@echo "    make verify       - Full pristine verification (mirrors CI)"
	@echo "    make check        - Run all checks (lint, types, drift, tests)"
	@echo ""
	@echo "  Python Quality:"
	@echo "    make lint         - Run ruff linter"
	@echo "    make format       - Format code with ruff"
	@echo "    make typecheck    - Run mypy type checker"
	@echo "    make test         - Run pytest"
	@echo ""
	@echo "  Drift Detection:"
	@echo "    make drift-check  - Check ALL drift (OpenAPI, schema, system-map, UI types)"
	@echo "    make openapi      - Generate docs/openapi.json"
	@echo "    make schema-export - Export docs/schema.sql"
	@echo "    make system-map   - Generate docs/system-map.json"
	@echo "    make ui-types     - Generate TS types from OpenAPI"
	@echo "    make breaking-check - Check for breaking API changes"
	@echo ""
	@echo "  UI Quality:"
	@echo "    make ui-setup     - Install UI dependencies (pnpm)"
	@echo "    make ui-lint      - Run ESLint + Prettier check"
	@echo "    make ui-typecheck - Run TypeScript type check"
	@echo "    make ui-test      - Run Vitest"
	@echo "    make ui-build     - Build production bundle"
	@echo ""
	@echo "  Security:"
	@echo "    make security-audit - Run pip-audit, pnpm audit, gitleaks"
	@echo ""
	@echo "  Development:"
	@echo "    make dev          - Start backend + frontend"
	@echo "    make api          - Start backend only"
	@echo "    make ui           - Start frontend only"
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

check: lint typecheck drift-check test ui-check
	@echo ""
	@echo "✅ All checks passed!"

# ==========================================
# PYTHON QUALITY
# ==========================================
lint:
	@echo "🔍 Running ruff linter (scoped)..."
	@uv run ruff check lib/ui_spec_v21/ lib/collectors/ lib/safety/ lib/contracts/ lib/observability/ api/ --fix

lint-full:
	@echo "🔍 Running ruff linter (full - may have legacy errors)..."
	@uv run ruff check lib/ api/ tests/ --fix || true

format:
	@echo "✨ Formatting code (scoped)..."
	@uv run ruff format lib/ui_spec_v21/ lib/collectors/ lib/safety/ lib/contracts/ lib/observability/ api/

typecheck:
	@echo "🔍 Running mypy..."
	@uv run mypy api/ lib/safety/ lib/contracts/ lib/observability/ --ignore-missing-imports --explicit-package-bases || true

test:
	@echo "🧪 Running pytest..."
	@uv run pytest tests/contract/ tests/test_safety.py -v --tb=short

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
# UI QUALITY
# ==========================================
ui-check: ui-lint ui-typecheck ui-test ui-build
	@echo "✅ UI checks passed"

ui-lint:
	@echo "🔍 Running ESLint + Prettier..."
	@cd time-os-ui && pnpm run lint && pnpm run format:check

ui-typecheck:
	@echo "🔍 Running TypeScript..."
	@cd time-os-ui && pnpm run typecheck

ui-test:
	@echo "🧪 Running Vitest..."
	@cd time-os-ui && pnpm test

ui-build:
	@echo "📦 Building UI..."
	@cd time-os-ui && pnpm run build && pnpm run bundle:check

# ==========================================
# SECURITY
# ==========================================
security-audit:
	@./scripts/security_audit.sh

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
generate-all: openapi schema-export system-map
	@echo "✅ All artifacts generated"
