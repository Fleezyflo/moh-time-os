"""Database optimization and management utilities."""

from lib.db_opt.connection_pool import (
    ConnectionPool,
    PooledDatabaseAdapter,
    PoolStats,
)
from lib.db_opt.db_adapter import (
    DatabaseAdapter,
    PostgreSQLAdapter,
    SQLiteAdapter,
)
from lib.db_opt.indexes import (
    IndexReport,
    drop_index,
    ensure_indexes,
    get_missing_indexes,
)
from lib.db_opt.query_optimizer import (
    BatchLoader,
    QueryStats,
    analyze_query_performance,
    explain_query,
    prefetch_related,
)
from lib.db_opt.sql_compat import (
    detect_dialect,
    translate_pg_to_sqlite,
    translate_sqlite_to_pg,
)

__all__ = [
    # Adapters
    "DatabaseAdapter",
    "SQLiteAdapter",
    "PostgreSQLAdapter",
    # Connection pooling
    "ConnectionPool",
    "PoolStats",
    "PooledDatabaseAdapter",
    # SQL compatibility
    "translate_sqlite_to_pg",
    "translate_pg_to_sqlite",
    "detect_dialect",
    # Query optimization
    "BatchLoader",
    "QueryStats",
    "prefetch_related",
    "explain_query",
    "analyze_query_performance",
    # Index management
    "IndexReport",
    "ensure_indexes",
    "get_missing_indexes",
    "drop_index",
]
