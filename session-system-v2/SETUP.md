# Session System Setup Guide

Complete step-by-step instructions for bootstrapping the session system on a new project. This guide covers everything from creating repositories to running your first session.

## Prerequisites

Before starting, ensure you have:

- **GitHub account** with permission to create private repositories
- **GitHub CLI** (`gh`) installed and authenticated
- **Python 3.11+** with PyYAML (`pip install pyyaml`)
- **Understanding** of GitHub Actions, GitHub fine-grained PATs, and branch protection rules
- **git** configured locally with SSH keys or auth configured

## Step 1: Create the Enforcement Repo

The enforcement repo is a private repository that holds blessed (canonical) versions of critical files and runs compliance checks.

### 1.1 Create the Repository

```bash
gh repo create YourOrg/enforcement --private --source=. --remote=origin --push
```

Replace `YourOrg` with your GitHub organization. Make a note of the repo URL: `https://github.com/YourOrg/enforcement`

### 1.2 Bootstrap the Enforcement Repo

Copy the `enforcement-template/` contents into the enforcement repo root:

```bash
# From your session-system-v2 directory
cp -r enforcement-template/* path/to/enforcement-repo/
git -C path/to/enforcement-repo add .
git -C path/to/enforcement-repo commit -m "init: enforcement repo structure"
git -C path/to/enforcement-repo push
```

The enforcement repo should now contain:
- `.github/workflows/enforcement-gate.yml` — Runs compliance checks on PRs
- `.github/workflows/bless.yml` — Workflow to bless (canonicalize) protected files
- `scripts/compare.sh` — Compares project files against blessed versions
- `scripts/restore.sh` — Restores blessed files to project
- `blessed/` — Directory holding canonical versions of protected files (initially empty)
- `protected-files.txt` — List of files under protection (generated after first bless)
- `README.md` — Enforcement repo documentation

### 1.3 Create GitHub Fine-Grained PATs

Create two fine-grained personal access tokens in GitHub:

#### Token 1: ENFORCEMENT_READ_TOKEN

This token is used by the project's CI to clone the enforcement repo and read blessed files.

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Click "Generate new token"
3. **Token name**: `enforcement-read-project-ci`
4. **Repository access**: Select the `enforcement` repo only
5. **Permissions**:
   - `contents`: read-only
   - `metadata`: read-only
