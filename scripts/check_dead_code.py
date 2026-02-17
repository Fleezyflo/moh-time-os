#!/usr/bin/env python3
"""
Check for dead code (unused functions, classes, variables).

Uses vulture for Python analysis.
Falls back to basic AST analysis if vulture not installed.
"""

import ast
import subprocess
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]  # Focus on core modules
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_", "_test.py"]

# Functions/classes that are entry points (not "dead" even if not imported)
ALLOWLIST = [
    "main",
    "app",
    "router",
    "spec_router",
    "intelligence_router",
    "__init__",
    "__str__",
    "__repr__",
    "setup",
    "teardown",
    "run",
    "execute",
    "handler",
    "endpoint",
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def run_vulture() -> list[str]:
    """Run vulture for dead code detection."""
    violations = []

    try:
        result = subprocess.run(
            ["vulture", "--min-confidence", "80"] + DIRS_TO_CHECK,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                # Filter out allowlisted items
                if not any(allowed in line for allowed in ALLOWLIST):
                    # Filter out low-confidence items
                    if "unused" in line.lower():
                        violations.append(f"  {line}")

    except FileNotFoundError:
        return []  # vulture not installed
    except subprocess.TimeoutExpired:
        return ["  Dead code check timed out"]

    return violations


def basic_dead_code_check() -> list[str]:
    """Basic dead code check using AST (fallback)."""
    violations = []
    all_definitions = {}  # name -> (filepath, lineno)
    all_references = set()

    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            try:
                content = py_file.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Track definitions
                    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                        if not node.name.startswith("_") and node.name not in ALLOWLIST:
                            all_definitions[node.name] = (py_file, node.lineno)
                    elif isinstance(node, ast.ClassDef):
                        if not node.name.startswith("_"):
                            all_definitions[node.name] = (py_file, node.lineno)

                    # Track references
                    elif isinstance(node, ast.Name):
                        all_references.add(node.id)
                    elif isinstance(node, ast.Attribute):
                        all_references.add(node.attr)
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            all_references.add(node.func.id)
                        elif isinstance(node.func, ast.Attribute):
                            all_references.add(node.func.attr)

            except (SyntaxError, OSError, UnicodeDecodeError):
                pass

    # Find unreferenced definitions
    for name, (filepath, lineno) in all_definitions.items():
        if name not in all_references:
            violations.append(f"  {filepath}:{lineno}: unused '{name}'")

    return violations[:20]  # Limit output


def main() -> int:
    """Main entry point."""
    # Try vulture first
    violations = run_vulture()

    if not violations:
        # Fall back to basic check
        violations = basic_dead_code_check()

    if violations:
        print("💀 POTENTIAL DEAD CODE:")
        print("\n".join(violations[:30]))
        if len(violations) > 30:
            print(f"  ... and {len(violations) - 30} more")
        print("\nReview and remove unused code, or add to allowlist if intentional.")
        # BLOCKING, don't fail
        return 1 if violations else 0  # BLOCKING

    return 1 if violations else 0  # BLOCKING


if __name__ == "__main__":
    sys.exit(main())
