# AGENT.md — MOH Time OS Audit Remediation

You are a code-writing agent. You write code and generate a command block. That is all.

**You NEVER run anything.** Not git, not ruff, not pytest, not python, not pip, not npx, not any command. You have five tools: **Read, Write, Edit, Glob, Grep.** A previous agent tried `pip install ruff`, `python -m ruff`, `.venv/bin/ruff` — all violations, session rejected. Do not repeat this.

You write code. Molham runs it on his Mac.

Follow the steps below in order. Do not skip ahead.

---

**Step 1 — Read `audit-remediation/state.json`.**
Find your current phase and session number. This is your first tool call.

The current phase will be one of: `phase-a`, `phase-b`, `phase-c`, `phase-d`. Map it to your task file:

| Phase | Task File | Description |
|-------|-----------|-------------|
| phase-a | `audit-remediation/tasks/PHASE-A-PRODUCTION-HARDENING.md` | API, daemon, collector reliability |
| phase-b | `audit-remediation/tasks/PHASE-B-SYSTEM-COMPLETENESS.md` | Wire existing code to consumers |
| phase-c | `audit-remediation/tasks/PHASE-C-INTELLIGENCE-EXPANSION.md` | New intelligence capabilities |
| phase-d | `audit-remediation/tasks/PHASE-D-POLISH.md` | Tests, cleanup, observability, docs |

---

**Step 2 — Read `audit-remediation/HANDOFF.md`.**
What happened last session. What's next. Lessons learned by previous agents.

---

**Step 3 — Read your task file.**
Read the task file from the table above matching your current phase. These are your work items, verification checklist, and scope.

Also read `audit-remediation/tasks/GAP-REGISTRY.yaml` to understand the full gap inventory and cross-references between items.

---

**Step 4 — Read `CLAUDE.md`.**
Repo-level engineering rules. Read it fully, do not skim. It contains code rules you must follow: no bare excepts, no f-string SQL, no `return {}`/`[]` in except blocks without logging, no `hashlib.md5`, no `requests.get` without timeout, and more. Violations fail CI.

---

**Step 5 — Investigate every module your tasks touch.**

This is the most important step. Do not skip it. Do not rush it. Previous agents jumped straight to writing code, introduced patterns that don't exist in the codebase, and got rejected.

For each module or file:

1. Read it. Understand its classes, methods, return types, error handling.
2. Grep for who imports it. Understand what callers expect from it.
3. Read what it imports. Understand its dependencies.
4. Read 2-3 neighboring modules in the same directory. Note how they handle errors, how they log, how they name things, how they import. Your code must match these patterns exactly.
5. Read the tests if they exist. Understand what's asserted and how.

**Do not proceed to step 6 until you have done all five for every module you will touch.**

---

**Step 6 — Write the code.**

Write or edit code using Read, Edit, Write, Glob, Grep only. You do not run anything. You do not verify anything. You write correct code and move on.

Rules that apply here — break any and the session is rejected:

- **Match existing patterns.** Your code must look like it was written by the same person who wrote the neighboring modules. If you introduce a new pattern, you failed step 5.
- **Never bypass a check.** No `noqa`, `nosec`, `# type: ignore`, `# pragma: no cover`, `|| true`, `--no-verify`. Fix the code. Can't fix it? Stop and tell Molham.
- **Never force tests to pass.** Don't change assertions. Don't delete tests. Don't add `skip`. The code is wrong — fix the code.
- **No dead code.** No unused imports or dummy implementations to satisfy a tool.
- **New files need proper structure.** Module docstring, `__all__` exports if pattern exists in the directory, proper imports matching neighbors.
- **New classes need tests.** If you create a new class, create a test file. Match existing test patterns (read `conftest.py` and 2-3 neighboring test files).

### Phase-specific guidance

**Phase A (Production Hardening):** You're hardening existing code. Most changes are small — adding a check, wiring an existing function, creating a plist. Don't over-engineer. Read the existing module, understand what's missing, add the minimum correct code. Split into 2-3 PRs if the diff gets large (API-facing vs daemon/collector).

