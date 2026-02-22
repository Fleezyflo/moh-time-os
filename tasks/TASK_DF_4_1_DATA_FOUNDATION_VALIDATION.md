# TASK: Data Foundation End-to-End Validation
> Brief: DATA_FOUNDATION | Phase: 4 | Sequence: 4.1 | Status: PENDING

## Context

This is the final validation task for the Data Foundation brief. All prior tasks (DF-1.1 through DF-3.3) should be complete. This task verifies that the combined effect of all fixes produces a system where the DIRECTIVE's core questions are answerable.

The DIRECTIVE says: "If this system requires Moh to go looking for insight, it has failed."

This task validates that the data foundation is solid enough for the intelligence layer to work.

## Objective

Run a comprehensive validation suite that proves the data foundation supports the system's intelligence requirements.

## Instructions

1. Create `scripts/validate_data_foundation.py`:
   - **Client coverage:**
     - Assert: >= 90% of clients with revenue have a tier assigned
     - Assert: `lifetime_revenue` populated for all clients with invoices
     - Print: tier distribution (A/B/C/NULL)
   - **Task integrity:**
     - Assert: >= 50% of Asana tasks have `project_id` linked
     - Assert: completed tasks have `completed_at` populated
     - Assert: `status` distribution includes 'completed' tasks
     - Print: task status distribution, link rate
   - **Entity link quality:**
     - Assert: proposed links < 30% of total (most should be confirmed)
     - Assert: avg confidence of confirmed links > 0.8
     - Print: link status distribution, method distribution
   - **Signal health:**
     - Assert: critical signals < 20% of active total
     - Assert: at least 3 severity levels used across active signals
     - Print: severity distribution
   - **Engagement coverage:**
     - Assert: engagements table has > 0 rows
     - Assert: projects reference engagements
     - Print: engagement type distribution
   - **Collector freshness:**
     - Assert: all enabled collectors ran within their scheduled interval
     - Print: last sync time per collector
   - **Capacity lanes:**
     - Assert: capacity_lanes has > 0 rows
     - Assert: at least 1 lane has tasks assigned
     - Print: lane load summary
   - **Cross-entity queries (smoke test):**
     - Query `v_client_operational_profile` — returns rows with non-null data
     - Query `v_project_operational_state` — returns rows with task counts > 0
     - Query `v_person_load_profile` — returns rows with assigned tasks

2. Output: print a structured report with PASS/FAIL per check and a summary score.
3. Run the validation against the live database.
4. Run: `pytest tests/ -q` (ensure no test regressions from the full brief)

## Preconditions
- [ ] All prior tasks (DF-1.1 through DF-3.3) complete
- [ ] Test suite passing

## Validation
1. `python scripts/validate_data_foundation.py` exits 0 with all checks passing
2. `pytest tests/ -q` all pass
3. No guardrail violations in any changes from the full brief

## Acceptance Criteria
- [ ] Validation script covers all 7 domains (clients, tasks, links, signals, engagements, collectors, lanes)
- [ ] Cross-entity views return meaningful data
- [ ] All assertions pass (or failures are documented with reasons)
- [ ] Full test suite passes
- [ ] HEARTBEAT updated with final brief status

## Output
- New: `scripts/validate_data_foundation.py`
- Updated: HEARTBEAT.md (brief completion)

## On Completion
- Update HEARTBEAT:
  - Mark Brief DATA_FOUNDATION as COMPLETE
  - Record final system state (table counts, test count, validation score)
  - Clear Current Task
  - Set Active Work to awaiting next brief
- Commit all changes on branch `brief/data-foundation`

## On Failure
- If specific validations fail, document which and why in HEARTBEAT → Blocked
- Do not mark brief as complete unless all critical assertions pass
- Non-critical failures can be documented as known issues
