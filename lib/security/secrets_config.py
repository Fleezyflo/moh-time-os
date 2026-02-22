"""
Centralized secrets configuration and validation.

Documents and validates all required secrets (environment variables) for MOH Time OS.
Never logs or prints actual secret values.

Provides:
- SecretsAuditResult dataclass with configured/missing/warnings lists
- validate_secrets() function to check which env vars are set
- mask_secret() function to safely mask secrets for logging
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SecretsAuditResult:
    """Result of secrets audit/validation."""

    configured: list[str] = field(default_factory=list)
    """List of configured (present) env vars."""

    missing: list[str] = field(default_factory=list)
    """List of missing (required but not set) env vars."""

    warnings: list[str] = field(default_factory=list)
    """List of configuration warnings/issues."""

    def is_complete(self) -> bool:
        """Check if all required secrets are configured."""
        return len(self.missing) == 0

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "configured": self.configured,
            "missing": self.missing,
            "warnings": self.warnings,
            "is_complete": self.is_complete(),
            "has_warnings": self.has_warnings(),
        }


# All required secrets for MOH Time OS
# Format: (env_var_name, description, is_optional)
REQUIRED_SECRETS = [
    # Authentication & Tokens
    ("INTEL_API_TOKEN", "Legacy authentication token for Intel API", False),
    ("GOOGLE_CHAT_WEBHOOK_URL", "Webhook URL for Google Chat notifications", True),
    ("ASANA_TOKEN", "Bearer token for Asana API access", False),
    ("GMAIL_TOKEN_PATH", "Path to Gmail OAuth2 token JSON file", True),
    ("GOOGLE_CALENDAR_TOKEN_PATH", "Path to Google Calendar OAuth2 token JSON file", True),
    # Xero Integration
    ("XERO_CLIENT_ID", "OAuth2 client ID for Xero API", True),
    ("XERO_CLIENT_SECRET", "OAuth2 client secret for Xero API", True),
    # Database
    ("DATABASE_PATH", "Path to SQLite database file", True),
    # CORS & API
    ("CORS_ORIGINS", "Comma-separated list of allowed CORS origins", True),
]


def validate_secrets(required_only: bool = True) -> SecretsAuditResult:
    """
    Validate configured secrets.

    Args:
        required_only: If True, only check required (non-optional) secrets.
                      If False, check all secrets.

    Returns:
        SecretsAuditResult with configured, missing, and warnings lists.
    """
    result = SecretsAuditResult()

    for var_name, _description, is_optional in REQUIRED_SECRETS:
        # Skip optional secrets if required_only=True
        if required_only and is_optional:
            continue

        if os.environ.get(var_name):
            result.configured.append(var_name)
        else:
            if not is_optional:
                result.missing.append(var_name)
            else:
                result.warnings.append(f"{var_name} is not configured (optional)")

    return result


def mask_secret(value: str, chars_visible: int = 4) -> str:
    """
    Mask a secret value for safe logging.

    Args:
        value: The secret value to mask.
        chars_visible: Number of first characters to show (default: 4).

    Returns:
        Masked value like "abc1***" or "***" if value is too short.
    """
    if not value or len(value) <= chars_visible:
        return "***"

    return value[:chars_visible] + "***"


def get_secret(var_name: str, default: str | None = None) -> str | None:
    """
    Get a secret value from environment.

    Never logs the actual value. Returns None if not set (unless default provided).

    Args:
        var_name: Name of environment variable.
        default: Default value if not set.

    Returns:
        Secret value or default, or None if not set and no default.
    """
    value = os.environ.get(var_name, default)
    if value and var_name in [s[0] for s in REQUIRED_SECRETS]:
        logger.debug(f"Using {var_name}: {mask_secret(value)}")
    return value


def is_configured(var_name: str) -> bool:
    """Check if a secret is configured (set in environment)."""
    return bool(os.environ.get(var_name))


def describe_secret(var_name: str) -> str | None:
    """Get description of a secret variable."""
    for name, desc, _ in REQUIRED_SECRETS:
        if name == var_name:
            return desc
    return None


def is_required_secret(var_name: str) -> bool:
    """Check if a secret is required (not optional)."""
    for name, _, is_optional in REQUIRED_SECRETS:
        if name == var_name:
            return not is_optional
    return False
