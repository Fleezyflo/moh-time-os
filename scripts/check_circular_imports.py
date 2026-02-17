#!/usr/bin/env python3
"""
Check for circular imports.

Builds an import graph and detects cycles that would cause ImportError at runtime.
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "collectors", "engine", "cli"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def get_module_name(filepath: Path) -> str:
    """Convert file path to module name."""
    parts = list(filepath.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def extract_imports(filepath: Path) -> list[str]:
    """Extract imported module names from a Python file."""
    imports = []
    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:  # Absolute imports only
                    imports.append(node.module)
    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return imports


def build_import_graph() -> dict[str, set[str]]:
    """Build a graph of module -> imported modules."""
    graph = defaultdict(set)

    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            module = get_module_name(py_file)
            imports = extract_imports(py_file)

            # Filter to only internal imports
            for imp in imports:
                if any(imp.startswith(d) for d in DIRS_TO_CHECK):
                    graph[module].add(imp)

    return dict(graph)


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find all cycles in the import graph using DFS."""
    cycles = []
    visited = set()
    rec_stack = []
    rec_set = set()

    def dfs(node: str):
        visited.add(node)
        rec_stack.append(node)
        rec_set.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                cycle = dfs(neighbor)
                if cycle:
                    return cycle
            elif neighbor in rec_set:
                # Found a cycle
                cycle_start = rec_stack.index(neighbor)
                return rec_stack[cycle_start:] + [neighbor]

        rec_stack.pop()
        rec_set.remove(node)
        return None

    for node in graph:
        if node not in visited:
            cycle = dfs(node)
            if cycle and cycle not in cycles:
                cycles.append(cycle)

    return cycles


def main() -> int:
    """Main entry point."""
    print("Building import graph...")
    graph = build_import_graph()

    print(f"Analyzing {len(graph)} modules for cycles...")
    cycles = find_cycles(graph)

    if cycles:
        print("🔄 CIRCULAR IMPORTS DETECTED:")
        for i, cycle in enumerate(cycles[:10], 1):
            cycle_str = " -> ".join(cycle)
            print(f"  {i}. {cycle_str}")
        if len(cycles) > 10:
            print(f"  ... and {len(cycles) - 10} more cycles")
        print("\nBreak cycles by:")
        print("  - Moving shared code to a common module")
        print("  - Using late imports (inside functions)")
        print("  - Restructuring module boundaries")
        return 1

    print("✅ No circular imports detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
