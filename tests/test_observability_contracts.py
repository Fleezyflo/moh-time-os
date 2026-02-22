"""
Observability Contract Tests.

PR-time tests that assert:
1. X-Request-ID infrastructure works
2. traceparent header parsing/generation works
3. Log schema includes request_id + trace_id fields
4. Request context propagation works

These tests verify the observability plumbing without requiring DB access.
Run with: pytest tests/test_observability_contracts.py -v
"""

import sqlite3
from datetime import datetime

import pytest


class TestRequestIdInfrastructure:
    """Verify request_id infrastructure works correctly."""

    def test_generate_request_id_format(self):
        """Generated request IDs have expected format."""
        from lib.observability import RequestContext

        with RequestContext() as ctx:
            assert ctx.request_id is not None
            assert len(ctx.request_id) >= 8
            # Should be prefixed with 'req-'
            assert ctx.request_id.startswith("req-")

    def test_custom_request_id_preserved(self):
        """Custom request ID is preserved in context."""
        from lib.observability import RequestContext, get_request_id

        with RequestContext(request_id="custom-test-123") as ctx:
            assert ctx.request_id == "custom-test-123"
            assert get_request_id() == "custom-test-123"

    def test_request_id_context_isolation(self):
        """Request ID contexts are isolated."""
        from lib.observability import RequestContext, get_request_id

        with RequestContext(request_id="outer-123"):
            assert get_request_id() == "outer-123"

            with RequestContext(request_id="inner-456"):
                assert get_request_id() == "inner-456"


class TestTraceparentSupport:
    """Verify W3C traceparent header support."""

    def test_parse_valid_traceparent(self):
        """Valid traceparent header is parsed correctly."""
        from lib.observability import parse_traceparent

        # Standard W3C traceparent format
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        trace_id, span_id = parse_traceparent(traceparent)

        assert trace_id == "0af7651916cd43dd8448eb211c80319c"
        assert span_id == "b7ad6b7169203331"

    def test_parse_invalid_traceparent(self):
        """Invalid traceparent returns None."""
        from lib.observability import parse_traceparent

        # None
        trace_id, span_id = parse_traceparent(None)
        assert trace_id is None
        assert span_id is None

        # Invalid format
        trace_id, span_id = parse_traceparent("invalid")
        assert trace_id is None
        assert span_id is None

        # Wrong number of parts
        trace_id, span_id = parse_traceparent("00-abc")
        assert trace_id is None
        assert span_id is None

    def test_parse_traceparent_wrong_lengths(self):
        """traceparent with wrong field lengths returns None."""
        from lib.observability import parse_traceparent

        # trace_id too short (should be 32 chars)
        trace_id, span_id = parse_traceparent("00-abc-def123456789abcd-01")
        assert trace_id is None

    def test_create_traceparent(self):
        """traceparent header can be created."""
        from lib.observability import create_traceparent, generate_span_id, generate_trace_id

        trace_id = generate_trace_id()
        span_id = generate_span_id()

        traceparent = create_traceparent(trace_id, span_id)

        # Format: version-trace_id-span_id-flags
        parts = traceparent.split("-")
        assert len(parts) == 4
        assert parts[0] == "00"  # version
        assert parts[1] == trace_id
        assert parts[2] == span_id
        assert parts[3] in ("00", "01")  # flags

    def test_generate_trace_id_format(self):
        """Generated trace IDs have correct format."""
        from lib.observability import generate_trace_id

        trace_id = generate_trace_id()
        assert len(trace_id) == 32  # 16 bytes hex encoded
        assert all(c in "0123456789abcdef" for c in trace_id)

    def test_generate_span_id_format(self):
        """Generated span IDs have correct format."""
        from lib.observability import generate_span_id

        span_id = generate_span_id()
        assert len(span_id) == 16  # 8 bytes hex encoded
        assert all(c in "0123456789abcdef" for c in span_id)


