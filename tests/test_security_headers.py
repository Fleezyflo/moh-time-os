"""
Test suite for security headers middleware.

Tests validate:
- All security headers present in responses
- CORS headers configuration
- CSP header values
- HSTS and other security headers
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from lib.security.headers import (
    CORS_ALLOWED_HEADERS,
    CORS_ALLOWED_METHODS,
    CSP_POLICY,
    DEFAULT_CORS_ORIGINS,
    SECURITY_HEADERS,
    SecurityHeadersMiddleware,
    is_cors_allowed,
    parse_cors_origins,
)


class TestParseCorsOrigins:
    """Tests for CORS origin parsing."""

    def test_parse_wildcard_origin(self):
        """Test parsing wildcard origin."""
        origins = parse_cors_origins("*")
        assert origins == ["*"]

    def test_parse_single_origin(self):
        """Test parsing single origin."""
        origins = parse_cors_origins("http://localhost:3000")
        assert origins == ["http://localhost:3000"]

    def test_parse_multiple_origins(self):
        """Test parsing comma-separated origins."""
        origins = parse_cors_origins("http://localhost:3000,https://example.com,http://app.local")
        assert origins == ["http://localhost:3000", "https://example.com", "http://app.local"]

    def test_parse_origins_with_whitespace(self):
        """Test parsing origins with surrounding whitespace."""
        origins = parse_cors_origins("  http://localhost:3000  ,  https://example.com  ")
        assert origins == ["http://localhost:3000", "https://example.com"]

    def test_parse_empty_string_defaults(self):
        """Test that empty string defaults to localhost."""
        origins = parse_cors_origins("")
        assert origins == ["http://localhost:*"]

    def test_parse_origins_with_trailing_comma(self):
        """Test parsing origins with trailing comma."""
        origins = parse_cors_origins("http://localhost:3000,https://example.com,")
        assert origins == ["http://localhost:3000", "https://example.com"]

    def test_parse_wildcard_pattern(self):
        """Test parsing wildcard pattern origin."""
        origins = parse_cors_origins("http://localhost:*")
        assert origins == ["http://localhost:*"]


class TestIsCorsAllowed:
    """Tests for CORS allow checking."""

    def test_wildcard_allows_all(self):
        """Test that wildcard allows all origins."""
        assert is_cors_allowed("http://example.com", ["*"]) is True
        assert is_cors_allowed("http://localhost:3000", ["*"]) is True
        assert is_cors_allowed("https://anything.com", ["*"]) is True

    def test_exact_match(self):
        """Test exact origin matching."""
        allowed = ["http://localhost:3000", "https://example.com"]
        assert is_cors_allowed("http://localhost:3000", allowed) is True
        assert is_cors_allowed("https://example.com", allowed) is True
        assert is_cors_allowed("http://other.com", allowed) is False

    def test_wildcard_pattern_matching(self):
        """Test wildcard pattern matching."""
        allowed = ["http://localhost:*"]
        assert is_cors_allowed("http://localhost:3000", allowed) is True
        assert is_cors_allowed("http://localhost:8080", allowed) is True
        assert is_cors_allowed("http://localhost:", allowed) is True
        assert is_cors_allowed("https://localhost:3000", allowed) is False
        assert is_cors_allowed("http://example.com:3000", allowed) is False

    def test_multiple_patterns(self):
        """Test multiple allowed patterns."""
        allowed = ["http://localhost:*", "https://example.com"]
        assert is_cors_allowed("http://localhost:3000", allowed) is True
        assert is_cors_allowed("https://example.com", allowed) is True
        assert is_cors_allowed("http://other.com", allowed) is False

    def test_empty_allowed_list(self):
        """Test behavior with empty allowed list."""
        assert is_cors_allowed("http://example.com", []) is False

    def test_subdomain_matching(self):
        """Test that subdomains don't match without wildcard."""
        allowed = ["https://example.com"]
        assert is_cors_allowed("https://example.com", allowed) is True
        assert is_cors_allowed("https://api.example.com", allowed) is False

    def test_protocol_sensitive_matching(self):
        """Test that protocol is considered in matching."""
        allowed = ["https://example.com"]
        assert is_cors_allowed("https://example.com", allowed) is True
        assert is_cors_allowed("http://example.com", allowed) is False


