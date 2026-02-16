#!/usr/bin/env python3
"""
Check that all environment variables used in code are documented.

Scans for os.getenv() and os.environ[] calls and compares against .env.example.
"""

import ast
import re
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "collectors", "engine", "cli"]
ENV_EXAMPLE_FILES = [".env.example", ".env.sample", "env.example"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]

# Environment variables that don't need documentation
STANDARD_ENV_VARS = {
    "HOME", "USER", "PATH", "PWD", "SHELL", "TERM",
    "LANG", "LC_ALL", "TZ", "PYTHONPATH", "VIRTUAL_ENV",
}


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def extract_env_vars_ast(filepath: Path) -> set[str]:
    """Extract environment variable names from a file using AST."""
    env_vars = set()

    try:
        content = filepath.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            # os.getenv("VAR")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    # Only match os.getenv specifically
                    if node.func.attr == "getenv" and node.args:
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                            if isinstance(node.args[0], ast.Constant):
                                env_vars.add(node.args[0].value)
                    # os.environ.get("VAR")
                    elif node.func.attr == "get" and node.args:
                        if isinstance(node.func.value, ast.Attribute):
                            if node.func.value.attr == "environ":
                                if isinstance(node.args[0], ast.Constant):
                                    env_vars.add(node.args[0].value)

            # os.environ["VAR"]
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Attribute):
                    if node.value.attr == "environ":
                        if isinstance(node.value.value, ast.Name) and node.value.value.id == "os":
                            if isinstance(node.slice, ast.Constant):
                                env_vars.add(node.slice.value)

    except (SyntaxError, OSError, UnicodeDecodeError):
        pass

    return env_vars


def extract_env_vars_regex(filepath: Path) -> set[str]:
    """Extract environment variable names using regex (fallback)."""
    env_vars = set()

    try:
        content = filepath.read_text()

        # os.getenv("VAR") or os.getenv('VAR')
        for match in re.finditer(r'os\.getenv\s*\(\s*["\']([^"\']+)["\']', content):
            env_vars.add(match.group(1))

        # os.environ["VAR"] or os.environ['VAR']
        for match in re.finditer(r'os\.environ\s*\[\s*["\']([^"\']+)["\']', content):
            env_vars.add(match.group(1))

        # os.environ.get("VAR")
        for match in re.finditer(r'os\.environ\.get\s*\(\s*["\']([^"\']+)["\']', content):
            env_vars.add(match.group(1))

    except (OSError, UnicodeDecodeError):
        pass

    return env_vars


def load_documented_vars() -> set[str]:
    """Load documented environment variables from .env.example."""
    documented = set()

    for env_file in ENV_EXAMPLE_FILES:
        path = Path(env_file)
        if path.exists():
            try:
                for line in path.read_text().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        var_name = line.split("=")[0].strip()
                        documented.add(var_name)
            except (OSError, UnicodeDecodeError):
                pass

    return documented


def main() -> int:
    """Main entry point."""
    # Collect all used env vars
    used_vars = set()

    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            vars_ast = extract_env_vars_ast(py_file)
            vars_regex = extract_env_vars_regex(py_file)
            used_vars.update(vars_ast)
            used_vars.update(vars_regex)

    # Remove standard vars
    used_vars -= STANDARD_ENV_VARS

    if not used_vars:
        print("✅ No custom environment variables found in code.")
        return 1

    # Load documented vars
    documented = load_documented_vars()

    # Find undocumented
    undocumented = used_vars - documented

    if undocumented:
        print("📋 UNDOCUMENTED ENVIRONMENT VARIABLES:")
        for var in sorted(undocumented):
            print(f"  {var}")
        print("\nAdd these to .env.example for documentation.")
        print(f"Used vars: {len(used_vars)}, Documented: {len(documented)}")
        # BLOCKING
        return 1  # BLOCKING

    print(f"✅ All {len(used_vars)} environment variables are documented.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
