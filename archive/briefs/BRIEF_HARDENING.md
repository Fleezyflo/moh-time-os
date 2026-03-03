# BRIEF: Hardening & Production Readiness

## Purpose

This brief addresses every gap, risk, and compromise made during Briefs 1-3. The goal is to transform the working prototype into a production-ready system.

**Entry State:** Working intelligence system with known gaps
**Exit State:** Production-ready system with monitoring, polish, and safeguards

---

## Phase 0: Data Infrastructure

### Why First
You can't show trends without history. You can't manage disk without cleanup. Fix the data foundation before anything else.

### Task 0.1: Score History Table

**Problem:** Scores are point-in-time. We can't answer "did this client improve over the last month?"

**Solution:**
```sql
CREATE TABLE score_history (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,      -- 'client', 'project', 'person', 'portfolio'
    entity_id TEXT NOT NULL,
    composite_score REAL NOT NULL,
    dimensions_json TEXT,           -- Full dimension breakdown
    recorded_at TEXT NOT NULL,      -- ISO timestamp
    recorded_date TEXT NOT NULL,    -- YYYY-MM-DD for daily grouping
    
    UNIQUE(entity_type, entity_id, recorded_date)  -- One per entity per day
);

CREATE INDEX idx_score_history_lookup 
ON score_history(entity_type, entity_id, recorded_date);
```

**Implementation:**
1. Create table with migration
2. Add `record_score()` function to scorecard.py
3. Call after each scoring run
4. Add `get_score_trend(entity, days)` query
5. Add `/scores/{type}/{id}/history` endpoint
6. Add trend chart to entity intel pages

**Acceptance:**
- [ ] Table created
- [ ] Scores recorded daily (not per-run)
- [ ] Trend query returns 30-day history
- [ ] UI shows trend chart

### Task 0.2: Snapshot DB Migration

**Problem:** Snapshots are JSON files in `data/snapshots/`. No cleanup, no querying.

**Solution:**
```sql
CREATE TABLE snapshot_store (
    id INTEGER PRIMARY KEY,
    snapshot_id TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    signal_count INTEGER,
    proposal_count INTEGER,
    portfolio_score REAL,
    critical_count INTEGER,
    pattern_count INTEGER,
    full_json TEXT,                 -- Complete snapshot for replay
    
    UNIQUE(snapshot_id)
);

CREATE INDEX idx_snapshot_created ON snapshot_store(created_at);
```

**Implementation:**
1. Create table
2. Migrate `changes.py` to use DB instead of files
3. Add retention policy (keep 30 days)
4. Add `/snapshots` endpoint for history
5. Delete old `data/snapshots/` files

**Acceptance:**
- [ ] Table created
- [ ] change detection uses DB
- [ ] Old snapshots queryable
- [ ] File-based storage removed

---

## Phase 1: Performance & Calibration

### Why Second
Users won't wait 47 seconds. False alarms erode trust. Fix before polish.

### Task 1.1: Pipeline Optimization

**Problem:** Full pipeline takes ~47 seconds. Too slow for interactive use.

**Target:** <10 seconds for standard run, <3 seconds for cached.

**Approach:**
1. **Profile first:** Identify which stages are slowest
2. **Caching:** Don't re-score unchanged entities
3. **Sampling:** Portfolio patterns can sample, not scan all
4. **Incremental:** Only re-detect signals for changed data
5. **Parallel:** Score clients in parallel (if safe)

**Implementation:**
```python
# Add to engine.py
CACHE_TTL = 300  # 5 minutes

def generate_intelligence_snapshot(use_cache=True, force_full=False):
    if use_cache and not force_full:
        cached = get_cached_snapshot()
        if cached and cached.age_seconds < CACHE_TTL:
            return cached
    
    # Run pipeline with incremental detection
    ...
```

**Acceptance:**
- [ ] Profiling report generated
- [ ] Caching implemented
- [ ] <10s for full run
- [ ] <3s for cached run
- [ ] No behavioral changes (same output)

### Task 1.2: Signal Threshold Tuning

**Problem:** Thresholds are guesses. "5 overdue tasks = warning" may be too sensitive or not enough.

**Approach:**
1. Run current signals for 2 weeks
2. Export all detections to CSV
3. Review with Moh: which are real issues vs noise?
4. Adjust thresholds based on feedback
5. Add threshold config file (not hardcoded)

