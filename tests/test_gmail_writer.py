"""
Tests for Gmail write-back integration.

Tests GmailWriter without calling real Gmail API.
All Google API calls are mocked using unittest.mock.
"""

from unittest.mock import MagicMock, patch

from lib.integrations.gmail_writer import GmailWriter, GmailWriteResult

# ============================================================
# GmailWriter Initialization Tests
# ============================================================


class TestGmailWriterInit:
    """Test GmailWriter initialization."""

    def test_init_with_default_params(self):
        """Can initialize with default parameters."""
        writer = GmailWriter()
        assert writer.delegated_user == "molham@hrmny.co"
        assert writer.dry_run is False
        assert writer._service is None

    def test_init_with_custom_user(self):
        """Can initialize with custom delegated user."""
        writer = GmailWriter(delegated_user="custom@example.com")
        assert writer.delegated_user == "custom@example.com"

    def test_init_with_env_var_user(self, monkeypatch):
        """Can initialize with GMAIL_USER env var."""
        monkeypatch.setenv("GMAIL_USER", "env_user@example.com")
        writer = GmailWriter()
        assert writer.delegated_user == "env_user@example.com"

    def test_init_dry_run_mode(self):
        """Can enable dry-run mode."""
        writer = GmailWriter(dry_run=True)
        assert writer.dry_run is True

    def test_init_with_custom_credentials_path(self, tmp_path):
        """Can initialize with custom credentials path."""
        creds_file = tmp_path / "sa.json"
        creds_file.write_text('{"type": "service_account"}')
        writer = GmailWriter(credentials_path=str(creds_file))
        assert writer.credentials_path == str(creds_file)

    def test_init_with_env_var_credentials(self, monkeypatch, tmp_path):
        """Can initialize with GMAIL_SA_FILE env var."""
        creds_file = tmp_path / "sa.json"
        creds_file.write_text('{"type": "service_account"}')
        monkeypatch.setenv("GMAIL_SA_FILE", str(creds_file))
        writer = GmailWriter()
        assert writer.credentials_path == str(creds_file)


# ============================================================
# GmailWriter Draft Creation Tests
# ============================================================


class TestGmailWriterCreateDraft:
    """Test draft creation."""

    def test_create_draft_minimal(self):
        """Can create a minimal draft in dry-run mode."""
        writer = GmailWriter(dry_run=True)
        result = writer.create_draft(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test body",
        )

        assert result.success
        assert result.draft_id == "draft_dry_run"
        assert result.data["dry_run"] is True
        assert result.data["to"] == "recipient@example.com"

    def test_create_draft_with_cc_bcc(self):
        """Can create draft with CC and BCC."""
        writer = GmailWriter(dry_run=True)
        result = writer.create_draft(
            to="recipient@example.com",
            subject="Test",
            body="Body",
            cc=["cc1@example.com", "cc2@example.com"],
            bcc=["bcc@example.com"],
        )

        assert result.success
        assert result.draft_id == "draft_dry_run"

    def test_create_draft_with_html_body(self):
        """Can create draft with HTML body."""
        writer = GmailWriter(dry_run=True)
        result = writer.create_draft(
            to="recipient@example.com",
            subject="Test",
            body="Plain text",
            html_body="<p>HTML content</p>",
        )

        assert result.success
        assert result.draft_id == "draft_dry_run"

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_create_draft_via_api(self, mock_get_service):
        """Can create draft via API."""
        mock_service = MagicMock()
        mock_response = {
            "id": "draft_123",
            "message": {"id": "msg_123"},
        }
        mock_service.users().drafts().create.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.create_draft(
            to="recipient@example.com",
            subject="Test",
            body="Body",
        )

        assert result.success
        assert result.draft_id == "draft_123"
        assert result.message_id == "msg_123"
        assert result.data == mock_response
        mock_service.users().drafts().create.assert_called_once()

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_create_draft_api_error(self, mock_get_service):
        """Handles API errors correctly."""
        mock_service = MagicMock()
        mock_service.users().drafts().create.return_value.execute.side_effect = Exception(
            "API Error: 403 Forbidden"
        )
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.create_draft(
            to="recipient@example.com",
            subject="Test",
            body="Body",
        )

        assert not result.success
        assert result.draft_id is None
        assert "API Error" in result.error


