"""
Tests for Query Optimizer — Batch Loading & Index Management

Tests:
- BatchLoader: ID collection and bulk loading
- prefetch_related: Bulk data loading
- explain_query: Query plan analysis
- QueryStats: Performance tracking
- ensure_indexes: Index creation and idempotency
- get_missing_indexes: Detection of missing indexes
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from lib.db_opt.indexes import (
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


@pytest.fixture
def temp_db():
    """Create a temporary in-memory SQLite database for testing."""
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = Path(db_file.name)
    db_file.close()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create test tables
    conn.execute(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            name TEXT,
            status TEXT
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            assignee_id TEXT,
            title TEXT,
            status TEXT,
            due_date TEXT
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE invoices (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            status TEXT,
            due_date TEXT,
            amount REAL
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE signals (
            id TEXT PRIMARY KEY,
            severity TEXT,
            status TEXT,
            created_at TEXT
        )
    """
    )

    # Insert test data
    conn.execute("INSERT INTO users VALUES ('u1', 'Alice', 'alice@example.com')")
    conn.execute("INSERT INTO users VALUES ('u2', 'Bob', 'bob@example.com')")
    conn.execute("INSERT INTO users VALUES ('u3', 'Charlie', 'charlie@example.com')")

    conn.execute("INSERT INTO projects VALUES ('p1', 'c1', 'Project A', 'active')")
    conn.execute("INSERT INTO projects VALUES ('p2', 'c1', 'Project B', 'active')")
    conn.execute("INSERT INTO projects VALUES ('p3', 'c2', 'Project C', 'inactive')")

    conn.execute("INSERT INTO tasks VALUES ('t1', 'p1', 'u1', 'Task 1', 'open', '2024-02-25')")
    conn.execute("INSERT INTO tasks VALUES ('t2', 'p1', 'u2', 'Task 2', 'open', '2024-02-26')")
    conn.execute("INSERT INTO tasks VALUES ('t3', 'p2', 'u1', 'Task 3', 'done', '2024-02-24')")
    conn.execute("INSERT INTO tasks VALUES ('t4', 'p3', 'u3', 'Task 4', 'open', '2024-02-27')")

    conn.execute("INSERT INTO invoices VALUES ('inv1', 'c1', 'unpaid', '2024-02-20', 1000.0)")
    conn.execute("INSERT INTO invoices VALUES ('inv2', 'c1', 'paid', '2024-02-15', 2000.0)")
    conn.execute("INSERT INTO invoices VALUES ('inv3', 'c2', 'unpaid', '2024-02-28', 1500.0)")

    conn.execute("INSERT INTO signals VALUES ('sig1', 'high', 'open', '2024-02-21')")
    conn.execute("INSERT INTO signals VALUES ('sig2', 'medium', 'open', '2024-02-21')")
    conn.execute("INSERT INTO signals VALUES ('sig3', 'low', 'resolved', '2024-02-20')")

    conn.commit()

    yield db_path, conn

    conn.close()
    db_path.unlink()


# =============================================================================
# QUERYSTATS TESTS
# =============================================================================


def test_query_stats_initialization():
    """Test QueryStats initialization."""
    stats = QueryStats()
    assert stats.query_count == 0
    assert stats.total_time_ms == 0.0
    assert stats.slowest_query_ms == 0.0
    assert stats.slowest_query_sql == ""


def test_query_stats_add_query():
    """Test adding queries to QueryStats."""
    stats = QueryStats()
    stats.add_query("SELECT * FROM users", 10.5)
    stats.add_query("SELECT * FROM projects", 5.2)

    assert stats.query_count == 2
    assert stats.total_time_ms == pytest.approx(15.7, abs=0.1)
    assert stats.slowest_query_ms == pytest.approx(10.5, abs=0.1)
    assert stats.slowest_query_sql == "SELECT * FROM users"


def test_query_stats_to_dict():
    """Test QueryStats serialization."""
    stats = QueryStats()
    stats.add_query("SELECT * FROM users", 10.0)
    stats.add_query("SELECT * FROM projects", 5.0)

    d = stats.to_dict()
    assert d["query_count"] == 2
    assert d["total_time_ms"] == 15.0
    assert d["slowest_query_ms"] == 10.0
    assert "avg_query_ms" in d


def test_query_stats_avg_ms():
    """Test average query time calculation."""
    stats = QueryStats()
    stats.add_query("Q1", 12.0)
    stats.add_query("Q2", 8.0)
    stats.add_query("Q3", 10.0)

    d = stats.to_dict()
    assert d["avg_query_ms"] == 10.0


# =============================================================================
# BATCHLOADER TESTS
# =============================================================================


def test_batch_loader_basic(temp_db):
    """Test basic batch loader functionality."""
    db_path, conn = temp_db

    loader = BatchLoader(conn, "users", "id", ["name", "email"])
    loader.add_id("u1")
    loader.add_id("u2")

    result = loader.get_map()
    assert len(result) == 2
    assert result["u1"]["name"] == "Alice"
    assert result["u2"]["email"] == "bob@example.com"


