"""
Evidence Renderer Contract Tests — Spec Section 6.16

Required test cases for evidence envelope validation and link rendering.
"""

from lib.ui_spec_v21.evidence import (
    LINKABLE_SOURCES,
    NO_LINK_SOURCES,
    VALID_EVIDENCE_KINDS,
    create_asana_task_evidence,
    create_calendar_evidence,
    create_gmail_evidence,
    create_invoice_evidence,
    render_link,
    validate_evidence,
)


class TestEvidenceValidation:
    """Test cases for evidence envelope validation (spec 6.16)."""

    def test_valid_invoice_evidence(self):
        """Invoice evidence with all required fields passes validation."""
        evidence = {
            "version": "v1",
            "kind": "invoice",
            "url": None,
            "display_text": "INV-001 · AED 10,000",
            "source_system": "xero",
            "source_id": "xero_inv_123",
            "payload": {
                "number": "INV-001",
                "amount": 10000,
                "currency": "AED",
                "status": "overdue",
            },
        }
        valid, error = validate_evidence(evidence)
        assert valid is True
        assert error is None

    def test_valid_asana_task_evidence(self):
        """Asana task evidence with task_gid passes validation."""
        evidence = {
            "version": "v1",
            "kind": "asana_task",
            "url": "https://app.asana.com/0/proj/task",
            "display_text": "Complete deliverable",
            "source_system": "asana",
            "source_id": "task_gid_123",
            "payload": {"task_gid": "task_gid_123", "name": "Complete deliverable"},
        }
        valid, error = validate_evidence(evidence)
        assert valid is True

    def test_valid_gmail_evidence(self):
        """Gmail thread evidence passes validation."""
        evidence = {
            "version": "v1",
            "kind": "gmail_thread",
            "url": "https://mail.google.com/mail/#all/thread123",
            "display_text": "Re: Project Update",
            "source_system": "gmail",
            "source_id": "thread123",
            "payload": {"thread_id": "thread123", "subject": "Re: Project Update"},
        }
        valid, error = validate_evidence(evidence)
        assert valid is True

    def test_valid_minutes_evidence_url_null(self):
        """Minutes evidence MUST have url=null (spec 6.16)."""
        evidence = {
            "version": "v1",
            "kind": "minutes_analysis",
            "url": None,  # Required to be null
            "display_text": "Meeting notes",
            "source_system": "minutes",
            "source_id": "meet_123",
            "payload": {
                "recording_url": "https://drive.google.com/...",
                "transcript_url": "https://docs.google.com/...",
            },
        }
        valid, error = validate_evidence(evidence)
        assert valid is True

    def test_minutes_evidence_with_url_fails(self):
        """Minutes evidence with non-null url must fail validation."""
        evidence = {
            "version": "v1",
            "kind": "minutes_analysis",
            "url": "https://some-url.com",  # Invalid - must be null
            "display_text": "Meeting notes",
            "source_system": "minutes",
            "source_id": "meet_123",
            "payload": {},
        }
        valid, error = validate_evidence(evidence)
        assert valid is False
        assert "url must be null" in error.lower()

    def test_missing_required_field_fails(self):
        """Evidence missing required field fails validation."""
        evidence = {
            "version": "v1",
            "kind": "invoice",
            # Missing: display_text, source_system, source_id
            "payload": {},
        }
        valid, error = validate_evidence(evidence)
        assert valid is False
        assert "Missing required field" in error

    def test_invalid_version_fails(self):
        """Evidence with unsupported version fails."""
        evidence = {
            "version": "v2",  # Only v1 supported
            "kind": "invoice",
            "display_text": "Test",
            "source_system": "xero",
            "source_id": "123",
            "payload": {
                "number": "1",
                "amount": 100,
                "currency": "AED",
                "status": "sent",
            },
        }
        valid, error = validate_evidence(evidence)
        assert valid is False
        assert "version" in error.lower()

    def test_invalid_kind_fails(self):
        """Evidence with unknown kind fails."""
        evidence = {
            "version": "v1",
            "kind": "unknown_kind",
            "display_text": "Test",
            "source_system": "test",
            "source_id": "123",
            "payload": {},
        }
        valid, error = validate_evidence(evidence)
        assert valid is False
        assert "kind" in error.lower()

    def test_invoice_missing_payload_fields_fails(self):
        """Invoice evidence missing required payload fields fails."""
        evidence = {
            "version": "v1",
            "kind": "invoice",
            "url": None,
            "display_text": "INV-001",
            "source_system": "xero",
            "source_id": "123",
            "payload": {
                "number": "INV-001",
                # Missing: amount, currency, status
            },
        }
        valid, error = validate_evidence(evidence)
        assert valid is False
        assert "payload" in error.lower()


