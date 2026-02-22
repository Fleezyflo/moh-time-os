# TASK: Auto-Confirm High-Confidence Entity Links
> Brief: DATA_FOUNDATION | Phase: 2 | Sequence: 2.2 | Status: PENDING

## Context

The `entity_links` table has 30,129 rows. 16,063 (53%) are in `proposed` status, 14,066 are `confirmed`. Proposed links propagate uncertainty through every downstream query — client communication profiles, project task counts, person load calculations all include unvalidated associations.

Link methods: naming=16,760, headers=12,943, rules=328, participants=98.
Link targets: client=12,985, person=9,722, task=4,481, thread=2,318, project=623.

Each link has a `confidence` score (0.0 to 1.0). High-confidence proposed links are almost certainly correct but haven't been bulk-confirmed.

## Objective

Create a batch confirmation process that auto-confirms entity links above a confidence threshold and flags low-confidence ones for manual review.

## Instructions

1. Read `lib/` for any existing entity link management code. Check `engine/store.py` for link-related functions.
2. Create `lib/entity_link_confirmer.py` with:
   - `auto_confirm_links(db_path, confidence_threshold=0.85)`:
     - UPDATE entity_links SET status='confirmed', confirmed_by='auto_confirmer', confirmed_at=now WHERE status='proposed' AND confidence >= threshold
     - Return count of confirmed links
   - `flag_low_confidence_links(db_path, threshold=0.5)`:
     - SELECT links where confidence < threshold for manual review
     - Return list of questionable links with artifact context
   - `link_confirmation_report(db_path)`:
     - Return summary: confirmed count, proposed count, rejected count, avg confidence by method
3. Add CLI command: `timeos confirm-links [--threshold 0.85] [--dry-run]`
4. Write tests:
   - Test that only links above threshold are confirmed
   - Test idempotency (running twice doesn't break anything)
   - Test dry-run mode
5. Run: `pytest tests/ -q`

## Preconditions
- [ ] Test suite passing
- [ ] `entity_links` table has proposed rows

## Validation
1. After running: proposed link count decreases, confirmed count increases
2. No link with confidence < threshold was auto-confirmed
3. All tests pass

## Acceptance Criteria
- [ ] Auto-confirmation function works with configurable threshold
- [ ] Low-confidence links are identified but not auto-confirmed
- [ ] Report function shows link status distribution
- [ ] CLI command with dry-run option
- [ ] All tests pass
- [ ] No guardrail violations

## Output
- New: `lib/entity_link_confirmer.py`
- New: `tests/test_entity_link_confirmer.py`
- Modified: CLI file (add `confirm-links` command)

## On Completion
- Update HEARTBEAT: Task DF-2.2 complete — N links auto-confirmed, M flagged for review
- Record: entity_links status distribution change

## On Failure
- If existing code manages link status elsewhere, document the conflict in Blocked