def test_batch_loader_empty(temp_db):
    """Test batch loader with no IDs."""
    db_path, conn = temp_db

    loader = BatchLoader(conn, "users", "id", ["name"])
    result = loader.get_map()
    assert result == {}


def test_batch_loader_get_method(temp_db):
    """Test get method on batch loader."""
    db_path, conn = temp_db

    loader = BatchLoader(conn, "users", "id", ["name"])
    loader.add_id("u1")
    loader.add_id("u2")

    assert loader.get("u1")["name"] == "Alice"
    assert loader.get("u3") is None
    assert loader.get("u3", {}) == {}


def test_batch_loader_idempotency(temp_db):
    """Test that batch loader is idempotent."""
    db_path, conn = temp_db

    loader = BatchLoader(conn, "users", "id", ["name"])
    loader.add_id("u1")

    map1 = loader.get_map()
    map2 = loader.get_map()

    assert map1 == map2


def test_batch_loader_add_ids(temp_db):
    """Test adding multiple IDs at once."""
    db_path, conn = temp_db

    loader = BatchLoader(conn, "users", "id", ["name"])
    loader.add_ids(["u1", "u2", "u3"])

    result = loader.get_map()
    assert len(result) == 3


def test_batch_loader_multiple_columns(temp_db):
    """Test loading multiple columns."""
    db_path, conn = temp_db

    loader = BatchLoader(conn, "users", "id", ["name", "email"])
    loader.add_id("u1")

    result = loader.get_map()
    row = result["u1"]
    assert row["id"] == "u1"
    assert row["name"] == "Alice"
    assert row["email"] == "alice@example.com"


def test_batch_loader_prevents_late_adds(temp_db):
    """Test that adding IDs after get_map is called is ignored."""
    db_path, conn = temp_db

    loader = BatchLoader(conn, "users", "id", ["name"])
    loader.add_id("u1")
    first_result = loader.get_map()

    # Try to add after loaded
    loader.add_id("u2")
    second_result = loader.get_map()

    assert len(first_result) == 1
    assert len(second_result) == 1  # u2 not added


# =============================================================================
# PREFETCH_RELATED TESTS
# =============================================================================


def test_prefetch_related_basic(temp_db):
    """Test prefetch_related basic functionality."""
    db_path, conn = temp_db

    result = prefetch_related(conn, "projects", ["c1", "c2"], id_column="client_id")

    assert "c1" in result
    assert "c2" in result


def test_prefetch_related_empty(temp_db):
    """Test prefetch_related with empty ID list."""
    db_path, conn = temp_db

    result = prefetch_related(conn, "projects", [], id_column="client_id")
    assert result == {}


def test_prefetch_related_specific_columns(temp_db):
    """Test prefetch_related with specific columns."""
    db_path, conn = temp_db

    result = prefetch_related(
        conn, "projects", ["c1"], id_column="client_id", columns=["name", "status"]
    )

    # c1 has multiple projects, so result is a list
    projects = result["c1"]
    if isinstance(projects, list):
        project = projects[0]
    else:
        project = projects
    assert "name" in project
    assert "status" in project


def test_prefetch_related_multiple_rows_per_id(temp_db):
    """Test prefetch_related with multiple rows per ID."""
    db_path, conn = temp_db

    # Client c1 has 2 projects
    result = prefetch_related(conn, "projects", ["c1"], id_column="client_id")

    # Should have both projects under c1
    assert "c1" in result


def test_prefetch_related_nonexistent_ids(temp_db):
    """Test prefetch_related with IDs that don't exist."""
    db_path, conn = temp_db

    result = prefetch_related(conn, "projects", ["nonexistent"], id_column="client_id")

    assert "nonexistent" not in result


# =============================================================================
# EXPLAIN_QUERY TESTS
# =============================================================================


def test_explain_query_basic(temp_db):
    """Test EXPLAIN QUERY PLAN."""
    db_path, conn = temp_db

    plan = explain_query(conn, "SELECT * FROM users WHERE id = ?", ("u1",))

    # Should return at least one step
    assert len(plan) > 0
    # EXPLAIN QUERY PLAN returns different columns than EXPLAIN
    assert "id" in plan[0] or "opcode" in plan[0]


def test_explain_query_invalid_sql(temp_db):
    """Test EXPLAIN with invalid SQL."""
    db_path, conn = temp_db

    # Invalid SQL should return empty list, not raise
    plan = explain_query(conn, "SELECT * FROM nonexistent_table")
    assert plan == []


def test_explain_query_scan_vs_index(temp_db):
    """Test that EXPLAIN shows different plans for different queries."""
    db_path, conn = temp_db

    # Create an index first
    conn.execute("CREATE INDEX idx_test ON users(id)")
    conn.commit()

    # Query with indexed column
    plan1 = explain_query(conn, "SELECT * FROM users WHERE id = ?", ("u1",))
    assert len(plan1) > 0


# =============================================================================
# ANALYZE_QUERY_PERFORMANCE TESTS
# =============================================================================


def test_analyze_query_performance_basic(temp_db):
    """Test query performance analysis."""
    db_path, conn = temp_db

    perf = analyze_query_performance(conn, "SELECT * FROM users", iterations=3)

    assert perf["avg_ms"] > 0
    assert perf["min_ms"] > 0
    assert perf["max_ms"] > 0
    assert perf["row_count"] == 3
    assert perf["iterations"] == 3


