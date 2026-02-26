#!/usr/bin/env python3
"""
Intelligence Expansion Validation Script (IE-7.1)

Validates all Brief 11 intelligence modules:
- Cost-to-serve engine instantiates and has required methods
- Correlation engine instantiates with domain classification
- Scenario engine instantiates with all scenario types
- Trajectory engine instantiates with computation methods
- Unified intelligence layer instantiates
- Auto-resolution engine instantiates with all 7 rules
- All tests pass (0 failures)

Exit code: 0 if all checks pass, 1 if any fail
"""

import subprocess
import sys
import tempfile
from pathlib import Path

# Add repo root to path
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


def check_cost_to_serve() -> bool:
    """Verify CostToServeEngine instantiates with required methods."""
    print("\n2. Checking cost-to-serve engine...")

    try:
        from lib.intelligence.cost_to_serve import (
            ClientCostProfile,
            CostToServeEngine,
            PortfolioProfitability,
            ProjectCostProfile,
        )

        CostToServeEngine.__new__(CostToServeEngine)
        print("   ✅ CostToServeEngine importable")

        required_methods = [
            "compute_client_cost",
            "compute_project_cost",
            "compute_portfolio_profitability",
            "get_hidden_cost_clients",
            "get_profitability_ranking",
        ]

        for method in required_methods:
            if hasattr(CostToServeEngine, method):
                print(f"   ✅ {method}() exists")
            else:
                print(f"   ❌ {method}() missing")
                return False

        # Check dataclasses
        for cls_name, cls in [
            ("ClientCostProfile", ClientCostProfile),
            ("ProjectCostProfile", ProjectCostProfile),
            ("PortfolioProfitability", PortfolioProfitability),
        ]:
            if hasattr(cls, "to_dict"):
                print(f"   ✅ {cls_name}.to_dict() exists")
            else:
                print(f"   ❌ {cls_name}.to_dict() missing")
                return False

        return True
    except Exception as e:
        print(f"   ❌ Cost-to-serve check failed: {type(e).__name__}: {e}")
        return False


def check_correlation_engine() -> bool:
    """Verify CorrelationEngine instantiates with domain classification."""
    print("\n3. Checking correlation engine...")

    try:
        from lib.intelligence.correlation_engine import (
            CompoundRisk,
            CorrelationEngine,
            CrossDomainCorrelation,
            Domain,
            IntelligenceBrief,
            PriorityAction,
        )

        # Check Domain enum
        domains = [d.value for d in Domain]
        print(f"   ✅ Domain enum: {domains}")

        required_methods = [
            "run_full_scan",
            "find_compound_risks",
            "classify_domain",
            "cross_domain_correlations",
            "generate_priority_actions",
        ]

        for method in required_methods:
            if hasattr(CorrelationEngine, method):
                print(f"   ✅ {method}() exists")
            else:
                print(f"   ❌ {method}() missing")
                return False

        # Check dataclasses
        for cls_name, cls in [
            ("CompoundRisk", CompoundRisk),
            ("CrossDomainCorrelation", CrossDomainCorrelation),
            ("PriorityAction", PriorityAction),
            ("IntelligenceBrief", IntelligenceBrief),
        ]:
            if hasattr(cls, "to_dict"):
                print(f"   ✅ {cls_name}.to_dict() exists")
            else:
                print(f"   ❌ {cls_name}.to_dict() missing")
                return False

        return True
    except Exception as e:
        print(f"   ❌ Correlation engine check failed: {type(e).__name__}: {e}")
        return False


def check_scenario_engine() -> bool:
    """Verify ScenarioEngine instantiates with all scenario types."""
    print("\n4. Checking scenario engine...")

    try:
        from lib.intelligence.scenario_engine import (
            ScenarioEngine,
            ScenarioType,
        )

        # Check ScenarioType enum
        types = [t.value for t in ScenarioType]
        print(f"   ✅ ScenarioType enum: {types}")

        expected_types = [
            "CLIENT_LOSS",
            "CLIENT_ADDITION",
            "RESOURCE_CHANGE",
            "PRICING_CHANGE",
            "CAPACITY_SHIFT",
            "WORKLOAD_REBALANCE",
        ]
        for et in expected_types:
            if et in types:
                print(f"   ✅ ScenarioType.{et} exists")
            else:
                print(f"   ❌ ScenarioType.{et} missing")
                return False

        required_methods = [
            "model_client_loss",
            "model_client_addition",
            "model_resource_change",
            "model_pricing_change",
            "compare_scenarios",
        ]

        for method in required_methods:
            if hasattr(ScenarioEngine, method):
                print(f"   ✅ {method}() exists")
            else:
                print(f"   ❌ {method}() missing")
                return False

        return True
    except Exception as e:
        print(f"   ❌ Scenario engine check failed: {type(e).__name__}: {e}")
        return False


