"""
test_traceability.py — Ensure spec traceability passes.

This test imports and runs the traceability check, failing if:
- Mismatches > 0
- Missing > 0
- Extra > 0

This prevents anyone from weakening the traceability script
without the test suite catching it.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestSpecTraceability:
    """Test that spec traceability passes with zero violations."""

    def test_traceability_zero_mismatches(self):
        """Contract must have zero mismatches with spec."""
        from scripts.spec_traceability import compare_spec_to_contract

        report, mismatch_count, missing_count, extra_count = compare_spec_to_contract()

        assert mismatch_count == 0, (
            f"Spec traceability found {mismatch_count} mismatch(es).\n"
            f"Contract fields do not match spec requirements.\n"
            f"Full report:\n{report}"
        )

    def test_traceability_zero_missing(self):
        """Contract must have zero missing fields from spec."""
        from scripts.spec_traceability import compare_spec_to_contract

        report, mismatch_count, missing_count, extra_count = compare_spec_to_contract()

        assert missing_count == 0, (
            f"Spec traceability found {missing_count} missing field(s).\n"
            f"Contract is missing required spec fields.\n"
            f"Full report:\n{report}"
        )

    def test_traceability_zero_extras(self):
        """Contract must have zero extra fields not in spec."""
        from scripts.spec_traceability import compare_spec_to_contract

        report, mismatch_count, missing_count, extra_count = compare_spec_to_contract()

        assert extra_count == 0, (
            f"Spec traceability found {extra_count} extra field(s).\n"
            f"Contract has fields not defined in spec.\n"
            f"Either remove the extra fields or formalize them as sanctioned extensions.\n"
            f"Full report:\n{report}"
        )

    def test_traceability_full_compliance(self):
        """Contract must pass full spec traceability (all zeros)."""
        from scripts.spec_traceability import compare_spec_to_contract

        report, mismatch_count, missing_count, extra_count = compare_spec_to_contract()

        total_violations = mismatch_count + missing_count + extra_count

        assert total_violations == 0, (
            f"Spec traceability FAILED with {total_violations} total violation(s):\n"
            f"  - Mismatches: {mismatch_count}\n"
            f"  - Missing: {missing_count}\n"
            f"  - Extra: {extra_count}\n"
            f"\nFull report:\n{report}"
        )
