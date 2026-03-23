# ADR-0024: Canonicalization Comments, Detector Production Mode, Portfolio Progressive Rendering

## Status
Accepted

## Context
Three related improvements bundled into one pass:

1. **Non-canonical route documentation (server.py):** Several API routes in `api/server.py` are not called by any UI page and have canonical replacements. These routes (`/api/control-room/proposals`, `/api/command/client-health`, `/api/command/team-load`) need deprecation markers pointing to their canonical replacements per CANONICALIZATION.md.

2. **Detector dry_run alignment (autonomous_loop.py, detectors/__init__.py):** The autonomous loop called `run_all_detectors(dry_run=True)`, writing to the non-canonical `detection_findings_preview` table. The canonical daemon (`lib/daemon.py`) already uses `dry_run=False`, writing to `detection_findings`. The autonomous loop should match.

3. **Portfolio blank screen (Portfolio.tsx):** The Portfolio page used a combined `isLoading` flag gating ALL content behind ALL hooks resolving. One slow or failed hook blanked the entire page.

Affected trigger files: `api/server.py` (comments only -- no behavioral change to routes).

## Decision
1. Add `NON-CANONICAL` warning comments to deprecated routes in `server.py` with references to canonical replacements and CANONICALIZATION.md sections.
2. Switch `autonomous_loop.py` from `dry_run=True` to `dry_run=False` to align with the daemon's production mode. Update docstrings in `lib/detectors/__init__.py` and `lib/intelligence/proposals.py` to document canonical vs non-canonical paths.
3. Replace Portfolio's global loading gate with per-section progressive rendering. Each section independently shows loading placeholders, content, or empty-state messages.
4. Update `test_audit_remediation_v3.py` to test against the canonical `intelligence_router.list_proposals` instead of the non-canonical `spec_router.get_intelligence_proposals`.
5. Remove `/api/auth/mode` smoke test from `scripts/dev.sh` (endpoint still exists in `api/auth.py`, just not essential for dev startup validation).

## Consequences
- Deprecated routes are clearly documented for future removal. No runtime behavior change in server.py.
- Autonomous loop now writes to the same `detection_findings` table as the daemon. The `detection_findings_preview` table is no longer written to by any production path.
- Portfolio page renders progressively -- users see content as each hook resolves instead of waiting for all hooks.
- 15 new component behavior tests verify the progressive rendering contract.
