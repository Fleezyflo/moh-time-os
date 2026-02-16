#!/usr/bin/env python3
"""
Check for basic accessibility issues in React/TSX code.

Detects:
- Images without alt text
- Buttons without accessible names
- Links without text
- Form inputs without labels
- onClick on non-interactive elements
"""

import re
import sys
from pathlib import Path

UI_DIR = Path("time-os-ui/src")
EXCLUDE_PATTERNS = ["node_modules", ".test.", ".spec.", "__tests__"]

# Accessibility patterns
A11Y_ISSUES = [
    # Images without alt
    (r'<img\s+(?![^>]*alt=)[^>]*/?>', "img without alt attribute"),
    
    # Buttons without content or aria-label
    (r'<button\s+(?![^>]*aria-label)[^>]*>\s*</button>', "empty button without aria-label"),
    
    # Links without content
    (r'<a\s+(?![^>]*aria-label)[^>]*>\s*</a>', "empty link without aria-label"),
    
    # onClick on divs without role
    (r'<div\s+(?![^>]*role=)[^>]*onClick', "div with onClick but no role"),
    
    # onClick on spans without role
    (r'<span\s+(?![^>]*role=)[^>]*onClick', "span with onClick but no role"),
    
    # Form inputs without id (for label association)
    (r'<input\s+(?![^>]*id=)[^>]*/>', "input without id for label association"),
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_file(filepath: Path) -> list[str]:
    """Check a file for a11y issues."""
    violations = []
    
    try:
        content = filepath.read_text()
        
        for pattern, message in A11Y_ISSUES:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                # Find line number
                lineno = content[:match.start()].count("\n") + 1
                violations.append(f"  {filepath}:{lineno}: {message}")
                
    except (OSError, UnicodeDecodeError):
        pass
    
    return violations[:10]  # Limit per file


def main() -> int:
    """Main entry point."""
    if not UI_DIR.exists():
        print("✅ No UI directory found.")
        return 1
    
    all_violations = []
    
    for file in UI_DIR.rglob("*.tsx"):
        if should_exclude(file):
            continue
        
        violations = check_file(file)
        all_violations.extend(violations)
    
    if all_violations:
        print("♿ ACCESSIBILITY ISSUES:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nFix accessibility issues for WCAG compliance.")
        print("Add alt text, aria-labels, and proper roles.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING
    
    print("✅ Basic accessibility checks passed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
