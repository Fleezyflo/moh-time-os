"""
Security Hardening — MOH TIME OS

API key management, role-based access control, rate limiting,
and security configuration.

Brief 13 (SH), Tasks SH-1.1 through SH-3.1

Production-grade security for the intelligence API.
"""

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# Role definitions
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"

# Endpoint scope definitions
SCOPE_READ = "read"
SCOPE_WRITE = "write"
SCOPE_ADMIN = "admin"
SCOPE_EXECUTE = "execute"

# Role → allowed scopes
ROLE_SCOPES = {
    ROLE_ADMIN: {SCOPE_READ, SCOPE_WRITE, SCOPE_ADMIN, SCOPE_EXECUTE},
    ROLE_OPERATOR: {SCOPE_READ, SCOPE_WRITE, SCOPE_EXECUTE},
    ROLE_VIEWER: {SCOPE_READ},
}


@dataclass
class APIKey:
    """An API key with associated metadata."""

    key_id: str
    key_hash: str  # SHA-256 hash of the actual key
    name: str
    role: str
    created_at: str
    expires_at: str | None = None
    revoked: bool = False
    revoked_at: str | None = None
    last_used_at: str | None = None
    request_count: int = 0

    def is_valid(self) -> bool:
        """Check if key is currently valid."""
        if self.revoked:
            return False
        if self.expires_at:
            try:
                exp = datetime.fromisoformat(self.expires_at)
                if datetime.now() > exp:
                    return False
            except ValueError:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "key_id": self.key_id,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "last_used_at": self.last_used_at,
            "request_count": self.request_count,
            "is_valid": self.is_valid(),
        }


