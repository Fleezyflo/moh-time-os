# TASK: Remove Tier Gating System
> Brief: USER_READINESS | Phase: 1 | Sequence: 1.1 | Status: PENDING

## Context

The tier gating system (Tiers 0-4) in `config/feature_flags.yaml` defines unlock criteria ("7 stable days") that nothing tracks. It adds complexity with zero value. Every reference must be removed.

## Objective

Complete removal of all tier gating logic and the feature_flags.yaml config. The generic feature flag system (`lib/features/`) is NOT about tiers and stays.

## Files to DELETE (entire file)

| File | Lines | Reason |
|------|-------|--------|
| `config/feature_flags.yaml` | 60 | Tier 0-4 gating config — sole purpose is tier unlock criteria |
| `lib/client_truth/tier_calculator.py` | 199 | Revenue-based tier assignment (A/B/C) — already computed in client tiers during DF-1.3 |
| `tests/test_tier_calculator.py` | 211 | Tests for the above |

## Files for SURGICAL REMOVAL

| File | What to Remove |
|------|---------------|
| `lib/time_truth/__init__.py` | Line 2: Remove "(Tier 0)" from docstring |
| `lib/time_truth/scheduler.py` | Line 4: Remove "Tier 0" from comment |
| `lib/time_truth/block_manager.py` | Line 2: Remove "Tier 0" from comment |
| `lib/commitment_truth/__init__.py` | Lines 2, 7: Remove "Tier 1" references |
| `lib/capacity_truth/__init__.py` | Lines 2, 7: Remove "Tier 2" references |
| `lib/client_truth/__init__.py` | Lines 2, 7-9: Remove "Tier 3" references and tier dependency comments |
| `lib/autonomous_loop.py` | Lines 242, 250, 258, 266, 406, 471, 532, 648: Remove tier number references in phase comments |

## Instructions

1. Delete the 3 files listed above
2. For each surgical removal file, find and remove/rewrite tier references
3. Check `lib/client_truth/__init__.py` imports — if it exports `tier_calculator`, remove that export
4. Grep to verify zero remaining references:
   ```bash
   grep -rn "Tier [0-4]\|tier_gate\|tier_lock\|feature_flags\.yaml\|tier_calculator" lib/ config/ tests/ --include="*.py" --include="*.yaml"
   ```
5. Run test suite

## Preconditions
- [ ] Brief 7 complete

## Validation
1. `grep -rn "feature_flags.yaml" .` returns empty
2. `grep -rn "tier_calculator" lib/ tests/` returns empty
3. `grep -rn "Tier [0-4]" lib/` returns empty (or only in unrelated contexts like "Tier A/B/C" client segments)
4. `python3 -c "import lib.client_truth"` succeeds
5. `pytest tests/ -q` — passes, count may drop by ~10 (test_tier_calculator.py removed)

## Acceptance Criteria
- [ ] feature_flags.yaml deleted
- [ ] tier_calculator.py deleted
- [ ] test_tier_calculator.py deleted
- [ ] All tier references removed from comments/docstrings
- [ ] No import errors
- [ ] Test suite passes

## Output
- Deleted: 3 files (~470 lines)
- Modified: 7 files (comment/docstring updates)
