# Prompt 23: Coupling Strength Thresholds Inconsistent

    **Source section:** 4.4 (from `DEFECT_MANIFEST.md`)

    ## Objective
    Implement the missing or incorrect behavior described in section **4.4**, and remove any stub/placeholder logic related to it.

    ## Constraints
    - Prefer minimal, local changes over wide refactors.
    - If a refactor is required, isolate it behind a small interface and document the decision in `logs/DECISIONS.md`.
    - Keep UI behavior consistent with existing intent; do not redesign.

    ## Manifest excerpt
    - **File:** `router.tsx` line 938
- **Code:** `.filter(c => c.strength > 0.5)`
- **vs.** Other places use `>= 0.60`, `>= 0.80`
- **Issue:** Different strength thresholds across the UI
- **Severity:** LOW

    ## Required deliverables
    1. Working implementation that satisfies the section’s stated behavior.
    2. Removal of fake handlers / TODO stubs / decorative UI for this section.
    3. Errors handled (UI + API) with user-safe messaging (no silent failures).
    4. Update `logs/RUN_LOG.md` with executed commands and outcomes.
    5. Update `logs/DECISIONS.md` with any tradeoffs.

    ## Execution steps
    1. Locate the referenced files/components via search.
    2. Identify the **current state** (what is stubbed, what is missing).
    3. Implement the behavior end-to-end (UI -> API call -> state refresh).
    4. Verify no stale-data regressions: after mutation, UI must update deterministically.
    5. Add/repair tests where feasible; otherwise add a manual verification checklist entry.

    ## Acceptance criteria
    - The feature works in the running app (dev server) with real data.
    - No console errors.
    - No dead UI controls related to this section.

    ## Manual verification
    - Start backend + frontend.
    - Navigate to the relevant page(s).
    - Trigger the action(s) described in the manifest and confirm UI updates immediately.
