# TASK: End-to-End Pipeline Validation
> Brief: PIPELINE_HARDENING | Phase: 5 | Sequence: 5.1 | Status: PENDING

## Context

After PH-1.1 through PH-4.2, all schema misalignments should be resolved, missing tables created, data populated, and code quality issues fixed. This task validates the full pipeline runs without error.

The pipeline cycle is:
1. **Collect** — sync data from sources (Asana, Gmail, Calendar, Chat, Xero)
2. **Normalize** — derive brand_id, client links, communication domains
3. **Commitment Extraction** — parse commitments from communications
4. **Lane Assignment** — assign tasks to capacity lanes
5. **Gates** — validate data quality gates (brand_id, client links, etc.)
6. **Resolution Queue** — surface items needing manual intervention

## Objective

Run each pipeline stage on live data. Zero crashes. Document results.

## Instructions

1. Test each stage individually:

   ```python
   # Stage 1: Normalize
   from lib.normalizer import Normalizer
   n = Normalizer()
   result = n.normalize_tasks()
   print(f"Tasks normalized: {result}")
   result = n.link_communications()
   print(f"Communications linked: {result}")
   ```

   ```python
   # Stage 2: Commitment Extraction
   from lib.commitment_extractor import CommitmentExtractor
   ce = CommitmentExtractor()
   result = ce.extract_all()
   print(f"Commitments extracted: {result}")
   ```

   ```python
   # Stage 3: Lane Assignment
   from lib.lane_assigner import LaneAssigner
   la = LaneAssigner()
   result = la.assign_all()
   print(f"Lanes assigned: {result}")
   ```

   ```python
   # Stage 4: Gates
   from lib.gates import GateChecker
   gc = GateChecker()
   result = gc.check_all()
   print(f"Gates: {result}")
   ```

   ```python
   # Stage 5: Resolution Queue
   from lib.resolution_queue import ResolutionQueue
   rq = ResolutionQueue()
   result = rq.scan()
   print(f"Resolution items: {result}")
   ```

2. For each stage that fails:
   - Document the exact error (traceback, file, line)
   - Apply minimal fix (schema, import, or column name — not logic change)
   - Re-test

3. Run the full pipeline in sequence if a pipeline orchestrator exists, or chain them manually.

4. Create `scripts/validate_pipeline.py` that runs all stages and reports pass/fail.

5. Run `pytest tests/ -q` to confirm no regressions.

6. Record final counts:
   ```
   Tasks normalized: X
   Communications linked: Y
   Commitments extracted: Z
   Lanes assigned: W
   Gates: X passed / Y failed
   Resolution items: Z
   ```

## Preconditions
- [ ] PH-1.1 through PH-4.2 all complete

## Validation
1. All 5 pipeline stages run without unhandled exceptions
2. `scripts/validate_pipeline.py` exits 0
3. `pytest tests/ -q` — all pass, 0 failures, 0 errors
4. Total passing tests documented

## Acceptance Criteria
- [ ] Normalizer runs (tasks + communications)
- [ ] Commitment extraction runs
- [ ] Lane assigner runs
- [ ] Gates checker runs (may still flag data gaps — that's OK, no crash)
- [ ] Resolution queue scans without error
- [ ] Pipeline validation script created
- [ ] Full test suite passes
- [ ] Final metrics documented

## On Completion
- Update HEARTBEAT:
  - Mark Brief PIPELINE_HARDENING as COMPLETE
  - Update System State with pipeline status
  - Record: "6 pipeline blockers → 0"
  - Set Active Work to awaiting next brief
- Commit all changes

## On Failure
- If specific stages still crash, document which and why in HEARTBEAT → Blocked
- Remaining crashes must be traced to a root cause with a plan
- Do not mark brief complete with any pipeline crashes

## Output
- Created: `scripts/validate_pipeline.py`
- Possibly modified: additional source files (if stragglers found)
- Updated: HEARTBEAT.md (brief completion)
