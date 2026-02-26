"""
Comprehensive tests for Action Framework.

Covers:
- ActionProposal creation and validation
- ApprovalPolicy evaluation
- ActionFramework lifecycle (propose → approve → execute)
- Rejection flow
- Auto-approval for low-risk actions
- Idempotency
- Dry-run mode
- Action history
- Rate limiting
- Batch proposals
- Middleware hooks
- Error handling
"""

import json
from unittest.mock import Mock

import pytest

from lib.actions import (
    ActionFramework,
    ActionProposal,
    ActionResult,
    ActionRouter,
    ActionSource,
    ActionStatus,
    ApprovalPolicy,
    ApprovalRule,
    PolicyEngine,
    RiskLevel,
)
from lib.actions.approval_policies import DEFAULT_POLICIES

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_store():
    """Provide a mock state store."""
    store = Mock()
    store.data = {}  # In-memory storage

    def insert(table, data):
        if table not in store.data:
            store.data[table] = {}
        id_ = data.get("id", f"id_{len(store.data[table])}")
        store.data[table][id_] = data
        return id_

    def get(table, id_):
        if table in store.data and id_ in store.data[table]:
            return store.data[table][id_]
        return None

    def update(table, id_, updates):
        if table in store.data and id_ in store.data[table]:
            store.data[table][id_].update(updates)
            return True
        return False

    def query(q, params=None):
        # Simple query implementation for testing
        if "WHERE status = ?" in q:
            status = params[0] if params else None
            table_name = "actions"
            if table_name in store.data:
                results = [v for v in store.data[table_name].values() if v.get("status") == status]
                if "ORDER BY created_at ASC" in q:
                    results.sort(key=lambda x: x.get("created_at", ""))
                if "LIMIT ?" in q:
                    limit = params[-1] if params else 50
                    results = results[:limit]
                return results
        if "WHERE status IN" in q:
            statuses = params[:3] if params else []
            table_name = "actions"
            if table_name in store.data:
                results = [
                    v for v in store.data[table_name].values() if v.get("status") in statuses
                ]
                if "ORDER BY created_at DESC" in q:
                    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                if "LIMIT ?" in q:
                    limit = params[-1] if params else 50
                    results = results[:limit]
                return results
        return []

    store.insert = insert
    store.get = get
    store.update = update
    store.query = query

    return store


@pytest.fixture
def policy_engine():
    """Provide a policy engine with default policies."""
    policy = ApprovalPolicy(DEFAULT_POLICIES)
    return PolicyEngine(policy)


@pytest.fixture
def framework(mock_store, policy_engine):
    """Provide an action framework instance."""
    return ActionFramework(store=mock_store, policy_engine=policy_engine, dry_run=False)


# =============================================================================
# ACTIONPROPOSAL TESTS
# =============================================================================


