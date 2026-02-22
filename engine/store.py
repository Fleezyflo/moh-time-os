import json
import sqlite3
import time
from typing import Any


def now_ms() -> int:
    return int(time.time() * 1000)


def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def upsert_config(con: sqlite3.Connection, key: str, value: Any) -> None:
    con.execute(
        "INSERT INTO config_kv(key,value_json,updated_at_ms) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at_ms=excluded.updated_at_ms",
        (key, json.dumps(value, ensure_ascii=False), now_ms()),
    )


def insert_raw_event(
    con: sqlite3.Connection, *, id: str, surface: str, source_ref: str, payload: Any
) -> None:
    con.execute(
        "INSERT OR REPLACE INTO events_raw(id,surface,source_ref,captured_at_ms,payload_json) VALUES(?,?,?,?,?)",
        (id, surface, source_ref, now_ms(), json.dumps(payload, ensure_ascii=False)),
    )


def insert_proposal(
    con: sqlite3.Connection,
    *,
    id: str,
    kind: str,
    payload: Any,
    attribution: Any,
    assumptions: Any | None = None,
) -> None:
    con.execute(
        "INSERT OR REPLACE INTO proposals(id,kind,payload_json,attribution_json,assumptions_json,created_at_ms) VALUES(?,?,?,?,?,?)",
        (
            id,
            kind,
            json.dumps(payload, ensure_ascii=False),
            json.dumps(attribution, ensure_ascii=False),
            json.dumps(assumptions, ensure_ascii=False) if assumptions is not None else None,
            now_ms(),
        ),
    )
