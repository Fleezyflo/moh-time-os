Last login: Tue Feb 10 17:15:52 on ttys001
You have mail.
molhamhomsi@Molhams-MacBook-Pro-746 moh_time_os % pwd
git rev-parse --show-toplevel
git status --porcelain
git branch --show-current
git log --oneline -n 25
git describe --tags --always --dirty
/Users/molhamhomsi/clawd/moh_time_os
/Users/molhamhomsi/clawd/moh_time_os
?? tools/
recover-wip
9e19079 (HEAD -> recover-wip) fix(pre-commit): upgrade ruff to v0.8.6 for proper noqa handling
7166081 chore: remove deprecated directories and files
6b16a06 chore: update design prototypes, scripts, and packaging
a89fa67 refactor(cli,collectors,engine,config): consolidate and update
14c8f80 refactor(lib): update core modules and remove deprecated files
0374220 refactor(lib/ui_spec_v21): update spec implementation modules
642fa06 refactor(lib/v4): update v4 services and detectors
969b8b4 refactor(lib): update collectors and integrations
4b6d5b7 refactor(lib): update truth modules
34fb2a6 feat(api): expand server endpoints and add spec router
26e6466 feat(time-os-ui): add new pages, components, and lib utilities
6269690 feat(lib/safety): add safety module with audit, context, migrations
ee20d5b feat(lib): add contracts and normalize modules
f69056a feat(lib/v5): add v5 architecture module
b406ba5 test: add contract, golden, and negative test suites
16f1276 docs: add spec documentation and architecture files
bf092f1 (chore/pristine-bootstrap) fix: add missing dependencies and fix verification
aa2015a chore: add pristine bootstrap configuration
37e6c70 chore: remove derived files from git index
8b2afb4 (main) feat: inbox evidence persistence + repo cleanup
5dedbd4 Add bytecode manifest for verification reference
47d663b Remove pycache
bbdddaa Clean up forensics and temp files
76ded42 Reconstruct server.py from Python 3.14 bytecode disassembly - 100+ endpoints, 17 Pydantic models, full API
9e19079
molhamhomsi@Molhams-MacBook-Pro-746 moh_time_os % ls -la
find . -maxdepth 2 -type f -name "pyproject.toml" -o -name "setup.py" -o -name "requirements*.txt" -o -name ".pre-commit-config.yaml" -o -name "pytest.ini" -o -name "ruff.toml" -o -name ".env.example"
find api lib engine collectors cli config scripts docs tests time-os-ui -maxdepth 2 -type f 2>/dev/null | head -n 200
total 1880
drwxr-xr-x  70 molhamhomsi  staff    2240 Feb 11 01:14 .
drwxr-xr-x  26 molhamhomsi  staff     832 Feb  8 15:18 ..
-rw-r--r--   1 molhamhomsi  staff   18436 Feb 10 22:38 .DS_Store
drwxr-xr-x  13 molhamhomsi  staff     416 Feb 11 01:37 .git
drwxr-xr-x   3 molhamhomsi  staff      96 Feb  8 20:52 .github
-rw-r--r--   1 molhamhomsi  staff    1063 Feb 10 20:59 .gitignore
drwxr-xr-x   4 molhamhomsi  staff     128 Feb 10 12:19 .logs
-rw-r--r--   1 molhamhomsi  staff    2948 Feb 11 01:14 .pre-commit-config.yaml
drwxr-xr-x   6 molhamhomsi  staff     192 Feb  3 18:38 .pytest_cache
drwxr-xr-x   7 molhamhomsi  staff     224 Feb 11 01:15 .ruff_cache
drwxr-xr-x   9 molhamhomsi  staff     288 Feb 10 20:13 .venv
-rw-r--r--   1 molhamhomsi  staff   33061 Feb 10 23:43 ARCHITECTURE_FIXES.md
-rw-r--r--   1 molhamhomsi  staff   30026 Feb 10 23:43 ARCHITECTURE_V2.md
-rw-r--r--   1 molhamhomsi  staff   26396 Feb 10 23:43 ARCHITECTURE_V3.md
-rw-r--r--   1 molhamhomsi  staff    3721 Feb 10 23:43 AUDIT.md
-rw-r--r--   1 molhamhomsi  staff    9910 Feb 10 23:43 COLLECTOR_AUDIT.md
-rw-r--r--   1 molhamhomsi  staff   32094 Feb 10 23:43 CRITIQUE.md
-rw-r--r--   1 molhamhomsi  staff   16949 Feb 10 23:43 DATA_WIRING_PLAN.md
-rw-r--r--   1 molhamhomsi  staff    1697 Feb 10 23:43 GAPS.md
-rw-r--r--   1 molhamhomsi  staff    3660 Feb 10 23:43 HEARTBEAT.md
-rw-r--r--   1 molhamhomsi  staff    6124 Feb 10 23:43 IMPLEMENTATION_LOG.md
-rw-r--r--   1 molhamhomsi  staff    7064 Feb 10 23:43 IMPLEMENTATION_PLAN_V4_FROZEN.md
-rw-r--r--   1 molhamhomsi  staff    4453 Feb 10 23:43 IMPLEMENTATION_STATE.md
-rw-r--r--   1 molhamhomsi  staff   16627 Feb 10 23:43 ISSUE_INDEX.md
-rw-r--r--@  1 molhamhomsi  staff   99223 Feb  3 02:07 MASTER_SPEC.md
-rw-r--r--@  1 molhamhomsi  staff    6380 Feb 10 22:23 Makefile
-rw-r--r--   1 molhamhomsi  staff   15691 Feb 10 23:43 PROPOSAL_SYSTEM_LOG.md
-rw-r--r--   1 molhamhomsi  staff    9065 Feb 10 23:43 PROPOSAL_SYSTEM_PLAN.md
-rw-r--r--   1 molhamhomsi  staff    7703 Feb 10 22:21 README.md
-rw-r--r--   1 molhamhomsi  staff   25932 Feb 10 23:43 SPEC_V4_EXECUTIVE_OS.md
-rw-r--r--   1 molhamhomsi  staff   30532 Feb 10 23:43 SURGICAL_PLAN.md
-rw-r--r--   1 molhamhomsi  staff      71 Feb  1 09:01 __init__.py
-rw-r--r--   1 molhamhomsi  staff     242 Feb 10 23:43 __main__.py
drwxr-xr-x   4 molhamhomsi  staff     128 Feb 10 22:38 __pycache__
-rw-r--r--   1 molhamhomsi  staff    1132 Feb 10 20:44 agent_index_log.md
-rw-r--r--   1 molhamhomsi  staff     705 Feb  9 11:29 agent_state.json
drwxr-xr-x   7 molhamhomsi  staff     224 Feb 10 23:43 api
drwxr-xr-x   7 molhamhomsi  staff     224 Feb 10 23:43 cli
-rw-r--r--   1 molhamhomsi  staff   11438 Feb 10 23:43 cli.py
-rw-r--r--   1 molhamhomsi  staff   18868 Feb 10 23:43 cli_v4.py
drwxr-xr-x  10 molhamhomsi  staff     320 Feb 10 23:43 collectors
-rw-r--r--   1 molhamhomsi  staff    1015 Feb 10 23:43 com.mohtimeos.api.plist
drwx------  15 molhamhomsi  staff     480 Feb 10 23:43 config
drwxr-xr-x   8 molhamhomsi  staff     256 Feb  9 12:57 dashboard
drwxr-xr-x  26 molhamhomsi  staff     832 Feb 11 01:35 data
drwxr-xr-x   6 molhamhomsi  staff     192 Feb 10 23:43 design
drwxr-xr-x   4 molhamhomsi  staff     128 Feb  9 17:37 dist
drwxr-xr-x  21 molhamhomsi  staff     672 Feb 10 23:43 docs
drwxr-xr-x  19 molhamhomsi  staff     608 Feb 10 23:43 engine
drwxr-xr-x  80 molhamhomsi  staff    2560 Feb 10 23:43 lib
drwxr-xr-x   4 molhamhomsi  staff     128 Feb 10 22:38 logs
drwxr-xr-x   3 molhamhomsi  staff      96 Jan 30 19:32 moh_time_os
drwxr-xr-x   6 molhamhomsi  staff     192 Feb 10 20:21 moh_time_os.egg-info
drwxr-xr-x  41 molhamhomsi  staff    1312 Feb 10 22:38 out
drwxr-xr-x   7 molhamhomsi  staff     224 Feb 10 22:38 output
-rw-r--r--   1 molhamhomsi  staff    3014 Feb 10 22:23 pyproject.toml
-rw-r--r--   1 molhamhomsi  staff     173 Feb 10 11:02 pytest.ini
-rw-r--r--   1 molhamhomsi  staff     189 Feb  9 16:46 requirements.txt
-rwxr-xr-x   1 molhamhomsi  staff     844 Feb 10 23:43 run_cycle.sh
drwxr-xr-x  20 molhamhomsi  staff     640 Feb 10 23:43 scripts
-rw-r--r--   1 molhamhomsi  staff    1813 Feb 10 23:43 setup.py
-rw-r--r--   1 molhamhomsi  staff  163075 Feb 10 23:43 spec_time_os_v2_1_final.md
-rw-r--r--   1 molhamhomsi  staff       0 Feb  6 20:26 state.db
drwxr-xr-x  15 molhamhomsi  staff     480 Feb 10 23:43 tests
drwxr-xr-x  19 molhamhomsi  staff     608 Feb 10 23:43 time-os-ui
-rw-r--r--   1 molhamhomsi  staff       0 Feb  6 21:03 time_os.db
-rw-------@  1 molhamhomsi  staff   14957 Feb  5 03:19 time_os_backend_spec_pack.zip
drwxr-xr-x@  9 molhamhomsi  staff     288 Feb  6 11:02 time_os_defect_prompt_pack
drwxr-xr-x   3 molhamhomsi  staff      96 Feb 10 23:43 tools
-rw-r--r--   1 molhamhomsi  staff  248908 Feb 10 22:23 uv.lock
./time_os_defect_prompt_pack/.env.example
./pytest.ini
./time-os-ui/.env.example
./requirements.txt
./.pre-commit-config.yaml
./pyproject.toml
./setup.py
api/server.py
api/.DS_Store
api/__pycache__/server.cpython-314.pyc
api/__pycache__/spec_router.cpython-314.pyc
api/spec_router.py
api/BYTECODE_MANIFEST.md
lib/sync.py
lib/capacity_truth/__init__.py
lib/capacity_truth/debt_tracker.py
lib/capacity_truth/calculator.py
lib/store.py
lib/analyzers/time.py
lib/analyzers/patterns.py
lib/analyzers/attendance.py
lib/analyzers/__init__.py
lib/analyzers/priority.py
lib/analyzers/orchestrator.py
lib/analyzers/anomaly.py
lib/migrations/v29_spec_alignment.py
lib/migrations/v29_inbox_schema.py
lib/migrations/v29_full_schema.py
lib/migrations/v4_milestone4_intersections_reports_policy.py
lib/migrations/__init__.py
lib/migrations/v4_milestone1_truth_proof.py
lib/migrations/v29_engagement_lifecycle.py
lib/migrations/v29_org_settings.py
lib/migrations/spec_schema_migration.py
lib/migrations/normalize_client_ids.py
lib/migrations/rebuild_schema_v12.py
lib/migrations/seed_brands.py
lib/migrations/migrate_to_spec_v12.py
lib/db.py
lib/task_duration.py
lib/state_store.py
lib/build_client_identities.py
lib/lane_assigner.py
lib/backup.py
lib/moves.py
lib/collectors/tasks.py
lib/collectors/asana.py
lib/collectors/__init__.py
lib/collectors/xero.py
lib/collectors/calendar.py
lib/collectors/gmail.py
lib/collectors/orchestrator.py
lib/collectors/base.py
lib/.DS_Store
lib/contacts.py
lib/resolve.py
lib/collector_registry.py
lib/db_writer.py
lib/build_team_registry.py
lib/paths.py
lib/notifier/briefs.py
lib/notifier/__init__.py
lib/notifier/engine.py
lib/resolution_queue.py
lib/client_truth/health_calculator.py
lib/client_truth/__init__.py
lib/client_truth/linker.py
lib/aggregator.py
lib/maintenance.py
lib/scheduling_engine.py
lib/health.py
lib/change_bundles.py
lib/classify.py
lib/state_tracker.py
lib/contracts/predicates.py
lib/contracts/thresholds.py
lib/contracts/__init__.py
lib/contracts/invariants.py
lib/contracts/schema.py
lib/protocol.py
lib/move_executor.py
lib/commitment_truth/detector.py
lib/commitment_truth/__init__.py
lib/commitment_truth/llm_extractor.py
lib/commitment_truth/commitment_manager.py
lib/sync_asana.py
lib/brief.py
lib/__init__.py
lib/link_projects.py
lib/gates.py
lib/routing_engine.py
lib/sync_xero.py
lib/priority.py
lib/__pycache__/entities.cpython-314.pyc
lib/__pycache__/collector_registry.cpython-314.pyc
lib/__pycache__/entities.cpython-312.pyc
lib/__pycache__/db.cpython-314.pyc
lib/__pycache__/change_bundles.cpython-314.pyc
lib/__pycache__/autonomous_loop.cpython-314.pyc
lib/__pycache__/entity_linker.cpython-314.pyc
lib/__pycache__/state_tracker.cpython-314.pyc
lib/__pycache__/items.cpython-314.pyc
lib/__pycache__/items.cpython-312.pyc
lib/__pycache__/calibration.cpython-314.pyc
lib/__pycache__/paths.cpython-312.pyc
lib/__pycache__/__init__.cpython-314.pyc
lib/__pycache__/state_store.cpython-314.pyc
lib/__pycache__/queries.cpython-312.pyc
lib/__pycache__/health.cpython-314.pyc
lib/__pycache__/store.cpython-312.pyc
lib/__pycache__/governance.cpython-314.pyc
lib/__pycache__/backup.cpython-312.pyc
lib/__pycache__/paths.cpython-314.pyc
lib/__pycache__/__init__.cpython-312.pyc
lib/__pycache__/queries.cpython-314.pyc
lib/__pycache__/health.cpython-312.pyc
lib/__pycache__/store.cpython-314.pyc
lib/__pycache__/backup.cpython-314.pyc
lib/config_store.py
lib/commitment_extractor.py
lib/reasoner/decisions.py
lib/reasoner/__init__.py
lib/reasoner/engine.py
lib/safety/audit.py
lib/safety/__init__.py
lib/safety/json_parse.py
lib/safety/context.py
lib/safety/utils.py
lib/safety/migrations.py
lib/safety/schema.py
lib/integrations/calendar_integration.py
lib/integrations/__init__.py
lib/integrations/clawdbot_api.py
lib/integrations/tasks_integration.py
lib/integrations/email_integration.py
lib/v5/database.py
lib/v5/data_loader.py
lib/v5/__init__.py
lib/v5/orchestrator.py
lib/priority_engine.py
lib/normalize/domain_models.py
lib/normalize/resolvers.py
lib/normalize/__init__.py
lib/enrollment_detector.py
lib/capture.py
lib/ui_spec_v21/suppression.py
lib/ui_spec_v21/engagement_lifecycle.py
lib/ui_spec_v21/IMPLEMENTATION_CHECKLIST.md
lib/ui_spec_v21/CONTRACT_MAP.md
lib/ui_spec_v21/org_settings.py
lib/ui_spec_v21/health.py
lib/ui_spec_v21/__init__.py
lib/ui_spec_v21/time_utils.py
lib/ui_spec_v21/inbox_lifecycle.py
lib/ui_spec_v21/issue_lifecycle.py
lib/ui_spec_v21/detectors.py
lib/ui_spec_v21/endpoints.py
lib/ui_spec_v21/evidence.py
lib/ui_spec_v21/inbox_enricher.py
lib/agency_snapshot/delivery.py
lib/agency_snapshot/client360_page10.py
lib/agency_snapshot/confidence.py
lib/agency_snapshot/scoring.py
lib/agency_snapshot/cash_ar_page12.py
lib/agency_snapshot/__init__.py
lib/agency_snapshot/comms_commitments_page11.py
lib/agency_snapshot/comms_commitments.py
lib/agency_snapshot/generator.py
lib/agency_snapshot/capacity_command_page7.py
lib/agency_snapshot/cash_ar.py
lib/agency_snapshot/client360.py
lib/agency_snapshot/deltas.py
lib/v4/coupling_service.py
lib/v4/proposal_service.py
lib/v4/seed_identities.py
lib/v4/artifact_service.py
lib/v4/proposal_aggregator.py
lib/v4/proposal_scoring.py
lib/v4/__init__.py
lib/v4/ingest_pipeline.py
lib/v4/identity_service.py
lib/v4/report_service.py
lib/v4/policy_service.py
lib/v4/orchestrator.py
lib/v4/entity_link_service.py
lib/v4/signal_service.py
lib/v4/issue_service.py
lib/v4/collector_hooks.py
lib/entity_linker.py
lib/delegation_engine.py
lib/queries.py
lib/conflicts.py
lib/executor/handlers.py
lib/executor/__init__.py
lib/executor/engine.py
lib/autonomous_loop.py
lib/entities.py
lib/normalizer.py
lib/projects.py
lib/cron_tasks.py
lib/sync_ar.py
lib/time_truth/rollover.py
lib/time_truth/calendar_sync.py
lib/time_truth/block_manager.py
lib/time_truth/brief.py
lib/time_truth/__init__.py
lib/time_truth/scheduler.py
molhamhomsi@Molhams-MacBook-Pro-746 moh_time_os % sed -n '1,220p' .pre-commit-config.yaml 2>/dev/null
sed -n '1,240p' pyproject.toml 2>/dev/null
sed -n '1,240p' pytest.ini 2>/dev/null
ls -la ruff.toml mypy.ini pyrightconfig.json tox.ini .editorconfig 2>/dev/null
# Pre-commit hooks - runs before every commit
# Install: pip install pre-commit && pre-commit install

repos:
  # ==========================================
  # RUFF - Fast Python linter + formatter
  # Only runs on active, maintained modules
  # ==========================================
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      # Linter - only run on v29/spec modules
      # Note: --ignore S110,S602,S608 skips security rules that are too noisy for legacy code
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix, --ignore, "S110,S602,S608,B904"]
        types_or: [python, pyi]
        files: ^(lib/ui_spec_v21|lib/collectors|lib/safety|lib/db|lib/paths|lib/collector_registry|api/spec_router|scripts/backfill|scripts/verify)/.*\.py$
      # Formatter - same scope
      - id: ruff-format
        types_or: [python, pyi]
        files: ^(lib/ui_spec_v21|lib/collectors|lib/safety|lib/db|lib/paths|lib/collector_registry|api/spec_router|scripts/backfill|scripts/verify)/.*\.py$

  # ==========================================
  # BANDIT - Security scanning
  # ==========================================
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.8
    hooks:
      - id: bandit
        args: [-r, -ll, --skip, "B101"]  # Skip assert warnings
        files: ^(lib/ui_spec_v21|lib/collectors|lib/safety|api/spec_router)/.*\.py$

  # ==========================================
  # GENERAL HOOKS
  # ==========================================
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
        files: ^(lib/ui_spec_v21|lib/collectors|lib/safety|api|tests|scripts)/
        exclude: \.md$
      - id: end-of-file-fixer
        files: ^(lib/ui_spec_v21|lib/collectors|lib/safety|api|tests|scripts)/
      - id: check-yaml
        files: ^(\.pre-commit-config\.yaml|pytest\.ini)$
      - id: check-json
        files: ^(lib|api|tests)/.*\.json$
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: detect-private-key

  # ==========================================
  # SQL INJECTION CHECK (custom)
  # Note: grep-based check. Known safe patterns excluded:
  # - lib/safety/migrations.py (trigger names from code)
  # - lib/safety/schema.py (table names from code)
  # - lib/ui_spec_v21/time_utils.py (table names from hardcoded list)
  # - api/server.py (constants, not user input)
  # ==========================================
  - repo: local
    hooks:
      - id: no-sql-fstrings
        name: Check for SQL f-string injection
        entry: bash -c 'grep -rn "execute.*f\"" --include="*.py" lib/ui_spec_v21/endpoints.py lib/ui_spec_v21/detectors.py lib/ui_spec_v21/inbox_lifecycle.py lib/ui_spec_v21/issue_lifecycle.py lib/collectors/ 2>/dev/null && exit 1 || exit 0'
        language: system
        pass_filenames: false
        types: [python]
# Moh Time OS - Project Configuration
# Toolchain: uv (Python package manager)
# API Framework: FastAPI/Uvicorn

[project]
name = "moh-time-os"
version = "1.0.0"
description = "Personal Operating System for Executive Workflows"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "flask>=3.0.0",
    "fastapi>=0.100.0",
    "uvicorn>=0.22.0",
    "pydantic>=2.0.0",
    "click>=8.0.0",
    "rich>=13.0.0",
    "cryptography>=42.0.0",
    "google-api-python-client>=2.100.0",
    "google-auth>=2.20.0",
    "google-auth-httplib2>=0.1.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
    "bandit>=1.7.0",
    "mypy>=1.8.0",
    "pre-commit>=3.0.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

# ==========================================
# HATCH - Build Configuration
# ==========================================
[tool.hatch.build.targets.wheel]
packages = ["lib", "api", "cli", "collectors", "engine"]

[tool.hatch.build.targets.sdist]
include = [
    "lib/",
    "api/",
    "cli/",
    "collectors/",
    "engine/",
    "tests/",
    "scripts/",
    "pyproject.toml",
    "README.md",
]

# ==========================================
# RUFF - Linting & Formatting
# ==========================================
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "S",      # flake8-bandit (security)
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "F401",   # unused imports (too noisy in large refactors)
    "S101",   # assert usage (allowed in tests)
    "B008",   # function call in default arg (FastAPI Depends)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "S105", "S106"]  # Allow asserts and hardcoded credentials in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false

