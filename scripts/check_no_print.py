#!/usr/bin/env python3
"""
Check for print() statements in production code.

Production code should use logging, not print().
"""

import ast
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_", "_test.py", "debug_"]

# Files allowed to use print (CLI tools, scripts)
PRINT_ALLOWED = [
    "cli/",
    "scripts/",
    "setup.py",
    "__main__.py",
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    if any(excl in path_str for excl in EXCLUDE_PATTERNS):
        return True
    if any(allowed in path_str for allowed in PRINT_ALLOWED):
        return True
    return False


def find_print_calls(filepath: Path) -> list[tuple[int, str]]:
    """Find print() calls in a file."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    # Get the line content
                    lines = content.split("\n")
                    line = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""

                    # Skip if has noqa comment
                    if "# noqa" in line or "# type: ignore" in line:
                        continue

                    violations.append((node.lineno, line[:80]))

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

            violations = find_print_calls(py_file)
            for lineno, line in violations:
                all_violations.append(f"  {py_file}:{lineno}: {line}")

    if all_violations:
        print("🖨️ PRINT STATEMENTS IN PRODUCTION CODE:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nUse logging.info/debug/warning instead of print().")
        print("Add '# noqa' to suppress if intentional.")
        # BLOCKING for now
        return 1 if all_violations else 0  # BLOCKING

    print("✅ No print() in production code.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
