# Brief 30: Adaptive Thresholds & Calibration Loop
> **Status:** DESIGNED | **Priority:** P2 | **Prefix:** AT

## Problem

thresholds.yaml contains static signal thresholds (e.g., overdue tasks ≥ 5, invoice aging ≥ 45 days). recalibrate.py has graduated severity rules but they're still manually defined. The system generates signals but doesn't learn from Molham's responses to them.

If a signal fires 100 times and gets dismissed 95 times, the threshold is too loose. If a signal fires and Molham immediately acts on it every time, it's well-calibrated. Today there's no feedback loop — the decision journal (Brief 22) RECORDS dismissals, but nothing feeds that back into thresholds.

## Dependencies

- **Requires:** Brief 22 (Strategic Memory) — decision journal must exist to know dismissal/action patterns
- **Requires:** Brief 28 (Intelligence Observability) IO-3.1 — drift detection identifies when recalibration is needed
- **Enhances:** All signal-consuming briefs

## Scope

Close the feedback loop: decision journal → effectiveness scoring → threshold adjustment → better signals.

## Architecture

```
Signal fires → User acts/dismisses → Decision Journal records
                                            ↓
Calibration Engine ← Effectiveness Scorer ← Journal analysis
       ↓
Updated thresholds.yaml
       ↓
Next cycle uses adjusted thresholds
```

## Tasks

| Task | Title | Est. Lines |
|------|-------|------------|
| AT-1.1 | Signal Effectiveness Scorer | ~250 |
| AT-2.1 | Threshold Adjustment Engine | ~300 |
| AT-3.1 | Seasonal & Contextual Modifiers | ~250 |
| AT-4.1 | Calibration Reporting | ~200 |
| AT-5.1 | Adaptive Threshold Validation | ~300 |

## Estimated Effort

~1,300 lines. 5 tasks. Medium.

## Success Criteria

- Signals that are consistently dismissed get their thresholds raised
- Signals that are consistently acted on maintain or lower their thresholds
- Seasonal adjustments account for Dubai business rhythms
- Calibration is transparent — Molham can see what changed and why
- No automatic threshold change exceeds a safety cap (max ±30% per calibration cycle)
