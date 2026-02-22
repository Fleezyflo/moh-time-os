# NI-3.1: Email Digest Channel

## Objective
Build an EmailDigestChannel that sends rich HTML digest emails using Brief 15's GmailWriter. Branded template with severity color coding, action links, and unsubscribe.

## Implementation

### HTML Email Template
Responsive HTML email template (inline CSS for email client compatibility):
- Header: MOH Time OS logo + digest period
- Sections per category with severity color bars
- Each item: title, one-line summary, direct link to item in SPA
- Footer: unsubscribe link, notification preferences link
- Mobile-responsive: single column, large tap targets

### EmailDigestChannel (`lib/notifications/email_channel.py`)
```python
class EmailDigestChannel:
    def __init__(self, gmail_writer: GmailWriter):
        self.gmail = gmail_writer

    def send_digest(self, user_email: str, digest: Digest):
        html = self.render_template(digest)
        subject = f"[TimeOS] {digest.bucket.title()} Digest — {digest.total_count} items"
        self.gmail.create_and_send(
            to=user_email,
            subject=subject,
            html_body=html,
        )
```

### Unsubscribe Flow
- Unsubscribe link in footer generates a signed token URL
- Hitting the URL sets `enabled=False` on notification_preferences
- One-click unsubscribe header (RFC 8058) for email client support

## Validation
- [ ] HTML email renders correctly in Gmail (test with actual send)
- [ ] Severity colors display correctly (inline CSS, not classes)
- [ ] Links to SPA items are correct and functional
- [ ] Unsubscribe link works (one-click disable)
- [ ] Empty digests are not sent
- [ ] Subject line includes item count
- [ ] Mobile-responsive: readable on 375px viewport

## Files Created
- `lib/notifications/email_channel.py`
- `lib/notifications/templates/digest.html`
- `tests/test_email_digest.py`

## Estimated Effort
Medium — ~300 lines (template + channel + unsubscribe)