# ==========================================
# BANDIT - Security Scanning
# ==========================================
[tool.bandit]
exclude_dirs = ["tests", ".venv", "venv"]
skips = ["B101"]  # Skip assert warnings

# ==========================================
# MYPY - Type Checking
# ==========================================
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
ignore_missing_imports = true
exclude = [
    "tests/",
    ".venv/",
    "venv/",
    "__pycache__/",
]

# ==========================================
# PYTEST - Testing
# ==========================================
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
filterwarnings = [
    "ignore::DeprecationWarning",
]
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
molhamhomsi@Molhams-MacBook-Pro-746 moh_time_os % python --version
uv --version
uv pip list | head -n 60
uv pip list | grep -E "ruff|pytest|fastapi|uvicorn|pydantic|sqlalchemy|alembic" || true
zsh: command not found: python
uv 0.8.11 (f892276ac 2025-08-14)
Package                  Version  Editable project location
------------------------ -------- ------------------------------------
annotated-doc            0.0.4
annotated-types          0.7.0
anyio                    4.12.1
bandit                   1.9.3
blinker                  1.9.0
certifi                  2026.1.4
cffi                     2.0.0
cfgv                     3.5.0
charset-normalizer       3.4.4
click                    8.3.1
coverage                 7.13.4
cryptography             46.0.4
distlib                  0.4.0
fastapi                  0.128.7
filelock                 3.20.3
flask                    3.1.2
google-api-core          2.29.0
google-api-python-client 2.189.0
google-auth              2.48.0
google-auth-httplib2     0.3.0
googleapis-common-protos 1.72.0
h11                      0.16.0
httpcore                 1.0.9
httplib2                 0.31.2
httpx                    0.28.1
identify                 2.6.16
idna                     3.11
iniconfig                2.3.0
itsdangerous             2.2.0
jinja2                   3.1.6
librt                    0.7.8
markdown-it-py           4.0.0
markupsafe               3.0.3
mdurl                    0.1.2
moh-time-os              1.0.0    /Users/molhamhomsi/clawd/moh_time_os
mypy                     1.19.1
mypy-extensions          1.1.0
nodeenv                  1.10.0
packaging                26.0
pathspec                 1.0.4
pip                      26.0.1
platformdirs             4.5.1
pluggy                   1.6.0
pre-commit               4.5.1
proto-plus               1.27.1
protobuf                 6.33.5
pyasn1                   0.6.2
pyasn1-modules           0.4.2
pycparser                3.0
pydantic                 2.12.5
pydantic-core            2.41.5
pygments                 2.19.2
pyparsing                3.3.2
pytest                   9.0.2
pytest-cov               7.0.0
pyyaml                   6.0.3
requests                 2.32.5
rich                     14.3.2
fastapi                  0.128.7
pydantic                 2.12.5
pydantic-core            2.41.5
pytest                   9.0.2
pytest-cov               7.0.0
ruff                     0.15.0
uvicorn                  0.40.0
molhamhomsi@Molhams-MacBook-Pro-746 moh_time_os % ls -la scripts/verify_pristine.sh 2>/dev/null
sed -n '1,260p' scripts/verify_pristine.sh 2>/dev/null
uv run pre-commit run --all-files
uv run pytest -q
-rwxr-xr-x  1 molhamhomsi  staff  5469 Feb 10 22:24 scripts/verify_pristine.sh
#!/usr/bin/env bash
# verify_pristine.sh - Full pristine verification for Moh Time OS
# Validates that the repo can be cloned fresh and run successfully.
#
# Usage: ./scripts/verify_pristine.sh
#
# Toolchain: uv (Python package manager)
# API Framework: FastAPI/Uvicorn

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT=$(pwd)

echo "========================================"
echo "MOH TIME OS — PRISTINE VERIFICATION"
echo "========================================"
echo "Repo: $REPO_ROOT"
echo "Date: $(date -Iseconds)"
echo ""

PASS=0
FAIL=0

pass() {
    echo "✅ PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "❌ FAIL: $1"
    FAIL=$((FAIL + 1))
}

# ==========================================
# 1. Check no derived files tracked
# ==========================================
echo "=== Step 1: No derived files tracked ==="
if ./scripts/check_no_derived_tracked.sh; then
    pass "No derived files in git index"
else
    fail "Derived files found in git index"
fi
echo ""

# ==========================================
# 2. Install dependencies (uv)
# ==========================================
echo "=== Step 2: Install dependencies (uv sync) ==="
if command -v uv >/dev/null 2>&1; then
    if uv sync --all-extras 2>/dev/null; then
        pass "Dependencies installed via uv sync"
    else
        # Try with pip install for older uv versions
        if uv pip install -e ".[dev]" 2>/dev/null; then
            pass "Dependencies installed via uv pip install"
        else
            fail "uv sync/install failed"
        fi
    fi
else
    echo "⚠️  uv not found, attempting pip fallback..."
    if python3 -m pip install -e ".[dev]" --quiet 2>/dev/null; then
        pass "Dependencies installed via pip (fallback)"
    else
        fail "Dependency installation failed"
    fi
fi
echo ""

# ==========================================
# 3. Run pre-commit hooks
# ==========================================
echo "=== Step 3: Pre-commit hooks ==="
if command -v pre-commit >/dev/null 2>&1 || uv run pre-commit --version >/dev/null 2>&1; then
    # Use uv run if available, otherwise direct pre-commit
    PRE_COMMIT_CMD="pre-commit"
    if command -v uv >/dev/null 2>&1; then
        PRE_COMMIT_CMD="uv run pre-commit"
    fi

    if $PRE_COMMIT_CMD run -a 2>&1 | tee /tmp/precommit_output.txt; then
        pass "Pre-commit hooks passed"
    else
        # Check if it's just "no files to check" (which is fine)
        if grep -q "Passed\|Skipped" /tmp/precommit_output.txt && ! grep -q "Failed" /tmp/precommit_output.txt; then
            pass "Pre-commit hooks passed (some skipped)"
        else
            fail "Pre-commit hooks failed"
        fi
    fi
else
    echo "⚠️  pre-commit not available, skipping"
    PASS=$((PASS + 1))  # Count as pass if not available
fi
echo ""

# ==========================================
# 4. Run pytest (contract + evidence tests)
# ==========================================
echo "=== Step 4: Pytest (contract tests) ==="
PYTEST_CMD="python3 -m pytest"
if command -v uv >/dev/null 2>&1; then
    PYTEST_CMD="uv run pytest"
fi

# Run a subset of tests that should pass on a clean checkout
TEST_DIRS=""
[ -d "tests/contract" ] && TEST_DIRS="$TEST_DIRS tests/contract/"
[ -f "tests/test_safety.py" ] && TEST_DIRS="$TEST_DIRS tests/test_safety.py"

if [ -n "$TEST_DIRS" ]; then
    if $PYTEST_CMD $TEST_DIRS -q --tb=line 2>&1; then
        pass "Pytest contract tests passed"
    else
        fail "Pytest contract tests failed"
    fi
else
    echo "⚠️  No contract tests found, skipping"
    PASS=$((PASS + 1))
fi
echo ""

# ==========================================
# 5. API Server Health Check
# ==========================================
echo "=== Step 5: API server health check ==="

# Create temp data directory if needed
mkdir -p data
export MOH_TIME_OS_DB_PATH="${REPO_ROOT}/data/test_pristine.db"

# Start server in background on a test port
API_PORT=8421
export PORT=$API_PORT
echo "Starting API server on port $API_PORT..."

# Use uv run or direct python
if command -v uv >/dev/null 2>&1; then
    uv run python -m api.server &
else
    PYTHONPATH=. python3 -m api.server &
fi
API_PID=$!

# Wait for server to start (max 15 seconds)
HEALTH_OK=false
for i in $(seq 1 15); do
    sleep 1
    if curl -sf "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
        HEALTH_OK=true
        break
    fi
done

if $HEALTH_OK; then
    HEALTH_RESPONSE=$(curl -sf "http://localhost:${API_PORT}/api/health")
    echo "Health response: $HEALTH_RESPONSE"
    if echo "$HEALTH_RESPONSE" | grep -q '"status".*"healthy"'; then
        pass "API server /api/health returned healthy"
    else
        fail "API server /api/health returned unexpected response"
    fi
else
    fail "API server failed to start or respond within 15s"
fi

# Cleanup
echo "Shutting down API server (PID $API_PID)..."
kill $API_PID 2>/dev/null || true
wait $API_PID 2>/dev/null || true

# Remove test DB
rm -f "${REPO_ROOT}/data/test_pristine.db" 2>/dev/null || true
echo ""

# ==========================================
# Summary
# ==========================================
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "🎉 ALL CHECKS PASSED — PRISTINE VERIFIED"
    exit 0
else
    echo "💥 VERIFICATION FAILED — See errors above"
    exit 1
fi
ruff.....................................................................Passed
ruff-format..............................................................Passed
bandit...................................................................Passed
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check json...........................................(no files to check)Skipped
check for added large files..............................................Passed
check for merge conflicts................................................Passed
detect private key.......................................................Passed
Check for SQL f-string injection.........................................Passed
=========================================== test session starts ===========================================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/molhamhomsi/clawd/moh_time_os
configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)
testpaths: tests
plugins: anyio-4.12.1, cov-7.0.0
collected 199 items

tests/contract/test_collector_paths.py ....                                                         [  2%]
tests/contract/test_collector_registry.py ....FF.....                                               [  7%]
tests/contract/test_invariants.py .........                                                         [ 12%]
tests/contract/test_paths_enforcement.py .                                                          [ 12%]
tests/contract/test_predicates.py .......                                                           [ 16%]
tests/contract/test_schema.py ..............                                                        [ 23%]
tests/contract/test_state_store_cache.py ...                                                        [ 24%]
tests/contract/test_thresholds.py ............                                                      [ 30%]
tests/contract/test_traceability.py ....                                                            [ 32%]
tests/golden/test_golden_ar.py F..                                                                  [ 34%]
tests/golden/test_golden_counts.py .F..F.                                                           [ 37%]
tests/negative/test_empty_when_data_exists.py .....                                                 [ 39%]
tests/negative/test_missing_sections.py ........                                                    [ 43%]
tests/negative/test_patchwork_policy.py ....                                                        [ 45%]
tests/negative/test_unresolved_scopes.py .....                                                      [ 48%]
tests/test_api_contracts.py ...............                                                         [ 55%]
tests/test_cash_ar.py .............FFFFFFFFFFFF                                                     [ 68%]
tests/test_comms_commitments.py FFFFFFFFFFFFFFFFFFFFF                                               [ 78%]
tests/test_inbox_enrichment.py .....                                                                [ 81%]
tests/test_inbox_evidence_persistence.py ..........                                                 [ 86%]
tests/test_safety.py ...........................                                                    [100%]

================================================ FAILURES =================================================
_______________________________ TestLegacyBlocked.test_legacy_import_raises _______________________________
tests/contract/test_collector_registry.py:99: in test_legacy_import_raises
    from collectors._legacy import team_calendar  # noqa: F401
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/collectors/__init__.py:6: in <module>
    from .base import BaseCollector
lib/collectors/base.py:16: in <module>
    from ..state_store import StateStore, get_store
E   ImportError: attempted relative import beyond top-level package
______________________________ TestLegacyBlocked.test_legacy_getattr_raises _______________________________
tests/contract/test_collector_registry.py:103: in test_legacy_getattr_raises
    import collectors._legacy as legacy
lib/collectors/__init__.py:6: in <module>
    from .base import BaseCollector
lib/collectors/base.py:16: in <module>
    from ..state_store import StateStore, get_store
