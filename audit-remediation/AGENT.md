# AGENT.md — MOH Time OS Audit Remediation

You have five tools: **Read, Write, Edit, Glob, Grep.** That is all. You have no Bash, no terminal, no shell. You cannot run any command — not `git`, `ruff`, `pytest`, `python`, `pip`, `npx`, or anything else. A previous agent tried `pip install ruff`, `python -m ruff`, `.venv/bin/ruff` — all violations, session nearly rejected. Do not repeat this.

You generate a command block. Molham runs it on his Mac.

Follow the steps below in order. Do not skip ahead.

---

**Step 1 — Read `audit-remediation/state.json`.**
Find your current phase and session number. This is your first tool call.

---

**Step 2 — Read `audit-remediation/HANDOFF.md`.**
What happened last session. What's next. Lessons learned by previous agents.

---

**Step 3 — Read `audit-remediation/plan/phase-NN.yaml`.**
NN = your current phase from state.json. These are your tasks.

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

**Step 6 — Do the work.**

Write or edit code using Read, Edit, Write, Glob, Grep only.

Rules that apply here — break any and the session is rejected:

- **Match existing patterns.** Your code must look like it was written by the same person who wrote the neighboring modules. If you introduce a new pattern, you failed step 5.
- **Never bypass a check.** No `noqa`, `nosec`, `# type: ignore`, `# pragma: no cover`, `|| true`, `--no-verify`. Fix the code. Can't fix it? Stop and tell Molham.
- **Never force tests to pass.** Don't change assertions. Don't delete tests. Don't add `skip`. The code is wrong — fix the code.
- **No dead code.** No unused imports or dummy implementations to satisfy a tool.

For verification phases (07-13), step 6 is reporting, not coding. For each task produce:
- **DONE** — works as specified. State what you verified and where.
- **GAP** — what's missing, severity (critical/high/medium/low), what should fix it.

Do not fix gaps inline. Document them.

---

**Step 7 — Update state, handoff, and session record.**

You must update three files. The next agent depends on all three being correct.

**7a. `audit-remediation/state.json`**
- Set `current_phase` to the NEXT phase (the one after what you just completed).
- Increment `current_session` by 1.
- Mark your phase's status as `"complete"`, set `completed_session`.
- Do NOT update `last_pr` — you don't know the PR number yet.

**7b. `audit-remediation/HANDOFF.md`**
Rewrite this file completely. Do not append — replace the entire contents. Write it for the NEXT agent, not for Molham. Assume your PR will be merged by the time the next agent reads this.

Structure:
```
# HANDOFF -- Audit Remediation

**Generated:** YYYY-MM-DD
**Current Phase:** phase-NN (pending) -- next after yours
**Current Session:** N+1
**Track:** T1/T2 status

---

## What Just Happened

### Session NNN -- Phase NN: Name
Summary of what you did. Files changed. Test results. PR number placeholder: "PR #TBD (branch: branch-name)".

---

## What's Next

### Phase NN: Name
- Task count and type
- See `audit-remediation/plan/phase-NN.yaml`
- Brief description of scope

---

## Key Rules

1. Never run git from sandbox (creates .git/index.lock)
2. Never format from sandbox (ruff version mismatch)
3. [Add any new rules you discovered this session]

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- Engineering standards
2. `audit-remediation/plan/phase-NN.yaml` -- Next phase
3. `audit-remediation/state.json` -- Current project state
4. `CLAUDE.md` -- Repo-level engineering rules
```

**7c. `audit-remediation/sessions/session-NNN.yaml`**
Write the session record with tasks completed, files changed, gaps found.

---

**Step 8 — Generate the command block.**

One copy-paste block for Molham. Real file paths — no placeholders.

Rules that apply here:

- **Commit subject MUST be under 72 characters.** `type: description` total. Count them. A previous agent wrote 87 — rejected. If yours is too long, shorten it before outputting.
- **Valid types only:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. A previous agent used `verify:` — rejected. Verification phases use `chore:`.
- First letter after prefix lowercase: `feat: wire` not `feat: Wire`.
- Use `--` not `---` in messages.
- If 20+ lines deleted, body includes `Deletion rationale:`.
- If .ts/.tsx changed, add prettier before git add.
- **Do not narrow verification scope.** The repo has pre-commit hooks (ruff, format, bandit, yaml, json, secrets, OpenAPI sync, system map sync) and a 7-gate pre-push hook (ruff lint, ruff format, fast tests, mypy, secrets, UI typecheck, guardrails). These run automatically on commit and push. Do not duplicate them with manual commands. Do not scope checks to only changed files — the hooks run full scope and will catch everything.

```bash
cd ~/clawd/moh_time_os

# Full test suite -- all directories
python -m pytest tests/contract/ tests/test_safety.py tests/negative/ tests/golden/ tests/ui_spec_v21/ tests/property/ tests/scenarios/ tests/test_features.py tests/test_audit.py tests/cassettes/ -x

# Commit (pre-commit hooks run automatically: ruff, format, bandit, yaml, json, secrets, OpenAPI sync, system map sync)
git checkout -b branch-name
git add path/to/changed1.py path/to/changed2.py audit-remediation/state.json audit-remediation/HANDOFF.md audit-remediation/sessions/session-NNN.yaml
git commit -m "$(cat <<'EOF'
chore: short description under 72 chars

What changed and why.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Push (7-gate pre-push runs automatically: ruff, format, fast tests, mypy, secrets, UI typecheck, guardrails)
git push -u origin branch-name
gh pr create --title "type: short description" --body "..."
gh pr merge --merge --auto
gh pr checks --watch
```

---

Start at step 1. Your first tool call is Read on `audit-remediation/state.json`.