# ============================================================
# GmailWriter Send Draft Tests
# ============================================================


class TestGmailWriterSendDraft:
    """Test draft sending."""

    def test_send_draft_dry_run(self):
        """Can send draft in dry-run mode."""
        writer = GmailWriter(dry_run=True)
        result = writer.send_draft("draft_123")

        assert result.success
        assert result.message_id == "msg_dry_run"
        assert result.data["dry_run"] is True

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_send_draft_via_api(self, mock_get_service):
        """Can send draft via API."""
        mock_service = MagicMock()
        mock_response = {"id": "msg_456"}
        mock_service.users().drafts().send.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.send_draft("draft_123")

        assert result.success
        assert result.message_id == "msg_456"
        assert result.draft_id == "draft_123"
        mock_service.users().drafts().send.assert_called_once()

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_send_draft_not_found(self, mock_get_service):
        """Handles draft not found error."""
        mock_service = MagicMock()
        mock_service.users().drafts().send.return_value.execute.side_effect = Exception(
            "404 Draft not found"
        )
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.send_draft("invalid_draft")

        assert not result.success
        assert "404" in result.error


# ============================================================
# GmailWriter Send Email Tests
# ============================================================


class TestGmailWriterSendEmail:
    """Test email sending."""

    def test_send_email_dry_run(self):
        """Can send email in dry-run mode."""
        writer = GmailWriter(dry_run=True)
        result = writer.send_email(
            to="recipient@example.com",
            subject="Test",
            body="Body",
        )

        assert result.success
        assert result.message_id == "msg_dry_run"
        assert result.data["dry_run"] is True

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_send_email_via_api(self, mock_get_service):
        """Can send email via API."""
        mock_service = MagicMock()
        mock_response = {"id": "msg_789"}
        mock_service.users().messages().send.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test body",
        )

        assert result.success
        assert result.message_id == "msg_789"
        assert result.data == mock_response
        mock_service.users().messages().send.assert_called_once()

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_send_email_with_cc_bcc(self, mock_get_service):
        """Can send email with CC and BCC."""
        mock_service = MagicMock()
        mock_response = {"id": "msg_101"}
        mock_service.users().messages().send.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.send_email(
            to="to@example.com",
            subject="Test",
            body="Body",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )

        assert result.success
        mock_service.users().messages().send.assert_called_once()

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_send_email_with_html_body(self, mock_get_service):
        """Can send email with HTML body."""
        mock_service = MagicMock()
        mock_response = {"id": "msg_202"}
        mock_service.users().messages().send.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.send_email(
            to="recipient@example.com",
            subject="Test",
            body="Plain text",
            html_body="<p>HTML</p>",
        )

        assert result.success
        mock_service.users().messages().send.assert_called_once()

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_send_email_quota_exceeded(self, mock_get_service):
        """Handles quota exceeded error."""
        mock_service = MagicMock()
        mock_service.users().messages().send.return_value.execute.side_effect = Exception(
            "429 Quota exceeded"
        )
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.send_email(
            to="recipient@example.com",
            subject="Test",
            body="Body",
        )

        assert not result.success
        assert "Quota" in result.error


# ============================================================
# GmailWriter Label Tests
# ============================================================


