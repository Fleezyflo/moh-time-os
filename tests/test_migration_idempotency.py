"""S3.2: the two destructive v12 migrations must self-skip when the DB is
already at or above the target schema version (PRAGMA user_version).

S3.6: v32_signal_lifecycle must not commit the ADD COLUMN loop before its
backfill; a backfill failure must roll back the column adds.
"""

import sqlite3
from pathlib import Path

import pytest

from lib import schema
from lib.migrations import migrate_to_spec_v12, rebuild_schema_v12


def _seed_db(path: Path, user_version: int) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO tasks (id, title) VALUES ('t1', 'keep me')")
    conn.execute(f"PRAGMA user_version = {user_version}")
    conn.commit()
    conn.close()


def _row_count(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    n = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    conn.close()
    return n


@pytest.mark.parametrize(
    "module",
    [migrate_to_spec_v12, rebuild_schema_v12],
    ids=["migrate_to_spec_v12", "rebuild_schema_v12"],
)
def test_migration_self_skips_when_already_current(tmp_path, monkeypatch, module):
    db_file = tmp_path / "already_migrated.db"
    _seed_db(db_file, schema.SCHEMA_VERSION)  # already at target -> must skip

    monkeypatch.setattr(module.paths, "db_path", lambda: db_file)
    monkeypatch.setattr(module.paths, "data_dir", lambda: tmp_path)

    result = module.run_migration()

    assert result == {"skipped": True, "reason": "already at schema version"}
    assert _row_count(db_file) == 1


def test_v32_rolls_back_column_adds_when_backfill_fails(tmp_path, monkeypatch):
    """S3.6: v32 migrate() must not leave columns added-but-unbackfilled. A
    failure during the backfill must roll back the ALTER TABLE ADD COLUMN adds
    (atomic ALTER+backfill), so the schema is not half-applied.

    The entry point is migrate(db_path) (there is no run_migration in v32).
    """
    from lib.migrations import v32_signal_lifecycle as v32

    db_file = tmp_path / "v32.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE signal_state (signal_key TEXT PRIMARY KEY, detected_at TEXT, severity TEXT)"
    )
    conn.execute(
        "INSERT INTO signal_state (signal_key, detected_at, severity) "
        "VALUES ('s1', '2026-01-01', 'high')"
    )
    conn.commit()
    conn.close()

    # Force the FIRST backfill UPDATE (first_detected_at) to fail. sqlite3's C
    # Connection.execute is immutable, so wrap the connection in a proxy that
    # delegates everything except the first_detected_at backfill UPDATE.
    real_connect = sqlite3.connect

    class _FailingConn:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, sql, *args, **kwargs):
            if "UPDATE signal_state" in sql and "first_detected_at" in sql:
                raise sqlite3.OperationalError("simulated backfill failure")
            return self._inner.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def _wrapped_connect(*args, **kwargs):
        return _FailingConn(real_connect(*args, **kwargs))

    monkeypatch.setattr(v32.sqlite3, "connect", _wrapped_connect)

    with pytest.raises(sqlite3.OperationalError):
        v32.migrate(db_path=db_file)

    monkeypatch.undo()
    conn = sqlite3.connect(str(db_file))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(signal_state)")}
    conn.close()
    assert "first_detected_at" not in cols, "ALTER must roll back when backfill fails"
