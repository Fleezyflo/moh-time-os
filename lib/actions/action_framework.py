"""
Action Framework — Comprehensive action proposal, approval, and execution.

Manages:
- Proposing actions with risk classification
- Applying approval policies
- Executing approved actions
- Tracking action history with side effects
- Middleware hooks and dry-run mode
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
import sqlite3

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionSource(Enum):
    """Where the action was proposed from."""

    SIGNAL = "signal"
    PROPOSAL = "proposal"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class ActionStatus(Enum):
    """Action lifecycle status."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ActionProposal:
    """A proposed action waiting for approval or execution."""

    id: str
    type: str  # e.g., "task_create", "calendar_update"
    target_entity: str  # e.g., "task", "calendar", "email"
    target_id: str  # Entity ID being affected
    payload: dict  # Action data
    risk_level: RiskLevel
    source: ActionSource
    confidence_score: float  # 0.0-1.0
    requires_approval: bool
    status: ActionStatus = ActionStatus.PROPOSED
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejection_reason: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dict, handling Enum serialization."""
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        data["source"] = self.source.value
        data["status"] = self.status.value
        return data


@dataclass
class ActionResult:
    """Result of action execution."""

    action_id: str
    success: bool
    result_data: dict | None = None
    error: str | None = None
    execution_time_ms: int = 0
    side_effects: list[dict] = field(default_factory=list)
    executed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dict."""
        return asdict(self)


@dataclass
class ApprovalDecision:
    """Decision from approval policy evaluation."""

    approved: bool
    requires_approval: bool
    requires_two_approvals: bool
    reason: str
    policy_matched: str | None = None


