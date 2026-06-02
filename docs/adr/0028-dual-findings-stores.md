# ADR-0028: Keep detection_findings and signal_state as separate stores

- Status: Accepted
- Date: 2026-06-02
- Deciders: Molham
- Workstream: WS5 (Detection / Intelligence Correctness)

## Context

The live database holds two parallel "findings" stores:

- `signal_state` — written by the intelligence subsystem: `lib/intelligence/signals.py`,
  `persistence.py`, `engine.py`, `signal_lifecycle.py`. Lifecycle-tracked
  (new/ongoing/escalated/cleared). This is the store the live signal picture lives in.
  Schema: `lib/schema.py:1598` (`TABLES["signal_state"]`).
- `detection_findings` — written by the detection subsystem:
  `lib/detectors/__init__.py:53` (`INSERT INTO detection_findings`) via the daemon's
  detection stage (`lib/daemon.py` `_handle_detection`, `dry_run=False`). Holds
  correlated detector outputs (collision/drift/bottleneck) with a
  `detection_findings_preview` dry-run twin. Schema: `lib/schema.py:1649`
  (`TABLES["detection_findings"]`), preview at `:1678`.

Verified by grep: `lib/detectors` never writes `signal_state`, and `lib/intelligence`
never writes `detection_findings` (both greps return empty). Both schemas are canonical
(defined in `lib/schema.py`), so neither is a stray table.

Consumers of `detection_findings` (`lib/detectors/morning_brief.py:67,77,87`,
`api/server.py` — 7 references) therefore surface only the detection-stage rows, while
the real, current signal picture is in `signal_state`. This makes "what is an active
finding?" ambiguous and is a latent source of inconsistent dashboards.

## Decision

Keep the two stores **separate**. They model distinct concepts:

- `detection_findings` = raw detector outputs with correlation grouping
  (collision/drift/bottleneck), suited to the morning-brief change-notification flow.
- `signal_state` = the lifecycle-tracked signal catalog (23 signals across
  THRESHOLD/TREND/ANOMALY/COMPOUND), the canonical answer to "which signals are
  currently active?".

A full merge into one unified findings model is a large design effort and is **out
of scope** for WS5. WS5's job is to make the intelligence pipeline actually populate
`signal_state` on a schedule (see the `MOH_INTELLIGENCE_FULL_MODE` switch and the
bulk-trajectory migration in the same workstream).

## Canonical store for "active findings"

`signal_state` is canonical for "active findings / current signals". Any UI or API
surface that wants the live operational picture MUST read `signal_state`, not
`detection_findings`.

## Consequences

- No schema or pipeline change in WS5; this ADR records the boundary so future work
  does not "fix" the duplication by accident.
- Consumer guidance: dashboards and briefings intended to show *current* signals
  should migrate to `signal_state`. `detection_findings`/`morning_brief` remain the
  detector-correlation change-notification path and are not the source of truth for
  active signals.
- Follow-up (NOT this workstream): if a unified findings model is desired later, it
  needs its own spec and migration plan; reference this ADR as the starting context.
