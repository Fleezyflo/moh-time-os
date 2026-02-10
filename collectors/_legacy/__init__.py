"""
DEPRECATED: Legacy collectors — DO NOT IMPORT

These collectors have been superseded by the canonical runner:
    collectors/scheduled_collect.py

Importing any module from this package will raise RuntimeError.
"""


def __getattr__(name):
    raise RuntimeError(
        f"collectors._legacy.{name} is deprecated. "
        f"Use collectors/scheduled_collect.py instead. "
        f"See COLLECTOR_AUDIT.md for migration details."
    )
