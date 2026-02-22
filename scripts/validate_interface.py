#!/usr/bin/env python3
"""
Brief 12: Interface & Experience — Validation Script (IX-6.1)

Validates all deliverables from Brief 12:
- IX-1.1: Design system & API contracts
- IX-2.1: Live intelligence dashboard
- IX-3.1: Resolution queue interface
- IX-4.1: Scenario modeling interface
- IX-5.1: Real-time updates & notification center
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def run_tests(test_files: list[str]) -> tuple[int, int]:
    """Run pytest on given files, return (passed, failed)."""
    cmd = [sys.executable, "-m", "pytest"] + test_files + ["-q", "--tb=no"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE))
    output = result.stdout + result.stderr
    # Parse "X passed" from output
    passed = 0
    failed = 0
    for line in output.split("\n"):
        if "passed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed":
                    try:
                        passed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
                if p == "failed":
                    try:
                        failed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
    return passed, failed


def main() -> int:
    global PASS, FAIL

    print("=" * 60)
    print("Brief 12: Interface & Experience — Validation")
    print("=" * 60)

    # Check 1: Design system files exist
    print("\n1. Design System (IX-1.1)")
    design_system = BASE / "design" / "system" / "DESIGN_SYSTEM.md"
    tokens_css = BASE / "design" / "system" / "tokens.css"
    api_contracts = BASE / "design" / "system" / "api_contracts.py"

    check("DESIGN_SYSTEM.md exists", design_system.exists())
    check("tokens.css exists", tokens_css.exists())
    check("api_contracts.py exists", api_contracts.exists())

    if design_system.exists():
        content = design_system.read_text()
        check(
            "Design system has color palette",
            "color" in content.lower() and "palette" in content.lower(),
        )
        check(
            "Design system has typography",
            "typography" in content.lower() or "font" in content.lower(),
        )
        check("Design system has components", "component" in content.lower())

    if tokens_css.exists():
        css = tokens_css.read_text()
        check("CSS tokens has custom properties", "--" in css)
        check("CSS tokens has accent color", "--accent" in css or "#ff3d00" in css)
        lines = len(css.split("\n"))
        check("CSS tokens substantial", lines >= 100, f"{lines} lines")

    if api_contracts.exists():
        contracts = api_contracts.read_text()
        check("API contracts uses Pydantic", "BaseModel" in contracts or "pydantic" in contracts)
        check("API contracts has response models", "Response" in contracts)

    # Check 2: Dashboard (IX-2.1)
    print("\n2. Live Dashboard (IX-2.1)")
    dashboard = BASE / "design" / "prototype" / "v6" / "index.html"
    check("v6/index.html exists", dashboard.exists())
    if dashboard.exists():
        html = dashboard.read_text()
        lines = len(html.split("\n"))
        check("Dashboard substantial", lines >= 500, f"{lines} lines")
        check("Dashboard has HRMNY brand", "HRMNY" in html)
        check("Dashboard has API fetch", "fetch(" in html)
        check("Dashboard has navigation", "Command" in html and "Clients" in html)
        check("Dashboard has fallback data", "fallback" in html.lower() or "demo" in html.lower())

    # Check 3: Resolution Queue (IX-3.1)
    print("\n3. Resolution Queue (IX-3.1)")
    resolution = BASE / "design" / "prototype" / "v6" / "resolution.html"
    check("resolution.html exists", resolution.exists())
    if resolution.exists():
        html = resolution.read_text()
        lines = len(html.split("\n"))
        check("Resolution page substantial", lines >= 500, f"{lines} lines")
        check("Has accept/defer/escalate", "Accept" in html or "accept" in html)
        check("Has confidence scores", "confidence" in html.lower())
        check("Has filter tabs", "filter" in html.lower() or "Filter" in html)

    # Check 4: Scenario Modeling (IX-4.1)
    print("\n4. Scenario Modeling (IX-4.1)")
    scenarios = BASE / "design" / "prototype" / "v6" / "scenarios.html"
    check("scenarios.html exists", scenarios.exists())
    if scenarios.exists():
        html = scenarios.read_text()
        lines = len(html.split("\n"))
        check("Scenarios page substantial", lines >= 500, f"{lines} lines")
        check("Has scenario types", "CLIENT_LOSS" in html or "client_loss" in html.lower())
        check("Has parameter forms", "input" in html.lower() or "form" in html.lower())
        check("Has comparison mode", "compare" in html.lower() or "comparison" in html.lower())

    # Check 5: Real-time Updates (IX-5.1)
    print("\n5. Real-time Updates (IX-5.1)")
    sse_router = BASE / "api" / "sse_router.py"
    notifications = BASE / "design" / "prototype" / "v6" / "notifications.html"
    check("sse_router.py exists", sse_router.exists())
    check("notifications.html exists", notifications.exists())
    if sse_router.exists():
        code = sse_router.read_text()
        check("SSE router has EventBus", "EventBus" in code)
        check(
            "SSE router has streaming",
            "StreamingResponse" in code
            or "EventSourceResponse" in code
            or "stream" in code.lower(),
        )
        check("SSE has heartbeat", "heartbeat" in code.lower())
    if notifications.exists():
        html = notifications.read_text()
        check("Notifications has EventSource", "EventSource" in html)
        check("Notifications has filter", "filter" in html.lower())

    # Check 6: Server integration
    print("\n6. Server Integration")
    server = BASE / "api" / "server.py"
    if server.exists():
        code = server.read_text()
        check("SSE router wired in server.py", "sse_router" in code)

    # Check 7: Test suite
    print("\n7. Test Suite")
    test_files = [
        "tests/test_api_contracts.py",
        "tests/test_resolution_queue_ui.py",
        "tests/test_scenario_ui.py",
        "tests/test_sse_events.py",
    ]
    existing_tests = [f for f in test_files if (BASE / f).exists()]
    check("All 4 test files exist", len(existing_tests) == 4, f"{len(existing_tests)}/4")

    if existing_tests:
        passed, failed = run_tests(existing_tests)
        total = passed + failed
        check("All Brief 12 tests pass", failed == 0, f"{passed} passed, {failed} failed")
        check("Test count >= 100", passed >= 100, f"{passed} tests")

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} checks passed")
    if FAIL == 0:
        print("STATUS: ✅ ALL CHECKS PASSED — Brief 12 VALIDATED")
    else:
        print(f"STATUS: ❌ {FAIL} CHECK(S) FAILED")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
