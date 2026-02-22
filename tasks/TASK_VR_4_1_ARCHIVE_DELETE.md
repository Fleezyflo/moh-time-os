# VR-4.1: Archive & Delete

## Objective

Remove lib/v4/ and lib/v5/ from the active codebase. Archive if there's reference value, delete if truly dead.

## Dependencies

- VR-3.1 (all consumers updated, no imports remain)

## Approach

1. Move lib/v4/ and lib/v5/ to docs/archive/v4/ and docs/archive/v5/
2. Or `git rm -r lib/v4/ lib/v5/` if no reference value
3. Include deletion rationale in commit body (per CLAUDE.md: "Deletion rationale:" when removing 20+ lines)

## Validation

- lib/v4/ and lib/v5/ no longer exist in working tree
- All tests pass
- No import errors
- Git history preserves the code for future reference

## Estimated Effort

~50 lines of commands. Small.