class TestLinkRendering:
    """Test cases for evidence link rendering rules (spec 6.16)."""

    def test_xero_never_renders_link(self):
        """Xero evidence NEVER renders clickable link even with URL."""
        evidence = {
            "version": "v1",
            "kind": "invoice",
            "url": "https://xero.com/invoice/123",  # URL present but ignored
            "display_text": "INV-001",
            "source_system": "xero",
            "source_id": "123",
            "payload": {"number": "INV-001"},
        }
        result = render_link(evidence)
        assert result["can_render_link"] is False
        assert result["is_plain_text"] is True
        assert "Xero" in result["link_text"]

    def test_asana_renders_link_with_url(self):
        """Asana evidence renders clickable link when URL present."""
        evidence = {
            "version": "v1",
            "kind": "asana_task",
            "url": "https://app.asana.com/0/proj/task",
            "display_text": "Task name",
            "source_system": "asana",
            "source_id": "task_123",
            "payload": {},
        }
        result = render_link(evidence)
        assert result["can_render_link"] is True
        assert result["link_url"] == "https://app.asana.com/0/proj/task"
        assert result["is_plain_text"] is False
        assert "Asana" in result["link_text"]

    def test_gmail_renders_link(self):
        """Gmail evidence renders clickable link."""
        evidence = {
            "version": "v1",
            "kind": "gmail_thread",
            "url": "https://mail.google.com/mail/#all/thread123",
            "display_text": "Email subject",
            "source_system": "gmail",
            "source_id": "thread123",
            "payload": {},
        }
        result = render_link(evidence)
        assert result["can_render_link"] is True
        assert result["is_plain_text"] is False
        assert "Thread" in result["link_text"] or "View" in result["link_text"]

    def test_minutes_uses_payload_urls(self):
        """Minutes evidence uses payload URLs for additional links."""
        evidence = {
            "version": "v1",
            "kind": "minutes_analysis",
            "url": None,
            "display_text": "Team sync",
            "source_system": "minutes",
            "source_id": "meet_123",
            "payload": {
                "recording_url": "https://drive.google.com/recording",
                "transcript_url": "https://docs.google.com/transcript",
            },
        }
        result = render_link(evidence)
        assert result["is_plain_text"] is True
        assert len(result["additional_links"]) == 2

        urls = [link["url"] for link in result["additional_links"]]
        assert "https://drive.google.com/recording" in urls
        assert "https://docs.google.com/transcript" in urls

    def test_minutes_no_payload_urls(self):
        """Minutes evidence with no payload URLs returns empty additional_links."""
        evidence = {
            "version": "v1",
            "kind": "minutes_analysis",
            "url": None,
            "display_text": "Quick call",
            "source_system": "minutes",
            "source_id": "meet_456",
            "payload": {},
        }
        result = render_link(evidence)
        assert result["additional_links"] == []

    def test_calendar_renders_link(self):
        """Calendar evidence renders clickable link."""
        evidence = {
            "version": "v1",
            "kind": "calendar_event",
            "url": "https://calendar.google.com/calendar/r/event?eid=abc",
            "display_text": "Project kickoff",
            "source_system": "calendar",
            "source_id": "event_abc",
            "payload": {},
        }
        result = render_link(evidence)
        assert result["can_render_link"] is True
        assert result["is_plain_text"] is False

    def test_gchat_renders_link(self):
        """Google Chat evidence renders clickable link."""
        evidence = {
            "version": "v1",
            "kind": "gchat_message",
            "url": "https://chat.google.com/dm/abc123",
            "display_text": "Chat message",
            "source_system": "gchat",
            "source_id": "msg_123",
            "payload": {},
        }
        result = render_link(evidence)
        assert result["can_render_link"] is True
        assert "Chat" in result["link_text"]

    def test_unknown_source_no_link(self):
        """Unknown source system does not render link."""
        evidence = {
            "version": "v1",
            "kind": "invoice",
            "url": "https://unknown.com/123",
            "display_text": "Test",
            "source_system": "unknown_system",
            "source_id": "123",
            "payload": {
                "number": "1",
                "amount": 100,
                "currency": "USD",
                "status": "sent",
            },
        }
        result = render_link(evidence)
        assert result["can_render_link"] is False


