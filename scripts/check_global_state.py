#!/usr/bin/env python3
"""
Check for dangerous global mutable state.

Detects:
- Global mutable variables (lists, dicts, sets)
- Module-level mutable state without locks
- Shared state that could cause race conditions
"""

import ast
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_", "config", "constants"]

# Types that are mutable
MUTABLE_TYPES = {"list", "dict", "set", "List", "Dict", "Set"}

# Safe patterns (constants, config, etc.)
SAFE_PATTERNS = [
    "CONST",
    "CONFIG",
    "SETTINGS",
    "DEFAULTS",
    "PATTERNS",
    "ALLOWED",
    "EXCLUDE",
    "_",  # Private/internal
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def is_safe_name(name: str) -> bool:
    """Check if variable name suggests it's a constant."""
    return any(pattern in name.upper() for pattern in SAFE_PATTERNS) or name.isupper()


def check_global_state(filepath: Path) -> list[str]:
    """Check for global mutable state."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        # Check module-level assignments
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id

                        # Skip if safe pattern
                        if is_safe_name(name):
                            continue

                        # Check if assigned a mutable value
                        value = node.value
                        is_mutable = False

                        if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                            is_mutable = True
                        elif isinstance(value, ast.Call):
                            if isinstance(value.func, ast.Name):
                                if value.func.id in MUTABLE_TYPES:
                                    is_mutable = True

                        if is_mutable:
                            violations.append(
                                f"  {filepath}:{node.lineno}: Global mutable '{name}' - use constant or encapsulate"
                            )

            # Check annotated assignments
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    name = node.target.id

                    if is_safe_name(name):
                        continue

                    if node.value:
                        if isinstance(node.value, (ast.List, ast.Dict, ast.Set)):
                            violations.append(
                                f"  {filepath}:{node.lineno}: Global mutable '{name}' - use constant or encapsulate"
                            )

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return violations


def main() -> int:
    """Main entry point."""
    all_violations = []

    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            violations = check_global_state(py_file)
            all_violations.extend(violations)

    if all_violations:
        print("🌍 GLOBAL MUTABLE STATE:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nGlobal mutable state can cause race conditions in concurrent code.")
        print("Consider: frozen dataclasses, module-level functions, or dependency injection.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING

    print("✅ No dangerous global mutable state.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
