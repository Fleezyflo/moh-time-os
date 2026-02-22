# TASK: Seed Commitments from Existing Communications
> Brief: USER_READINESS | Phase: 2 | Sequence: 2.3 | Status: PENDING

## Context

The commitment_truth module has a Detector that extracts commitments from communications, but it may have never run on the live dataset. The `commitments` table exists (schema verified in Brief 7 investigation) but may be empty or sparsely populated.

The commitment extractor (`lib/commitment_extractor.py`) and the truth module detector (`lib/commitment_truth/detector.py`) both have extraction logic. Need to determine which is canonical and run it.

## Objective

Ensure the commitments table has real data extracted from communications, so the commitment truth module produces meaningful output.

## Instructions

1. Check current commitments state:
   ```sql
   SELECT COUNT(*) FROM commitments;
   SELECT status, COUNT(*) FROM commitments GROUP BY status;
   ```

2. If commitments exist, verify they're meaningful (not test data):
   ```sql
   SELECT commitment_text, due_at, status FROM commitments LIMIT 10;
   ```

3. Read both extractors to determine which to use:
   - `lib/commitment_extractor.py` — pipeline-level extractor
   - `lib/commitment_truth/detector.py` — truth module detector
   Choose the one that works with current schema.

4. Run extraction on communications that have text:
   ```python
   # Approach depends on which extractor is used
   from lib.commitment_truth.detector import CommitmentDetector
   d = CommitmentDetector(db_path="data/moh_time_os.db")
   result = d.detect_from_recent(days=90)
   ```

5. If the detector needs `client_id` on communications (populated by Brief 7 PH-3.2), verify it exists.

6. Verify commitments are populated:
   ```sql
   SELECT COUNT(*) FROM commitments;
   SELECT status, COUNT(*) FROM commitments GROUP BY status;
   ```

7. Test CommitmentManager can read them:
   ```python
   from lib.commitment_truth.commitment_manager import CommitmentManager
   cm = CommitmentManager(db_path="data/moh_time_os.db")
   overdue = cm.get_overdue()
   print(f"Overdue commitments: {len(overdue)}")
   ```

## Preconditions
- [ ] UR-2.1 complete (truth cycle wired)
- [ ] Brief 7 PH-1.2 complete (communications.client_id exists)

## Validation
1. `commitments` count > 0
2. At least some commitments have status, due_at, commitment_text
3. CommitmentManager.get_overdue() returns without error
4. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] Commitments seeded from communications
- [ ] CommitmentManager functions return real data
- [ ] No test regressions

## Output
- Modified: live DB (commitments populated)
- Possibly modified: detector if schema adaptation needed