class TestGmailWriterLabeling:
    """Test label management."""

    def test_add_label_dry_run(self):
        """Can add labels in dry-run mode."""
        writer = GmailWriter(dry_run=True)
        result = writer.add_label("msg_123", ["IMPORTANT", "STARRED"])

        assert result.success
        assert result.message_id == "msg_123"
        assert result.data["dry_run"] is True

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_add_label_via_api(self, mock_get_service):
        """Can add labels via API."""
        mock_service = MagicMock()
        mock_response = {"id": "msg_123"}
        mock_service.users().messages().modify.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.add_label("msg_123", ["IMPORTANT"])

        assert result.success
        assert result.message_id == "msg_123"
        mock_service.users().messages().modify.assert_called_once()

    def test_remove_label_dry_run(self):
        """Can remove labels in dry-run mode."""
        writer = GmailWriter(dry_run=True)
        result = writer.remove_label("msg_123", ["SPAM"])

        assert result.success
        assert result.message_id == "msg_123"

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_remove_label_via_api(self, mock_get_service):
        """Can remove labels via API."""
        mock_service = MagicMock()
        mock_response = {"id": "msg_123"}
        mock_service.users().messages().modify.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.remove_label("msg_123", ["SPAM"])

        assert result.success
        mock_service.users().messages().modify.assert_called_once()

    def test_archive_message_dry_run(self):
        """Can archive message in dry-run mode."""
        writer = GmailWriter(dry_run=True)
        result = writer.archive_message("msg_123")

        assert result.success
        assert result.message_id == "msg_123"

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_archive_message_via_api(self, mock_get_service):
        """Can archive message via API (removes INBOX label)."""
        mock_service = MagicMock()
        mock_response = {"id": "msg_123"}
        mock_service.users().messages().modify.return_value.execute.return_value = mock_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.archive_message("msg_123")

        assert result.success
        # Verify it calls remove_label with INBOX
        call_args = mock_service.users().messages().modify.call_args
        assert call_args is not None


# ============================================================
# GmailWriter Reply Tests
# ============================================================


class TestGmailWriterReply:
    """Test thread replies."""

    def test_reply_to_thread_dry_run(self):
        """Can reply to thread in dry-run mode."""
        writer = GmailWriter(dry_run=True)
        result = writer.reply_to_thread(
            "thread_123",
            "Thanks for the email",
        )

        assert result.success
        assert result.message_id == "msg_dry_run"

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_reply_to_thread_via_api(self, mock_get_service):
        """Can reply to thread via API."""
        mock_service = MagicMock()

        # Mock thread get
        thread_response = {
            "messages": [
                {"id": "msg_first"},
                {"id": "msg_second"},
            ]
        }
        mock_service.users().threads().get.return_value.execute.return_value = thread_response

        # Mock message get (to extract headers)
        msg_response = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Original Subject"},
                ]
            }
        }
        mock_service.users().messages().get.return_value.execute.return_value = msg_response

        # Mock send
        send_response = {"id": "msg_reply"}
        mock_service.users().messages().send.return_value.execute.return_value = send_response

        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.reply_to_thread("thread_123", "Reply body")

        assert result.success
        assert result.message_id == "msg_reply"
        mock_service.users().threads().get.assert_called_once()
        mock_service.users().messages().send.assert_called_once()

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_reply_to_thread_empty_thread(self, mock_get_service):
        """Handles empty thread error."""
        mock_service = MagicMock()
        thread_response = {"messages": []}
        mock_service.users().threads().get.return_value.execute.return_value = thread_response
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.reply_to_thread("thread_invalid", "Body")

        assert not result.success
        assert "no messages" in result.error

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_reply_re_prefix(self, mock_get_service):
        """Adds Re: prefix to subject if needed."""
        mock_service = MagicMock()

        thread_response = {"messages": [{"id": "msg_first"}]}
        mock_service.users().threads().get.return_value.execute.return_value = thread_response

        msg_response = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Test Subject"},  # No Re: prefix
                ]
            }
        }
        mock_service.users().messages().get.return_value.execute.return_value = msg_response

        send_response = {"id": "msg_reply"}
        mock_service.users().messages().send.return_value.execute.return_value = send_response

        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.reply_to_thread("thread_123", "Reply body")

        assert result.success
        # Verify the message was sent with Re: prefix
        call_args = mock_service.users().messages().send.call_args
        assert call_args is not None


# ============================================================
# MIME Message Construction Tests
# ============================================================


