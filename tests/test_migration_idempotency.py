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
