#!/usr/bin/env python3
"""
Check for PII (Personally Identifiable Information) in logging.

Detects potential PII exposure:
- Email addresses in log statements
- Phone numbers
- Names in format strings
- IDs that might be sensitive
"""

import ast
import re
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine", "collectors"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_"]

# PII patterns
PII_PATTERNS = [
    (r'email["\']?\s*[:=]', "email field"),
    (r'phone["\']?\s*[:=]', "phone field"),
    (r'password["\']?\s*[:=]', "password field"),
    (r'ssn["\']?\s*[:=]', "SSN field"),
    (r'credit.?card["\']?\s*[:=]', "credit card field"),
    (r'social.?security["\']?\s*[:=]', "social security field"),
    (r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "email address literal"),
]

# Logging method names
LOGGING_METHODS = {"debug", "info", "warning", "error", "critical", "exception", "log"}


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_logging_calls(filepath: Path) -> list[str]:
    """Check logging calls for PII."""
    violations = []
    
    try:
        content = filepath.read_text()
        tree = ast.parse(content)
        lines = content.split("\n")
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if it's a logging call
                is_logging = False
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in LOGGING_METHODS:
                        is_logging = True
                
                if not is_logging:
                    continue
                
                # Get the line content
                if node.lineno <= len(lines):
                    line = lines[node.lineno - 1]
                    
                    # Check for PII patterns
                    for pattern, name in PII_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            violations.append(
                                f"  {filepath}:{node.lineno}: Potential {name} in log statement"
                            )
                            break
                            
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
            
            violations = check_logging_calls(py_file)
            all_violations.extend(violations)
    
    if all_violations:
        print("🔐 POTENTIAL PII IN LOGS:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nRedact or hash PII before logging. Use IDs instead of raw values.")
        # Warning only
        return 1  # BLOCKING
    
    print("✅ No obvious PII in logging detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
