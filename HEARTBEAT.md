# HEARTBEAT.md — Contracts & Validation Implementation

> **Last Updated:** 2025-02-09T21:30:00+04:00

## Tracking Files

- **Implementation Log:** [IMPLEMENTATION_LOG.md](./IMPLEMENTATION_LOG.md)
- **Implementation State:** [IMPLEMENTATION_STATE.md](./IMPLEMENTATION_STATE.md)
- **Frozen Plan:** [IMPLEMENTATION_PLAN_V4_FROZEN.md](./IMPLEMENTATION_PLAN_V4_FROZEN.md)

---

## GLOBAL_PROMPT — Implementation Pillars

1. **Truth pledge:** If I have not actually edited files, run tests, or validated gates, I must say "NO WORK PERFORMED" and stop claiming progress.

2. **Evidence-or-fail rule:** Every claimed improvement must include file paths + diff summary + command(s) run + pass/fail output logged in IMPLEMENTATION_LOG.md; otherwise it is treated as deception and must be corrected immediately.

3. **No patchwork constraint:** Any post-build mutation of the snapshot (manual JSON enrichment, dict surgery after aggregation, conditional "fill missing" hacks) is forbidden; if found, I must rip it out and move the logic upstream (extract/normalize/aggregate) with a test that would have caught it.

4. **Hard-work bias:** If two approaches exist, I must pick the one that reduces future entropy (centralized semantic rules + contract/invariants + fixtures) even if it's more work now; choosing the "quick pass" path is a failure condition that must be logged as such.

5. **Self-audit trigger:** At the start of every loop, I must run and log a patchwork scan (grep for snapshot mutation/placeholder literals) and a gate run (contract + invariants + tests). Any mismatch between claims and evidence is recorded in IMPLEMENTATION_STATE.md under "Integrity Violations" with the immediate corrective action.

6. **Fix at root only:** All fixes must happen in extract/normalize/aggregate. Never in the final output path.

7. **Loud unknowns:** Unknown scope types raise exceptions. No silent None. Unresolved items produce explicit reason + count against thresholds.

8. **Production invariants:** Invariants run in production generator, not just tests. Generator fails if invariants fail.

9. **Persist immediately:** Every time I read any file, I append progress to IMPLEMENTATION_LOG.md immediately. No silent work.

---

## Current Directives

**Active Task:** COMPLETE — All contracts, validation, and spec traceability implemented

**Current Spec:** [IMPLEMENTATION_PLAN_V4_FROZEN.md](./IMPLEMENTATION_PLAN_V4_FROZEN.md)

**Status:** ✅ GREEN — All gates passing

---

## Completed Checklist

- ✅ `lib/contracts/` — schema, predicates, invariants, thresholds
- ✅ `lib/normalize/` — domain models, resolvers with exhaustive types
- ✅ Wire validation into generator pipeline (lines 326-341)
- ✅ Patchwork scan made strict + integrated into CI
- ✅ Spec traceability check (schema_version=2.9.0 bound to UI spec)
- ✅ CI enforcement of spec traceability (blocking step)
- ✅ Anti-tamper tests for traceability (4 tests)

---

## Integrity Status

**Last Patchwork Scan:** 2025-02-09T21:30+04:00
**Patchwork Result:** ✅ 0 violations
**Last Gate Run:** 2025-02-09T21:30+04:00 — 77 tests passing
**Spec Traceability:** Matches=13, Mismatches=0, Missing=0, Extra=0

**Test Breakdown:**
- `tests/contract/` — 46 tests (including 4 traceability)
- `tests/negative/` — 22 tests (including 4 patchwork policy)
- `tests/golden/` — 9 tests

**Integrity Violations:** None

---

## Cleanup Opportunity

- `dashboard/enrich_snapshot.py` — Orphaned file (no usages found). Can be deleted.

---

*This file is the agent's heartbeat. Check IMPLEMENTATION_STATE.md for current objective and IMPLEMENTATION_LOG.md for evidence trail.*
