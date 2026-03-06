# TASK: Audit return {}/[] error-masking patterns
> Brief: AUDIT_REMEDIATION | Priority: P2 | Sequence: P2.1 | Status: PENDING

## Context

102 instances of `return {}` or `return []` exist in the codebase. Many are legitimate (empty results when no data found), but some mask errors by returning "no data" from `except` blocks instead of raising or logging. Error-masking hides failures as "no data" and makes debugging nearly impossible.

## Objective

Audit every `return {}` and `return []` instance. Fix those that mask errors. Leave legitimate empty returns alone.

## Instructions

### 1. Find all instances

```bash
grep -rn "return {}" lib/ api/ engine/ --include="*.py"
grep -rn "return \[\]" lib/ api/ engine/ --include="*.py"
```

### 2. Classify each instance

For each occurrence, check the surrounding context:

**ERROR-MASKING (fix these):**
- Inside an `except` block → masking an error
- In a function that should raise on failure → hiding failure
- After a failed condition check where the failure should be logged

**LEGITIMATE (leave these):**
- Default return when no data matches a query (e.g., "no clients found")
- Initial value for an accumulator
- Explicit "empty result" that the caller expects and handles

### 3. Fix error-masking instances

Replace with one of:
- `logging.error(f"...: {e}")` + `return {}` (at minimum, LOG the error)
- `raise` (if the caller should handle it)
- Return a typed error result (e.g., `{"error": str(e), "data": []}`)

### 4. Never use `except: pass` or `except Exception: pass`

If any are found during audit, fix them too (CLAUDE.md code rules).

## Preconditions
- [ ] None

## Validation
1. Zero `return {}` / `return []` in `except` blocks without logging
2. `ruff check` clean on all modified files
3. `bandit -r` clean on all modified files
4. `python -m pytest tests/ -x` passes

## Acceptance Criteria
- [ ] Every `return {}` / `return []` in an except block has `logging.error()` or `logging.warning()` before it
- [ ] No `except: pass` or `except Exception: pass` anywhere
- [ ] ruff, bandit clean

## Output
- Modified: multiple files across lib/, api/, engine/

## Estimate
3 hours (102 instances, need judgment per instance)

## Branch
`fix/error-masking-returns`
