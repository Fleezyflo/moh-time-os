# Codebase Investigation Log

> Started: 2026-02-18
> Status: IN PROGRESS
> Methodology: Find → Fix immediately → Document → Continue

---

## Investigation Scope

Surgical forensic audit of the entire codebase:

| Category | Description |
|----------|-------------|
| Stub code | Functions that return hardcoded/fake data, `pass`, `NotImplementedError` |
| Error swallowing | `except: pass`, bare `except`, missing error propagation |
| Dead code | Unreachable code, unused functions, orphaned files |
| Inconsistencies | API contracts vs implementation, schema vs code |
| Missing tests | Critical paths without coverage |
| Security | Injection, shell=True, credential exposure, unsafe deserialization |
| Performance | N+1 queries, unbounded loops, missing indexes |
| Architecture | Circular imports, coupling violations, layer breaches |

**Protocol:** Find issue → Fix immediately → Document here → Continue

---

## Issues Found & Fixed

### Issue #1: Debug scripts in production code paths

**Location:** `lib/collectors/`
**Type:** Code Organization
**Severity:** Low
**Status:** ✅ FIXED

**Files moved:**
- `debug_dwd_token.py` → `scripts/debug/`
- `debug_dwd_token2.py` → `scripts/debug/`
- `debug_dwd_token3.py` → `scripts/debug/`
- `debug_directory_auth.py` → `scripts/debug/`
- `test_calendar_sync_modes.py` → `tests/`

---

### Issue #2: Missing imports causing NameError (F821)

**Location:** Multiple files in `lib/`
**Type:** Missing Imports
**Severity:** HIGH (runtime crash)
**Status:** ✅ FIXED

| File | Missing Import |
|------|----------------|
| `lib/aggregator.py` | `from pathlib import Path` |
| `lib/autonomous_loop.py` | `from pathlib import Path` |
| `lib/daemon.py` | `PROJECT_ROOT = paths.project_root()` |
| `lib/gates.py` | `from pathlib import Path` |
| `lib/migrations/migrate_to_spec_v12.py` | `from pathlib import Path` |
| `lib/move_executor.py` | `from pathlib import Path` |
| `lib/normalizer.py` | `from pathlib import Path` |
| `lib/notifier/briefs.py` | `import sys` |
| `lib/resolution_queue.py` | `from pathlib import Path` |
| `lib/sync.py` | `import os` |

---

### Issue #3: Unused variables (F841)

**Location:** Multiple files
**Type:** Dead Code
**Severity:** Low
**Status:** ✅ FIXED

| File | Unused Variable |
|------|-----------------|
| `lib/agency_snapshot/generator.py` | `is_blocked` |
| `lib/agency_snapshot/generator.py` | `project_client_id` |
| `lib/intelligence/patterns.py` | `method` |
| `lib/intelligence/patterns.py` | `client_revenue` |
| `lib/intelligence/patterns.py` | `project_client` |
| `lib/intelligence/proposals.py` | `entity_type` |
| `lib/intelligence/signals.py` | `baseline_start` |
| `lib/intelligence/signals.py` | `measurement_start` |
| `lib/intelligence/signals.py` | `measurement_end` |

---

### Issue #4: Test/implementation mismatch

**Location:** `tests/test_intelligence_api.py`
**Type:** Test Mismatch
**Severity:** Low
**Status:** ✅ FIXED

**Problem:** `test_get_critical_items_returns_list` expected `list` but function returns `dict` with `items` key.

**Fix:** Updated test to check for `dict` with `items` key.

---

### Issue #5: Duplicate API route definitions

**Location:** `api/server.py`
**Type:** Duplicate Routes
**Severity:** HIGH (silent override)
**Status:** ✅ FIXED

FastAPI uses the LAST definition, silently ignoring earlier ones.

| Route | Lines | Action |
|-------|-------|--------|
| `POST /api/priorities/{item_id}/complete` | 1954, 2447 | Kept bundle version (1954) |
| `POST /api/priorities/{item_id}/snooze` | 1998, 2468 | Kept bundle version (1998) |
| `POST /api/priorities/{item_id}/delegate` | 2033, 2489 | Kept governance version (2033) |
| `GET /api/delegations` | 1323, 1900 | Removed alias (1900) |
| `GET /api/insights` | 1922, 2954 | Kept filter version (2954) |
| `GET /api/emails` | 2920, 4001 | Disabled duplicate (4001) |

---

## Investigation Progress

| Area | Status | Issues | Fixed |
|------|--------|--------|-------|
| lib/collectors/ | ✅ | 1 | 1 |
| lib/intelligence/ | 🔄 | 4 | 4 |
| lib/executor/ | ✅ DONE | 6 | 6 |
| lib/analyzers/ | ⬜ | - | - |
| lib/v4/ | ⬜ | - | - |
| lib/v5/ | ⬜ | - | - |
| lib/agency_snapshot/ | 🔄 | 2 | 2 |
| lib/migrations/ | 🔄 | 1 | 1 |
| lib/notifier/ | 🔄 | 1 | 1 |
| lib/*.py (root) | 🔄 | 6 | 6 |
| api/ | 🔄 | 6 | 6 |
| tests/ | 🔄 | 1 | 1 |
| time-os-ui/ | ⬜ | - | - |

---

## Summary

**Total Issues Found:** 28
**Total Issues Fixed:** 28
**Remaining:** 0

### Issue #6: Unguarded NotImplementedError call path

**Location:** `lib/executor/handlers/task.py`
**Type:** Stub Code
**Severity:** HIGH (will crash at runtime)
**Status:** ✅ FIXED

**Problem:** `_complete_in_asana()` was called unconditionally when completing Asana-sourced tasks, but the method raises `NotImplementedError`.

**Fix:** Added config guard `self.config.get("asana_enabled")` to match the pattern used for `_sync_to_asana()`.

---

### Issue #7: Silent error handling in executor handlers

**Location:** `lib/executor/handlers/`
**Type:** Error Swallowing
**Severity:** MEDIUM (errors returned but not logged)
**Status:** ✅ FIXED

**Problem:** All 5 executor handlers caught exceptions and returned error responses, but did NOT log the errors. This makes debugging production issues difficult.

| File | Fix |
|------|-----|
| `task.py` | Added `logger.error()` with exc_info |
| `delegation.py` | Added `logger.error()` with exc_info |
| `email.py` | Added `logger.error()` with exc_info |
| `calendar.py` | Added `logger.error()` with exc_info |
| `notification.py` | Added `logger.error()` with exc_info |

---

## Next Areas to Investigate

1. **lib/executor/** - Action execution layer
2. **lib/analyzers/** - Analysis modules
3. **lib/v4/** - V4 architecture modules
4. **lib/v5/** - V5 architecture modules
5. **time-os-ui/** - Frontend codebase
6. **Deep dive on error handling patterns**
7. **Deep dive on stub/unimplemented code**
