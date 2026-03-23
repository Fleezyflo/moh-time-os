# Step 1b: Close Step 1 Gaps — Plan & Checklist

## Context

Step 1 committed 88 files of schema centralization, error handling refactoring, and daemon restoration. Post-commit audit revealed 4 gaps that were not addressed:

1. One `return {"error": ...}` still hiding errors in an except block
2. `subject_access.py` public methods not wrapped in DataResult (inconsistent with the rest of the governance layer)
3. Three API endpoints calling collector orchestrator without exception wrapping
4. `inbox_enricher.py` bare raises reaching API via unprotected endpoints (same 3 endpoints)

Two items initially flagged as violations were investigated and determined to be false positives:
- `proposal_service.py:385` — `safe_json()` is a data sanitizer for DB columns, not an error handler
- `threshold_adjuster.py:488,495` — returning `{"signals": {}}` on missing/corrupt YAML is correct startup behavior; raising would crash the constructor

## Files to Modify

| File | Type of Change |
|------|---------------|
| `lib/governance/data_export.py` | Fix 1 bare return in except |
| `lib/governance/subject_access.py` | Wrap 7 public methods in DataResult |
| `api/governance_router.py` | Unwrap DataResult at 7 endpoints |
| `api/intelligence_router.py` | Unwrap DataResult at 1 call site |
| `api/server.py` | Add try/except to 3 collector endpoints |
| `tests/test_subject_access.py` | Update ~60 assertions to unwrap DataResult |

## Detailed Changes

### 1. `lib/governance/data_export.py:224`

**Current:**
```python
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Error getting schema for {table}: {e}")
    return {"error": str(e)}
```

**Change to:**
```python
except (sqlite3.Error, ValueError, OSError) as e:
    logger.error(f"Error getting schema for {table}: {e}")
    raise
```

**Caller:** `_export_table_data()` at line ~196 already has a try/except wrapping this call.

---

### 2. `lib/governance/subject_access.py` — 7 methods

Each method gets the same pattern. Example for `create_request()`:

**Current:**
```python
def create_request(self, subject_identifier: str, ...) -> str:
    try:
        ...
        return request_id
    except (sqlite3.Error, ValueError) as e:
        logger.error(...)
        raise
```

**Change to:**
```python
def create_request(self, subject_identifier: str, ...) -> DataResult[str]:
    try:
        ...
        return DataResult.ok(request_id)
    except (sqlite3.Error, ValueError, OSError) as e:
        logger.error(...)
        return DataResult.fail(str(e))
```

**Methods and their return types:**

| Method | Line | Old Return | New Return |
|--------|------|-----------|------------|
| `create_request()` | 155 | `str` | `DataResult[str]` |
| `find_subject_data()` | 316 | `SubjectDataReport` | `DataResult[SubjectDataReport]` |
| `export_subject_data()` | 397 | `str` | `DataResult[str]` |
| `delete_subject_data()` | 470 | `DeletionResult` | `DataResult[DeletionResult]` |
| `anonymize_subject_data()` | 587 | `DeletionResult` | `DataResult[DeletionResult]` |
| `get_request_status()` | 704 | `SubjectAccessRequest\|None` | `DataResult[SubjectAccessRequest\|None]` |
| `list_requests()` | 733 | `list[SubjectAccessRequest]` | `DataResult[list[SubjectAccessRequest]]` |

**3 internal callers that must also unwrap:**

| Line | Caller Method | Calls | Change |
|------|--------------|-------|--------|
| 413 | `export_subject_data()` | `find_subject_data()` | Add: `if report_result.failed: return DataResult.fail(report_result.error)` then use `report_result.data` |
| 488 | `delete_subject_data()` | `find_subject_data()` | Same pattern |
| 605 | `anonymize_subject_data()` | `find_subject_data()` | Same pattern |

---

### 3. `api/governance_router.py` — 7 endpoint handlers

Each handler currently does:
```python
result = sae.some_method(...)
# uses result directly
```

Change to:
```python
result = sae.some_method(...)
if result.failed:
    raise HTTPException(status_code=500, detail=result.error)
# uses result.data instead of result
```

| Line | Endpoint | Method | Fields Accessed on `.data` |
|------|----------|--------|--------------------------|
| 59 | POST `/governance/subject-access` | `create_request()` | Used as `request_id` string |
| 84 | GET `/governance/subject-access/{id}` | `get_request_status()` | `.request_id`, `.subject_identifier`, `.status`, `.created_at` |
| 114 | GET `/governance/subject-access` | `list_requests()` | Iterated: `for req in result.data` |
| 168 | GET `/governance/subject-data/{id}` | `find_subject_data()` | `.subject_identifier`, `.tables_searched`, `.tables_with_data`, `.total_records`, `.data_by_table` |
| 180 | POST `/governance/subject-data/{id}/export` | `export_subject_data()` | Used as `file_path` string |
| 189 | DELETE `/governance/subject-data/{id}` | `delete_subject_data()` | `.subject_identifier`, `.tables_affected`, `.rows_deleted`, `.tables_skipped`, `.completed_at` |
| 202 | POST `/governance/subject-data/{id}/anonymize` | `anonymize_subject_data()` | `.subject_identifier`, `.tables_affected`, `.rows_anonymized`, `.tables_skipped`, `.completed_at` |

