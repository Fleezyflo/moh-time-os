#!/usr/bin/env python3
"""
Check for import boundary violations.

Enforces architectural layers:
- api/ can import from lib/, engine/
- api/ CANNOT import from cli/, collectors/
- lib/ can import from lib/ (internal)
- lib/ CANNOT import from api/, cli/, collectors/
- cli/ can import from lib/, engine/, api/
- collectors/ can import from lib/, engine/
- collectors/ CANNOT import from api/, cli/
- engine/ can import from lib/
- engine/ CANNOT import from api/, cli/, collectors/
"""

import ast
import sys
from pathlib import Path

# Define allowed imports for each layer
IMPORT_RULES = {
    "api": {
        "allowed": ["lib", "engine"],
        "forbidden": ["cli", "collectors"],
    },
    "lib": {
        "allowed": ["lib"],  # Internal only
        "forbidden": ["api", "cli", "collectors"],
    },
    "cli": {
        "allowed": ["lib", "engine", "api"],
        "forbidden": ["collectors"],
    },
    "collectors": {
        "allowed": ["lib", "engine"],
        "forbidden": ["api", "cli"],
    },
    "engine": {
        "allowed": ["lib", "engine"],
        "forbidden": ["api", "cli", "collectors"],
    },
}

EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_", "_test.py"]

# Allowed exceptions - specific files that legitimately need cross-boundary imports
# These are legacy patterns that would require significant refactoring
ALLOWED_EXCEPTIONS = {
    "lib/collector_registry.py": ["collectors"],  # Registry needs to know about collectors
    "lib/enrollment_detector.py": ["collectors"],  # Enrollment integrates with collectors
    "lib/autonomous_loop.py": ["collectors"],  # Autonomous loop orchestrates collectors
    "lib/collectors/orchestrator.py": [
        "collectors"
    ],  # Collector orchestrator delegates to collectors
}


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def get_layer(filepath: Path) -> str | None:
    """Get the architectural layer for a file."""
    parts = filepath.parts
    for layer in IMPORT_RULES:
        if layer in parts:
            return layer
    return None


def extract_imports(filepath: Path) -> list[tuple[int, str]]:
    """Extract all imports from a Python file. Returns (line_num, module_name)."""
    imports = []
    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((node.lineno, alias.name.split(".")[0]))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append((node.lineno, node.module.split(".")[0]))
    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return imports


def check_file(filepath: Path) -> list[str]:
    """Check a file for import boundary violations."""
    violations = []

    layer = get_layer(filepath)
    if not layer or layer not in IMPORT_RULES:
        return violations

    rules = IMPORT_RULES[layer]
    forbidden = set(rules["forbidden"])

    # Check for allowed exceptions
    filepath_str = str(filepath)
    allowed_for_file = set()
    for exception_path, allowed_modules in ALLOWED_EXCEPTIONS.items():
        if exception_path in filepath_str:
            allowed_for_file.update(allowed_modules)

    imports = extract_imports(filepath)

    for line_num, module in imports:
        if module in forbidden and module not in allowed_for_file:
            violations.append(f"  {filepath}:{line_num}: {layer}/ cannot import from {module}/")

    return violations


def main() -> int:
    """Main entry point."""
    all_violations = []

    for layer in IMPORT_RULES:
        layer_path = Path(layer)
        if not layer_path.exists():
            continue

        for py_file in layer_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            violations = check_file(py_file)
            all_violations.extend(violations)

    if all_violations:
        print("🏗️ IMPORT BOUNDARY VIOLATIONS:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nRespect architectural layers. Move shared code to lib/.")
        return 1

    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
