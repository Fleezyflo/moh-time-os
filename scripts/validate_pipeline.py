#!/usr/bin/env python3
"""
Pipeline Validation Script — Brief 7 (Pipeline Hardening) Task PH_5_1

Runs each pipeline stage on the live DB and reports pass/fail with counts.
Usage:
    MOH_TIME_OS_DB=data/moh_time_os.db python scripts/validate_pipeline.py
"""

import os
import sys
import traceback

# Ensure we can import lib/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Verify DB path is set
db_path = os.environ.get("MOH_TIME_OS_DB")
if not db_path:
    print("ERROR: Set MOH_TIME_OS_DB env var (e.g. MOH_TIME_OS_DB=data/moh_time_os.db)")
    sys.exit(1)

if not os.path.exists(db_path):
    print(f"ERROR: DB not found at {db_path}")
    sys.exit(1)


def run_stage(name: str, fn) -> tuple[bool, str]:
    """Run a pipeline stage, return (success, result_description)."""
    try:
        result = fn()
        return True, str(result)
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"{e}\n{tb}"


def main():
    results = {}
    all_passed = True

    # Stage 1: Normalizer
    print("=" * 60)
    print("Stage 1: Normalizer")
    print("=" * 60)

    def run_normalizer():
        from lib.normalizer import Normalizer

        n = Normalizer()
        return n.run()

    ok, detail = run_stage("normalizer", run_normalizer)
    results["normalizer"] = (ok, detail)
    print(f"  {'PASS' if ok else 'FAIL'}: {detail}")
    if not ok:
        all_passed = False
    print()

    # Stage 2: Commitment Extraction
    print("=" * 60)
    print("Stage 2: Commitment Extraction")
    print("=" * 60)

    def run_commitments():
        from lib.commitment_extractor import run

        return run()

    ok, detail = run_stage("commitment_extraction", run_commitments)
    results["commitment_extraction"] = (ok, detail)
    print(f"  {'PASS' if ok else 'FAIL'}: {detail}")
    if not ok:
        all_passed = False
    print()

    # Stage 3: Lane Assignment
    print("=" * 60)
    print("Stage 3: Lane Assignment")
    print("=" * 60)

    def run_lanes():
        from lib.lane_assigner import run_assignment

        return run_assignment()

    ok, detail = run_stage("lane_assignment", run_lanes)
    results["lane_assignment"] = (ok, detail)
    print(f"  {'PASS' if ok else 'FAIL'}: {detail}")
    if not ok:
        all_passed = False
    print()

    # Stage 4: Gates
    print("=" * 60)
    print("Stage 4: Gates")
    print("=" * 60)

    def run_gates():
        from lib.gates import evaluate_gates

        return evaluate_gates()

    ok, detail = run_stage("gates", run_gates)
    results["gates"] = (ok, detail)
    print(f"  {'PASS' if ok else 'FAIL'}: {detail}")
    if not ok:
        all_passed = False
    print()

    # Stage 5: Resolution Queue
    print("=" * 60)
    print("Stage 5: Resolution Queue")
    print("=" * 60)

    def run_resolution():
        from lib.resolution_queue import populate_queue

        return populate_queue()

    ok, detail = run_stage("resolution_queue", run_resolution)
    results["resolution_queue"] = (ok, detail)
    print(f"  {'PASS' if ok else 'FAIL'}: {detail}")
    if not ok:
        all_passed = False
    print()

    # Summary
    print("=" * 60)
    print("PIPELINE VALIDATION SUMMARY")
    print("=" * 60)
    for stage, (ok, detail) in results.items():
        status = "PASS" if ok else "FAIL"
        # Truncate detail for summary
        short = detail.split("\n")[0][:80]
        print(f"  [{status}] {stage}: {short}")

    print()
    if all_passed:
        print("ALL STAGES PASSED")
        return 0
    else:
        failed = [s for s, (ok, _) in results.items() if not ok]
        print(f"FAILED STAGES: {', '.join(failed)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
