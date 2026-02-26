"""
Utility functions for safety module.
"""

import os
import shutil
import subprocess
import uuid
from datetime import UTC, datetime


def get_git_sha() -> str:
    """
    Get current git SHA (short form).
    Returns 'unknown' if not in a git repo.
    """
    git = shutil.which("git")
    if not git:
        return "unknown"

    try:
        result = subprocess.run(
            [git, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        import logging

        logging.getLogger(__name__).debug("Failed to get git hash: %s", e)
    return "unknown"


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"req-{uuid.uuid4().hex[:16]}"


def now_utc_iso() -> str:
    """Return current timezone.utc time in ISO format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# Cache git sha at module load (doesn't change during runtime)
_cached_git_sha: str | None = None


def get_cached_git_sha() -> str:
    """Get git SHA, cached for performance."""
    global _cached_git_sha
    if _cached_git_sha is None:
        _cached_git_sha = get_git_sha()
    return _cached_git_sha
