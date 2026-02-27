# ADR-0007: Centralized Safe SQL — Bypass Comment Elimination

## Status
Accepted

## Context
ADR-0001 approved file-level lint suppressions for legacy S608 (dynamic SQL) across api/ and lib/. Over time, 141+ inline `noqa S608` / `nosec B608` / `type: ignore` comments accumulated across 34 files, each suppressing a real or potential SQL injection warning.

These bypass comments:
- Hid actual security warnings behind per-line suppressions
- Made it impossible to distinguish safe from unsafe SQL at a glance
- Grew with every new query, compounding technical debt

## Decision
Replace all inline bypass comments with a centralized `lib/safe_sql.py` module that:
1. Validates all dynamic identifiers against `[a-zA-Z0-9_]` before interpolation
2. Provides 16 typed builder functions (select, insert, update, delete, pragma, alter, drop, create, etc.)
3. Contains a single file-level `# ruff: noqa: S608` suppression — the only S608 suppression in the codebase
4. Raises `ValueError` on any identifier containing non-alphanumeric characters

This supersedes ADR-0001's S608 suppression strategy. The B904 file-level suppression in api/server.py remains (separate concern).

## Affected Files
- **New:** lib/safe_sql.py (centralized SQL builder)
- **Refactored:** 26 lib/ files, 2 api/ files, 2 scripts, 4 test files
- **api/server.py:** file-level noqa reduced from `B904,S608,S104` to `B904`
- **Test files:** f-string SQL converted to parameterized queries; hardcoded /tmp replaced with tempfile.gettempdir() (B108); xml.etree.ElementTree replaced with defusedxml (B314)

## Consequences
- Zero inline noqa S608 / nosec B608 in maintained scope
- Zero type:ignore in api/
- Single suppression point is auditable and enforceable
- Any new dynamic SQL must go through safe_sql.py or use parameterized queries
- ADR-0001 S608 provisions are fully superseded