@dataclass
class RateLimitConfig:
    """Rate limit configuration per key or role."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max concurrent

    def to_dict(self) -> dict:
        return {
            "requests_per_minute": self.requests_per_minute,
            "requests_per_hour": self.requests_per_hour,
            "burst_limit": self.burst_limit,
        }


# Default rate limits by role
DEFAULT_RATE_LIMITS = {
    ROLE_ADMIN: RateLimitConfig(requests_per_minute=120, requests_per_hour=5000, burst_limit=20),
    ROLE_OPERATOR: RateLimitConfig(requests_per_minute=60, requests_per_hour=2000, burst_limit=10),
    ROLE_VIEWER: RateLimitConfig(requests_per_minute=30, requests_per_hour=500, burst_limit=5),
}


@dataclass
class RateLimitState:
    """Runtime state for rate limiting."""

    minute_count: int = 0
    hour_count: int = 0
    minute_reset_at: float = 0.0
    hour_reset_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "minute_count": self.minute_count,
            "hour_count": self.hour_count,
        }


@dataclass
class AuthResult:
    """Result of an authentication attempt."""

    authenticated: bool
    key_id: str = ""
    role: str = ""
    scopes: set[str] = field(default_factory=set)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "authenticated": self.authenticated,
            "key_id": self.key_id,
            "role": self.role,
            "scopes": sorted(self.scopes),
            "error": self.error,
        }


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining_minute: int = 0
    remaining_hour: int = 0
    retry_after_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "remaining_minute": self.remaining_minute,
            "remaining_hour": self.remaining_hour,
            "retry_after_s": round(self.retry_after_s, 1),
        }


@dataclass
class SecurityConfig:
    """Security configuration for the application."""

    cors_allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])
    csp_directives: dict[str, str] = field(
        default_factory=lambda: {
            "default-src": "'self'",
            "script-src": "'self'",
            "style-src": "'self' 'unsafe-inline'",
            "img-src": "'self' data:",
            "connect-src": "'self'",
            "frame-ancestors": "'none'",
        }
    )
    hsts_max_age: int = 31536000  # 1 year
    x_content_type_options: str = "nosniff"
    x_frame_options: str = "DENY"
    referrer_policy: str = "strict-origin-when-cross-origin"

    def get_security_headers(self) -> dict[str, str]:
        """Generate security headers dict."""
        csp = "; ".join(f"{k} {v}" for k, v in self.csp_directives.items())
        return {
            "Content-Security-Policy": csp,
            "Strict-Transport-Security": f"max-age={self.hsts_max_age}; includeSubDomains",
            "X-Content-Type-Options": self.x_content_type_options,
            "X-Frame-Options": self.x_frame_options,
            "Referrer-Policy": self.referrer_policy,
        }

    def to_dict(self) -> dict:
        return {
            "cors_allowed_origins": self.cors_allowed_origins,
            "security_headers": self.get_security_headers(),
        }


@dataclass
class SecurityAuditEntry:
    """An entry in the security audit log."""

    timestamp: str
    event_type: str  # auth_success | auth_failure | key_created | key_revoked | rate_limited
    key_id: str = ""
    ip_address: str = ""
    endpoint: str = ""
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "key_id": self.key_id,
            "ip_address": self.ip_address,
            "endpoint": self.endpoint,
            "details": self.details,
        }


def hash_key(raw_key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key_id() -> str:
    """Generate a unique key ID."""
    return f"moh_{secrets.token_hex(8)}"


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"moh_sk_{secrets.token_urlsafe(32)}"


class APIKeyManager:
    """
    Manages API key lifecycle: creation, validation, rotation, revocation.
    """

    def __init__(self) -> None:
        self.keys: dict[str, APIKey] = {}  # key_id → APIKey
        self.key_lookup: dict[str, str] = {}  # key_hash → key_id

    def create_key(
        self,
        name: str,
        role: str = ROLE_VIEWER,
        expires_in_days: int | None = None,
    ) -> tuple:
        """
        Create a new API key.

        Returns (raw_key, api_key_object).
        The raw key is only returned once — store it securely.
        """
        if role not in ROLE_SCOPES:
            raise ValueError(f"Invalid role: {role}. Must be one of {list(ROLE_SCOPES.keys())}")

        raw_key = generate_api_key()
        key_id = generate_key_id()
        key_h = hash_key(raw_key)

        expires_at = None
        if expires_in_days:
            expires_at = (datetime.now() + timedelta(days=expires_in_days)).isoformat()

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_h,
            name=name,
            role=role,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at,
        )

        self.keys[key_id] = api_key
        self.key_lookup[key_h] = key_id
        return raw_key, api_key

    def authenticate(self, raw_key: str) -> AuthResult:
        """Authenticate a request using an API key."""
        if not raw_key:
            return AuthResult(authenticated=False, error="no key provided")

        key_h = hash_key(raw_key)
        key_id = self.key_lookup.get(key_h)

        if not key_id:
            return AuthResult(authenticated=False, error="invalid key")

        api_key = self.keys.get(key_id)
        if not api_key:
            return AuthResult(authenticated=False, error="key not found")

        if not api_key.is_valid():
            if api_key.revoked:
                return AuthResult(authenticated=False, key_id=key_id, error="key revoked")
            return AuthResult(authenticated=False, key_id=key_id, error="key expired")

        # Update usage
        api_key.last_used_at = datetime.now().isoformat()
        api_key.request_count += 1

        return AuthResult(
            authenticated=True,
            key_id=key_id,
            role=api_key.role,
            scopes=ROLE_SCOPES.get(api_key.role, set()),
        )

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        api_key = self.keys.get(key_id)
        if not api_key:
            return False
        api_key.revoked = True
        api_key.revoked_at = datetime.now().isoformat()
        return True

    def rotate_key(self, key_id: str) -> tuple | None:
        """Rotate an API key — revokes old, creates new with same config."""
        old_key = self.keys.get(key_id)
        if not old_key:
            return None

        # Revoke old
        self.revoke_key(key_id)

        # Create new with same config
        raw_key, new_key = self.create_key(
            name=old_key.name,
            role=old_key.role,
        )
        return raw_key, new_key

    def list_keys(self, include_revoked: bool = False) -> list[APIKey]:
        """List all API keys."""
        keys = list(self.keys.values())
        if not include_revoked:
            keys = [k for k in keys if not k.revoked]
        return keys

    def check_scope(self, key_id: str, required_scope: str) -> bool:
        """Check if a key has a required scope."""
        api_key = self.keys.get(key_id)
        if not api_key:
            return False
        allowed = ROLE_SCOPES.get(api_key.role, set())
        return required_scope in allowed


class RateLimiter:
    """
    Per-key rate limiting using sliding window counters.
    """

    def __init__(
        self,
        role_limits: dict[str, RateLimitConfig] | None = None,
    ) -> None:
        self.role_limits = role_limits or DEFAULT_RATE_LIMITS
        self.state: dict[str, RateLimitState] = {}  # key_id → state

    def check_rate_limit(
        self,
        key_id: str,
        role: str = ROLE_VIEWER,
    ) -> RateLimitResult:
        """Check and update rate limit for a key."""
        config = self.role_limits.get(role, DEFAULT_RATE_LIMITS[ROLE_VIEWER])
        now = time.monotonic()

        if key_id not in self.state:
            self.state[key_id] = RateLimitState(
                minute_reset_at=now + 60,
                hour_reset_at=now + 3600,
            )

        state = self.state[key_id]

        # Reset windows if expired
        if now >= state.minute_reset_at:
            state.minute_count = 0
            state.minute_reset_at = now + 60

        if now >= state.hour_reset_at:
            state.hour_count = 0
            state.hour_reset_at = now + 3600

        # Check limits
        if state.minute_count >= config.requests_per_minute:
            return RateLimitResult(
                allowed=False,
                remaining_minute=0,
                remaining_hour=max(0, config.requests_per_hour - state.hour_count),
                retry_after_s=state.minute_reset_at - now,
            )

        if state.hour_count >= config.requests_per_hour:
            return RateLimitResult(
                allowed=False,
                remaining_minute=0,
                remaining_hour=0,
                retry_after_s=state.hour_reset_at - now,
            )

        # Allow and increment
        state.minute_count += 1
        state.hour_count += 1

        return RateLimitResult(
            allowed=True,
            remaining_minute=config.requests_per_minute - state.minute_count,
            remaining_hour=config.requests_per_hour - state.hour_count,
        )

    def get_usage(self, key_id: str) -> dict[str, Any]:
        """Get current rate limit usage for a key."""
        state = self.state.get(key_id)
        if not state:
            return {"minute_count": 0, "hour_count": 0}
        return state.to_dict()
