# Guardrails Index

All guardrail files collected in one place. Subfolders match original locations.

## Structure

```
_guardrails/
├── git_hooks/           ← from .git/hooks/
│   ├── pre-commit       # Runs pre-commit framework
│   ├── commit-msg       # Validates commit message format
│   └── pre-push         # Runs before push to remote
│
├── pre-commit/          ← from repo root
│   └── .pre-commit-config.yaml   # Orchestrates all hooks
│
├── semgrep/             ← from .semgrep/
│   ├── security-rules.yaml       # Security patterns
│   ├── policy-rules.yaml         # Policy enforcement
│   ├── rules.yaml                # General rules
│   └── .semgrepignore            # Exclusions
│
├── python_config/       ← from repo root
│   └── pyproject.toml            # ruff, bandit, mypy, pytest config
│
├── scripts/             ← from scripts/
│   ├── check_secrets.py          # P0: Hardcoded secrets
│   ├── check_vulnerabilities.py  # P0: Vulnerable dependencies
│   ├── check_sql_fstrings.py     # P0: SQL injection
│   ├── check_path_traversal.py   # P0: Path traversal
│   ├── check_pii_logging.py      # P0: PII in logs
│   ├── check_duplicate_endpoints.py  # P1
│   ├── check_import_boundaries.py    # P1
│   ├── check_breaking_changes.py     # P1
│   ├── check_monolith_files.py       # P1
│   ├── check_empty_db.py             # P1
│   ├── check_migration_safety.py     # P1
│   ├── check_licenses.py             # P1
│   ├── check_complexity.py           # P2
│   ├── check_docstrings.py           # P2
│   ├── check_error_handling.py       # P2
│   ├── check_no_print.py             # P2
│   ├── check_query_safety.py         # P2
│   ├── check_transaction_safety.py   # P2
│   ├── check_pagination.py           # P2
│   ├── check_response_types.py       # P2
│   ├── check_hardcoded_config.py     # P2
│   ├── check_unused_deps.py          # P2
│   ├── check_env_vars.py             # P2
│   ├── check_circular_imports.py     # P2
│   ├── check_dead_code.py            # P2
│   ├── check_global_state.py         # P2
│   ├── check_endpoint_auth.py        # P2
│   ├── check_http_timeouts.py        # P2
│   ├── check_async_blocking.py       # P2
│   ├── check_test_skips.py           # P2
│   ├── check_new_code_tests.py       # P2
│   ├── check_lockfile_sync.py        # P2
│   ├── check_accessibility.py        # FE
│   ├── check_no_console.py           # FE
│   ├── check_bundle_size.py          # FE
│   ├── check_mypy.py
│   ├── check_mypy_baseline.py
│   ├── check_coverage.py
│   ├── check_test_coverage.py
│   ├── check_commit_message.py
│   ├── check_api_breaking.py
│   └── check_system_invariants.py
│
├── github_workflows/    ← from .github/workflows/
│   ├── ci.yml                    # Main CI (runs pre-commit)
│   ├── guardrails.yml            # Guardrails-specific
│   └── nightly.yml               # Nightly checks
│
├── frontend/            ← from time-os-ui/
│   ├── eslint.config.js          # ESLint rules
│   ├── tsconfig.json             # TypeScript config
│   ├── vitest.config.ts          # Test config
│   ├── .prettierrc               # Formatting
│   └── package.json              # Dependencies + scripts
│
└── repo_policies/       ← from repo root
    ├── CODEOWNERS                # Code ownership
    ├── .nvmrc                    # Node version
    ├── .envrc                    # direnv
    ├── Makefile                  # Make targets
    └── GUARDRAILS_VERIFICATION.md
```

## Original Locations

| Folder | Original Path |
|--------|---------------|
| git_hooks/ | `.git/hooks/` |
| pre-commit/ | `.pre-commit-config.yaml` |
| semgrep/ | `.semgrep/` |
| python_config/ | `pyproject.toml` |
| scripts/ | `scripts/check_*.py` |
| github_workflows/ | `.github/workflows/` |
| frontend/ | `time-os-ui/` |
| repo_policies/ | repo root |

## Priority Levels

- **P0**: Security critical - blocks commit
- **P1**: Architecture/safety - blocks commit  
- **P2**: Code quality - blocks commit (per policy)
- **FE**: Frontend quality - blocks commit (per policy)
