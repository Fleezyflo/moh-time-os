# Session System v2 — Core

This directory contains the template files that go into every project repo. They form the session persistence layer — the system that lets stateless agents manage multi-session plans without drift.

## Files

| File | Purpose | Format |
|------|---------|--------|
| `AGENT.md` | Agent instructions. Replaces CLAUDE.md. | Markdown with structured sections |
| `state.json` | Machine-readable project state. Single source of truth. | JSON |
| `plan/` | Plan directory. One file per phase. | YAML per phase + index.yaml |
| `sessions/` | Session log directory. One file per session. | YAML per session |
| `HANDOFF.md` | Generated from state.json + plan/ + sessions/. Never hand-edited. | Markdown (generated) |
| `scripts/check_state.py` | Validates state.json against plan/ and sessions/. Runs in pre-commit. | Python |
| `scripts/generate_handoff.py` | Generates HANDOFF.md from structured state. | Python |

## How It Works

### State is structured

`state.json` is the single source of truth for project status:

```json
{
  "project": "my-project",
  "current_phase": "phase-03",
  "current_session": 12,
  "phases": {
    "phase-00": {"status": "complete", "completed_session": 5, "prs": [28, 30]},
    "phase-01": {"status": "complete", "completed_session": 6, "prs": [31]},
    "phase-02": {"status": "complete", "completed_session": 6, "prs": [32]},
    "phase-03": {"status": "in_progress", "started_session": 7, "prs": []},
    "phase-04": {"status": "blocked", "blocked_by": ["phase-03"]},
    "phase-05": {"status": "pending"}
  },
  "rules_version": 3,
  "enforcement_repo": "Org/enforcement",
  "last_pr": 35,
  "last_verified": "2026-02-28T12:05:51Z"
}
```

A script can parse this. A pre-commit hook can validate it. An agent reads it and knows exactly where things stand — no interpretation needed.

### Plans decompose into phases, phases into tasks

```
plan/
  index.yaml          # Phase list, dependencies, status (mirrors state.json phases)
  phase-00.yaml       # Detailed spec for phase 0
  phase-01.yaml       # Detailed spec for phase 1
  ...
```

Each phase YAML has:
- Description, dependencies, estimated sessions
- Tasks (ordered list of discrete work units)
- Each task has: description, files involved, verification criteria, estimated scope
- Completion criteria for the phase

### Sessions are individual records

```
sessions/
  session-001.yaml
  session-002.yaml
  ...
```

Each session YAML has:
- Session number, date, type (build/verify/plan/investigate)
- Assigned phase and tasks
- Work done (list of concrete items with file paths)
- PRs created/merged
- Issues discovered
- Rules learned
- State changes (what changed in state.json)

### HANDOFF.md is generated, never hand-edited

`scripts/generate_handoff.py` reads state.json + plan/ + sessions/ and produces HANDOFF.md. This eliminates stale handoffs. The generated file includes:
- Current state (from state.json)
- What the last session did (from latest session YAML)
- What the next session should do (from plan/ — next incomplete task in current phase)
- All rules (from AGENT.md, categorized)
- File reading order

### Consistency is enforced by pre-commit

`scripts/check_state.py` runs as a pre-commit hook. It checks:
1. Every phase marked "complete" in state.json has a session record confirming it
2. Every phase marked "complete" has its PRs listed
3. No phase is "in_progress" if its dependencies aren't "complete"
4. state.json `current_phase` matches the first non-complete phase
5. HANDOFF.md matches what generate_handoff.py would produce (detects hand-edits)
6. Plan index.yaml status fields match state.json

If any check fails, the commit is blocked. The agent cannot proceed without fixing the inconsistency.

## Setup

1. Copy the `core/` directory into your project repo
2. Create `plan/index.yaml` with your phases
3. Create individual phase YAML files
4. Initialize `state.json` with all phases in "pending" status
5. Add `scripts/check_state.py` to `.pre-commit-config.yaml`
6. Run `scripts/generate_handoff.py` to create initial HANDOFF.md
