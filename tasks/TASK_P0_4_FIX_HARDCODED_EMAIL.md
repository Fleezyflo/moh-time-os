# TASK: Fix hardcoded email in chat collector
> Brief: AUDIT_REMEDIATION | Priority: P0 | Sequence: P0.4 | Status: PENDING

## Context

`lib/collectors/chat.py:31` has `DEFAULT_USER = "molham@hrmny.co"` hardcoded without an environment variable wrapper. This should use `os.environ.get()` for portability and to avoid leaking PII in source.

## Objective

Wrap the hardcoded email in an environment variable lookup with the current value as fallback.

## Instructions

1. Open `lib/collectors/chat.py`
2. Add `import os` if not already present
3. Line 31: Change:
   ```python
   DEFAULT_USER = "molham@hrmny.co"
   ```
   To:
   ```python
   DEFAULT_USER = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")
   ```

4. Grep for other hardcoded emails:
   ```
   grep -rn 'molham@hrmny.co' lib/ api/ engine/
   ```
   If any appear without env var wrappers, fix them too.

## Preconditions
- [ ] None

## Validation
1. `grep -rn 'molham@hrmny.co' lib/collectors/chat.py` — only appears as fallback default in `os.environ.get()`
2. `ruff check lib/collectors/chat.py` — clean
3. `bandit -r lib/collectors/chat.py` — clean

## Acceptance Criteria
- [ ] `DEFAULT_USER` uses `os.environ.get("MOH_ADMIN_EMAIL", ...)`
- [ ] No bare hardcoded emails outside fallback defaults
- [ ] ruff, bandit clean

## Output
- Modified: `lib/collectors/chat.py`

## Estimate
5 minutes