class TestActionProposal:
    """Tests for ActionProposal dataclass."""

    def test_create_proposal(self):
        """Create a valid action proposal."""
        proposal = ActionProposal(
            id="action_test1",
            type="task_create",
            target_entity="task",
            target_id="task_123",
            payload={"title": "Test task"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.9,
            requires_approval=False,
        )

        assert proposal.id == "action_test1"
        assert proposal.type == "task_create"
        assert proposal.status == ActionStatus.PROPOSED
        assert proposal.approved_by is None

    def test_proposal_to_dict_serializes_enums(self):
        """Proposal.to_dict() should serialize Enums as strings."""
        proposal = ActionProposal(
            id="action_test1",
            type="task_create",
            target_entity="task",
            target_id="task_123",
            payload={"title": "Test"},
            risk_level=RiskLevel.HIGH,
            source=ActionSource.SIGNAL,
            confidence_score=0.8,
            requires_approval=True,
        )

        data = proposal.to_dict()
        assert data["risk_level"] == "high"
        assert data["source"] == "signal"
        assert data["status"] == "proposed"

    def test_proposal_has_created_at_timestamp(self):
        """Proposal should have created_at timestamp."""
        proposal = ActionProposal(
            id="action_test1",
            type="task_create",
            target_entity="task",
            target_id="task_123",
            payload={},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        assert proposal.created_at
        assert "T" in proposal.created_at  # ISO format


# =============================================================================
# APPROVALRULE & APPROVALPOLICY TESTS
# =============================================================================


class TestApprovalRules:
    """Tests for ApprovalRule and ApprovalPolicy."""

    def test_rule_matches_exact_action_type(self):
        """Rule should match exact action type."""
        rule = ApprovalRule(
            action_type_pattern="task_create", risk_threshold=RiskLevel.LOW, auto_approve=True
        )
        policy = ApprovalPolicy([rule])

        assert (
            policy.find_matching_rule(
                ActionProposal(
                    id="a1",
                    type="task_create",
                    target_entity="task",
                    target_id="t1",
                    payload={},
                    risk_level=RiskLevel.LOW,
                    source=ActionSource.MANUAL,
                    confidence_score=0.8,
                    requires_approval=False,
                )
            )
            is rule
        )

    def test_rule_matches_wildcard_pattern(self):
        """Rule should match wildcard patterns."""
        rule = ApprovalRule(
            action_type_pattern="task_*", risk_threshold=RiskLevel.MEDIUM, auto_approve=True
        )
        policy = ApprovalPolicy([rule])

        # Should match task_create, task_update, etc.
        assert (
            policy.find_matching_rule(
                ActionProposal(
                    id="a1",
                    type="task_create",
                    target_entity="task",
                    target_id="t1",
                    payload={},
                    risk_level=RiskLevel.MEDIUM,
                    source=ActionSource.MANUAL,
                    confidence_score=0.8,
                    requires_approval=False,
                )
            )
            is rule
        )

    def test_rule_respects_risk_threshold(self):
        """Rule should only apply if risk is at or below threshold."""
        rule = ApprovalRule(
            action_type_pattern="task_*", risk_threshold=RiskLevel.MEDIUM, auto_approve=True
        )
        policy = ApprovalPolicy([rule])

        # MEDIUM risk should match
        assert (
            policy.find_matching_rule(
                ActionProposal(
                    id="a1",
                    type="task_create",
                    target_entity="task",
                    target_id="t1",
                    payload={},
                    risk_level=RiskLevel.MEDIUM,
                    source=ActionSource.MANUAL,
                    confidence_score=0.8,
                    requires_approval=False,
                )
            )
            is rule
        )

        # CRITICAL risk should not match
        assert (
            policy.find_matching_rule(
                ActionProposal(
                    id="a2",
                    type="task_create",
                    target_entity="task",
                    target_id="t2",
                    payload={},
                    risk_level=RiskLevel.CRITICAL,
                    source=ActionSource.MANUAL,
                    confidence_score=0.8,
                    requires_approval=False,
                )
            )
            is None
        )


# =============================================================================
# POLICYENGINE TESTS
# =============================================================================


class TestPolicyEngine:
    """Tests for PolicyEngine approval evaluation."""

    def test_auto_approve_low_risk_task_create(self):
        """Low-risk task_create should auto-approve."""
        policy = ApprovalPolicy(DEFAULT_POLICIES)
        engine = PolicyEngine(policy)

        proposal = ActionProposal(
            id="a1",
            type="task_create",
            target_entity="task",
            target_id="t1",
            payload={},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        decision = engine.evaluate(proposal)

        assert decision.approved is True
        assert decision.requires_approval is False
        assert decision.policy_matched == "task_create"

    def test_require_approval_for_critical_risk(self):
        """Critical risk should require approval."""
        policy = ApprovalPolicy(DEFAULT_POLICIES)
        engine = PolicyEngine(policy)

        proposal = ActionProposal(
            id="a1",
            type="task_create",
            target_entity="task",
            target_id="t1",
            payload={},
            risk_level=RiskLevel.CRITICAL,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        decision = engine.evaluate(proposal)

        assert decision.approved is False
        assert decision.requires_approval is True

    def test_low_confidence_overrides_auto_approve(self):
        """Low confidence should override auto-approve policy."""
        policy = ApprovalPolicy(DEFAULT_POLICIES)
        engine = PolicyEngine(policy)

        proposal = ActionProposal(
            id="a1",
            type="task_create",
            target_entity="task",
            target_id="t1",
            payload={},
            risk_level=RiskLevel.LOW,
            source=ActionSource.SIGNAL,
            confidence_score=0.3,  # Low confidence
            requires_approval=False,
        )

        decision = engine.evaluate(proposal)

        assert decision.approved is False
        assert decision.requires_approval is True

    def test_two_approvals_for_deletions(self):
        """Deletions should require two approvals."""
        policy = ApprovalPolicy(DEFAULT_POLICIES)
        engine = PolicyEngine(policy)

        proposal = ActionProposal(
            id="a1",
            type="task_delete",
            target_entity="task",
            target_id="t1",
            payload={},
            risk_level=RiskLevel.HIGH,
            source=ActionSource.MANUAL,
            confidence_score=0.9,
            requires_approval=False,
        )

        decision = engine.evaluate(proposal)

        assert decision.requires_approval is True
        assert decision.requires_two_approvals is True


# =============================================================================
# ACTIONFRAMEWORK TESTS
# =============================================================================


class TestActionFrameworkProposal:
    """Tests for ActionFramework.propose_action."""

    def test_propose_action_returns_action_id(self, framework):
        """propose_action should return an action_id."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        assert action_id.startswith("action_")

    def test_propose_action_auto_approves_low_risk(self, framework):
        """Low-risk actions should auto-approve."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        action = framework._get_proposal(action_id)
        assert action["status"] == ActionStatus.APPROVED.value
        assert action["approved_by"] == "system_policy"

    def test_propose_action_requires_approval_for_critical(self, framework):
        """Critical risk should require approval."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.CRITICAL,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        action = framework._get_proposal(action_id)
        assert action["status"] == ActionStatus.PROPOSED.value

    def test_idempotency_prevents_duplicate_actions(self, framework):
        """Same idempotency key should return same action_id."""
        key = "idem_test_1"

        id1 = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
            idempotency_key=key,
        )

        id2 = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
            idempotency_key=key,
        )

        assert id1 == id2


class TestActionFrameworkApproval:
    """Tests for approve/reject workflows."""

    def test_approve_pending_action(self, framework):
        """Should approve a pending action."""
        action_id = framework.propose_action(
            action_type="task_delete",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.HIGH,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        success = framework.approve_action(action_id, approved_by="user_1")
        assert success is True

        action = framework._get_proposal(action_id)
        assert action["status"] == ActionStatus.APPROVED.value
        assert action["approved_by"] == "user_1"

    def test_reject_pending_action(self, framework):
        """Should reject a pending action."""
        action_id = framework.propose_action(
            action_type="task_delete",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.HIGH,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        success = framework.reject_action(action_id, rejected_by="user_1", reason="Not needed")
        assert success is True

        action = framework._get_proposal(action_id)
        assert action["status"] == ActionStatus.REJECTED.value
        assert action["rejection_reason"] == "Not needed"

    def test_cannot_approve_non_existent_action(self, framework):
        """Should fail to approve non-existent action."""
        success = framework.approve_action("action_nonexistent", approved_by="user_1")
        assert success is False

    def test_cannot_approve_already_approved_action(self, framework):
        """Should fail to approve already approved action."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        # Already auto-approved, should fail
        success = framework.approve_action(action_id, approved_by="user_1")
        assert success is False


class TestActionFrameworkExecution:
    """Tests for action execution."""

    def test_execute_approved_action(self, framework):
        """Should execute an approved action."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        # Register a handler
        def handler(payload):
            return ActionResult(
                action_id=action_id, success=True, result_data={"task_id": "created_task_1"}
            )

        framework.register_handler("task_create", handler)

        result = framework.execute_action(action_id)

        assert result.success is True
        assert result.error is None
        assert result.result_data["task_id"] == "created_task_1"

    def test_cannot_execute_non_approved_action(self, framework):
        """Should fail to execute non-approved action."""
        action_id = framework.propose_action(
            action_type="task_delete",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.CRITICAL,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        def handler(payload):
            return {"success": True}

        framework.register_handler("task_delete", handler)

        result = framework.execute_action(action_id)

        assert result.success is False
        assert "Cannot execute action in state" in result.error

    def test_execute_with_missing_handler(self, framework):
        """Should fail to execute without handler."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        result = framework.execute_action(action_id)

        assert result.success is False
        assert "No handler registered" in result.error

    def test_execution_time_tracked(self, framework):
        """Execution should track execution time."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        def handler(payload):
            return ActionResult(action_id=action_id, success=True, result_data={})

        framework.register_handler("task_create", handler)

        result = framework.execute_action(action_id)

        assert result.execution_time_ms >= 0

    def test_dry_run_mode(self, framework):
        """Dry-run should not invoke handler."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        handler_called = False

        def handler(payload):
            nonlocal handler_called
            handler_called = True
            return ActionResult(action_id=action_id, success=True)

        framework.register_handler("task_create", handler)

        result = framework.execute_action(action_id, dry_run=True)

        assert result.success is True
        assert handler_called is False
        assert result.result_data["dry_run"] is True


class TestActionFrameworkHistory:
    """Tests for action history retrieval."""

    def test_get_pending_actions(self, framework):
        """Should retrieve pending actions."""
        action_id = framework.propose_action(
            action_type="task_delete",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.HIGH,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        pending = framework.get_pending_actions()

        assert len(pending) >= 1
        assert any(a["id"] == action_id for a in pending)

    def test_get_action_history(self, framework):
        """Should retrieve action history."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        def handler(payload):
            return ActionResult(action_id=action_id, success=True)

        framework.register_handler("task_create", handler)
        framework.execute_action(action_id)

        history = framework.get_action_history()

        assert any(a["id"] == action_id for a in history)


class TestActionFrameworkRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_enforcement(self, framework):
        """Should enforce rate limits."""
        framework.set_rate_limit("task_create", max_per_minute=2)

        def handler(payload):
            return ActionResult(action_id="test", success=True)

        framework.register_handler("task_create", handler)

        # Propose and execute actions
        action_ids = []
        for i in range(3):
            action_id = framework.propose_action(
                action_type="task_create",
                target_entity="task",
                target_id=f"t{i}",
                payload={},
                risk_level=RiskLevel.LOW,
                source=ActionSource.MANUAL,
                confidence_score=0.8,
                requires_approval=False,
            )
            action_ids.append(action_id)

        # Execute first two (should succeed), third should fail rate limit
        results = []
        for action_id in action_ids:
            result = framework.execute_action(action_id)
            results.append(result)

        # First two succeed, third fails due to rate limit
        assert results[0].success is True
        assert results[1].success is True
        assert results[2].success is False
        assert "Rate limit exceeded" in results[2].error


class TestActionFrameworkMiddleware:
    """Tests for middleware hooks."""

    def test_before_execute_hook(self, framework):
        """Before-execute hook should be called."""
        hook_called = False
        hook_proposal = None

        def hook(proposal):
            nonlocal hook_called, hook_proposal
            hook_called = True
            hook_proposal = proposal

        framework.register_before_execute_hook(hook)

        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        def handler(payload):
            return ActionResult(action_id=action_id, success=True)

        framework.register_handler("task_create", handler)
        framework.execute_action(action_id)

        assert hook_called is True
        assert hook_proposal is not None

    def test_after_execute_hook(self, framework):
        """After-execute hook should be called."""
        hook_called = False

        def hook(proposal, result):
            nonlocal hook_called
            hook_called = True

        framework.register_after_execute_hook(hook)

        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        def handler(payload):
            return ActionResult(action_id=action_id, success=True)

        framework.register_handler("task_create", handler)
        framework.execute_action(action_id)

        assert hook_called is True

    def test_error_hook_on_handler_failure(self, framework):
        """Error hook should be called on handler failure."""
        error_hook_called = False

        def error_hook(proposal, result):
            nonlocal error_hook_called
            error_hook_called = True

        framework.register_on_error_hook(error_hook)

        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        def handler(payload):
            raise Exception("Handler error")

        framework.register_handler("task_create", handler)
        result = framework.execute_action(action_id)

        assert result.success is False
        assert error_hook_called is True


# =============================================================================
# ACTIONROUTER TESTS
# =============================================================================


class TestActionRouter:
    """Tests for ActionRouter."""

    def test_router_dispatch(self):
        """Router should dispatch to registered handler."""
        router = ActionRouter()

        def handler(payload):
            return ActionResult(action_id="test", success=True, result_data={"processed": True})

        router.register("test_action", handler)

        result = router.dispatch("test_action", {}, action_id="test")

        assert result.success is True
        assert result.result_data["processed"] is True

    def test_router_dispatch_missing_handler(self):
        """Router should fail gracefully with missing handler."""
        router = ActionRouter()

        result = router.dispatch("unknown_action", {}, action_id="test")

        assert result.success is False
        assert "No handler registered" in result.error

    def test_router_dry_run(self):
        """Router should support dry-run mode."""
        router = ActionRouter()
        router.dry_run = True

        handler_called = False

        def handler(payload):
            nonlocal handler_called
            handler_called = True
            return ActionResult(action_id="test", success=True)

        router.register("test_action", handler)

        result = router.dispatch("test_action", {"key": "value"}, action_id="test")

        assert result.success is True
        assert handler_called is False
        assert result.result_data["dry_run"] is True

    def test_router_before_dispatch_hook(self):
        """Router should call before-dispatch hooks."""
        router = ActionRouter()

        hook_called = False

        def hook(action_type, payload):
            nonlocal hook_called
            hook_called = True

        router.register_before_dispatch(hook)

        def handler(payload):
            return ActionResult(action_id="test", success=True)

        router.register("test_action", handler)
        router.dispatch("test_action", {}, action_id="test")

        assert hook_called is True


# =============================================================================
# ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_handler_exception_captured(self, framework):
        """Handler exceptions should be captured."""
        action_id = framework.propose_action(
            action_type="task_create",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.LOW,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        def handler(payload):
            raise ValueError("Test error")

        framework.register_handler("task_create", handler)

        result = framework.execute_action(action_id)

        assert result.success is False
        assert "Test error" in result.error

    def test_approval_context_included(self, framework):
        """Approval context should be stored in payload."""
        action_id = framework.propose_action(
            action_type="task_delete",
            target_entity="task",
            target_id="t1",
            payload={"title": "Test"},
            risk_level=RiskLevel.HIGH,
            source=ActionSource.MANUAL,
            confidence_score=0.8,
            requires_approval=False,
        )

        context = {"reason": "No longer needed"}
        framework.approve_action(action_id, approved_by="user_1", additional_context=context)

        action = framework._get_proposal(action_id)
        payload = json.loads(action["payload"])
        assert payload.get("approval_context") == context
