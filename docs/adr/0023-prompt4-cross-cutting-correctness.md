# ADR-0023: Prompt 4 — Cross-Cutting Correctness Fixes

## Status
Accepted

## Context
Hostile verification (Pass 7) found production-grade defects across four categories that name-based detectors missed: naive `datetime.now()` calls via aliased imports, `fromtimestamp()` without timezone, module-level path captures that cache before env overrides take effect, and unguarded lazy singletons in `lib/v4/` services.

Affected trigger files: `lib/migrations/add_communications_columns.py` (removed module-level `DEFAULT_DB` path capture), `api/spec_router.py` (fixed mypy `str` vs `Path` type mismatch in `QueryEngine` constructor call).

## Decision
1. Convert all naive `datetime.now()` and `fromtimestamp()` calls to timezone-aware equivalents using `timezone.utc`, including aliased imports (`dt.now()` in orchestrator.py).
2. Replace module-level path constants (`CONFIG_PATH`, `KB_PATH`, `DEFAULT_DB`, etc.) with runtime getter functions that resolve paths at call time.
3. Add `threading.Lock()` with double-checked locking to all 13 lazy singletons in `lib/v4/`.
4. Replace name-based closed-list detectors with AST-walking structural detectors that catch any new violation regardless of variable naming or import aliasing.
5. Fix downstream type errors: add missing `timezone` imports, correct `str` vs `Path` mismatches, add `'degraded'` to `HealthResponse.status` union type.

## Consequences
- All datetime operations in production code are now timezone-aware. Structural detector prevents regression.
- Path resolution respects runtime environment overrides. Structural detector prevents new module-level captures.
- `lib/v4/` singletons are thread-safe under concurrent access.
- Test monkeypatches updated from constant patching to function patching (`_cassettes_dir` lambda).
- Changes to `lib/migrations/` and `api/spec_router.py` are non-behavioral (removed dead constant and fixed type annotation).
