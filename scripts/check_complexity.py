#!/usr/bin/env python3
"""
Check for overly complex functions.

Measures cyclomatic complexity and flags functions over threshold.
Uses radon if available, falls back to AST-based analysis.
"""

import ast
import subprocess
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "collectors", "engine", "cli"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]

# Complexity thresholds
MAX_COMPLEXITY = 15  # Cyclomatic complexity
MAX_COGNITIVE = 20  # Cognitive complexity (harder to measure)
MAX_LINES_PER_FUNCTION = 100


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def run_radon() -> list[str]:
    """Run radon for complexity analysis."""
    violations = []

    try:
        for dir_name in DIRS_TO_CHECK:
            if not Path(dir_name).exists():
                continue

            result = subprocess.run(
                ["radon", "cc", dir_name, "-a", "-nc", "--min", "C"],  # Grade C or worse
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip() and not line.startswith("Average"):
                        violations.append(f"  {line.strip()}")

    except FileNotFoundError:
        return []  # radon not installed
    except subprocess.TimeoutExpired:
        return ["  Complexity check timed out"]

    return violations


def calculate_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity of a function."""
    complexity = 1  # Base complexity

    for child in ast.walk(node):
        # Decision points increase complexity
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            complexity += 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, ast.Assert):
            complexity += 1
        elif isinstance(child, ast.comprehension):
            complexity += 1
            if child.ifs:
                complexity += len(child.ifs)
        elif isinstance(child, (ast.And, ast.Or)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.IfExp):  # Ternary
            complexity += 1

    return complexity


def count_function_lines(node: ast.AST) -> int:
    """Count lines in a function."""
    if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
        return node.end_lineno - node.lineno + 1
    return 1


def analyze_file(filepath: Path) -> list[str]:
    """Analyze a file for complex functions."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = calculate_complexity(node)
                lines = count_function_lines(node)

                if complexity > MAX_COMPLEXITY:
                    violations.append(
                        f"  {filepath}:{node.lineno}: {node.name}() "
                        f"complexity={complexity} (max {MAX_COMPLEXITY})"
                    )
                elif lines > MAX_LINES_PER_FUNCTION:
                    violations.append(
                        f"  {filepath}:{node.lineno}: {node.name}() "
                        f"lines={lines} (max {MAX_LINES_PER_FUNCTION})"
                    )

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return violations


def main() -> int:
    """Main entry point."""
    # Try radon first
    violations = run_radon()

    if not violations:
        # Fall back to AST-based analysis
        for dir_name in DIRS_TO_CHECK:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                continue

            for py_file in dir_path.rglob("*.py"):
                if should_exclude(py_file):
                    continue

                file_violations = analyze_file(py_file)
                violations.extend(file_violations)

    if violations:
        print("🧩 COMPLEX FUNCTIONS:")
        print("\n".join(violations[:30]))
        if len(violations) > 30:
            print(f"  ... and {len(violations) - 30} more")
        print("\nRefactor complex functions into smaller, focused units.")
        return 1

    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
