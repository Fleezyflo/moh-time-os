# TASK: Replace Minimal Builders with Full Implementations
> Brief: USER_READINESS | Phase: 3 | Sequence: 3.1 | Status: PENDING

## Context

The Agency Snapshot Generator (`lib/agency_snapshot/generator.py`) uses "minimal builders" for pages 0, 1, 7, 10, 11, 12 — these are stub implementations that return skeleton data. The generator has comment documentation noting these are "pending full schema fixes."

After Brief 7 (Pipeline Hardening), the schema is aligned. These minimal builders can now be replaced with full data-driven implementations.

## Objective

Replace each minimal builder with a full implementation that queries live data and populates the snapshot section completely.

## Instructions

1. Identify all minimal builders in generator.py:
   ```bash
   grep -n "minimal\|_build_minimal\|stub\|placeholder\|pending" lib/agency_snapshot/generator.py
   ```

2. For each minimal builder, determine:
   - What data the section needs (per the AgencySnapshotContract schema in `lib/contracts/schema.py`)
   - What tables/views provide that data
   - What the full page engine already computes (e.g., delivery.py, client360.py, cash_ar.py, comms_commitments.py already have full engines)

3. For pages that have full engines (pages 2-6, 8-9):
   - Verify the engine is already wired into the generator
   - If not, wire it

4. For pages with minimal builders (0, 1, 7, 10, 11, 12):
   - Page 0 (Overview): Aggregate from all other pages — top-level metrics
   - Page 1 (Delivery Command): `delivery.py` engine exists — verify it's wired
   - Page 7 (Capacity Command): `capacity_command_page7.py` exists — verify wiring
   - Page 10 (Client 360 Detail): Extension of client360.py for selected client
   - Page 11 (Comms/Commitments): `comms_commitments.py` engine exists — verify wiring
   - Page 12 (Cash/AR): `cash_ar.py` engine exists — verify wiring

5. For each replacement:
   - Implement using existing data access patterns from working engines
   - Ensure output matches the contract schema for that section
   - Test against live data

6. Run the full snapshot generator and validate:
   ```python
   from lib.agency_snapshot.generator import AgencySnapshotGenerator
   g = AgencySnapshotGenerator(db_path="data/moh_time_os.db")
   snapshot = g.generate()
   # Should pass all 4 validation gates
   ```

## Preconditions
- [ ] Phase 2 complete (truth modules wired, data populated)
- [ ] Brief 7 complete (schema aligned)

## Validation
1. `AgencySnapshotGenerator().generate()` succeeds without error
2. All 4 validation gates pass (predicates, invariants, thresholds, schema)
3. No section contains only placeholder/minimal data
4. `pytest tests/ -q` — passes

## Acceptance Criteria
- [ ] All minimal builders replaced with full implementations
- [ ] Snapshot passes all validation gates
- [ ] Output contains real data for all pages
- [ ] No test regressions

## Output
- Modified: `lib/agency_snapshot/generator.py` (major update)
- Possibly modified: individual page engine files
