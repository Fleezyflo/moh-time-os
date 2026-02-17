#!/usr/bin/env python3
"""
Ratchet Check — Verify metrics haven't increased from baseline.

This implements the ratchet pattern: metrics can decrease (improve)
but should never increase. Any increase fails the check.

Usage:
    python scripts/ratchet_check.py           # Check against baseline
    python scripts/ratchet_check.py --strict  # Fail on any increase (default)
    python scripts/ratchet_check.py --warn    # Warn but don't fail
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BASELINE_FILE = PROJECT_ROOT / ".ratchet-baseline.json"


def main():
    # Import metrics collection from snapshot script
    from ratchet_snapshot import collect_metrics

    warn_only = "--warn" in sys.argv

    # Load baseline
    if not BASELINE_FILE.exists():
        print("❌ No baseline found. Run ratchet_snapshot.py first.")
        sys.exit(1)

    baseline = json.loads(BASELINE_FILE.read_text())

    # Collect current metrics
    current = collect_metrics()

    # Compare
    failures = []
    improvements = []
    unchanged = []

    for key in baseline:
        if key not in current:
            continue

        baseline_val = baseline[key]
        current_val = current[key]

        if current_val > baseline_val:
            failures.append((key, baseline_val, current_val))
        elif current_val < baseline_val:
            improvements.append((key, baseline_val, current_val))
        else:
            unchanged.append(key)

    # Report
    print("=" * 60)
    print("RATCHET CHECK")
    print("=" * 60)

    if improvements:
        print("\n✅ IMPROVEMENTS (can update baseline):")
        for key, old, new in improvements:
            print(f"   {key}: {old} → {new} (↓{old - new})")

    if unchanged:
        print(f"\n⚪ UNCHANGED: {len(unchanged)} metrics")

    if failures:
        print("\n❌ REGRESSIONS (blocked):")
        for key, old, new in failures:
            print(f"   {key}: {old} → {new} (↑{new - old})")

        if warn_only:
            print("\n⚠️  Regressions detected (warn mode, not blocking)")
        else:
            print("\n❌ FAILED: Metrics increased from baseline.")
            print("   Fix the regressions or run ratchet_snapshot.py to update baseline.")
            sys.exit(1)
    else:
        print("\n✅ PASSED: No regressions detected.")

    # Summary
    print(f"\n📊 Summary: {len(improvements)} improved, {len(unchanged)} unchanged, {len(failures)} regressed")


if __name__ == "__main__":
    main()
