"""
Role-based access control (RBAC) for MOH TIME OS API.

Provides:
- Role enum (VIEWER, OPERATOR, ADMIN)
- Role hierarchy and permission checking
- Endpoint-to-role mapping
- require_role() dependency for FastAPI

Role Hierarchy:
  ADMIN >= OPERATOR >= VIEWER

Default Permissions:
  VIEWER: All GET endpoints
  OPERATOR: GET + POST/PUT (create/update tasks, resolve items)
  ADMIN: Everything + DELETE + key management

Usage:
    from lib.security.rbac import Role, require_role

    @router.get("/protected", dependencies=[Depends(require_role(Role.VIEWER))])
    def protected_endpoint():
        ...
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class Role(StrEnum):
    """Role enumeration with hierarchy: ADMIN > OPERATOR > VIEWER.

    Inherits from str to make comparisons with string literals work naturally.
    """

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


# Role hierarchy: higher value = more permissions
_ROLE_HIERARCHY = {
    Role.VIEWER: 1,
    Role.OPERATOR: 2,
    Role.ADMIN: 3,
}


def _role_has_permission(user_role: Role, minimum_role: Role) -> bool:
    """Check if user_role has at least minimum_role permissions.

    Args:
        user_role: The user's actual role
        minimum_role: The minimum required role

    Returns:
        True if user_role >= minimum_role in the hierarchy
    """
    user_level = _ROLE_HIERARCHY.get(user_role, 0)
    min_level = _ROLE_HIERARCHY.get(minimum_role, 0)
    return user_level >= min_level


@dataclass
class RolePermission:
    """Mapping of endpoint pattern to minimum required role."""

    method: str  # HTTP method (GET, POST, PUT, DELETE)
    path_pattern: str  # URL path pattern (supports wildcards like /api/v2/intelligence/*)
    minimum_role: Role  # Minimum role required


# Default permission map
# All endpoints are scoped here
_DEFAULT_PERMISSIONS: list[RolePermission] = [
    # ==========================================================================
    # /api/v2/intelligence/* — Intelligence endpoints (all GET)
    # ==========================================================================
    # VIEWER can read all intelligence data
    RolePermission("GET", "/api/v2/intelligence/portfolio/overview", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/portfolio/risks", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/portfolio/trajectory", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/clients/*/profile", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/clients/*/tasks", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/clients/*/communication", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/clients/*/trajectory", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/clients/*/compare", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/clients/compare", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/team/distribution", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/team/capacity", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/team/*/profile", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/team/*/trajectory", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/projects/*/state", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/projects/health", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/financial/aging", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/snapshot", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/critical", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/briefing", Role.VIEWER),
    RolePermission("GET", "/api/v2/intelligence/*", Role.VIEWER),
    # ==========================================================================
    # /api/v2/events/* — SSE endpoints (streaming)
    # ==========================================================================
    # VIEWER can subscribe to events
    RolePermission("GET", "/api/v2/events/stream", Role.VIEWER),
    RolePermission("GET", "/api/v2/events/*", Role.VIEWER),
    # ==========================================================================
    # /api/v2/* — Spec router endpoints
    # ==========================================================================
    RolePermission("GET", "/api/v2/*", Role.VIEWER),
    RolePermission("POST", "/api/v2/*", Role.OPERATOR),
    RolePermission("PUT", "/api/v2/*", Role.OPERATOR),
    RolePermission("DELETE", "/api/v2/*", Role.ADMIN),
    # ==========================================================================
    # /api/* — Main server endpoints
    # ==========================================================================
    # Read-only endpoints (VIEWER)
    RolePermission("GET", "/api/overview", Role.VIEWER),
    RolePermission("GET", "/api/time/blocks", Role.VIEWER),
    RolePermission("GET", "/api/time/summary", Role.VIEWER),
    RolePermission("GET", "/api/time/brief", Role.VIEWER),
    RolePermission("GET", "/api/commitments", Role.VIEWER),
    RolePermission("GET", "/api/commitments/untracked", Role.VIEWER),
    RolePermission("GET", "/api/commitments/due", Role.VIEWER),
    RolePermission("GET", "/api/commitments/summary", Role.VIEWER),
    RolePermission("GET", "/api/capacity/lanes", Role.VIEWER),
    RolePermission("GET", "/api/capacity/utilization", Role.VIEWER),
    RolePermission("GET", "/api/capacity/forecast", Role.VIEWER),
    RolePermission("GET", "/api/capacity/debt", Role.VIEWER),
    RolePermission("GET", "/api/clients/health", Role.VIEWER),
    RolePermission("GET", "/api/clients/at-risk", Role.VIEWER),
    RolePermission("GET", "/api/clients/*/health", Role.VIEWER),
    RolePermission("GET", "/api/clients/*/projects", Role.VIEWER),
    RolePermission("GET", "/api/clients/linking-stats", Role.VIEWER),
    RolePermission("GET", "/api/tasks", Role.VIEWER),
    RolePermission("GET", "/api/tasks/*", Role.VIEWER),
    RolePermission("GET", "/api/delegations", Role.VIEWER),
    RolePermission("GET", "/api/data-quality", Role.VIEWER),
    RolePermission("GET", "/api/data-quality/preview/*", Role.VIEWER),
    RolePermission("GET", "/api/team", Role.VIEWER),
    RolePermission("GET", "/api/calendar", Role.VIEWER),
    RolePermission("GET", "/api/inbox", Role.VIEWER),
    RolePermission("GET", "/api/insights", Role.VIEWER),
    RolePermission("GET", "/api/decisions", Role.VIEWER),
    # Write operations (OPERATOR and ADMIN)
    RolePermission("POST", "/api/time/schedule", Role.OPERATOR),
    RolePermission("POST", "/api/time/unschedule", Role.OPERATOR),
    RolePermission("POST", "/api/commitments/link", Role.OPERATOR),
    RolePermission("POST", "/api/commitments/*/link", Role.OPERATOR),
    RolePermission("POST", "/api/commitments/*/done", Role.OPERATOR),
    RolePermission("POST", "/api/commitments/done", Role.OPERATOR),
    RolePermission("POST", "/api/capacity/debt/accrue", Role.OPERATOR),
    RolePermission("POST", "/api/capacity/debt/*/resolve", Role.OPERATOR),
    RolePermission("POST", "/api/clients/link", Role.OPERATOR),
    RolePermission("POST", "/api/clients/*/link", Role.OPERATOR),
    RolePermission("POST", "/api/tasks", Role.OPERATOR),
    RolePermission("PUT", "/api/tasks/*", Role.OPERATOR),
    RolePermission("POST", "/api/tasks/*/notes", Role.OPERATOR),
    RolePermission("POST", "/api/tasks/*/delegate", Role.OPERATOR),
    RolePermission("POST", "/api/tasks/*/escalate", Role.OPERATOR),
    RolePermission("POST", "/api/tasks/*/recall", Role.OPERATOR),
    RolePermission("POST", "/api/priorities/*/complete", Role.OPERATOR),
    RolePermission("POST", "/api/queue/*/resolve", Role.OPERATOR),
    # Data quality maintenance (ADMIN)
    RolePermission("POST", "/api/data-quality/cleanup/ancient", Role.ADMIN),
    RolePermission("POST", "/api/data-quality/cleanup/stale", Role.ADMIN),
    RolePermission("POST", "/api/data-quality/recalculate-priorities", Role.ADMIN),
    RolePermission("POST", "/api/data-quality/cleanup/legacy-signals", Role.ADMIN),
    # Delete operations (ADMIN only)
    RolePermission("DELETE", "/api/tasks/*", Role.ADMIN),
    # Fallback: remaining POST/PUT/DELETE require OPERATOR/ADMIN
    # (These are scoped by method since specifics match above)
    # Fallback for any remaining GET endpoints
    RolePermission("GET", "/api/*", Role.VIEWER),
    # Fallback for POST (OPERATOR if not otherwise specified)
    RolePermission("POST", "/api/*", Role.OPERATOR),
    # Fallback for PUT (OPERATOR if not otherwise specified)
    RolePermission("PUT", "/api/*", Role.OPERATOR),
    # Fallback for DELETE (ADMIN if not otherwise specified)
    RolePermission("DELETE", "/api/*", Role.ADMIN),
]


def _match_path_pattern(actual_path: str, pattern: str) -> bool:
    """Match URL path against pattern with wildcard support.

    Patterns:
        /api/tasks/* matches /api/tasks/123, /api/tasks/abc/xyz, etc.
        /api/v2/intelligence/* matches /api/v2/intelligence/anything
        /api/* matches /api/anything

    Args:
        actual_path: The actual request path
        pattern: The pattern with optional wildcards

    Returns:
        True if the actual_path matches the pattern
    """
    # Exact match
    if actual_path == pattern:
        return True

    # Wildcard match
    if "*" in pattern:
        prefix = pattern.rstrip("*")
        return actual_path.startswith(prefix)

    return False


def get_endpoint_role(method: str, path: str) -> Role:
    """Get the minimum required role for an endpoint.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: Request path

    Returns:
        The minimum role required (defaults to ADMIN if not found)
    """
    # Normalize method
    method = method.upper()

    # Find matching permission in order
    for perm in _DEFAULT_PERMISSIONS:
        if perm.method == method and _match_path_pattern(path, perm.path_pattern):
            return perm.minimum_role

    # No match found - require ADMIN for safety (deny by default)
    logger.warning(f"No permission mapping found for {method} {path} - requiring ADMIN")
    return Role.ADMIN


def check_permission(role: Role, method: str, path: str) -> bool:
    """Check if a role has permission for an endpoint.

    Args:
        role: The user's role
        method: HTTP method
        path: Request path

    Returns:
        True if the role has permission
    """
    required_role = get_endpoint_role(method, path)
    return _role_has_permission(role, required_role)


def require_role(minimum_role: Role) -> Callable:
    """
    FastAPI dependency that requires a minimum role.

    Returns a function that can be used as a dependency in route handlers.

    Args:
        minimum_role: The minimum role required for this endpoint

    Returns:
        An async function that validates role and raises HTTPException if insufficient

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(Role.ADMIN))])
        def admin_only():
            ...
    """

    async def _check_role(request: Request) -> Role:
        """Check that request has required role.

        The role is expected to be set in request.state.role by the RBAC middleware.
        """
        # Get role from request state (set by middleware)
        role = getattr(request.state, "role", None)

        if not role:
            logger.warning(f"No role found in request state for {request.url.path}")
            raise HTTPException(
                status_code=403,
                detail="Role information not available. Ensure RBAC middleware is installed.",
            )

        # Check role hierarchy
        if not _role_has_permission(role, minimum_role):
            logger.warning(
                f"Access denied: {role} lacks permission for {minimum_role} at {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {minimum_role}, got: {role}",
            )

        return role

    return _check_role
