"""
Python 3.10 compatibility shims.

datetime.UTC and StrEnum were introduced in Python 3.11.
This module provides backports for Python 3.10 environments.
"""

from datetime import timezone
from enum import Enum, EnumMeta

# datetime.UTC was added in Python 3.11; timezone.utc works in 3.9+
UTC = timezone.utc

try:
    from enum import StrEnum
except ImportError:
    # Python 3.10: build StrEnum(str, Enum) via EnumMeta to satisfy both
    # the Enum metaclass and ruff UP042 (which flags class-form inheritance).
    _ns = EnumMeta.__prepare__("StrEnum", (str, Enum))
    StrEnum = EnumMeta("StrEnum", (str, Enum), _ns)

__all__ = ["UTC", "StrEnum"]