---

### 4. `api/intelligence_router.py` — 1 call site

| Line | Current | Change |
|------|---------|--------|
| 1440 | `deletion_requests = sae.list_requests(...)` then `len(deletion_requests)` | Unwrap: `result = sae.list_requests(...)`, check `result.failed`, use `len(result.data)` |

---

### 5. `api/server.py` — 3 unprotected endpoints

| Line | Endpoint | Current | Change |
|------|----------|---------|--------|
| 3218 | GET `/api/sync/status` | `return collectors.get_status()` | Wrap in `try/except Exception as e: raise HTTPException(status_code=500, detail=str(e))` |
| 3224 | POST `/api/sync` | `return collectors.force_sync(source=source or "")` | Same wrap |
| 3246 | GET `/api/status` | `"sync": collectors.get_status()` (inside dict) | Wrap entire dict construction |

---

### 6. `tests/test_subject_access.py` — ~60 assertions

Every test that calls a public method changes from:
```python
request_id = sae.create_request(...)
assert request_id.startswith("sar_")
```
To:
```python
result = sae.create_request(...)
assert result.succeeded
request_id = result.data
assert request_id.startswith("sar_")
```

**Exhaustive list of test lines to update:**

**`create_request()` assertions:**
- Line 187: `request_id = sae.create_request(...)` → unwrap
- Line 201: `request_id = sae.create_request(...)` → unwrap
- Line 222: `request_id = sae.create_request(...)` → unwrap
- Lines 244-245: `request_id = sae.create_request(...)` → unwrap
- Line 256: `request_id = sae.create_request(...)` → unwrap

**`get_request_status()` assertions:**
- Line 227: `status = sae.get_request_status(...)` → unwrap, check `.data`
- Line 237: `status = sae.get_request_status(...)` → unwrap, check `.data`

**`list_requests()` assertions:**
- Line 247: `requests = sae.list_requests(...)` → unwrap, iterate `.data`
- Line 258: `requests = sae.list_requests(...)` → unwrap, iterate `.data`

**`find_subject_data()` assertions:**
- Line 266: `report = sae.find_subject_data(...)` → unwrap, access `.data.tables_with_data`
- Line 277: `report = sae.find_subject_data(...)` → unwrap
- Line 286: `report = sae.find_subject_data(...)` → unwrap
- Line 295: `report = sae.find_subject_data(...)` → unwrap
- Line 304: `report = sae.find_subject_data(...)` → unwrap
- Line 315: `report = sae.find_subject_data(...)` → unwrap
- Line 330: `report = sae.find_subject_data(...)` → unwrap

**`export_subject_data()` assertions:**
- Line 315: `file_path = sae.export_subject_data(...)` → unwrap

**`delete_subject_data()` assertions:**
- Line 349: `result = sae.delete_subject_data(...)` → unwrap `.data`
- Line 366: `result = sae.delete_subject_data(...)` → unwrap `.data`
- Line 381: `result = sae.delete_subject_data(...)` → unwrap `.data`
- Line 397: `result = sae.delete_subject_data(...)` → unwrap `.data`
- Line 411: `result = sae.delete_subject_data(...)` → unwrap `.data`
- Line 424: `result = sae.delete_subject_data(...)` → unwrap `.data`

**`anonymize_subject_data()` assertions:**
- Line 442: `result = sae.anonymize_subject_data(...)` → unwrap `.data`
- Line 455: `result = sae.anonymize_subject_data(...)` → unwrap `.data`
- Line 471: `result = sae.anonymize_subject_data(...)` → unwrap `.data`
- Line 491: `result = sae.anonymize_subject_data(...)` → unwrap `.data`
- Line 539: `result = sae.anonymize_subject_data(...)` → unwrap `.data`
- Line 543: `result = sae.anonymize_subject_data(...)` → unwrap `.data`

---

## Execution Checklist

### A. Fix `data_export.py:224`
- [ ] A1. Change `return {"error": str(e)}` to `raise` at line 224
- [ ] A2. Read caller at line ~196 to confirm it catches the re-raised exception
- [ ] A3. ruff check `lib/governance/data_export.py`
- [ ] A4. Run `pytest tests/ -k data_export -x -q`

