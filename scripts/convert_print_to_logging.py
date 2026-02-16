#!/usr/bin/env python3
"""
Convert print() statements to logger.info() calls.

Usage:
    python scripts/convert_print_to_logging.py [--dry-run]
"""

import re
import sys
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv

# Directories to process
DIRS = ["lib", "api"]

# Files to skip (migrations often use print intentionally for CLI feedback)
SKIP_PATTERNS = [
    "test_",
    "__pycache__",
]

LOGGER_IMPORT = "import logging\n"
LOGGER_INIT = "logger = logging.getLogger(__name__)\n"


def has_logger_import(content: str) -> bool:
    """Check if file already imports logging and creates logger."""
    return "logger = logging.getLogger" in content or "logger = log.getLogger" in content


def add_logger_import(content: str) -> str:
    """Add logger import and initialization to file."""
    lines = content.split("\n")

    # Find the right place to insert (after existing imports)
    insert_idx = 0
    in_docstring = False
    docstring_char = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track docstrings
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_char = stripped[:3]
                if stripped.count(docstring_char) == 1:
                    in_docstring = True
                insert_idx = i + 1
                continue
        else:
            if docstring_char in stripped:
                in_docstring = False
                insert_idx = i + 1
                continue

        if in_docstring:
            continue

        # Track imports
        if stripped.startswith("import ") or stripped.startswith("from "):
            insert_idx = i + 1
        elif stripped and not stripped.startswith("#") and insert_idx > 0:
            # First non-import, non-comment line after imports
            break

    # Check if logging is already imported
    has_logging_import = any("import logging" in line for line in lines[: insert_idx + 5])

    # Insert logger initialization
    if not has_logging_import:
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, LOGGER_IMPORT.strip())
        lines.insert(insert_idx + 2, LOGGER_INIT.strip())
        lines.insert(insert_idx + 3, "")
    else:
        # Just add the logger = line after imports
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, LOGGER_INIT.strip())
        lines.insert(insert_idx + 2, "")

    return "\n".join(lines)


def convert_print_to_logger(content: str) -> str:
    """Convert print() calls to logger.info() calls."""

    # Pattern for simple print statements
    # print("text") -> logger.info("text")
    # print(f"text") -> logger.info("text")
    # print(f"text {var}") -> logger.info("text %s", var) or keep f-string

    # Simple replacement for basic cases
    # We'll keep f-strings as they work with logging

    def replace_print(match):
        indent = match.group(1)
        content = match.group(2)

        # Handle print with file= argument (stderr etc)
        if "file=" in content or "file =" in content:
            # Convert to logger.error for stderr
            if "stderr" in content:
                # Remove file=sys.stderr argument
                content = re.sub(r",?\s*file\s*=\s*sys\.stderr", "", content)
                return f"{indent}logger.error({content})"
            return match.group(0)  # Keep as is for other file outputs

        # Handle print() with no args
        if not content.strip():
            return f"{indent}# (blank line - was empty print)"

        return f"{indent}logger.info({content})"

    # Match print statements
    pattern = r"^(\s*)print\((.+)\)\s*$"
    content = re.sub(pattern, replace_print, content, flags=re.MULTILINE)

    return content


def process_file(filepath: Path) -> tuple[bool, int]:
    """Process a single file. Returns (modified, count)."""

    content = filepath.read_text()
    original = content

    # Count prints before
    print_count = len(re.findall(r"\bprint\(", content))
    if print_count == 0:
        return False, 0

    # Skip if no prints or already has proper logging for each print

    # Add logger if needed
    if not has_logger_import(content):
        content = add_logger_import(content)

    # Convert prints
    content = convert_print_to_logger(content)

    if content != original:
        if not DRY_RUN:
            filepath.write_text(content)
        return True, print_count

    return False, 0


def main():
    total_files = 0
    total_prints = 0

    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Converting print() to logger.info()...\n")

    for dir_name in DIRS:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        for filepath in dir_path.rglob("*.py"):
            # Skip test files and pycache
            if any(skip in str(filepath) for skip in SKIP_PATTERNS):
                continue

            try:
                modified, count = process_file(filepath)
                if modified:
                    total_files += 1
                    total_prints += count
                    print(f"  {'[WOULD MODIFY] ' if DRY_RUN else '✓ '}{filepath} ({count} prints)")
            except Exception as e:
                print(f"  ✗ {filepath}: {e}")

    print(
        f"\n{'Would modify' if DRY_RUN else 'Modified'}: {total_files} files, {total_prints} print statements"
    )

    if DRY_RUN:
        print("\nRun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
