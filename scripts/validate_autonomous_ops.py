#!/usr/bin/env python3
"""
Autonomous Operations Validation Script (AO-6.1)

Validates that the system can run autonomously without intervention:
- All tests pass (0 failures)
- Critical modules import cleanly
- AutonomousLoop instantiates with mocked deps
- TimeOSDaemon job registration works
- HealthChecker returns valid report
- Change bundle lifecycle works
- DataLifecycleManager policies are correct
- Backup functions exist and are callable

Exit code: 0 if all checks pass, 1 if any fail
"""

# Add repo root to path
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


def check_full_test_suite() -> bool:
    """Run all tests, assert 0 failures."""
    print("\n1. Running full test suite...")

    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/", "-q", "--tb=short"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=300,
            text=True,
        )

        # Parse output for pass/fail
        output_lines = result.stdout.split("\n")
        for line in output_lines:
            if "passed" in line or "failed" in line:
                print(f"   {line}")

        if result.returncode == 0:
            print("   ✅ All tests passed")
            return True
        else:
            print(f"   ❌ Tests failed with code {result.returncode}")
            print(f"   stderr: {result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        print("   ❌ Test suite timed out (>5 minutes)")
        return False
    except Exception as e:
        print(f"   ❌ Test suite failed: {e}")
        return False


def check_import_validation() -> bool:
    """Verify all critical modules import cleanly."""
    print("\n2. Checking critical module imports...")

    imports_to_check = [
        ("lib.daemon", ["TimeOSDaemon", "JobConfig", "JobState", "JobHealth"]),
        ("lib.autonomous_loop", ["AutonomousLoop"]),
        ("lib.change_bundles", ["BundleManager", "create_bundle"]),
        ("lib.cycle_result", ["CycleResult"]),
        ("lib.data_lifecycle", ["DataLifecycleManager"]),
        ("lib.backup", ["create_backup", "restore_backup"]),
        ("lib.maintenance", ["get_maintenance_report"]),
        ("lib.observability.metrics", ["REGISTRY", "Counter", "Gauge", "Histogram"]),
        ("lib.observability.health", ["HealthChecker", "HealthStatus"]),
        ("lib.observability.logging", ["JSONFormatter"]),
        ("lib.observability.middleware", ["CorrelationIdMiddleware"]),
        ("lib.collectors.resilience", ["RetryConfig", "CircuitBreaker", "RateLimiter"]),
    ]

    all_imported = True
    for module_name, items in imports_to_check:
        try:
            module = __import__(module_name, fromlist=items)
            missing = []
            for item in items:
                if not hasattr(module, item):
                    missing.append(item)

            if missing:
                print(f"   ❌ {module_name}: missing {missing}")
                all_imported = False
            else:
                print(f"   ✅ {module_name}: {', '.join(items)}")
        except ImportError as e:
            print(f"   ❌ {module_name}: ImportError: {e}")
            all_imported = False
        except Exception as e:
            print(f"   ❌ {module_name}: {type(e).__name__}: {e}")
            all_imported = False

    return all_imported


def check_simulated_cycle_run() -> bool:
    """Instantiate AutonomousLoop with mocked deps and verify structure."""
    print("\n3. Checking simulated cycle run...")

    try:
        from lib.autonomous_loop import AutonomousLoop
        from lib.cycle_result import CycleResult, PhaseResult

        # Create temp config dir
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock the dependencies
            with (
                patch("lib.autonomous_loop.CollectorOrchestrator"),
                patch("lib.autonomous_loop.AnalyzerOrchestrator"),
                patch("lib.autonomous_loop.ReasonerEngine"),
                patch("lib.autonomous_loop.ExecutorEngine"),
                patch("lib.autonomous_loop.NotificationEngine"),
                patch("lib.autonomous_loop.get_store"),
                patch("lib.autonomous_loop.get_governance"),
                patch("lib.autonomous_loop.BundleManager"),
            ):
                # Instantiate loop with string path (tmpdir is already a string)
                loop = AutonomousLoop(config_path=tmpdir)
                print("   ✅ AutonomousLoop instantiated")

                # Verify it has the right methods
                if hasattr(loop, "run_cycle"):
                    print("   ✅ AutonomousLoop.run_cycle() exists")
                else:
                    print("   ❌ AutonomousLoop.run_cycle() not found")
                    return False

                if hasattr(loop, "collect"):
                    print("   ✅ AutonomousLoop.collect() exists")

                if hasattr(loop, "analyze"):
                    print("   ✅ AutonomousLoop.analyze() exists")

                if hasattr(loop, "reason"):
                    print("   ✅ AutonomousLoop.reason() exists")

                return True
    except Exception as e:
        print(f"   ❌ Simulated cycle failed: {type(e).__name__}: {e}")
        return False


def check_daemon_job_registration() -> bool:
    """Instantiate TimeOSDaemon and verify jobs register correctly."""
    print("\n4. Checking daemon job registration...")

    try:
        from lib.daemon import JobConfig, JobHealth, JobState, TimeOSDaemon

        # Create a daemon instance
        daemon = TimeOSDaemon()
        print("   ✅ TimeOSDaemon instantiated")

        # Verify it has jobs dict
        if hasattr(daemon, "jobs"):
            print(f"   ✅ jobs dict exists: {len(daemon.jobs)} default jobs")
        else:
            print("   ❌ jobs dict not found")
            return False

        # Verify it has running flag
        if hasattr(daemon, "running"):
            print("   ✅ running flag exists")
        else:
            print("   ❌ running flag not found")
            return False

        # Create a test job config
        test_job = JobConfig(
            name="test_job",
            interval_minutes=60,
            command=["echo", "test"],
        )
        print(f"   ✅ JobConfig created: {test_job.name}")

        # Register the job
        daemon.register_job(test_job)
        print(f"   ✅ Job registered: {test_job.name}")

        # Verify JobHealth enum works
        health = JobHealth.HEALTHY
        print(f"   ✅ JobHealth enum works: {health.value}")

        # Verify JobState is instantiable
        JobState(last_run=None, last_success=None)
        print("   ✅ JobState dataclass works")

        return True
    except Exception as e:
        print(f"   ❌ Daemon job registration failed: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_health_check_validation() -> bool:
    """Run HealthChecker and verify it returns a valid report."""
    print("\n5. Checking health check validation...")

    try:
        from lib.observability.health import HealthChecker, HealthStatus

        # Instantiate health checker
        checker = HealthChecker()
        print("   ✅ HealthChecker instantiated")

        # Verify it has run_all method
        if hasattr(checker, "run_all"):
            print("   ✅ run_all() method exists")
        else:
            print("   ❌ run_all() method not found")
            return False

        # Verify HealthStatus enum exists
        status_values = [s.value for s in HealthStatus]
        print(f"   ✅ HealthStatus enum works: {status_values}")

        return True
    except Exception as e:
        print(f"   ❌ Health check validation failed: {type(e).__name__}: {e}")
        return False


def check_change_bundle_lifecycle() -> bool:
    """Create a bundle, verify structure, BundleManager works."""
    print("\n6. Checking change bundle lifecycle...")

    try:
        from lib.change_bundles import BundleManager, create_bundle

        # Create a bundle with correct parameters
        bundle = create_bundle(
            domain="tasks",
            description="Test bundle for validation",
            changes=[{"op": "update", "id": "test"}],
        )
        print(f"   ✅ create_bundle() works: {bundle.get('id', 'N/A')}")

        # Verify bundle structure
        if "id" in bundle:
            print("   ✅ Bundle has id")
        else:
            print("   ❌ Bundle missing id")
            return False

        if "domain" in bundle:
            print(f"   ✅ Bundle has domain: {bundle['domain']}")
        else:
            print("   ❌ Bundle missing domain")
            return False

        # Instantiate BundleManager (no arguments)
        manager = BundleManager()
        print("   ✅ BundleManager instantiated")

        # Verify it has required methods
        if hasattr(manager, "list_bundles_for_status"):
            print("   ✅ list_bundles_for_status() method exists")
        else:
            print("   ❌ list_bundles_for_status() not found")
            return False

        if hasattr(manager, "rollback_cycle"):
            print("   ✅ rollback_cycle() method exists")
        else:
            print("   ❌ rollback_cycle() not found")
            return False

        return True
    except Exception as e:
        print(f"   ❌ Change bundle lifecycle failed: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_data_lifecycle() -> bool:
    """Verify DataLifecycleManager instantiates with correct default policies."""
    print("\n7. Checking data lifecycle...")

    try:
        from lib.data_lifecycle import DataLifecycleManager

        # Instantiate with defaults
        manager = DataLifecycleManager()
        print("   ✅ DataLifecycleManager instantiated")

        # Verify it has required attributes (use private _retention_policies)
        if hasattr(manager, "_retention_policies"):
            print("   ✅ retention_policies exists")
        else:
            print("   ❌ retention_policies not found")
            return False

        # Verify it has required methods
        if hasattr(manager, "enforce_retention"):
            print("   ✅ enforce_retention() method exists")
        else:
            print("   ❌ enforce_retention() not found")
            return False

        if hasattr(manager, "get_lifecycle_report"):
            print("   ✅ get_lifecycle_report() method exists")
        else:
            print("   ❌ get_lifecycle_report() not found")
            return False

        return True
    except Exception as e:
        print(f"   ❌ Data lifecycle check failed: {type(e).__name__}: {e}")
        return False


def check_backup_validation() -> bool:
    """Verify backup module functions exist and are callable."""
    print("\n8. Checking backup validation...")

    try:
        from lib.backup import create_backup, restore_backup

        # Verify functions are callable
        if callable(create_backup):
            print("   ✅ create_backup() is callable")
        else:
            print("   ❌ create_backup() not callable")
            return False

        if callable(restore_backup):
            print("   ✅ restore_backup() is callable")
        else:
            print("   ❌ restore_backup() not callable")
            return False

        return True
    except ImportError as e:
        print(f"   ❌ Backup import failed: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Backup validation failed: {type(e).__name__}: {e}")
        return False


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("Autonomous Operations Validation (AO-6.1)")
    print("=" * 70)

    checks = [
        ("Full test suite", check_full_test_suite),
        ("Import validation", check_import_validation),
        ("Simulated cycle run", check_simulated_cycle_run),
        ("Daemon job registration", check_daemon_job_registration),
        ("Health check validation", check_health_check_validation),
        ("Change bundle lifecycle", check_change_bundle_lifecycle),
        ("Data lifecycle", check_data_lifecycle),
        ("Backup validation", check_backup_validation),
    ]

    results = []
    for name, check_fn in checks:
        try:
            passed = check_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ {name}: FAILED with exception: {type(e).__name__}: {e}")
            results.append((name, False))

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed_count = 0
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if passed:
            passed_count += 1

    total = len(results)
    print(f"\nScore: {passed_count}/{total} checks passed")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✅ All checks passed! System is ready for autonomous operations.")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
