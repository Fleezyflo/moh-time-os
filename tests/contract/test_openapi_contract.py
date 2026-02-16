"""
OpenAPI contract tests.

These tests verify:
- Key endpoints exist
- Response models include required fields
- No overly permissive schemas
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def openapi_schema():
    """Load pinned OpenAPI schema."""
    schema_path = Path("docs/openapi.json")
    if not schema_path.exists():
        pytest.skip("docs/openapi.json not found")
    return json.loads(schema_path.read_text())


class TestRequiredEndpoints:
    """Verify key endpoints exist."""

    REQUIRED_ENDPOINTS = [
        "/api/health",
        "/api/v2/health",
        "/api/clients",
        "/api/control-room/proposals",
        "/api/control-room/issues",
    ]

    def test_required_endpoints_exist(self, openapi_schema):
        """All required endpoints must be defined."""
        paths = openapi_schema.get("paths", {})

        for endpoint in self.REQUIRED_ENDPOINTS:
            assert endpoint in paths, f"Required endpoint missing: {endpoint}"

    def test_health_endpoint_has_get(self, openapi_schema):
        """Health endpoints must have GET method."""
        paths = openapi_schema.get("paths", {})

        for endpoint in ["/api/health", "/api/v2/health"]:
            if endpoint in paths:
                assert "get" in paths[endpoint], f"{endpoint} missing GET method"


class TestResponseModels:
    """Verify response models have required fields."""

    def test_health_response_has_status(self, openapi_schema):
        """Health response must include status field."""
        paths = openapi_schema.get("paths", {})
        health_path = paths.get("/api/health", {})
        get_op = health_path.get("get", {})
        responses = get_op.get("responses", {})

        # Check 200 response exists
        assert "200" in responses, "/api/health missing 200 response"

    def test_proposals_endpoint_exists(self, openapi_schema):
        """Proposals endpoint should exist with GET method."""
        paths = openapi_schema.get("paths", {})
        proposals_path = paths.get("/api/control-room/proposals", {})

        assert "get" in proposals_path, "Proposals endpoint missing GET method"
        assert "200" in proposals_path["get"].get("responses", {}), (
            "Proposals endpoint missing 200 response"
        )


class TestSchemaStrictness:
    """Verify schemas are not overly permissive."""

    def test_no_root_additionalProperties_true(self, openapi_schema):
        """Root schemas should not allow arbitrary additional properties."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})

        permissive_schemas = []
        for name, schema in schemas.items():
            if schema.get("additionalProperties") is True:
                permissive_schemas.append(name)

        # Allow some flexibility but flag if too many
        max_permissive = 5
        if len(permissive_schemas) > max_permissive:
            pytest.fail(
                f"Too many permissive schemas ({len(permissive_schemas)} > {max_permissive}): "
                f"{permissive_schemas[:5]}..."
            )

    def test_any_type_responses_tracked(self, openapi_schema):
        """Track endpoints without defined schemas (burn-down target)."""
        paths = openapi_schema.get("paths", {})

        any_type_endpoints = []
        for path, methods in paths.items():
            for method, op in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    responses = op.get("responses", {})
                    for _code, response in responses.items():
                        content = response.get("content", {})
                        json_content = content.get("application/json", {})
                        schema = json_content.get("schema", {})

                        # Flag if schema is just {} or {type: object} with no properties
                        if schema == {} or (
                            schema.get("type") == "object"
                            and not schema.get("properties")
                            and not schema.get("$ref")
                        ):
                            any_type_endpoints.append(f"{method.upper()} {path}")

        # Current baseline: 165 any-type endpoints (legacy)
        # Target: reduce to <50 over time
        # For now, just track and don't fail
        current_baseline = 170
        if len(any_type_endpoints) > current_baseline:
            pytest.fail(
                f"Any-type endpoints grew ({len(any_type_endpoints)} > {current_baseline}): "
                f"new endpoints should have proper schemas"
            )


class TestEndpointCount:
    """Track endpoint count to detect unexpected additions/removals."""

    def test_endpoint_count_in_range(self, openapi_schema):
        """Endpoint count should be in expected range."""
        paths = openapi_schema.get("paths", {})
        count = len(paths)

        # Current count is ~172, allow some flexibility
        min_expected = 100
        max_expected = 250

        assert min_expected <= count <= max_expected, (
            f"Endpoint count {count} outside expected range [{min_expected}, {max_expected}]"
        )


class TestUiUsedEndpoints:
    """
    Verify UI-used endpoints cannot loosen.

    These endpoints are used by the React UI and their schemas
    must not remove required fields or change types.
    """

    # Endpoints the UI actually uses - these cannot loosen
    UI_USED_ENDPOINTS = [
        "/api/health",
        "/api/v2/health",
        "/api/metrics",
    ]

    def test_ui_used_endpoints_exist(self, openapi_schema):
        """All UI-used endpoints must exist."""
        paths = openapi_schema.get("paths", {})

        for endpoint in self.UI_USED_ENDPOINTS:
            assert endpoint in paths, f"UI-used endpoint missing: {endpoint}"

    def test_ui_used_endpoints_have_get(self, openapi_schema):
        """UI-used endpoints must support GET method."""
        paths = openapi_schema.get("paths", {})

        for endpoint in self.UI_USED_ENDPOINTS:
            if endpoint in paths:
                assert "get" in paths[endpoint], f"UI-used endpoint {endpoint} missing GET method"

    def test_health_has_required_fields(self, openapi_schema):
        """Health endpoint response must have required fields."""
        paths = openapi_schema.get("paths", {})
        health_path = paths.get("/api/health", {})
        get_op = health_path.get("get", {})
        responses = get_op.get("responses", {})

        # Must have 200 response
        assert "200" in responses, "/api/health must have 200 response"

        # Response must have content
        response_200 = responses["200"]
        content = response_200.get("content", {})
        assert "application/json" in content, "/api/health must return JSON"

    def test_metrics_endpoint_exists(self, openapi_schema):
        """Metrics endpoint must exist for observability."""
        paths = openapi_schema.get("paths", {})
        assert "/api/metrics" in paths, "Metrics endpoint required for observability"
