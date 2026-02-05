# 11_CHANGELOG_AND_NEXT_STEPS.md — Changelog and Recommended Next Steps

> Phase I Deliverable | Generated: 2026-02-04

---

## Changelog

### v1.0.0 (2026-02-04)

**Initial Data Atlas Release**

- Created complete schema documentation (36 tables + 1 view)
- Documented all 5 active collectors (Tasks, Calendar, Gmail, Asana, Xero)
- Cataloged 80+ fields with semantic types and usage patterns
- Documented 10 gates and 6 scoring models
- Created 15+ query recipes for common UI patterns
- Mapped 60+ UI surface opportunities across 6 domains
- Documented all known data gaps and confidence constraints
- Provided sample data pack for UI testing

---

## Data Quality Summary

| Metric | Current Value | Target |
|--------|---------------|--------|
| Task→Project linkage | 98.9% | ≥95% ✅ |
| Task→Client linkage | 87.1% | ≥80% ✅ |
| Comm→Client linkage | 12.3% | ≥50% ❌ |
| Invoices linked | 100% | 100% ✅ |
| Commitments extracted | 3 | ≥50 ❌ |
| Team members registered | 31 | N/A ✅ |
| Client identities | 25 | ≥50 ⚠️ |

---

## Recommended Next Steps

### Immediate (High Impact, Low Effort)

1. **Add more client_identities**
   - Mine existing communications for new domain patterns
   - Manually add known client domains
   - Impact: Improves comm→client linkage from 12% to 30-50%

2. **Increase Asana project sync limit**
   - Current: 15 projects
   - Recommendation: 50 or unlimited
   - Impact: Complete task coverage

3. **Fix commitment extraction**
   - Review extraction patterns
   - Run on historical comms
   - Impact: Enables comms domain features

### Short-term (1-2 weeks)

4. **Add response detection to Gmail collector**
   - Detect "RE:" patterns
   - Track thread depth
   - Impact: Enables response SLA tracking

5. **Build project enrollment flow**
   - UI to link projects → brands → clients
   - Impact: Improves delivery chain integrity

6. **Add client contact sync**
   - Google Contacts or manual entry
   - Impact: Enables people → client mapping

### Medium-term (1 month)

7. **Time tracking integration**
   - Options: Toggl, Harvest, Clockify, manual
   - Impact: Enables capacity domain (currently theoretical)

8. **Slack/Teams integration**
   - Additional comms source
   - Impact: Better communication coverage

9. **Meeting notes extraction**
   - Transcription or manual input
   - Impact: Better context for client interactions

---

## Known Limitations

### Capacity Domain

The capacity domain is currently **theoretical only**. All capacity metrics are based on:
- Task duration estimates (default 60 min)
- No actual time tracking
- No PTO/vacation data
- No meeting load from team calendars (unless team_calendar enabled)

**Recommendation:** Either:
- Hide capacity features until time tracking exists, OR
- Label all capacity data as "Estimated" with prominent disclaimer

### Commitment Extraction

Only 3 commitments extracted to date. The extraction system:
- Requires body_text (only ~50% have it)
- Pattern matching may miss commitments
- No manual override mechanism

**Recommendation:** Mark commitment features as "Beta" or "Experimental"

### Communication Linkage

88% of communications are unlinked to clients because:
- Only 25 client_identities exist
- Subject-line matching limited to exact client names
- No manual linking UI

**Recommendation:** Build "Link this email to client" UI action

---

## Schema Evolution Notes

### Tables Not Actively Used

| Table | Status | Notes |
|-------|--------|-------|
| time_blocks | Empty | Scheduling engine not active |
| time_debt | Empty | Requires time tracking |
| meet_attendance | Empty | Meet integration not active |
| item_history | Empty | Change tracking not implemented |
| patterns | Empty | Pattern detection not active |
| insights | Empty | Insight generation not active |
| feedback | Empty | Feedback collection not implemented |
| pending_actions | Empty | Governance in observe mode |

### Deprecated Fields

These fields exist but are rarely populated:
- `tasks.effort_min`, `tasks.effort_max` (use duration_min)
- `tasks.waiting_for` (not populated)
- `tasks.delegated_by`, `tasks.delegated_at` (delegation not active)
- `communications.expected_response_by` (SLA not implemented)
- `communications.requires_response` (detection unreliable)

---

## UI Design Recommendations

### Must-Have Confidence Indicators

Every UI surface should show:
1. **Data freshness** - "Last synced X ago"
2. **Coverage** - "Based on X% of data"
3. **Gate status** - Visual indicator for blocked/degraded

### Safe to Display (High Confidence)

- AR totals and aging (Xero is authoritative)
- Task counts and status distribution
- Project completion percentages
- Calendar events
- Sync state

### Display with Caution (Medium Confidence)

- Client health scores (depends on linkage)
- Slip risk scores (depends on deadline accuracy)
- Communication metrics (limited linkage)

### Avoid Until Fixed (Low Confidence)

- Capacity/utilization metrics (no time tracking)
- SLA breach counts (detection broken)
- Commitment counts (extraction sparse)

---

## Validation Checklist

Before using this atlas for UI design, verify:

- [ ] All 12 files present in `docs/ui_atlas/`
- [ ] JSON files parse correctly
- [ ] Sample data relationships are consistent
- [ ] Query recipes execute without error
- [ ] Gate queries return expected results

---

*End of 11_CHANGELOG_AND_NEXT_STEPS.md*
