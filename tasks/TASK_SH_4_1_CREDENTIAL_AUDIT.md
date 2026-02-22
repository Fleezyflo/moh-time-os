# SH-4.1: Credential Audit & Secure Storage

## Objective
Audit the entire codebase for hardcoded secrets, ensure all credentials use env vars or encrypted config, and document the credential inventory.

## Context
Brief 7 (PH-4.2) extracts hardcoded config values, but doesn't specifically audit for security-sensitive credentials. This task goes deeper: API tokens, OAuth secrets, webhook URLs, database paths — every secret must be in env vars with no fallback to hardcoded values.

## Implementation

### Audit Targets
Grep for and remediate:
```bash
# Patterns to find
grep -rn "password\|secret\|token\|api_key\|webhook_url\|credentials" lib/ api/ --include="*.py"
grep -rn "Bearer \|sk-\|xoxb-\|ghp_\|gho_" lib/ api/ --include="*.py"
grep -rn "localhost:.*@\|://.*:.*@" lib/ api/ --include="*.py"  # connection strings
```

### Credential Inventory Document
```markdown
| Credential | Source | Env Var | Required | Rotation |
|------------|--------|---------|----------|----------|
| API auth token | SH-1.1 | (DB-managed) | Yes | Via CLI |
| Asana PAT | Asana API | ASANA_PAT | Yes | Manual |
| Google OAuth | Gmail/Cal/Chat | GOOGLE_CREDENTIALS_PATH | Yes | OAuth refresh |
| Xero OAuth | Xero API | XERO_CLIENT_ID, XERO_CLIENT_SECRET | Yes | OAuth refresh |
| GChat webhook | Notifications | MOH_GCHAT_WEBHOOK_URL | Yes | Manual |
| DB path | SQLite | MOH_DB_PATH | No (default) | N/A |
```

### .env.example
Create a template `.env.example` (no real values) documenting every required env var:
```bash
# MOH Time OS Configuration
INTEL_API_TOKEN=        # Deprecated: use API key management (SH-1.1)
ASANA_PAT=              # Asana Personal Access Token
GOOGLE_CREDENTIALS_PATH= # Path to Google OAuth credentials JSON
XERO_CLIENT_ID=         # Xero OAuth client ID
XERO_CLIENT_SECRET=     # Xero OAuth client secret
MOH_GCHAT_WEBHOOK_URL=  # Google Chat webhook for notifications
MOH_DB_PATH=data/moh_time_os.db  # SQLite database path
MOH_DASHBOARD_ORIGIN=http://localhost:8080  # CORS allowed origin
```

### Gitignore Verification
Ensure `.env`, `credentials.json`, `token.json`, `*.pem`, `*.key` are all in `.gitignore`.

## Validation
- [ ] Zero hardcoded secrets found in grep audit
- [ ] Credential inventory document complete
- [ ] .env.example created with all required vars
- [ ] .gitignore blocks all sensitive file patterns
- [ ] Application starts correctly with only env vars (no inline secrets)
- [ ] Missing required env var → clear error message (not silent fallback)

## Files Modified
- Multiple lib/ and api/ files — remove any hardcoded credentials
- New: `.env.example`
- `.gitignore` — verify entries

## Estimated Effort
Medium — audit + remediation across codebase
