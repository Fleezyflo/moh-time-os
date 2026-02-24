"""
Action API Router — REST endpoints for action proposal, approval, and execution.

Endpoints:
- POST /api/actions/propose — propose new action
- POST /api/actions/{action_id}/approve — approve action
- POST /api/actions/{action_id}/reject — reject action
- POST /api/actions/{action_id}/execute — execute approved action
- GET /api/actions/pending — list pending actions
- GET /api/actions/history — action history with filters
- POST /api/actions/batch — batch propose multiple actions
"""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from lib.actions import (
    ActionFramework,
    ActionSource,
    ActionStatus,
    RiskLevel,
)
from lib.state_store import get_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])

# Global action framework instance
_framework: ActionFramework | None = None


def get_action_framework() -> ActionFramework:
    """Get or create global action framework instance."""
    global _framework
    if _framework is None:
        from lib.actions.approval_policies import DEFAULT_POLICIES, ApprovalPolicy, PolicyEngine

        store = get_store()
        policy = ApprovalPolicy(DEFAULT_POLICIES)
        policy_engine = PolicyEngine(policy)
        _framework = ActionFramework(store=store, policy_engine=policy_engine, dry_run=False)
    return _framework


# Pydantic models for API
class ProposalRequest(BaseModel):
    """Request to propose an action."""

    action_type: str = Field(..., description="Action type, e.g., task_create")
    target_entity: str = Field(..., description="Entity type, e.g., task, calendar")
    target_id: str = Field(..., description="ID of entity being affected")
    payload: dict = Field(..., description="Action data")
    risk_level: str = Field(default="medium", description="low|medium|high|critical")
    source: str = Field(default="manual", description="signal|proposal|manual|scheduled")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
    idempotency_key: str | None = None


class BatchProposalRequest(BaseModel):
    """Request to batch propose multiple actions."""

    actions: list[ProposalRequest] = Field(..., description="List of actions to propose")


class ApproveRequest(BaseModel):
    """Request to approve an action."""

    approved_by: str = Field(..., description="Who is approving (user_id)")
    additional_context: dict | None = None


class RejectRequest(BaseModel):
    """Request to reject an action."""

    rejected_by: str = Field(..., description="Who is rejecting (user_id)")
    reason: str = Field(..., description="Reason for rejection")


class ExecuteRequest(BaseModel):
    """Request to execute an action."""

    dry_run: bool = Field(default=False, description="Simulate execution without side effects")


class ActionResponse(BaseModel):
    """Response containing action data."""

    id: str
    type: str
    target_entity: str
    target_id: str
    status: str
    risk_level: str
    source: str
    confidence_score: float
    approved_by: str | None = None
    approved_at: str | None = None
    executed_at: str | None = None
    error: str | None = None


class ActionStatusResponse(BaseModel):
    """Response for action status changes (propose, approve, reject)."""

    action_id: str
    status: str


class BatchActionResponse(BaseModel):
    """Response for batch action proposal."""

    count: int
    action_ids: list[str]
    status: str


class ActionExecutionResponse(BaseModel):
    """Response for action execution."""

    action_id: str
    success: bool
    error: str | None = None
    execution_time_ms: float | None = None
    result_data: Any = None


class ActionListResponse(BaseModel):
    """Response for listing actions."""

    count: int
    actions: list[Any] = Field(default_factory=list)


# Endpoints


@router.post("/propose", response_model=ActionStatusResponse)
async def propose_action(request: ProposalRequest):
    """Propose a new action for approval."""
    try:
        framework = get_action_framework()

        action_id = framework.propose_action(
            action_type=request.action_type,
            target_entity=request.target_entity,
            target_id=request.target_id,
            payload=request.payload,
            risk_level=RiskLevel(request.risk_level),
            source=ActionSource(request.source),
            confidence_score=request.confidence_score,
            requires_approval=True,
            idempotency_key=request.idempotency_key,
        )

        return {"action_id": action_id, "status": "proposed"}

    except ValueError as e:
        logger.error(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error proposing action: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/batch", response_model=BatchActionResponse)
async def batch_propose(request: BatchProposalRequest):
    """Batch propose multiple actions."""
    try:
        framework = get_action_framework()
        action_ids = []

        for action_req in request.actions:
            action_id = framework.propose_action(
                action_type=action_req.action_type,
                target_entity=action_req.target_entity,
                target_id=action_req.target_id,
                payload=action_req.payload,
                risk_level=RiskLevel(action_req.risk_level),
                source=ActionSource(action_req.source),
                confidence_score=action_req.confidence_score,
                requires_approval=True,
                idempotency_key=action_req.idempotency_key,
            )
            action_ids.append(action_id)

        return {"count": len(action_ids), "action_ids": action_ids, "status": "proposed"}

    except ValueError as e:
        logger.error(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error batch proposing actions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/{action_id}/approve", response_model=ActionStatusResponse)
async def approve_action(action_id: str, request: ApproveRequest):
    """Approve a pending action."""
    try:
        framework = get_action_framework()

        success = framework.approve_action(
            action_id=action_id,
            approved_by=request.approved_by,
            additional_context=request.additional_context,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Action not found or already approved")

        return {"action_id": action_id, "status": "approved"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving action: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/{action_id}/reject", response_model=ActionStatusResponse)
async def reject_action(action_id: str, request: RejectRequest):
    """Reject a pending action."""
    try:
        framework = get_action_framework()

        success = framework.reject_action(
            action_id=action_id, rejected_by=request.rejected_by, reason=request.reason
        )

        if not success:
            raise HTTPException(status_code=404, detail="Action not found or already rejected")

        return {"action_id": action_id, "status": "rejected"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting action: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/{action_id}/execute", response_model=ActionExecutionResponse)
async def execute_action(action_id: str, request: ExecuteRequest):
    """Execute an approved action."""
    try:
        framework = get_action_framework()

        result = framework.execute_action(action_id=action_id, dry_run=request.dry_run)

        return {
            "action_id": result.action_id,
            "success": result.success,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
            "result_data": result.result_data,
        }

    except Exception as e:
        logger.error(f"Error executing action: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/pending", response_model=ActionListResponse)
async def get_pending_actions(action_type: str | None = None, limit: int = 50):
    """Get pending actions awaiting approval."""
    try:
        framework = get_action_framework()

        actions = framework.get_pending_actions(
            status=ActionStatus.PROPOSED, action_type=action_type, limit=limit
        )

        return {"count": len(actions), "actions": actions}

    except Exception as e:
        logger.error(f"Error fetching pending actions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/history", response_model=ActionListResponse)
async def get_action_history(
    entity_id: str | None = None, action_type: str | None = None, limit: int = 50
):
    """Get action execution history."""
    try:
        framework = get_action_framework()

        actions = framework.get_action_history(
            entity_id=entity_id, action_type=action_type, limit=limit
        )

        return {"count": len(actions), "actions": actions}

    except Exception as e:
        logger.error(f"Error fetching action history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