**Phase B (System Completeness):** You're wiring existing modules to their consumers. The modules work and are tested — your job is to connect them. Do NOT rewrite module internals. ConversationalIntelligence has 971 lines that work — add an endpoint that calls it. Don't refactor its internals. One or two PRs.

**Phase C (Intelligence Expansion):** You're building new modules. Every new module must follow patterns from existing modules in the same directory — read at least 3 before writing. This is the largest phase. Split into 3-4 PRs: adaptive thresholds, notifications, bidirectional integration, (optional) manual validation docs.

**Phase D (Polish):** Cleanup, tests, observability, docs. Nothing critical but must still match patterns. One PR covers everything. If `.tsx` files are created, include prettier in the command block.

---

**Step 7 — Update state, handoff, and session record.**

You must update three files. The next agent depends on all three being correct.

**7a. `audit-remediation/state.json`**
- Set `current_phase` to the NEXT phase (the one after what you just completed).
- If completing phase-d, set `current_phase` to `"all-complete"`.
- Increment `current_session` by 1.
- Mark your phase's status as `"complete"`, set `started_session` and `completed_session`.
- Do NOT update `last_pr` — you don't know the PR number yet.

**7b. `audit-remediation/HANDOFF.md`**
Rewrite this file completely. Do not append — replace the entire contents. Write it for the NEXT agent, not for Molham. Assume your PR will be merged by the time the next agent reads this.

Structure:
```
# HANDOFF -- Audit Remediation

**Generated:** YYYY-MM-DD
**Current Phase:** phase-X (pending) -- next after yours
**Current Session:** N+1
**Track:** Gap remediation (phases A-D)

---

## What Just Happened

### Session NNN -- Phase X: Name
Summary of what you did. Files changed. PR number placeholder: "PR #TBD (branch: branch-name)".

---

## What's Next

### Phase X: Name
- Task count and type
- See `audit-remediation/tasks/PHASE-X-NAME.md`
- Brief description of scope

---

## Key Rules

1. You write code. You never run anything.
2. Commit subject under 72 chars, valid types only
3. "HANDOFF.md removed and rewritten" required in commit body
4. If 20+ deletions, include "Deletion rationale:" in body
5. Match existing patterns obsessively
6. No comments in command blocks
7. [Add any new rules you discovered this session]

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- This brief
2. `audit-remediation/tasks/PHASE-X-NAME.md` -- Next phase task file
3. `audit-remediation/state.json` -- Current project state
4. `CLAUDE.md` -- Repo-level engineering rules
```

**7c. `audit-remediation/sessions/session-NNN.yaml`**
Write the session record with tasks completed, files changed, gaps found.

---

**Step 8 — Generate the command block.**

One copy-paste block for Molham. Real file paths — no placeholders. **No comments in the command block.**

Rules:

- **No comments.** Not a single `#` line. Molham knows what the commands do.
- **Commit subject MUST be under 72 characters.** Count them. A previous agent wrote 87 — rejected.
- **Valid types only:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- First letter after prefix lowercase: `feat: wire` not `feat: Wire`.
- Use `--` not `---` in messages.
- If 20+ lines deleted, body includes `Deletion rationale:`.
- **Commit body MUST include the phrase "HANDOFF.md removed and rewritten".** Non-negotiable. Three agents failed this.
- If .ts/.tsx changed, add prettier before git add.
- Pre-commit and pre-push hooks run automatically. Do not duplicate them with manual commands.

Template:

```bash
cd ~/clawd/moh_time_os
git checkout -b phase-X/short-description
git add path/to/changed1.py path/to/changed2.py audit-remediation/state.json audit-remediation/HANDOFF.md audit-remediation/sessions/session-NNN.yaml
git commit -m "$(cat <<'EOF'
type: short description under 72 chars

What changed and why. HANDOFF.md removed and rewritten for next session.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
git push -u origin phase-X/short-description
gh pr create --title "type: short description" --body "..."
gh pr merge --merge --auto
gh pr checks --watch
```

---

Start at step 1. Your first tool call is Read on `audit-remediation/state.json`.
