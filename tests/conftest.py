"""
Test configuration — ensures repo root is in sys.path.

This allows tests to import from top-level packages (collectors, scripts, lib).
"""

import sys
from pathlib import Path

# Add repo root to sys.path so tests can import collectors.*, scripts.*, lib.*
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
