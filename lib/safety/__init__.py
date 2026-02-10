"""
Safety + Provenance + Parity Foundation

This module provides:
- Write context management (actor/request_id/source/git_sha)
- Audit logging for all DB writes
- Schema assertions
- Write guards preventing unattributed changes

Usage:
    from lib.safety import WriteContext, get_git_sha

    with WriteContext(conn, actor="user123", source="api", request_id="req-abc"):
        # All writes within this context are attributed and audited
        conn.execute("UPDATE inbox_items_v29 SET ...")
"""

from .audit import AuditLogger
from .context import (
    WriteContext,
    clear_write_context,
    get_write_context,
    set_write_context,
)
from .json_parse import ParseResult, TrustMeta, parse_json_field, safe_json_loads
from .migrations import run_safety_migrations
from .schema import SchemaAssertion, assert_schema
from .utils import generate_request_id, get_git_sha

__all__ = [
    "WriteContext",
    "set_write_context",
    "clear_write_context",
    "get_write_context",
    "AuditLogger",
    "SchemaAssertion",
    "assert_schema",
    "run_safety_migrations",
    "get_git_sha",
    "generate_request_id",
    # Safe JSON parsing
    "safe_json_loads",
    "parse_json_field",
    "ParseResult",
    "TrustMeta",
]
