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
    2. Platform-specific default:
       - macOS: ~/Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json
       - Linux: ~/.config/gogcli/sa-bW9saGFtQGhybW55LmNv.json

    Returns:
        Path to the SA file. Caller must check .exists() before use.
    """
    env_val = os.environ.get("GOOGLE_SA_FILE")
    if env_val:
        return Path(env_val).expanduser().resolve()

    sa_filename = "sa-bW9saGFtQGhybW55LmNv.json"
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "gogcli" / sa_filename
    # Linux / CI / Docker / other
    return Path.home() / ".config" / "gogcli" / sa_filename


def credentials_json() -> Path:
    """
    Path to .credentials.json (Asana, Xero tokens etc.).

    Uses the project config directory from lib.paths.
    """
    return paths.project_root() / "config" / ".credentials.json"


def xero_token_cache() -> Path:
    """
    Path to Xero OAuth token cache file.

    Uses the project config directory from lib.paths.
    """
    return paths.project_root() / "config" / ".xero_token_cache.json"
