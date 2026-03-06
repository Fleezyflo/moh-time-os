# Enforcement Repo Template

This directory bootstraps a private enforcement repository that has compliance authority over your project repo. The project cannot modify its own protected files — this repo holds the canonical (blessed) versions and gates every PR.

## How It Works

1. **Protected files** (e.g., `pyproject.toml`, `.pre-commit-config.yaml`, `ci.yml`) have blessed copies stored in `blessed/`.
2. **Every project CI job** clones this repo and restores blessed copies before running checks. The project branch's version of protected files is overwritten — CI always runs against blessed.
3. **On every PR**, the project dispatches an `enforcement-check` event to this repo. The enforcement gate compares the PR's protected files against blessed and posts a pass/fail status.
4. **If files differ**, the PR cannot merge (branch protection requires the `enforcement-gate` status).
5. **To legitimately change a protected file**, an admin runs the `bless.yml` workflow, which copies the new version from the project into `blessed/` and updates `protected-files.txt`.

## Directory Structure

```
.github/workflows/
  enforcement-gate.yml    # Compares PR files against blessed, posts status
  bless.yml               # Updates blessed copies when legitimate changes are made
blessed/                  # Canonical versions of protected files
  pyproject.toml          # (populated after first bless)
  .pre-commit-config.yaml
  ...
scripts/
  compare.sh              # File comparison logic (used by enforcement-gate)
  restore.sh              # Restores blessed files (distributed to project CI)
  init-enforcement.sh     # One-time bootstrap for new enforcement repos
protected-files.txt       # Registry of protected file paths
```

## Setup

### Quick Start

```bash
# 1. Create a new private repo (e.g., YourOrg/enforcement)
# 2. Clone it
git clone git@github.com:YourOrg/enforcement.git
cd enforcement

# 3. Copy this template into it
cp -r /path/to/enforcement-template/* .
cp -r /path/to/enforcement-template/.github .

# 4. Run the bootstrap script
bash scripts/init-enforcement.sh

# 5. Commit and push
git add -A && git commit -m "chore: bootstrap enforcement repo"
git push
```

### Tokens Required

Three fine-grained Personal Access Tokens (PATs) are needed:

| Token | Stored In | Scopes | Purpose |
|-------|-----------|--------|---------|
| `ENFORCEMENT_READ_TOKEN` | Project repo secrets | Read access to enforcement repo | Project CI clones enforcement to get blessed files |
| `ENFORCEMENT_DISPATCH_TOKEN` | Project repo secrets | Workflow dispatch on enforcement repo | Project CI triggers enforcement gate check |
| `PROJECT_STATUS_TOKEN` | Enforcement repo secrets | Commit statuses + PR comments on project repo | Enforcement gate posts pass/fail to project PR |

### Branch Protection

On the **project repo**, configure branch protection for `main`:

- Require status checks: all CI jobs + `enforcement-gate`
- Require PR before merging
- No direct pushes

This ensures no code reaches main without passing both project CI (running against blessed files) and the enforcement gate (verifying files match blessed).

## Workflows

### enforcement-gate.yml

Triggered by `repository_dispatch` from project CI. Receives the project repo, PR number, branch, and commit SHA. Compares each file listed in `protected-files.txt` against its blessed copy. Posts a commit status (`enforcement-gate` context) on the project PR.

### bless.yml

Triggered manually (`workflow_dispatch`) by repo admins. Inputs: project repo, branch, file list, and reason. Clones the project at the specified branch, copies listed files to `blessed/`, updates `protected-files.txt`, and commits with full audit trail.

## Scripts

### compare.sh

Compares a project checkout against blessed copies. Used by `enforcement-gate.yml`.

```bash
./scripts/compare.sh /path/to/project-clone ./blessed ./protected-files.txt
```

Exit 0 if all files match. Exit 1 if any differ or are missing.

### restore.sh

Restores blessed copies into a project checkout. Distributed to project repos and used by their CI.

```bash
./scripts/restore.sh /path/to/enforcement-clone /path/to/project
```

### init-enforcement.sh

One-time bootstrap that creates the directory structure and initial files.

```bash
bash scripts/init-enforcement.sh
```

## Security Model

- The enforcement repo is **private**. Only authorized users can see or modify blessed copies.
- The project repo **cannot modify** the enforcement repo. It can only read (via `ENFORCEMENT_READ_TOKEN`) and dispatch events (via `ENFORCEMENT_DISPATCH_TOKEN`).
- Blessing requires **admin access** to the enforcement repo. The `bless.yml` workflow creates a full audit trail (who blessed, when, why, which files).
- Even if an agent modifies a protected file in a PR branch, CI uses the blessed version (restore step) and the enforcement gate blocks the merge (comparison step). Defense in depth.