**Implementation:**
```python
# lib/intelligence/thresholds.yaml
signals:
  sig_client_overdue_tasks:
    warning_threshold: 5
    critical_threshold: 15
  sig_person_overloaded:
    warning_threshold: 20
    critical_threshold: 35
```

**Acceptance:**
- [ ] 2-week signal export generated
- [ ] Thresholds reviewed with Moh
- [ ] Config file created
- [ ] Signals reload thresholds from config
- [ ] Documentation of each threshold's meaning

---

## Phase 2: UI Polish

### Why Third
Functional ≠ usable. Users need clear feedback at every state.

### Task 2.1: UI Error States

**Problem:** Errors show raw messages or nothing.

**Solution:**
- Friendly error messages with context
- Retry buttons that actually work
- Error boundaries that don't crash entire page
- Log errors for debugging

**Implementation:**
```tsx
// components/ErrorState.tsx
function ErrorState({ error, onRetry, context }) {
  return (
    <div className="error-container">
      <AlertIcon />
      <h3>Something went wrong</h3>
      <p>{friendlyMessage(error, context)}</p>
      <button onClick={onRetry}>Try Again</button>
      <details>
        <summary>Technical details</summary>
        <pre>{error.message}</pre>
      </details>
    </div>
  );
}
```

**Acceptance:**
- [ ] All pages have error boundaries
- [ ] All data fetches have error states
- [ ] Retry works without page refresh
- [ ] Errors logged to console

### Task 2.2: UI Loading States

**Problem:** Just a pulse animation. No skeleton that hints at content.

**Solution:**
- Skeleton loaders matching content shape
- Progressive loading (show what you have)
- Loading indicators for actions

**Implementation:**
```tsx
// components/SkeletonCard.tsx
function SkeletonCard({ lines = 3 }) {
  return (
    <div className="skeleton-card">
      <div className="skeleton-badge" />
      <div className="skeleton-title" />
      {Array(lines).fill(0).map((_, i) => (
        <div key={i} className="skeleton-line" style={{ width: `${80 - i * 15}%` }} />
      ))}
    </div>
  );
}
```

**Acceptance:**
- [ ] All lists have skeleton loaders
- [ ] Skeletons match real content shape
- [ ] No layout shift when content loads

### Task 2.3: UI Empty States

**Problem:** Empty lists show nothing or confusing messages.

**Solution:**
- Clear "nothing here" with helpful context
- Suggest actions when appropriate
- Different states: empty vs filtered-to-empty

**Implementation:**
```tsx
// components/EmptyState.tsx
function EmptyState({ type, hasFilters, onClearFilters }) {
  if (hasFilters) {
    return (
      <div className="empty-state">
        <FilterIcon />
        <h3>No matches</h3>
        <p>Try adjusting your filters</p>
        <button onClick={onClearFilters}>Clear filters</button>
      </div>
    );
  }
  
  return (
    <div className="empty-state">
      <CheckIcon />
      <h3>{emptyMessages[type].title}</h3>
      <p>{emptyMessages[type].description}</p>
    </div>
  );
}
```

**Acceptance:**
- [ ] All empty lists have empty states
- [ ] Filtered-empty vs truly-empty distinguished
- [ ] Clear filters action works

### Task 2.4: Mobile Responsiveness

**Problem:** Desktop-first. Cramped on mobile.

**Solution:**
- Touch-friendly tap targets (44px minimum)
- Stacked layouts on small screens
- Collapsible filters
- Bottom sheet for details instead of drawers

**Implementation:**
- Audit all components with mobile viewport
- Use Tailwind responsive prefixes consistently
- Test on actual devices

**Acceptance:**
- [ ] All pages usable on 375px width
- [ ] Tap targets ≥44px
- [ ] Filters collapse on mobile
- [ ] No horizontal scroll

---

## Phase 3: Operational Gaps

### Task 3.1: Notification Delivery

**Problem:** Notifications queue but never send.

**Solution (Slack first):**
```python
# lib/intelligence/delivery.py
def deliver_pending_notifications():
    pending = get_pending_notifications(limit=20)
    
    for notif in pending:
        try:
            if notif.priority == 'high':
                send_slack_message(
                    channel=SLACK_CHANNEL,
                    text=f"*{notif.title}*\n{notif.body}",
                    blocks=format_notification_blocks(notif)
                )
            mark_delivered(notif.id)
        except Exception as e:
            log_delivery_failure(notif.id, e)
            # Will retry next run
```

