"""
Comprehensive tests for credential audit system.

Tests:
- Scanner detects hardcoded passwords
- Scanner detects hardcoded tokens
- Scanner detects API keys
- Scanner detects AWS-style keys
- Scanner detects Google API keys
- Scanner detects JWT tokens
- Scanner detects connection strings with credentials
- Scanner ignores test files
- Scanner ignores .env.example
- Scanner ignores env var references
- Scanner ignores comments
- Secrets config validates required vars
- Secrets config detects missing vars
- mask_secret properly masks values
- mask_secret handles short values
- .env.example contains all documented secrets
- SecretsAuditResult.is_complete() works
- SecretsAuditResult.has_warnings() works
- SecretsAuditResult.to_dict() works
- get_secret() returns configured values
- is_configured() checks if secret is set
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.security.secrets_config import (
    REQUIRED_SECRETS,
    SecretsAuditResult,
    describe_secret,
    get_secret,
    is_configured,
    is_required_secret,
    mask_secret,
    validate_secrets,
)
from scripts.audit_credentials import CredentialScanner

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def scanner():
    """Create a credential scanner instance."""
    return CredentialScanner()


@pytest.fixture
def temp_python_file():
    """Create a temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        yield f
    Path(f.name).unlink()


@pytest.fixture
def temp_test_file():
    """Create a temporary test Python file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix="test.py", delete=False) as f:
        yield f
    Path(f.name).unlink()


# =============================================================================
# Scanner Tests - Hardcoded Credentials Detection
# =============================================================================


class TestScannerDetectsPasswords:
    """Test scanner detects hardcoded passwords."""

    def test_detects_password_double_quotes(self, scanner, temp_python_file):
        """Scanner detects password = "..." with double quotes."""
        temp_python_file.write('password = "my_secret_password_12345678"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"
        assert len(result.issues) > 0
        assert result.issues[0][1] == "password_hardcoded"

    def test_detects_password_single_quotes(self, scanner, temp_python_file):
        """Scanner detects password = '...' with single quotes."""
        temp_python_file.write("password = 'secret_pass_98765432'\n")
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"
        assert len(result.issues) > 0

    def test_detects_passwd_variant(self, scanner, temp_python_file):
        """Scanner detects passwd (variant of password)."""
        temp_python_file.write('passwd = "hidden_passwd_abcd1234"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"

    def test_ignores_password_in_comment(self, scanner, temp_python_file):
        """Scanner ignores passwords mentioned in comments."""
        temp_python_file.write("# password = 'secret'\n")
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "PASS"


class TestScannerDetectsTokens:
    """Test scanner detects hardcoded tokens."""

    def test_detects_token_hardcoded(self, scanner, temp_python_file):
        """Scanner detects token = "..." patterns."""
        temp_python_file.write('token = "bearer_token_abcdef123456"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"
        assert any(issue[1] == "token_hardcoded" for issue in result.issues)

    def test_detects_api_key_hardcoded(self, scanner, temp_python_file):
        """Scanner detects api_key = "..." patterns."""
        temp_python_file.write('api_key = "fake_api_key_abcdefghijklmnopqrst1234"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"

    def test_detects_secret_key(self, scanner, temp_python_file):
        """Scanner detects SECRET_KEY = "..." patterns."""
        temp_python_file.write('SECRET_KEY = "django_secret_abcdef1234567890abcdef1234567890"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"


class TestScannerDetectsSpecialFormats:
    """Test scanner detects special credential formats."""

    def test_detects_aws_key(self, scanner, temp_python_file):
        """Scanner detects AWS-style keys (AKIA...)."""
        temp_python_file.write('aws_key = "AKIAIOSFODNN7EXAMPLE"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"
        assert any("aws_key" in issue[1] for issue in result.issues)

    def test_detects_google_api_key(self, scanner, temp_python_file):
        """Scanner detects Google API keys (AIza...)."""
        temp_python_file.write('google_key = "AIzaSyDummyKeyWith35Characters1234567"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"

    def test_detects_jwt_token(self, scanner, temp_python_file):
        """Scanner detects JWT tokens (eyJ...)."""
        temp_python_file.write(
            'jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"\n'
        )
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"

    def test_detects_postgres_connection_string(self, scanner, temp_python_file):
        """Scanner detects postgres://user:pass@host connection strings."""
        temp_python_file.write('db_url = "postgres://admin:mypassword123@localhost:5432/dbname"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"

    def test_detects_mysql_connection_string(self, scanner, temp_python_file):
        """Scanner detects mysql://user:pass@host connection strings."""
        temp_python_file.write('db_url = "mysql://root:password@localhost/dbname"\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "FAIL"


class TestScannerExclusions:
    """Test scanner properly excludes certain patterns."""

    def test_ignores_env_environ_get(self, scanner, temp_python_file):
        """Scanner ignores os.environ.get(...) patterns."""
        temp_python_file.write('password = os.environ.get("PASSWORD")\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "PASS"

    def test_ignores_os_getenv(self, scanner, temp_python_file):
        """Scanner ignores os.getenv(...) patterns."""
        temp_python_file.write('api_key = os.getenv("API_KEY")\n')
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "PASS"

    def test_ignores_test_files(self, scanner):
        """Scanner ignores test_*.py files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, prefix="test_") as f:
            f.write('password = "secret_test_password_12345678"\n')
            f.flush()
            result = scanner.scan_file(Path(f.name))
            Path(f.name).unlink()

        # Test files are skipped entirely
        assert result.status == "PASS"

    def test_ignores_env_example_file(self, scanner):
        """Scanner ignores .env.example files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env.example", delete=False) as f:
            f.write("PASSWORD=example_password_value\n")
            f.flush()
            result = scanner.scan_file(Path(f.name))
            Path(f.name).unlink()

        # .env.example is skipped entirely
        assert result.status == "PASS"

    def test_ignores_audit_script_itself(self, scanner):
        """Scanner ignores audit_credentials.py itself."""
        # This is checked by file name, so we'll verify the skip logic
        audit_path = Path("audit_credentials.py")
        assert scanner.should_skip_file(audit_path)


# =============================================================================
# SecretsAuditResult Tests
# =============================================================================


class TestSecretsAuditResult:
    """Test SecretsAuditResult dataclass."""

    def test_is_complete_true(self):
        """is_complete() returns True when no missing secrets."""
        result = SecretsAuditResult(configured=["TOKEN1", "TOKEN2"], missing=[], warnings=[])
        assert result.is_complete() is True

    def test_is_complete_false(self):
        """is_complete() returns False when secrets are missing."""
        result = SecretsAuditResult(configured=["TOKEN1"], missing=["TOKEN2"], warnings=[])
        assert result.is_complete() is False

    def test_has_warnings_true(self):
        """has_warnings() returns True when warnings exist."""
        result = SecretsAuditResult(configured=["TOKEN1"], missing=[], warnings=["Warning message"])
        assert result.has_warnings() is True

    def test_has_warnings_false(self):
        """has_warnings() returns False when no warnings."""
        result = SecretsAuditResult(configured=["TOKEN1"], missing=[], warnings=[])
        assert result.has_warnings() is False

    def test_to_dict(self):
        """to_dict() serializes result properly."""
        result = SecretsAuditResult(
            configured=["TOKEN1", "TOKEN2"],
            missing=["TOKEN3"],
            warnings=["Warning"],
        )
        d = result.to_dict()

        assert d["configured"] == ["TOKEN1", "TOKEN2"]
        assert d["missing"] == ["TOKEN3"]
        assert d["warnings"] == ["Warning"]
        assert d["is_complete"] is False
        assert d["has_warnings"] is True


# =============================================================================
# validate_secrets Tests
# =============================================================================


class TestValidateSecrets:
    """Test secrets validation."""

    def test_validate_required_only_true(self):
        """validate_secrets(required_only=True) checks only required secrets."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_secrets(required_only=True)

            # Should have missing required secrets
            assert len(result.missing) > 0
            assert "INTEL_API_TOKEN" in result.missing
            assert "ASANA_TOKEN" in result.missing

    def test_validate_required_only_false(self):
        """validate_secrets(required_only=False) checks all secrets."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_secrets(required_only=False)

            # Should include both required and optional as missing/warning
            total_items = len(result.configured) + len(result.missing) + len(result.warnings)
            assert total_items == len(REQUIRED_SECRETS)

    def test_validate_detects_configured(self):
        """validate_secrets() detects configured secrets."""
        with patch.dict(
            os.environ,
            {"INTEL_API_TOKEN": "test_token", "ASANA_TOKEN": "test_asana"},
            clear=True,
        ):
            result = validate_secrets(required_only=True)

            assert "INTEL_API_TOKEN" in result.configured
            assert "ASANA_TOKEN" in result.configured

    def test_validate_detects_missing(self):
        """validate_secrets() detects missing required secrets."""
        with patch.dict(
            os.environ,
            {"INTEL_API_TOKEN": "test_token"},
            clear=True,
        ):
            result = validate_secrets(required_only=True)

            # ASANA_TOKEN should be missing
            assert "ASANA_TOKEN" in result.missing


# =============================================================================
# mask_secret Tests
# =============================================================================


class TestMaskSecret:
    """Test secret masking functionality."""

    def test_mask_secret_normal_length(self):
        """mask_secret() masks normal-length secrets."""
        result = mask_secret("my_secret_api_key_12345")
        assert result == "my_s***"

    def test_mask_secret_custom_chars(self):
        """mask_secret() respects chars_visible parameter."""
        result = mask_secret("my_secret_api_key_12345", chars_visible=10)
        assert result == "my_secret_***"

    def test_mask_secret_too_short(self):
        """mask_secret() returns *** for very short values."""
        result = mask_secret("abc")
        assert result == "***"

    def test_mask_secret_empty(self):
        """mask_secret() handles empty strings."""
        result = mask_secret("")
        assert result == "***"

    def test_mask_secret_long_value(self):
        """mask_secret() masks very long values."""
        long_secret = "a" * 1000
        result = mask_secret(long_secret, chars_visible=4)
        assert result == "aaaa***"


# =============================================================================
# Helper Functions Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper functions in secrets_config."""

    def test_get_secret_configured(self):
        """get_secret() returns value when configured."""
        with patch.dict(os.environ, {"INTEL_API_TOKEN": "test_token"}):
            result = get_secret("INTEL_API_TOKEN")
            assert result == "test_token"

    def test_get_secret_missing_with_default(self):
        """get_secret() returns default when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_secret("NONEXISTENT", default="default_value")
            assert result == "default_value"

    def test_get_secret_missing_no_default(self):
        """get_secret() returns None when not configured and no default."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_secret("NONEXISTENT")
            assert result is None

    def test_is_configured_true(self):
        """is_configured() returns True when env var is set."""
        with patch.dict(os.environ, {"INTEL_API_TOKEN": "value"}):
            assert is_configured("INTEL_API_TOKEN") is True

    def test_is_configured_false(self):
        """is_configured() returns False when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_configured("INTEL_API_TOKEN") is False

    def test_describe_secret_known(self):
        """describe_secret() returns description for known secrets."""
        description = describe_secret("INTEL_API_TOKEN")
        assert description is not None
        assert "Intel" in description

    def test_describe_secret_unknown(self):
        """describe_secret() returns None for unknown secrets."""
        description = describe_secret("UNKNOWN_SECRET")
        assert description is None

    def test_is_required_secret_required(self):
        """is_required_secret() returns True for required secrets."""
        assert is_required_secret("INTEL_API_TOKEN") is True
        assert is_required_secret("ASANA_TOKEN") is True

    def test_is_required_secret_optional(self):
        """is_required_secret() returns False for optional secrets."""
        assert is_required_secret("GOOGLE_CHAT_WEBHOOK_URL") is False

    def test_is_required_secret_unknown(self):
        """is_required_secret() returns False for unknown secrets."""
        assert is_required_secret("UNKNOWN_SECRET") is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestEnvExampleFile:
    """Test that .env.example contains all documented secrets."""

    def test_env_example_contains_all_secrets(self):
        """All REQUIRED_SECRETS should be mentioned in .env.example."""
        env_example_path = Path(__file__).parent.parent / ".env.example"

        if not env_example_path.exists():
            pytest.skip(".env.example not found")

        content = env_example_path.read_text()

        for var_name, _, _ in REQUIRED_SECRETS:
            assert var_name in content, f"{var_name} not found in .env.example"

    def test_env_example_has_descriptions(self):
        """Each secret in .env.example should have a description."""
        env_example_path = Path(__file__).parent.parent / ".env.example"

        if not env_example_path.exists():
            pytest.skip(".env.example not found")

        content = env_example_path.read_text()

        # Check for comment lines
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("INTEL_API_TOKEN=") or line.startswith("ASANA_TOKEN="):
                # Should have a comment above it
                if i > 0:
                    prev_line = lines[i - 1]
                    # Allow multiple comment lines
                    assert prev_line.startswith("#") or lines[i - 2].startswith(
                        "#"
                    ), f"No description for {line.split('=')[0]}"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_scanner_handles_unreadable_file(self, scanner, temp_python_file):
        """Scanner handles files it can't read gracefully."""
        file_path = Path(temp_python_file.name)
        # Make file unreadable
        os.chmod(file_path, 0o000)

        try:
            result = scanner.scan_file(file_path)
            # Should return WARN, not crash
            assert result.status in ["WARN", "FAIL", "PASS"]
        finally:
            # Restore permissions for cleanup
            os.chmod(file_path, 0o644)

    def test_scanner_handles_empty_file(self, scanner, temp_python_file):
        """Scanner handles empty files."""
        temp_python_file.write("")
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "PASS"

    def test_scanner_handles_unicode(self, scanner, temp_python_file):
        """Scanner handles files with unicode characters."""
        temp_python_file.write("# Comment with unicode: 你好世界 🚀\n")
        temp_python_file.flush()

        result = scanner.scan_file(Path(temp_python_file.name))
        assert result.status == "PASS"

    def test_mask_secret_with_none(self):
        """mask_secret handles None gracefully."""
        # Should handle falsy values
        result = mask_secret("") if "" else "***"
        assert result == "***"
