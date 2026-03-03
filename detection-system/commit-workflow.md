# Commit Workflow & Error Recovery Protocol

This document defines the exact flow for getting code from agent sessions into the repo, and how to recover when things go wrong.

---

## Normal Flow (Happy Path)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. AGENT SESSION                                                │
│    - Agent reads HANDOFF.md + phase spec + AGENT.md             │
│    - Agent implements task(s)                                    │
│    - Agent runs verification (ruff, bandit, pytest)             │
│    - Agent produces Session Output block (see AGENT.md format)  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Molham copies Session Output
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. CLAUDE (Commit Assistant)                                    │
│    - Receives Session Output from Molham                        │
│    - Validates: all verification steps passed?                  │
│    - Generates commit/push/merge commands                       │
│    - Includes Mac-only steps (tsc, prettier, format)            │
│    - Returns single copy-paste command block                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Molham runs commands on Mac
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. MAC EXECUTION                                                │
│    - Molham runs the command block on Mac                       │
│    - Pre-commit hooks run                                       │
│    - Push triggers CI                                           │
│    - gh pr merge --auto waits for CI                            │
│    - gh pr checks --watch shows CI status                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ CI passes → PR merges → Done
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. STATE UPDATE                                                 │
│    - Update state.json: mark tasks complete, add PR number      │
│    - Update HANDOFF.md: reflect completed work, point to next   │
│    - If phase complete: update plan/index.yaml status           │
│    - Commit state updates (can be in same or next PR)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Error Recovery Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ CI FAILS or MAC COMMAND FAILS                                   │
│ Molham sees error output                                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Molham copies error logs
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ CLAUDE (Error Analyzer)                                         │
│ - Receives error logs from Molham                               │
│ - Identifies: which tool failed (ruff/bandit/tsc/prettier/test) │
│ - Identifies: which file(s) and line(s)                         │
│ - Generates EITHER:                                             │
│   A) Direct fix commands (if simple: format, lint, typo)        │
│   B) Fix prompt for agent (if complex: logic error, test fail)  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
              Path A ▼       Path B ▼
┌──────────────────────┐  ┌──────────────────────────────────────┐
│ SIMPLE FIX           │  │ AGENT FIX                            │
│ Claude gives Molham  │  │ Claude gives Molham a prompt to      │
│ direct Mac commands: │  │ paste into the agent session:        │
│                      │  │                                      │
│ cd ~/clawd/moh_time_ │  │ "The CI failed with this error:     │
│ uv run pre-commit .. │  │  [exact error]. Fix the issue in     │
│ git add <files>      │  │  <file> at line <N>. The root cause  │
│ git commit -m "fix:."│  │  is <analysis>. After fixing, re-run │
│ git push             │  │  verification and produce a new      │
│                      │  │  Session Output block."              │
└──────────┬───────────┘  └──────────────────┬───────────────────┘
           │                                  │
           ▼                                  │ Agent produces new
    Push + CI watch                           │ Session Output
           │                                  ▼
           │                    Back to Step 2 (Claude generates
           │                    new commit commands)
           ▼
    CI passes → Done
```

---

## Error Classification

| Error Type | Tool | Path | Example |
|---|---|---|---|
| Format error | ruff format | A (simple) | Molham runs `uv run pre-commit run ruff-format --files <path>` |
| Lint error | ruff check | A or B | Simple unused import = Path A. Logic error = Path B |
| Security finding | bandit | B (agent) | Agent must change the code pattern |
| Type error | mypy / tsc | B (agent) | Agent must fix types |
| Test failure | pytest | B (agent) | Agent must fix logic or update test |
| Prettier error | prettier | A (simple) | Molham runs `pnpm exec prettier --write <files>` |
| Pre-commit fail | mixed | A or B | Depends on which hook failed |
| Governance fail | CI | B (agent) | Missing ADR -- agent must create it |
| Drift detection | CI | A (simple) | Molham runs `uv run python scripts/generate_system_map.py` |
| Enforcement gate | CI | STOP | Protected file changed -- tell Molham, he runs blessing |

---

## Command Templates

### Template: Fresh Commit (no prior failures)

```bash
cd ~/clawd/moh_time_os

