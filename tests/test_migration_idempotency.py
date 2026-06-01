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


# Heavy per-migration step functions to neutralize so we can exercise the
# guard -> migrate -> STAMP -> re-run-skip property without a full pre-v12
# schema. verify_schema must return True so migrate_to_spec_v12 reaches the
# stamp; backup_db is stubbed so no real backup I/O happens.
_NOOP_STEPS = {
    "migrate_to_spec_v12": [
        "backup_db",
        "drop_all_views",
        "migrate_tasks",
        "migrate_communications",
        "migrate_projects",
        "migrate_clients",
        "migrate_invoices",
        "migrate_commitments",
        "ensure_spec_tables",
        "recreate_items_view",
    ],
    "rebuild_schema_v12": [
        "backup_db",
        "drop_views",
        "rebuild_tasks",
        "rebuild_communications",
        "rebuild_projects",
        "recreate_items_view",
    ],
}


@pytest.mark.parametrize(
    "module",
    [migrate_to_spec_v12, rebuild_schema_v12],
    ids=["migrate_to_spec_v12", "rebuild_schema_v12"],
)
def test_migration_stamps_version_so_rerun_skips(tmp_path, monkeypatch, module):
    """The real idempotency property: a migration run on a DB BELOW the target
    must stamp user_version on success, so the SECOND run self-skips. Without the
    completion stamp the guard is unreachable for the DBs these scripts target
    and a re-run re-enters the destructive path.
    """
    db_file = tmp_path / "pre_v12.db"
    _seed_db(db_file, schema.SCHEMA_VERSION - 1)  # below target -> first run proceeds
    # rebuild_schema_v12 has an inline post-commit verification block that reads
    # sqlite_master for tasks/communications/projects; create empty stand-ins so
    # that cosmetic check does not crash once the heavy steps are stubbed out.
    _conn = sqlite3.connect(str(db_file))
    for tbl in ("communications", "projects"):
        _conn.execute(f"CREATE TABLE IF NOT EXISTS {tbl} (id TEXT)")
    _conn.commit()
    _conn.close()

    monkeypatch.setattr(module.paths, "db_path", lambda: db_file)
    monkeypatch.setattr(module.paths, "data_dir", lambda: tmp_path)
    # Neutralize the heavy schema-transform steps; we only assert the stamp.
    for fn in _NOOP_STEPS[module.__name__.rsplit(".", 1)[-1]]:
        if hasattr(module, fn):
            monkeypatch.setattr(module, fn, lambda *a, **k: None)
    # migrate_to_spec_v12 gates the stamp behind verify_schema() -> force True.
    if hasattr(module, "verify_schema"):
        monkeypatch.setattr(module, "verify_schema", lambda *a, **k: True)

    # First run: below target, so it proceeds (does NOT return the skip dict)
    # and must stamp the version.
    first = module.run_migration()
    assert first != {"skipped": True, "reason": "already at schema version"}

    conn = sqlite3.connect(str(db_file))
    stamped = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    assert stamped == schema.SCHEMA_VERSION, "migration must stamp user_version on success"

    # Second run: now at target -> guard must self-skip.
    second = module.run_migration()
    assert second == {"skipped": True, "reason": "already at schema version"}


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
