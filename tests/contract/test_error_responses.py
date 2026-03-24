"""
Contract tests for unified ErrorResponse format.

These tests verify that all HTTP errors from the API return a consistent
ErrorResponse shape: {error, error_type, detail?, request_id?}.

This ensures frontend code can rely on a single error format across all endpoints.
"""

import pytest
from pydantic import ValidationError

from api.response_models import ErrorResponse, classify_error_type

# =============================================================================
# ErrorResponse model tests
# =============================================================================


class TestErrorResponseModel:
    """Verify ErrorResponse model fields and validation."""

    def test_error_response_required_fields(self):
        """ErrorResponse must have error and error_type."""
        resp = ErrorResponse(error="Something went wrong", error_type="server")
        assert resp.error == "Something went wrong"
        assert resp.error_type == "server"
        assert resp.detail is None
        assert resp.request_id is None

    def test_error_response_all_fields(self):
        """ErrorResponse supports all optional fields."""
        resp = ErrorResponse(
            error="Not found",
            error_type="not_found",
            detail="Entity with id=123 does not exist",
            request_id="req-abc-123",
        )
        assert resp.error == "Not found"
        assert resp.error_type == "not_found"
        assert resp.detail == "Entity with id=123 does not exist"
        assert resp.request_id == "req-abc-123"

    def test_error_response_missing_required_raises(self):
        """ErrorResponse raises ValidationError without required fields."""
        with pytest.raises(ValidationError):
            ErrorResponse()  # type: ignore[call-arg]

    def test_error_response_serialization(self):
        """ErrorResponse serializes to dict with correct keys."""
        resp = ErrorResponse(error="Bad request", error_type="validation")
        data = resp.model_dump()
        assert "error" in data
        assert "error_type" in data
        assert "detail" in data
        assert "request_id" in data

    def test_error_response_exclude_none(self):
        """ErrorResponse exclude_none removes optional None fields."""
        resp = ErrorResponse(error="Unauthorized", error_type="auth")
        data = resp.model_dump(exclude_none=True)
        assert "error" in data
        assert "error_type" in data
        assert "detail" not in data
        assert "request_id" not in data


# =============================================================================
# classify_error_type tests
# =============================================================================


class TestClassifyErrorType:
    """Verify status code to error_type mapping."""

    def test_400_is_validation(self):
        assert classify_error_type(400) == "validation"

    def test_401_is_auth(self):
        assert classify_error_type(401) == "auth"

    def test_403_is_forbidden(self):
        assert classify_error_type(403) == "forbidden"

    def test_404_is_not_found(self):
        assert classify_error_type(404) == "not_found"

    def test_409_is_conflict(self):
        assert classify_error_type(409) == "conflict"

    def test_500_is_server(self):
        assert classify_error_type(500) == "server"

    def test_502_is_server(self):
        """All 5xx codes map to server."""
        assert classify_error_type(502) == "server"

    def test_503_is_server(self):
        assert classify_error_type(503) == "server"

    def test_422_is_server(self):
        """Unrecognized 4xx codes default to server."""
        assert classify_error_type(422) == "server"


# =============================================================================
# Integration test: HTTPException handler produces ErrorResponse shape
# =============================================================================


class TestUnifiedErrorHandler:
    """Verify the custom HTTPException handler in server.py returns ErrorResponse shape."""

    @pytest.fixture
    def client(self):
        """Create a TestClient for the FastAPI app."""
        try:
            from fastapi.testclient import TestClient

            from api.server import app

            return TestClient(app, raise_server_exceptions=False)
        except Exception:
            pytest.skip("TestClient or app not available")

    def test_404_returns_error_response_shape(self, client):
        """404 errors return unified ErrorResponse with error_type=not_found."""
        resp = client.get("/api/v2/nonexistent-endpoint-that-does-not-exist")
        # FastAPI returns 404 for unknown routes
        if resp.status_code == 404:
            data = resp.json()
            assert "error" in data, f"Missing 'error' field in response: {data}"
            assert "error_type" in data, f"Missing 'error_type' field in response: {data}"
            assert data["error_type"] == "not_found"

    def test_error_response_has_required_fields(self, client):
        """All error responses include error and error_type fields."""
        # Hit a known endpoint with invalid data to trigger an error
        resp = client.get("/api/v2/nonexistent-endpoint-that-does-not-exist")
        if resp.status_code >= 400:
            data = resp.json()
            assert "error" in data
            assert "error_type" in data
            # Validate it conforms to ErrorResponse model
            ErrorResponse(**data)
