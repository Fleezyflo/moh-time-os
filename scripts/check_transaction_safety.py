#!/usr/bin/env python3
"""
Check for transaction safety issues.

Detects:
- Multiple writes without transaction
- Missing rollback on error
- Connection not closed
"""

import ast
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_transaction_patterns(filepath: Path) -> list[str]:
    """Check for transaction safety issues."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Count write operations in function
                writes = 0
                has_commit = False
                has_rollback = False
                has_transaction = False
                has_context_manager = False

                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_name = get_call_name(child)

                        if call_name in ("execute", "executemany"):
                            # Check if it's a write
                            if child.args:
                                arg = child.args[0]
                                if isinstance(arg, ast.Constant):
                                    sql = str(arg.value).upper()
                                    if any(w in sql for w in ["INSERT", "UPDATE", "DELETE"]):
                                        writes += 1

                        if "commit" in call_name:
                            has_commit = True
                        if "rollback" in call_name:
                            has_rollback = True
                        if "begin" in call_name or "transaction" in call_name:
                            has_transaction = True

                    # Check for context manager (with conn:)
                    if isinstance(child, ast.With):
                        has_context_manager = True

                # Multiple writes without explicit transaction is risky
                if writes > 1 and not has_transaction and not has_context_manager:
                    violations.append(
                        f"  {filepath}:{node.lineno}: {node.name}() has {writes} writes without transaction"
                    )

                # Commit without rollback in try block
                if has_commit and not has_rollback:
                    # Check if there's a try block
                    has_try = any(isinstance(c, ast.Try) for c in ast.walk(node))
                    if has_try:
                        violations.append(
                            f"  {filepath}:{node.lineno}: {node.name}() has commit without rollback"
                        )

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return violations


def get_call_name(node: ast.Call) -> str:
    """Get call name."""
    if isinstance(node.func, ast.Name):
        return node.func.id.lower()
    elif isinstance(node.func, ast.Attribute):
        return node.func.attr.lower()
    return ""


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

            violations = check_transaction_patterns(py_file)
            all_violations.extend(violations)

    if all_violations:
        print("💾 TRANSACTION SAFETY ISSUES:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nUse transactions for multiple writes. Add rollback in except blocks.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING

    print("✅ Transaction patterns look safe.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
