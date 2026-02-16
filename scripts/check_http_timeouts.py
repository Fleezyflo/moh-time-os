#!/usr/bin/env python3
"""
Check for HTTP calls without timeouts.

All HTTP requests should have explicit timeouts to prevent hanging.
"""

import ast
import re
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine", "collectors"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]

# HTTP libraries and their call patterns
HTTP_CALLS = [
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.patch",
    "requests.request",
    "httpx.get",
    "httpx.post",
    "httpx.put",
    "httpx.delete",
    "httpx.patch",
    "httpx.request",
    "urllib.request.urlopen",
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_http_calls(filepath: Path) -> list[str]:
    """Check for HTTP calls without timeout."""
    violations = []
    
    try:
        content = filepath.read_text()
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = get_call_name(node)
                
                if any(http in call_name for http in ["requests.", "httpx.", "urlopen"]):
                    # Check if timeout is specified
                    has_timeout = False
                    
                    for keyword in node.keywords:
                        if keyword.arg == "timeout":
                            has_timeout = True
                            break
                    
                    if not has_timeout:
                        violations.append(
                            f"  {filepath}:{node.lineno}: {call_name}() without timeout"
                        )
                        
    except (SyntaxError, OSError, UnicodeDecodeError):
        pass
    
    return violations


def get_call_name(node: ast.Call) -> str:
    """Get the full name of a call."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    elif isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}"
        elif isinstance(node.func.value, ast.Attribute):
            if isinstance(node.func.value.value, ast.Name):
                return f"{node.func.value.value.id}.{node.func.value.attr}.{node.func.attr}"
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
            
            violations = check_http_calls(py_file)
            all_violations.extend(violations)
    
    if all_violations:
        print("⏱️ HTTP CALLS WITHOUT TIMEOUT:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nAdd timeout parameter to prevent hanging: requests.get(url, timeout=30)")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING
    
    print("✅ All HTTP calls have timeouts.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
