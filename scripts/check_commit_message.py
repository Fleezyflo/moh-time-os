#!/usr/bin/env python3
"""
Conventional Commits enforcement.

Validates commit messages follow the conventional commits format:
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
Scope: optional, identifies the affected area

Usage:
    echo "feat(api): add new endpoint" | python scripts/check_commit_message.py
    python scripts/check_commit_message.py --file .git/COMMIT_EDITMSG
    python scripts/check_commit_message.py --message "feat: add feature"
"""

import argparse
import re
import sys

# Conventional commit types
VALID_TYPES = [
    "feat",  # New feature
    "fix",  # Bug fix
    "docs",  # Documentation
    "style",  # Formatting (no code change)
    "refactor",  # Code restructuring
    "perf",  # Performance improvement
    "test",  # Tests
    "build",  # Build system
    "ci",  # CI configuration
    "chore",  # Maintenance
    "revert",  # Revert previous commit
]

# Pattern: type(scope): description  OR  type: description
PATTERN = re.compile(
    r"^(?P<type>" + "|".join(VALID_TYPES) + r")"
    r"(\((?P<scope>[a-z0-9_/-]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<description>.+)$",
    re.IGNORECASE,
)

# Allow merge commits
MERGE_PATTERN = re.compile(r"^Merge (branch|pull request|remote-tracking branch) ")

# Allow revert commits
REVERT_PATTERN = re.compile(r'^Revert "')


def validate_message(message: str) -> tuple[bool, str]:
    """Validate a commit message."""
    # Get first line (subject)
    lines = message.strip().split("\n")
    subject = lines[0].strip()

    # Allow empty (for commit --amend)
    if not subject:
        return False, "Empty commit message"

    # Allow merge commits
    if MERGE_PATTERN.match(subject):
        return True, "Merge commit"

    # Allow revert commits
    if REVERT_PATTERN.match(subject):
        return True, "Revert commit"

    # Check conventional format
    match = PATTERN.match(subject)
    if not match:
        return False, (
            f"Invalid commit message format.\n\n"
            f"Expected: <type>(<scope>): <description>\n"
            f"Got: {subject}\n\n"
            f"Valid types: {', '.join(VALID_TYPES)}\n"
            f"Examples:\n"
            f"  feat(api): add new endpoint\n"
            f"  fix: correct calculation bug\n"
            f"  docs(readme): update installation steps\n"
            f"  chore: update dependencies"
        )

    # Check subject length (max 72 chars recommended)
    if len(subject) > 72:
        return False, f"Subject too long ({len(subject)} > 72 chars): {subject[:50]}..."

    # Check description starts with lowercase
    desc = match.group("description")
    if desc and desc[0].isupper():
        return False, f"Description should start with lowercase: '{desc}'"

    return True, f"Valid: {match.group('type')}({match.group('scope') or 'no scope'})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate conventional commit messages")
    parser.add_argument("--file", "-f", help="Read message from file")
    parser.add_argument("--message", "-m", help="Commit message string")
    args = parser.parse_args()

    # Read message
    if args.file:
        with open(args.file) as f:
            message = f.read()
    elif args.message:
        message = args.message
    else:
        message = sys.stdin.read()

    valid, reason = validate_message(message)

    if valid:
        print(f"✅ {reason}")
        return 0
    else:
        print(f"❌ {reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
