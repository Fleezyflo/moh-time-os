# Agent Instructions

This file defines how the agent operates. It replaces the monolithic CLAUDE.md with a structured, categorized system.

## Identity

You are an engineering agent working on {{PROJECT_NAME}}. You write code, run commands, fix problems, and verify your own work.

## Session Entry Protocol

Every session starts with these steps, in order. No exceptions.

1. **Read `state.json`.** This is the single source of truth. It tells you: current phase, current session number, which phases are complete, which PRs exist, what's blocked.

2. **Read `HANDOFF.md`.** This is generated from state.json + plan/ + sessions/. It tells you: what the last session did, what you should do now, which files to read, which rules apply.

3. **Read the current phase spec.** `plan/phase-NN.yaml` for whatever `current_phase` says in state.json. This has the detailed spec, task list, and verification criteria.

4. **Read `AGENT.md` rules section.** You're reading it now. Absorb the rules by priority.

5. **Verify cross-file consistency.** Run `python scripts/check_state.py` mentally or actually. Compare:
   - state.json phase statuses vs session records
   - HANDOFF.md claims vs actual state
   - Plan index vs state.json
   If anything is inconsistent, fix it BEFORE starting work. This is not optional. This is the mechanism that prevents drift.

6. **State your intent.** Before writing any code, declare: "This session will [do X] on [phase Y], tasks [N-M]."

## Rules

Rules are categorized by severity. Higher severity rules always take precedence.

### CRITICAL — Violation causes data loss, security breach, or irreversible damage

- Never add `nosec`, `noqa`, or `# type: ignore` — fix the root cause
- Never run destructive git commands without explicit owner approval
- Never modify protected files — stop and report what needs to change
- Never suppress security scanner findings — they are real until proven otherwise
- Never commit secrets, credentials, or tokens

### HIGH — Violation causes CI failure, broken builds, or wasted sessions

- Update state.json when a phase completes. Do it at the moment of completion, not later.
- Update session YAML after each commit. Not at session end. At the commit.
- Run all verification gates before providing commit commands
- Stage ALL modified files before committing (prevents stash conflicts)
- Never format from sandbox if sandbox tooling versions differ from CI pinned versions

### MEDIUM — Violation causes friction, rework, or inconsistency

- Follow existing code patterns — grep before inventing
- One session, one phase section — don't jump around
- Commit subject max 72 characters, lowercase after prefix
- Include deletion rationale when removing 20+ lines
- Regenerate derived files when source changes (system map, types, etc.)

### LOW — Style and convention

- Use `--` not em dash in commit messages
- Conventional commit format: `type: description`
- Branch names: `type/short-description`

## Decision Authority

- **Agent decides:** Implementation approach, pattern choice, test structure, fix strategy
- **Owner decides:** What to work on, whether to merge, tradeoff acceptance, protected file changes

## Session Exit Protocol

Before a session ends (or context runs low):

1. Update state.json with any phase status changes
2. Write/update the session YAML for this session
3. Run `scripts/generate_handoff.py` to regenerate HANDOFF.md
4. Run `scripts/check_state.py` to validate consistency
5. All four artifacts (state.json, session YAML, HANDOFF.md, any plan updates) must be included in the commit

## Environment Constraints

{{ENVIRONMENT_CONSTRAINTS}}

Replace this section with project-specific constraints (sandbox limitations, tool version mismatches, platform restrictions).

## Code Rules

{{CODE_RULES}}

Replace this section with project-specific code rules (language-specific, framework-specific, security requirements).

## Verification Requirements

{{VERIFICATION_REQUIREMENTS}}

Replace this section with project-specific verification gates (linters, formatters, tests, type checkers, security scanners).
