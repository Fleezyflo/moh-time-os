# Session System v2

A project-agnostic template for session persistence, plan management, and file enforcement across stateless AI agent sessions. Built from 12 sessions, 14 merged PRs, and hard-won lessons about context preservation, documentation drift, and compliance at the edge of stateless computing.

## What This Is

This is a **structural solution** to three critical problems:

1. **Stateless agents lose context** — Between sessions, agents forget what was done, what's planned, and what the rules are
2. **Documentation drifts** — Phase specs get stale, plans diverge from reality, handoff notes become inaccurate
3. **Protected files get modified** — Critical configuration, CI rules, and enforcement specs can be changed by agent code, breaking the system from the inside

The session system addresses all three:
- **State** is structured as JSON + YAML, not prose (machine-readable, version-controlled, validatable)
- **Artifacts** are generated, never hand-edited (HANDOFF.md is computed from state.json and phase specs)
- **Enforcement** is built into CI/CD and a separate private repo with compliance authority

## The Problem

### Session 1: Context Loss

An agent completes work on Friday: "I wrote the authentication module, here's what to do next." But on Monday, a new agent session starts. It reads the codebase, not the previous agent's notes. It re-discovers the architecture, re-learns the code rules, re-decides how to structure the next phase. Wasted time, inconsistent decisions, repeated bugs.

**Root cause**: Knowledge stored in prose (chat history, loose Markdown). No machine-readable state. No way to hand off structured context.

### Sessions 2-4: Documentation Drift

A plan document says "Phase 2 is not started." But work has been done. The phase spec says "must have 4 endpoints" but only 3 were implemented. The HANDOFF.md references "pending PR #45" but PR #45 merged a week ago. Code is shipping, but docs are 2 weeks behind. New agents read stale guidance.

**Root cause**: Docs updated by hand, sporadically, by busy engineers. No enforcement that forces docs to update when code changes. No validation that state.json matches reality.

### Sessions 5-8: Protected Files Modified

An agent modifies `pyproject.toml` to add a dependency. It modifies `.pre-commit-config.yaml` to disable a check. It modifies `ci.yml` to skip a test. These modifications are hidden — the CI runs the original versions (blessed copies), so the PR looks like it passed. But the changes were made. When the PR merges, the modifications persist. The system drifts.

**Root cause**: No authority enforcement. No mechanism says "these files are immutable without explicit blessing." CI doesn't check if the agent modified protected files. The agent learns too late (or never).

## The Solution

### Structural Enforcement (Not Just Guidelines)

**State.json** — Single source of truth for project metadata, phases, PRs, status.

```json
{
  "project": { "name": "my-product", "repo": "org/project", "enforcement_repo": "org/enforcement" },
  "phases": [ { "id": "phase-00", "status": "pending" }, ... ],
  "current_phase": "phase-00",
  "pending_prs": [ { "number": 42, "phase": "phase-01", "status": "awaiting_review" } ],
  "completed_phases": [ { "id": "phase-00", "session_completed": 1 } ]
}
```

**Artifacts** — Files generated from state, never hand-edited.

- `HANDOFF.md` is computed from state.json + phase specs
- Agent reads `HANDOFF.md` to learn what's next
- When state.json updates (PR merged, phase completed), `HANDOFF.md` is regenerated
- No manual editing means no stale guidance

**Protected Files** — Canonical versions live in a separate enforcement repo.

1. Agent modifies `pyproject.toml`? CI restores the blessed copy before running lint/test
2. Agent's modified version is checked by enforcement gate (separate repo, separate CI)
3. If they differ, PR fails status check and cannot merge
4. Blessing happens only via explicit workflow (Molham only)

**Pre-commit Hooks** — Block commits that violate state consistency.

- Before committing, hooks validate state.json
- Before committing, hooks verify all phase files exist
- Before committing, hooks confirm HANDOFF.md is up-to-date

## Architecture Overview

