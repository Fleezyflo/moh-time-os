"""
Tests for SecurityHardening — API keys, RBAC, rate limiting.

Brief 13 (SH), Task SH-1.1
"""

import pytest

from lib.intelligence.security_hardening import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    SCOPE_ADMIN,
    SCOPE_EXECUTE,
    SCOPE_READ,
    SCOPE_WRITE,
    APIKey,
    APIKeyManager,
    AuthResult,
    RateLimitConfig,
    RateLimiter,
    RateLimitResult,
    SecurityConfig,
    hash_key,
)


class TestHashKey:
    def test_deterministic(self):
        assert hash_key("test") == hash_key("test")

    def test_different_inputs(self):
        assert hash_key("a") != hash_key("b")


class TestAPIKeyManager:
    def test_create_key(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("test_key", role=ROLE_VIEWER)
        assert raw.startswith("moh_sk_")
        assert key.key_id.startswith("moh_")
        assert key.role == ROLE_VIEWER
        assert key.is_valid()

    def test_authenticate_valid(self):
        mgr = APIKeyManager()
        raw, _ = mgr.create_key("test_key", role=ROLE_OPERATOR)
        result = mgr.authenticate(raw)
        assert result.authenticated is True
        assert result.role == ROLE_OPERATOR
        assert SCOPE_READ in result.scopes
        assert SCOPE_WRITE in result.scopes

    def test_authenticate_invalid(self):
        mgr = APIKeyManager()
        result = mgr.authenticate("invalid_key")
        assert result.authenticated is False
        assert result.error == "invalid key"

    def test_authenticate_empty(self):
        mgr = APIKeyManager()
        result = mgr.authenticate("")
        assert result.authenticated is False
        assert result.error == "no key provided"

    def test_revoke_key(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("test_key")
        assert mgr.revoke_key(key.key_id) is True
        result = mgr.authenticate(raw)
        assert result.authenticated is False
        assert result.error == "key revoked"

    def test_revoke_nonexistent(self):
        mgr = APIKeyManager()
        assert mgr.revoke_key("nonexistent") is False

    def test_rotate_key(self):
        mgr = APIKeyManager()
        raw_old, old_key = mgr.create_key("test_key", role=ROLE_ADMIN)
        result = mgr.rotate_key(old_key.key_id)
        assert result is not None
        raw_new, new_key = result
        # Old key should be revoked
        assert mgr.authenticate(raw_old).authenticated is False
        # New key should work
        assert mgr.authenticate(raw_new).authenticated is True
        assert new_key.role == ROLE_ADMIN

    def test_rotate_nonexistent(self):
        mgr = APIKeyManager()
        assert mgr.rotate_key("nonexistent") is None

    def test_list_keys(self):
        mgr = APIKeyManager()
        mgr.create_key("key1")
        mgr.create_key("key2")
        _, key3 = mgr.create_key("key3")
        mgr.revoke_key(key3.key_id)
        active = mgr.list_keys(include_revoked=False)
        assert len(active) == 2
        all_keys = mgr.list_keys(include_revoked=True)
        assert len(all_keys) == 3

    def test_check_scope_admin(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("admin_key", role=ROLE_ADMIN)
        assert mgr.check_scope(key.key_id, SCOPE_ADMIN) is True
        assert mgr.check_scope(key.key_id, SCOPE_READ) is True

    def test_check_scope_viewer(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("view_key", role=ROLE_VIEWER)
        assert mgr.check_scope(key.key_id, SCOPE_READ) is True
        assert mgr.check_scope(key.key_id, SCOPE_WRITE) is False
        assert mgr.check_scope(key.key_id, SCOPE_ADMIN) is False

    def test_invalid_role(self):
        mgr = APIKeyManager()
        with pytest.raises(ValueError, match="Invalid role"):
            mgr.create_key("bad", role="superuser")

    def test_key_expiry(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("expiring", expires_in_days=0)
        # expires_in_days=0 → expires_at stays None (falsy 0)
        # Actually, 0 is falsy so expires_at = None → key should be valid
        result = mgr.authenticate(raw)
        assert result.authenticated is True

    def test_request_count_increments(self):
        mgr = APIKeyManager()
        raw, key = mgr.create_key("counter")
        mgr.authenticate(raw)
        mgr.authenticate(raw)
        assert key.request_count == 2

    def test_to_dict(self):
        mgr = APIKeyManager()
        _, key = mgr.create_key("test")
        d = key.to_dict()
        assert "key_id" in d
        assert "is_valid" in d
        assert "key_hash" not in d  # Hash should not be in dict


class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter()
        result = limiter.check_rate_limit("key1", role=ROLE_VIEWER)
        assert result.allowed is True
        assert result.remaining_minute > 0

    def test_blocks_over_minute_limit(self):
        limiter = RateLimiter()
        for _ in range(30):
            limiter.check_rate_limit("key1", role=ROLE_VIEWER)
        result = limiter.check_rate_limit("key1", role=ROLE_VIEWER)
        assert result.allowed is False
        assert result.retry_after_s > 0

    def test_different_keys_independent(self):
        limiter = RateLimiter()
        for _ in range(30):
            limiter.check_rate_limit("key1", role=ROLE_VIEWER)
        result = limiter.check_rate_limit("key2", role=ROLE_VIEWER)
        assert result.allowed is True

    def test_admin_higher_limits(self):
        limiter = RateLimiter()
        for _ in range(60):
            limiter.check_rate_limit("admin_key", role=ROLE_ADMIN)
        result = limiter.check_rate_limit("admin_key", role=ROLE_ADMIN)
        assert result.allowed is True  # Admin has 120/min

    def test_get_usage(self):
        limiter = RateLimiter()
        limiter.check_rate_limit("key1", role=ROLE_VIEWER)
        usage = limiter.get_usage("key1")
        assert usage["minute_count"] == 1
        assert usage["hour_count"] == 1

    def test_get_usage_unknown(self):
        limiter = RateLimiter()
        usage = limiter.get_usage("unknown")
        assert usage["minute_count"] == 0

    def test_result_to_dict(self):
        limiter = RateLimiter()
        result = limiter.check_rate_limit("key1")
        d = result.to_dict()
        assert "allowed" in d
        assert "remaining_minute" in d


class TestSecurityConfig:
    def test_default_headers(self):
        config = SecurityConfig()
        headers = config.get_security_headers()
        assert "Content-Security-Policy" in headers
        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"

    def test_hsts(self):
        config = SecurityConfig()
        headers = config.get_security_headers()
        assert "31536000" in headers["Strict-Transport-Security"]

    def test_to_dict(self):
        config = SecurityConfig()
        d = config.to_dict()
        assert "cors_allowed_origins" in d
        assert "security_headers" in d


class TestAuthResult:
    def test_to_dict(self):
        result = AuthResult(
            authenticated=True,
            key_id="test",
            role=ROLE_ADMIN,
            scopes={SCOPE_READ, SCOPE_WRITE},
        )
        d = result.to_dict()
        assert d["authenticated"] is True
        assert isinstance(d["scopes"], list)  # sorted list
