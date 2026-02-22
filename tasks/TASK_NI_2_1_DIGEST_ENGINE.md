# NI-2.1: Digest Engine

## Objective
Build a DigestEngine that collects queued notifications and generates batched summaries on schedule (hourly/daily/weekly), grouped by category with severity ordering.

## Implementation

### DigestEngine (`lib/notifications/digest.py`)
```python
class DigestEngine:
    def generate_digest(self, user_id: str, bucket: str) -> Digest:
        """Collect all undelivered items in this bucket, group, and format."""
        items = self.collect_pending(user_id, bucket)
        grouped = self.group_by_category(items)  # proposals, issues, watchers, patterns
        sorted_groups = self.sort_by_severity(grouped)
        return Digest(
            user_id=user_id,
            bucket=bucket,
            groups=sorted_groups,
            total_count=len(items),
            critical_count=sum(1 for i in items if i.severity == 'critical'),
            generated_at=utc_now(),
        )

    def render_chat(self, digest: Digest) -> str:
        """Render as Google Chat Card v2 message."""

    def render_html(self, digest: Digest) -> str:
        """Render as HTML email body."""

    def deliver_and_mark(self, digest: Digest, channel: str):
        """Deliver digest and mark all items as delivered."""
```

### Scheduling
Wire into daemon cron:
- Hourly digest: runs at :00 for users with `digest_frequency='hourly'`
- Daily digest: runs at 09:00 user timezone
- Weekly digest: runs Monday 09:00 user timezone

### Digest Format
```
📊 Daily Intelligence Digest — Feb 22, 2026

🔴 Critical (2)
  • [Issue] Client X invoice 45 days overdue — AED 52K
  • [Proposal] Reallocate Project Y to prevent deadline miss

🟡 High (5)
  • [Watcher] 3 new scope change signals on Project Z
  • ...

🟢 Medium (12)
  • [Pattern] Consistent late delivery on Lane 3 (4th week)
  • ...

Total: 19 items | View all → [link]
```

## Validation
- [ ] Digest collects all undelivered items for the correct bucket
- [ ] Items grouped by category and sorted by severity
- [ ] Chat format renders readable Card v2 message
- [ ] HTML format renders with proper styling
- [ ] Items marked as delivered after digest sent
- [ ] Empty digest (no pending items) is suppressed, not sent
- [ ] Cron scheduling fires at correct times per timezone

## Files Created
- `lib/notifications/digest.py`
- `tests/test_digest_engine.py`

## Files Modified
- Daemon cron configuration

## Estimated Effort
Medium — ~500 lines
