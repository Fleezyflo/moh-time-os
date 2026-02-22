# VR-2.1: Migrate Unique Functionality

## Objective

Move any functionality identified as MIGRATE in VR-1.1 into lib/intelligence/ or appropriate lib/ modules. Adapt to existing patterns.

## Dependencies

- VR-1.1 (audit determines what to migrate)

## Approach

For each MIGRATE item from the audit:

1. Identify the closest existing module in lib/intelligence/ or lib/
2. Adapt the code to use existing patterns (QueryEngine for reads, sqlite3 for writes, etc.)
3. Write tests for the migrated functionality
4. Update all consumers to import from the new location

## Likely Migration Candidates

Based on the v4/v5 structure, these are plausible unique features:

- **Policy service** (v4) — if it has policy evaluation logic not in governance.py
- **Issue lifecycle** (v5) — if it has issue state machine not in resolution_queue.py
- **Tagging system** (v4) — artifact tagging may not exist in lib/intelligence/

For each: adapt or subsume into existing modules. No new standalone modules unless genuinely orthogonal.

## Validation

- Migrated functionality has tests
- All consumers updated to new import paths
- No functionality lost (compare outputs before/after for same inputs)

## Estimated Effort

~200 lines (varies based on VR-1.1 findings). Could be less if v4/v5 is mostly duplicated.
