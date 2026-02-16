#!/usr/bin/env python3
"""
Check for skipped tests without proper justification.

Skipped tests should have a reason documented.
"""

import ast
import sys
from pathlib import Path

TESTS_DIR = Path("tests")
EXCLUDE_PATTERNS = ["__pycache__", ".venv"]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_skipped_tests(filepath: Path) -> list[str]:
    """Check for skipped tests without reasons."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            # Check for @pytest.mark.skip decorators
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    skip_type = None
                    has_reason = False

                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr in ("skip", "skipif", "xfail"):
                                skip_type = decorator.func.attr
                                # Check for reason keyword
                                for kw in decorator.keywords:
                                    if kw.arg == "reason":
                                        has_reason = True
                                        break
                        elif isinstance(decorator.func, ast.Name):
                            if decorator.func.id in ("skip", "skipif", "xfail"):
                                skip_type = decorator.func.id
                                for kw in decorator.keywords:
                                    if kw.arg == "reason":
                                        has_reason = True

                    elif isinstance(decorator, ast.Attribute):
                        if decorator.attr in ("skip", "skipif", "xfail"):
                            skip_type = decorator.attr

                    if skip_type and not has_reason:
                        violations.append(
                            f"  {filepath}:{node.lineno}: @{skip_type} on {node.name}() without reason"
                        )

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return violations


def count_test_stats(filepath: Path) -> tuple[int, int]:
    """Count total tests and skipped tests."""
    total = 0
    skipped = 0

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    total += 1

                    for decorator in node.decorator_list:
                        is_skip = False
                        if isinstance(decorator, ast.Call):
                            if isinstance(decorator.func, ast.Attribute):
                                if decorator.func.attr in ("skip", "skipif", "xfail"):
                                    is_skip = True
                        elif isinstance(decorator, ast.Attribute):
                            if decorator.attr in ("skip", "skipif", "xfail"):
                                is_skip = True

                        if is_skip:
                            skipped += 1
                            break

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return total, skipped


def main() -> int:
    """Main entry point."""
    if not TESTS_DIR.exists():
        print("✅ No tests directory found.")
        return 1

    all_violations = []
    total_tests = 0
    total_skipped = 0

    for py_file in TESTS_DIR.rglob("test_*.py"):
        if should_exclude(py_file):
            continue

        violations = check_skipped_tests(py_file)
        all_violations.extend(violations)

        tests, skipped = count_test_stats(py_file)
        total_tests += tests
        total_skipped += skipped

    skip_rate = (total_skipped / total_tests * 100) if total_tests > 0 else 0

    print(f"📊 Test stats: {total_tests} total, {total_skipped} skipped ({skip_rate:.1f}%)")

    if all_violations:
        print("\n⏭️ SKIPPED TESTS WITHOUT REASON:")
        print("\n".join(all_violations[:20]))
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        print("\nAdd reason='...' to skip decorators.")

    if skip_rate > 10:
        print(f"\n⚠️ Skip rate is high ({skip_rate:.1f}%). Review and fix skipped tests.")

    return 1 if all_violations else 0  # BLOCKING


if __name__ == "__main__":
    sys.exit(main())
