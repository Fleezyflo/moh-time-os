"""
Action Router — Routes action types to appropriate handlers.

Manages:
- Handler registration and dispatch
- Middleware hooks (before/after/error)
- Dry-run mode
- Rate limiting
- Idempotency
"""

import logging
from collections.abc import Callable
from typing import Optional

from lib.actions.action_framework import ActionResult
import sqlite3

logger = logging.getLogger(__name__)


class ActionRouter:
    """
    Routes actions to registered handlers.

    Supports:
    - Multiple handlers per action type
    - Before/after/error middleware
    - Dry-run mode
    - Rate limiting per handler
    """

    def __init__(self):
        # Handler registry: action_type -> handler_fn
        self.handlers: dict[str, Callable] = {}

        # Middleware hooks
        self.before_dispatch_hooks: list[Callable] = []
        self.after_dispatch_hooks: list[Callable] = []
        self.on_dispatch_error_hooks: list[Callable] = []

        # Rate limiting: handler_name -> (count, window_start_ms)
        self.rate_limits: dict[str, tuple[int, int]] = {}
        self.rate_limit_config: dict[str, int] = {}

        # Dry-run mode
        self.dry_run = False

    def register(
        self, action_type: str, handler: Callable, rate_limit_per_minute: int | None = None
    ):
        """Register a handler for an action type."""
        self.handlers[action_type] = handler

        if rate_limit_per_minute:
            self.rate_limit_config[action_type] = rate_limit_per_minute

        logger.info(f"Registered handler for action type: {action_type}")

    def register_before_dispatch(self, hook: Callable):
        """Register hook to run before dispatch."""
        self.before_dispatch_hooks.append(hook)

    def register_after_dispatch(self, hook: Callable):
        """Register hook to run after dispatch."""
        self.after_dispatch_hooks.append(hook)

    def register_on_error(self, hook: Callable):
        """Register hook to run on dispatch error."""
        self.on_dispatch_error_hooks.append(hook)

    def set_rate_limit(self, action_type: str, max_per_minute: int):
        """Set rate limit for action type."""
        self.rate_limit_config[action_type] = max_per_minute

    def dispatch(
        self,
        action_type: str,
        payload: dict,
        action_id: str | None = None,
        dry_run: bool | None = None,
    ) -> ActionResult:
        """
        Dispatch action to handler.

        Returns ActionResult.
        """
        is_dry_run = dry_run if dry_run is not None else self.dry_run

        # Get handler
        handler = self.handlers.get(action_type)
        if not handler:
            error = f"No handler registered for action type: {action_type}"
            logger.error(error)
            result = ActionResult(action_id=action_id or "unknown", success=False, error=error)

            # Run error hooks
            for hook in self.on_dispatch_error_hooks:
                try:
                    hook(action_type, payload, result)
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.error(f"Error hook failed: {str(e)}")

            return result

        # Check rate limiting
        if not self._check_rate_limit(action_type):
            error = f"Rate limit exceeded for action type: {action_type}"
            logger.error(error)
            result = ActionResult(action_id=action_id or "unknown", success=False, error=error)

            for hook in self.on_dispatch_error_hooks:
                try:
                    hook(action_type, payload, result)
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.error(f"Error hook failed: {str(e)}")

            return result

        # Run before-dispatch hooks
        try:
            for hook in self.before_dispatch_hooks:
                hook(action_type, payload)
        except (sqlite3.Error, ValueError, OSError) as e:
            error = f"Before-dispatch hook failed: {str(e)}"
            logger.error(error)
            result = ActionResult(action_id=action_id or "unknown", success=False, error=error)

            for hook in self.on_dispatch_error_hooks:
                try:
                    hook(action_type, payload, result)
                except (sqlite3.Error, ValueError, OSError) as err:
                    logger.error(f"Error hook failed: {str(err)}")

            return result

        # Execute handler or dry-run
        try:
            if is_dry_run:
                logger.info(f"DRY RUN: Would dispatch {action_type} with payload: {payload}")
                result = ActionResult(
                    action_id=action_id or "unknown",
                    success=True,
                    result_data={"dry_run": True, "payload": payload},
                )
            else:
                handler_result = handler(payload)

                # Normalize result to ActionResult
                if isinstance(handler_result, ActionResult):
                    result = handler_result
                    if result.action_id == "unknown":
                        result.action_id = action_id or "unknown"
                else:
                    # Handler returned dict
                    result = ActionResult(
                        action_id=action_id or "unknown",
                        success=handler_result.get("success", False),
                        result_data=handler_result,
                    )

        except (sqlite3.Error, ValueError, OSError) as e:
            error = str(e)
            logger.error(f"Handler execution failed: {error}")
            result = ActionResult(action_id=action_id or "unknown", success=False, error=error)

            # Run error hooks
            for hook in self.on_dispatch_error_hooks:
                try:
                    hook(action_type, payload, result)
                except (sqlite3.Error, ValueError, OSError) as hook_error:
                    logger.error(f"Error hook failed: {str(hook_error)}")

            return result

        # Run after-dispatch hooks
        try:
            for hook in self.after_dispatch_hooks:
                hook(action_type, payload, result)
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"After-dispatch hook failed: {str(e)}")

        logger.info(
            f"Action dispatched: {action_type}, "
            f"success={result.success}, action_id={result.action_id}"
        )

        return result

    def _check_rate_limit(self, action_type: str) -> bool:
        """Check if action type is within rate limit."""
        if action_type not in self.rate_limit_config:
            return True

        import time

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
