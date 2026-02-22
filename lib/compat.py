"""Python 3.10/3.11+ compatibility shims."""

import enum
import sys
from datetime import timezone

# Python 3.11+ has datetime.UTC; on 3.10, use timezone.utc
if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    UTC = timezone.utc

# Python 3.11+ has enum.StrEnum; on 3.10, provide a backport
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:

    class StrEnum(str, enum.Enum):
        """Backport of StrEnum for Python 3.10."""

        pass
