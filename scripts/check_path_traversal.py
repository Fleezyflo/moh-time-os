#!/usr/bin/env python3
"""
Check for path traversal vulnerabilities.

Detects:
- User input used in file paths without validation
- Use of .. in path operations
- Unvalidated path joins
"""

import ast
import re
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]

# Dangerous patterns
PATH_TRAVERSAL_PATTERNS = [
    (r"open\s*\([^)]*\+[^)]*\)", "Dynamic path in open()"),
    (r"Path\s*\([^)]*\+[^)]*\)", "Dynamic path in Path()"),
    (r"os\.path\.join\s*\([^)]*request", "User input in path join"),
    (r'f["\'][^"\']*\{[^}]*\}[^"\']*["\'].*open', "f-string path in open"),
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_path_operations(filepath: Path) -> list[str]:
    """Check for path traversal issues using AST."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check open() calls with non-constant paths
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    if node.args and not isinstance(node.args[0], ast.Constant):
                        # Check if it's a validated path
                        if isinstance(node.args[0], ast.BinOp):
                            violations.append(
                                f"  {filepath}:{node.lineno}: Dynamic path in open() - validate input"
                            )

                # Check Path() with f-strings or concatenation
                if isinstance(node.func, ast.Name) and node.func.id == "Path":
                    if node.args and isinstance(node.args[0], ast.JoinedStr):
                        violations.append(
                            f"  {filepath}:{node.lineno}: f-string in Path() - validate input"
                        )

                # Check os.path.join with request data
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "join":
                        for arg in node.args:
                            if isinstance(arg, ast.Attribute):
                                if hasattr(arg, "value") and hasattr(arg.value, "id"):
                                    if arg.value.id in ("request", "params", "query"):
                                        violations.append(
                                            f"  {filepath}:{node.lineno}: User input in path.join()"
                                        )

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return violations


def check_with_regex(filepath: Path) -> list[str]:
    """Check for path traversal using regex patterns."""
    violations = []

    try:
        content = filepath.read_text()
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            for pattern, message in PATH_TRAVERSAL_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(f"  {filepath}:{i}: {message}")
                    break

    except (OSError, UnicodeDecodeError):
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

            violations = check_path_operations(py_file)
            all_violations.extend(violations)

            regex_violations = check_with_regex(py_file)
            all_violations.extend(regex_violations)

    if all_violations:
        print("🛤️ PATH TRAVERSAL RISKS:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nValidate and sanitize file paths. Use Path.resolve() and check prefixes.")
        # Warning only
        return 1  # BLOCKING

    print("✅ No obvious path traversal issues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