class TestEvidenceFactories:
    """Test cases for evidence factory functions."""

    def test_create_invoice_evidence_structure(self):
        """create_invoice_evidence returns valid envelope."""
        evidence = create_invoice_evidence(
            invoice_number="INV-2026-001",
            amount=50000,
            currency="AED",
            due_date="2026-01-15",
            days_overdue=23,
            status="overdue",
            source_id="xero_inv_abc",
        )

        # Validate structure
        valid, error = validate_evidence(evidence)
        assert valid is True, f"Validation failed: {error}"

        # Check required fields
        assert evidence["version"] == "v1"
        assert evidence["kind"] == "invoice"
        assert evidence["url"] is None
        assert evidence["source_system"] == "xero"
        assert evidence["source_id"] == "xero_inv_abc"

        # Check payload
        assert evidence["payload"]["number"] == "INV-2026-001"
        assert evidence["payload"]["amount"] == 50000
        assert evidence["payload"]["days_overdue"] == 23

        # Check display_text contains key info
        assert "INV-2026-001" in evidence["display_text"]
        assert "50,000" in evidence["display_text"]

    def test_create_asana_task_evidence_structure(self):
        """create_asana_task_evidence returns valid envelope with URL."""
        evidence = create_asana_task_evidence(
            task_gid="1234567890",
            name="Complete brand guidelines",
            assignee="Jane Doe",
            due_date="2026-02-01",
            days_overdue=7,
            project_name="Brand Refresh",
            project_gid="9876543210",
        )

        valid, error = validate_evidence(evidence)
        assert valid is True, f"Validation failed: {error}"

        assert evidence["kind"] == "asana_task"
        assert evidence["source_system"] == "asana"
        assert "asana.com" in evidence["url"]
        assert "9876543210" in evidence["url"]  # project_gid in URL
        assert "1234567890" in evidence["url"]  # task_gid in URL

    def test_create_gmail_evidence_structure(self):
        """create_gmail_evidence returns valid envelope."""
        evidence = create_gmail_evidence(
            thread_id="thread_abc123",
            subject="Re: Contract review",
            sender="client@example.com",
            snippet="Please review the attached...",
            received_at="2026-02-07T10:30:00.000Z",
        )

        valid, error = validate_evidence(evidence)
        assert valid is True, f"Validation failed: {error}"

        assert evidence["kind"] == "gmail_thread"
        assert "mail.google.com" in evidence["url"]
        assert evidence["payload"]["sender"] == "client@example.com"

    def test_create_calendar_evidence_structure(self):
        """create_calendar_evidence returns valid envelope."""
        evidence = create_calendar_evidence(
            event_id="event_xyz",
            title="Weekly sync",
            start_time="2026-02-08T10:00:00.000Z",
            cancelled=False,
            rescheduled=False,
        )

        valid, error = validate_evidence(evidence)
        assert valid is True, f"Validation failed: {error}"

        assert evidence["kind"] == "calendar_event"
        assert "calendar.google.com" in evidence["url"]


class TestLinkableSourcesConstants:
    """Test that constants match spec 6.16."""

    def test_linkable_sources(self):
        """LINKABLE_SOURCES contains spec-defined sources."""
        expected = {"asana", "gmail", "gchat", "calendar"}
        assert expected == LINKABLE_SOURCES

    def test_no_link_sources(self):
        """NO_LINK_SOURCES contains Xero."""
        assert "xero" in NO_LINK_SOURCES

    def test_valid_evidence_kinds(self):
        """VALID_EVIDENCE_KINDS contains all spec-defined kinds."""
        expected = {
            "invoice",
            "asana_task",
            "gmail_thread",
            "calendar_event",
            "minutes_analysis",
            "gchat_message",
            "xero_contact",
        }
        assert expected == VALID_EVIDENCE_KINDS