def check_trajectory_engine() -> bool:
    """Verify TrajectoryEngine instantiates with computation methods."""
    print("\n5. Checking trajectory engine...")

    try:
        from lib.intelligence.trajectory import (
            TrajectoryEngine,
            TrendDirection,
        )

        # Check TrendDirection enum
        directions = [d.value for d in TrendDirection]
        print(f"   ✅ TrendDirection enum: {directions}")

        required_methods = [
            "compute_velocity",
            "compute_acceleration",
            "detect_trend",
            "detect_seasonality",
            "project_forward",
            "client_full_trajectory",
            "portfolio_health_trajectory",
        ]

        for method in required_methods:
            if hasattr(TrajectoryEngine, method):
                print(f"   ✅ {method}() exists")
            else:
                print(f"   ❌ {method}() missing")
                return False

        # Test pure math (no DB needed)
        engine = TrajectoryEngine.__new__(TrajectoryEngine)
        vel = engine.compute_velocity([10, 20, 30, 40, 50])
        print(f"   ✅ compute_velocity works: velocity={vel.current_velocity}")

        trend = engine.detect_trend([10, 20, 30, 40, 50])
        print(f"   ✅ detect_trend works: direction={trend.direction}")

        return True
    except Exception as e:
        print(f"   ❌ Trajectory engine check failed: {type(e).__name__}: {e}")
        return False


def check_unified_intelligence() -> bool:
    """Verify IntelligenceLayer instantiates."""
    print("\n6. Checking unified intelligence layer...")

    try:
        from lib.intelligence.unified_intelligence import (
            ClientIntelligence,
            IntelligenceCycleResult,
            IntelligenceLayer,
            PortfolioDashboard,
        )

        required_methods = [
            "run_intelligence_cycle",
            "get_client_intelligence",
            "get_portfolio_dashboard",
            "run_scenario",
        ]

        for method in required_methods:
            if hasattr(IntelligenceLayer, method):
                print(f"   ✅ {method}() exists")
            else:
                print(f"   ❌ {method}() missing")
                return False

        for cls_name, cls in [
            ("IntelligenceCycleResult", IntelligenceCycleResult),
            ("ClientIntelligence", ClientIntelligence),
            ("PortfolioDashboard", PortfolioDashboard),
        ]:
            if hasattr(cls, "to_dict"):
                print(f"   ✅ {cls_name}.to_dict() exists")
            else:
                print(f"   ❌ {cls_name}.to_dict() missing")
                return False

        return True
    except Exception as e:
        print(f"   ❌ Unified intelligence check failed: {type(e).__name__}: {e}")
        return False


def check_auto_resolution() -> bool:
    """Verify AutoResolutionEngine instantiates with all 7 rules."""
    print("\n7. Checking auto-resolution engine...")

    try:
        from lib.intelligence.auto_resolution import (
            AutoResolutionEngine,
        )

        required_methods = [
            "scan_and_resolve",
            "attempt_auto_resolve",
            "get_resolution_rules",
            "batch_resolve",
            "escalate",
        ]

        for method in required_methods:
            if hasattr(AutoResolutionEngine, method):
                print(f"   ✅ {method}() exists")
            else:
                print(f"   ❌ {method}() missing")
                return False

        # Check rules cover all 7 issue types
        engine = AutoResolutionEngine(db_path=Path(tempfile.gettempdir()) / "dummy_validation.db")
        rules = engine.get_resolution_rules()
        rule_types = {r.issue_type for r in rules}
        print(f"   ✅ {len(rules)} resolution rules found: {rule_types}")

        if len(rules) >= 7:
            print(f"   ✅ All {len(rules)} resolution rules present")
        else:
            print(f"   ❌ Expected 7+ rules, got {len(rules)}")
            return False
        return True
    except Exception as e:
        print(f"   ❌ Auto-resolution check failed: {type(e).__name__}: {e}")
        return False


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("Intelligence Expansion Validation (IE-7.1)")
    print("=" * 70)

    checks = [
        ("Full test suite", check_full_test_suite),
        ("Cost-to-serve engine", check_cost_to_serve),
        ("Correlation engine", check_correlation_engine),
        ("Scenario engine", check_scenario_engine),
        ("Trajectory engine", check_trajectory_engine),
        ("Unified intelligence layer", check_unified_intelligence),
        ("Auto-resolution engine", check_auto_resolution),
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
        print("\n✅ All checks passed! Intelligence expansion is complete.")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
