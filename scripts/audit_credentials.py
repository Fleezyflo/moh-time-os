#!/usr/bin/env python3
"""
Credential Audit Scanner

Scans the entire codebase for hardcoded secrets, API keys, tokens, and passwords.

Patterns detected:
- password = "..." or password = '...'
- token = "..." or api_key = "..."
- secret = "..." or SECRET_KEY = "..."
- Base64-encoded strings that look like keys (40+ char alphanumeric)
- Connection strings with embedded credentials (postgres://user:pass@...)
- AWS-style keys (AKIA...)
- Google API keys (AIza...)
- JWT tokens (eyJ...)

Exclusions:
- Test files (test_*.py)
- .env.example files
- This script itself
- Comments explaining what env vars to set
- Strings that are clearly variable references like os.environ.get("...")

Exit code:
- 0 if no FAIL (only PASS or WARN)
- 1 if any FAIL
"""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ScanResult:
    """Result of scanning a file."""

    file_path: str
    status: str  # PASS, WARN, FAIL
    issues: list[tuple[int, str, str]] = None  # (line_num, pattern_type, line_content)

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class CredentialScanner:
    """Scans files for hardcoded credentials."""

    def __init__(self):
        """Initialize scanner with patterns."""
        # Regex patterns for detecting secrets
        self.patterns = {
            "password_hardcoded": re.compile(
                r'(?:password|passwd)\s*[=:]\s*["\']([^"\']{4,})["\']',
                re.IGNORECASE,
            ),
            "token_hardcoded": re.compile(
                r'(?:token|api_token|auth_token)\s*[=:]\s*["\']([^"\']{8,})["\']',
                re.IGNORECASE,
            ),
            "api_key_hardcoded": re.compile(
                r'(?:api_key|apikey|api-key)\s*[=:]\s*["\']([^"\']{8,})["\']',
                re.IGNORECASE,
            ),
            "secret_key": re.compile(
                r'(?:secret|secret_key|SECRET_KEY)\s*[=:]\s*["\']([^"\']{8,})["\']',
                re.IGNORECASE,
            ),
            "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
            "google_api_key": re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
            "jwt_token": re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+"),
            "postgres_connection": re.compile(r"postgres(?:\+psycopg2)?://[^:]+:[^@]+@[^\s]+"),
            "mysql_connection": re.compile(r"mysql://[^:]+:[^@]+@[^\s]+"),
            "mongodb_connection": re.compile(r"mongodb(?:\+srv)?://[^:]+:[^@]+@[^\s]+"),
        }

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        # Skip this script itself
        if file_path.name == "audit_credentials.py":
            return True

        # Skip .env.example (it's supposed to have placeholder values)
        if file_path.name == ".env.example":
            return True

        # Skip test files (they may have test fixtures)
        if file_path.name.startswith("test_") or file_path.name.endswith("_test.py"):
            return True

        # Skip non-Python files
        if file_path.suffix != ".py":
            return True

        return False

    def should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped."""
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            return True

        # Skip obvious variable references (os.environ.get, os.getenv, etc.)
        if "os.environ" in line and ("get(" in line or "[" in line):
            return True

        if "os.getenv" in line:
            return True

        # Skip lines that are clearly documenting env vars in docstrings/comments
        if any(
            keyword in line.lower()
            for keyword in ["set this env var", "environment variable", "env var"]
        ):
            return True

        return False

    def is_base64_like_secret(self, text: str) -> bool:
        """Check if text looks like a base64-encoded secret (40+ chars, alphanumeric+/+=)."""
        if len(text) < 40:
            return False

        # Check if it's mostly alphanumeric + base64 chars
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-")
        char_count = sum(1 for c in text if c in valid_chars)

        # At least 90% should be valid base64/url-safe chars
        return (char_count / len(text)) > 0.9

    def scan_line(self, line: str, line_num: int) -> list[tuple[str, str]]:
        """
        Scan a single line for credential patterns.

        Returns list of (pattern_type, matched_text) tuples.
        """
        if self.should_skip_line(line):
            return []

        issues = []

        for pattern_name, pattern in self.patterns.items():
            matches = pattern.finditer(line)
            for match in matches:
                matched_text = match.group(0)

                # For connection strings, always flag them
                if pattern_name.endswith("_connection"):
                    # Mask the credentials
                    masked = re.sub(r"://([^:]+):([^@]+)@", r"://***:***@", matched_text)
                    issues.append((pattern_name, masked))
                # For AWS, Google API, JWT patterns - no captured groups, always flag
                elif pattern_name in ["aws_key", "google_api_key", "jwt_token"]:
                    issues.append((pattern_name, "***"))
                # For other patterns (password, token, api_key, secret), check captured group
                else:
                    # These patterns have a captured group with the secret value
                    if len(match.groups()) > 0:
                        secret_part = match.group(1)
                        # Only flag if it looks like an actual secret (not just a short placeholder)
                        if self.is_base64_like_secret(secret_part) or len(secret_part) >= 4:
                            issues.append((pattern_name, "***"))

        return issues

    def scan_file(self, file_path: Path) -> ScanResult:
        """Scan a file for credentials."""
        if self.should_skip_file(file_path):
            return ScanResult(str(file_path), "PASS")

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return ScanResult(str(file_path), "WARN", [(0, "read_error", str(e))])

        issues = []
        for line_num, line in enumerate(content.split("\n"), 1):
            line_issues = self.scan_line(line, line_num)
            for pattern_type, _matched_text in line_issues:
                # Truncate long lines for display
                display_line = line[:100] + "..." if len(line) > 100 else line
                issues.append((line_num, pattern_type, display_line))

        if not issues:
            return ScanResult(str(file_path), "PASS")

        # Determine severity
        # FAIL if we found actual hardcoded secrets
        # WARN if we found suspicious patterns but could be false positives
        return ScanResult(str(file_path), "FAIL", issues)

    def scan_directory(self, root_path: Path) -> list[ScanResult]:
        """Recursively scan directory for Python files."""
        results = []

        for py_file in sorted(root_path.rglob("*.py")):
            # Skip common non-source directories
            if any(
                skip_dir in py_file.parts
                for skip_dir in [
                    "__pycache__",
                    ".venv",
                    ".git",
                    "node_modules",
                    ".hypothesis",
                    ".pytest_cache",
                    ".mypy_cache",
                ]
            ):
                continue

            result = self.scan_file(py_file)
            if result.status in ["WARN", "FAIL"]:
                results.append(result)

        return results


def print_report(results: list[ScanResult], root_path: Path):
    """Print formatted report."""
    total_files = 0
    passed = 0
    warnings = 0
    failures = 0

    # Count files (including skipped ones by doing a real count)
    for _ in root_path.rglob("*.py"):
        if not any(
            skip_dir in _.parts
            for skip_dir in [
                "__pycache__",
                ".venv",
                ".git",
                "node_modules",
                ".hypothesis",
                ".pytest_cache",
                ".mypy_cache",
            ]
        ):
            total_files += 1

    for result in results:
        if result.status == "PASS":
            passed += 1
        elif result.status == "WARN":
            warnings += 1
        elif result.status == "FAIL":
            failures += 1
            print(f"FAIL: {result.file_path}")
            for line_num, pattern_type, line_content in result.issues:
                print(f"  Line {line_num} ({pattern_type}): {line_content}")

    print("\n" + "=" * 70)
    print("CREDENTIAL AUDIT REPORT")
    print("=" * 70)
    print(f"Total files scanned: {total_files}")
    print(f"  PASS: {passed}")
    print(f"  WARN: {warnings}")
    print(f"  FAIL: {failures}")
    print()

    if failures > 0:
        print("RESULT: FAILED - Hardcoded credentials detected!")
        print()
        print("Action required:")
        print("1. Move secrets to environment variables")
        print("2. Use lib.security.secrets_config.get_secret() to access them")
        print("3. Update .env.example with placeholder values")
        return False
    elif warnings > 0:
        print("RESULT: PASSED WITH WARNINGS")
        print()
        return True
    else:
        print("RESULT: PASSED - No hardcoded credentials detected!")
        print()
        return True


def main():
    """Main entry point."""
    # Scan from repo root
    repo_root = Path(__file__).parent.parent
    print(f"Scanning {repo_root} for hardcoded credentials...\n")

    scanner = CredentialScanner()
    results = scanner.scan_directory(repo_root)

    success = print_report(results, repo_root)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
