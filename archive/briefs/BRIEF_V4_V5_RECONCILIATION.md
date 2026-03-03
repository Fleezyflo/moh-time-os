# Brief 29: V4/V5 Architecture Reconciliation
> **Status:** DESIGNED | **Priority:** P2 | **Prefix:** VR

## Problem

Three intelligence implementations coexist in the codebase:
- `lib/intelligence/` — the ACTIVE layer (13,761 lines, 18 files, fully wired into daemon)
- `lib/v4/` — artifact-centric proposal system, dormant
- `lib/v5/` — next-iteration skeleton, mostly stubs

This creates confusion for any agent working in the codebase, risks import collisions, and inflates the surface area of code to maintain. IE-5.1 described consolidation but it was one task inside Brief 11 whose other tasks are already done.

## Dependencies

- **Requires:** Nothing (can run in parallel with any other work)
- **Unblocks:** Cleaner codebase for all future briefs

## Scope

1. Audit what's in v4/ and v5/ that isn't in lib/intelligence/
2. Migrate any unique functionality
3. Archive the rest
4. Update all imports and consumers
5. Delete dead code

## Tasks

| Task | Title | Est. Lines |
|------|-------|------------|
| VR-1.1 | V4/V5 Functionality Audit | Research only |
| VR-2.1 | Migrate Unique Functionality | ~200 (varies) |
| VR-3.1 | Consumer Update & Import Cleanup | ~100 |
| VR-4.1 | Archive & Delete | ~50 (deletion) |
| VR-5.1 | Reconciliation Validation | ~200 |

## Estimated Effort

Small-medium. Mostly research and deletion. New code only where v4/v5 has unique functionality not in lib/intelligence/.

## Success Criteria

- lib/v4/ and lib/v5/ removed from active codebase (moved to docs/archive/ or deleted)
- No import references to lib.v4 or lib.v5 remain
- Any unique functionality preserved in lib/intelligence/
- All tests pass after cleanup
- Codebase surface area reduced