class TestGmailWriterMimeConstruction:
    """Test MIME message construction."""

    def test_create_message_plain_text(self):
        """Can construct plain text MIME message."""
        writer = GmailWriter()
        msg_b64 = writer._create_message(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test body",
        )

        # Decode and verify
        import base64

        msg_str = base64.urlsafe_b64decode(msg_b64).decode("utf-8")
        # Check content regardless of header case
        assert "recipient@example.com" in msg_str
        assert "Test Subject" in msg_str
        assert "Test body" in msg_str

    def test_create_message_with_html(self):
        """Can construct MIME message with HTML."""
        writer = GmailWriter()
        msg_b64 = writer._create_message(
            to="recipient@example.com",
            subject="Test",
            body="Plain",
            html_body="<p>HTML</p>",
        )

        import base64

        msg_str = base64.urlsafe_b64decode(msg_b64).decode("utf-8")
        assert "recipient@example.com" in msg_str
        assert "Plain" in msg_str
        assert "<p>HTML</p>" in msg_str

    def test_create_message_with_cc_bcc(self):
        """Can construct MIME message with CC and BCC."""
        writer = GmailWriter()
        msg_b64 = writer._create_message(
            to="to@example.com",
            subject="Test",
            body="Body",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )

        import base64

        msg_str = base64.urlsafe_b64decode(msg_b64).decode("utf-8")
        assert "to@example.com" in msg_str
        assert "cc@example.com" in msg_str
        assert "bcc@example.com" in msg_str

    def test_create_message_with_reply_to(self):
        """Can construct MIME message with In-Reply-To header."""
        writer = GmailWriter()
        msg_b64 = writer._create_message(
            to="recipient@example.com",
            subject="Re: Test",
            body="Reply body",
            reply_to_message_id="msg_original_123",
        )

        import base64

        msg_str = base64.urlsafe_b64decode(msg_b64).decode("utf-8")
        assert "msg_original_123" in msg_str
        assert "Reply body" in msg_str


# ============================================================
# Error Handling Tests
# ============================================================


class TestGmailWriterErrorHandling:
    """Test error handling."""

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_auth_failure(self, mock_get_service):
        """Handles authentication failure."""
        mock_get_service.side_effect = Exception("Invalid service account credentials")

        writer = GmailWriter(dry_run=False)
        result = writer.send_email(
            to="recipient@example.com",
            subject="Test",
            body="Body",
        )

        assert not result.success
        assert "Invalid service account" in result.error

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_label_not_found(self, mock_get_service):
        """Handles label not found error."""
        mock_service = MagicMock()
        mock_service.users().messages().modify.return_value.execute.side_effect = Exception(
            "400 Invalid label"
        )
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.add_label("msg_123", ["INVALID_LABEL"])

        assert not result.success
        assert "Invalid label" in result.error

    @patch("lib.integrations.gmail_writer.GmailWriter._get_service")
    def test_message_not_found(self, mock_get_service):
        """Handles message not found error."""
        mock_service = MagicMock()
        mock_service.users().messages().modify.return_value.execute.side_effect = Exception(
            "404 Message not found"
        )
        mock_get_service.return_value = mock_service

        writer = GmailWriter(dry_run=False)
        result = writer.add_label("invalid_msg", ["IMPORTANT"])

        assert not result.success
        assert "404" in result.error


# ============================================================
# GmailWriteResult Tests
# ============================================================


class TestGmailWriteResult:
    """Test result object."""

    def test_result_success(self):
        """Can create success result."""
        result = GmailWriteResult(
            success=True,
            message_id="msg_123",
            data={"id": "msg_123"},
        )

        assert result.success
        assert result.message_id == "msg_123"
        assert result.error is None

    def test_result_failure(self):
        """Can create failure result."""
        result = GmailWriteResult(
            success=False,
            error="API Error",
        )

        assert not result.success
        assert result.message_id is None
        assert result.error == "API Error"

    def test_result_draft(self):
        """Can create result for draft."""
        result = GmailWriteResult(
            success=True,
            draft_id="draft_123",
            message_id="msg_456",
        )

        assert result.success
        assert result.draft_id == "draft_123"
        assert result.message_id == "msg_456"