6. **Expiration**: Set to 90 days; plan to rotate before expiry
7. Generate and copy the token value
8. Store it securely (you'll add it to the project repo shortly)

#### Token 2: ENFORCEMENT_DISPATCH_TOKEN

This token is used by the project's CI to trigger the enforcement gate workflow.

1. Create another fine-grained token: `enforcement-dispatch-project-ci`
2. **Repository access**: Select the `enforcement` repo
3. **Permissions**:
   - `actions`: read & write (allows workflow dispatch)
   - `contents`: read-only
   - `metadata`: read-only
4. **Expiration**: 90 days
5. Generate and copy the token value

#### Token 3: PROJECT_STATUS_TOKEN (for Enforcement Repo)

This token is used by the enforcement repo's `enforcement-gate.yml` to post commit status checks on the project repo.

1. Create a fine-grained token in your personal account (or shared service account): `project-status-enforcement`
2. **Repository access**: Select the project repo
3. **Permissions**:
   - `checks`: read & write
   - `statuses`: read & write
   - `contents`: read-only (to verify PR is from the right branch)
4. **Expiration**: 90 days
5. Generate and copy the token value
6. Add this to the **enforcement repo** as a secret (see Step 1.4)

### 1.4 Add Secrets to Enforcement Repo

```bash
# Add the PROJECT_STATUS_TOKEN so enforcement workflows can post status
gh secret set PROJECT_STATUS_TOKEN \
  --repo YourOrg/enforcement \
  --body "$(pbpaste)"  # or your method of pasting the token
```

Verify:
```bash
gh secret list --repo YourOrg/enforcement
```

You should see `PROJECT_STATUS_TOKEN` listed.

## Step 2: Set Up the Project Repo

Now set up your main project repository to use the session system.

### 2.1 Copy Core Contents

Copy the `core/` directory into your project root (or subdirectory if your project already has a complex structure):

```bash
# From session-system-v2 directory
cp -r core/* path/to/project-repo/
cd path/to/project-repo
git add .
```

The project repo should now contain:
- `state.json` — Current state machine (phases, PR tracking, session info)
- `plan/index.yaml` — Master plan index
- `plan/phase-template.yaml` — Template for creating phase specs
- `scripts/check_state.py` — Validates state.json consistency
- `scripts/generate_handoff.py` — Generates HANDOFF.md from state.json + phase specs
- `AGENT.md` — Agent instructions (to be customized)
- `HANDOFF.md` — Generated; do not edit by hand

### 2.2 Edit state.json

Open `state.json` and fill in your project details:

```json
{
  "project": "my-product-name",
  "owner": "molham",
  "current_phase": null,
  "current_session": 0,
  "phases": {},
  "last_pr": 0,
  "last_verified": null,
  "enforcement": {
    "repo": "YourOrg/enforcement",
    "read_token_secret": "ENFORCEMENT_READ_TOKEN",
    "dispatch_token_secret": "ENFORCEMENT_DISPATCH_TOKEN",
    "protected_files": []
  }
}
```

- **project**: Short name of your project
- **owner**: GitHub username or team that owns the project
- **enforcement.repo**: Full path to the enforcement repo created in Step 1 (YourOrg/enforcement)
- **enforcement.protected_files**: List of protected files (populated after first bless workflow)

### 2.3 Edit AGENT.md

The `AGENT.md` template in `core/` contains sections for project-specific rules. Customize each section:

**[Project-Specific Rules]**
- List code rules (no MD5, no shell=True, etc.)
- Verification steps (which tests to run, which linters to use)
- Directory structure notes
- Performance constraints

**[Session Discipline]**
- When to read which files
- Phase completion criteria
- Documentation update triggers

Example:
```markdown
## Code Rules

- No `except Exception: pass` — always log and return error results
- No f-string SQL — use parameterized queries
- All API endpoints require timeout= parameter
- Fixtures must be in tests/fixtures/ directory
- Tests must be pytest, no unittest
```

### 2.4 Copy and Edit CI Workflow

Copy the CI workflow template:

```bash
mkdir -p .github/workflows
cp path/to/session-system-v2/enforcement-template/project-ci-template.yml .github/workflows/ci.yml
```

Open `.github/workflows/ci.yml` and replace placeholders:

- `ENFORCEMENT_REPO`: Set to `YourOrg/enforcement`
- `PROTECTED_FILES_PATH`: Path to `protected-files.txt` in enforcement repo (usually `protected-files.txt`)
- `LINT_COMMANDS`: Your ruff, mypy, bandit commands
- `TEST_COMMAND`: Your pytest or test runner command
- `PROJECT_NAME`: From state.json

Example workflow section:
```yaml
name: CI

on: [push, pull_request]

env:
  ENFORCEMENT_REPO: YourOrg/enforcement

jobs:
  restore-blessed:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Clone enforcement repo
        env:
          ENFORCEMENT_READ_TOKEN: ${{ secrets.ENFORCEMENT_READ_TOKEN }}
        run: |
          git clone --depth 1 \
            https://${ENFORCEMENT_READ_TOKEN}@github.com/$ENFORCEMENT_REPO.git \
            .enforcement-tmp
      - name: Restore blessed files
        run: |
          bash .enforcement-tmp/scripts/restore.sh .enforcement-tmp .

  lint:
    needs: restore-blessed
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint with ruff
        run: ruff check .
      - name: Format check with ruff
        run: ruff format --check .
      - name: Security scan with bandit
        run: bandit -r src/ tests/

  test:
    needs: restore-blessed
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: python -m pytest tests/ -x

  dispatch-gate:
    needs: [lint, test]
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Dispatch enforcement gate
        env:
          ENFORCEMENT_DISPATCH_TOKEN: ${{ secrets.ENFORCEMENT_DISPATCH_TOKEN }}
        run: |
          gh workflow run enforcement-gate.yml \
            --repo $ENFORCEMENT_REPO \
            --ref main \
            -f project_repo=${{ github.repository }} \
            -f pr_number=${{ github.event.pull_request.number }} \
            -f token=$ENFORCEMENT_DISPATCH_TOKEN
```

### 2.5 Copy Pre-commit Configuration

Copy the pre-commit config template:

```bash
cp path/to/session-system-v2/enforcement-template/project-precommit-template.yaml .pre-commit-config.yaml
```

Edit to match your tools:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.1
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-c, .bandit]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

### 2.6 Add Repository Secrets

Add the tokens created in Step 1 to your project repo:

```bash
# ENFORCEMENT_READ_TOKEN
gh secret set ENFORCEMENT_READ_TOKEN \
  --repo YourOrg/my-project \
  --body "$(pbpaste)"

# ENFORCEMENT_DISPATCH_TOKEN
gh secret set ENFORCEMENT_DISPATCH_TOKEN \
  --repo YourOrg/my-project \
  --body "$(pbpaste)"
```

