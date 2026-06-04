"""Edge-case tests for the StateStore.query() read-only guard.

The core accept/reject contract (INSERT/UPDATE/DELETE/CREATE/DROP/ALTER reject,
SELECT allows) is pinned by TestWritePathRule / TestWritePathBehavioralExtended in
tests/test_audit_remediation_v3*.py. This file locks the *parser* behavior the guard
relies on: leading whitespace/newlines, leading SQL comments, case-insensitivity,
REPLACE, and the read forms used across the codebase (WITH...SELECT, EXPLAIN, PRAGMA).
"""

import tempfile

import pytest

from lib.state_store import StateStore


@pytest.fixture
def store():
    StateStore._instance = None
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        s = StateStore(f.name)
        # A real table so allowed reads return rows rather than erroring on missing schema.
        s.execute_write("CREATE TABLE g (id TEXT PRIMARY KEY, name TEXT)")
        s.execute_write("INSERT INTO g (id, name) VALUES ('1', 'x')")
        yield s
        StateStore._instance = None


# ---- rejects: writes/DDL regardless of surrounding whitespace/comments/case ----


def test_rejects_replace(store):
    with pytest.raises(RuntimeError, match="read-only"):
        store.query("REPLACE INTO g (id, name) VALUES ('1', 'y')")


def test_rejects_lowercase_insert(store):
    with pytest.raises(RuntimeError, match="read-only"):
        store.query("insert into g (id) values ('2')")


def test_rejects_leading_whitespace_and_newlines(store):
    with pytest.raises(RuntimeError, match="read-only"):
        store.query("\n   \n   UPDATE g SET name = 'z' WHERE id = '1'")


def test_rejects_leading_line_comment(store):
    with pytest.raises(RuntimeError, match="read-only"):
        store.query("-- sneaky\nDELETE FROM g WHERE id = '1'")


def test_rejects_leading_block_comment(store):
    with pytest.raises(RuntimeError, match="read-only"):
        store.query("/* hidden */ DROP TABLE g")


# ---- allows: the read forms used across the codebase ----


def test_allows_select_with_leading_newline(store):
    rows = store.query("\n            SELECT * FROM g")
    assert len(rows) == 1


def test_allows_lowercase_select(store):
    rows = store.query("select id from g")
    assert rows[0]["id"] == "1"


def test_allows_with_cte_select(store):
    rows = store.query("WITH t AS (SELECT id FROM g) SELECT id FROM t")
    assert rows[0]["id"] == "1"


def test_allows_explain(store):
    # EXPLAIN returns opcode rows; just assert it does not raise.
    store.query("EXPLAIN SELECT * FROM g")


def test_allows_pragma_read(store):
    rows = store.query("PRAGMA table_info(g)")
    assert any(r["name"] == "id" for r in rows)


def test_allows_select_after_leading_comment(store):
    rows = store.query("-- comment\nSELECT name FROM g WHERE id = '1'")
    assert rows[0]["name"] == "x"
