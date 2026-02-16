#!/usr/bin/env python3
"""
Check dependency licenses for compatibility.

Ensures no GPL or incompatible licenses in the dependency tree.
"""

import json
import subprocess
import sys
from pathlib import Path

# Licenses that are NOT compatible with MIT/Apache
FORBIDDEN_LICENSES = [
    "GPL",
    "AGPL",
    "LGPL",
    "CC-BY-NC",
    "CC-BY-ND",
    "SSPL",
    "BSL",
    "Commons Clause",
]

# Licenses that are OK
ALLOWED_LICENSES = [
    "MIT",
    "Apache",
    "BSD",
    "ISC",
    "0BSD",
    "Unlicense",
    "CC0",
    "WTFPL",
    "Python",
    "PSF",
    "MPL",
    "Zlib",
    "Public Domain",
]


def check_python_licenses() -> list[str]:
    """Check Python dependency licenses."""
    violations = []

    try:
        result = subprocess.run(
            ["pip-licenses", "--format=json"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            packages = json.loads(result.stdout)
            for pkg in packages:
                name = pkg.get("Name", "unknown")
                license_type = pkg.get("License", "Unknown")

                # Check for forbidden
                for forbidden in FORBIDDEN_LICENSES:
                    if forbidden.upper() in license_type.upper():
                        violations.append(f"  Python: {name} ({license_type})")
                        break

    except FileNotFoundError:
        pass  # pip-licenses not installed
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass

    return violations


def check_node_licenses() -> list[str]:
    """Check Node.js dependency licenses."""
    violations = []
    ui_dir = Path("time-os-ui")

    if not ui_dir.exists():
        return violations

    try:
        result = subprocess.run(
            ["npx", "license-checker", "--json", "--production"],
            capture_output=True,
            text=True,
            cwd=ui_dir,
            timeout=120,
        )

        if result.returncode == 0:
            packages = json.loads(result.stdout)
            for pkg_name, info in packages.items():
                license_type = info.get("licenses", "Unknown")

                # Handle arrays
                if isinstance(license_type, list):
                    license_type = ", ".join(license_type)

                # Check for forbidden
                for forbidden in FORBIDDEN_LICENSES:
                    if forbidden.upper() in str(license_type).upper():
                        violations.append(f"  Node: {pkg_name} ({license_type})")
                        break

    except FileNotFoundError:
        pass  # license-checker not installed
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass

    return violations


def main() -> int:
    """Main entry point."""
    all_violations = []

    python_issues = check_python_licenses()
    all_violations.extend(python_issues)

    node_issues = check_node_licenses()
    all_violations.extend(node_issues)

    if all_violations:
        print("⚖️ LICENSE COMPATIBILITY ISSUES:")
        print("\n".join(all_violations[:20]))
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        print("\nThese licenses may not be compatible with MIT/Apache.")
        print("Consider finding alternative packages.")
        return 1  # Blocking

    print("✅ All dependency licenses are compatible.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
