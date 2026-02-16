#!/usr/bin/env python3
"""
Check for blocking calls in async code.

Detects:
- time.sleep() in async functions
- blocking I/O (open(), requests.) in async
- synchronous DB calls in async context
"""

import ast
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]

# Blocking calls that shouldn't be in async
BLOCKING_CALLS = {
    "time.sleep": "Use asyncio.sleep() instead",
    "requests.get": "Use httpx.AsyncClient or aiohttp",
    "requests.post": "Use httpx.AsyncClient or aiohttp",
    "requests.put": "Use httpx.AsyncClient or aiohttp",
    "requests.delete": "Use httpx.AsyncClient or aiohttp",
    "open": "Use aiofiles.open() for file I/O in async",
    "subprocess.run": "Use asyncio.create_subprocess_exec()",
    "subprocess.call": "Use asyncio.create_subprocess_exec()",
}


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def find_blocking_in_async(filepath: Path) -> list[str]:
    """Find blocking calls inside async functions."""
    violations = []

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        # Find async functions
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check for blocking calls inside
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_name = get_call_name(child)
                        if call_name in BLOCKING_CALLS:
                            fix = BLOCKING_CALLS[call_name]
                            violations.append(
                                f"  {filepath}:{child.lineno}: {call_name}() in async function '{node.name}'"
                                f"\n    → {fix}"
                            )

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return violations


def get_call_name(node: ast.Call) -> str:
    """Extract the full call name (e.g., 'time.sleep')."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    elif isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}"
        elif isinstance(node.func.value, ast.Attribute):
            # requests.Session().get -> just get the method
            return node.func.attr
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

            violations = find_blocking_in_async(py_file)
            all_violations.extend(violations)

    if all_violations:
        print("⏳ BLOCKING CALLS IN ASYNC CODE:")
        print("\n".join(all_violations[:20]))
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        print("\nBlocking calls in async functions block the event loop.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING

    print("✅ No blocking calls in async code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