class ActionFramework:
    """
    Main action framework for proposal, approval, and execution.

    Wires together:
    - Proposal creation with risk classification
    - Approval policy evaluation
    - Handler dispatch and execution
    - Execution result tracking
    """

    def __init__(self, store, policy_engine=None, approval_policies=None, dry_run: bool = False):
        self.store = store
        self.policy_engine = policy_engine
        self.approval_policies = approval_policies or {}
        self.dry_run = dry_run

        # Handler registry
        self.handlers: dict[str, Callable] = {}

        # Middleware hooks
        self.before_execute_hooks: list[Callable] = []
        self.after_execute_hooks: list[Callable] = []
        self.on_error_hooks: list[Callable] = []

        # Rate limiting: action_type -> (count, window_start_ms)
        self.rate_limits: dict[str, tuple[int, int]] = {}
        self.rate_limit_config: dict[str, int] = {}  # action_type -> max_per_minute

        # Idempotency: idempotency_key -> action_id
        self.idempotency_keys: dict[str, str] = {}

    def register_handler(self, action_type: str, handler: Callable[[dict], ActionResult]):
        """Register a handler for an action type."""
        self.handlers[action_type] = handler
        logger.info(f"Registered handler for action type: {action_type}")

    def register_before_execute_hook(self, hook: Callable):
        """Register a hook to run before action execution."""
        self.before_execute_hooks.append(hook)

    def register_after_execute_hook(self, hook: Callable):
        """Register a hook to run after action execution."""
        self.after_execute_hooks.append(hook)

    def register_on_error_hook(self, hook: Callable):
        """Register a hook to run on execution error."""
        self.on_error_hooks.append(hook)

    def set_rate_limit(self, action_type: str, max_per_minute: int):
        """Set rate limit for an action type."""
        self.rate_limit_config[action_type] = max_per_minute

    def propose_action(
        self,
        action_type: str,
        target_entity: str,
        target_id: str,
        payload: dict,
        risk_level: RiskLevel,
        source: ActionSource,
        confidence_score: float = 0.8,
        requires_approval: bool = True,
        idempotency_key: str | None = None,
    ) -> str:
        """
        Propose a new action for approval and execution.

        Returns action_id.
        """
        # Check idempotency
        if idempotency_key:
            if idempotency_key in self.idempotency_keys:
                logger.info(f"Duplicate action with idempotency key: {idempotency_key}")
                return self.idempotency_keys[idempotency_key]

        # Create proposal
        action_id = f"action_{uuid4().hex[:12]}"
        proposal = ActionProposal(
            id=action_id,
            type=action_type,
            target_entity=target_entity,
            target_id=target_id,
            payload=payload,
            risk_level=risk_level,
            source=source,
            confidence_score=confidence_score,
            requires_approval=requires_approval,
        )

        # Evaluate approval policy
        approval_decision = None
        if self.policy_engine:
            approval_decision = self.policy_engine.evaluate(proposal)

        # Auto-approve if policy allows
        if (
            approval_decision
            and approval_decision.approved
            and not approval_decision.requires_approval
        ):
            proposal.status = ActionStatus.APPROVED
            proposal.approved_at = datetime.now().isoformat()
            proposal.approved_by = "system_policy"
            logger.info(
                f"Auto-approved action {action_id} by policy: {approval_decision.policy_matched}"
            )

        # Store proposal
        self._store_proposal(proposal)

        # Track idempotency key
        if idempotency_key:
            self.idempotency_keys[idempotency_key] = action_id

        logger.info(
            f"Proposed action {action_id}: {action_type} "
            f"(risk={risk_level.value}, status={proposal.status.value})"
        )

        return action_id

    def approve_action(
        self, action_id: str, approved_by: str, additional_context: dict | None = None
    ) -> bool:
        """Approve a pending action."""
        proposal = self._get_proposal(action_id)
        if not proposal:
            logger.error(f"Action not found: {action_id}")
            return False

        if proposal["status"] != ActionStatus.PROPOSED.value:
            logger.error(f"Cannot approve action in state: {proposal['status']}")
            return False

        update = {
            "status": ActionStatus.APPROVED.value,
            "approved_by": approved_by,
            "approved_at": datetime.now().isoformat(),
        }

        if additional_context:
            payload = (
                json.loads(proposal["payload"])
                if isinstance(proposal["payload"], str)
                else proposal["payload"]
            )
            payload["approval_context"] = additional_context
            update["payload"] = json.dumps(payload)

        self.store.update("actions", action_id, update)
        logger.info(f"Action {action_id} approved by {approved_by}")
        return True

    def reject_action(self, action_id: str, rejected_by: str, reason: str) -> bool:
        """Reject a pending action."""
        proposal = self._get_proposal(action_id)
        if not proposal:
            logger.error(f"Action not found: {action_id}")
            return False

        if proposal["status"] != ActionStatus.PROPOSED.value:
            logger.error(f"Cannot reject action in state: {proposal['status']}")
            return False

        self.store.update(
            "actions",
            action_id,
            {
                "status": ActionStatus.REJECTED.value,
                "rejected_by": rejected_by,
                "rejection_reason": reason,
            },
        )

        logger.info(f"Action {action_id} rejected by {rejected_by}: {reason}")
        return True

    def execute_action(self, action_id: str, dry_run: bool | None = None) -> ActionResult:
        """Execute an approved action."""
        is_dry_run = dry_run if dry_run is not None else self.dry_run

        proposal = self._get_proposal(action_id)
        if not proposal:
            error = f"Action not found: {action_id}"
            logger.error(error)
            return ActionResult(action_id=action_id, success=False, error=error)

        if proposal["status"] != ActionStatus.APPROVED.value:
            error = f"Cannot execute action in state: {proposal['status']}"
            logger.error(error)
            return ActionResult(action_id=action_id, success=False, error=error)

        # Check rate limiting
        action_type = proposal["type"]
        if not self._check_rate_limit(action_type):
            error = f"Rate limit exceeded for action type: {action_type}"
            logger.error(error)
            return ActionResult(action_id=action_id, success=False, error=error)

        # Get handler
        handler = self.handlers.get(action_type)
        if not handler:
            error = f"No handler registered for action type: {action_type}"
            logger.error(error)
            return ActionResult(action_id=action_id, success=False, error=error)

        # Run before-execute hooks
        try:
            for hook in self.before_execute_hooks:
                hook(proposal)
        except (sqlite3.Error, ValueError, OSError) as e:
            error = f"Before-execute hook failed: {str(e)}"
            logger.error(error)
            return ActionResult(action_id=action_id, success=False, error=error)

        # Update status to executing
        self.store.update("actions", action_id, {"status": ActionStatus.EXECUTING.value})

        # Execute
        start_time = time.time()
        result = None
        execution_error = None

        try:
            payload = (
                json.loads(proposal["payload"])
                if isinstance(proposal["payload"], str)
                else proposal["payload"]
            )

            if is_dry_run:
                logger.info(f"DRY RUN: Would execute action {action_id} with payload: {payload}")
                result_data = {"dry_run": True, "payload": payload}
                result = ActionResult(
                    action_id=action_id,
                    success=True,
                    result_data=result_data,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )
            else:
                handler_result = handler(payload)
                execution_time = int((time.time() - start_time) * 1000)

                if isinstance(handler_result, ActionResult):
                    result = handler_result
                    result.execution_time_ms = execution_time
                else:
                    # Handler returned dict
                    result = ActionResult(
                        action_id=action_id,
                        success=handler_result.get("success", False),
                        result_data=handler_result,
                        execution_time_ms=execution_time,
                    )

        except (sqlite3.Error, ValueError, OSError) as e:
            execution_error = str(e)
            logger.error(f"Action execution failed: {execution_error}")
            execution_time = int((time.time() - start_time) * 1000)

            result = ActionResult(
                action_id=action_id,
                success=False,
                error=execution_error,
                execution_time_ms=execution_time,
            )

            # Run error hooks
            try:
                for hook in self.on_error_hooks:
                    hook(proposal, result)
            except (sqlite3.Error, ValueError, OSError) as hook_error:
                logger.error(f"Error hook failed: {str(hook_error)}")

        # Store result
        final_status = ActionStatus.SUCCESS if result.success else ActionStatus.FAILED
        update = {
            "status": final_status.value,
            "result": json.dumps(result.to_dict()),
            "executed_at": datetime.now().isoformat(),
        }
        if result.error:
            update["error"] = result.error

        self.store.update("actions", action_id, update)

        # Run after-execute hooks
        try:
            for hook in self.after_execute_hooks:
                hook(proposal, result)
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"After-execute hook failed: {str(e)}")

        logger.info(
            f"Action {action_id} executed: success={result.success}, "
            f"time={result.execution_time_ms}ms"
        )

        return result

    def get_pending_actions(
        self, status: ActionStatus | None = None, action_type: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Get pending actions with optional filters."""
        query = "SELECT * FROM actions WHERE status = ?"
        params = [ActionStatus.PROPOSED.value]

        if status:
            query = "SELECT * FROM actions WHERE status = ?"
            params = [status.value]

        if action_type:
            query += " AND type = ?"
            params.append(action_type)

        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)

        return self.store.query(query, params)

    def get_action_history(
        self, entity_id: str | None = None, action_type: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Get action history with optional filters."""
        query = "SELECT * FROM actions WHERE status IN (?, ?, ?)"
        params = [
            ActionStatus.SUCCESS.value,
            ActionStatus.FAILED.value,
            ActionStatus.REJECTED.value,
        ]

        if entity_id:
            query += " AND target_id = ?"
            params.append(entity_id)

        if action_type:
            query += " AND type = ?"
            params.append(action_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        return self.store.query(query, params)

    def _store_proposal(self, proposal: ActionProposal):
        """Store proposal in database."""
        self.store.insert(
            "actions",
            {
                "id": proposal.id,
                "type": proposal.type,
                "target_entity": proposal.target_entity,
                "target_id": proposal.target_id,
                "payload": json.dumps(proposal.payload),
                "risk_level": proposal.risk_level.value,
                "source": proposal.source.value,
                "confidence_score": proposal.confidence_score,
                "requires_approval": 1 if proposal.requires_approval else 0,
                "status": proposal.status.value,
                "approved_by": proposal.approved_by,
                "approved_at": proposal.approved_at,
                "created_at": proposal.created_at,
            },
        )

    def _get_proposal(self, action_id: str) -> dict | None:
        """Get proposal from database."""
        return self.store.get("actions", action_id)

    def _check_rate_limit(self, action_type: str) -> bool:
        """Check if action type is within rate limit."""
        if action_type not in self.rate_limit_config:
            return True

        max_per_minute = self.rate_limit_config[action_type]
        current_time = int(time.time() * 1000)

        if action_type not in self.rate_limits:
            self.rate_limits[action_type] = (1, current_time)
            return True

        count, window_start = self.rate_limits[action_type]
        window_elapsed = current_time - window_start

        # Reset window if older than 1 minute
        if window_elapsed > 60000:
            self.rate_limits[action_type] = (1, current_time)
            return True

        # Check if within limit
        if count < max_per_minute:
            self.rate_limits[action_type] = (count + 1, window_start)
            return True

        return False
