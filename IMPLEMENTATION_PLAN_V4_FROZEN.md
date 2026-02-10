# Implementation Plan v4 — FROZEN

> **Status:** FROZEN
> **Frozen At:** 2025-02-09T17:30:00+04:00
> **DO NOT MODIFY WITHOUT PR + JUSTIFICATION**

---

## Amendment 1: "No Post-Processing" Enforcement

**Rule:** Generator output must be produced ONLY by:
```
extract → normalize → aggregate → validate
```

No "enrich_snapshot(snapshot)" stage. No last-minute fill-ins.

**CI Scan:** Grep-ban common patch patterns in generator path:
```bash
# scripts/patchwork_scan.sh
grep -rn --include="*.py" \
  -E "(snapshot\[|setdefault|\.update\(|deepmerge|\"fallback\"|if missing|if not |or \{\}|or \[\])" \
  lib/agency_snapshot/ lib/normalize/ lib/aggregators/ dashboard/
```

**Banned Files:** `dashboard/enrich_snapshot.py` must be deleted after logic is moved upstream.

---

## Amendment 2: Unknown Scope Types Fail Fast

**Hard Gate (not logging):**
- Unknown `scope_ref_type` ⇒ `raise ValueError(...)`
- Known but unresolvable ⇒ must produce `(resolved=False, unresolved_reason=...)` and count against thresholds

```python
# REQUIRED in resolvers.py
case _:
    raise ValueError(
        f"Unknown scope_ref_type '{scope_type}' for {entity_id}. "
        f"Add handling to resolver or update ScopeRefType enum."
    )
```

---

## Amendment 3: Thresholds Justified + Environment-Specific

**Required in `contracts/thresholds.py`:**

```python
"""
THRESHOLD JUSTIFICATIONS:

COMMITMENT_RESOLUTION_RATE = 0.85 (85%)
  - Why: Below 85% means >15% of commitments have no client context,
    making downstream aggregation unreliable for client360.
  - Source: Observed baseline from standard_agency fixture = 92%.

THREAD_CLIENT_LINKAGE = 0.70 (70%)
  - Why: Threads can legitimately be internal (no client).
    70% ensures majority have context while allowing internal comms.
  - Source: Business rule from ops review.

INVOICE_VALIDITY_RATE = 0.90 (90%)
  - Why: AR calculations depend on clean invoice data.
    <90% validity corrupts financial views.
  - Source: Xero data quality baseline.
"""

# Environment-specific overrides
THRESHOLDS = {
    "standard_agency": {
        "commitment_resolution_rate": 0.85,
        "thread_client_linkage": 0.70,
        "invoice_validity_rate": 0.90,
    },
    "production": {
        "commitment_resolution_rate": 0.80,  # Production has more edge cases
        "thread_client_linkage": 0.65,
        "invoice_validity_rate": 0.85,
    },
}
```

---

## Amendment 4: Invariants Run on BOTH Fixture and Live

**Required:** Generator runs invariants in normal execution and fails on violation.

```python
# generator.py (production path)
def generate(self, db_path: str) -> dict:
    raw = self.extractor.extract_all(db_path)
    normalized = self.normalizer.normalize(raw)
    snapshot = self.aggregator.build_snapshot(normalized)

    # INVARIANTS RUN IN PRODUCTION - not just tests
    violations = enforce_invariants(snapshot, normalized)
    if violations:
        raise InvariantViolation(
            f"Generator invariant failures:\n" + "\n".join(violations)
        )

    validated = AgencySnapshotContract.model_validate(snapshot)
    return validated.model_dump()
```

---

## Amendment 5: Golden Fixtures Cannot Be Massaged

**Rules:**
1. Golden expectations must be hand-derived (not auto-generated)
2. Stored in file that is hard to "auto-update"
3. Any change requires explicit WHY note

**Enforcement:**

