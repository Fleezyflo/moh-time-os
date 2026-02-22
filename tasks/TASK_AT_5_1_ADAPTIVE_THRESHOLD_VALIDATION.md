# AT-5.1: Adaptive Threshold Validation

## Objective

Comprehensive test suite validating the full adaptive threshold pipeline: effectiveness scoring → calibration → seasonal modifiers → reporting. Tests verify safety guardrails, edge cases, and integration between components.

## Dependencies

- AT-1.1 through AT-4.1 (all components must exist)
- Brief 22 SM-1.1 (decision journal fixtures)
- Brief 17 IW-1.1 (thresholds.yaml fixture)

## Test Files

### `tests/test_effectiveness_scorer.py` (~80 lines)

- High-dismiss signal (95/100 dismissed) → low effectiveness score (<0.2)
- High-action signal (90/100 acted on) → high effectiveness score (>0.8)
- Mixed signal (50/50) → moderate effectiveness (~0.5)
- Health improvement rate computed correctly (acted signals that improved health ÷ total acted)
- Timeliness factor decays correctly (response at 0h → 1.0, at 36h → 0.5, at 72h → 0.0)
- Signal with no journal entries → returns `{"status": "insufficient_data"}`
- score_all returns sorted list (worst first)
- Recommendation: effectiveness < 0.4 → "raise_threshold"
- Recommendation: effectiveness > 0.7 → "maintain"
- Recommendation: action_rate > 0.9 → "lower_threshold"
- Threshold suggestion stays within ±30% cap

### `tests/test_threshold_calibrator.py` (~100 lines)

- propose_adjustments returns correct direction for low-effectiveness signal
- ±30% cap is enforced (effectiveness=0.05 would suggest 60% raise → capped at 30%)
- Minimum data threshold: skip if < 20 fires
- Cooldown: skip if threshold was adjusted in last 14 days
- Oscillation detection: skip if last 2 adjustments went opposite directions
- apply_adjustments with dry_run=True makes no file changes
- apply_adjustments with dry_run=False writes new thresholds.yaml
- Backup file created before any modification
- Rollback restores correct previous state
- calibration_log populated with correct data
- Integer rounding for count thresholds, 1-decimal for percentages
- Duration thresholds round to nearest 5

### `tests/test_seasonal_modifiers.py` (~70 lines)

- Ramadan modifier activates during known Ramadan dates
- Weekend modifier activates on Friday (day 4) and Saturday (day 5)
- Q4 close modifier activates Nov 15 - Dec 31
- Factor multiplication produces correct adjusted thresholds
- Multiple overlapping modifiers stack multiplicatively
- Custom modifier can be added and retrieved
- Custom modifier can be removed
- Modifier calendar returns all entries for given year
- Date outside any modifier → no adjustments applied
- Seasonal modifier does not permanently alter thresholds.yaml

### `tests/test_calibration_reporter.py` (~60 lines)

- Weekly report includes all adjustments from the week
- Skipped adjustments include reason text
- Effectiveness report summary counts match individual categorizations
- Noisiest signals sorted by effectiveness ascending
- Most effective signals sorted by effectiveness descending
- History computes net direction correctly (2 raises + 1 lower = net raise)
- format_for_briefing returns non-empty string under 500 chars
- Empty data produces graceful "building baseline" message
- Seasonal exclusion count is accurate

### `tests/test_adaptive_integration.py` (~90 lines)

Full pipeline integration tests:

- **Scenario: Noisy signal gets quieter**
  1. Seed 100 fires of signal X, 85 dismissed
  2. Run effectiveness scorer → effectiveness < 0.4
  3. Run calibrator → proposes raise_threshold
  4. Apply adjustment → threshold increases
  5. Verify calibration_log entry
  6. Verify report includes the adjustment

- **Scenario: Well-calibrated signal unchanged**
  1. Seed 50 fires of signal Y, 40 acted on
  2. Run scorer → effectiveness > 0.7
  3. Run calibrator → proposes "maintain"
  4. No threshold change

- **Scenario: Seasonal exclusion**
  1. Seed 60 fires of signal Z, 50 during Ramadan, 10 outside
  2. Effectiveness scorer excludes Ramadan fires from analysis
  3. Only 10 fires → insufficient data → skip

- **Scenario: Safety cap enforcement**
  1. Seed extremely low effectiveness (0.05) → would suggest 50%+ raise
  2. Calibrator caps at 30%
  3. Verify final threshold = original × 1.30

- **Scenario: Oscillation prevention**
  1. Seed calibration_log with: raise on Feb 1, lower on Feb 15
  2. Run calibrator → proposes adjustment
  3. Verify adjustment is skipped due to oscillation

### Fixtures

Create `tests/fixtures/seed_decision_journal.py`:
- 200 decision journal entries across 10 signal types
- Varying action/dismiss ratios per signal type
- Health outcomes for acted signals
- Response times ranging from 15 minutes to 48 hours
- Entries spanning 90-day period
- Some entries during Ramadan dates, some outside

Create `tests/fixtures/seed_calibration_history.py`:
- 10 past calibration runs
- Mix of adjustments, skips, and one rollback
- 3 signal types with multiple adjustments (for oscillation testing)

## Validation

- All tests pass
- No test modifies real thresholds.yaml (use temp copies)
- Integration tests cover the full propose → apply → report cycle
- Safety guardrails (cap, cooldown, oscillation, min data) each have dedicated tests
- Seasonal modifier tests use known fixed dates, not system clock
- Edge cases: zero fires, all dismissed, all acted on, exactly at cap boundary

## Estimated Effort

~300 lines across 5 test files + 2 fixture files
