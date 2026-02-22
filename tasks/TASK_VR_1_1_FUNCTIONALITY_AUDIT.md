# VR-1.1: V4/V5 Functionality Audit

## Objective

Determine exactly what's in lib/v4/ and lib/v5/, what's unique (not replicated in lib/intelligence/), and what can be safely removed.

## Deliverables

### Audit report: `docs/audits/v4_v5_reconciliation.md`

For each file in lib/v4/ and lib/v5/:

1. **File path and size** (lines)
2. **What it does** (1-2 sentences)
3. **Equivalent in lib/intelligence/** (if any) — file path and what covers the same functionality
4. **Unique functionality** (if any) — what this file does that lib/intelligence/ does NOT
5. **Import consumers** — who imports from this file? (grep for `from lib.v4` and `from lib.v5`)
6. **Decision:** MIGRATE (unique), ARCHIVE (reference only), DELETE (dead code)

### Import graph

```bash
# Run this to find all consumers
grep -r "from lib\.v4" --include="*.py" | grep -v __pycache__
grep -r "from lib\.v5" --include="*.py" | grep -v __pycache__
grep -r "import lib\.v4" --include="*.py" | grep -v __pycache__
grep -r "import lib\.v5" --include="*.py" | grep -v __pycache__
```

### Known v4 components (from earlier exploration)

- `lib/v4/orchestrator.py` — may have unique orchestration logic
- `lib/v4/signal_service.py` — signal management (likely duplicated)
- `lib/v4/policy_service.py` — policy evaluation (check if unique)
- `lib/v4/proposal_service.py` — proposal generation (likely duplicated)
- `lib/v4/detectors/` — individual signal detectors

### Known v5 components

- `lib/v5/api/` — API layer (check overlap with spec_router.py)
- `lib/v5/models/` — data models
- `lib/v5/database.py` — DB layer
- `lib/v5/migrations/` — may have unique tables
- `lib/v5/detectors/` — signal detectors
- `lib/v5/issues/` — issue management

## Validation

- Every file in v4/ and v5/ accounted for
- Every import consumer identified
- Clear MIGRATE/ARCHIVE/DELETE decision for each file
- Unique functionality documented with enough detail for VR-2.1 to migrate

## Estimated Effort

Research only — no code changes. 2-3 hours of reading.
