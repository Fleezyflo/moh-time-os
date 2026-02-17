# ADR-0001: Lint Suppression for Legacy Files

## Status
Accepted

## Context
The CI pipeline now runs full ruff linting on `api/` and `lib/` directories. Several legacy files contain pre-existing code patterns that trigger lint errors:

- **B904**: Exception re-raising without `from` (legacy HTTPException patterns)
- **S608**: Dynamic SQL construction (validated/escaped inputs)
- **S602**: subprocess with shell=True (controlled internal use)
- **S110**: Silent exception handling (intentional try-except-pass)
- **S104**: Binding to all interfaces (development server only)

These patterns exist throughout legacy code and are not practical to refactor without significant risk.

## Decision
Add file-level lint suppressions via:
1. Per-file-ignores in pyproject.toml for reusable configuration
2. File-level `# ruff: noqa:` comments for files with many issues

This approach:
- Enables full CI coverage on new code
- Avoids risky refactoring of stable legacy code
- Documents known technical debt explicitly

## Affected Files
- api/server.py (B904, S608, S104)
- api/spec_router.py (B904, S608) - via pyproject.toml only (protected file)
- lib/collectors/base.py (B904, S602)
- lib/safety/migrations.py (S608)
- lib/ui_spec_v21/*.py (S110, S608)

## Consequences
- New code in these files will still be subject to unignored rules
- Legacy patterns are documented as technical debt
- Full CI coverage for new files and modules
