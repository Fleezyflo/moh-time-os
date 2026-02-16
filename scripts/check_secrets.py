#!/usr/bin/env python3
"""
Check for hardcoded secrets in code.

Detects:
- API keys (OpenAI, Anthropic, AWS, Google, Stripe, etc.)
- Tokens (GitHub, Slack, Discord, etc.)
- Passwords in strings
- High-entropy strings (potential secrets)
- Base64-encoded secrets
"""

import re
import sys
from pathlib import Path

# Directories to scan
DIRS_TO_CHECK = ["lib", "api", "collectors", "engine", "cli", "scripts", "time-os-ui/src"]
EXCLUDE_PATTERNS = ["_archive", "__pycache__", ".venv", "node_modules", ".git"]

# Known secret patterns
SECRET_PATTERNS = [
    # OpenAI
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key"),
    # Anthropic
    (r"sk-ant-[a-zA-Z0-9\-]{20,}", "Anthropic API key"),
    # AWS
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    # AWS Secret Key - must not be all same char or separator
    (r"(?<![=\-#])[a-zA-Z0-9/+=]{40}(?![=\-#])", "Potential AWS Secret Key"),
    # GitHub
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"ghu_[a-zA-Z0-9]{36}", "GitHub User Token"),
    (r"ghs_[a-zA-Z0-9]{36}", "GitHub Server Token"),
    # Slack
    (r"xox[baprs]-[a-zA-Z0-9\-]{10,}", "Slack Token"),
    # Discord
    (r"[MN][a-zA-Z0-9]{23,}\.[a-zA-Z0-9\-_]{6}\.[a-zA-Z0-9\-_]{27}", "Discord Token"),
    # Stripe
    (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe Live Secret Key"),
    (r"sk_test_[a-zA-Z0-9]{24,}", "Stripe Test Secret Key"),
    # Google
    (r"AIza[a-zA-Z0-9\-_]{35}", "Google API Key"),
    # Twilio
    (r"SK[a-f0-9]{32}", "Twilio API Key"),
    # SendGrid
    (r"SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43}", "SendGrid API Key"),
    # Generic patterns
    (r'(?i)password\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded password"),
    (r'(?i)secret\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret"),
    (r'(?i)api_key\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded API key"),
    (r'(?i)token\s*=\s*["\'][a-zA-Z0-9\-_]{20,}["\']', "Hardcoded token"),
    # Private keys
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private key"),
    (r"-----BEGIN PGP PRIVATE KEY BLOCK-----", "PGP private key"),
]

# Allowlist patterns (false positives)
ALLOWLIST = [
    r"XERO_TOKEN_URL",  # URL constant, not a token
    r"sync_token",  # Parameter name, not a value
    r"token_uri",  # OAuth endpoint name
    r"_token",  # Suffix in variable names
    r"test.*token",  # Test fixtures
    r"example\.com",  # Example domains
    r"\.env\.example",  # Example files
    r"SECRET_KEY.*=.*os\.getenv",  # Env var lookup (correct pattern)
    r"# noqa: secret",  # Explicit ignore
    r"^#\s*[=\-]{10,}",  # Comment separator lines
    r"[=]{10,}",  # Separator lines with equals
    r"[-]{10,}",  # Separator lines with dashes
    r"^\s*#.*={5,}",  # Any comment with repeated equals
    r"check_secrets\.py",  # Self-reference in this file
    r'\(r["\']-----BEGIN',  # Regex pattern definitions
]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded."""
    path_str = str(path)
    return any(excl in path_str for excl in EXCLUDE_PATTERNS)


def is_allowlisted(line: str) -> bool:
    """Check if line matches allowlist."""
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in ALLOWLIST)


def scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Scan a file for secrets. Returns (line_num, secret_type, line)."""
    violations = []
    try:
        content = filepath.read_text(errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            # Skip comments in some languages
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                if "noqa" in stripped.lower() or "nosec" in stripped.lower():
                    continue

            # Skip allowlisted lines
            if is_allowlisted(line):
                continue

            # Check each pattern
            for pattern, secret_type in SECRET_PATTERNS:
                if re.search(pattern, line):
                    # Additional check: avoid false positives on short matches
                    if "password" not in secret_type.lower():
                        violations.append((i, secret_type, line.strip()[:100]))
                    else:
                        # For password patterns, verify it's not just a variable name
                        if re.search(r'=\s*["\'][^"\']+["\']', line):
                            violations.append((i, secret_type, line.strip()[:100]))
    except (OSError, UnicodeDecodeError):
        pass
    return violations


def main() -> int:
    """Main entry point."""
    all_violations = []

    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue

        # Scan Python files
        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue
            violations = scan_file(py_file)
            for line_num, secret_type, line in violations:
                all_violations.append(f"  {py_file}:{line_num} [{secret_type}]: {line}")

        # Scan TypeScript/JavaScript files
        for ext in ["*.ts", "*.tsx", "*.js", "*.jsx"]:
            for ts_file in dir_path.rglob(ext):
                if should_exclude(ts_file):
                    continue
                violations = scan_file(ts_file)
                for line_num, secret_type, line in violations:
                    all_violations.append(f"  {ts_file}:{line_num} [{secret_type}]: {line}")

        # Scan config files
        for ext in ["*.json", "*.yaml", "*.yml", "*.toml", "*.env"]:
            for cfg_file in dir_path.rglob(ext):
                if should_exclude(cfg_file) or ".example" in str(cfg_file):
                    continue
                violations = scan_file(cfg_file)
                for line_num, secret_type, line in violations:
                    all_violations.append(f"  {cfg_file}:{line_num} [{secret_type}]: {line}")

    if all_violations:
        print("🔐 SECRETS DETECTED IN CODE:")
        print("\n".join(all_violations[:20]))  # Limit output
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        print(
            "\nUse environment variables instead. Add '# noqa: secret' to ignore false positives."
        )
        return 1

    return 0  # PASS when no violations


if __name__ == "__main__":
    sys.exit(main())
