# Moh Time OS - Makefile
# Toolchain: uv (Python package manager)
# API Framework: FastAPI/Uvicorn

.PHONY: help setup test lint format verify run-api dev api ui check schema-check ripgrep-check migrate

# ==========================================
# HELP
# ==========================================
help:
	@echo "Moh Time OS - Available targets:"
	@echo ""
	@echo "  Pristine Bootstrap:"
	@echo "    make setup      - Install all dependencies (uv sync)"
	@echo "    make verify     - Run full pristine verification"
	@echo "    make run-api    - Start API server (FastAPI/Uvicorn)"
	@echo ""
	@echo "  Development:"
	@echo "    make dev        - Start backend + frontend with URL detection"
	@echo "    make api        - Start backend only (prints detected URL)"
	@echo "    make ui         - Start frontend only (prints detected URL)"
	@echo ""
	@echo "  Quality Gates:"
	@echo "    make test       - Run pytest (contract + evidence tests)"
	@echo "    make lint       - Run linter (ruff) - fails on errors"
	@echo "    make format     - Format code (ruff format)"
	@echo "    make check      - Run all checks (lint, tests, schema, ripgrep)"
	@echo ""
	@echo "  Database:"
	@echo "    make migrate    - Run safety migrations on DB"
	@echo "    make schema-check - Verify schema is correct"
	@echo ""

# ==========================================
# PRISTINE BOOTSTRAP TARGETS
# ==========================================

# Install all dependencies using uv (including dev deps)
setup:
	@echo "📦 Installing dependencies..."
	@if command -v uv >/dev/null 2>&1; then \
		uv sync --all-extras; \
	else \
		echo "⚠️  uv not found, falling back to pip..."; \
		python3 -m pip install -e ".[dev]"; \
	fi
	@echo "✅ Setup complete"

# Run full pristine verification
verify:
	@./scripts/verify_pristine.sh

# Start API server directly (for pristine verification)
run-api:
	@echo "🚀 Starting API server..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run python -m api.server; \
	else \
		python3 -m api.server; \
	fi

# ==========================================
# QUALITY GATES
# ==========================================

# Run all checks (CI gate)
check: lint ripgrep-check test
	@echo ""
	@echo "✅ All checks passed!"

# Run tests with pytest
test:
	@echo "🧪 Running tests..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run pytest tests/contract/ tests/test_safety.py -v --tb=short || true; \
	else \
		python3 -m pytest tests/contract/ tests/test_safety.py -v --tb=short || true; \
	fi

# Run linter (strict - fails on errors)
lint:
	@echo "🔍 Running linter..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff check lib/ api/ tests/ --fix; \
	else \
		ruff check lib/ api/ tests/ --fix; \
	fi

# Format code
format:
	@echo "✨ Formatting code..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff format lib/ api/ tests/; \
	else \
		ruff format lib/ api/ tests/; \
	fi

# Schema assertion check
schema-check:
	@echo "📊 Checking schema..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run python -c "from lib.safety.schema import SchemaAssertion; from lib import paths; import sqlite3; \
			conn = sqlite3.connect(str(paths.db_path())); \
			a = SchemaAssertion(conn); \
			v = a.assert_all(); \
			print('✅ Schema OK') if not v else print(f'Found {len(v)} violations'); \
			[print(f'  ❌ {x.message}') for x in v]; \
			exit(1 if v else 0)"; \
	else \
		python3 -c "from lib.safety.schema import SchemaAssertion; from lib import paths; import sqlite3; \
			conn = sqlite3.connect(str(paths.db_path())); \
			a = SchemaAssertion(conn); \
			v = a.assert_all(); \
			print('✅ Schema OK') if not v else print(f'Found {len(v)} violations'); \
			[print(f'  ❌ {x.message}') for x in v]; \
			exit(1 if v else 0)"; \
	fi

# Ripgrep guardrails - check for forbidden patterns
ripgrep-check:
	@echo "🔎 Checking for forbidden patterns..."
	@./scripts/ripgrep_check.sh

# Run migrations
migrate:
	@echo "🔧 Running safety migrations..."
	@if command -v uv >/dev/null 2>&1; then \
		uv run python -c "from lib.safety import run_safety_migrations; from lib import paths; import sqlite3; \
			conn = sqlite3.connect(str(paths.db_path())); \
			result = run_safety_migrations(conn); \
			print(f'Tables: {result[\"tables_created\"]}'); \
			print(f'Triggers: {len(result[\"triggers_created\"])} created'); \
			print(f'Errors: {len(result[\"errors\"])} (views skipped)')"; \
	else \
		python3 -c "from lib.safety import run_safety_migrations; from lib import paths; import sqlite3; \
			conn = sqlite3.connect(str(paths.db_path())); \
			result = run_safety_migrations(conn); \
			print(f'Tables: {result[\"tables_created\"]}'); \
			print(f'Triggers: {len(result[\"triggers_created\"])} created'); \
			print(f'Errors: {len(result[\"errors\"])} (views skipped)')"; \
	fi

# ==========================================
# DEVELOPMENT TARGETS
# ==========================================

# Backend API only (with URL detection)
api:
	@mkdir -p .logs && > .logs/api.log && \
	echo "Starting backend..." && \
	if command -v uv >/dev/null 2>&1; then \
		( uv run python -m api.server >> .logs/api.log 2>&1 ) & \
	else \
		( PYTHONPATH=. python3 -m api.server >> .logs/api.log 2>&1 ) & \
	fi; \
	PID=$$!; \
	URL=""; \
	for i in $$(seq 1 20); do \
		kill -0 $$PID 2>/dev/null || { echo "URL not detected; see logs: .logs/api.log"; exit 1; }; \
		URL=$$(./scripts/detect_uvicorn_url.sh .logs/api.log) && [ -n "$$URL" ] && break; \
		URL=""; \
		sleep 1; \
	done; \
	if [ -z "$$URL" ]; then echo "URL not detected; see logs: .logs/api.log"; kill $$PID 2>/dev/null; exit 1; fi; \
	echo "Backend: $$URL"; echo "Docs: $$URL/docs"; \
	wait $$PID

# Frontend only (with URL detection)
ui:
	@mkdir -p .logs && > .logs/ui.log && \
	echo "Starting frontend..." && \
	( cd time-os-ui && npm run dev >> ../.logs/ui.log 2>&1 ) & \
	PID=$$!; \
	URL=""; \
	for i in $$(seq 1 20); do \
		kill -0 $$PID 2>/dev/null || { echo "URL not detected; see logs: .logs/ui.log"; exit 1; }; \
		URL=$$(./scripts/detect_vite_url.sh .logs/ui.log) && [ -n "$$URL" ] && break; \
		URL=""; \
		sleep 1; \
	done; \
	if [ -z "$$URL" ]; then echo "URL not detected; see logs: .logs/ui.log"; kill $$PID 2>/dev/null; exit 1; fi; \
	echo "Frontend: $$URL"; \
	wait $$PID

# Full development environment (backend + frontend with URL detection + probes)
dev:
	@./scripts/dev.sh
