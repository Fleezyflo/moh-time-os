"""
Canonical Credential Path Resolution for MOH TIME OS.

ALL code must use this module for credential file paths. No hardcoded
platform-specific paths elsewhere.

Policy:
- Google SA file: resolved from GOOGLE_SA_FILE env var, then platform-specific default
- Credentials JSON: resolved from project config dir
- Token caches: resolved from project config dir

This prevents macOS-only paths from breaking on Linux/CI/Docker.
"""

import os
import platform
from pathlib import Path

from lib import paths


def google_sa_file() -> Path:
    """
    Resolve Google Service Account JSON file path.

    Resolution order:
    1. GOOGLE_SA_FILE env var (explicit override — required for CI/Docker/Linux)
    2. Platform-specific default (filename from GOOGLE_SA_FILENAME, default
       service-account.json):
       - macOS: ~/Library/Application Support/gogcli/<sa_filename>
       - Linux: ~/.config/gogcli/<sa_filename>

    Returns:
        Path to the SA file. Caller must check .exists() before use.
    """
    env_val = os.environ.get("GOOGLE_SA_FILE")
    if env_val:
        return Path(env_val).expanduser().resolve()

    # Filename is configurable so generic path code does not leak a specific
    # user's identity (the previous default base64-encoded a real email).
    sa_filename = os.environ.get("GOOGLE_SA_FILENAME", "service-account.json")
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "gogcli" / sa_filename
    # Linux / CI / Docker / other
    return Path.home() / ".config" / "gogcli" / sa_filename


def credentials_json() -> Path:
    """
    Path to .credentials.json (Asana, Xero tokens etc.).

    Resolution order:
    1. CREDENTIALS_JSON_FILE env var (explicit override -- keeps live secret
       material out of the repo tree; required after S3.3 key rotation).
    2. Project config directory default: <repo>/config/.credentials.json.

    Returns:
        Path to the credentials file. Caller must check .exists() before use.
    """
    env_val = os.environ.get("CREDENTIALS_JSON_FILE")
    if env_val:
        return Path(env_val).expanduser().resolve()
    return paths.project_root() / "config" / ".credentials.json"


def xero_token_cache() -> Path:
    """
    Path to Xero OAuth token cache file.

    Uses the project config directory from lib.paths.
    """
    return paths.project_root() / "config" / ".xero_token_cache.json"