class TestLogSchema:
    """Verify log schema includes required observability fields."""

    def test_log_entry_accepts_request_id(self):
        """LogEntry can include request_id field."""
        from lib.observability.log_schema import LogEntry, LogLevel

        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Test message",
            logger="test_logger",
            request_id="log-test-123",
        )

        serialized = entry.to_dict()
        assert "request_id" in serialized
        assert serialized["request_id"] == "log-test-123"

    def test_log_entry_accepts_trace_id(self):
        """LogEntry can include trace_id field."""
        from lib.observability.log_schema import LogEntry, LogLevel

        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Test message",
            logger="test_logger",
            trace_id="trace-abc123",
        )

        serialized = entry.to_dict()
        assert "trace_id" in serialized
        assert serialized["trace_id"] == "trace-abc123"

    def test_log_entry_required_fields(self):
        """LogEntry requires timestamp, level, message, logger."""
        from lib.observability.log_schema import LogEntry, LogLevel

        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.ERROR,
            message="Error occurred",
            logger="api.endpoint",
        )

        serialized = entry.to_dict()
        assert "timestamp" in serialized
        assert "level" in serialized
        assert "message" in serialized
        assert "logger" in serialized


class TestObservabilityExports:
    """Verify observability module exports required functions."""

    def test_request_context_exported(self):
        """RequestContext class is exported."""
        from lib.observability import RequestContext

        assert RequestContext is not None

    def test_request_id_functions_exported(self):
        """Request ID functions are exported."""
        from lib.observability import get_request_id, set_request_id

        assert callable(get_request_id)
        assert callable(set_request_id)

    def test_trace_functions_exported(self):
        """Trace functions are exported."""
        from lib.observability import (
            create_traceparent,
            generate_span_id,
            generate_trace_id,
            get_trace_id,
            parse_traceparent,
        )

        assert callable(parse_traceparent)
        assert callable(create_traceparent)
        assert callable(generate_trace_id)
        assert callable(generate_span_id)
        assert callable(get_trace_id)


class TestSpecRouterRequestIdHandling:
    """Verify spec_router request_id handling setup."""

    def test_get_request_id_dependency_exists(self):
        """spec_router has get_request_id dependency function."""
        from api.spec_router import get_request_id

        assert callable(get_request_id)

    def test_generate_request_id_exists(self):
        """generate_request_id function exists."""
        from lib.safety import generate_request_id

        assert callable(generate_request_id)

        # Verify format
        rid = generate_request_id()
        assert rid.startswith("req-")
        assert len(rid) >= 8


class TestAuditRequestIdIntegration:
    """Verify audit system captures request_id."""

    def test_audit_event_has_request_id_field(self):
        """AuditEvent dataclass has request_id field."""
        # Check the dataclass has request_id field
        import dataclasses

        from lib.audit import AuditEvent

        fields = {f.name for f in dataclasses.fields(AuditEvent)}
        assert "request_id" in fields

    def test_audit_store_records_request_id(self, tmp_path):
        """AuditStore records request_id with events."""
        from lib.audit import AuditStore
        from lib.observability import RequestContext

        # Create a temp DB connection
        db_path = tmp_path / "test_audit.db"
        conn = sqlite3.connect(str(db_path))

        store = AuditStore(conn)

        with RequestContext(request_id="audit-test-123"):
            event = store.record(
                event_type="test_event",
                entity_type="test",
                entity_id="entity-1",
                payload={"data": "value"},
            )

        assert event.request_id == "audit-test-123"
        conn.close()


class TestSafetyContextRequestId:
    """Verify safety context includes request_id."""

    def test_write_context_data_has_request_id_field(self):
        """WriteContextData has request_id field."""
        # Check the dataclass has request_id field
        import dataclasses

        from lib.safety.context import WriteContextData

        fields = {f.name for f in dataclasses.fields(WriteContextData)}
        assert "request_id" in fields

    def test_write_context_can_be_created(self):
        """WriteContextData can be instantiated with request_id."""
        from lib.safety.context import WriteContextData

        ctx = WriteContextData(
            request_id="write-ctx-123",
            actor="test_user",
            source="test",
            git_sha="abc123",
            set_at="2026-02-11T00:00:00Z",
        )

        assert ctx.request_id == "write-ctx-123"