# Mac-only verification (before commit)
cd time-os-ui && npx tsc --noEmit && cd ..          # if UI changes
cd time-os-ui && pnpm exec prettier --write <NEW_FILES> && cd ..  # if new .tsx/.ts
uv run pre-commit run ruff-format --files <PATHS>   # format on Mac

# Commit
git checkout -b <BRANCH>
git add <FILES>
git commit -m "$(cat <<'EOF'
<type>: <description max 72 chars>

<body>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
git push -u origin <BRANCH>
gh pr create --title "<type>: <description>" --body "<body>"
gh pr merge <N> --merge --auto
gh pr checks <N> --watch
```

### Template: Fix After CI Failure

```bash
cd ~/clawd/moh_time_os

# Apply fix (varies by error type)
<FIX_COMMANDS>

# Re-verify
<VERIFICATION_COMMANDS>

# Fresh commit (NEVER amend)
git add <FILES>
git commit -m "$(cat <<'EOF'
fix: <what was fixed>

Root cause: <why it failed>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
git push
gh pr checks <N> --watch
```

### Template: Agent Fix Prompt

```
The CI failed on PR #<N> with this error:

```
<EXACT ERROR OUTPUT>
```

**Failed tool:** <ruff/bandit/tsc/pytest/etc>
**Failed file:** <path/to/file.py> at line <N>
**Root cause:** <analysis of why it failed>

Fix the issue. After fixing:
1. Re-run `ruff check <file>` and `bandit -r <file>`
2. Re-run `python -m pytest tests/ -x`
3. Produce a new Session Output block (see AGENT.md format)

Do NOT change any other files. Do NOT fix unrelated issues.
```

---

## State Update Commands

After PR merges, update state tracking:

```bash
# In detection-system/state.json:
# - Set phase tasks_complete count
# - Add PR number to prs array
# - If all tasks done: set phase status to "complete", completed_session to N
# - If next phase unblocked: set status from "blocked" to "pending"
# - Increment current_session

# In detection-system/HANDOFF.md:
# - Rewrite "What Just Happened" with completed work
# - Rewrite "What's Next" pointing to next phase/task
# - Add any new rules to "Key Rules"
```

---

## Pre-Flight Checklist (Before Every Session)

The agent MUST do these before writing any code:

1. Read `detection-system/HANDOFF.md` -- what's current
2. Read `detection-system/plan/phase-NN.yaml` -- task specs
3. Read `detection-system/AGENT.md` -- rules and constraints
4. Read `detection-system/state.json` -- verify task statuses match reality
5. Read `docs/design/DETECTION_SYSTEM_DESIGN.md` -- relevant section for current phase
6. Read `CLAUDE.md` -- repo-level rules

If HANDOFF.md and state.json disagree, fix the inconsistency before starting work.

---

## Anti-Patterns (Things That Waste Time)

1. **Formatting from sandbox.** ruff version mismatch causes infinite stash conflicts.
2. **Running git from sandbox.** Creates index.lock that blocks Mac.
3. **Amending after pre-commit failure.** The commit didn't happen -- amend modifies the PREVIOUS commit.
4. **Using `--no-verify`.** Breaks the pre-push hook marker file.
5. **Forgetting to stage all files.** Causes pre-commit stash conflicts.
6. **Not running tsc before commit.** Type errors caught after push waste a CI cycle.
7. **Not running prettier on new .tsx files.** CI runs prettier --check on all src/.
8. **Using calendar_events table.** It doesn't exist. Use events JOIN calendar_attendees.
9. **Calling collect_calendar_for_user() for storage.** It fetches but doesn't persist. Use CalendarCollector.sync().
10. **Not regenerating system map.** New fetch('/api/...') calls trigger drift detection CI failure.
