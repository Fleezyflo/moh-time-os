# TASK: Verify SH-4.1, SH-5.1 (credential audit, security validation)
> Brief: AUDIT_VERIFICATION | Priority: P3 | Sequence: P3.21 | Status: PENDING

## Instructions
1. Read `tasks/TASK_SH_4_1_CREDENTIAL_AUDIT.md`
2. `grep -rn 'password\|secret\|api_key\|token' lib/ api/ --include="*.py"` — find hardcoded credentials
3. Verify all credentials use env vars
4. Run `bandit -r lib/ api/ -f json` and count findings
5. Read `tasks/TASK_SH_5_1_SECURITY_VALIDATION.md` — comprehensive security validation
6. Check `lib/security/secrets_config.py` — has 0 imports, may be dead code

## Acceptance Criteria
- [ ] Credential audit report: all env var based or GAP
- [ ] Bandit findings count
- [ ] secrets_config.py status (used or dead)
