#!/usr/bin/env python3
"""
Check for dead code using vulture.

Vulture is a proper dead code detector that understands Python semantics.
No fallback to naive AST analysis - that produces too many false positives.
"""

import subprocess
import sys

DIRS_TO_CHECK = ["lib", "api", "engine"]

# Minimal allowlist - only genuine entry points that vulture can't detect
ALLOWLIST = [
    # FastAPI app/routers (instantiated by framework)
    "app",
    "router",
    "spec_router",
    "intelligence_router",
    # Dunder methods (called by Python runtime)
    "__init__",
    "__str__",
    "__repr__",
    "__enter__",
    "__exit__",
    # Test fixtures
    "setup",
    "teardown",
]


def main() -> int:
    """Main entry point."""
    try:
        result = subprocess.run(
            ["vulture", "--min-confidence", "80"] + DIRS_TO_CHECK,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print("⚠️ vulture not installed, skipping dead code check")
        return 0
    except subprocess.TimeoutExpired:
        print("⚠️ Dead code check timed out")
        return 1

    if not result.stdout.strip():
        print("✅ No dead code found")
        return 0

    # Filter violations
    violations = []
    for line in result.stdout.strip().split("\n"):
        # Skip allowlisted items
        if any(f"'{allowed}'" in line for allowed in ALLOWLIST):
            continue
        violations.append(f"  {line}")

    if violations:
        print("💀 DEAD CODE FOUND:")
        for v in violations:
            print(v)
        print("\nFix these issues:")
        print("  - Remove unused imports")
        print("  - Delete unreachable code")
        print("  - Remove unused functions/variables")
        return 1

    print("✅ No dead code found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