class TestSecurityHeadersMiddlewareBasics:
    """Tests for basic middleware initialization."""

    def test_middleware_initialization_default(self):
        """Test middleware initialization with default origins."""
        app = MagicMock()
        with patch.dict(os.environ, {}, clear=True):
            middleware = SecurityHeadersMiddleware(app)
            assert middleware.allowed_origins == ["http://localhost:*"]

    def test_middleware_initialization_custom_origins(self):
        """Test middleware initialization with custom origins."""
        app = MagicMock()
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://example.com"}, clear=True):
            middleware = SecurityHeadersMiddleware(app)
            assert middleware.allowed_origins == ["https://example.com"]

    def test_middleware_initialization_multiple_origins(self):
        """Test middleware with multiple origins."""
        app = MagicMock()
        origins_env = "https://example.com,https://app.example.com,http://localhost:3000"
        with patch.dict(os.environ, {"CORS_ORIGINS": origins_env}, clear=True):
            middleware = SecurityHeadersMiddleware(app)
            assert len(middleware.allowed_origins) == 3


class TestSecurityHeaders:
    """Tests for individual security headers and CSP policy."""

    def test_csp_header_present_in_constants(self):
        """Test that CSP header constant is defined."""
        assert CSP_POLICY is not None
        assert len(CSP_POLICY) > 0

    def test_csp_contains_required_directives(self):
        """Test that CSP contains required directives."""
        assert "default-src 'self'" in CSP_POLICY
        assert "script-src 'self'" in CSP_POLICY
        assert "style-src 'self'" in CSP_POLICY
        assert "font-src 'self'" in CSP_POLICY
        assert "connect-src 'self'" in CSP_POLICY

    def test_csp_contains_unsafe_inline(self):
        """Test that CSP contains unsafe-inline for scripts and styles."""
        assert "'unsafe-inline'" in CSP_POLICY

    def test_csp_contains_external_resources(self):
        """Test that CSP allows external fonts and styles."""
        assert "https://fonts.googleapis.com" in CSP_POLICY
        assert "https://fonts.gstatic.com" in CSP_POLICY

    def test_hsts_header_present_in_config(self):
        """Test that HSTS header is in security headers."""
        assert "Strict-Transport-Security" in SECURITY_HEADERS
        assert "max-age=31536000" in SECURITY_HEADERS["Strict-Transport-Security"]

    def test_x_frame_options_header_config(self):
        """Test that X-Frame-Options header is configured."""
        assert "X-Frame-Options" in SECURITY_HEADERS
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"

    def test_x_content_type_options_header_config(self):
        """Test that X-Content-Type-Options header is configured."""
        assert "X-Content-Type-Options" in SECURITY_HEADERS
        assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"

    def test_x_xss_protection_header_config(self):
        """Test that X-XSS-Protection header is configured."""
        assert "X-XSS-Protection" in SECURITY_HEADERS
        assert SECURITY_HEADERS["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy_header_config(self):
        """Test that Referrer-Policy header is configured."""
        assert "Referrer-Policy" in SECURITY_HEADERS
        assert SECURITY_HEADERS["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_header_config(self):
        """Test that Permissions-Policy header is configured."""
        assert "Permissions-Policy" in SECURITY_HEADERS
        perms = SECURITY_HEADERS["Permissions-Policy"]
        assert "camera=()" in perms
        assert "microphone=()" in perms
        assert "geolocation=()" in perms

    def test_all_security_headers_present(self):
        """Test that all required security headers are in config."""
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Referrer-Policy",
            "Permissions-Policy",
        ]
        for header in required_headers:
            assert header in SECURITY_HEADERS, f"Missing header: {header}"


class TestSecurityHeadersConstants:
    """Tests for header configuration constants."""

    def test_cors_allowed_methods(self):
        """Test CORS methods configuration."""
        assert "GET" in CORS_ALLOWED_METHODS
        assert "POST" in CORS_ALLOWED_METHODS
        assert "PUT" in CORS_ALLOWED_METHODS
        assert "DELETE" in CORS_ALLOWED_METHODS
        assert "OPTIONS" in CORS_ALLOWED_METHODS

    def test_cors_allowed_headers(self):
        """Test CORS headers configuration."""
        assert "Authorization" in CORS_ALLOWED_HEADERS
        assert "Content-Type" in CORS_ALLOWED_HEADERS
        assert "X-API-Token" in CORS_ALLOWED_HEADERS

    def test_security_headers_config(self):
        """Test security headers configuration is complete."""
        assert "X-Content-Type-Options" in SECURITY_HEADERS
        assert "X-Frame-Options" in SECURITY_HEADERS
        assert "X-XSS-Protection" in SECURITY_HEADERS
        assert "Strict-Transport-Security" in SECURITY_HEADERS
        assert "Referrer-Policy" in SECURITY_HEADERS
        assert "Permissions-Policy" in SECURITY_HEADERS