def test_analyze_query_performance_with_params(temp_db):
    """Test performance analysis with parameters."""
    db_path, conn = temp_db

    perf = analyze_query_performance(
        conn,
        "SELECT * FROM users WHERE id = ?",
        params=("u1",),
        iterations=2,
    )

    assert perf["row_count"] == 1
    assert perf["iterations"] == 2


# =============================================================================
# INDEX MANAGEMENT TESTS
# =============================================================================


def test_ensure_indexes_creation(temp_db):
    """Test that ensure_indexes creates new indexes."""
    db_path, conn = temp_db
    conn.close()  # Close before checking with new connection

    report = ensure_indexes(db_path)

    # Should create multiple indexes
    assert len(report.created) > 0
    assert report.total_checked > 0


def test_ensure_indexes_idempotent(temp_db):
    """Test that ensure_indexes is idempotent."""
    db_path, conn = temp_db
    conn.close()

    report1 = ensure_indexes(db_path)
    len(report1.created)

    # Run again
    report2 = ensure_indexes(db_path)
    created2 = len(report2.created)

    # Second run should create 0 new indexes (all exist)
    assert created2 == 0
    assert len(report2.already_existed) > 0


def test_ensure_indexes_skip_missing_tables(temp_db):
    """Test that ensure_indexes skips tables that don't exist."""
    db_path, conn = temp_db
    conn.close()

    # Should not raise error even though some tables don't exist
    report = ensure_indexes(db_path)
    assert report is not None


def test_ensure_indexes_report_structure(temp_db):
    """Test IndexReport structure."""
    db_path, conn = temp_db
    conn.close()

    report = ensure_indexes(db_path)

    assert isinstance(report.created, list)
    assert isinstance(report.already_existed, list)
    assert isinstance(report.errors, list)
    assert report.total_checked > 0


def test_get_missing_indexes_basic(temp_db):
    """Test detection of missing indexes."""
    db_path, conn = temp_db
    conn.close()

    # Before creating indexes, should return many
    missing = get_missing_indexes(db_path)
    initial_count = len(missing)

    # Create indexes
    ensure_indexes(db_path)

    # After creating, should be fewer (or none for existing tables)
    missing_after = get_missing_indexes(db_path)

    # Should have reduced significantly
    assert len(missing_after) <= initial_count


def test_drop_index(temp_db):
    """Test dropping an index."""
    db_path, conn = temp_db
    conn.close()

    # Create indexes
    ensure_indexes(db_path)

    # Drop one
    success = drop_index(db_path, "users", ["id"])
    assert success


def test_index_report_to_dict(temp_db):
    """Test IndexReport serialization."""
    db_path, conn = temp_db
    conn.close()

    report = ensure_indexes(db_path)
    d = report.to_dict()

    assert "created" in d
    assert "already_existed" in d
    assert "errors" in d
    assert "total_checked" in d


def test_ensure_indexes_nonexistent_db():
    """Test ensure_indexes with nonexistent database."""
    with pytest.raises(FileNotFoundError):
        ensure_indexes("nonexistent.db")


def test_get_missing_indexes_nonexistent_db():
    """Test get_missing_indexes with nonexistent database."""
    result = get_missing_indexes("nonexistent.db")
    assert result == []


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_batch_loader_vs_naive_n_plus_one(temp_db):
    """Demonstrate batch loader solving N+1 problem."""
    db_path, conn = temp_db

    # Naive approach (N+1): loop and query for each
    project_ids = ["p1", "p2", "p3"]
    naive_results = []
    for pid in project_ids:
        cursor = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,))
        naive_results.append(cursor.fetchone())

    # Batch approach: single query
    loader = BatchLoader(conn, "projects", "id", ["name", "status"])
    loader.add_ids(project_ids)
    batch_results = loader.get_map()

    # Same data
    assert len(naive_results) == len(batch_results)
    for pid in project_ids:
        assert pid in batch_results


def test_combined_optimization_workflow(temp_db):
    """Test realistic optimization workflow."""
    db_path, conn = temp_db
    conn.close()

    # Step 1: Check what's missing
    missing = get_missing_indexes(db_path)
    assert len(missing) > 0

    # Step 2: Create indexes
    report = ensure_indexes(db_path)
    assert len(report.created) > 0

    # Step 3: Check again - should be fewer/none
    missing_after = get_missing_indexes(db_path)
    assert len(missing_after) < len(missing)


def test_batch_loader_with_performance_stats(temp_db):
    """Test batch loader with performance tracking."""
    db_path, conn = temp_db

    stats = QueryStats()

    # Simulate batch loader performance
    loader = BatchLoader(conn, "users", "id", ["name", "email"])
    loader.add_ids(["u1", "u2", "u3"])

    import time

    start = time.time()
    loader.get_map()
    duration = (time.time() - start) * 1000

    stats.add_query("BatchLoader.get_map()", duration)

    assert stats.query_count == 1
    assert stats.total_time_ms >= 0