### B. Wrap `subject_access.py` methods in DataResult

**B.0 — Setup**
- [ ] B0a. Add `from lib.common.result_types import DataResult` to subject_access.py imports

**B.1 — `create_request()` (line 155)**
- [ ] B1a. Wrap success return in `DataResult.ok(request_id)`
- [ ] B1b. Wrap failure path in `DataResult.fail(str(e))`
- [ ] B1c. Update `api/governance_router.py:59` — unwrap with `result.failed` check, use `result.data`
- [ ] B1d. Update `tests/test_subject_access.py` lines 187, 201, 222, 244-245, 256

**B.2 — `find_subject_data()` (line 316)**
- [ ] B2a. Wrap success return in `DataResult.ok(report)`
- [ ] B2b. Wrap failure path in `DataResult.fail(str(e))`
- [ ] B2c. Update internal caller at line 413 (`export_subject_data`) — check `result.failed`
- [ ] B2d. Update internal caller at line 488 (`delete_subject_data`) — check `result.failed`
- [ ] B2e. Update internal caller at line 605 (`anonymize_subject_data`) — check `result.failed`
- [ ] B2f. Update `api/governance_router.py:168` — unwrap, access `.data.subject_identifier` etc.
- [ ] B2g. Update `tests/test_subject_access.py` lines 266, 277, 286, 295, 304, 315, 330

**B.3 — `export_subject_data()` (line 397)**
- [ ] B3a. Wrap success return in `DataResult.ok(file_path)`
- [ ] B3b. Wrap failure path in `DataResult.fail(str(e))`
- [ ] B3c. Update `api/governance_router.py:180` — unwrap
- [ ] B3d. Update `tests/test_subject_access.py` line 315

**B.4 — `delete_subject_data()` (line 470)**
- [ ] B4a. Wrap success return in `DataResult.ok(deletion_result)`
- [ ] B4b. Wrap failure path in `DataResult.fail(str(e))`
- [ ] B4c. Update `api/governance_router.py:189` — unwrap, access `.data.tables_affected` etc.
- [ ] B4d. Update `tests/test_subject_access.py` lines 349, 366, 381, 397, 411, 424

**B.5 — `anonymize_subject_data()` (line 587)**
- [ ] B5a. Wrap success return in `DataResult.ok(deletion_result)`
- [ ] B5b. Wrap failure path in `DataResult.fail(str(e))`
- [ ] B5c. Update `api/governance_router.py:202` — unwrap
- [ ] B5d. Update `tests/test_subject_access.py` lines 442, 455, 471, 491, 539, 543

**B.6 — `get_request_status()` (line 704)**
- [ ] B6a. Wrap success return in `DataResult.ok(request_or_none)`
- [ ] B6b. Wrap failure path in `DataResult.fail(str(e))`
- [ ] B6c. Update `api/governance_router.py:84` — unwrap, check `.data is None` for 404
- [ ] B6d. Update `tests/test_subject_access.py` lines 227, 237

**B.7 — `list_requests()` (line 733)**
- [ ] B7a. Wrap success return in `DataResult.ok(requests_list)`
- [ ] B7b. Wrap failure path in `DataResult.fail(str(e))`
- [ ] B7c. Update `api/governance_router.py:114` — unwrap, iterate `result.data`
- [ ] B7d. Update `api/intelligence_router.py:1440` — unwrap, `len(result.data)`
- [ ] B7e. Update `tests/test_subject_access.py` lines 247, 258

**B.8 — Verification**
- [ ] B8a. ruff check `lib/governance/subject_access.py`
- [ ] B8b. ruff check `api/governance_router.py`
- [ ] B8c. ruff check `api/intelligence_router.py`
- [ ] B8d. Run `pytest tests/test_subject_access.py -x -q` — all pass
- [ ] B8e. Verify `DataResult` import resolves correctly

### C. Wrap 3 API endpoints with try/except

- [ ] C1. `server.py:3218` GET `/api/sync/status` — wrap `collectors.get_status()`
- [ ] C2. `server.py:3224` POST `/api/sync` — wrap `collectors.force_sync()`
- [ ] C3. `server.py:3246` GET `/api/status` — wrap dict construction with `collectors.get_status()`
- [ ] C4. ruff check `api/server.py`
- [ ] C5. Verify the `raise HTTPException(...)` is caught by global handler at server.py:129-154

### D. Final verification

- [ ] D1. ruff check on all 6 modified files
- [ ] D2. bandit on all 6 modified files
- [ ] D3. AST parse check on all 6 modified files
- [ ] D4. `pytest tests/test_subject_access.py -v` — all pass
- [ ] D5. Full test suite — no new failures beyond existing 444
- [ ] D6. git add, commit, push, create PR
