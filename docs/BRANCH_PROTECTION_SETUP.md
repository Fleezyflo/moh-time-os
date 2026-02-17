# GitHub Rulesets Configuration

This repository uses **GitHub Rulesets** (not legacy branch protection rules) for repository protection.

**Key advantage:** Rulesets with empty bypass lists cannot be overridden by admins without first editing the ruleset — which itself is an auditable action.

## ⚠️ Personal Repo Limitation

**Current status:** This repo is owned by a personal account (`Fleezyflo`), not a GitHub Organization.

**Impact:** Org-level required workflows are NOT available. This means:
- Someone with admin access COULD delete the CI workflow file
- They could then merge without CI checks running

**Current mitigations:**
1. **Ruleset 4 (Workflow Protection)** — requires PR + approval to modify `.github/`
2. **CODEOWNERS** — `.github/` changes require code owner review
3. **Audit trail** — all changes are logged in git history

**Recommended:** Move this repo to a GitHub Organization to enable:
- Org-level required workflows (can't be deleted by repo admins)
- Org-level rulesets (managed centrally)
- Enterprise audit logging

See: [Org-Level Required Workflow Setup](#org-level-required-workflow-for-organizations)

## Setup

```bash
# Configure all rulesets
./scripts/setup_github_rulesets.sh

# Verify configuration
./scripts/verify_github_rulesets.sh
```

## ⚠️ Enterprise-Only Features

The following rulesets require **GitHub Enterprise** and are NOT available on free/personal repos:

| Ruleset | Feature Required | Status |
|---------|------------------|--------|
| Workflow Protection | `file_path_restriction` | ❌ Not available |
| Sensitive File Gate | Push rulesets | ❌ Not available |
| Config Protection | `file_path_restriction` | ❌ Not available |

**Mitigations on free plans:**
- CODEOWNERS + code owner review requirement covers `.github/` and `config/`
- Pre-commit hooks block `.db`, `.env`, `*-full.json` locally
- CI checks for forbidden file patterns

**Successfully created rulesets (3 of 6):**
- ✅ Main Gate (branch protection for main)
- ✅ Sandbox Guard (sandbox/** branches)
- ✅ Tag Protection (v* tags)

## Configured Rulesets

### 1. Main Gate (branch: main)

**Targets:** `refs/heads/main`
**Enforcement:** Active
**Bypass Actors:** None (not even admins)

| Rule | Setting |
|------|---------|
| Require pull request | ✓ |
| Min approvals | 1 |
| Dismiss stale reviews | ✓ |
| Require code owner review | ✓ |
| Require last push approval | ✓ |
| Require conversation resolution | ✓ |
| Require signed commits | ✓ |
| Require linear history | ✓ |
| Block force pushes | ✓ |
| Block deletions | ✓ |

**Required Status Checks (strict):**
- `pre-commit`
- `python-guards`
- `security-scan`
- `route-integrity`
- `ratchet`
- `test`
- `build-ui`

### 2. Sandbox Guard (branches: sandbox/**)

**Targets:** `refs/heads/sandbox/**`
**Enforcement:** Active
**Bypass Actors:** None

| Rule | Setting |
|------|---------|
| Require pull request | ✗ (direct push allowed) |
| Block force pushes | ✓ (preserve audit trail) |
| Block deletions | ✓ |

**Required Status Checks:**
- `Sandbox Security` (from sandbox-guard.yml — P0 security only)

### 3. Tag Protection (tags: v*)

**Targets:** `refs/tags/v*`
**Enforcement:** Active
**Bypass Actors:** None

| Rule | Setting |
|------|---------|
| Restrict tag creation | ✓ |
| Block tag deletion | ✓ |
| Block force push | ✓ |

### 4. Workflow Protection (paths: .github/**)

**Targets:** All branches
**Restricted Paths:** `.github/**`
**Enforcement:** Active
**Bypass Actors:** None

| Rule | Setting |
|------|---------|
| Require pull request | ✓ |
| Min approvals | 1 |
| Require code owner review | ✓ |

**Purpose:** Prevents editing CI workflows to remove checks and then merging.

### 5. Sensitive File Gate (push restriction)

**Targets:** All branches (push ruleset)
**Enforcement:** Active
**Bypass Actors:** None

**Blocked file patterns:**
- `**/*.db`, `**/*.sqlite`, `**/*.sqlite3`
- `**/*.pem`, `**/*.key`, `**/*.p12`
- `**/sa-*.json`
- `**/.env`, `**/.env.*`
- `**/*-full.json`

**Purpose:** Files matching these patterns are rejected at push time — they never even land in the repo.

### 6. Config Protection (paths: config/**)

**Targets:** All branches
**Restricted Paths:** `config/**`
**Enforcement:** Active
**Bypass Actors:** None

| Rule | Setting |
|------|---------|
| Require pull request | ✓ |
| Min approvals | 1 |

**Purpose:** Prevents secrets from being added to config files without review.

## Verification

```bash
# List all rulesets
gh api repos/{owner}/{repo}/rulesets

# Verify specific ruleset
gh api repos/{owner}/{repo}/rulesets/{id}

# Run verification script
./scripts/verify_github_rulesets.sh
```

## Why Rulesets Over Branch Protection?

| Feature | Branch Protection | Rulesets |
|---------|------------------|----------|
| Path-based rules | ✗ | ✓ |
| Push restrictions | Limited | ✓ |
| Org-level deployment | ✗ | ✓ |
| Admin bypass prevention | Weak | Strong |
| Audit trail | Basic | Detailed |
| Tag protection | Limited | Full |

## Emergency Procedures

**There are no emergency bypasses.** This is intentional.

If an emergency requires immediate deployment:

1. **DO NOT** modify rulesets to add bypass actors
2. Create a hotfix branch: `hotfix/YYYY-MM-DD-description`
3. Get expedited review from a CODEOWNER
4. Ensure all CI checks pass (they're there for a reason)
5. Merge via normal PR process
6. Document the incident

**Philosophy:** If CI is blocking a fix, the fix is probably wrong. If CI itself is broken, fix CI first.

## Audit

All ruleset modifications are logged in GitHub's audit log:

```bash
# View recent ruleset changes (requires org admin)
gh api /orgs/{org}/audit-log --jq '.[] | select(.action | startswith("repo.ruleset"))'
```

## Troubleshooting

### "Ruleset not found"

```bash
# Re-run setup
./scripts/setup_github_rulesets.sh
```

### "Status check not found"

Ensure CI workflow job names match exactly:
- Job `name:` field must match (not the job key)
- Check `.github/workflows/ci.yml` for correct names

### "Push rejected by ruleset"

The Sensitive File Gate is working correctly. Do not commit:
- Database files
- Private keys
- Service account files
- Environment files
- Data dumps

Remove the file from your commit and try again.

---

## Org-Level Required Workflow (for Organizations)

If/when this repo moves to a GitHub Organization, register the org-level security workflow:

### 1. The Workflow File

`.github/workflows/org-required-security.yml` is already created and includes:
- Semgrep security scan
- detect-secrets scan
- Banned file pattern check

### 2. Register as Org-Level Required Workflow

```bash
# Create the org ruleset with required workflow
gh api /orgs/{ORG_NAME}/rulesets -X POST --input - << 'EOF'
{
  "name": "Org Security Gate",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    },
    "repository_name": {
      "include": ["~ALL"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "workflows",
      "parameters": {
        "workflows": [
          {
            "path": ".github/workflows/org-required-security.yml",
            "repository_id": {REPO_ID},
            "ref": "refs/heads/main"
          }
        ]
      }
    }
  ]
}
EOF
```

### 3. Get the Repository ID

```bash
gh api repos/{ORG}/{REPO} --jq '.id'
```

### 4. The Non-Bypassable Chain

Once configured:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROTECTION CHAIN                             │
├─────────────────────────────────────────────────────────────────┤
│ 1. Rulesets block merge without CI passing                      │
│    └─ Bypass list: EMPTY                                        │
│                                                                 │
│ 2. CI can't be modified without PR + approval                   │
│    └─ Ruleset 4: Workflow Protection                            │
│    └─ CODEOWNERS: .github/ requires review                      │
│                                                                 │
│ 3. Even if repo CI deleted, ORG workflow still runs             │
│    └─ Org-level required workflow (can't be repo-deleted)       │
│    └─ Managed at org level, not repo level                      │
│                                                                 │
│ 4. No bypass actors anywhere                                    │
│    └─ Even org admins must edit ruleset first                   │
│    └─ Ruleset edits are audit-logged                            │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Why This Matters

| Scenario | Without Org Workflow | With Org Workflow |
|----------|---------------------|-------------------|
| Admin deletes CI file | Can merge unprotected | Org workflow still blocks |
| Admin force pushes | Blocked by ruleset | Blocked by ruleset |
| Admin bypasses checks | Empty bypass list | Empty bypass list |
| Admin edits ruleset | Audit logged | Audit logged |

The org-level workflow is the **last line of defense** against a malicious (or compromised) admin.
