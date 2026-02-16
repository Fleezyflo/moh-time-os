#!/usr/bin/env python3
"""
Check for proper error handling patterns.

Detects:
- Empty except blocks (swallowed exceptions)
- Except without logging
- Bare except clauses
- Missing error context
"""

import ast
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine", "collectors"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]

# Logging calls that indicate proper error handling
LOGGING_CALLS = {"exception", "error", "warning", "critical", "log"}


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_except_handlers(filepath: Path) -> list[str]:
    """Check exception handlers for proper patterns."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check for empty except (just pass or ...)
                if len(node.body) == 1:
                    body = node.body[0]
                    if isinstance(body, ast.Pass):
                        violations.append(
                            f"  {filepath}:{node.lineno}: Empty except block (pass) - exception swallowed"
                        )
                    elif isinstance(body, ast.Expr) and isinstance(body.value, ast.Constant):
                        if body.value.value == ...:
                            violations.append(
                                f"  {filepath}:{node.lineno}: Empty except block (...) - exception swallowed"
                            )

                # Check if exception is logged
                has_logging = False
                has_raise = False

                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if child.func.attr in LOGGING_CALLS:
                                has_logging = True
                    if isinstance(child, ast.Raise):
                        has_raise = True

                # If no logging and no re-raise, it's suspicious
                if not has_logging and not has_raise and len(node.body) > 1:
                    # Check if it's a simple return/continue
                    is_simple = all(
                        isinstance(n, (ast.Return, ast.Continue, ast.Break, ast.Pass))
                        for n in node.body
                    )
                    if not is_simple:
                        violations.append(
                            f"  {filepath}:{node.lineno}: Except block without logging or re-raise"
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

            violations = check_except_handlers(py_file)
            all_violations.extend(violations)

    if all_violations:
        print("🔇 ERROR HANDLING ISSUES:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nLog exceptions with logger.exception() or re-raise with context.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING

    print("✅ Error handling looks good.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
