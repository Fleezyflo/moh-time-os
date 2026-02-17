#!/usr/bin/env python3
"""
Check that list endpoints have pagination.

All endpoints returning lists should support pagination to prevent OOM.
"""

import ast
import re
import sys
from pathlib import Path

API_DIR = Path("api")
EXCLUDE_PATTERNS = ["_archive", "__pycache__", "test_"]

# Patterns indicating a list endpoint
LIST_PATTERNS = [
    r"return\s+\[",
    r"return\s+list\s*\(",
    r"\.fetchall\s*\(",
    r'return\s+\{\s*["\']items["\']\s*:',
    r'return\s+\{\s*["\']data["\']\s*:',
]

# Patterns indicating pagination is implemented
PAGINATION_PATTERNS = [
    r"limit\s*[=:]",
    r"offset\s*[=:]",
    r"page\s*[=:]",
    r"skip\s*[=:]",
    r"cursor\s*[=:]",
    r"Pagination",
    r"paginate",
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def extract_endpoints(filepath: Path) -> list[tuple[int, str, str]]:
    """Extract endpoint functions from file."""
    endpoints = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if it has route decorator
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr in ("get", "post"):
                                # Get the path
                                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                    path = decorator.args[0].value
                                    # Get function body
                                    func_start = node.lineno
                                    func_end = (
                                        node.end_lineno
                                        if hasattr(node, "end_lineno")
                                        else node.lineno + 50
                                    )
                                    lines = content.split("\n")[func_start - 1 : func_end]
                                    body = "\n".join(lines)
                                    endpoints.append((node.lineno, path, body))

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return endpoints


def check_list_endpoints(filepath: Path) -> list[str]:
    """Check list endpoints for pagination."""
    violations = []

    endpoints = extract_endpoints(filepath)

    for lineno, path, body in endpoints:
        # Check if it returns a list
        is_list_endpoint = any(re.search(p, body) for p in LIST_PATTERNS)

        if is_list_endpoint:
            # Check if pagination is implemented
            has_pagination = any(re.search(p, body, re.IGNORECASE) for p in PAGINATION_PATTERNS)

            if not has_pagination:
                violations.append(f"  {filepath}:{lineno}: {path} returns list without pagination")

    return violations


def main() -> int:
    """Main entry point."""
    if not API_DIR.exists():
        print("✅ No API directory found.")
        return 1

    all_violations = []

    for py_file in API_DIR.rglob("*.py"):
        if should_exclude(py_file):
            continue

        violations = check_list_endpoints(py_file)
        all_violations.extend(violations)

    if all_violations:
        print("📜 LIST ENDPOINTS WITHOUT PAGINATION:")
        print("\n".join(all_violations[:20]))
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        print("\nAdd limit/offset or cursor-based pagination to prevent OOM.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING

    print("✅ List endpoints have pagination.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