Verify:
```bash
gh secret list --repo YourOrg/my-project
```

## Step 3: Create Your Plan

The plan is a sequence of phases that define your work. Each phase is a YAML file describing deliverables, tests, and acceptance criteria.

### 3.1 Edit plan/index.yaml

Open `plan/index.yaml` and define your phases:

```yaml
phases:
  - id: "phase-00"
    title: "Environment & Tooling"
    summary: "Set up CI, pre-commit, typing, and foundational tooling"

  - id: "phase-01"
    title: "Core Data Model"
    summary: "Design and implement the main data structures"

  - id: "phase-02"
    title: "API Layer"
    summary: "Build REST endpoints with proper validation and error handling"

  - id: "phase-03"
    title: "Frontend Integration"
    summary: "Connect UI to API endpoints"

  - id: "phase-04"
    title: "Production Hardening"
    summary: "Logging, monitoring, error handling, docs"
```

### 3.2 Create Phase Specification Files

For each phase in `index.yaml`, create a corresponding `plan/phase-NN.yaml` file. Use `plan/phase-template.yaml` as a starting point:

```yaml
# plan/phase-00.yaml
id: phase-00
title: Environment & Tooling
owner: molham
status: pending
session_created: null
session_completed: null

description: |
  Set up foundational CI/CD infrastructure, pre-commit hooks, type checking,
  and development tooling.

deliverables:
  - name: "GitHub Actions CI workflow"
    files: [".github/workflows/ci.yml"]
    acceptance: "CI passes on all PRs, no manual intervention required"

  - name: "Pre-commit hooks"
    files: [".pre-commit-config.yaml"]
    acceptance: "Pre-commit passes 100% of checks before every commit"

  - name: "Type checking baseline"
    files: ["scripts/check_mypy_baseline.py", "pyproject.toml"]
    acceptance: "mypy strict islands configured, baseline passes"

work:
  steps:
    - "Copy CI template into .github/workflows/ci.yml"
    - "Edit state.json with project name and enforcement repo URL"
    - "Run pre-commit on full codebase"
    - "Configure mypy with strict mode on critical paths"
    - "Commit and create PR"

verification:
  - "Run: `ruff check . && ruff format --check .`"
  - "Run: `python -m pytest tests/ -x`"
  - "Run: `python scripts/check_mypy_baseline.py --strict-only`"
  - "Verify: CI passes on the PR"
  - "Verify: Pre-commit hook passes before commit"

exit_criteria:
  - "CI workflow is live and passing"
  - "Pre-commit configuration is in place"
  - "Type checking baseline established"
  - "All code follows style guide"

notes: |
  This is the foundational phase. Everything else depends on tooling.
  Do not skip verification steps.
```

Create `phase-01.yaml`, `phase-02.yaml`, etc. following the same structure.

### 3.3 Update state.json with Phase List

Add your phases to `state.json`:

```json
{
  "project": "my-product",
  "owner": "molham",
  "current_phase": "phase-00",
  "current_session": 1,
  "phases": {
    "phase-00": {
      "status": "pending",
      "tasks_total": 0,
      "tasks_complete": 0
    },
    "phase-01": {
      "status": "pending",
      "tasks_total": 0,
      "tasks_complete": 0
    }
  },
  "last_pr": 0,
  "last_verified": null,
  "enforcement": {
    "repo": "YourOrg/enforcement",
    "read_token_secret": "ENFORCEMENT_READ_TOKEN",
    "dispatch_token_secret": "ENFORCEMENT_DISPATCH_TOKEN",
    "protected_files": []
  }
}
```

## Step 4: Generate Initial HANDOFF.md

The HANDOFF.md file is generated from state.json and phase specs. Do not edit it by hand.

```bash
cd path/to/project-repo
python scripts/generate_handoff.py
```

This creates or updates `HANDOFF.md` with:
- "What Just Happened" — Empty initially (will populate as PRs merge)
- "What's Next" — Next phase (phase-00) with deliverables and work steps
- "Key Rules" — From AGENT.md
- "Documents to Read" — Pointers to phase spec, AGENT.md, CLAUDE.md

Commit:
```bash
git add plan/ state.json HANDOFF.md AGENT.md .pre-commit-config.yaml .github/workflows/ci.yml
git commit -m "init: session system scaffolding"
git push -u origin main
```