```yaml
# .github/workflows/contract.yml
- name: Check golden fixture changes
  run: |
    if git diff --name-only HEAD~1 | grep -qE "(tests/golden/fixtures/|GOLDEN_EXPECTATIONS)"; then
      # Check PR description contains GOLDEN_CHANGE_JUSTIFICATION
      if ! echo "${{ github.event.pull_request.body }}" | grep -q "GOLDEN_CHANGE_JUSTIFICATION:"; then
        echo "::error::Golden fixtures modified without GOLDEN_CHANGE_JUSTIFICATION in PR description."
        exit 1
      fi
    fi
```

**File:** `tests/golden/JUSTIFICATION.md` required for any fixture changes:
```markdown
# Golden Fixture Change Log

## [DATE] — [FIXTURE] — [FIELD]
**Changed:** [old] → [new]
**Why:** [explanation]
**Verified by:** [manual verification method]
```

---

## Core Architecture

### Multi-Layer Validation Pipeline

```
Extract → [VALIDATE raw completeness]
    ↓
Normalize → [VALIDATE domain model integrity]
    ↓
Aggregate → [VALIDATE section invariants]
    ↓
Assemble → [VALIDATE contract shape]
    ↓
Emit (only if all gates pass)
```

### Deliverable Structure

```
lib/contracts/
  __init__.py
  schema.py           # Pydantic models (shape)
  invariants.py       # Semantic invariants (meaning)
  predicates.py       # Existence predicates (data-existence rules)
  thresholds.py       # Quality gates with justifications

lib/normalize/
  __init__.py
  domain_models.py    # Canonical types + NormalizedData with stats
  extractors/
  resolvers.py        # Exhaustive resolvers with metrics

lib/aggregators/
  cash_ar.py
  comms_commitments.py
  capacity.py
  client360.py
  delivery.py

tests/
  golden/
    fixtures/
      standard_agency.db    # Frozen fixture
    JUSTIFICATION.md        # Change log
    conftest.py             # GOLDEN_EXPECTATIONS
    test_golden_ar.py
    test_golden_counts.py
  negative/
    test_missing_sections.py
    test_empty_when_data_exists.py
    test_unresolved_scopes.py
    test_wrong_extraction_shape.py
  contract/
    test_thresholds.py
    test_invariants.py
    test_predicates.py
```

---

## Day-by-Day Deliverables

| Day | Core | Add-on |
|-----|------|--------|
| 1 | `lib/contracts/` (schema, predicates, thresholds) | `invariants.py` + `validate_invariants()` gate |
| 2 | `lib/normalize/` (extractors, resolvers) | `normalized.stats` + threshold tests |
| 3 | Aggregators + generator pipeline refactor | All gates integrated, `enrich_snapshot.py` deleted |
| 4 | Golden tests + CI gates | Negative tests for each bug class |

---

## Non-Negotiables

1. **No patchwork:** Do not mutate/enrich final outputs to "make it pass"
2. **Fix at root:** All fixes in extract/normalize/aggregate only
3. **Hard gates:** Contract + invariants + completeness metrics fail the build
4. **Single source:** Every mapping rule lives in one place and has a test
5. **Loud failures:** Unknowns fail with clear error, or explicit unresolved record + threshold gate
6. **Production invariants:** Invariants run in production, not just tests

---

## Patchwork Scan (Run Before Every Commit)

```bash
#!/bin/bash
# scripts/patchwork_scan.sh
set -e

echo "=== Patchwork Anti-Pattern Scan ==="

VIOLATIONS=$(grep -rn --include="*.py" \
  -E "(snapshot\[.*\]\s*=|\.setdefault\(|\.update\(\{|deepmerge|\"fallback\"|\"if missing\"|or \{\}$|or \[\]$)" \
  lib/agency_snapshot/ lib/normalize/ lib/aggregators/ dashboard/ 2>/dev/null || true)

if [ -n "$VIOLATIONS" ]; then
  echo "❌ PATCHWORK VIOLATIONS FOUND:"
  echo "$VIOLATIONS"
  echo ""
  echo "These patterns suggest post-processing. Move logic upstream."
  exit 1
fi

echo "✅ No patchwork patterns detected"
```

---

**This plan is FROZEN. Implementation begins immediately.**