E   ImportError: attempted relative import beyond top-level package
________________________________ TestGoldenAR.test_total_ar_matches_golden ________________________________
tests/golden/test_golden_ar.py:31: in test_total_ar_matches_golden
    assert abs(actual - expected) < 0.01, (
E   AssertionError: Total AR changed: actual=1025020.48, golden=1027172.25. If intentional, update GOLDEN_EXPECTATIONS with PR justification.
E   assert 2151.7700000000186 < 0.01
E    +  where 2151.7700000000186 = abs((1025020.48 - 1027172.25))
________________________ TestGoldenCounts.test_unpaid_invoice_count_matches_golden ________________________
tests/golden/test_golden_counts.py:51: in test_unpaid_invoice_count_matches_golden
    assert actual == expected, (
E   AssertionError: Unpaid invoice count changed: actual=33, golden=34. If intentional, update GOLDEN_EXPECTATIONS with PR justification.
E   assert 33 == 34
______________ TestGoldenSnapshotCounts.test_snapshot_debtors_not_empty_when_invoices_exist _______________
tests/golden/test_golden_counts.py:108: in test_snapshot_debtors_not_empty_when_invoices_exist
    assert (
E   AssertionError: Normalized invoice count mismatch: 33 vs golden 34
E   assert 33 == 34
___________________________ TestValidInvalidAR.test_valid_ar_included_in_totals ___________________________
tests/test_cash_ar.py:295: in test_valid_ar_included_in_totals
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
_________________________ TestValidInvalidAR.test_invalid_ar_excluded_from_totals _________________________
tests/test_cash_ar.py:318: in test_invalid_ar_excluded_from_totals
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
___________________________ TestPortfolioOrdering.test_ordering_risk_band_first ___________________________
tests/test_cash_ar.py:363: in test_ordering_risk_band_first
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
_________________________ TestInvoiceOrdering.test_ordering_bucket_severity_first _________________________
tests/test_cash_ar.py:409: in test_ordering_bucket_severity_first
    result = engine.generate(selected_client_id="c1")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
______________________________________ TestCaps.test_invoice_cap_25 _______________________________________
tests/test_cash_ar.py:443: in test_invoice_cap_25
    result = engine.generate(selected_client_id="c1")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
_________________________________ TestCaps.test_portfolio_cap_12_default __________________________________
tests/test_cash_ar.py:466: in test_portfolio_cap_12_default
    result = engine.generate(expanded=False)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
_________________________________ TestCaps.test_portfolio_cap_30_expanded _________________________________
tests/test_cash_ar.py:490: in test_portfolio_cap_30_expanded
    result = engine.generate(expanded=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
___________________________________ TestCaps.test_global_actions_cap_10 ___________________________________
tests/test_cash_ar.py:515: in test_global_actions_cap_10
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
_______________________ TestInvalidARActions.test_missing_due_date_generates_action _______________________
tests/test_cash_ar.py:538: in test_missing_due_date_generates_action
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
_________________________ TestActionIdempotency.test_actions_have_idempotency_key _________________________
tests/test_cash_ar.py:572: in test_actions_have_idempotency_key
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
___________________________ TestActionIdempotency.test_idempotency_keys_unique ____________________________
tests/test_cash_ar.py:598: in test_idempotency_keys_unique
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
________________________ TestDataIntegrityGate.test_integrity_false_blocks_render _________________________
tests/test_cash_ar.py:612: in test_integrity_false_blocks_render
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:171: in generate
    all_invoices = self._get_all_ar_invoices()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/cash_ar.py:228: in _get_all_ar_invoices
    rows = self._query_all("""
lib/agency_snapshot/cash_ar.py:147: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: i.payment_date
______________________ TestResponseStatusDerivation.test_overdue_when_past_expected _______________________
tests/test_comms_commitments.py:138: in test_overdue_when_past_expected
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
________________________ TestResponseStatusDerivation.test_due_when_within_horizon ________________________
tests/test_comms_commitments.py:160: in test_due_when_within_horizon
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
__________________________ TestResponseStatusDerivation.test_ok_when_far_future ___________________________
tests/test_comms_commitments.py:188: in test_ok_when_far_future
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
____________________ TestExpectedResponseByDerivation.test_uses_stored_deadline_first _____________________
tests/test_comms_commitments.py:215: in test_uses_stored_deadline_first
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
_________________________ TestExpectedResponseByDerivation.test_vip_gets_6_hours __________________________
tests/test_comms_commitments.py:242: in test_vip_gets_6_hours
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
_______________________ TestExpectedResponseByDerivation.test_tier_b_gets_24_hours ________________________
tests/test_comms_commitments.py:274: in test_tier_b_gets_24_hours
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
_______________ TestCommitmentBreachClassification.test_broken_when_past_deadline_and_open ________________
tests/test_comms_commitments.py:308: in test_broken_when_past_deadline_and_open
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
______________ TestCommitmentBreachClassification.test_at_risk_when_deadline_within_horizon _______________
tests/test_comms_commitments.py:333: in test_at_risk_when_deadline_within_horizon
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
__________________________ TestHotListOrdering.test_overdue_before_due_before_ok __________________________
tests/test_comms_commitments.py:377: in test_overdue_before_due_before_ok
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
___________________________________ TestHotListCaps.test_default_cap_9 ____________________________________
tests/test_comms_commitments.py:415: in test_default_cap_9
    result = engine.generate(expanded=False)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
__________________________________ TestHotListCaps.test_expanded_cap_25 ___________________________________
tests/test_comms_commitments.py:439: in test_expanded_cap_25
    result = engine.generate(expanded=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
___________________________________ TestSnippetsCap.test_snippets_max_8 ___________________________________
tests/test_comms_commitments.py:469: in test_snippets_max_8
    result = engine.generate(selected_thread_id="thread1")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
__________________ TestThreadRoomStructure.test_selected_thread_has_all_required_fields ___________________
tests/test_comms_commitments.py:496: in test_selected_thread_has_all_required_fields
    result = engine.generate(selected_thread_id="thread1")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
_______________________ TestUnlinkedComms.test_unlinked_surfaces_as_unknown_triage ________________________
tests/test_comms_commitments.py:541: in test_unlinked_surfaces_as_unknown_triage
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
___________________________ TestUnlinkedComms.test_unlinked_includes_fix_action ___________________________
tests/test_comms_commitments.py:565: in test_unlinked_includes_fix_action
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
_________________________ TestActionIdempotency.test_actions_have_idempotency_key _________________________
tests/test_comms_commitments.py:606: in test_actions_have_idempotency_key
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
___________________________ TestActionIdempotency.test_idempotency_keys_unique ____________________________
tests/test_comms_commitments.py:632: in test_idempotency_keys_unique
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
________________________________ TestVIPClassification.test_tier_a_is_vip _________________________________
tests/test_comms_commitments.py:661: in test_tier_a_is_vip
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
________________________________ TestVIPClassification.test_starred_is_vip ________________________________
tests/test_comms_commitments.py:687: in test_starred_is_vip
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
__________________________ TestBaseScoreComputation.test_overdue_has_high_score ___________________________
tests/test_comms_commitments.py:712: in test_overdue_has_high_score
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
_________________________ TestDataIntegrityGate.test_integrity_false_is_reflected _________________________
tests/test_comms_commitments.py:728: in test_integrity_false_is_reflected
    result = engine.generate()
             ^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:255: in generate
    threads = self._get_all_threads()
              ^^^^^^^^^^^^^^^^^^^^^^^
lib/agency_snapshot/comms_commitments.py:318: in _get_all_threads
    rows = self._query_all("""
lib/agency_snapshot/comms_commitments.py:235: in _query_all
    rows = conn.execute(sql, params).fetchall()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
E   sqlite3.OperationalError: no such column: c.commitment_id
========================================= short test summary info =========================================
FAILED tests/contract/test_collector_registry.py::TestLegacyBlocked::test_legacy_import_raises - ImportError: attempted relative import beyond top-level package
FAILED tests/contract/test_collector_registry.py::TestLegacyBlocked::test_legacy_getattr_raises - ImportError: attempted relative import beyond top-level package
FAILED tests/golden/test_golden_ar.py::TestGoldenAR::test_total_ar_matches_golden - AssertionError: Total AR changed: actual=1025020.48, golden=1027172.25. If intentional, update GOLDEN_...
FAILED tests/golden/test_golden_counts.py::TestGoldenCounts::test_unpaid_invoice_count_matches_golden - AssertionError: Unpaid invoice count changed: actual=33, golden=34. If intentional, update GOLDEN_EXPE...
FAILED tests/golden/test_golden_counts.py::TestGoldenSnapshotCounts::test_snapshot_debtors_not_empty_when_invoices_exist - AssertionError: Normalized invoice count mismatch: 33 vs golden 34
FAILED tests/test_cash_ar.py::TestValidInvalidAR::test_valid_ar_included_in_totals - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestValidInvalidAR::test_invalid_ar_excluded_from_totals - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestPortfolioOrdering::test_ordering_risk_band_first - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestInvoiceOrdering::test_ordering_bucket_severity_first - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestCaps::test_invoice_cap_25 - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestCaps::test_portfolio_cap_12_default - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestCaps::test_portfolio_cap_30_expanded - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestCaps::test_global_actions_cap_10 - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestInvalidARActions::test_missing_due_date_generates_action - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestActionIdempotency::test_actions_have_idempotency_key - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestActionIdempotency::test_idempotency_keys_unique - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_cash_ar.py::TestDataIntegrityGate::test_integrity_false_blocks_render - sqlite3.OperationalError: no such column: i.payment_date
FAILED tests/test_comms_commitments.py::TestResponseStatusDerivation::test_overdue_when_past_expected - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestResponseStatusDerivation::test_due_when_within_horizon - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestResponseStatusDerivation::test_ok_when_far_future - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestExpectedResponseByDerivation::test_uses_stored_deadline_first - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestExpectedResponseByDerivation::test_vip_gets_6_hours - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestExpectedResponseByDerivation::test_tier_b_gets_24_hours - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestCommitmentBreachClassification::test_broken_when_past_deadline_and_open - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestCommitmentBreachClassification::test_at_risk_when_deadline_within_horizon - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestHotListOrdering::test_overdue_before_due_before_ok - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestHotListCaps::test_default_cap_9 - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestHotListCaps::test_expanded_cap_25 - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestSnippetsCap::test_snippets_max_8 - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestThreadRoomStructure::test_selected_thread_has_all_required_fields - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestUnlinkedComms::test_unlinked_surfaces_as_unknown_triage - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestUnlinkedComms::test_unlinked_includes_fix_action - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestActionIdempotency::test_actions_have_idempotency_key - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestActionIdempotency::test_idempotency_keys_unique - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestVIPClassification::test_tier_a_is_vip - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestVIPClassification::test_starred_is_vip - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestBaseScoreComputation::test_overdue_has_high_score - sqlite3.OperationalError: no such column: c.commitment_id
FAILED tests/test_comms_commitments.py::TestDataIntegrityGate::test_integrity_false_is_reflected - sqlite3.OperationalError: no such column: c.commitment_id
===================================== 38 failed, 161 passed in 2.36s ======================================
molhamhomsi@Molhams-MacBook-Pro-746 moh_time_os % ls -la api
sed -n '1,220p' api/server.py 2>/dev/null
ls -la api/spec_router.py 2>/dev/null && sed -n '1,260p' api/spec_router.py 2>/dev/null
total 504
drwxr-xr-x   7 molhamhomsi  staff     224 Feb 10 23:43 .
drwxr-xr-x  70 molhamhomsi  staff    2240 Feb 11 01:14 ..
-rw-r--r--   1 molhamhomsi  staff    6148 Feb 10 22:05 .DS_Store
-rw-r--r--   1 molhamhomsi  staff   25699 Feb 10 23:43 BYTECODE_MANIFEST.md
drwxr-xr-x   4 molhamhomsi  staff     128 Feb 11 00:18 __pycache__
-rw-r--r--   1 molhamhomsi  staff  177489 Feb 10 23:43 server.py
-rw-r--r--   1 molhamhomsi  staff   39565 Feb 10 23:43 spec_router.py
"""
MOH TIME OS API Server - REST API for dashboard and integrations.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from lib import db as db_module
from lib import paths
from lib.analyzers import AnalyzerOrchestrator
from lib.autonomous_loop import AutonomousLoop
from lib.calibration import CalibrationEngine
from lib.change_bundles import (
    create_bundle,
    create_task_bundle,
    get_bundle,
    list_bundles,
    list_rollbackable_bundles,
    mark_applied,
    mark_failed,
    rollback_bundle,
)
from lib.collectors import CollectorOrchestrator
from lib.governance import DomainMode, get_governance
from lib.state_store import get_store
from lib.ui_spec_v21.detectors import DetectorRunner
from lib.v4.coupling_service import CouplingService
from lib.v4.issue_service import IssueService
from lib.v4.proposal_service import ProposalService

logger = logging.getLogger(__name__)

# Legacy filter: tasks overdue more than this many days are considered archived/legacy
# and excluded from active proposals to avoid noise pollution
LEGACY_OVERDUE_THRESHOLD_DAYS = 365

# FastAPI app initialization
app = FastAPI(
    title="MOH TIME OS API",
    description="Personal Operating System API - Direct control without AI",
    version="1.0.0",
)

# CORS middleware - configurable via CORS_ORIGINS env var
# Dev default: allow all origins; Production: set CORS_ORIGINS to comma-separated list
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
cors_origins = (
    ["*"]
    if cors_origins_env == "*"
    else [o.strip() for o in cors_origins_env.split(",")]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
store = get_store()
collectors = CollectorOrchestrator(store=store)
analyzers = AnalyzerOrchestrator(store=store)
governance = get_governance(store=store)

# UI directory (built Vite app)
UI_DIR = paths.app_home() / "time-os-ui" / "dist"

# ==== Spec v2.9 Router ====
# Mount spec-compliant endpoints at /api/v2
# These implement CLIENT-UI-SPEC-v2.9.md using lib/ui_spec_v21 modules
from api.spec_router import spec_router  # noqa: E402 - intentionally imported here, right before use

app.include_router(spec_router, prefix="/api/v2")


# ==== DB Startup & Migrations ====
@app.on_event("startup")
async def run_db_migrations_on_startup():
    """Run DB migrations and log DB info at startup."""
    try:
        db_path = db_module.get_db_path()
        logger.info("=== MOH TIME OS Startup ===")
        logger.info(f"DB path: {db_path}")
        logger.info(f"DB exists: {db_path.exists()}")

        if db_path.exists():
            with db_module.get_connection() as conn:
                version = db_module.get_schema_version(conn)
                logger.info(f"DB schema version (user_version): {version}")

        # Run migrations
        migration_result = db_module.run_startup_migrations()
        if migration_result.get("columns_added"):
            logger.info(
                f"Migrations added columns: {migration_result['columns_added']}"
            )

    except Exception as e:
        logger.warning(f"DB startup check failed: {e}")


# ==== Detector Startup ====
# Run detectors on startup to populate inbox_items
@app.on_event("startup")
async def run_detectors_on_startup():
    """Run detectors to populate inbox_items table on server start."""
    try:
        db_path = db_module.get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        detector = DetectorRunner(conn)
        result = detector.run_all()
        logger.info(
            f"Detectors: {result.issues_created} issues, {result.flagged_signals_created} flagged signals created"
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.info(f"[WARN] Detector startup failed: {e}")


# Root endpoint
@app.get("/")
async def root(request: Request = None):
    """Serve the dashboard UI."""
    index_path = UI_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    # UI build missing - return helpful 404 instead of 500
    hint = "cd time-os-ui && npm ci && npm run build"

    # Check Accept header to decide format
    accept = ""
    if request:
        accept = request.headers.get("accept", "")

    if "text/html" in accept:
        html = f"""<!DOCTYPE html>
<html><head><title>UI Build Missing</title></head>
<body style="font-family: system-ui; padding: 2rem;">
<h1>UI Build Missing</h1>
<p>The frontend has not been built yet.</p>
<pre style="background: #f4f4f4; padding: 1rem; border-radius: 4px;">Run: {hint}</pre>
<p><a href="/docs">API Documentation</a> | <a href="/api/health">Health Check</a></p>
</body></html>"""
        return HTMLResponse(content=html, status_code=404)

    return JSONResponse(
        content={"error": "ui_build_missing", "hint": hint}, status_code=404
    )


# ==== Pydantic Models ====


class ApprovalAction(BaseModel):
    action: str


class ModeChange(BaseModel):
    mode: str


# ==== Overview Endpoint ====


@app.get("/api/overview")
async def get_overview():
    """Get dashboard overview with priorities, calendar, decisions, anomalies."""
    # Get priority queue
    priority_queue = (
        analyzers.priority_analyzer.analyze()
        if hasattr(analyzers, "priority_analyzer")
        else []
    )
    top_priorities = sorted(
        priority_queue, key=lambda x: x.get("score", 0), reverse=True
    )[:5]

    # Get today's events
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    events = store.query(
        "SELECT * FROM events WHERE date(start_time) = ? ORDER BY start_time", [today]
    )

    # Get pending decisions
    pending_decisions = store.query(
        "SELECT * FROM decisions WHERE approved IS NULL ORDER BY created_at DESC LIMIT 5"
    )

    # Get anomalies
    anomalies = store.query(
        "SELECT * FROM insights WHERE type = 'anomaly' AND (expires_at IS NULL OR expires_at > datetime('now')) ORDER BY created_at DESC LIMIT 5"
    )

    return {
        "priorities": {"items": top_priorities, "total": len(priority_queue)},
        "calendar": {"events": [dict(e) for e in events], "event_count": len(events)},
        "decisions": {
            "pending": [dict(d) for d in pending_decisions],
            "pending_count": store.count("decisions", "approved IS NULL"),
        },
        "anomalies": {
            "items": [dict(a) for a in anomalies],
            "total": store.count(
                "insights",
-rw-r--r--  1 molhamhomsi  staff  39565 Feb 10 23:43 api/spec_router.py
"""
Spec-Compliant API Router — CLIENT-UI-SPEC-v2.9.md

This router implements the API endpoints defined in the spec using
the ui_spec_v21 modules. Mount this on the main FastAPI app.

Usage in server.py:
    from api.spec_router import spec_router
    app.include_router(spec_router, prefix="/api/v2")
"""

import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from lib import paths
from lib.ui_spec_v21.endpoints import (
    ClientEndpoints,
    FinancialsEndpoints,
    InboxEndpoints,
)
from lib.ui_spec_v21.inbox_lifecycle import InboxLifecycleManager
from lib.ui_spec_v21.issue_lifecycle import (
    AVAILABLE_ACTIONS,
    IssueLifecycleManager,
    IssueState,
)
from lib.ui_spec_v21.time_utils import now_iso

# Import safety modules
try:
    from lib.safety import WriteContext, generate_request_id, get_git_sha

    SAFETY_ENABLED = True
except ImportError:
    SAFETY_ENABLED = False
    WriteContext = None

logger = logging.getLogger(__name__)

# Router
spec_router = APIRouter(tags=["Spec v2.9"])

# Database path
DB_PATH = paths.db_path()


def get_db() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db_with_context(
    actor: str,
    request_id: str | None = None,
    source: str = "api",
) -> Generator[sqlite3.Connection, None, None]:
    """
    Get database connection with write context for attributed writes.

    Usage:
        with get_db_with_context(actor="user123", request_id="req-xxx") as conn:
            conn.execute("UPDATE ...")
            conn.commit()
    """
    conn = get_db()
    try:
        if SAFETY_ENABLED and WriteContext:
            with WriteContext(conn, actor=actor, source=source, request_id=request_id):
                yield conn
        else:
            yield conn
    finally:
        conn.close()


def get_request_id(
    x_request_id: str | None = Header(None, alias="X-Request-Id"),
) -> str:
    """Get or generate request ID from header."""
    if x_request_id:
        return x_request_id
    if SAFETY_ENABLED:
        return generate_request_id()
    return f"req-{now_iso()}"


# ==== Request/Response Models ====


class InboxActionRequest(BaseModel):
    action: str
    assign_to: str | None = None
    snooze_days: int | None = None
    link_engagement_id: str | None = None
    select_candidate_id: str | None = None
    note: str | None = None


class IssueTransitionRequest(BaseModel):
    action: str
    assigned_to: str | None = None
    snooze_days: int | None = None
    note: str | None = None


# ==== Client Endpoints (§7.1-7.3, 7.9) ====


@spec_router.get("/clients")
async def get_clients(
    status: str | None = Query(
        None, description="Filter by status: active|recently_active|cold"
    ),
    tier: str | None = Query(None, description="Filter by tier"),
    has_issues: bool | None = Query(
        None, description="Filter clients with open issues"
    ),
    has_overdue_ar: bool | None = Query(
        None, description="Filter clients with overdue AR"
    ),
):
    """
    GET /api/v2/clients

    Spec: 7.1 Client Index
    """
    conn = get_db()
    try:
        endpoints = ClientEndpoints(conn)
        filters = {}
        if status:
            filters["status"] = status
        if tier:
            filters["tier"] = tier
        if has_issues:
            filters["has_issues"] = has_issues
        if has_overdue_ar:
            filters["has_overdue_ar"] = has_overdue_ar

        return endpoints.get_clients(filters)
    finally:
        conn.close()


@spec_router.get("/clients/{client_id}")
async def get_client_detail(
    client_id: str,
    include: str | None = Query(
        None, description="Comma-separated sections to include"
    ),
):
    """
    GET /api/v2/clients/:id

    Spec: 7.2 Active Client Detail, 7.9 Include Policy
    """
    conn = get_db()
    try:
        endpoints = ClientEndpoints(conn)
        include_sections = include.split(",") if include else None
        result, error_code = endpoints.get_client_detail(client_id, include_sections)
        if error_code:
            raise HTTPException(
                status_code=error_code, detail=result.get("error", "Error")
            )
        if not result:
            raise HTTPException(status_code=404, detail="Client not found")
        return result
    finally:
        conn.close()


@spec_router.get("/clients/{client_id}/snapshot")
async def get_client_snapshot(
    client_id: str,
    context_issue_id: str | None = Query(None),
    context_inbox_item_id: str | None = Query(None),
):
    """
    GET /api/v2/clients/:id/snapshot

    Spec: 7.3 Client Snapshot (Cold clients from Inbox)
    """
    conn = get_db()
    try:
        endpoints = ClientEndpoints(conn)
        result = endpoints.get_client_snapshot(
            client_id,
            context_issue_id=context_issue_id,
            context_inbox_item_id=context_inbox_item_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Client not found")
        return result
    finally:
        conn.close()


# ==== Financials Endpoints (§7.5) ====


@spec_router.get("/clients/{client_id}/invoices")
async def get_client_invoices(
    client_id: str,
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    """
    GET /api/v2/clients/:id/invoices

    Spec: 7.5 Financials
    """
    conn = get_db()
    try:
        endpoints = FinancialsEndpoints(conn)
        return endpoints.get_invoices(
            client_id, {"status": status, "page": page, "limit": limit}
        )
    finally:
        conn.close()


@spec_router.get("/clients/{client_id}/ar-aging")
async def get_client_ar_aging(client_id: str):
    """
    GET /api/v2/clients/:id/ar-aging

    Spec: 7.5 AR Aging Breakdown
    """
    conn = get_db()
    try:
        endpoints = FinancialsEndpoints(conn)
        return endpoints.get_ar_aging(client_id)
    finally:
        conn.close()


# ==== Inbox Endpoints (§7.10) ====


@spec_router.get("/inbox")
async def get_inbox(
    state: str | None = Query(None, description="Filter by state: proposed|snoozed"),
    type: str | None = Query(
        None, description="Filter by type: issue|flagged_signal|orphan|ambiguous"
    ),
    severity: str | None = Query(None, description="Filter by severity"),
    client_id: str | None = Query(None, description="Filter by client"),
    unread_only: bool | None = Query(None, description="Only unread items"),
    sort: str | None = Query(
        "severity", description="Sort by: severity|age|age_desc|client"
molhamhomsi@Molhams-MacBook-Pro-746 moh_time_os % uv run python -m api.server 2>/dev/null || uv run uvicorn api.server:app --port 8421

2026-02-11 01:38:05 [INFO] lib.state_store: StateStore initializing with DB: /Users/molhamhomsi/.moh_time_os/data/moh_time_os.db
2026-02-11 01:38:05 [INFO] lib.db: ==================================================
2026-02-11 01:38:05 [INFO] lib.db: MOH TIME OS Database Startup
2026-02-11 01:38:05 [INFO] lib.db: ==================================================
2026-02-11 01:38:05 [INFO] lib.db: Resolved DB path: /Users/molhamhomsi/.moh_time_os/data/moh_time_os.db
2026-02-11 01:38:05 [INFO] lib.db: DB exists: True
2026-02-11 01:38:05 [INFO] lib.db: Target SCHEMA_VERSION: 9
2026-02-11 01:38:05 [INFO] lib.db: Current user_version: 9
2026-02-11 01:38:05 [INFO] lib.db: Tables created: ['issues_v29', 'issue_transitions_v29', 'inbox_items_v29', 'inbox_suppression_rules_v29']
2026-02-11 01:38:05 [INFO] lib.db: OK clients present
2026-02-11 01:38:05 [INFO] lib.db: OK inbox_items_v29 present
2026-02-11 01:38:05 [INFO] lib.db: Final user_version: 9
2026-02-11 01:38:05 [INFO] lib.db: ==================================================
2026-02-11 01:38:05 [INFO] lib.state_store: StateStore ready, DB path: /Users/molhamhomsi/.moh_time_os/data/moh_time_os.db
2026-02-11 01:38:05 [INFO] CollectorOrchestrator: Initialized collector: tasks
2026-02-11 01:38:05 [INFO] CollectorOrchestrator: Initialized collector: calendar
2026-02-11 01:38:05 [INFO] CollectorOrchestrator: Initialized collector: gmail
2026-02-11 01:38:05 [INFO] CollectorOrchestrator: Initialized collector: asana
2026-02-11 01:38:05 [INFO] CollectorOrchestrator: Initialized collector: xero
INFO:     Started server process [23538]
INFO:     Waiting for application startup.
2026-02-11 01:38:05 [INFO] api.server: === MOH TIME OS Startup ===
2026-02-11 01:38:05 [INFO] api.server: DB path: /Users/molhamhomsi/.moh_time_os/data/moh_time_os.db
2026-02-11 01:38:05 [INFO] api.server: DB exists: True
2026-02-11 01:38:05 [INFO] api.server: DB schema version (user_version): 9
2026-02-11 01:38:05 [INFO] lib.db: ==================================================
2026-02-11 01:38:05 [INFO] lib.db: MOH TIME OS Database Startup
2026-02-11 01:38:05 [INFO] lib.db: ==================================================
2026-02-11 01:38:05 [INFO] lib.db: Resolved DB path: /Users/molhamhomsi/.moh_time_os/data/moh_time_os.db
2026-02-11 01:38:05 [INFO] lib.db: DB exists: True
2026-02-11 01:38:05 [INFO] lib.db: Target SCHEMA_VERSION: 9
2026-02-11 01:38:05 [INFO] lib.db: Current user_version: 9
2026-02-11 01:38:05 [INFO] lib.db: Migrations already applied, skipping
2026-02-11 01:38:05 [INFO] api.server: Detectors: 0 issues, 0 flagged signals created
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8421 (Press CTRL+C to quit)
INFO:     127.0.0.1:61762 - "GET /openapi.json HTTP/1.1" 200 OK
INFO:     127.0.0.1:61763 - "GET /openapi.json HTTP/1.1" 200 OK

(.venv) molhamhomsi@Molhams-MacBook-Pro-645 moh_time_os % curl -s http://127.0.0.1:8421/openapi.json | head -n 40
curl -s http://127.0.0.1:8421/openapi.json | wc -c
{"openapi":"3.1.0","info":{"title":"MOH TIME OS API","description":"Personal Operating System API - Direct control without AI","version":"1.0.0"},"paths":{"/api/v2/clients":{"get":{"tags":["Spec v2.9"],"summary":"Get Clients","description":"GET /api/v2/clients\n\nSpec: 7.1 Client Index","operationId":"get_clients_api_v2_clients_get","parameters":[{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by status: active|recently_active|cold","title":"Status"},"description":"Filter by status: active|recently_active|cold"},{"name":"tier","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by tier","title":"Tier"},"description":"Filter by tier"},{"name":"has_issues","in":"query","required":false,"schema":{"anyOf":[{"type":"boolean"},{"type":"null"}],"description":"Filter clients with open issues","title":"Has Issues"},"description":"Filter clients with open issues"},{"name":"has_overdue_ar","in":"query","required":false,"schema":{"anyOf":[{"type":"boolean"},{"type":"null"}],"description":"Filter clients with overdue AR","title":"Has Overdue Ar"},"description":"Filter clients with overdue AR"}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/clients/{client_id}":{"get":{"tags":["Spec v2.9"],"summary":"Get Client Detail","description":"GET /api/v2/clients/:id\n\nSpec: 7.2 Active Client Detail, 7.9 Include Policy","operationId":"get_client_detail_api_v2_clients__client_id__get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}},{"name":"include","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Comma-separated sections to include","title":"Include"},"description":"Comma-separated sections to include"}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/clients/{client_id}/snapshot":{"get":{"tags":["Spec v2.9"],"summary":"Get Client Snapshot","description":"GET /api/v2/clients/:id/snapshot\n\nSpec: 7.3 Client Snapshot (Cold clients from Inbox)","operationId":"get_client_snapshot_api_v2_clients__client_id__snapshot_get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}},{"name":"context_issue_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Context Issue Id"}},{"name":"context_inbox_item_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Context Inbox Item Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/clients/{client_id}/invoices":{"get":{"tags":["Spec v2.9"],"summary":"Get Client Invoices","description":"GET /api/v2/clients/:id/invoices\n\nSpec: 7.5 Financials","operationId":"get_client_invoices_api_v2_clients__client_id__invoices_get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}},{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by status","title":"Status"},"description":"Filter by status"},{"name":"page","in":"query","required":false,"schema":{"type":"integer","minimum":1,"default":1,"title":"Page"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","maximum":100,"minimum":1,"default":10,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/clients/{client_id}/ar-aging":{"get":{"tags":["Spec v2.9"],"summary":"Get Client Ar Aging","description":"GET /api/v2/clients/:id/ar-aging\n\nSpec: 7.5 AR Aging Breakdown","operationId":"get_client_ar_aging_api_v2_clients__client_id__ar_aging_get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/inbox":{"get":{"tags":["Spec v2.9"],"summary":"Get Inbox","description":"GET /api/v2/inbox\n\nSpec: 7.10 Control Room Inbox\n\nReturns inbox items with counts. Counts are always global (ignore filters).","operationId":"get_inbox_api_v2_inbox_get","parameters":[{"name":"state","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by state: proposed|snoozed","title":"State"},"description":"Filter by state: proposed|snoozed"},{"name":"type","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by type: issue|flagged_signal|orphan|ambiguous","title":"Type"},"description":"Filter by type: issue|flagged_signal|orphan|ambiguous"},{"name":"severity","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by severity","title":"Severity"},"description":"Filter by severity"},{"name":"client_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by client","title":"Client Id"},"description":"Filter by client"},{"name":"unread_only","in":"query","required":false,"schema":{"anyOf":[{"type":"boolean"},{"type":"null"}],"description":"Only unread items","title":"Unread Only"},"description":"Only unread items"},{"name":"sort","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Sort by: severity|age|age_desc|client","default":"severity","title":"Sort"},"description":"Sort by: severity|age|age_desc|client"}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/inbox/recent":{"get":{"tags":["Spec v2.9"],"summary":"Get Inbox Recent","description":"GET /api/v2/inbox/recent\n\nSpec: 7.10 Recently Actioned Tab","operationId":"get_inbox_recent_api_v2_inbox_recent_get","parameters":[{"name":"days","in":"query","required":false,"schema":{"type":"integer","maximum":90,"minimum":1,"description":"Number of days to look back","default":7,"title":"Days"},"description":"Number of days to look back"},{"name":"state","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by terminal state: linked_to_issue|dismissed","title":"State"},"description":"Filter by terminal state: linked_to_issue|dismissed"},{"name":"type","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by type","title":"Type"},"description":"Filter by type"}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/inbox/counts":{"get":{"tags":["Spec v2.9"],"summary":"Get Inbox Counts","description":"GET /api/v2/inbox/counts\n\nSpec: 7.10 Recommended separate counts endpoint (cacheable)","operationId":"get_inbox_counts_api_v2_inbox_counts_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/v2/inbox/{item_id}/action":{"post":{"tags":["Spec v2.9"],"summary":"Execute Inbox Action","description":"POST /api/v2/inbox/:id/action\n\nSpec: 7.10 Inbox Actions\n\nAll writes are attributed via write_context and audited.","operationId":"execute_inbox_action_api_v2_inbox__item_id__action_post","parameters":[{"name":"item_id","in":"path","required":true,"schema":{"type":"string","title":"Item Id"}},{"name":"actor","in":"query","required":true,"schema":{"type":"string","description":"User ID performing the action","title":"Actor"},"description":"User ID performing the action"},{"name":"X-Request-Id","in":"header","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Request-Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/InboxActionRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/inbox/{item_id}/read":{"post":{"tags":["Spec v2.9"],"summary":"Mark Inbox Read","description":"POST /api/v2/inbox/:id/read\n\nSpec: 1.10 Mark Read","operationId":"mark_inbox_read_api_v2_inbox__item_id__read_post","parameters":[{"name":"item_id","in":"path","required":true,"schema":{"type":"string","title":"Item Id"}},{"name":"actor","in":"query","required":true,"schema":{"type":"string","description":"User ID marking as read","title":"Actor"},"description":"User ID marking as read"},{"name":"X-Request-Id","in":"header","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Request-Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/issues":{"get":{"tags":["Spec v2.9"],"summary":"Get Issues","description":"GET /api/v2/issues\n\nSpec: 7.6 Issues","operationId":"get_issues_api_v2_issues_get","parameters":[{"name":"client_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by client","title":"Client Id"},"description":"Filter by client"},{"name":"state","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by state","title":"State"},"description":"Filter by state"},{"name":"severity","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by severity","title":"Severity"},"description":"Filter by severity"},{"name":"include_snoozed","in":"query","required":false,"schema":{"type":"boolean","description":"Include snoozed issues","default":false,"title":"Include Snoozed"},"description":"Include snoozed issues"},{"name":"include_suppressed","in":"query","required":false,"schema":{"type":"boolean","description":"Include suppressed issues","default":false,"title":"Include Suppressed"},"description":"Include suppressed issues"}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/issues/{issue_id}":{"get":{"tags":["Spec v2.9"],"summary":"Get Issue","description":"GET /api/v2/issues/:id\n\nSpec: 7.6 Issue Detail","operationId":"get_issue_api_v2_issues__issue_id__get","parameters":[{"name":"issue_id","in":"path","required":true,"schema":{"type":"string","title":"Issue Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/issues/{issue_id}/transition":{"post":{"tags":["Spec v2.9"],"summary":"Transition Issue","description":"POST /api/v2/issues/:id/transition\n\nSpec: 7.6 Issue Transitions","operationId":"transition_issue_api_v2_issues__issue_id__transition_post","parameters":[{"name":"issue_id","in":"path","required":true,"schema":{"type":"string","title":"Issue Id"}},{"name":"actor","in":"query","required":true,"schema":{"type":"string","description":"User ID performing the action","title":"Actor"},"description":"User ID performing the action"},{"name":"X-Request-Id","in":"header","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Request-Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/IssueTransitionRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/clients/{client_id}/signals":{"get":{"tags":["Spec v2.9"],"summary":"Get Client Signals","description":"GET /api/v2/clients/:id/signals\n\nSpec: 7.7 Signals","operationId":"get_client_signals_api_v2_clients__client_id__signals_get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}},{"name":"sentiment","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter: good|neutral|bad|all","title":"Sentiment"},"description":"Filter: good|neutral|bad|all"},{"name":"source","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"Filter by source","title":"Source"},"description":"Filter by source"},{"name":"days","in":"query","required":false,"schema":{"type":"integer","maximum":365,"minimum":1,"default":30,"title":"Days"}},{"name":"page","in":"query","required":false,"schema":{"type":"integer","minimum":1,"default":1,"title":"Page"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","maximum":100,"minimum":1,"default":20,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/clients/{client_id}/team":{"get":{"tags":["Spec v2.9"],"summary":"Get Client Team","description":"GET /api/v2/clients/:id/team\n\nSpec: 7.8 Team","operationId":"get_client_team_api_v2_clients__client_id__team_get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}},{"name":"days","in":"query","required":false,"schema":{"type":"integer","maximum":365,"minimum":1,"default":30,"title":"Days"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/team":{"get":{"tags":["Spec v2.9"],"summary":"Get Team","description":"GET /api/v2/team\n\nReturns all team members with workload metrics.","operationId":"get_team_api_v2_team_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/v2/engagements":{"get":{"tags":["Spec v2.9"],"summary":"Get Engagements","description":"GET /api/v2/engagements\n\nSpec: 7.4 Engagements","operationId":"get_engagements_api_v2_engagements_get","parameters":[{"name":"client_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Id"}},{"name":"state","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"State"}},{"name":"type","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Type"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","maximum":200,"minimum":1,"default":50,"title":"Limit"}},{"name":"offset","in":"query","required":false,"schema":{"type":"integer","minimum":0,"default":0,"title":"Offset"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/engagements/{engagement_id}":{"get":{"tags":["Spec v2.9"],"summary":"Get Engagement","description":"GET /api/v2/engagements/:id\n\nSpec: 7.4 Engagement Detail","operationId":"get_engagement_api_v2_engagements__engagement_id__get","parameters":[{"name":"engagement_id","in":"path","required":true,"schema":{"type":"string","title":"Engagement Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/engagements/{engagement_id}/transition":{"post":{"tags":["Spec v2.9"],"summary":"Transition Engagement","description":"POST /api/v2/engagements/:id/transition\n\nSpec: 7.11 Engagement Lifecycle Actions","operationId":"transition_engagement_api_v2_engagements__engagement_id__transition_post","parameters":[{"name":"engagement_id","in":"path","required":true,"schema":{"type":"string","title":"Engagement Id"}},{"name":"actor","in":"query","required":false,"schema":{"type":"string","default":"user","title":"Actor"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/EngagementTransitionRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/health":{"get":{"tags":["Spec v2.9"],"summary":"Health Check","description":"Health check endpoint.","operationId":"health_check_api_v2_health_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/v2/jobs/snooze-expiry":{"post":{"tags":["Spec v2.9"],"summary":"Run Snooze Expiry Job","description":"Run snooze expiry job.\n\nSpec: 6.5 Snooze Timer Execution\n\nShould be called hourly by a scheduler.","operationId":"run_snooze_expiry_job_api_v2_jobs_snooze_expiry_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/v2/jobs/regression-watch":{"post":{"tags":["Spec v2.9"],"summary":"Run Regression Watch Job","description":"Run regression watch expiry job.\n\nSpec: 6.5 Regression Watch (90-day)\n\nShould be called daily by a scheduler.","operationId":"run_regression_watch_job_api_v2_jobs_regression_watch_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/v2/priorities":{"get":{"tags":["Spec v2.9"],"summary":"Get Priorities V2","description":"GET /api/v2/priorities\n\nAlias to /api/priorities for frontend compatibility.","operationId":"get_priorities_v2_api_v2_priorities_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":20,"title":"Limit"}},{"name":"context","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Context"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/projects":{"get":{"tags":["Spec v2.9"],"summary":"Get Projects V2","description":"GET /api/v2/projects\n\nAlias to /api/projects for frontend compatibility.","operationId":"get_projects_v2_api_v2_projects_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}},{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/events":{"get":{"tags":["Spec v2.9"],"summary":"Get Events V2","description":"GET /api/v2/events\n\nAlias to /api/events for frontend compatibility.","operationId":"get_events_v2_api_v2_events_get","parameters":[{"name":"start_date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Start Date"}},{"name":"end_date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"End Date"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/invoices":{"get":{"tags":["Spec v2.9"],"summary":"Get Invoices V2","description":"GET /api/v2/invoices\n\nGlobal invoices endpoint for frontend compatibility.","operationId":"get_invoices_v2_api_v2_invoices_get","parameters":[{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}},{"name":"client_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Id"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/proposals":{"get":{"tags":["Spec v2.9"],"summary":"Get Proposals V2","description":"GET /api/v2/proposals","operationId":"get_proposals_v2_api_v2_proposals_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":20,"title":"Limit"}},{"name":"status","in":"query","required":false,"schema":{"type":"string","default":"open","title":"Status"}},{"name":"days","in":"query","required":false,"schema":{"type":"integer","default":7,"title":"Days"}},{"name":"client_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/watchers":{"get":{"tags":["Spec v2.9"],"summary":"Get Watchers V2","description":"GET /api/v2/watchers","operationId":"get_watchers_v2_api_v2_watchers_get","parameters":[{"name":"hours","in":"query","required":false,"schema":{"type":"integer","default":24,"title":"Hours"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/couplings":{"get":{"tags":["Spec v2.9"],"summary":"Get Couplings V2","description":"GET /api/v2/couplings","operationId":"get_couplings_v2_api_v2_couplings_get","parameters":[{"name":"anchor_type","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Anchor Type"}},{"name":"anchor_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Anchor Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/v2/fix-data":{"get":{"tags":["Spec v2.9"],"summary":"Get Fix Data V2","description":"GET /api/v2/fix-data","operationId":"get_fix_data_v2_api_v2_fix_data_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/v2/evidence/{entity_type}/{entity_id}":{"get":{"tags":["Spec v2.9"],"summary":"Get Evidence V2","description":"GET /api/v2/evidence/{entity_type}/{entity_id}","operationId":"get_evidence_v2_api_v2_evidence__entity_type___entity_id__get","parameters":[{"name":"entity_type","in":"path","required":true,"schema":{"type":"string","title":"Entity Type"}},{"name":"entity_id","in":"path","required":true,"schema":{"type":"string","title":"Entity Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/":{"get":{"summary":"Root","description":"Serve the dashboard UI.","operationId":"root__get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/overview":{"get":{"summary":"Get Overview","description":"Get dashboard overview with priorities, calendar, decisions, anomalies.","operationId":"get_overview_api_overview_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/time/blocks":{"get":{"summary":"Get Time Blocks","description":"Get time blocks for a given date.","operationId":"get_time_blocks_api_time_blocks_get","parameters":[{"name":"date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Date"}},{"name":"lane","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Lane"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/time/summary":{"get":{"summary":"Get Time Summary","description":"Get time summary for a date.","operationId":"get_time_summary_api_time_summary_get","parameters":[{"name":"date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Date"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/time/brief":{"get":{"summary":"Get Time Brief","description":"Get a brief time overview.","operationId":"get_time_brief_api_time_brief_get","parameters":[{"name":"date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Date"}},{"name":"format","in":"query","required":false,"schema":{"type":"string","default":"markdown","title":"Format"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/time/schedule":{"post":{"summary":"Schedule Task","description":"Schedule a task into a time block.","operationId":"schedule_task_api_time_schedule_post","parameters":[{"name":"task_id","in":"query","required":true,"schema":{"type":"string","title":"Task Id"}},{"name":"block_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Block Id"}},{"name":"date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Date"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/time/unschedule":{"post":{"summary":"Unschedule Task","description":"Unschedule a task from its time block.","operationId":"unschedule_task_api_time_unschedule_post","parameters":[{"name":"task_id","in":"query","required":true,"schema":{"type":"string","title":"Task Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/commitments":{"get":{"summary":"Get Commitments","description":"Get all commitments.","operationId":"get_commitments_api_commitments_get","parameters":[{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/commitments/untracked":{"get":{"summary":"Get Untracked Commitments","description":"Get commitments that aren't linked to tasks.","operationId":"get_untracked_commitments_api_commitments_untracked_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/commitments/due":{"get":{"summary":"Get Commitments Due","description":"Get commitments due by a date.","operationId":"get_commitments_due_api_commitments_due_get","parameters":[{"name":"date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Date"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/commitments/summary":{"get":{"summary":"Get Commitments Summary","description":"Get commitments summary statistics.","operationId":"get_commitments_summary_api_commitments_summary_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/commitments/{commitment_id}/link":{"post":{"summary":"Link Commitment","description":"Link a commitment to a task.","operationId":"link_commitment_api_commitments__commitment_id__link_post","parameters":[{"name":"commitment_id","in":"path","required":true,"schema":{"type":"string","title":"Commitment Id"}},{"name":"task_id","in":"query","required":true,"schema":{"type":"string","title":"Task Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/commitments/{commitment_id}/done":{"post":{"summary":"Mark Commitment Done","description":"Mark a commitment as done.","operationId":"mark_commitment_done_api_commitments__commitment_id__done_post","parameters":[{"name":"commitment_id","in":"path","required":true,"schema":{"type":"string","title":"Commitment Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/capacity/lanes":{"get":{"summary":"Get Capacity Lanes","description":"Get capacity lanes configuration.","operationId":"get_capacity_lanes_api_capacity_lanes_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/capacity/utilization":{"get":{"summary":"Get Capacity Utilization","description":"Get capacity utilization metrics.","operationId":"get_capacity_utilization_api_capacity_utilization_get","parameters":[{"name":"start_date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Start Date"}},{"name":"end_date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"End Date"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/capacity/forecast":{"get":{"summary":"Get Capacity Forecast","description":"Get capacity forecast for upcoming days.","operationId":"get_capacity_forecast_api_capacity_forecast_get","parameters":[{"name":"days","in":"query","required":false,"schema":{"type":"integer","default":7,"title":"Days"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/capacity/debt":{"get":{"summary":"Get Capacity Debt","description":"Get capacity debt (overcommitments).","operationId":"get_capacity_debt_api_capacity_debt_get","parameters":[{"name":"lane","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Lane"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/capacity/debt/accrue":{"post":{"summary":"Accrue Debt","description":"Record accrued capacity debt.","operationId":"accrue_debt_api_capacity_debt_accrue_post","parameters":[{"name":"hours","in":"query","required":false,"schema":{"anyOf":[{"type":"number"},{"type":"null"}],"title":"Hours"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/capacity/debt/{debt_id}/resolve":{"post":{"summary":"Resolve Debt","description":"Resolve a capacity debt item.","operationId":"resolve_debt_api_capacity_debt__debt_id__resolve_post","parameters":[{"name":"debt_id","in":"path","required":true,"schema":{"type":"string","title":"Debt Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients/health":{"get":{"summary":"Get Clients Health","description":"Get client health overview.","operationId":"get_clients_health_api_clients_health_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":20,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients/at-risk":{"get":{"summary":"Get At Risk Clients","description":"Get clients that are at risk (health score below threshold).","operationId":"get_at_risk_clients_api_clients_at_risk_get","parameters":[{"name":"threshold","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Threshold"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients/{client_id}/health":{"get":{"summary":"Get Client Health","description":"Get detailed health for a specific client.","operationId":"get_client_health_api_clients__client_id__health_get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients/{client_id}/projects":{"get":{"summary":"Get Client Projects","description":"Get projects for a client.","operationId":"get_client_projects_api_clients__client_id__projects_get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients/link":{"post":{"summary":"Link Project To Client","description":"Link a project to a client.","operationId":"link_project_to_client_api_clients_link_post","parameters":[{"name":"project_id","in":"query","required":true,"schema":{"type":"string","title":"Project Id"}},{"name":"client_id","in":"query","required":true,"schema":{"type":"string","title":"Client Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients/linking-stats":{"get":{"summary":"Get Linking Stats","description":"Get client linking statistics.","operationId":"get_linking_stats_api_clients_linking_stats_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/tasks":{"get":{"summary":"Get Tasks","description":"Get tasks with optional filters.","operationId":"get_tasks_api_tasks_get","parameters":[{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}},{"name":"project","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Project"}},{"name":"assignee","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assignee"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}},"post":{"summary":"Create Task","description":"Create a new task.","operationId":"create_task_api_tasks_post","requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/TaskCreate"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/tasks/{task_id}":{"get":{"summary":"Get Task","description":"Get a specific task.","operationId":"get_task_api_tasks__task_id__get","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}},"put":{"summary":"Update Task","description":"Update a task with comprehensive validation and tracking.","operationId":"update_task_api_tasks__task_id__put","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/TaskUpdate"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}},"delete":{"summary":"Delete Task","description":"Delete (archive) a task.","operationId":"delete_task_api_tasks__task_id__delete","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/tasks/{task_id}/notes":{"post":{"summary":"Add Task Note","description":"Add a note to a task.","operationId":"add_task_note_api_tasks__task_id__notes_post","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/NoteAdd"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/tasks/{task_id}/delegate":{"post":{"summary":"Delegate Task","description":"Delegate a task to someone with validation and workload awareness.","operationId":"delegate_task_api_tasks__task_id__delegate_post","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/DelegateRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/tasks/{task_id}/escalate":{"post":{"summary":"Escalate Task","description":"Escalate a task with priority boost and notification chain.","operationId":"escalate_task_api_tasks__task_id__escalate_post","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/EscalateRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/tasks/{task_id}/recall":{"post":{"summary":"Recall Task","description":"Recall a delegated task.","operationId":"recall_task_api_tasks__task_id__recall_post","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/delegations":{"get":{"summary":"Api Delegations","description":"Get delegated tasks (alias).","operationId":"api_delegations_api_delegations_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/data-quality":{"get":{"summary":"Get Data Quality","description":"Get data quality metrics and cleanup suggestions.","operationId":"get_data_quality_api_data_quality_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/data-quality/cleanup/ancient":{"post":{"summary":"Cleanup Ancient Tasks","description":"Archive tasks that are >30 days overdue.","operationId":"cleanup_ancient_tasks_api_data_quality_cleanup_ancient_post","parameters":[{"name":"confirm","in":"query","required":false,"schema":{"type":"boolean","default":false,"title":"Confirm"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/data-quality/cleanup/stale":{"post":{"summary":"Cleanup Stale Tasks","description":"Archive tasks that are 14-30 days overdue.","operationId":"cleanup_stale_tasks_api_data_quality_cleanup_stale_post","parameters":[{"name":"confirm","in":"query","required":false,"schema":{"type":"boolean","default":false,"title":"Confirm"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/data-quality/recalculate-priorities":{"post":{"summary":"Recalculate Priorities","description":"Recalculate priorities for all pending tasks.","operationId":"recalculate_priorities_api_data_quality_recalculate_priorities_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/data-quality/cleanup/legacy-signals":{"post":{"summary":"Cleanup Legacy Signals","description":"Clean up legacy signals and proposals by:\n1. Expiring signals for tasks overdue > LEGACY_OVERDUE_THRESHOLD_DAYS\n2. Recalculating proposals without legacy noise\n\nThis fixes the issue of 1000+ day old overdue tasks polluting the dashboard.","operationId":"cleanup_legacy_signals_api_data_quality_cleanup_legacy_signals_post","parameters":[{"name":"confirm","in":"query","required":false,"schema":{"type":"boolean","default":false,"title":"Confirm"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/data-quality/preview/{cleanup_type}":{"get":{"summary":"Preview Cleanup","description":"Preview what would be affected by a cleanup operation.","operationId":"preview_cleanup_api_data_quality_preview__cleanup_type__get","parameters":[{"name":"cleanup_type","in":"path","required":true,"schema":{"type":"string","title":"Cleanup Type"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/team":{"get":{"summary":"Get Team","description":"Get team members with workload metrics.","operationId":"get_team_api_team_get","parameters":[{"name":"type_filter","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Type Filter"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/calendar":{"get":{"summary":"Api Calendar","description":"Get calendar events.","operationId":"api_calendar_api_calendar_get","parameters":[{"name":"start_date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Start Date"}},{"name":"end_date","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"End Date"}},{"name":"view","in":"query","required":false,"schema":{"type":"string","default":"week","title":"View"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/inbox":{"get":{"summary":"Api Inbox","description":"Get inbox items (unprocessed communications, new tasks, etc.).","operationId":"api_inbox_api_inbox_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/insights":{"get":{"summary":"Get Insights","description":"Get insights.","operationId":"get_insights_api_insights_get","parameters":[{"name":"category","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Category"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/decisions":{"get":{"summary":"Api Decisions","description":"Get pending decisions.","operationId":"api_decisions_api_decisions_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":20,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/priorities/{item_id}/complete":{"post":{"summary":"Complete Item","description":"Complete a priority item based on its type/source.","operationId":"complete_item_api_priorities__item_id__complete_post","parameters":[{"name":"item_id","in":"path","required":true,"schema":{"type":"string","title":"Item Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/priorities/{item_id}/snooze":{"post":{"summary":"Snooze Item","description":"Snooze a priority item.","operationId":"snooze_item_api_priorities__item_id__snooze_post","parameters":[{"name":"item_id","in":"path","required":true,"schema":{"type":"string","title":"Item Id"}},{"name":"hours","in":"query","required":false,"schema":{"type":"integer","default":4,"title":"Hours"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/priorities/{item_id}/delegate":{"post":{"summary":"Delegate Item","description":"Delegate a priority item.","operationId":"delegate_item_api_priorities__item_id__delegate_post","parameters":[{"name":"item_id","in":"path","required":true,"schema":{"type":"string","title":"Item Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/DelegateAction"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/decisions/{decision_id}":{"post":{"summary":"Api Decision","description":"Process a decision (approve/reject) with side-effect execution.","operationId":"api_decision_api_decisions__decision_id__post","parameters":[{"name":"decision_id","in":"path","required":true,"schema":{"type":"string","title":"Decision Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ApprovalAction"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/bundles":{"get":{"summary":"Api Bundles","description":"Get change bundles.","operationId":"api_bundles_api_bundles_get","parameters":[{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}},{"name":"domain","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Domain"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/bundles/rollbackable":{"get":{"summary":"Api Bundles Rollbackable","description":"Get bundles that can be rolled back.","operationId":"api_bundles_rollbackable_api_bundles_rollbackable_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/bundles/summary":{"get":{"summary":"Get Bundles Summary","description":"Get summary of bundle activity.","operationId":"get_bundles_summary_api_bundles_summary_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/bundles/rollback-last":{"post":{"summary":"Rollback Last Bundle","description":"Rollback the most recent bundle.","operationId":"rollback_last_bundle_api_bundles_rollback_last_post","parameters":[{"name":"domain","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Domain"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/bundles/{bundle_id}":{"get":{"summary":"Api Bundle Get","description":"Get a specific bundle.","operationId":"api_bundle_get_api_bundles__bundle_id__get","parameters":[{"name":"bundle_id","in":"path","required":true,"schema":{"type":"string","title":"Bundle Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/bundles/{bundle_id}/rollback":{"post":{"summary":"Api Bundle Rollback","description":"Rollback a specific bundle.","operationId":"api_bundle_rollback_api_bundles__bundle_id__rollback_post","parameters":[{"name":"bundle_id","in":"path","required":true,"schema":{"type":"string","title":"Bundle Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/calibration":{"get":{"summary":"Api Calibration Last","description":"Get last calibration results.","operationId":"api_calibration_last_api_calibration_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/calibration/run":{"post":{"summary":"Api Calibration Run","description":"Run calibration.","operationId":"api_calibration_run_api_calibration_run_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/feedback":{"post":{"summary":"Api Feedback","description":"Submit feedback on a recommendation or action.","operationId":"api_feedback_api_feedback_post","requestBody":{"content":{"application/json":{"schema":{"$ref":"#/components/schemas/FeedbackRequest"}}},"required":true},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/priorities":{"get":{"summary":"Get Priorities","description":"Get prioritized items.","operationId":"get_priorities_api_priorities_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":20,"title":"Limit"}},{"name":"context","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Context"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/priorities/filtered":{"get":{"summary":"Get Priorities Filtered","description":"Get filtered priority items with reasons.","operationId":"get_priorities_filtered_api_priorities_filtered_get","parameters":[{"name":"due","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Due"}},{"name":"assignee","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assignee"}},{"name":"source","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Source"}},{"name":"project","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Project"}},{"name":"q","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Q"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/priorities/bulk":{"post":{"summary":"Bulk Action","description":"Perform bulk actions on priority items.","operationId":"bulk_action_api_priorities_bulk_post","requestBody":{"content":{"application/json":{"schema":{"$ref":"#/components/schemas/BulkAction"}}},"required":true},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/filters":{"get":{"summary":"Get Saved Filters","description":"Get saved filters.","operationId":"get_saved_filters_api_filters_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/priorities/advanced":{"get":{"summary":"Advanced Filter","description":"Advanced priority filtering with more options.","operationId":"advanced_filter_api_priorities_advanced_get","parameters":[{"name":"q","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Q"}},{"name":"due","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Due"}},{"name":"assignee","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assignee"}},{"name":"project","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Project"}},{"name":"status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"}},{"name":"min_score","in":"query","required":false,"schema":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Min Score"}},{"name":"max_score","in":"query","required":false,"schema":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Max Score"}},{"name":"tags","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Tags"}},{"name":"sort","in":"query","required":false,"schema":{"type":"string","default":"score","title":"Sort"}},{"name":"order","in":"query","required":false,"schema":{"type":"string","default":"desc","title":"Order"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}},{"name":"offset","in":"query","required":false,"schema":{"type":"integer","default":0,"title":"Offset"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/priorities/archive-stale":{"post":{"summary":"Archive Stale","description":"Archive stale priority items.","operationId":"archive_stale_api_priorities_archive_stale_post","parameters":[{"name":"days_threshold","in":"query","required":false,"schema":{"type":"integer","default":14,"title":"Days Threshold"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/events":{"get":{"summary":"Get Events","description":"Get upcoming events.","operationId":"get_events_api_events_get","parameters":[{"name":"hours","in":"query","required":false,"schema":{"type":"integer","default":24,"title":"Hours"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/day/{date}":{"get":{"summary":"Get Day Analysis","description":"Get analysis for a specific day.","operationId":"get_day_analysis_api_day__date__get","parameters":[{"name":"date","in":"path","required":true,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Date"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/week":{"get":{"summary":"Get Week Analysis","description":"Get analysis for the current week.","operationId":"get_week_analysis_api_week_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/emails":{"get":{"summary":"Get Email Queue","description":"Get email queue.","operationId":"get_email_queue_api_emails_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":20,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/emails/{email_id}/mark-actionable":{"post":{"summary":"Mark Email Actionable","description":"Mark an email as actionable.","operationId":"mark_email_actionable_api_emails__email_id__mark_actionable_post","parameters":[{"name":"email_id","in":"path","required":true,"schema":{"type":"string","title":"Email Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/anomalies":{"get":{"summary":"Get Anomalies","description":"Get anomalies.","operationId":"get_anomalies_api_anomalies_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/notifications":{"get":{"summary":"Get Notifications","description":"Get notifications.","operationId":"get_notifications_api_notifications_get","parameters":[{"name":"include_dismissed","in":"query","required":false,"schema":{"type":"boolean","default":false,"title":"Include Dismissed"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/notifications/stats":{"get":{"summary":"Get Notification Stats","description":"Get notification statistics.","operationId":"get_notification_stats_api_notifications_stats_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/notifications/{notif_id}/dismiss":{"post":{"summary":"Dismiss Notification","description":"Dismiss a notification.","operationId":"dismiss_notification_api_notifications__notif_id__dismiss_post","parameters":[{"name":"notif_id","in":"path","required":true,"schema":{"type":"string","title":"Notif Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/notifications/dismiss-all":{"post":{"summary":"Dismiss All Notifications","description":"Dismiss all notifications.","operationId":"dismiss_all_notifications_api_notifications_dismiss_all_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/approvals":{"get":{"summary":"Get Approvals","description":"Get pending approvals.","operationId":"get_approvals_api_approvals_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/approvals/{decision_id}":{"post":{"summary":"Process Approval","description":"Process an approval.","operationId":"process_approval_api_approvals__decision_id__post","parameters":[{"name":"decision_id","in":"path","required":true,"schema":{"type":"string","title":"Decision Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ApprovalAction"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/approvals/{decision_id}/modify":{"post":{"summary":"Modify Approval","description":"Modify and approve a decision.","operationId":"modify_approval_api_approvals__decision_id__modify_post","parameters":[{"name":"decision_id","in":"path","required":true,"schema":{"type":"string","title":"Decision Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ModifyApproval"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/governance":{"get":{"summary":"Get Governance Status","description":"Get governance configuration and status.","operationId":"get_governance_status_api_governance_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/governance/{domain}":{"put":{"summary":"Set Governance Mode","description":"Set governance mode for a domain.","operationId":"set_governance_mode_api_governance__domain__put","parameters":[{"name":"domain","in":"path","required":true,"schema":{"type":"string","title":"Domain"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ModeChange"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/governance/{domain}/threshold":{"put":{"summary":"Set Governance Threshold","description":"Set confidence threshold for a domain.","operationId":"set_governance_threshold_api_governance__domain__threshold_put","parameters":[{"name":"domain","in":"path","required":true,"schema":{"type":"string","title":"Domain"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ThresholdUpdate"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/governance/history":{"get":{"summary":"Get Governance History","description":"Get governance action history.","operationId":"get_governance_history_api_governance_history_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/governance/emergency-brake":{"post":{"summary":"Activate Emergency Brake","description":"Activate emergency brake.","operationId":"activate_emergency_brake_api_governance_emergency_brake_post","parameters":[{"name":"reason","in":"query","required":false,"schema":{"type":"string","default":"Manual activation","title":"Reason"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}},"delete":{"summary":"Release Emergency Brake","description":"Release emergency brake.","operationId":"release_emergency_brake_api_governance_emergency_brake_delete","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/sync/status":{"get":{"summary":"Get Sync Status","description":"Get sync status for all collectors.","operationId":"get_sync_status_api_sync_status_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/sync":{"post":{"summary":"Force Sync","description":"Force a sync operation.","operationId":"force_sync_api_sync_post","parameters":[{"name":"source","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Source"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/analyze":{"post":{"summary":"Run Analysis","description":"Run analysis.","operationId":"run_analysis_api_analyze_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/cycle":{"post":{"summary":"Run Cycle","description":"Run a full autonomous cycle.","operationId":"run_cycle_api_cycle_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/status":{"get":{"summary":"Get Status","description":"Get system status.","operationId":"get_status_api_status_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/health":{"get":{"summary":"Health Check","description":"Health check endpoint.","operationId":"health_check_api_health_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/debug/db":{"get":{"summary":"Debug Db","description":"Debug endpoint to inspect database configuration.\n\nReturns resolved DB path, file info, schema version, and column lists\nfor key tables (tasks, communications).","operationId":"debug_db_api_debug_db_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/summary":{"get":{"summary":"Get Summary","description":"Get a comprehensive summary.","operationId":"get_summary_api_summary_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/search":{"get":{"summary":"Search Items","description":"Search across tasks, projects, and clients.","operationId":"search_items_api_search_get","parameters":[{"name":"q","in":"query","required":true,"schema":{"type":"string","title":"Q"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":20,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/team/workload":{"get":{"summary":"Get Team Workload","description":"Get team workload distribution.","operationId":"get_team_workload_api_team_workload_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/priorities/grouped":{"get":{"summary":"Get Grouped Priorities","description":"Get priorities grouped by a field.","operationId":"get_grouped_priorities_api_priorities_grouped_get","parameters":[{"name":"group_by","in":"query","required":false,"schema":{"type":"string","default":"project","title":"Group By"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":10,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients":{"get":{"summary":"Get Clients","description":"Get clients with filters.","operationId":"get_clients_api_clients_get","parameters":[{"name":"tier","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Tier"}},{"name":"health","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Health"}},{"name":"ar_status","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Ar Status"}},{"name":"active_only","in":"query","required":false,"schema":{"type":"boolean","default":true,"title":"Active Only"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":100,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/clients/portfolio":{"get":{"summary":"Get Client Portfolio","description":"Get client portfolio overview.","operationId":"get_client_portfolio_api_clients_portfolio_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/clients/{client_id}":{"get":{"summary":"Get Client Detail","description":"Get detailed client information.","operationId":"get_client_detail_api_clients__client_id__get","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}},"put":{"summary":"Update Client","description":"Update client information.","operationId":"update_client_api_clients__client_id__put","parameters":[{"name":"client_id","in":"path","required":true,"schema":{"type":"string","title":"Client Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ClientUpdate"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/projects":{"get":{"summary":"Get Projects","description":"Get projects with filters.","operationId":"get_projects_api_projects_get","parameters":[{"name":"client_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Id"}},{"name":"include_archived","in":"query","required":false,"schema":{"type":"boolean","default":false,"title":"Include Archived"}},{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":50,"title":"Limit"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/projects/candidates":{"get":{"summary":"Get Project Candidates","description":"Get projects that could be enrolled (candidates and proposed).","operationId":"get_project_candidates_api_projects_candidates_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/projects/enrolled":{"get":{"summary":"Get Enrolled Projects","description":"Get enrolled projects with client info and task counts.","operationId":"get_enrolled_projects_api_projects_enrolled_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/projects/{project_id}/enrollment":{"post":{"summary":"Process Enrollment","description":"Process project enrollment action.","operationId":"process_enrollment_api_projects__project_id__enrollment_post","parameters":[{"name":"project_id","in":"path","required":true,"schema":{"type":"string","title":"Project Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/EnrollmentAction"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/projects/detect":{"get":{"summary":"Detect New Projects","description":"Detect new projects from tasks.","operationId":"detect_new_projects_api_projects_detect_get","parameters":[{"name":"force","in":"query","required":false,"schema":{"type":"boolean","default":false,"title":"Force"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/projects/{project_id}":{"get":{"summary":"Get Project Detail","description":"Get detailed project information.","operationId":"get_project_detail_api_projects__project_id__get","parameters":[{"name":"project_id","in":"path","required":true,"schema":{"type":"string","title":"Project Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/sync/xero":{"post":{"summary":"Sync Xero","description":"Sync with Xero.","operationId":"sync_xero_api_sync_xero_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/tasks/link":{"post":{"summary":"Bulk Link Tasks","description":"Bulk link tasks to projects/clients.","operationId":"bulk_link_tasks_api_tasks_link_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/projects/propose":{"post":{"summary":"Propose Project","description":"Propose a new project.","operationId":"propose_project_api_projects_propose_post","parameters":[{"name":"name","in":"query","required":true,"schema":{"type":"string","title":"Name"}},{"name":"client_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Id"}},{"name":"type","in":"query","required":false,"schema":{"type":"string","default":"retainer","title":"Type"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/emails/{email_id}/dismiss":{"post":{"summary":"Dismiss Email","description":"Dismiss an email.","operationId":"dismiss_email_api_emails__email_id__dismiss_post","parameters":[{"name":"email_id","in":"path","required":true,"schema":{"type":"string","title":"Email Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/digest/weekly":{"get":{"summary":"Get Weekly Digest","description":"Get weekly digest.","operationId":"get_weekly_digest_api_digest_weekly_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/tasks/{task_id}/block":{"post":{"summary":"Add Blocker","description":"Add a blocker to a task.","operationId":"add_blocker_api_tasks__task_id__block_post","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/BlockerRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/tasks/{task_id}/block/{blocker_id}":{"delete":{"summary":"Remove Blocker","description":"Remove a blocker from a task.","operationId":"remove_blocker_api_tasks__task_id__block__blocker_id__delete","parameters":[{"name":"task_id","in":"path","required":true,"schema":{"type":"string","title":"Task Id"}},{"name":"blocker_id","in":"path","required":true,"schema":{"type":"string","title":"Blocker Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/dependencies":{"get":{"summary":"Get Dependencies","description":"Get task dependency graph.","operationId":"get_dependencies_api_dependencies_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/control-room/proposals":{"get":{"summary":"Get Proposals","description":"Get proposals with full hierarchy context.\n\nArgs:\n    limit: Max proposals to return\n    status: Filter by status (open, snoozed, dismissed, accepted)\n    days: Filter to signals within last N days (1=today, 7=week, 30=month)\n    client_id: Filter to signals for a specific client (optional)\n    member_id: Filter to signals for tasks assigned to this team member (optional)\n\nReturns:\n    items: List of proposals with:\n        - scope_level, scope_name (project/client level)\n        - client_name, client_tier\n        - score, score_breakdown\n        - signal_summary (counts by category)\n        - worst_signal (text description)\n        - signal_count, remaining_count","operationId":"get_proposals_api_control_room_proposals_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":7,"title":"Limit"}},{"name":"status","in":"query","required":false,"schema":{"type":"string","default":"open","title":"Status"}},{"name":"days","in":"query","required":false,"schema":{"type":"integer","default":7,"title":"Days"}},{"name":"client_id","in":"query","required":false,"schema":{"type":"string","title":"Client Id"}},{"name":"member_id","in":"query","required":false,"schema":{"type":"string","title":"Member Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/issues":{"get":{"summary":"Get Issues","description":"Get issues from real data in moh_time_os.db.\n\nArgs:\n    limit: Max issues to return\n    days: Filter to issues active within last N days\n    client_id: Filter to issues for a specific client (optional)\n    member_id: Filter to issues for tasks assigned to this team member (optional)","operationId":"get_issues_api_control_room_issues_get","parameters":[{"name":"limit","in":"query","required":false,"schema":{"type":"integer","default":5,"title":"Limit"}},{"name":"days","in":"query","required":false,"schema":{"type":"integer","default":7,"title":"Days"}},{"name":"client_id","in":"query","required":false,"schema":{"type":"string","title":"Client Id"}},{"name":"member_id","in":"query","required":false,"schema":{"type":"string","title":"Member Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}},"post":{"summary":"Create Issue From Proposal","description":"Tag a proposal to create a monitored Issue.","operationId":"create_issue_from_proposal_api_control_room_issues_post","requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/TagProposalRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/issues/{issue_id}/resolve":{"patch":{"summary":"Resolve Issue","description":"Resolve an issue.","operationId":"resolve_issue_api_control_room_issues__issue_id__resolve_patch","parameters":[{"name":"issue_id","in":"path","required":true,"schema":{"type":"string","title":"Issue Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ResolveIssueRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/issues/{issue_id}/state":{"patch":{"summary":"Change Issue State","description":"Change an issue's state.","operationId":"change_issue_state_api_control_room_issues__issue_id__state_patch","parameters":[{"name":"issue_id","in":"path","required":true,"schema":{"type":"string","title":"Issue Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ChangeIssueStateRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/issues/{issue_id}/notes":{"post":{"summary":"Add Issue Note","description":"Add a note to an issue.","operationId":"add_issue_note_api_control_room_issues__issue_id__notes_post","parameters":[{"name":"issue_id","in":"path","required":true,"schema":{"type":"string","title":"Issue Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/AddIssueNoteRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/watchers":{"get":{"summary":"Get Watchers","description":"Get issue watchers/alerts that have been triggered recently.","operationId":"get_watchers_api_control_room_watchers_get","parameters":[{"name":"hours","in":"query","required":false,"schema":{"type":"integer","default":24,"title":"Hours"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/watchers/{watcher_id}/dismiss":{"post":{"summary":"Dismiss Watcher","description":"Dismiss a watcher (remove from active list).","operationId":"dismiss_watcher_api_control_room_watchers__watcher_id__dismiss_post","parameters":[{"name":"watcher_id","in":"path","required":true,"schema":{"type":"string","title":"Watcher Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/DismissWatcherRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/watchers/{watcher_id}/snooze":{"post":{"summary":"Snooze Watcher","description":"Snooze a watcher for N hours.","operationId":"snooze_watcher_api_control_room_watchers__watcher_id__snooze_post","parameters":[{"name":"watcher_id","in":"path","required":true,"schema":{"type":"string","title":"Watcher Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/SnoozeWatcherRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/fix-data":{"get":{"summary":"Get Fix Data","description":"Get data quality issues for Fix tab.","operationId":"get_fix_data_api_control_room_fix_data_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/control-room/proposals/{proposal_id}":{"get":{"summary":"Get Proposal Detail","description":"Get detailed view of a proposal with full signal information.\n\nReturns:\n    - Full proposal metadata\n    - Score breakdown\n    - Top 5 signals with task details\n    - Link to issues page for \"see more\"","operationId":"get_proposal_detail_api_control_room_proposals__proposal_id__get","parameters":[{"name":"proposal_id","in":"path","required":true,"schema":{"type":"string","title":"Proposal Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/proposals/{proposal_id}/snooze":{"post":{"summary":"Snooze Proposal","description":"Snooze a proposal for N days.","operationId":"snooze_proposal_api_control_room_proposals__proposal_id__snooze_post","parameters":[{"name":"proposal_id","in":"path","required":true,"schema":{"type":"string","title":"Proposal Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/SnoozeProposalRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/proposals/{proposal_id}/dismiss":{"post":{"summary":"Dismiss Proposal","description":"Dismiss a proposal.","operationId":"dismiss_proposal_api_control_room_proposals__proposal_id__dismiss_post","parameters":[{"name":"proposal_id","in":"path","required":true,"schema":{"type":"string","title":"Proposal Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/DismissProposalRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/fix-data/{item_type}/{item_id}/resolve":{"post":{"summary":"Resolve Fix Data Item","description":"Resolve a fix-data item (identity conflict or ambiguous link).","operationId":"resolve_fix_data_item_api_control_room_fix_data__item_type___item_id__resolve_post","parameters":[{"name":"item_type","in":"path","required":true,"schema":{"type":"string","title":"Item Type"}},{"name":"item_id","in":"path","required":true,"schema":{"type":"string","title":"Item Id"}}],"requestBody":{"required":true,"content":{"application/json":{"schema":{"$ref":"#/components/schemas/ResolveFixDataRequest"}}}},"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/couplings":{"get":{"summary":"Get Couplings","description":"Get intersections/couplings.","operationId":"get_couplings_api_control_room_couplings_get","parameters":[{"name":"anchor_type","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Anchor Type"}},{"name":"anchor_id","in":"query","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Anchor Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/clients":{"get":{"summary":"Get Control Room Clients","description":"Get clients for control room.","operationId":"get_control_room_clients_api_control_room_clients_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/control-room/team":{"get":{"summary":"Get Control Room Team","description":"Get team members for control room.","operationId":"get_control_room_team_api_control_room_team_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/control-room/evidence/{entity_type}/{entity_id}":{"get":{"summary":"Get Evidence","description":"Get evidence/proof for an entity.","operationId":"get_evidence_api_control_room_evidence__entity_type___entity_id__get","parameters":[{"name":"entity_type","in":"path","required":true,"schema":{"type":"string","title":"Entity Type"}},{"name":"entity_id","in":"path","required":true,"schema":{"type":"string","title":"Entity Id"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}},"/api/control-room/health":{"get":{"summary":"Control Room Health","description":"Health check endpoint for the Control Room API.","operationId":"control_room_health_api_control_room_health_get","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/api/admin/seed-identities":{"post":{"summary":"Seed Identities","description":"Seed identity profiles from clients and people tables.","operationId":"seed_identities_api_admin_seed_identities_post","responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}}}}},"/{path}":{"get":{"summary":"Spa Fallback","description":"Serve static files or fall back to SPA index.html.","operationId":"spa_fallback__path__get","parameters":[{"name":"path","in":"path","required":true,"schema":{"type":"string","title":"Path"}}],"responses":{"200":{"description":"Successful Response","content":{"application/json":{"schema":{}}}},"422":{"description":"Validation Error","content":{"application/json":{"schema":{"$ref":"#/components/schemas/HTTPValidationError"}}}}}}}},"components":{"schemas":{"AddIssueNoteRequest":{"properties":{"text":{"type":"string","title":"Text"},"actor":{"type":"string","title":"Actor","default":"moh"}},"type":"object","required":["text"],"title":"AddIssueNoteRequest"},"ApprovalAction":{"properties":{"action":{"type":"string","title":"Action"}},"type":"object","required":["action"],"title":"ApprovalAction"},"BlockerRequest":{"properties":{"blocker_id":{"type":"string","title":"Blocker Id"}},"type":"object","required":["blocker_id"],"title":"BlockerRequest"},"BulkAction":{"properties":{"action":{"type":"string","title":"Action"},"ids":{"items":{"type":"string"},"type":"array","title":"Ids"},"assignee":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assignee"},"snooze_days":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Snooze Days"},"snooze_until":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Snooze Until"},"priority":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Priority"},"project":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Project"}},"type":"object","required":["action","ids"],"title":"BulkAction"},"ChangeIssueStateRequest":{"properties":{"state":{"type":"string","title":"State"},"reason":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Reason"},"actor":{"type":"string","title":"Actor","default":"moh"}},"type":"object","required":["state"],"title":"ChangeIssueStateRequest"},"ClientUpdate":{"properties":{"tier":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Tier"},"health":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Health"},"trend":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Trend"},"notes":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Notes"},"annual_value":{"anyOf":[{"type":"number"},{"type":"null"}],"title":"Annual Value"},"contact_name":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Contact Name"},"contact_email":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Contact Email"}},"type":"object","title":"ClientUpdate"},"DelegateAction":{"properties":{"to":{"type":"string","title":"To"},"note":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Note"}},"type":"object","required":["to"],"title":"DelegateAction"},"DelegateRequest":{"properties":{"to":{"type":"string","title":"To"},"note":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Note"},"due_date":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Due Date"}},"type":"object","required":["to"],"title":"DelegateRequest"},"DismissProposalRequest":{"properties":{"reason":{"type":"string","title":"Reason","default":"Dismissed by user"}},"type":"object","title":"DismissProposalRequest"},"DismissWatcherRequest":{"properties":{"actor":{"type":"string","title":"Actor","default":"moh"}},"type":"object","title":"DismissWatcherRequest"},"EngagementTransitionRequest":{"properties":{"action":{"type":"string","title":"Action"},"note":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Note"}},"type":"object","required":["action"],"title":"EngagementTransitionRequest"},"EnrollmentAction":{"properties":{"action":{"type":"string","title":"Action"},"reason":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Reason"},"client_id":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Client Id"},"involvement_type":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Involvement Type"},"snooze_days":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Snooze Days"}},"type":"object","required":["action"],"title":"EnrollmentAction"},"EscalateRequest":{"properties":{"to":{"type":"string","title":"To"},"reason":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Reason"}},"type":"object","required":["to"],"title":"EscalateRequest"},"FeedbackRequest":{"properties":{"item_id":{"type":"string","title":"Item Id"},"rating":{"type":"integer","title":"Rating"},"comment":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Comment"}},"type":"object","required":["item_id","rating"],"title":"FeedbackRequest"},"HTTPValidationError":{"properties":{"detail":{"items":{"$ref":"#/components/schemas/ValidationError"},"type":"array","title":"Detail"}},"type":"object","title":"HTTPValidationError"},"InboxActionRequest":{"properties":{"action":{"type":"string","title":"Action"},"assign_to":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assign To"},"snooze_days":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Snooze Days"},"link_engagement_id":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Link Engagement Id"},"select_candidate_id":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Select Candidate Id"},"note":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Note"}},"type":"object","required":["action"],"title":"InboxActionRequest"},"IssueTransitionRequest":{"properties":{"action":{"type":"string","title":"Action"},"assigned_to":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assigned To"},"snooze_days":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Snooze Days"},"note":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Note"}},"type":"object","required":["action"],"title":"IssueTransitionRequest"},"ModeChange":{"properties":{"mode":{"type":"string","title":"Mode"}},"type":"object","required":["mode"],"title":"ModeChange"},"ModifyApproval":{"properties":{"modifications":{"additionalProperties":true,"type":"object","title":"Modifications"}},"type":"object","required":["modifications"],"title":"ModifyApproval"},"NoteAdd":{"properties":{"note":{"type":"string","title":"Note"}},"type":"object","required":["note"],"title":"NoteAdd"},"ResolveFixDataRequest":{"properties":{"resolution":{"type":"string","title":"Resolution","default":"manually_resolved"},"actor":{"type":"string","title":"Actor","default":"moh"}},"type":"object","title":"ResolveFixDataRequest"},"ResolveIssueRequest":{"properties":{"resolution":{"type":"string","title":"Resolution","default":"manually_resolved"},"actor":{"type":"string","title":"Actor","default":"moh"}},"type":"object","title":"ResolveIssueRequest"},"SnoozeProposalRequest":{"properties":{"days":{"type":"integer","title":"Days","default":7}},"type":"object","title":"SnoozeProposalRequest"},"SnoozeWatcherRequest":{"properties":{"hours":{"type":"integer","title":"Hours","default":24},"actor":{"type":"string","title":"Actor","default":"moh"}},"type":"object","title":"SnoozeWatcherRequest"},"TagProposalRequest":{"properties":{"proposal_id":{"type":"string","title":"Proposal Id"},"actor":{"type":"string","title":"Actor","default":"moh"}},"type":"object","required":["proposal_id"],"title":"TagProposalRequest"},"TaskCreate":{"properties":{"title":{"type":"string","title":"Title"},"description":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Description"},"project":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Project"},"assignee":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assignee"},"due_date":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Due Date"},"priority":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Priority","default":50},"tags":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Tags"},"source":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Source","default":"api"},"status":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status","default":"pending"}},"type":"object","required":["title"],"title":"TaskCreate"},"TaskUpdate":{"properties":{"title":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Title"},"description":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Description"},"project":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Project"},"assignee":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Assignee"},"due_date":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Due Date"},"priority":{"anyOf":[{"type":"integer"},{"type":"null"}],"title":"Priority"},"status":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Status"},"tags":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"Tags"}},"type":"object","title":"TaskUpdate"},"ThresholdUpdate":{"properties":{"threshold":{"type":"number","title":"Threshold"}},"type":"object","required":["threshold"],"title":"ThresholdUpdate"},"ValidationError":{"properties":{"loc":{"items":{"anyOf":[{"type":"string"},{"type":"integer"}]},"type":"array","title":"Location"},"msg":{"type":"string","title":"Message"},"type":{"type":"string","title":"Error Type"},"input":{"title":"Input"},"ctx":{"type":"object","title":"Context"}},"type":"object","required":["loc","msg","type"],"title":"ValidationError"}}}}  104965
(.venv) molhamhomsi@Molhams-MacBook-Pro-645 moh_time_os % find . -maxdepth 3 -type f -name "*.db" -o -name "*.sqlite" -o -name "*.sql" -o -name "*migration*" -o -name "alembic.ini" -o -name "env.py" 2>/dev/null | sed 's|^\./||'
find lib -maxdepth 3 -type f -name "*db*" -o -name "*schema*" -o -name "*migration*" 2>/dev/null | head -n 200
state.db
docs/ui_atlas/03_SCHEMA_ATLAS.sql
time_os.db
lib/migrations
lib/migrations/spec_schema_migration.py
lib/safety/migrations.py
lib/v5/migrations
lib/ui_spec_v21/migrations
data/state.db
data/gmail_collector_state.db
data/agency_v4.db
data/moh_time_os.db
data/time_os.db
data/time_os_v5.db
data/test.db
data/backups/moh_time_os_20260131_034759_final-build.db
data/backups/moh_time_os_20260203_030051.db
data/backups/moh_time_os_20260206_222135.db
data/backups/moh_time_os_20260201_030006.db
data/backups/moh_time_os_20260131_032114_day2-complete.db
data/backups/moh_time_os_20260131_045750_pre_sync.db
data/backups/moh_time_os_20260131_045836_pre_sync.db
data/backups/moh_time_os_20260131_045645_pre_sync.db
data/backups/moh_time_os_20260131_045650_pre_sync.db
data/backups/moh_time_os_20260131_034602_pre-cleanup.db
data/backups/moh_time_os_20260204_221923.db
data/backups/moh_time_os_20260203_221909.db
data/backups/state_20260202_223816_pre_spec_migration.db
data/backups/moh_time_os_20260205_221927.db
lib/migrations
lib/migrations/v29_inbox_schema.py
lib/migrations/v29_full_schema.py
lib/migrations/spec_schema_migration.py
lib/migrations/rebuild_schema_v12.py
lib/db.py
lib/db_writer.py
lib/notifier/channels/clawdbot.py
lib/contracts/__pycache__/schema.cpython-314.pyc
lib/contracts/schema.py
lib/__pycache__/db.cpython-314.pyc
lib/safety/__pycache__/schema.cpython-312.pyc
lib/safety/__pycache__/schema.cpython-314.pyc
lib/safety/__pycache__/migrations.cpython-314.pyc
lib/safety/__pycache__/migrations.cpython-312.pyc
lib/safety/migrations.py
lib/safety/schema.py
lib/integrations/clawdbot_api.py
lib/v5/migrations
lib/v5/migrations/001_create_v5_schema.sql
lib/v5/migrations/run_migrations.py
lib/ui_spec_v21/migrations
(.venv) molhamhomsi@Molhams-MacBook-Pro-645 moh_time_os % ls -la data 2>/dev/null
sqlite3 data/moh_time_os.db 'PRAGMA user_version; .tables' 2>/dev/null
sqlite3 data/moh_time_os.db 'SELECT name, sql FROM sqlite_master WHERE type="table" ORDER BY name LIMIT 15;' 2>/dev/null
total 372320
drwxr-xr-x  26 molhamhomsi  staff        832 Feb 11 01:38 .
drwxr-xr-x  70 molhamhomsi  staff       2240 Feb 11 01:14 ..
-rw-r--r--@  1 molhamhomsi  staff       6148 Feb  8 15:20 .DS_Store
-rw-r--r--   1 molhamhomsi  staff          0 Feb  9 23:42 agency_v4.db
drwxr-xr-x  27 molhamhomsi  staff        864 Feb 10 10:27 backups
drwxr-xr-x  14 molhamhomsi  staff        448 Feb  6 19:49 bundles
drwxr-xr-x   5 molhamhomsi  staff        160 Feb 10 22:05 cache
-rw-r--r--   1 molhamhomsi  staff       9234 Feb  1 08:33 config.json
-rw-r--r--   1 molhamhomsi  staff        144 Feb  1 08:33 config_history.json
-rw-r--r--   1 molhamhomsi  staff        981 Feb  1 08:48 conflicts.json
-rw-r--r--   1 molhamhomsi  staff      70022 Feb 10 22:05 daemon.log
-rw-r--r--   1 molhamhomsi  staff        769 Feb 10 22:05 daemon_state.json
-rw-r--r--   1 molhamhomsi  staff       2761 Feb  1 08:48 delegation_graph.json
-rw-r--r--   1 molhamhomsi  staff        864 Feb  1 08:43 delegation_packets.json
-rw-r--r--   1 molhamhomsi  staff     405504 Feb  8 15:15 gmail_collector_state.db
-rw-r--r--   1 molhamhomsi  staff        427 Feb  1 08:48 governance.json
-rw-r--r--   1 molhamhomsi  staff        188 Feb  1 08:48 mode_history.json
-rw-r--r--   1 molhamhomsi  staff  187609088 Feb 11 01:38 moh_time_os.db
-rw-r--r--   1 molhamhomsi  staff        819 Feb  1 08:36 projects.json
-rw-r--r--   1 molhamhomsi  staff     229376 Feb 10 23:40 state.db
-rw-r--r--   1 molhamhomsi  staff        336 Feb 10 22:05 state.json
-rw-r--r--   1 molhamhomsi  staff          0 Feb 10 22:38 test.db
-rw-r--r--   1 molhamhomsi  staff          0 Feb  9 12:06 time_os.db
-rw-r--r--   1 molhamhomsi  staff    1245184 Feb  9 18:00 time_os_v5.db
-rw-r--r--   1 molhamhomsi  staff      32768 Feb 10 01:07 time_os_v5.db-shm
-rw-r--r--   1 molhamhomsi  staff          0 Feb 10 01:07 time_os_v5.db-wal
9
_health_check|CREATE TABLE _health_check (
                    id INTEGER PRIMARY KEY,
                    checked_at TEXT
                )
_schema_version|CREATE TABLE _schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
)
access_roles|CREATE TABLE access_roles (
    role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    permissions TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
actions|CREATE TABLE actions (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    target_system TEXT,
                    payload TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    requires_approval INTEGER DEFAULT 1,
                    approved_by TEXT,
                    approved_at TEXT,
                    executed_at TEXT,
                    result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
artifact_blobs|CREATE TABLE artifact_blobs (
    blob_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,  -- JSON or base64 encoded
    mime_type TEXT DEFAULT 'application/json',
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    retention_class TEXT NOT NULL DEFAULT 'standard'  -- standard, extended, legal_hold
)
artifact_excerpts|CREATE TABLE artifact_excerpts (
    excerpt_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    anchor_type TEXT NOT NULL,  -- byte_span, line_span, json_path, message_quote
    anchor_start TEXT NOT NULL,  -- could be int or path depending on type
    anchor_end TEXT NOT NULL,
    excerpt_text TEXT NOT NULL,  -- cached excerpt content
    excerpt_hash TEXT NOT NULL,  -- for integrity
    redaction_status TEXT DEFAULT 'none',  -- none, pending, redacted
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
artifacts|CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,  -- gmail, gchat, calendar, asana, docs, sheets, drive, minutes_gemini, billing, xero
    source_id TEXT NOT NULL,  -- stable upstream identifier
    type TEXT NOT NULL,  -- message, thread, calendar_event, meeting, minutes, task, task_update, doc_update, invoice, payment
    occurred_at TEXT NOT NULL,
    actor_person_id TEXT,  -- nullable, references identity_profiles
    payload_ref TEXT NOT NULL,  -- pointer to blob_id or inline
    content_hash TEXT NOT NULL,  -- dedupe + integrity
    visibility_tags TEXT DEFAULT '[]',  -- JSON array for ACL/routing
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(source, source_id)
)
asana_project_map|CREATE TABLE asana_project_map (
                asana_gid TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asana_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
brands|CREATE TABLE brands (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_id TEXT REFERENCES clients(id),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
)
canonical_projects|CREATE TABLE canonical_projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  involvement_type TEXT,
  recognizers_json TEXT,
  rules_bundle_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
)
canonical_tasks|CREATE TABLE canonical_tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  lane TEXT,
  project_id TEXT,
  status TEXT NOT NULL,
  urgency TEXT,
  impact TEXT,
  deadline_kind TEXT, -- hard|soft
  deadline_date TEXT, -- YYYY-MM-DD
  effort_min_minutes INTEGER,
  effort_max_minutes INTEGER,
  waiting_for TEXT,
  deps_json TEXT,
  sensitivity_json TEXT,
  recommended_next_action TEXT,
  dedupe_key TEXT NOT NULL UNIQUE,
  conflicts_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
)
capacity_lanes|CREATE TABLE capacity_lanes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_name TEXT,
                    owner TEXT,
                    weekly_hours INTEGER DEFAULT 40,
                    buffer_pct REAL DEFAULT 0.2,
                    color TEXT DEFAULT '#6366f1',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
change_bundles|CREATE TABLE change_bundles (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  mode TEXT NOT NULL, -- propose|execute
  manifest_json TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  applied_at_ms INTEGER,
  rolled_back_at_ms INTEGER
)
client_health_log|CREATE TABLE client_health_log (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    health_score INTEGER,
                    factors TEXT,
                    computed_at TEXT NOT NULL,
                    FOREIGN KEY (client_id) REFERENCES clients(id)
                )
client_projects|CREATE TABLE client_projects (
                    client_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY (client_id, project_id),
                    FOREIGN KEY (client_id) REFERENCES clients(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
(.venv) molhamhomsi@Molhams-MacBook-Pro-645 moh_time_os % ls -la time-os-ui 2>/dev/null
cat time-os-ui/package.json 2>/dev/null
ls -la time-os-ui/src 2>/dev/null
find time-os-ui/src -maxdepth 2 -type f -name "*api*" -o -name "*client*" -o -name "*router*" -o -name "*.ts" -o -name "*.tsx" 2>/dev/null | head -n 120
total 480
drwxr-xr-x  19 molhamhomsi  staff     608 Feb 10 23:43 .
drwxr-xr-x  70 molhamhomsi  staff    2240 Feb 11 01:14 ..
-rw-r--r--@  1 molhamhomsi  staff    6148 Feb  6 10:12 .DS_Store
-rw-r--r--   1 molhamhomsi  staff     300 Feb 10 23:43 .env.example
-rw-r--r--   1 molhamhomsi  staff     253 Feb  5 18:24 .gitignore
-rw-r--r--   1 molhamhomsi  staff    5156 Feb 10 23:43 ARCHITECTURE.md
-rw-r--r--   1 molhamhomsi  staff    2762 Feb 10 23:43 DEPLOY.md
drwxr-xr-x   9 molhamhomsi  staff     288 Feb 10 16:41 dist
-rw-r--r--   1 molhamhomsi  staff     658 Feb  5 18:26 index.html
drwxr-xr-x  24 molhamhomsi  staff     768 Feb  9 21:03 node_modules
-rw-r--r--   1 molhamhomsi  staff    1075 Feb 10 23:43 package.json
-rw-r--r--   1 molhamhomsi  staff  185641 Feb 10 23:43 pnpm-lock.yaml
-rw-r--r--   1 molhamhomsi  staff      35 Feb  5 18:24 pnpm-workspace.yaml
-rw-r--r--   1 molhamhomsi  staff      69 Feb  5 18:25 postcss.config.js
drwxr-xr-x   7 molhamhomsi  staff     224 Feb 10 23:43 public
drwxr-xr-x  11 molhamhomsi  staff     352 Feb 10 23:43 src
-rw-r--r--   1 molhamhomsi  staff     602 Feb 10 23:43 tsconfig.json
-rw-r--r--   1 molhamhomsi  staff     556 Feb 10 23:43 vite.config.ts
-rw-r--r--   1 molhamhomsi  staff     185 Feb 10 23:43 vitest.config.ts
{
  "name": "time-os-ui",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "build:check": "tsc && vite build",
    "typecheck": "tsc --noEmit",
    "lint": "echo 'No linter configured'",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "ci": "npm run typecheck && npm test && npm run build"
  },
  "engines": {
    "node": ">=18.0.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.1.18",
    "@testing-library/jest-dom": "^6.9.1",
    "@testing-library/react": "^16.3.2",
    "@types/react": "^19.2.13",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^5.1.3",
    "autoprefixer": "^10.4.24",
    "jsdom": "^28.0.0",
    "postcss": "^8.5.6",
    "tailwindcss": "^4.1.18",
    "typescript": "~5.9.3",
    "vite": "^7.2.4",
    "vite-plugin-pwa": "^1.2.0",
    "vitest": "^4.0.18"
  },
  "dependencies": {
    "@tanstack/react-router": "^1.158.1",
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "zustand": "^5.0.11"
  }
}
total 32
drwxr-xr-x  11 molhamhomsi  staff   352 Feb 10 23:43 .
drwxr-xr-x  19 molhamhomsi  staff   608 Feb 10 23:43 ..
drwxr-xr-x   8 molhamhomsi  staff   256 Feb 10 23:43 __tests__
drwxr-xr-x  17 molhamhomsi  staff   544 Feb 10 23:43 components
drwxr-xr-x   3 molhamhomsi  staff    96 Feb 10 23:43 constants
-rw-r--r--   1 molhamhomsi  staff   653 Feb  5 18:25 index.css
drwxr-xr-x  12 molhamhomsi  staff   384 Feb 10 23:43 lib
-rw-r--r--   1 molhamhomsi  staff   767 Feb 10 23:43 main.tsx
drwxr-xr-x  15 molhamhomsi  staff   480 Feb 10 23:43 pages
-rw-r--r--   1 molhamhomsi  staff  4341 Feb 10 23:43 router.tsx
drwxr-xr-x   4 molhamhomsi  staff   128 Feb 10 23:43 types
time-os-ui/src/main.tsx
time-os-ui/src/types/api.ts
time-os-ui/src/types/spec.ts
time-os-ui/src/constants/labels.ts
time-os-ui/src/components/IssueCard.tsx
time-os-ui/src/components/EvidenceViewer.tsx
time-os-ui/src/components/PostureStrip.tsx
time-os-ui/src/components/ProposalCard.tsx
time-os-ui/src/components/RoomDrawer.tsx
time-os-ui/src/components/ErrorState.tsx
time-os-ui/src/components/SuspenseWrapper.tsx
time-os-ui/src/components/IssueDrawer.tsx
time-os-ui/src/components/ConfidenceBadge.tsx
time-os-ui/src/components/index.ts
time-os-ui/src/components/Toast.tsx
time-os-ui/src/components/EmptyState.tsx
time-os-ui/src/components/FixDataCard.tsx
time-os-ui/src/components/Skeleton.tsx
time-os-ui/src/components/ErrorBoundary.tsx
time-os-ui/src/router.tsx
time-os-ui/src/__tests__/issue-helpers.test.ts
time-os-ui/src/__tests__/format.test.ts
time-os-ui/src/__tests__/priority.test.ts
time-os-ui/src/__tests__/apiConfig.test.ts
time-os-ui/src/__tests__/api.test.ts
time-os-ui/src/lib/datetime.ts
time-os-ui/src/lib/api.ts
time-os-ui/src/lib/priority.ts
time-os-ui/src/lib/format.ts
time-os-ui/src/lib/coupling.ts
time-os-ui/src/lib/teamLoad.ts
time-os-ui/src/lib/useDebounce.ts
time-os-ui/src/lib/thresholds.ts
time-os-ui/src/lib/hooks.ts
time-os-ui/src/lib/store.ts
time-os-ui/src/pages/RecentlyActiveDrilldown.tsx
time-os-ui/src/pages/Team.tsx
time-os-ui/src/pages/FixData.tsx
time-os-ui/src/pages/Inbox.tsx
time-os-ui/src/pages/Snapshot.tsx
time-os-ui/src/pages/Issues.tsx
time-os-ui/src/pages/TeamDetail.tsx
time-os-ui/src/pages/ClientDetailSpec.tsx
time-os-ui/src/pages/ColdClients.tsx
time-os-ui/src/pages/ClientDetail.tsx
time-os-ui/src/pages/index.ts
time-os-ui/src/pages/Clients.tsx
time-os-ui/src/pages/ClientIndex.tsx
(.venv) molhamhomsi@Molhams-MacBook-Pro-645 moh_time_os % ls -la docs 2>/dev/null
find docs -maxdepth 2 -type f -name "*.md" 2>/dev/null | head -n 120
ls -la lib/ui_spec_v21 2>/dev/null
ls -la lib/ui_spec_v21/*.md 2>/dev/null
sed -n '1,260p' lib/ui_spec_v21/CONTRACT_MAP.md 2>/dev/null
total 1248
drwxr-xr-x  21 molhamhomsi  staff     672 Feb 10 23:43 .
drwxr-xr-x  70 molhamhomsi  staff    2240 Feb 11 01:14 ..
-rw-r--r--   1 molhamhomsi  staff    8196 Feb 10 22:05 .DS_Store
-rw-r--r--   1 molhamhomsi  staff  275345 Feb 10 23:43 CLIENT-UI-SPEC-v2.9.md
-rw-r--r--   1 molhamhomsi  staff    3887 Jan 30 04:10 DISCOVERY.md
-rw-r--r--   1 molhamhomsi  staff   32638 Jan 30 18:52 FINANCIAL_PULSE_DESIGN.md
-rw-r--r--   1 molhamhomsi  staff   34780 Jan 30 22:34 IMPLEMENTATION.md
-rw-r--r--   1 molhamhomsi  staff   18068 Feb  3 14:53 PAGE0_AGENCY_CONTROL_ROOM_SPEC.md
-rw-r--r--   1 molhamhomsi  staff   10187 Feb  3 15:17 PAGE1_DELIVERY_COMMAND_SPEC.md
-rw-r--r--   1 molhamhomsi  staff    6986 Feb 10 23:43 SAFETY.md
-rw-r--r--   1 molhamhomsi  staff   11109 Feb 10 23:43 SPEC-ERRATA-v2.1.1.md
-rw-r--r--   1 molhamhomsi  staff   10213 Feb 10 23:43 SPEC-EXECUTIVE-SUMMARY.md
-rw-r--r--   1 molhamhomsi  staff   23417 Feb 10 23:43 SPEC-PATCH-v2.9.md
-rw-r--r--   1 molhamhomsi  staff   18059 Jan 30 22:32 SYSTEM_DESIGN.md
-rw-r--r--   1 molhamhomsi  staff  106516 Jan 31 03:01 SYSTEM_DESIGN_V3.md
drwxr-xr-x   8 molhamhomsi  staff     256 Feb 10 23:43 agent
drwxr-xr-x  15 molhamhomsi  staff     480 Feb  2 15:16 archive
drwxr-xr-x  14 molhamhomsi  staff     448 Feb  4 17:30 ui_atlas
-rw-r--r--   1 molhamhomsi  staff   51720 Feb  4 20:50 ui_atlas.zip
drwxr-xr-x   4 molhamhomsi  staff     128 Feb 10 22:05 ui_exec
drwxr-xr-x   3 molhamhomsi  staff      96 Feb  5 19:32 ui_spec
docs/IMPLEMENTATION.md
docs/ui_atlas/01_SYSTEM_MAP.md
docs/ui_atlas/00_INDEX.md
docs/ui_atlas/06_METRICS_AND_SCORES.md
docs/ui_atlas/08_UI_SURFACE_OPPORTUNITIES.md
docs/ui_atlas/02_SOURCES_AND_COLLECTORS.md
docs/ui_atlas/07_VIEWS_AND_QUERY_RECIPES.md
docs/ui_atlas/09_GAPS_FAILURE_MODES_AND_CONFIDENCE.md
docs/ui_atlas/11_CHANGELOG_AND_NEXT_STEPS.md
docs/ui_atlas/04_ENTITY_CATALOG.md
docs/archive/MASTER_CHECKLIST.md
docs/archive/OPS_LEDGER.md
docs/archive/SURGICAL_PLAN.md
docs/archive/BUILD_STATE.md
docs/archive/CRITIQUE.md
docs/archive/BUILD_PLAN.md
docs/archive/DESIGN_V4_SURGICAL.md
docs/archive/DESIGN_V3.md
docs/archive/BUILD_AUDIT.md
docs/archive/SPEC.md
docs/archive/CONFIG_PROPOSAL.md
docs/archive/FORENSIC_BUILD_SPEC.md
docs/archive/README_V2.md
docs/CLIENT-UI-SPEC-v2.9.md
docs/SYSTEM_DESIGN.md
docs/SAFETY.md
docs/agent/COMPLETE_SPEC_GAPS.md
docs/agent/heartbeat.md
docs/agent/agent_index_log.md
docs/agent/SPEC_GAP_ANALYSIS.md
docs/SPEC-ERRATA-v2.1.1.md
docs/DISCOVERY.md
docs/PAGE0_AGENCY_CONTROL_ROOM_SPEC.md
docs/PAGE1_DELIVERY_COMMAND_SPEC.md
docs/SPEC-EXECUTIVE-SUMMARY.md
docs/SPEC-PATCH-v2.9.md
docs/FINANCIAL_PULSE_DESIGN.md
docs/SYSTEM_DESIGN_V3.md
total 504
drwxr-xr-x  19 molhamhomsi  staff    608 Feb 10 23:43 .
drwxr-xr-x  80 molhamhomsi  staff   2560 Feb 10 23:43 ..
-rw-r--r--   1 molhamhomsi  staff   9459 Feb 10 23:43 CONTRACT_MAP.md
-rw-r--r--   1 molhamhomsi  staff   8158 Feb 10 23:43 IMPLEMENTATION_CHECKLIST.md
-rw-r--r--   1 molhamhomsi  staff    957 Feb 10 21:40 __init__.py
drwxr-xr-x  20 molhamhomsi  staff    640 Feb 11 00:18 __pycache__
-rw-r--r--   1 molhamhomsi  staff  20590 Feb 10 23:43 detectors.py
-rw-r--r--   1 molhamhomsi  staff  49945 Feb 10 23:43 endpoints.py
-rw-r--r--   1 molhamhomsi  staff  14956 Feb 10 23:43 engagement_lifecycle.py
-rw-r--r--   1 molhamhomsi  staff  13903 Feb 10 23:43 evidence.py
-rw-r--r--   1 molhamhomsi  staff   8870 Feb 10 23:43 health.py
-rw-r--r--   1 molhamhomsi  staff  13698 Feb 10 23:43 inbox_enricher.py
-rw-r--r--   1 molhamhomsi  staff  22981 Feb 10 23:43 inbox_lifecycle.py
-rw-r--r--   1 molhamhomsi  staff  22708 Feb 10 23:43 issue_lifecycle.py
drwxr-xr-x  10 molhamhomsi  staff    320 Feb 10 22:23 migrations
-rw-r--r--   1 molhamhomsi  staff   6825 Feb 10 23:43 org_settings.py
-rw-r--r--   1 molhamhomsi  staff  12062 Feb 10 23:43 suppression.py
drwxr-xr-x   7 molhamhomsi  staff    224 Feb 10 23:43 tests
-rw-r--r--   1 molhamhomsi  staff  21521 Feb 10 23:43 time_utils.py
-rw-r--r--  1 molhamhomsi  staff  9459 Feb 10 23:43 lib/ui_spec_v21/CONTRACT_MAP.md
-rw-r--r--  1 molhamhomsi  staff  8158 Feb 10 23:43 lib/ui_spec_v21/IMPLEMENTATION_CHECKLIST.md
# Contract Map — Time OS Client UI Specification v2.1

*Derived from spec_time_os_v2_1_final.md — 2026-02-07*

## 1. Database Tables

### 1.1 Core Tables

| Table | Spec Section | Purpose |
|-------|--------------|---------|
| `inbox_items` | 6.13 | Proposal wrappers for issues/signals/orphans/ambiguous |
| `issues` | 6.14 | Tracked problems from aggregated signals |
| `signals` | 6.15 | Single observations from source systems |
| `issue_transitions` | 6.5 | Audit trail for issue state changes |
| `engagement_transitions` | 6.7 | Audit trail for engagement state changes |
| `inbox_suppression_rules` | 1.8 | Suppression keys to prevent re-proposals |

### 1.2 Table Constraints (inbox_items)

| Constraint | Type | SQL |
|------------|------|-----|
| `chk_underlying_exclusive` | CHECK | `(underlying_issue_id IS NOT NULL) != (underlying_signal_id IS NOT NULL)` |
| `chk_type_issue_mapping` | CHECK | `type != 'issue' OR (underlying_issue_id IS NOT NULL AND underlying_signal_id IS NULL)` |
| `chk_type_signal_mapping` | CHECK | `type NOT IN ('flagged_signal', 'orphan', 'ambiguous') OR (underlying_signal_id IS NOT NULL AND underlying_issue_id IS NULL)` |
| `chk_snooze_requires_until` | CHECK | `state != 'snoozed' OR snooze_until IS NOT NULL` |
| `chk_dismissed_requires_key` | CHECK | `state != 'dismissed' OR suppression_key IS NOT NULL` |
| `chk_terminal_requires_resolved` | CHECK | `state NOT IN ('dismissed', 'linked_to_issue') OR resolved_at IS NOT NULL` |
| `chk_linked_requires_issue` | CHECK | `state != 'linked_to_issue' OR resolved_issue_id IS NOT NULL` |
| `chk_dismissed_requires_audit` | CHECK | `state != 'dismissed' OR (dismissed_at IS NOT NULL AND dismissed_by IS NOT NULL)` |

### 1.3 Unique Partial Indexes

| Index | Purpose |
|-------|---------|
| `idx_inbox_items_unique_active_issue` | At most one active inbox item per underlying issue |
| `idx_inbox_items_unique_active_signal` | At most one active inbox item per underlying signal |

---

## 2. Endpoints

### 2.1 Client Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/clients` | GET | 7.1 | Client index with sections active/recently_active/cold |
| `/api/clients/:id` | GET | 7.2 | Client detail with include policy |
| `/api/clients/:id/snapshot` | GET | 7.3 | Cold client snapshot from inbox |
| `/api/clients/:id/engagements` | GET | 7.4 | Engagements grouped by brand |
| `/api/clients/:id/financials` | GET | 7.5 | Financial summary with calc version |
| `/api/clients/:id/invoices` | GET | 7.5 | Invoice list with aging |
| `/api/clients/:id/issues` | GET | 7.6 | Issues with state/severity filters |
| `/api/clients/:id/signals` | GET | 7.7 | Signals summary and list |
| `/api/clients/:id/team` | GET | 7.8 | Team involvement and workload |
| `/api/clients/search` | GET | 7.10 | Client search |

### 2.2 Issue Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/issues/:id/transition` | POST | 7.6 | Issue state transitions |
| `/api/issues/:id/unsuppress` | POST | 7.6 | Unsuppress issue (idempotent) |

### 2.3 Inbox Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/inbox` | GET | 7.10 | Active inbox items (proposed/snoozed) |
| `/api/inbox/recent` | GET | 7.10 | Terminal items for audit |
| `/api/inbox/counts` | GET | 7.10 | Inbox counts by grouping |
| `/api/inbox/:id/action` | POST | 7.10 | Inbox actions (tag/assign/snooze/dismiss/link/select) |
| `/api/inbox/:id/mark_read` | POST | 7.10 | Mark item as read |
| `/api/inbox/mark_all_read` | POST | 7.10 | Bulk mark all as read |
| `/api/inbox/bulk_action` | POST | 7.10 | Bulk snooze/dismiss |
| `/api/inbox/search` | GET | 7.10 | Inbox search |

### 2.4 Engagement Endpoints

| Endpoint | Method | Spec Section | Purpose |
|----------|--------|--------------|---------|
| `/api/engagements/:id` | GET | 7.11 | Engagement detail |
| `/api/engagements/:id/transition` | POST | 7.11 | Engagement state transition |

---

## 3. State Machines

### 3.1 Issue Lifecycle (10 states)

```
detected → surfaced → acknowledged → addressing → awaiting_resolution → resolved → regression_watch → closed
                  ↓                                                                              ↓
              snoozed ←──────────────────────────────────────────────────────────────────── regressed
```

| State | Health Penalty | Open/Closed |
|-------|----------------|-------------|
| detected | No | Open |
| surfaced | Yes | Open |
| snoozed | No | Open |
| acknowledged | Yes | Open |
| addressing | Yes | Open |
| awaiting_resolution | Yes | Open |
| resolved | No | Closed |
| regression_watch | No | Closed |
| closed | No | Closed |
| regressed | Yes | Open |

### 3.2 Inbox Item Lifecycle (4 states)

```
proposed → snoozed → proposed (resurface)
      ↓        ↓
  linked_to_issue (terminal)
      ↓
  dismissed (terminal)
```

### 3.3 Engagement Lifecycle (7 states)

```
planned → active → delivering → delivered → completed
            ↓↑          ↓↑
         blocked, paused
```

---

## 4. Timers

| Timer | Frequency | Action |
|-------|-----------|--------|
| Snooze expiry (inbox) | Hourly | `snoozed` → `proposed` if `snooze_until <= now()` |
| Snooze expiry (issue) | Hourly | `snoozed` → `surfaced` + log transition |
| Regression watch | Daily | After 90d: `regression_watch` → `closed` |
| Suppression cleanup | Daily | Delete expired `inbox_suppression_rules` |

---

## 5. Deterministic Calculations

### 5.1 Timezone (0.1)

```python
def local_midnight_utc(org_tz: str, date: date) -> datetime:
    local_midnight = datetime.combine(date, time.min, tzinfo=ZoneInfo(org_tz))
    return local_midnight.astimezone(UTC)

def window_start(org_tz: str, days: int) -> datetime:
    local_today = datetime.now(ZoneInfo(org_tz)).date()
    local_start_date = local_today - timedelta(days=days)
    return local_midnight_utc(org_tz, local_start_date)
```

### 5.2 Client Status (6.1)

```
Active:          MAX(invoices.issue_date) >= today - 90 days
Recently Active: MAX(invoices.issue_date) >= today - 270 days AND < today - 90 days
Cold:            MAX(invoices.issue_date) < today - 270 days OR no invoices
```

### 5.3 Client Health (6.6)

```python
AR_penalty = floor(min(40, overdue_ratio * 60))
Issue_penalty = min(30, high_critical_open_issues * 10)
Health = max(0, 100 - AR_penalty - Issue_penalty)
```

### 5.4 Engagement Health (6.6/6.17)

```python
if open_tasks_in_source == 0:
    return None, "no_tasks"
if linked_pct < 0.90:
    return None, "task_linking_incomplete"
Overdue_penalty = floor(min(50, overdue_ratio * 80))
Completion_lag = floor(min(30, avg_days_late * 5))
Health = max(0, 100 - Overdue_penalty - Completion_lag)
```

### 5.5 Suppression Key (1.8)

```python
def suppression_key(item_type: str, data: dict) -> str:
    payload = {"v": "v1", "t": item_type, **data}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return "sk_" + hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]
```

### 5.6 Invoice Aging (7.5)

| status | Condition | days_overdue | aging_bucket | status_inconsistent |
|--------|-----------|--------------|--------------|---------------------|
| overdue | due_date not null | `max(0, today - due_date)` | Computed | false |
| overdue | due_date null | null | 90_plus | false |
| sent | due_date > today | null | current | false |
| sent | due_date <= today | Computed | Computed | **true** |
| paid/voided/draft | any | null | null | false |

---

## 6. Severity Ordering (0.1)

| Severity | Weight |
|----------|--------|
| critical | 5 |
| high | 4 |
| medium | 3 |
| low | 2 |
| info | 1 |

---

## 7. Suppression Expiry Defaults (1.8)

| Item Type | Expiry |
|-----------|--------|
| Issue | 90 days |
| Flagged Signal | 30 days |
| Orphan | 180 days |
| Ambiguous | 30 days |

---

## 8. Action Payload Validation (7.10)

| Action | Required | Optional | Reject if Present |
|--------|----------|----------|-------------------|
| tag | — | note | assign_to, snooze_days, link_engagement_id, select_candidate_id |
| assign | assign_to | note | snooze_days, link_engagement_id, select_candidate_id |
| snooze | snooze_days | note | assign_to, link_engagement_id, select_candidate_id |
| dismiss | — | note | assign_to, snooze_days, link_engagement_id, select_candidate_id |
| link | link_engagement_id | note | assign_to, snooze_days, select_candidate_id |
| select | select_candidate_id | note | assign_to, snooze_days, link_engagement_id |

---

## 9. Detector Rules (6.4)

| Rule ID | Source | Trigger |
|---------|--------|---------|
| meeting_cancelled_short_notice | calendar | Cancelled < 24h before start |
| email_unanswered_48h | gmail | Client email unanswered 48h+ |
| task_overdue | asana | Task past due_date |
| sentiment_negative | gmail/gchat/minutes | Sentiment < -0.3 |
| escalation_keyword | gchat | "urgent", "escalate", "problem" |
| invoice_overdue | xero | Invoice past due_date |
| invoice_status_inconsistent | xero | status='sent' AND due_date <= today |

---

## 10. Patch Notes (Contradiction Resolutions)

None detected. Spec is internally consistent.

---

*End of contract map.*
(.venv) molhamhomsi@Molhams-MacBook-Pro-645 moh_time_os % rg -n "CollectorOrchestrator|collector|register|registry" lib collectors engine api 2>/dev/null | head -n 80
rg -n "StateStore|sqlite|DB|SCHEMA_VERSION|user_version" lib api 2>/dev/null | head -n 80
rg -n "openapi|OpenAPI|schema|pydantic|BaseModel" api lib 2>/dev/null | head -n 80
rg -n "fetch\\(|axios|/api/|BASE_URL|VITE_" time-os-ui/src 2>/dev/null | head -n 80
api/BYTECODE_MANIFEST.md:805:- Doc: Get sync status for all collectors.
lib/heartbeat_processor.py:44:    """Load latest cached data from collectors."""
collectors/gmail_multi_user.py:24:STATE_DB = paths.data_dir() / "gmail_collector_state.db"
collectors/gmail_multi_user.py:145:    from collectors.gmail_direct import get_gmail_service
lib/protocol.py:270:                    lines.append("\n**Contacts:** None registered")
api/server.py:32:from lib.collectors import CollectorOrchestrator
api/server.py:72:collectors = CollectorOrchestrator(store=store)
api/server.py:224:        "sync_status": collectors.get_status(),
api/server.py:3261:    """Get sync status for all collectors."""
api/server.py:3262:    return collectors.get_status()
api/server.py:3268:    return collectors.force_sync(source=source)
api/server.py:3280:    loop = AutonomousLoop(store, collectors, analyzers, governance)
api/server.py:3290:        "sync": collectors.get_status(),
api/server.py:3366:        "sync_status": collectors.get_status(),
api/server.py:4005:    return collectors.sync(source="xero")
collectors/xero_ops.py:3:Xero Operational Intelligence collector.
collectors/scheduled_collect.py:75:    """Collect Gmail incrementally using multi-user collector."""
collectors/scheduled_collect.py:80:        collector_path = Path(__file__).parent / "gmail_multi_user.py"
collectors/scheduled_collect.py:82:            "gmail_multi_user", collector_path
collectors/scheduled_collect.py:84:        gmail_collector = importlib.util.module_from_spec(spec)
collectors/scheduled_collect.py:85:        spec.loader.exec_module(gmail_collector)
collectors/scheduled_collect.py:88:        gmail_collector.run_collection_cycle()
collectors/scheduled_collect.py:91:        status = gmail_collector.get_status()
collectors/scheduled_collect.py:218:            from lib.collectors.xero import XeroCollector
collectors/scheduled_collect.py:221:            xero_collector = XeroCollector({}, store=get_store())
collectors/scheduled_collect.py:222:            sync_result = xero_collector.sync()
collectors/scheduled_collect.py:291:    from lib.collector_registry import CollectorLock
collectors/scheduled_collect.py:296:            print("❌ Another collector is already running. Exiting.")
collectors/scheduled_collect.py:297:            return {"error": "locked", "message": "Another collector is running"}
collectors/scheduled_collect.py:306:    from lib.collector_registry import get_all_sources
collectors/scheduled_collect.py:316:    collectors = {
collectors/scheduled_collect.py:329:    # Run all collectors in parallel
collectors/scheduled_collect.py:332:            executor.submit(collectors[src]): src
collectors/scheduled_collect.py:334:            if src in collectors
collectors/scheduled_collect.py:352:            from v4_integration import ingest_from_collectors
collectors/scheduled_collect.py:357:            v4_results = ingest_from_collectors()
collectors/_legacy/README.md:5:These collectors were moved here during the collector cleanup (2025-02-10).
collectors/_legacy/README.md:10:- `team_calendar.py` — Multi-user calendar collector (superseded by scheduled_collect.py + V5)
collectors/_legacy/README.md:15:1. Not in `lib/collectors/orchestrator.py`'s `collector_map`
collectors/_legacy/README.md:16:2. Overlapping functionality with `collectors/scheduled_collect.py`
collectors/_legacy/README.md:23:collectors/scheduled_collect.py → out/*.json → V5 detectors → v29 tables → API
collectors/_legacy/asana_sync.py:9:    python3 -m lib.collectors.asana_sync sync        # Full sync
collectors/_legacy/asana_sync.py:10:    python3 -m lib.collectors.asana_sync projects    # Sync projects only
collectors/_legacy/asana_sync.py:11:    python3 -m lib.collectors.asana_sync tasks       # Sync tasks only
collectors/_legacy/asana_sync.py:12:    python3 -m lib.collectors.asana_sync map         # Show unmapped projects
collectors/_legacy/__init__.py:2:DEPRECATED: Legacy collectors — DO NOT IMPORT
collectors/_legacy/__init__.py:4:These collectors have been superseded by the canonical runner:
collectors/_legacy/__init__.py:5:    collectors/scheduled_collect.py
collectors/_legacy/__init__.py:13:        f"collectors._legacy.{name} is deprecated. "
collectors/_legacy/__init__.py:14:        f"Use collectors/scheduled_collect.py instead. "
engine/tasks_board.py:596:def write_board_from_collector_outputs(
lib/collectors/base.py:2:Base Collector - Template for all data collectors.
lib/collectors/base.py:3:Every collector MUST:
lib/collectors/base.py:20:    """Base class for all data collectors."""
lib/collectors/base.py:114:        """Check if this collector needs to sync."""
lib/collectors/base.py:121:        """Check if collector can reach its source."""
lib/daemon.py:107:        self._register_default_jobs()
lib/daemon.py:112:    def _register_default_jobs(self):
lib/daemon.py:116:        self.register_job(
lib/daemon.py:122:                    str(PROJECT_ROOT / "collectors" / "scheduled_collect.py"),
lib/daemon.py:128:        self.register_job(
lib/daemon.py:137:        self.register_job(
lib/daemon.py:145:    def register_job(self, config: JobConfig):
lib/collectors/orchestrator.py:2:Collector Orchestrator - Manages all collectors and coordinates syncing.
lib/collectors/orchestrator.py:23:class CollectorOrchestrator:
lib/collectors/orchestrator.py:25:    Orchestrates all data collectors.
lib/collectors/orchestrator.py:37:        self.collectors: dict[str, Any] = {}
lib/collectors/orchestrator.py:39:        self._init_collectors()
lib/collectors/orchestrator.py:49:    def _init_collectors(self):
lib/collectors/orchestrator.py:50:        """Initialize enabled collectors."""
lib/collectors/orchestrator.py:51:        # Map config names to collector classes
lib/collectors/orchestrator.py:52:        collector_map = {
lib/collectors/orchestrator.py:62:        # Always enable core collectors
lib/collectors/orchestrator.py:82:            collector_class = collector_map.get(source_name)
lib/collectors/orchestrator.py:83:            if collector_class:
lib/collectors/orchestrator.py:85:                    self.collectors[source_name] = collector_class(source_config, self.store)
lib/collectors/orchestrator.py:86:                    self.logger.info(f"Initialized collector: {source_name}")
lib/collectors/orchestrator.py:92:        Sync all collectors — delegates to canonical runner.
lib/collectors/orchestrator.py:98:        Sync one or all collectors — delegates to canonical runner.
lib/collectors/orchestrator.py:112:        from collectors.scheduled_collect import collect_all
api/spec_router.py:13:import sqlite3
api/spec_router.py:49:DB_PATH = paths.db_path()
api/spec_router.py:52:def get_db() -> sqlite3.Connection:
api/spec_router.py:54:    conn = sqlite3.connect(str(DB_PATH))
api/spec_router.py:55:    conn.row_factory = sqlite3.Row
api/spec_router.py:64:) -> Generator[sqlite3.Connection, None, None]:
api/server.py:8:import sqlite3
api/server.py:87:# ==== DB Startup & Migrations ====
api/server.py:90:    """Run DB migrations and log DB info at startup."""
api/server.py:94:        logger.info(f"DB path: {db_path}")
api/server.py:95:        logger.info(f"DB exists: {db_path.exists()}")
api/server.py:100:                logger.info(f"DB schema version (user_version): {version}")
api/server.py:110:        logger.warning(f"DB startup check failed: {e}")
api/server.py:120:        conn = sqlite3.connect(str(db_path))
api/server.py:121:        conn.row_factory = sqlite3.Row
api/server.py:1715:    conn = sqlite3.connect(store.db_path)
api/server.py:3306:    Returns resolved DB path, file info, schema version, and column lists
api/server.py:4343:        conn = sqlite3.connect(store.db_path)
api/server.py:4344:        conn.row_factory = sqlite3.Row
api/server.py:4516:        conn = sqlite3.connect(store.db_path)
api/server.py:4517:        conn.row_factory = sqlite3.Row
api/server.py:4679:        conn = sqlite3.connect(store.db_path)
api/server.py:4728:        conn = sqlite3.connect(store.db_path)
api/server.py:4769:        conn = sqlite3.connect(store.db_path)
api/server.py:4815:        conn = sqlite3.connect(store.db_path)
api/server.py:4816:        conn.row_factory = sqlite3.Row
api/server.py:4879:        conn = sqlite3.connect(store.db_path)
api/server.py:4908:        conn = sqlite3.connect(store.db_path)
api/server.py:4938:        conn = sqlite3.connect(store.db_path)
api/server.py:4939:        conn.row_factory = sqlite3.Row
api/server.py:5223:        conn = sqlite3.connect(store.db_path)
api/server.py:5224:        conn.row_factory = sqlite3.Row
api/server.py:5298:        conn = sqlite3.connect(store.db_path)
api/server.py:5299:        conn.row_factory = sqlite3.Row
api/server.py:5323:        conn = sqlite3.connect(store.db_path)
api/server.py:5324:        conn.row_factory = sqlite3.Row
api/server.py:5348:        conn = sqlite3.connect(store.db_path)
api/server.py:5349:        conn.row_factory = sqlite3.Row
api/server.py:5384:        conn = sqlite3.connect(store.db_path)
lib/heartbeat_processor.py:23:TIME_OS_DB_AVAILABLE = False
lib/heartbeat_processor.py:31:    TIME_OS_DB_AVAILABLE = True
lib/heartbeat_processor.py:219:    if TIME_OS_DB_AVAILABLE and overdue is not None:
lib/heartbeat_processor.py:232:    if not TIME_OS_DB_AVAILABLE:
lib/move_executor.py:14:import sqlite3
lib/move_executor.py:22:DB_PATH = paths.db_path()
lib/move_executor.py:29:    def __init__(self, db_path: Path = DB_PATH):
lib/move_executor.py:32:    def _get_conn(self) -> sqlite3.Connection:
lib/move_executor.py:33:        conn = sqlite3.connect(self.db_path)
lib/move_executor.py:34:        conn.row_factory = sqlite3.Row
lib/move_executor.py:88:        except sqlite3.Error as e:
lib/move_executor.py:134:        except sqlite3.Error as e:
lib/move_executor.py:187:        except sqlite3.OperationalError as e:
lib/governance.py:16:from .state_store import StateStore, get_store
lib/governance.py:36:    def __init__(self, config: dict = None, store: StateStore = None):
lib/governance.py:291:def get_governance(config: dict = None, store: StateStore = None) -> GovernanceEngine:
lib/calibration.py:15:from .state_store import StateStore, get_store
lib/calibration.py:23:    def __init__(self, store: StateStore = None):
lib/contracts/schema.py:25:SCHEMA_VERSION = "2.9.0"
lib/contracts/schema.py:228:    schema_version: str = SCHEMA_VERSION  # MUST match UI spec version
lib/contracts/schema.py:302:        if actual != SCHEMA_VERSION:
lib/contracts/schema.py:305:                f"but contract requires '{SCHEMA_VERSION}'. "
lib/contracts/__init__.py:27:    SCHEMA_VERSION,
lib/contracts/__init__.py:48:    "SCHEMA_VERSION",
lib/items.py:170:            refresh_context: If True, refresh entity state from DB
lib/status_engine.py:245:    import sqlite3
lib/status_engine.py:258:        conn = sqlite3.connect(db_path)
lib/collectors/base.py:6:3. Store in StateStore
lib/collectors/base.py:16:from ..state_store import StateStore, get_store
lib/collectors/base.py:22:    def __init__(self, config: dict, store: StateStore = None):
lib/health.py:10:    DB_PATH,
lib/health.py:20:BACKUP_DIR = DB_PATH.parent / "backups"
lib/health.py:113:        stat = os.statvfs(DB_PATH.parent)
lib/health.py:139:    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
lib/health.py:142:    # Initialize DB if missing
lib/db_writer.py:2:Single DB Write Module - All writes go through here.
lib/db_writer.py:11:import sqlite3
lib/db_writer.py:17:DB_PATH = paths.db_path()
lib/db_writer.py:20:class DBWriter:
lib/db_writer.py:23:    def __init__(self, db_path: Path = DB_PATH):
lib/db_writer.py:27:    def _get_conn(self) -> sqlite3.Connection:
api/spec_router.py:18:from pydantic import BaseModel
api/spec_router.py:98:class InboxActionRequest(BaseModel):
api/spec_router.py:107:class IssueTransitionRequest(BaseModel):
api/spec_router.py:881:class EngagementTransitionRequest(BaseModel):
api/server.py:15:from pydantic import BaseModel
api/server.py:99:                version = db_module.get_schema_version(conn)
api/server.py:100:                logger.info(f"DB schema version (user_version): {version}")
api/server.py:168:class ApprovalAction(BaseModel):
api/server.py:172:class ModeChange(BaseModel):
api/server.py:662:class TaskCreate(BaseModel):
api/server.py:674:class TaskUpdate(BaseModel):
api/server.py:864:class NoteAdd(BaseModel):
api/server.py:921:class DelegateRequest(BaseModel):
api/server.py:927:class EscalateRequest(BaseModel):
api/server.py:1540:class CleanupRequest(BaseModel):
api/server.py:2458:class FeedbackRequest(BaseModel):
api/server.py:2542:class DelegateAction(BaseModel):
api/server.py:2656:class BulkAction(BaseModel):
api/server.py:2770:class SavedFilter(BaseModel):
api/server.py:3142:class ModifyApproval(BaseModel):
api/server.py:3205:class ThresholdUpdate(BaseModel):
api/server.py:3306:    Returns resolved DB path, file info, schema version, and column lists
api/server.py:3764:class ClientUpdate(BaseModel):
api/server.py:3885:class EnrollmentAction(BaseModel):
api/server.py:4137:class BlockerRequest(BaseModel):
api/server.py:4670:class ResolveIssueRequest(BaseModel):
api/server.py:4711:class ChangeIssueStateRequest(BaseModel):
api/server.py:4760:class AddIssueNoteRequest(BaseModel):
api/server.py:4871:class DismissWatcherRequest(BaseModel):
api/server.py:4899:class SnoozeWatcherRequest(BaseModel):
api/server.py:5005:class TagProposalRequest(BaseModel):
api/server.py:5171:class SnoozeProposalRequest(BaseModel):
api/server.py:5193:class DismissProposalRequest(BaseModel):
api/server.py:5212:class ResolveFixDataRequest(BaseModel):
lib/contracts/schema.py:14:Any schema changes must be coordinated with frontend.
lib/contracts/schema.py:19:from pydantic import BaseModel, Field, field_validator, model_validator
lib/contracts/schema.py:33:class AgingBucket(BaseModel):
lib/contracts/schema.py:41:class DebtorEntry(BaseModel):
lib/contracts/schema.py:55:class CashARTiles(BaseModel):
lib/contracts/schema.py:64:class CashARSection(BaseModel):
lib/contracts/schema.py:82:class PortfolioProject(BaseModel):
lib/contracts/schema.py:96:class DeliveryCommandSection(BaseModel):
lib/contracts/schema.py:108:class HeatstripProject(BaseModel):
lib/contracts/schema.py:127:class ClientEntry(BaseModel):
lib/contracts/schema.py:140:class Client360Section(BaseModel):
lib/contracts/schema.py:153:class CommitmentEntry(BaseModel):
lib/contracts/schema.py:166:class ThreadEntry(BaseModel):
lib/contracts/schema.py:177:class CommsCommitmentsSection(BaseModel):
lib/contracts/schema.py:190:class PersonEntry(BaseModel):
lib/contracts/schema.py:202:class CapacityCommandSection(BaseModel):
lib/contracts/schema.py:219:class MetaSection(BaseModel):
lib/contracts/schema.py:228:    schema_version: str = SCHEMA_VERSION  # MUST match UI spec version
lib/contracts/schema.py:231:class TrustSection(BaseModel):
lib/contracts/schema.py:244:class AgencySnapshotContract(BaseModel):
lib/contracts/schema.py:299:    def validate_schema_version(self):
lib/contracts/schema.py:300:        """Ensure snapshot schema_version matches expected UI spec version."""
lib/contracts/schema.py:301:        actual = self.meta.schema_version
lib/contracts/schema.py:318:    Validate snapshot against contract schema.
lib/contracts/__init__.py:5:- schema.py: Pydantic models for shape validation
lib/contracts/__init__.py:26:from .schema import (
lib/contracts/thresholds.py:123:        # Current schema limitation: commitments/communications lack client_id
lib/contracts/thresholds.py:125:        # TODO: Raise when schema supports client linkages
lib/entities.py:661:            # Try source_id first (new schema), fallback to asana_project_id (old schema)
lib/migrations/migrate_to_spec_v12.py:57:    """Migrate tasks to §12 schema."""
lib/migrations/migrate_to_spec_v12.py:64:    # §12 tasks schema + legacy columns
lib/migrations/migrate_to_spec_v12.py:185:    """Migrate communications to §12 schema."""
lib/migrations/migrate_to_spec_v12.py:296:    """Migrate projects to §12 schema."""
lib/migrations/migrate_to_spec_v12.py:398:    """Migrate clients to §12 schema."""
lib/migrations/migrate_to_spec_v12.py:451:    """Migrate invoices to §12 schema."""
lib/migrations/migrate_to_spec_v12.py:506:    """Migrate commitments to §12 schema."""
lib/migrations/migrate_to_spec_v12.py:764:def verify_schema(conn):
lib/migrations/migrate_to_spec_v12.py:839:        if verify_schema(conn):
lib/migrations/v4_milestone4_intersections_reports_policy.py:119:        cursor.execute("SELECT MAX(version) FROM _schema_version")
lib/migrations/v4_milestone4_intersections_reports_policy.py:125:        logger.info("_schema_version table missing. Run v4_milestone1 migration first.")
lib/migrations/v4_milestone4_intersections_reports_policy.py:130:        "INSERT INTO _schema_version (version, applied_at) VALUES (?, ?)",
lib/state_store.py:52:        self._init_schema()
lib/state_store.py:75:    def _init_schema(self):
lib/state_store.py:78:            # Skip schema creation if core tables already exist (moh_time_os.db has V4 schema)
lib/state_store.py:83:                # Database already has tables, skip schema init
lib/state_store.py:333:                -- COMMITMENTS (§12 schema)
time-os-ui/src/pages/ClientIndex.tsx:8:const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';
time-os-ui/src/pages/ClientIndex.tsx:71:        const res = await fetch(url);
time-os-ui/src/pages/ColdClients.tsx:8:const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';
time-os-ui/src/pages/ColdClients.tsx:57:        const res = await fetch(`${API_BASE}/clients?${params.toString()}`);
time-os-ui/src/pages/Inbox.tsx:8:const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';
time-os-ui/src/pages/Inbox.tsx:91:      const res = await fetch(`${API_BASE}/inbox/counts`);
time-os-ui/src/pages/Inbox.tsx:115:      const res = await fetch(url);
time-os-ui/src/pages/Inbox.tsx:195:      const res = await fetch(`${API_BASE}/inbox/${itemId}/action?actor=user`, {
time-os-ui/src/pages/ClientDetailSpec.tsx:8:const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';
time-os-ui/src/pages/ClientDetailSpec.tsx:199:        const res = await fetch(`${API_BASE}/clients/${clientId}`);
time-os-ui/src/pages/ClientDetailSpec.tsx:253:      const res = await fetch(`${API_BASE}/issues/${issueId}/transition?actor=user`, {
time-os-ui/src/pages/ClientDetailSpec.tsx:260:      const clientRes = await fetch(`${API_BASE}/clients/${clientId}`);
time-os-ui/src/lib/store.ts:176:        actor: import.meta.env.VITE_ACTOR || 'moh',
time-os-ui/src/types/spec.ts:2:// Source of truth: /api/v2/* endpoints
time-os-ui/src/pages/FixData.tsx:74:        refetch();
time-os-ui/src/pages/FixData.tsx:125:    refetch();
time-os-ui/src/pages/RecentlyActiveDrilldown.tsx:8:const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';
time-os-ui/src/pages/RecentlyActiveDrilldown.tsx:84:        const res = await fetch(`${API_BASE}/clients/${clientId}?include=recently_active`);
time-os-ui/src/types/api.ts:2:// Source of truth: /api/v2/* endpoints (spec-compliant)
time-os-ui/src/lib/api.ts:2:// Connects to FastAPI backend at /api/v2/* (spec-compliant)
time-os-ui/src/lib/api.ts:17:// API base URL: configurable via env, defaults to /api/v2 for spec-compliant endpoints
time-os-ui/src/lib/api.ts:18:const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';
time-os-ui/src/lib/api.ts:21:let currentActor = import.meta.env.VITE_ACTOR || 'system';
time-os-ui/src/lib/api.ts:90:    res = await fetch(url);
time-os-ui/src/lib/api.ts:183:  // LEGACY: backend-only endpoint; migrate to /api/v2 when available
time-os-ui/src/lib/api.ts:184:  return fetchJson(`/api/control-room/proposals/${proposalId}`);
time-os-ui/src/lib/api.ts:187:// Tasks API (uses /api/tasks)
time-os-ui/src/lib/api.ts:193:  let url = `/api/tasks?limit=${limit}`;
time-os-ui/src/lib/api.ts:210:  const res = await fetch(url, {
time-os-ui/src/lib/api.ts:320:  const res = await fetch(url, {
time-os-ui/src/__tests__/apiConfig.test.ts:8:  it('should use VITE_API_BASE_URL when set', () => {
time-os-ui/src/__tests__/apiConfig.test.ts:9:    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/control-room');
time-os-ui/src/__tests__/apiConfig.test.ts:12:    expect(import.meta.env.VITE_API_BASE_URL).toBe('https://api.example.com/control-room');
time-os-ui/src/__tests__/apiConfig.test.ts:18:    const apiBase = envValue || '/api/control-room';
time-os-ui/src/__tests__/apiConfig.test.ts:20:    expect(apiBase).toBe('/api/control-room');
time-os-ui/src/__tests__/apiConfig.test.ts:28:    const apiBase = envValue || '/api/control-room';
time-os-ui/src/__tests__/api.test.ts:5:const API_BASE = 'http://localhost:8420/api/control-room';
time-os-ui/src/__tests__/api.test.ts:12:    const res = await fetch(`${API_BASE}/clients`, { signal: AbortSignal.timeout(2000) });
time-os-ui/src/__tests__/api.test.ts:25:      const res = await fetch(`${API_BASE}/proposals?limit=5&status=open&days=30`);
time-os-ui/src/__tests__/api.test.ts:47:      const res1 = await fetch(`${API_BASE}/proposals?limit=100&days=1`);
time-os-ui/src/__tests__/api.test.ts:48:      const res30 = await fetch(`${API_BASE}/proposals?limit=100&days=30`);
time-os-ui/src/__tests__/api.test.ts:62:      const res = await fetch(`${API_BASE}/issues?limit=10&days=30`);
time-os-ui/src/__tests__/api.test.ts:82:      const res = await fetch(`${API_BASE}/clients`);
time-os-ui/src/__tests__/api.test.ts:103:      const res = await fetch(`${API_BASE}/team`);
time-os-ui/src/__tests__/api.test.ts:122:      const res = await fetch(`${API_BASE}/couplings`);
time-os-ui/src/__tests__/api.test.ts:142:      const res = await fetch(`${API_BASE}/proposals?limit=100&days=90`);
time-os-ui/src/__tests__/api.test.ts:161:      const res = await fetch(`${API_BASE}/issues?limit=100&days=90`);
time-os-ui/src/__tests__/api.test.ts:178:      const res = await fetch(`${API_BASE}/proposals?limit=50&days=30`);
time-os-ui/src/__tests__/api.test.ts:192:      const issuesRes = await fetch(`${API_BASE}/issues?limit=1&days=90`);
time-os-ui/src/__tests__/api.test.ts:202:      const res = await fetch(`${API_BASE}/issues/${issueId}/resolve`, {
time-os-ui/src/__tests__/api.test.ts:224:      const issuesRes = await fetch(`${API_BASE}/issues?limit=1&days=90`);
time-os-ui/src/__tests__/api.test.ts:234:      const res = await fetch(`${API_BASE}/issues/${issueId}/notes`, {
time-os-ui/src/__tests__/api.test.ts:256:      const proposalsRes = await fetch(`${API_BASE}/proposals?limit=1&days=90`);
time-os-ui/src/__tests__/api.test.ts:266:      const res = await fetch(`${API_BASE}/proposals/${proposalId}/dismiss`, {
time-os-ui/src/__tests__/api.test.ts:299:    const res = await fetch(`${API_BASE}/health`);
