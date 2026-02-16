#!/usr/bin/env python3
"""
Check for console.log statements in TypeScript/JavaScript production code.

Frontend code should not have console.* in production.
"""

import re
import sys
from pathlib import Path

UI_DIR = Path("time-os-ui/src")
EXCLUDE_PATTERNS = ["node_modules", ".test.", ".spec.", "__tests__"]

# Console patterns
CONSOLE_PATTERN = re.compile(r'\bconsole\.(log|debug|info|warn|error|trace|table)\s*\(')


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def check_file(filepath: Path) -> list[str]:
    """Check a file for console.* calls."""
    violations = []
    
    try:
        content = filepath.read_text()
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            
            # Skip if disabled
            if "eslint-disable" in line or "noqa" in line:
                continue
            
            if CONSOLE_PATTERN.search(line):
                violations.append(f"  {filepath}:{i}: {stripped[:60]}")
                
    except (OSError, UnicodeDecodeError):
        pass
    
    return violations


def main() -> int:
    """Main entry point."""
    if not UI_DIR.exists():
        print("✅ No UI directory found.")
        return 1
    
    all_violations = []
    
    for ext in ["*.ts", "*.tsx", "*.js", "*.jsx"]:
        for file in UI_DIR.rglob(ext):
            if should_exclude(file):
                continue
            
            violations = check_file(file)
            all_violations.extend(violations)
    
    if all_violations:
        print("🖥️ CONSOLE STATEMENTS IN PRODUCTION:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nRemove console.* or use a proper logging library.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING
    
    print("✅ No console.* in production code.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
