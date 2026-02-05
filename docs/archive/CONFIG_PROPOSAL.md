# CONFIG_PROPOSAL.md

**Generated:** 2026-02-01T02:01:00+04:00

## 1. Proposed Lanes Taxonomy
Based on 14 days of data, the following work categories (lanes) are recommended with signal counts for tuning:

| Lane       | Signal Count |
|------------|--------------|
| Finance    | 53           |
| People     | 31           |
| Creative   | 10           |
| Sales      | 7            |
| Personal   | 3            |
| Operations | 2            |

*Recommendation:* Focus on the top four lanes (Finance, People, Creative, Sales) initially, then expand to Personal/Operations as volume grows.

## 2. Priority Tier Thresholds
- **High priority:** ~29 threads (~15%).
- **Medium priority:** ~3 threads (~2%).
- **Low priority:** ~168 threads (~83%).

*Recommendation:* Classify as high any sender in the top-10 high_senders list; medium for domains in the top-15 by count; all others default to low.

## 3. Scheduling (Deep Work) Windows
**Meeting density by hour:** 10am, 11am, 12pm, 2pm, 4pm, 5pm, 7pm.

**Free hours:** 9am, 1pm, 3pm, 6pm.

*Recommendation:* Block recurring deep-entry focus windows at 9:00, 13:00, 15:00, and 18:00 daily.

## 4. Detected Project Enrollment Signals
Recurring patterns suggesting active projects:

- HRMNY (8 signals)
- PEOPLE (2 signals)
- FIVE GUYS (2 signals)
- GMG (2 signals)
- MP (2 signals)

*Recommendation:* Kick off project-specific lanes or filters for these five entities to track incoming work against discrete projects.

---

*End of CONFIG_PROPOSAL.md*
