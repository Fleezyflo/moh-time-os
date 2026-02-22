# TASK: Fix StrEnum Imports for Python 3.10 Compatibility
> Brief: TEST_REMEDIATION | Phase: 1 | Sequence: 1.2 | Status: PENDING

## Context

`enum.StrEnum` was introduced in Python 3.11. Our environment runs Python 3.10.12. 16 source files use `from enum import StrEnum`, causing ImportError for tests that import `lib.agency_snapshot`, `lib.ui_spec_v21`, `lib.v5.models`, or `lib.change_bundles`.

The standard Python 3.10 backport pattern is:
```python
class StrEnum(str, Enum):
    pass
```

This is functionally identical to the 3.11 `StrEnum`.

## Objective

Replace all `from enum import StrEnum` with a 3.10-compatible definition across the entire codebase.

## Instructions

1. Add `StrEnum` to the compatibility shim at `lib/compat.py` (created in TR-1.1):
   ```python
   import sys
   if sys.version_info >= (3, 11):
       from enum import StrEnum
   else:
       from enum import Enum
       class StrEnum(str, Enum):
           pass
   ```

2. Replace `from enum import StrEnum` in all 16 files with `from lib.compat import StrEnum`:

   **Files (16 total):**
   - `lib/v5/models/issue.py`
   - `lib/v5/models/xero.py`
   - `lib/v5/models/calendar.py`
   - `lib/v5/models/base.py`
   - `lib/v5/models/gchat.py`
   - `lib/status_engine.py`
   - `lib/conflicts.py`
   - `lib/change_bundles.py`
   - `lib/agency_snapshot/comms_commitments_page11.py`
   - `lib/agency_snapshot/client360_page10.py`
   - `lib/agency_snapshot/cash_ar_page12.py`
   - `lib/agency_snapshot/client360.py`
   - `lib/agency_snapshot/capacity_command_page7.py`
   - `lib/ui_spec_v21/detectors.py`
   - `lib/ui_spec_v21/issue_lifecycle.py`
   - `lib/ui_spec_v21/inbox_lifecycle.py`

3. Verify the backport works:
   ```python
   from lib.compat import StrEnum
   class Color(StrEnum):
       RED = "red"
       BLUE = "blue"
   assert Color.RED == "red"
   assert isinstance(Color.RED, str)
   ```

## Preconditions
- [ ] TR-1.1 complete (compat.py exists)

## Validation
1. `grep -r "from enum import StrEnum" lib/` returns empty
2. `python -c "import lib.agency_snapshot"` succeeds (was blocked by StrEnum)
3. `python -c "import lib.ui_spec_v21"` succeeds (was blocked by StrEnum)
4. `python -c "import lib.v5.models.base"` succeeds (was blocked by StrEnum)
5. `pytest tests/test_cash_ar.py tests/test_comms_commitments.py -q --co` — collection succeeds
6. `pytest tests/ -q` — collection errors reduced by ≥4

## Tests Unblocked by This Fix
- tests/test_cash_ar.py (was error → should now collect)
- tests/test_comms_commitments.py (was error → should now collect)
- tests/test_inbox_enrichment.py (5 failures → should pass)
- tests/test_inbox_evidence_persistence.py (10 failures → should pass)

## Acceptance Criteria
- [ ] Zero files contain `from enum import StrEnum`
- [ ] All 16 files import from `lib.compat` or use inline backport
- [ ] StrEnum subclasses behave identically (instances are strings, comparable)
- [ ] 15+ previously-failing tests now pass

## Output
- Modified: 16 source files
- Modified: `lib/compat.py` (add StrEnum)