## Step 5: Configure Branch Protection

Protect the main branch to enforce the session system:

```bash
gh repo rule create \
  --repo YourOrg/my-project \
  --type "branch_name_pattern" \
  --pattern "main" \
  --require-status-checks \
  --status-checks "CI" "enforcement-gate" \
  --require-pull-request \
  --dismiss-stale-reviews \
  --require-code-owner-reviews
```

Or use the GitHub web UI:

1. Go to repo → Settings → Rules → Rulesets → New ruleset
2. Name: "Protect main"
3. **Enforcement**: Active
4. **Target branches**: main
5. **Rules** section:
   - Enable "Require status checks to pass" → Add "CI" and "enforcement-gate"
   - Enable "Require pull request before merging"
   - Enable "Dismiss stale pull request approvals when new commits are pushed"
6. Save

## Step 6: Bless Initial Protected Files

Identify files that should be protected (canonical, blessed by project owner only):

```
pyproject.toml               (project metadata, dependencies)
.pre-commit-config.yaml      (tool versions)
.github/workflows/ci.yml     (CI rules)
AGENT.md                     (agent behavior rules)
scripts/check_state.py       (state validation)
scripts/generate_handoff.py  (artifact generation)
```

Run the bless workflow from the enforcement repo:

```bash
gh workflow run bless.yml \
  --repo YourOrg/enforcement \
  -f project_repo="YourOrg/my-project" \
  -f files_to_bless="pyproject.toml,.pre-commit-config.yaml,.github/workflows/ci.yml,AGENT.md,scripts/check_state.py,scripts/generate_handoff.py"
```

This:
1. Clones the project repo at current main
2. Copies the specified files into `blessed/`
3. Adds them to `protected-files.txt`
4. Commits and pushes to enforcement repo

Verify:
```bash
gh repo view YourOrg/enforcement --web  # Check protected-files.txt was created
```

## Step 7: First Session

Your session system is now ready. The agent will:

1. Read `state.json` → determine project, phases, current phase
2. Read `HANDOFF.md` → understand what's next
3. Read `plan/phase-00.yaml` → work steps and acceptance criteria
4. Read `AGENT.md` → code rules and verification procedures
5. Declare intent (e.g., "I will implement phase-00 work: CI setup, pre-commit, typing")
6. Begin work

### Session Flow

```
┌──────────────────────────────────┐
│ 1. Agent reads state.json        │
│    → project name, phases, etc.  │
└──────────────────┬───────────────┘
                   │
┌──────────────────▼───────────────┐
│ 2. Agent reads HANDOFF.md        │
│    → What's next (phase spec)    │
└──────────────────┬───────────────┘
                   │
┌──────────────────▼───────────────┐
│ 3. Agent reads plan/phase-NN.yaml│
│    → Deliverables, work, verify  │
└──────────────────┬───────────────┘
                   │
┌──────────────────▼───────────────┐
│ 4. Agent reads AGENT.md          │
│    → Code rules, verification    │
└──────────────────┬───────────────┘
                   │
┌──────────────────▼───────────────┐
│ 5. Agent declares intent         │
│    → What will be done           │
└──────────────────┬───────────────┘
                   │
┌──────────────────▼───────────────┐
│ 6. Agent works                   │
│    → Code, test, commit, PR      │
└──────────────────┬───────────────┘
                   │
┌──────────────────▼───────────────┐
│ 7. Agent updates docs            │
│    → sessions/session-NNN.yaml    │
│       HANDOFF.md                  │
└──────────────────┬───────────────┘
                   │
┌──────────────────▼───────────────┐
│ 8. Agent gives Molham commit     │
│    → Single command to run       │
└──────────────────────────────────┘
```

---

## System Architecture Diagram

```
┌─────────────────────────────────┐       ┌──────────────────────────────┐
│   PROJECT REPO                  │       │   ENFORCEMENT REPO           │
│                                 │       │   (private)                  │
│  .github/workflows/             │       │  .github/workflows/          │
│    ci.yml                       │       │    enforcement-gate.yml      │
│      ├─ restore blessed files ◄─┼───────│    bless.yml                 │
│      ├─ run lint & tests        │       │                              │
│      └─ dispatch gate workflow ─┼──────►│  blessed/                    │
│                                 │       │    pyproject.toml            │
│  state.json                     │       │    .pre-commit-config.yaml   │
│  plan/                          │       │    ci.yml                    │
│    index.yaml                   │       │    AGENT.md                  │
│    phase-00.yaml                │       │                              │
│    phase-01.yaml                │       │  protected-files.txt         │
│  sessions/                      │       │  scripts/                    │
│    SESSION_LOG.md               │       │    compare.sh                │
│  AGENT.md                       │       │    restore.sh                │
│  HANDOFF.md (generated)         │       │                              │
│  scripts/                       │       │  README.md                   │
│    check_state.py               │       │                              │
│    generate_handoff.py          │       │                              │
└─────────────────────────────────┘       └──────────────────────────────┘
     │                                             ▲
     │ (1) read blessed files                      │
     └─────────────────────────────────────────────┘
```

