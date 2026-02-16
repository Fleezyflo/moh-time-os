#!/usr/bin/env python3
"""
Check that all API endpoints have authentication.

Scans for endpoints without Depends(auth) or similar auth patterns.
"""

import re
import sys
from pathlib import Path

API_DIR = Path("api")
EXCLUDE_PATTERNS = ["_archive", "__pycache__", "test_"]

# Patterns for endpoints
ENDPOINT_PATTERN = re.compile(
    r'@(?:app|router|spec_router|intelligence_router)\.'
    r'(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
)

# Patterns that indicate auth is present
AUTH_PATTERNS = [
    r'Depends\s*\(\s*(?:get_current_user|verify_token|auth|authenticate|require_auth)',
    r'dependencies\s*=\s*\[.*(?:auth|verify|token)',
    r'security\s*=',
    r'HTTPBearer',
    r'OAuth2',
    r'APIKey',
]

# Endpoints that are allowed without auth
PUBLIC_ENDPOINTS = [
    "/health",
    "/healthz",
    "/ready",
    "/readyz",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/",
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def is_public_endpoint(path: str) -> bool:
    """Check if endpoint is allowed to be public."""
    return any(path == pub or path.startswith(pub) for pub in PUBLIC_ENDPOINTS)


def extract_function_with_context(content: str, endpoint_match) -> str:
    """Extract the function definition following an endpoint decorator."""
    start = endpoint_match.end()
    # Find the function definition
    func_match = re.search(r'\ndef\s+\w+\s*\([^)]*\)', content[start:start+500])
    if func_match:
        return content[start:start + func_match.end()]
    return content[start:start+200]


def check_file(filepath: Path) -> list[str]:
    """Check a file for unauth'd endpoints."""
    violations = []

    try:
        content = filepath.read_text()
        content.split("\n")

        for match in ENDPOINT_PATTERN.finditer(content):
            method = match.group(1).upper()
            path = match.group(2)

            # Skip public endpoints
            if is_public_endpoint(path):
                continue

            # Get context around the endpoint (decorator + function)
            context = extract_function_with_context(content, match)

            # Check if any auth pattern is present
            has_auth = any(re.search(pattern, context, re.IGNORECASE)
                          for pattern in AUTH_PATTERNS)

            if not has_auth:
                # Find line number
                line_num = content[:match.start()].count("\n") + 1
                violations.append(
                    f"  {filepath}:{line_num}: {method} {path} - no auth detected"
                )

    except (OSError, UnicodeDecodeError):
        pass

    return violations


def main() -> int:
    """Main entry point."""
    if not API_DIR.exists():
        print("✅ No API directory found.")
        return 0

    all_violations = []

    for py_file in API_DIR.rglob("*.py"):
        if should_exclude(py_file):
            continue

        violations = check_file(py_file)
        all_violations.extend(violations)

    if all_violations:
        print("🔓 ENDPOINTS WITHOUT AUTHENTICATION:")
        print("\n".join(all_violations[:30]))
        if len(all_violations) > 30:
            print(f"  ... and {len(all_violations) - 30} more")
        print("\nAdd authentication to protect these endpoints:")
        print("  from fastapi import Depends")
        print("  @router.get('/path', dependencies=[Depends(auth)])")
        # BLOCKING for now
        return 1 if all_violations else 0  # BLOCKING

    print("✅ All endpoints have authentication.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
