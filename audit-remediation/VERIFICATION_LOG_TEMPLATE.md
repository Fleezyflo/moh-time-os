# Verification Log — [Branch Name]

**Session:** [number]
**Date:** [YYYY-MM-DD]
**Agent:** [session ID or identifier]

---

## Pre-Edit Verification

For EVERY method call you add or modify, fill in one row. If any cell is "no" or blank, you cannot commit.

| File edited | Method called | Defined at (file:line) | Signature confirmed | Return type matches usage | Callers checked |
|-------------|--------------|----------------------|--------------------|--------------------------|-----------------|
| | | | | | |

## Pre-Commit Verification

| Check | Result | Output snippet |
|-------|--------|---------------|
| `ruff check` on changed files | | |
| `ruff format --check` on changed files | | |
| `bandit -r` on changed files | | |
| `pytest` (Molham's Mac) | | |
| Every method call in changed files resolves to a real `def` | | |
| Verification log included in `git add` | | |

## PR Scope Check

| Planned PR | Files in this commit | Matches plan? |
|-----------|---------------------|--------------|
| | | |

If this commit contains files from more than one planned PR: **STOP. Split the commit.**

---

## How to use this template

1. Copy this file to `audit-remediation/VERIFICATION_LOG_S[session].md` at session start
2. Fill in the Pre-Edit table BEFORE writing each edit (not after)
3. Fill in the Pre-Commit table AFTER all edits, BEFORE giving commit commands
4. Include the filled log in `git add` with every commit
5. The next session reviews the previous log for completeness