## Token Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        GITHUB ACTIONS                            │
│                                                                  │
│  Project CI                           Enforcement CI            │
│  ──────────                          ───────────────            │
│                                                                  │
│  Uses ENFORCEMENT_READ_TOKEN         Uses PROJECT_STATUS_TOKEN │
│       ↓                                    ↓                    │
│  Clone enforcement repo          Post commit status on project  │
│  Read blessed files              (pass/fail enforcement gate)   │
│                                                                  │
│  Uses ENFORCEMENT_DISPATCH_TOKEN                                │
│       ↓                                                          │
│  Trigger enforcement-gate.yml workflow                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

Token Scopes:
─────────────

ENFORCEMENT_READ_TOKEN (in project repo)
  Scope: YourOrg/enforcement
  Permissions: contents (read-only), metadata (read-only)
  Used by: Project CI restore-blessed step
  Purpose: Clone enforcement repo, download blessed files

ENFORCEMENT_DISPATCH_TOKEN (in project repo)
  Scope: YourOrg/enforcement
  Permissions: actions (read+write), contents (read-only)
  Used by: Project CI dispatch-gate step
  Purpose: Trigger enforcement-gate.yml workflow on enforcement repo

PROJECT_STATUS_TOKEN (in enforcement repo)
  Scope: YourOrg/my-project
  Permissions: checks (read+write), statuses (read+write)
  Used by: Enforcement CI enforcement-gate.yml
  Purpose: Post commit status checks on project PRs
```

---

## Troubleshooting

### CI fails with "Could not clone enforcement repo"

**Problem**: ENFORCEMENT_READ_TOKEN is invalid, expired, or has insufficient permissions.

**Solution**:
1. Check token expiry: `gh auth token list` (personal access tokens don't show here; check web UI)
2. Regenerate token in GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
3. Update secret: `gh secret set ENFORCEMENT_READ_TOKEN --repo YourOrg/my-project --body "new-token"`

### Enforcement gate workflow doesn't run

**Problem**: PROJECT_STATUS_TOKEN missing or dispatch failing.

**Solution**:
1. Verify token exists in enforcement repo: `gh secret list --repo YourOrg/enforcement`
2. Check CI workflow syntax: `gh workflow view ci.yml --repo YourOrg/my-project`
3. Verify enforcement repo has `enforcement-gate.yml`: `gh workflow list --repo YourOrg/enforcement`

### Pre-commit hook fails but CI passes

**Problem**: Pre-commit version differs from CI version, or local Python differs from CI.

**Solution**:
1. Ensure `.pre-commit-config.yaml` pins exact versions (e.g., `rev: v0.15.1`)
2. Update local pre-commit: `pre-commit autoupdate`
3. Run: `pre-commit run -a`

### Protected file was modified but CI passed

**Problem**: CI "restore blessed files" step didn't run before lint/test, or enforcement gate is not configured as a required status check.

**Solution**:
1. Verify CI workflow: restore-blessed job must run first (before lint/test jobs)
2. Check job dependencies: `needs: restore-blessed`
3. Add enforcement-gate to branch protection required status checks
4. Re-run CI: `gh workflow run ci.yml --repo YourOrg/my-project -r main`

### State file is out of sync

**Problem**: Phases in state.json don't match plan/ directory, or phase status is inconsistent.

**Solution**:
1. Run validator: `python scripts/check_state.py`
2. Fix state.json manually or update phase files
3. Regenerate HANDOFF.md: `python scripts/generate_handoff.py`
4. Commit: `git add state.json plan/ HANDOFF.md && git commit -m "fix: state consistency"`

---

## Next Steps

1. Complete all 7 steps above
2. Verify enforcement repo has `protected-files.txt` with blessed file list
3. Create a test PR (any small change) and verify CI passes and enforcement-gate posts status
4. Read HANDOFF.md generated by step 4
5. Begin Phase 0 work

The system is now ready for multi-session development with full context preservation and compliance enforcement.
