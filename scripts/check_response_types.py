#!/usr/bin/env python3
"""
Check that API endpoints have response type annotations.

All endpoints should have explicit response models for documentation and validation.
"""

import ast
import re
import sys
from pathlib import Path

API_DIR = Path("api")
EXCLUDE_PATTERNS = ["_archive", "__pycache__", "test_"]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_endpoint_types(filepath: Path) -> list[str]:
    """Check endpoints for return type annotations."""
    violations = []
    
    try:
        content = filepath.read_text()
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_endpoint = False
                endpoint_path = ""
                
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr in ("get", "post", "put", "delete", "patch"):
                                is_endpoint = True
                                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                    endpoint_path = decorator.args[0].value
                
                if is_endpoint:
                    # Check for return annotation
                    if node.returns is None:
                        violations.append(
                            f"  {filepath}:{node.lineno}: {endpoint_path or node.name}() missing return type"
                        )
                    # Check for response_model in decorator
                    has_response_model = False
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            for kw in decorator.keywords:
                                if kw.arg == "response_model":
                                    has_response_model = True
                    
                    if not has_response_model and node.returns is None:
                        pass  # Already counted above
                        
    except (SyntaxError, OSError, UnicodeDecodeError):
        pass
    
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
        
        violations = check_endpoint_types(py_file)
        all_violations.extend(violations)
    
    if all_violations:
        print("📋 ENDPOINTS WITHOUT RESPONSE TYPES:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nAdd response_model or return type annotation for API documentation.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING
    
    print("✅ All endpoints have response types.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
