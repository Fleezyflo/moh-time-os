# VR-3.1: Consumer Update & Import Cleanup

## Objective

Update all files that import from lib.v4 or lib.v5 to use lib.intelligence or lib.* equivalents. After this task, zero imports reference v4/v5.

## Dependencies

- VR-2.1 (migrated functionality must exist at new locations)

## Approach

1. Run import grep (from VR-1.1 audit)
2. For each consumer file, update imports to new location
3. Run tests after each file to catch breakage immediately
4. Verify no remaining v4/v5 references

## Validation

```bash
grep -r "from lib\.v4" --include="*.py" | grep -v __pycache__  # should return nothing
grep -r "from lib\.v5" --include="*.py" | grep -v __pycache__  # should return nothing
grep -r "lib/v4" --include="*.py" | grep -v __pycache__        # should return nothing
grep -r "lib/v5" --include="*.py" | grep -v __pycache__        # should return nothing
```

- All tests pass
- No import errors at runtime

## Estimated Effort

~100 lines of changes (varies based on consumer count)