The system has two parts: **core/** (in your project) and **enforcement-template/** (bootstraps the enforcement repo).

### core/ — Project Repo

```
core/
├── state.json                    # Current state (project, phases, PRs, status)
├── plan/
│   ├── index.yaml               # Master list of phases
│   ├── phase-template.yaml       # Template for new phases
│   ├── phase-00.yaml             # Phase spec (deliverables, work, verification)
│   └── ...
├── scripts/
│   ├── check_state.py            # Validate state.json + phases match
│   └── generate_handoff.py        # Generate HANDOFF.md from state.json + specs
├── AGENT.md                      # Agent instructions (code rules, session discipline)
└── HANDOFF.md                    # Generated at setup; agent reads this (what's next)
```

### enforcement-template/ — Enforcement Repo

```
enforcement-template/
├── .github/workflows/
│   ├── enforcement-gate.yml      # Checks protected files match blessed versions
│   └── bless.yml                 # Workflow to canonicalize protected files
├── scripts/
│   ├── compare.sh                # Compare project files vs. blessed
│   └── restore.sh                # Restore blessed files
├── blessed/                      # Canonical versions of protected files
│   ├── pyproject.toml
│   ├── .pre-commit-config.yaml
│   └── ...
├── protected-files.txt           # List of protected files (generated)
└── README.md                     # Enforcement repo docs
```

### How It Works

```
┌─────────────────────────────┐
│  Agent reads state.json     │
│  Learns: project, phases,   │
│  current phase              │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Agent reads HANDOFF.md     │
│  Learns: what's next (from  │
│  plan/phase-NN.yaml)        │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Agent works:               │
│  - reads code               │
│  - makes changes            │
│  - runs tests locally       │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Agent commits to branch    │
│  Pre-commit validates state │
│  (consistent, no drift)     │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Agent creates PR           │
│  Project CI runs:           │
│  - restore blessed files    │
│  - lint, test on blessed    │
│  - dispatch enforcement     │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Enforcement CI:            │
│  - compares files vs.       │
│    blessed                  │
│  - post status on PR        │
│  - PR fails if different    │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  If PR passes both:         │
│  - Merge to main            │
│  - Trigger bless workflow   │
│    (if protected files      │
│     changed)                │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Agent updates docs:        │
│  - SESSION_LOG.md (append)  │
│  - state.json (mark phase   │
│    complete)                │
│  - regenerate HANDOFF.md    │
│  - commit, push             │
└─────────────────────────────┘

Next session agent reads
updated HANDOFF.md and
starts with full context.
```

## Directory Structure

```
.
├── core/                         # Copy into your project root
│   ├── state.json               # Project state (edit at setup)
│   ├── plan/
│   │   ├── index.yaml           # Phase index (edit at setup)
│   │   ├── phase-template.yaml   # Template for new phases
│   │   ├── phase-00.yaml         # First phase spec
│   │   └── ...                   # More phase specs
│   ├── scripts/
│   │   ├── check_state.py        # Validate state consistency
│   │   └── generate_handoff.py   # Generate HANDOFF.md (supports --check)
│   ├── AGENT.md                 # Agent instructions (customize)
│   └── HANDOFF.md               # Generated; do not edit
│
├── enforcement-template/         # Bootstrap your enforcement repo
│   ├── .github/workflows/
│   │   ├── enforcement-gate.yml  # Compliance check
│   │   └── bless.yml             # Blessing workflow
│   ├── scripts/
│   │   ├── compare.sh            # File comparison
│   │   ├── restore.sh            # File restoration
│   │   └── init-enforcement.sh   # Bootstrap new enforcement repo
│   ├── blessed/                  # Canonical file versions (after first bless)
│   ├── protected-files.txt       # Generated after first bless
│   ├── project-ci-template.yml   # CI workflow template for project repo
│   └── project-precommit-template.yaml  # Pre-commit config for project repo
│
└── examples/                     # Concrete example (TaskFlow project)
    ├── state.json               # Populated state at session 4
    ├── plan/                    # Phase index + phase-02 spec
    ├── sessions/                # Session 004 record
    └── AGENT.md                 # Filled-in agent instructions
```

## Quick Start

See **[SETUP.md](./SETUP.md)** for complete step-by-step instructions.

TL;DR:
1. Create a private enforcement repo, bootstrap with `enforcement-template/`
2. Copy `core/` into your project
3. Edit `state.json` with your project name and enforcement repo URL
4. Create phase specs in `plan/phase-NN.yaml`
5. Run `python scripts/generate_handoff.py`
6. Create and protect main branch
7. Run bless workflow to canonicalize protected files
8. Start first session

## Design Principles

See **[CRITIQUE.md](./CRITIQUE.md)** for full analysis and rationale.

**Seven core principles:**

1. **State is structured** — JSON/YAML, not prose. Machine-readable, validatable, versioned.

2. **Artifacts are generated** — HANDOFF.md is computed from state.json and phase specs, never edited by hand. Regenerate after every meaningful change.

3. **Plan is immutable during session** — Phases and deliverables cannot change mid-session. New discoveries go in SESSION_LOG.md or notes, not into phase specs. Phase specs are sacred.

4. **Documentation is mandatory** — Every code change requires a documentation update: what changed, where, why. Not optional. Not deferred. Not batch-updated at the end.

5. **Enforcement is structural** — Not guidelines. Blessed files are restored by CI. Protected files are compared by a separate repo. Pre-commit blocks commits that violate state consistency. Breaking the system requires deliberate effort.

6. **Authority is distributed** — Agent decides code structure, tests, implementation. Project owner (Molham) decides what to work on, whether to merge, whether tradeoffs are acceptable, and runs blessing workflows.

7. **Sessions are bounded** — Each session starts by reading current state, reads the phase spec, declares intent, does work, updates docs, and stops. No carryover. No assumptions about next session. Full handoff is explicit and generated.

## What's in Each Directory

### `core/`

The scaffolding you copy into your project. Contains:

- **state.json** — Your project's state machine. Edit at setup, update as you work.
- **plan/** — Phase specifications. One file per phase. Templates provided. Read by agents, not modified during sessions.
- **scripts/** — Utilities for validation and artifact generation. Run by CI and pre-commit.
- **AGENT.md** — Instructions for agents. Code rules, verification procedures, session discipline. Customize for your project.
- **HANDOFF.md** — Generated artifact. Never edit by hand. Regenerated every time state changes. Agent reads this to learn what's next.

### `enforcement-template/`

The scaffold for your enforcement repo. Contains:

- **.github/workflows/** — Two workflows:
  - `enforcement-gate.yml` — Runs on every PR in the project. Checks protected files. Posts status.
  - `bless.yml` — Blessing workflow. Copies protected files from project to enforcement repo as canonical versions.
- **scripts/** — Utilities for comparing, restoring, and bootstrapping: `compare.sh`, `restore.sh`, `init-enforcement.sh`.
- **blessed/** — Directory holding canonical (blessed) versions of protected files. Populated after first bless.
- **protected-files.txt** — List of files under protection. Generated by first bless workflow.
- **project-ci-template.yml** — CI workflow template for the project repo. Copy to project's `.github/workflows/ci.yml`.
- **project-precommit-template.yaml** — Pre-commit config template for the project repo.

## How Agents Use This

### First Session

Agent reads files in this order:

1. **state.json** — Understand project name, phases, current phase, enforcement repo
2. **HANDOFF.md** — Learn what's next (generated, computed, current)
3. **plan/phase-NN.yaml** — Read phase spec: deliverables, work steps, acceptance criteria
4. **AGENT.md** — Learn code rules, verification procedures, documentation discipline
5. **CLAUDE.md** (if exists) — Project-specific rules and session discipline

Agent then:
- Declares intent: "I will implement phase-00: CI setup, pre-commit, typing"
- Does work: reads code, makes changes, runs tests
- Verifies: lints, tests, pre-commit, type checking
- Commits: follows format, includes context
- Creates PR: watches CI, verifies no protected file modifications
- Updates docs: SESSION_LOG.md, state.json, regenerates HANDOFF.md
- Hands off: gives Molham a single commit/push command

### Subsequent Sessions

Agent reads same files (now updated from previous session):

1. **state.json** — See current status: completed phases, current phase, pending PRs
2. **HANDOFF.md** — Rewritten by previous session; describes what's next
3. **plan/phase-NN.yaml** — Read next phase spec
4. **AGENT.md** — Same rules as before, may have new entries
5. **SESSION_LOG.md** — Read previous session's work, learn from lessons

Work proceeds as before. Cycle repeats. Knowledge accumulates.

## Verification & Compliance

### Pre-commit Enforcement

Every commit triggers:

1. **State validation** — `check_state.py` verifies state.json is consistent
2. **Phase inventory** — All phases in state.json have corresponding files in plan/
3. **HANDOFF.md freshness** — Regenerate and verify it's up-to-date
4. **Code rules** — ruff lint, ruff format, bandit
5. **End-of-file fixes** — Trailing whitespace, final newline

Commit blocks if any check fails.

### CI Enforcement

Every PR triggers:

1. **Restore blessed files** — Download canonical versions from enforcement repo
2. **Run all checks** — lint, format, test, type checking against blessed versions
3. **Dispatch enforcement gate** — Project CI calls enforcement repo's gate workflow
4. **Enforcement gate** — Compares project files against blessed, posts status
5. **Branch protection** — PR cannot merge until both CI and enforcement gate pass

Protected file modifications are caught and PR fails.

### Post-merge Blessing

If protected files were modified and PR is approved:

1. Enforcement repo's `bless.yml` workflow triggers
2. Pulls modified files from main branch
3. Copies them to `blessed/`
4. Updates `protected-files.txt`
5. Commits and pushes

Next PR will restore the new blessed versions. The system stays in sync.

## Example Workflow

```bash
# Session N+1 starts
# Agent reads state.json, sees current_phase: "phase-02"
# Agent reads HANDOFF.md, sees it was regenerated by previous session
# Agent reads plan/phase-02.yaml, sees next task

# Agent makes a change
vim src/api/endpoints.py

# Agent runs tests
python -m pytest tests/ -x
# ✓ passes

# Agent verifies lint
ruff check .
ruff format --check .
# ✓ passes

# Agent stages changes
git add src/api/endpoints.py

# Agent commits (pre-commit validates state)
git commit -m "feat: add user endpoint with validation"
# pre-commit: check_state.py ✓
# pre-commit: ruff lint ✓
# pre-commit: ruff format ✓
# ✓ commit succeeds

# Agent pushes
git push

# Project CI runs:
#   - restore blessed files ✓
#   - lint & test against blessed ✓
#   - dispatch enforcement gate ✓

# Enforcement CI:
#   - compare protected files vs. blessed ✓
#   - post status on PR ✓

# PR passes both gates, can merge

# Agent updates docs
vim SESSION_LOG.md        # append: what changed
vim state.json            # update phase status
python scripts/generate_handoff.py  # regenerate HANDOFF.md

git add SESSION_LOG.md state.json HANDOFF.md plan/
git commit -m "docs: session N+1 phase-02 complete"

# Next session agent reads updated HANDOFF.md
# Full context preserved, no backslide
```

## Why This Works

**For agents:** Structured state + generated artifacts = no manual docs to maintain. Read JSON, read HANDOFF.md, read phase spec, work. No context loss.

**For code quality:** Pre-commit + CI + enforcement gate = protected files cannot be modified without explicit blessing. No surprise changes hidden in a PR.

**For plan adherence:** Phase specs are immutable during sessions. New discoveries go in SESSION_LOG.md. Next session reads log, learns context, adjusts plan if needed. No mid-phase scope creep.

**For scalability:** System is project-agnostic. Swap code rules, add phases, change tools. State, validation, artifact generation stay the same.

## Limitations & Future Work

**Current limitations:**

- Enforcement repo requires separate PATs. GitHub should have better multi-repo enforcement primitives.
- Phase immutability is by convention, not enforced. Agent *could* edit plan/phase-NN.yaml. Don't.
- Blessing workflow requires manual dispatch (for now). Could be automated on merge.
- HANDOFF.md generation is Python-only. Could port to shell script for portability.

**Future improvements:**

- Webhook-based blessing (auto-bless when protected files merge)
- Merge dry-run in enforcement gate (preview what blessed would be)
- Phase branching (experimental branches for large changes)
- Structured session notes (JSON, not Markdown)
- Agent introspection (agent reads its own session log, learns from previous mistakes)

## See Also

- **[SETUP.md](./SETUP.md)** — Complete setup instructions (7 steps, 3 hours)
- **[CRITIQUE.md](./CRITIQUE.md)** — Design analysis, rationale, alternatives considered
- **[core/AGENT.md](./core/AGENT.md)** — Template for agent instructions
- **[core/plan/phase-template.yaml](./core/plan/phase-template.yaml)** — Template for phase specs
- **[enforcement-template/README.md](./enforcement-template/README.md)** — Enforcement repo docs

---

Built from real production lessons. Battles scars included.
