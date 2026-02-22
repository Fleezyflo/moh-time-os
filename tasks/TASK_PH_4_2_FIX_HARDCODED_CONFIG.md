# TASK: Extract Hardcoded Values to Config
> Brief: PIPELINE_HARDENING | Phase: 4 | Sequence: 4.2 | Status: PENDING

## Context

8+ files contain hardcoded values that should be in config:
- Email addresses (`molham@hrmny.co`) hardcoded in collectors
- macOS file paths hardcoded in data paths
- Silent `except Exception: pass` blocks hiding errors (2 files)
- `return {}` / `return []` on failure hiding errors as "no data" (15+ instances)

These violate CLAUDE.md rules:
- "No hardcoded values where config/env vars should be"
- "No `except Exception: pass`"
- "No `return {}` or `return []` on failure"

## Objective

Extract hardcoded values, fix silent error suppression, and fix empty-return-on-failure patterns.

## Instructions

### Part A: Hardcoded Config Values

1. Find all hardcoded emails:
   ```bash
   grep -rn "molham@\|hrmny\.co\|@gmail\.com" lib/ --include="*.py"
   ```

2. For each, move to `lib/config.py` or environment variable:
   ```python
   # In lib/config.py:
   import os
   ADMIN_EMAIL = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")
   ```

3. Find hardcoded paths:
   ```bash
   grep -rn "/Users/\|/home/\|C:\\\\" lib/ --include="*.py"
   ```
   Replace with `lib/paths.py` references (which already exists).

### Part B: Silent Error Suppression

1. Find bare except blocks:
   ```bash
   grep -rn "except.*:\s*$" lib/ --include="*.py" -A1 | grep -B1 "pass"
   grep -rn "except Exception" lib/ --include="*.py"
   ```

2. Replace `except Exception: pass` with proper logging:
   ```python
   # BEFORE:
   except Exception:
       pass

   # AFTER:
   except Exception:
       logger.warning("Failed to process %s: %s", item_id, e, exc_info=True)
   ```

### Part C: Empty Return on Failure

1. Find empty dict/list returns:
   ```bash
   grep -rn "return {}\|return \[\]" lib/ --include="*.py"
   ```

2. Evaluate each: if it's a "no results" return (legitimate), leave it. If it's in an except block or error path, replace with:
   ```python
   # Option 1: Raise
   raise

   # Option 2: Return typed error
   logger.error("Failed to fetch %s", resource)
   return {"error": str(e), "data": []}
   ```

3. Be conservative — only fix cases that clearly mask errors.

## Preconditions
- [ ] PH-4.1 complete (f-string SQL fixed — avoids merge conflicts)

## Validation
1. `grep -rn "except.*pass" lib/ --include="*.py"` returns empty (or documented exceptions)
2. No hardcoded email addresses in lib/ (all in config)
3. `pytest tests/ -q` — no regressions
4. Spot-check: trigger an error condition and verify it's logged

## Acceptance Criteria
- [ ] Hardcoded emails/paths extracted to config
- [ ] Silent exception suppression eliminated
- [ ] Error-masking empty returns replaced with logged errors
- [ ] No test regressions

## Output
- Modified: 8-15 source files
- Modified or created: `lib/config.py` (centralized config)
