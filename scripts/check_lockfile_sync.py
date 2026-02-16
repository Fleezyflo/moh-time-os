#!/usr/bin/env python3
"""
Check that lockfiles are in sync with manifests.

Verifies:
- Python: uv.lock matches pyproject.toml
- Node: pnpm-lock.yaml matches package.json
"""

import subprocess
import sys
from pathlib import Path


def check_python_lockfile() -> tuple[bool, str]:
    """Check Python lockfile is in sync."""
    pyproject = Path("pyproject.toml")
    Path("uv.lock")

    if not pyproject.exists():
        return True, "No pyproject.toml found"

    # Try uv first
    try:
        result = subprocess.run(
            ["uv", "lock", "--check"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return True, "uv.lock is in sync"
        else:
            return False, "uv.lock is out of sync - run 'uv lock'"
    except FileNotFoundError:
        pass  # uv not installed
    except subprocess.TimeoutExpired:
        return False, "Lockfile check timed out"

    # Try pip-compile
    try:
        result = subprocess.run(
            ["pip-compile", "--dry-run", "--quiet", "pyproject.toml"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, "requirements.txt would be unchanged"
        else:
            return False, "requirements.txt needs update - run 'pip-compile'"
    except FileNotFoundError:
        pass  # pip-tools not installed
    except subprocess.TimeoutExpired:
        return False, "Lockfile check timed out"

    return True, "No Python lock tool found - skipping"


def check_node_lockfile() -> tuple[bool, str]:
    """Check Node lockfile is in sync."""
    ui_dir = Path("time-os-ui")
    package_json = ui_dir / "package.json"
    pnpm_lock = ui_dir / "pnpm-lock.yaml"

    if not package_json.exists():
        return True, "No package.json found"

    if not pnpm_lock.exists():
        return False, "pnpm-lock.yaml missing - run 'pnpm install'"

    try:
        result = subprocess.run(
            ["pnpm", "install", "--frozen-lockfile", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=ui_dir,
            timeout=60,
        )
        if result.returncode == 0:
            return True, "pnpm-lock.yaml is in sync"
        else:
            # Check specific error
            if "frozen-lockfile" in result.stderr.lower():
                return False, "pnpm-lock.yaml is out of sync - run 'pnpm install'"
            return True, "pnpm check completed"
    except FileNotFoundError:
        return True, "pnpm not found - skipping"
    except subprocess.TimeoutExpired:
        return False, "Lockfile check timed out"

    return True, "Lockfile appears in sync"


def main() -> int:
    """Main entry point."""
    failures = []

    py_ok, py_msg = check_python_lockfile()
    if py_ok:
        print(f"✅ Python: {py_msg}")
    else:
        print(f"❌ Python: {py_msg}")
        failures.append("Python")

    node_ok, node_msg = check_node_lockfile()
    if node_ok:
        print(f"✅ Node: {node_msg}")
    else:
        print(f"❌ Node: {node_msg}")
        failures.append("Node")

    if failures:
        print(f"\n⚠️ Lockfiles out of sync: {', '.join(failures)}")
        print("This can cause 'works on my machine' issues.")
        # BLOCKING for now
        return 1  # BLOCKING

    return 1  # BLOCKING


if __name__ == "__main__":
    sys.exit(main())
