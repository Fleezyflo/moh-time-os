#!/usr/bin/env python3
"""
Check for hardcoded configuration values.

Detects:
- Hardcoded URLs/hosts
- Hardcoded ports
- Hardcoded timeouts
- Hardcoded file paths
"""

import re
import sys
from pathlib import Path

DIRS_TO_CHECK = ["lib", "api", "engine"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "test_", "migration"]

# Patterns for hardcoded values
PATTERNS = [
    # URLs (but not example.com or localhost for dev)
    (
        r"https?://(?!localhost|127\.0\.0\.1|example\.com)[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,}",
        "Hardcoded URL",
    ),
    # Ports in strings (but not common defaults)
    (r'["\']:\d{4,5}["\']', "Hardcoded port"),
    # Timeout values (but not in variable assignments)
    (r"timeout\s*=\s*\d{2,}(?!\s*\*)", "Hardcoded timeout"),
    # Absolute file paths (Unix)
    (r'["\']\/(?:home|Users|var|etc|opt)\/[^"\']+["\']', "Hardcoded absolute path"),
    # Windows paths
    (r'["\'][A-Z]:\\[^"\']+["\']', "Hardcoded Windows path"),
]

# Allowlist patterns
ALLOWLIST = [
    r"localhost",
    r"127\.0\.0\.1",
    r"example\.com",
    r"test",
    r"\.env",
    r"os\.getenv",
    r"config\.",
    r"settings\.",
    r"# noqa",
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def is_allowlisted(line: str) -> bool:
    """Check if line matches allowlist."""
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in ALLOWLIST)


def check_file(filepath: Path) -> list[str]:
    """Check a file for hardcoded config."""
    violations = []

    try:
        content = filepath.read_text()
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            if is_allowlisted(line):
                continue

            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern, name in PATTERNS:
                if re.search(pattern, line):
                    violations.append(f"  {filepath}:{i}: {name}")
                    break

    except (OSError, UnicodeDecodeError):
        pass

    return violations[:10]  # Limit per file


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

    if all_violations:
        print("🔧 HARDCODED CONFIGURATION:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nMove configuration to environment variables or config files.")
        # BLOCKING
        return 1 if all_violations else 0  # BLOCKING

    print("✅ No hardcoded configuration detected.")
    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
