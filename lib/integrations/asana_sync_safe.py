"""
Outbox-safe AsanaSyncManager wrapper.

Wraps sync_task_to_asana (both create and update paths) with durable-intent
tracking. The existing AsanaSyncManager makes direct external API calls to
Asana via AsanaWriter without recording intent first. This wrapper adds:

1. Idempotent intent check before external call
2. Durable intent record
3. Fulfilled/failed marking after external result
4. Retry-safe behavior via idempotency keys

This module is the ONLY sanctioned path for Asana sync mutations.
"""

import hashlib
import logging

from lib.integrations.asana_sync import AsanaSyncManager, SyncResult
from lib.outbox import SideEffectOutbox, get_outbox

logger = logging.getLogger(__name__)

_HANDLER = "asana_sync"


def _idem_key(action: str, local_task_id: str, project_gid: str) -> str:
    """Generate deterministic idempotency key for Asana sync."""
    digest = hashlib.sha256(f"{action}:{local_task_id}:{project_gid}".encode()).hexdigest()[:16]
    return f"asana_{action}_{digest}"


class SafeAsanaSyncManager:
    """Outbox-protected AsanaSyncManager facade.

    Wraps sync_task_to_asana so both create and update paths go through
    the durable-intent outbox before making external Asana API calls.
    """

    def __init__(
        self,
        manager: AsanaSyncManager | None = None,
        outbox: SideEffectOutbox | None = None,
    ):
        self._manager = manager or AsanaSyncManager(_direct_call_allowed=True)
        self._outbox = outbox or get_outbox()

    def sync_task_to_asana(
        self,
        local_task_id: str,
        project_gid: str,
    ) -> SyncResult:
        """Sync a local task to Asana with outbox protection.

        Covers both create (new task) and update (existing mapping) paths.
        The idempotency key is based on task ID + project GID, so retries
        with the same arguments are safe.
        """
        idem_key = _idem_key("sync_task", local_task_id, project_gid)

        # Check for already-fulfilled intent
        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return SyncResult(
                success=True,
                local_id=local_task_id,
                asana_gid=fulfilled.get("external_resource_id"),
                action="fulfilled_from_outbox",
            )

        # Record durable intent BEFORE external call
        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="sync_task",
            payload={
                "local_task_id": local_task_id,
                "project_gid": project_gid,
            },
            idempotency_key=idem_key,
        )

        # Delegate to underlying manager (which calls AsanaWriter)
        result = self._manager.sync_task_to_asana(local_task_id, project_gid)

        if result.success and result.asana_gid:
            self._outbox.mark_fulfilled(
                intent_id,
                external_resource_id=result.asana_gid,
            )
        elif not result.success:
            self._outbox.mark_failed(
                intent_id,
                error=result.error or "Unknown sync error",
            )

        return result

    def sync_completion(self, local_task_id: str) -> SyncResult:
        """Mark task complete in Asana with outbox protection."""
        idem_key = f"asana_complete_{hashlib.sha256(local_task_id.encode()).hexdigest()[:16]}"

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return SyncResult(
                success=True,
                local_id=local_task_id,
                asana_gid=fulfilled.get("external_resource_id"),
                action="fulfilled_from_outbox",
            )

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="sync_completion",
            payload={"local_task_id": local_task_id},
            idempotency_key=idem_key,
        )

        result = self._manager.sync_completion(local_task_id)

        if result.success:
            self._outbox.mark_fulfilled(
                intent_id,
                external_resource_id=result.asana_gid or local_task_id,
            )
        else:
            self._outbox.mark_failed(
                intent_id,
                error=result.error or "Unknown completion error",
            )

        return result

    def post_status_comment(self, local_task_id: str, comment: str = "") -> SyncResult:
        """Post a status comment with outbox protection."""
        digest = hashlib.sha256(f"{local_task_id}:{comment[:100]}".encode()).hexdigest()[:16]
        idem_key = f"asana_comment_{digest}"

        fulfilled = self._outbox.get_fulfilled_intent(idempotency_key=idem_key)
        if fulfilled:
            return SyncResult(
                success=True,
                local_id=local_task_id,
                asana_gid=fulfilled.get("external_resource_id"),
                action="fulfilled_from_outbox",
            )

        intent_id = self._outbox.record_intent(
            handler=_HANDLER,
            action="post_status_comment",
            payload={"local_task_id": local_task_id, "comment": comment[:200]},
            idempotency_key=idem_key,
        )

        result = self._manager.post_status_comment(local_task_id, comment)

        if result.success:
            self._outbox.mark_fulfilled(
                intent_id,
                external_resource_id=result.asana_gid or local_task_id,
            )
        else:
            self._outbox.mark_failed(
                intent_id,
                error=result.error or "Unknown comment error",
            )

        return result

    def bulk_sync(
        self,
        task_ids: list[str],
        project_gid: str,
    ) -> list[SyncResult]:
        """Sync multiple tasks with outbox protection on each.

        Each task goes through sync_task_to_asana individually, so every
        external call gets its own durable intent record.
        """
        results = []
        for task_id in task_ids:
            result = self.sync_task_to_asana(task_id, project_gid)
            results.append(result)
        return results
