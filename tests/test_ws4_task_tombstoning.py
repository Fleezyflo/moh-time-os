"""WS4 S4.6 — source-scoped tombstoning for the shared tasks table."""

import sqlite3

from lib.collectors.reconcile import tombstone_missing


def _tasks_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, source TEXT, source_id TEXT, title TEXT)"
    )
    conn.executemany("INSERT INTO tasks (id, source, source_id, title) VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return path


def test_tombstone_deletes_rows_not_in_seen_set(tmp_path):
    db = _tasks_db(
        tmp_path / "t.db",
        [
            ("gtask_a", "google_tasks", "a", "A"),
            ("gtask_b", "google_tasks", "b", "B"),  # will be deleted upstream
            ("asana_x", "asana", "x", "X"),  # different source, untouched
        ],
    )
    deleted = tombstone_missing(str(db), table="tasks", source="google_tasks", seen_ids={"gtask_a"})
    assert deleted == 1

    conn = sqlite3.connect(str(db))
    remaining = {r[0] for r in conn.execute("SELECT id FROM tasks").fetchall()}
    conn.close()
    assert remaining == {"gtask_a", "asana_x"}


def test_tombstone_noop_on_empty_seen_set(tmp_path):
    """Empty seen set = fetch failure; must NOT wipe the table."""
    db = _tasks_db(tmp_path / "t.db", [("gtask_a", "google_tasks", "a", "A")])
    deleted = tombstone_missing(str(db), table="tasks", source="google_tasks", seen_ids=set())
    assert deleted == 0

    conn = sqlite3.connect(str(db))
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    conn.close()
    assert count == 1


def test_tasks_collector_reconciles_after_store(tmp_path, monkeypatch):
    """TasksCollector.sync must tombstone with the seen ids derived from the STORED rows."""
    from unittest.mock import MagicMock

    import lib.collectors.tasks as tasks_mod

    store = MagicMock()
    store.db_path = str(tmp_path / "ignored.db")  # never opened (tombstone stubbed)
    store.insert_many.return_value = 2

    collector = tasks_mod.TasksCollector(config={}, store=store)
    # Stub collect/transform so no Google API is touched. base.sync() will store
    # the transform output and stash it on self._last_synced_rows. The fetch is
    # marked complete so tombstoning is allowed to run.
    monkeypatch.setattr(
        collector, "collect", lambda: {"tasks": [], "lists": [], "_primary_fetch_complete": True}
    )
    monkeypatch.setattr(
        collector,
        "transform",
        lambda raw: [
            {"id": "gtask_a", "source": "google_tasks", "source_id": "a", "title": "A"},
            {"id": "gtask_b", "source": "google_tasks", "source_id": "b", "title": "B"},
        ],
    )

    captured = {}

    def _fake_tombstone(db_path, *, table, source, seen_ids):
        captured["table"] = table
        captured["source"] = source
        captured["seen_ids"] = seen_ids
        return 0

    monkeypatch.setattr(tasks_mod, "tombstone_missing", _fake_tombstone)

    collector.sync()

    assert captured["table"] == "tasks"
    assert captured["source"] == "google_tasks"
    assert captured["seen_ids"] == {"gtask_a", "gtask_b"}


def test_tasks_collector_seen_set_is_stored_rows_not_second_fetch(tmp_path, monkeypatch):
    """Regression (data-loss): the seen-set must come from the STORED rows, not a
    second collect(). A divergent/partial second fetch must NOT shrink the seen-set
    (which would tombstone just-stored live rows). Proven by: collect() is called
    exactly ONCE, and the seen-set equals what was stored even though a hypothetical
    second collect() would return fewer rows.
    """
    from unittest.mock import MagicMock

    import lib.collectors.tasks as tasks_mod

    store = MagicMock()
    store.db_path = str(tmp_path / "ignored.db")
    store.insert_many.return_value = 3

    collector = tasks_mod.TasksCollector(config={}, store=store)

    collect_calls = {"n": 0}

    def _collect():
        # First (and only legitimate) call returns the full set; a SECOND call
        # would return a partial set (simulating a transient per-list failure).
        collect_calls["n"] += 1
        if collect_calls["n"] == 1:
            return {
                "tasks": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                "lists": [],
                "_primary_fetch_complete": True,
            }
        return {"tasks": [{"id": "a"}], "lists": [], "_primary_fetch_complete": True}  # 2nd fetch

    monkeypatch.setattr(collector, "collect", _collect)
    monkeypatch.setattr(
        collector,
        "transform",
        lambda raw: [
            {"id": f"gtask_{t['id']}", "source": "google_tasks", "source_id": t["id"], "title": ""}
            for t in raw.get("tasks", [])
        ],
    )

    captured = {}

    def _fake_tombstone(db_path, *, table, source, seen_ids):
        captured["seen_ids"] = seen_ids
        return 0

    monkeypatch.setattr(tasks_mod, "tombstone_missing", _fake_tombstone)

    collector.sync()

    # collect() ran exactly once (no divergent second fetch), and the seen-set is
    # the full stored set — so b and c are NOT tombstoned.
    assert collect_calls["n"] == 1
    assert captured["seen_ids"] == {"gtask_a", "gtask_b", "gtask_c"}


def test_tasks_collector_skips_tombstone_on_partial_fetch(tmp_path, monkeypatch):
    """Regression (data-loss): a PARTIAL task-list fetch must NOT tombstone, because
    the seen-set is incomplete and would delete still-live tasks from failed lists."""
    from unittest.mock import MagicMock

    import lib.collectors.tasks as tasks_mod

    store = MagicMock()
    store.db_path = str(tmp_path / "ignored.db")
    store.insert_many.return_value = 1

    collector = tasks_mod.TasksCollector(config={}, store=store)
    # A list failed -> _primary_fetch_complete is False even though some tasks came back.
    monkeypatch.setattr(
        collector,
        "collect",
        lambda: {"tasks": [{"id": "a"}], "lists": [], "_primary_fetch_complete": False},
    )
    monkeypatch.setattr(
        collector,
        "transform",
        lambda raw: [{"id": "gtask_a", "source": "google_tasks", "source_id": "a", "title": ""}],
    )

    called = {"n": 0}

    def _fake_tombstone(db_path, *, table, source, seen_ids):
        called["n"] += 1
        return 0

    monkeypatch.setattr(tasks_mod, "tombstone_missing", _fake_tombstone)

    collector.sync()

    assert called["n"] == 0  # tombstone skipped on partial fetch -> no live rows deleted


def test_asana_collector_reconciles_after_store(tmp_path, monkeypatch):
    """AsanaCollector.sync must tombstone source='asana' rows after storing."""
    from unittest.mock import MagicMock

    import lib.collectors.asana as asana_mod

    store = MagicMock()
    store.db_path = str(tmp_path / "ignored.db")  # never opened (tombstone stubbed)
    store.insert_many.return_value = 1

    collector = asana_mod.AsanaCollector(config={}, store=store)
    raw = {
        "tasks": [{"gid": "111", "name": "Live task"}],
        "subtasks_by_parent": {},
        "stories_by_task": {},
        "dependencies_by_task": {},
        "attachments_by_task": {},
        "portfolios": [],
        "goals": [],
        "_secondary_fetch_errors": {},
        "_primary_fetch_complete": True,
    }
    monkeypatch.setattr(collector, "collect", lambda: raw)

    captured = {}

    def _fake_tombstone(db_path, *, table, source, seen_ids):
        captured.update(table=table, source=source, seen_ids=seen_ids)
        return 0

    monkeypatch.setattr(asana_mod, "tombstone_missing", _fake_tombstone)

    collector.sync()

    assert captured["table"] == "tasks"
    assert captured["source"] == "asana"
    assert captured["seen_ids"] == {"asana_111"}


def test_asana_collector_skips_tombstone_on_partial_fetch(tmp_path, monkeypatch):
    """Regression (data-loss): a PARTIAL Asana project fetch must NOT tombstone."""
    from unittest.mock import MagicMock

    import lib.collectors.asana as asana_mod

    store = MagicMock()
    store.db_path = str(tmp_path / "ignored.db")
    store.insert_many.return_value = 1

    collector = asana_mod.AsanaCollector(config={}, store=store)
    raw = {
        "tasks": [{"gid": "111", "name": "Live task"}],
        "subtasks_by_parent": {},
        "stories_by_task": {},
        "dependencies_by_task": {},
        "attachments_by_task": {},
        "portfolios": [],
        "goals": [],
        "_secondary_fetch_errors": {},
        "_primary_fetch_complete": False,  # a project fetch failed
    }
    monkeypatch.setattr(collector, "collect", lambda: raw)

    called = {"n": 0}

    def _fake_tombstone(db_path, *, table, source, seen_ids):
        called["n"] += 1
        return 0

    monkeypatch.setattr(asana_mod, "tombstone_missing", _fake_tombstone)

    collector.sync()

    assert called["n"] == 0  # tombstone skipped on partial fetch
