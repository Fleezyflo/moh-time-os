#!/usr/bin/env python3
"""
Check for unused dependencies.

Uses deptry for Python analysis.
"""

import subprocess
import sys
from pathlib import Path


def check_python_deps() -> list[str]:
    """Check for unused Python dependencies."""
    violations = []

    try:
        result = subprocess.run(
            ["deptry", ".", "--ignore-notebooks"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0 and result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip() and "DEP" in line:
                    violations.append(f"  {line.strip()}")

    except FileNotFoundError:
        # deptry not installed, try basic check
        return check_python_deps_basic()
    except subprocess.TimeoutExpired:
        violations.append("  Dependency check timed out")

    return violations


def check_python_deps_basic() -> list[str]:
    """Basic unused dependency check without deptry."""
    violations = []

    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return violations

    try:
        import tomllib
        content = pyproject.read_text()
        data = tomllib.loads(content)
    except ImportError:
        import tomli as tomllib
        content = pyproject.read_text()
        data = tomllib.loads(content)
    except Exception:
        return violations

    # Get declared dependencies
    deps = data.get("project", {}).get("dependencies", [])
    dep_names = set()
    for dep in deps:
        # Extract package name from dependency string
        name = dep.split("[")[0].split(">=")[0].split("==")[0].split("<")[0].strip()
        dep_names.add(name.lower().replace("-", "_"))

    # Scan for imports
    used_imports = set()
    for dir_name in ["lib", "api", "collectors", "engine", "cli"]:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            try:
                content = py_file.read_text()
                # Basic import extraction
                for line in content.split("\n"):
                    if line.startswith("import ") or line.startswith("from "):
                        parts = line.split()
                        if len(parts) >= 2:
                            module = parts[1].split(".")[0].lower().replace("-", "_")
                            used_imports.add(module)
            except Exception:
                pass

    # Find unused
    for dep in dep_names:
        if dep not in used_imports:
            # Check common aliases
            aliases = {
                "pyyaml": "yaml",
                "pillow": "pil",
                "python_dateutil": "dateutil",
            }
            if aliases.get(dep, dep) not in used_imports:
                violations.append(f"  Possibly unused: {dep}")

    return violations[:10]  # Limit output


def main() -> int:
    """Main entry point."""
    violations = check_python_deps()

    if violations:
        print("📦 POTENTIALLY UNUSED DEPENDENCIES:")
        print("\n".join(violations[:20]))
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")
        print("\nRemove unused dependencies to reduce attack surface.")
        # BLOCKING
        return 1 if violations else 0  # BLOCKING

    print("✅ No unused dependencies detected.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
