# IMPLEMENTATION_LOG.md

**Links:**
- [IMPLEMENTATION_STATE.md](./IMPLEMENTATION_STATE.md)
- [docs/SAFETY.md](./docs/SAFETY.md)
- [HEARTBEAT.md](../../HEARTBEAT.md)
- **Current spec entrypoint:** `lib/agency_snapshot/generator.py`
- **Current contracts module:** `lib/contracts/`

---

## 2026-02-10 11:15 — Safety + Provenance + Parity Foundation Complete

**Objective:** Implement systematic safety foundation so errors are caught before landing, and every DB write is attributable.

**Non-Negotiable Outcomes Achieved:**

1. ✅ `inbox_items_v29` is the only writable inbox table. `inbox_items` is now a VIEW.
2. ✅ DB cannot accept terminal state transitions without required audit fields (triggers ABORT).
3. ✅ Every DB write is attributable (actor/request_id/source/git_sha) via `write_context_v1` and logged to `db_write_audit_v1`.
4. ✅ CI fails on schema drift, missing triggers, missing indexes (schema assertions + tests).
5. ✅ Bulk/mass updates prevented unless in maintenance mode.
6. ✅ Single `make check` runs everything.

**Key Artifacts Created:**

| File | Purpose |
|------|---------|
| `lib/safety/` | WriteContext, audit logging, schema assertions, migrations |
| `tools/db_exec.py` | Attributed manual SQL execution |
| `tests/test_safety.py` | 17 safety tests |
| `scripts/ripgrep_check.sh` | Forbidden pattern scanner |
| `docs/SAFETY.md` | Documentation |
| `Makefile` | Build targets (check, test, migrate, dev) |

**Triggers Created (30 total):**
- 6 invariant triggers on `inbox_items_v29` (terminal state, dismiss fields, issue pointer)
- 12 context enforcement triggers (INSERT/UPDATE/DELETE on 4 tables)
- 12 audit triggers (INSERT/UPDATE/DELETE on 4 tables)

**Proof:**
- Direct SQL write without context: BLOCKED with `SAFETY: write context required`
- Audit entries show actor, request_id, source, git_sha for all writes
- `make check` passes: lint, ripgrep, schema, 17 tests

---

## 2026-02-09 23:45 — Fix-Data Endpoint Schema Mismatch

**Issue:** `[WARNING] api.spec_router: Fix-data endpoint error: no such column: id`

**Root Cause:** The `/api/v2/fix-data` endpoint's SQL query for `entity_links` used column names that don't exist in the actual schema.

| Expected (code) | Actual (schema) |
|-----------------|-----------------|
| id | link_id |
| entity_type | (doesn't exist) |
| entity_id | from_artifact_id |
| linked_type | to_entity_type |
| linked_id | to_entity_id |

**Fix Applied:**
- File: `api/spec_router.py` L1167-1173
- Changed query to use correct column names with aliases for API stability

**Verification:**
```sql
sqlite3 ~/.moh_time_os/data/moh_time_os.db \
  "SELECT link_id AS id, from_artifact_id AS entity_id, ... LIMIT 5;"
-- Query succeeds (empty result = no low-confidence links)
```

---

## 2026-02-09 14:30 — Audit Performed

**What:** Full audit of claimed implementation vs actual state.

**Findings:**

| Component | Claimed | Actual |
|-----------|---------|--------|
| lib/contracts/ | Complete | Files exist, NOT integrated into generator |
| lib/normalize/ | Complete | Files exist, NOT integrated into generator |
| Generator gates | Present | **ABSENT** — generate() returns dict with no validation |
| CI contract tests | Running | **NOT running** — ci.yml points to wrong test dir |
| CI patchwork scan | Gate | **ABSENT** — no step exists |
| tests/negative/ | Exists | **DOES NOT EXIST** |

**Evidence:**
```
# generator.py generate() method (L108-126):
snapshot = {
    "meta": self._build_meta(started_at),
    "trust": self._trust.to_dict(),
}
...
return snapshot  # <-- NO validation gates before return
```

**Why:** Prior work created facade files without structural integration.

**Corrective Action:** Begin actual integration now.

---

## 2026-02-09 14:35 — Generator Gate Integration COMPLETE

**Objective:** Make generator.generate() call all validation gates.

### Files Modified

1. **lib/agency_snapshot/generator.py**
   - Added imports: `from lib.contracts import AgencySnapshotContract, enforce_predicates_strict, enforce_invariants_strict, enforce_thresholds_strict, PredicateViolation, InvariantViolation, ThresholdViolation`
   - Added `_build_normalized_data()` method (L117-175)
   - Added `_compute_resolution_stats()` method (L177-218)
   - Added `_get_validation_environment()` method (L220-227)
   - Modified `generate()` to call gates before return (L229-310)
   - Gate order: predicates → invariants → thresholds → schema

2. **lib/contracts/__init__.py**
   - Added exports: `enforce_predicates_strict`, `enforce_invariants_strict`, `enforce_thresholds_strict`

3. **lib/gates.py**
   - Fixed pre-existing bug: `paid_date` → `payment_date`

4. **data/moh_time_os.db**
   - Added missing columns: `is_internal` (projects), `brand_id` (tasks)

5. **.github/workflows/ci.yml**
   - Added `pytest tests/contract/` step
   - Added `pytest tests/negative/` step
   - Added patchwork-scan job (mutation pattern detection)

6. **tests/negative/** (NEW)
   - `test_missing_sections.py` — 8 tests
   - `test_empty_when_data_exists.py` — 5 tests
   - `test_unresolved_scopes.py` — 5 tests

### Evidence

**Import test:**
```
$ python3 -c "from lib.agency_snapshot.generator import AgencySnapshotGenerator; print('Import OK')"
Import OK
```

**Gate functionality test:**
```
Testing Gate 1: Predicates...
  PASS
Testing Gate 2: Invariants...
  PASS
Testing Gate 3: Thresholds...
  PASS
Testing Gate 4: Schema...
  PASS
All gates callable and working.
```

**Negative test (gates fail when they should):**
```
Test 1: Empty debtors with unpaid invoices...
  CORRECTLY FAILED: Predicate check failed with 1 violation(s):
  - PREDICATE_VIOLATION: cash_ar.debtors is empty but must exist (unpaid_invoices=1)

Test 2: Commitment without resolution reason...
  CORRECTLY FAILED: Commitments with no resolution AND no reason: ['c1']. Count: 1

Test 3: Missing cash_ar section...
  CORRECTLY FAILED: ValidationError
```

**Test suite:**
```
$ pytest tests/contract/ tests/negative/ -v
============================== 54 passed in 0.17s ==============================
```

### Status: COMPLETE
