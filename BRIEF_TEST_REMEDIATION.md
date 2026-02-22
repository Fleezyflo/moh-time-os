# BRIEF: Test Remediation
> Status: PENDING
> Branch: `brief/test-remediation`
> Trigger: Data Foundation complete — 58 pre-existing test failures (14 collection errors, 5 setup errors, 39 runtime failures) blocking green CI

## Problem Statement

The test suite reports 446 pass / 39 fail / 5 error / 14 collection error. Every failure traces to one of four root causes:

| Root Cause | Impact | Files | Tests Blocked |
|---|---|---|---|
| `from datetime import UTC` (Python 3.11+) | 26 source files import UTC which doesn't exist in Python 3.10 | 26 | 27 errors + 20 failures |
| `from enum import StrEnum` (Python 3.11+) | 16 source files import StrEnum which doesn't exist in Python 3.10 | 16 | 2 errors + 15 failures |
| Missing `pydantic` / `fastapi` packages | Contract tests and API tests can't import | 8+10 | 9 errors + 2 failures |
| `asana_project_map` test fixture schema mismatch | Test creates columns `project_name, asana_gid` but code queries `asana_name, project_id` | 1 test + 1 source | 4 failures |

## Goals

1. **Zero collection errors** — all test files import successfully
2. **Zero test failures** attributable to Python 3.10 compatibility
3. **Zero test failures** from schema mismatches
4. **Full suite green** — 490+ tests passing with 0 failures, 0 errors

## Approach: Compatibility Shims (Not Upgrade)

We fix the source code to work on Python 3.10+, NOT upgrade Python. Rationale:
- Moh's production Mac runs 3.10 (system Python used by launchd plist)
- Shims are 1-line changes; upgrading Python is an environment risk
- `datetime.timezone.utc` is the canonical equivalent of `UTC`
- `class StrEnum(str, Enum): pass` is the standard 3.10 backport pattern

## Phases

| Phase | Name | Tasks | Purpose |
|---|---|---|---|
| 1 | Fix Import Shims | 1.1, 1.2 | Make all 42 source files importable on Python 3.10 |
| 2 | Install Missing Deps | 2.1 | Add pydantic + fastapi to dev dependencies |
| 3 | Fix Schema Mismatch | 3.1 | Align test fixture with production schema |
| 4 | Validation | 4.1 | Full suite green, no regressions |

## Out of Scope

- Upgrading Python to 3.11+
- Changing test logic or expected values (only import/schema fixes)
- Modifying protected files
