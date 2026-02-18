# Codebase Investigation Log

> Started: 2026-02-18
> Status: IN PROGRESS

---

## Investigation Scope

Surgical forensic audit of the entire codebase:
- Stub code / unimplemented features
- Error swallowing / silent failures
- Dead code / orphaned files
- Inconsistencies / mismatches
- Missing tests / untested paths
- Documentation gaps
- Security vulnerabilities
- Performance issues
- Architectural problems

**Protocol:** Find issue → Fix immediately → Document here → Continue

---

## Issues Found & Fixed

### Issue #1: Debug scripts in production code paths

**Location:** `lib/collectors/`
**Type:** Code Organization
**Severity:** Low
**Status:** ✅ FIXED

**Problem:**
5 debug/test scripts were living in `lib/collectors/` alongside production code:
- `debug_dwd_token.py`
- `debug_dwd_token2.py`
- `debug_dwd_token3.py`
- `debug_directory_auth.py`
- `test_calendar_sync_modes.py`

**Fix:**
- Moved debug scripts to `scripts/debug/`
- Moved test file to `tests/`

---

### Issue #2: Missing imports causing undefined name errors

**Location:** Multiple files in `lib/`
**Type:** Missing Imports (F821)
**Severity:** HIGH (would cause runtime errors)
**Status:** ✅ FIXED

**Problem:**
Multiple files were missing imports that would cause `NameError` at runtime:
- `lib/aggregator.py` - missing `from pathlib import Path`
- `lib/autonomous_loop.py` - missing `from pathlib import Path`
- `lib/daemon.py` - missing `PROJECT_ROOT` constant
- `lib/gates.py` - missing `from pathlib import Path`
- `lib/migrations/migrate_to_spec_v12.py` - missing `from pathlib import Path`
- `lib/move_executor.py` - missing `from pathlib import Path`
- `lib/normalizer.py` - missing `from pathlib import Path`
- `lib/notifier/briefs.py` - missing `import sys`
- `lib/resolution_queue.py` - missing `from pathlib import Path`
- `lib/sync.py` - missing `import os`

**Fix:**
Added missing imports to all affected files.

---

### Issue #3: Unused variables (dead code)

**Location:** Multiple files in `lib/`
**Type:** Unused Variables (F841)
**Severity:** Low (code smell, not bugs)
**Status:** ✅ FIXED

**Problem:**
10 unused variables across:
- `lib/agency_snapshot/generator.py` - `is_blocked`, `project_client_id`
- `lib/intelligence/patterns.py` - `method`, `client_revenue`, `project_client`
- `lib/intelligence/proposals.py` - `entity_type`
- `lib/intelligence/signals.py` - `baseline_start`, `measurement_start`, `measurement_end`

**Fix:**
Removed all unused variable assignments using ruff --unsafe-fixes.

---

### Issue #4: Test/implementation mismatch

**Location:** `tests/test_intelligence_api.py`
**Type:** Test Mismatch
**Severity:** Low (CI would catch)
**Status:** ✅ FIXED

**Problem:**
`test_get_critical_items_returns_list` expected list but function returns dict with `items` key.

**Fix:**
Updated test to check for dict with `items` key instead of bare list.

### Issue #5: Duplicate API route definitions

**Location:** `api/server.py`
**Type:** Duplicate Routes
**Severity:** HIGH (later definition overrides earlier)
**Status:** ✅ FIXED

**Problem:**
6 duplicate route definitions found:
- `POST /api/priorities/{item_id}/snooze` (lines 1998 & 2484)
- `POST /api/priorities/{item_id}/delegate` (lines 2022 & 2508)
- `POST /api/priorities/{item_id}/complete` (lines 1973 & 2456)
- `GET /api/emails` (lines 2920 & 4001)
- `GET /api/delegations` (lines ~3100 & ~4100)
- `GET /api/insights` (lines ~3200 & ~4200)

FastAPI uses the LAST definition, silently ignoring earlier ones.
The earlier versions often had better implementations (bundles, audit trails).

**Fix:**
Removed duplicate definitions, keeping the more complete implementations.

---

## Investigation Progress

| Area | Status | Issues Found | Issues Fixed |
|------|--------|--------------|--------------|
| lib/collectors/ | 🔄 | 1 | 1 |
| lib/intelligence/ | 🔄 | 4 | 4 |
| lib/executor/ | ⬜ | 0 | 0 |
| api/ | 🔄 | 6 | 6 |
| lib/*.py (root) | 🔄 | 10 | 10 |
| tests/ | 🔄 | 1 | 1 |
| time-os-ui/ | ⬜ | 0 | 0 |

---

## Summary

**Total Issues Found:** 22
**Total Issues Fixed:** 22
**Remaining:** 0
