#!/usr/bin/env python3
"""
Check for missing docstrings on public functions and classes.

Enforces documentation standards:
- All public functions must have docstrings
- All public classes must have docstrings
- Modules should have docstrings
"""

import ast
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_", "__init__.py"]

# Minimum docstring length to be considered valid
MIN_DOCSTRING_LENGTH = 10


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def get_docstring(node: ast.AST) -> str | None:
    """Get docstring from a node."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        if node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, ast.Constant):
                if isinstance(node.body[0].value.value, str):
                    return node.body[0].value.value
    return None


def check_file(filepath: Path) -> list[str]:
    """Check a file for missing docstrings."""
    violations = []
    
    try:
        content = filepath.read_text()
        tree = ast.parse(content)
        
        # Check module docstring
        module_doc = get_docstring(tree)
        if not module_doc or len(module_doc) < MIN_DOCSTRING_LENGTH:
            violations.append(f"  {filepath}:1: Missing module docstring")
        
        # Check functions and classes
        for node in ast.walk(tree):
            # Skip private/internal
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                    
                docstring = get_docstring(node)
                if not docstring or len(docstring) < MIN_DOCSTRING_LENGTH:
                    violations.append(
                        f"  {filepath}:{node.lineno}: Missing docstring for function '{node.name}()'"
                    )
                    
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                    
                docstring = get_docstring(node)
                if not docstring or len(docstring) < MIN_DOCSTRING_LENGTH:
                    violations.append(
                        f"  {filepath}:{node.lineno}: Missing docstring for class '{node.name}'"
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
            
            violations = check_file(py_file)
            all_violations.extend(violations)
    
    # Summary stats
    total = len(all_violations)
    
    if all_violations:
        print(f"📝 MISSING DOCSTRINGS ({total} total):")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nAdd docstrings to public functions and classes.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING
    
    print("✅ All public items have docstrings.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
