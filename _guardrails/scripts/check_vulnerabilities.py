#!/usr/bin/env python3
"""
Check for vulnerable dependencies.

Uses pip-audit for Python and pnpm audit for Node.
"""

import json
import subprocess
import sys
from pathlib import Path


def check_python_vulnerabilities() -> list[str]:
    """Check Python dependencies for vulnerabilities."""
    violations = []

    try:
        # Run pip-audit
        result = subprocess.run(
            ["pip-audit", "--format", "json", "--strict"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            try:
                data = json.loads(result.stdout)
                for vuln in data.get("dependencies", []):
                    name = vuln.get("name", "unknown")
                    version = vuln.get("version", "?")
                    for v in vuln.get("vulns", []):
                        vuln_id = v.get("id", "?")
                        fix = v.get("fix_versions", ["upgrade"])
                        violations.append(f"  Python: {name}=={version} ({vuln_id}) - fix: {fix}")
            except json.JSONDecodeError:
                # Parse text output as fallback
                if "found" in result.stdout.lower() and "vulnerabilit" in result.stdout.lower():
                    violations.append(f"  Python: {result.stdout.strip()[:200]}")

    except FileNotFoundError:
        # pip-audit not installed, try safety
        try:
            result = subprocess.run(
                ["safety", "check", "--json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                violations.append("  Python: Run 'pip install pip-audit' to check vulnerabilities")
        except FileNotFoundError:
            pass  # Neither installed, skip
    except subprocess.TimeoutExpired:
        violations.append("  Python: Vulnerability check timed out")
    except Exception as e:
        violations.append(f"  Python: Error checking vulnerabilities: {e}")

    return violations


def check_node_vulnerabilities() -> list[str]:
    """Check Node.js dependencies for vulnerabilities."""
    violations = []
    ui_dir = Path("time-os-ui")

    if not ui_dir.exists():
        return violations

    try:
        result = subprocess.run(
            ["pnpm", "audit", "--json"],
            capture_output=True,
            text=True,
            cwd=ui_dir,
            timeout=120,
        )

        if result.returncode != 0:
            try:
                # pnpm audit returns structured JSON
                data = json.loads(result.stdout)
                advisories = data.get("advisories", {})
                for adv_id, adv in advisories.items():
                    name = adv.get("module_name", "unknown")
                    severity = adv.get("severity", "unknown")
                    title = adv.get("title", "Unknown vulnerability")
                    if severity in ["critical", "high"]:
                        violations.append(f"  Node: {name} [{severity}] - {title}")
            except json.JSONDecodeError:
                # Check for non-JSON output indicating issues
                if "vulnerabilit" in result.stdout.lower() or "critical" in result.stdout.lower():
                    lines = result.stdout.strip().split("\n")[:5]
                    for line in lines:
                        if line.strip():
                            violations.append(f"  Node: {line.strip()[:100]}")

    except FileNotFoundError:
        pass  # pnpm not installed
    except subprocess.TimeoutExpired:
        violations.append("  Node: Vulnerability check timed out")
    except Exception as e:
        violations.append(f"  Node: Error checking vulnerabilities: {e}")

    return violations


def main() -> int:
    """Main entry point."""
    violations = []

    print("Checking for vulnerable dependencies...")

    python_vulns = check_python_vulnerabilities()
    violations.extend(python_vulns)

    node_vulns = check_node_vulnerabilities()
    violations.extend(node_vulns)

    # Filter to only critical/high severity
    critical_violations = [
        v for v in violations if "critical" in v.lower() or "high" in v.lower() or "Error" in v
    ]

    if critical_violations:
        print("🚨 VULNERABLE DEPENDENCIES (Critical/High):")
        print("\n".join(critical_violations))
        print("\nRun 'pip-audit --fix' or 'pnpm audit fix' to resolve.")
        return 1

    if violations:
        print("⚠️ VULNERABLE DEPENDENCIES (Low/Medium - warning only):")
        print("\n".join(violations[:10]))
        # Don't fail on low/medium, just warn
        return 1  # BLOCKING

    print("✅ No critical vulnerabilities found.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