**Implementation:**
1. Add Slack webhook integration
2. Create delivery runner (cron-able)
3. Format notifications as Slack blocks
4. Add retry logic with backoff
5. Add delivery status to API

**Acceptance:**
- [ ] Slack webhook configured
- [ ] High-priority notifications → Slack
- [ ] Delivery status tracked
- [ ] Failed deliveries retry

### Task 3.2: Snapshot Cleanup

**Problem:** Snapshots accumulate forever.

**Solution:**
```python
def cleanup_old_snapshots(retention_days=30):
    cutoff = datetime.now() - timedelta(days=retention_days)
    
    conn.execute("""
        DELETE FROM snapshot_store 
        WHERE created_at < ?
    """, (cutoff.isoformat(),))
```

**Implementation:**
1. Add cleanup function
2. Add to cron schedule (daily)
3. Log what was deleted
4. Add retention_days config

**Acceptance:**
- [ ] Cleanup function implemented
- [ ] Runs automatically (cron)
- [ ] Keeps 30 days by default
- [ ] Logged for audit

---

## Phase 4: Test Coverage

### Task 4.1: UI Component Tests

**Problem:** No tests for React components.

**Solution:**
```tsx
// __tests__/SignalCard.test.tsx
describe('SignalCard', () => {
  it('renders critical signal with red styling', () => {
    render(<SignalCard signal={mockCriticalSignal} />);
    expect(screen.getByText('critical')).toHaveClass('text-red-400');
  });
  
  it('expands on click', async () => {
    render(<SignalCard signal={mockSignal} />);
    await userEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Recommended Action')).toBeVisible();
  });
});
```

**Implementation:**
1. Add Testing Library to project
2. Write tests for all shared components
3. Write tests for page components
4. Add to CI pipeline

**Acceptance:**
- [ ] Testing Library configured
- [ ] All 8 shared components tested
- [ ] All 7 pages have basic tests
- [ ] Tests run in CI

### Task 4.2: Integration Tests

**Problem:** No tests that verify API + UI work together.

**Solution:**
```python
# tests/test_integration.py
def test_full_pipeline_produces_valid_api_response():
    # Run pipeline
    snapshot = generate_intelligence_snapshot()
    
    # Call API
    response = client.get("/api/v2/intelligence/snapshot")
    
    # Verify structure matches
    assert response.json()["status"] == "ok"
    assert "signals" in response.json()["data"]
```

**Implementation:**
1. Add API integration tests
2. Add smoke tests that hit real endpoints
3. Add data validation tests

**Acceptance:**
- [ ] 10+ integration tests
- [ ] All critical paths covered
- [ ] Tests use fixture DB

---

## Phase 5: Production Readiness

### Task 5.1: API Authentication

**Problem:** Anyone can access intelligence APIs.

**Solution (Simple token first):**
```python
# Middleware
def verify_token(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token or token != os.environ.get("INTEL_API_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")
```

**Implementation:**
1. Add token verification middleware
2. Apply to intelligence routes
3. Document token setup
4. Add to deployment instructions

**Acceptance:**
- [ ] Token required for all intel endpoints
- [ ] 401 returned without token
- [ ] Token configurable via env
- [ ] Documentation updated

### Task 5.2: Production Checklist

**Final verification before production:**

- [ ] All tests pass
- [ ] Pipeline <10s
- [ ] UI works on mobile
- [ ] Notifications deliver
- [ ] Auth enabled
- [ ] Snapshots clean up
- [ ] Error states work
- [ ] Logging configured
- [ ] Metrics collected
- [ ] Backup strategy defined
- [ ] Rollback plan documented

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 0 | 0.1-0.2 | Data infrastructure |
| 1 | 1.1-1.2 | Performance + calibration |
| 2 | 2.1-2.4 | UI polish |
| 3 | 3.1-3.2 | Operational gaps |
| 4 | 4.1-4.2 | Test coverage |
| 5 | 5.1-5.2 | Production readiness |

**Total: 14 tasks**

Each task is designed to be completable in one session. No task should take more than 2 hours.

After this brief, the system will be:
- Historically aware (score trends)
- Fast (<10s pipeline)
- Calibrated (tuned thresholds)
- Polished (proper UI states)
- Operational (notifications work)
- Tested (UI + integration)
- Secured (auth required)
- Production-ready (checklist complete)
