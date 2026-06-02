"""Source-scoped tombstoning for append-only collectors.

Append-only collectors (Asana, Google Tasks) upsert rows but never delete,
so a task removed upstream lingers in SQLite forever. tombstone_missing()
deletes rows for one source whose ids were NOT seen in the latest fetch.

Empty-guard: when seen_ids is empty we treat it as a fetch failure and do
NOTHING, so a dead collector never wipes the table.

SQL is built via lib.safe_sql (validated identifiers, the codebase's single
approved S608 suppression) — no f-string SQL and no per-call noqa here.
"""

import logging
import sqlite3

from lib import safe_sql

logger = logging.getLogger(__name__)


def tombstone_missing(
    db_path: str,
    *,
    table: str,
    source: str,
    seen_ids: set[str],
) -> int:
    """Delete rows of `table` for `source` whose id is not in `seen_ids`.

    Returns the number of rows deleted. Returns 0 (no-op) when seen_ids is
    empty, to avoid mass-deleting on a failed fetch.
    """
    if not seen_ids:
        logger.warning(
            "tombstone_missing: empty seen set for source=%s table=%s -- skipping "
            "(treating as fetch failure, not 'all deleted')",
            source,
            table,
        )
        return 0

    # safe_sql validates `table` and emits only ?-placeholders for values; the
    # WHERE clause is hardcoded identifiers + bound params (no user data in SQL).
    # NOT IN: delete rows for this source whose id was not in the latest fetch.
    placeholders = safe_sql.in_placeholders(len(seen_ids))
    where = "source = ? AND id NOT IN (" + placeholders + ")"
    sql = safe_sql.delete(table, where=where)
    params = [source, *sorted(seen_ids)]

    # NB: FK enforcement is intentionally NOT enabled here. `time_blocks.task_id`
    # REFERENCES tasks(id) with no ON DELETE action, so `PRAGMA foreign_keys=ON`
    # would ABORT this DELETE whenever a tombstoned task has a scheduled block —
    # breaking tombstoning entirely once any scheduling exists. SQLite also
    # defaults foreign_keys OFF per-connection, matching the rest of the codebase's
    # delete paths (the Xero source-replace likewise does not enforce it). Cleaning
    # up dependent time_blocks for upstream-deleted tasks is a separate follow-up.
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        deleted = cur.rowcount
    finally:
        conn.close()

    if deleted:
        logger.info("Tombstoned %d stale %s rows for source=%s", deleted, table, source)
    return deleted
