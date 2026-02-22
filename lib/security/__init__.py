"""
Security module for MOH TIME OS.

Provides:
1. API key management (creation, validation, rotation, revocation)
2. Role-based access control (RBAC) for API endpoints

Exports:
    KeyRole: Enum of API key roles (VIEWER, OPERATOR, ADMIN)
    KeyManager: Multi-key API key management system
    KeyInfo: Metadata about an API key
    Role: Enum of endpoint roles (VIEWER, OPERATOR, ADMIN)
    require_role: Dependency for FastAPI to enforce role requirements
    check_permission: Function to check if a role has permission
    RBACMiddleware: Middleware for logging RBAC access
"""

from lib.security.key_manager import KeyInfo, KeyManager, KeyRole
from lib.security.middleware import RBACMiddleware
from lib.security.rbac import (
    Role,
    RolePermission,
    check_permission,
    get_endpoint_role,
    require_role,
)

__all__ = [
    "KeyRole",
    "KeyManager",
    "KeyInfo",
    "Role",
    "RolePermission",
    "require_role",
    "check_permission",
    "get_endpoint_role",
    "RBACMiddleware",
]
