#!/usr/bin/env python3
"""
Brief 13: Security Hardening — Validation Script (SH-5.1)

Validates all deliverables from Brief 13:
- SH-1.1: API key management (multi-key, hashed, CLI)
- SH-2.1: Role-based endpoint scoping (viewer/operator/admin)
- SH-3.1: Rate limiting + CORS + CSP headers
- SH-4.1: Credential audit (no hardcoded secrets)
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def run_tests(test_files: list[str]) -> tuple[int, int]:
    """Run pytest on given files, return (passed, failed)."""
    cmd = [sys.executable, "-m", "pytest"] + test_files + ["-q", "--tb=no"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE))
    output = result.stdout + result.stderr
    passed = failed = 0
    for line in output.split("\n"):
        if "passed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed":
                    try:
                        passed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
                if p == "failed":
                    try:
                        failed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
    return passed, failed


def main() -> int:
    global PASS, FAIL

    print("=" * 60)
    print("Brief 13: Security Hardening — Validation")
    print("=" * 60)

    # Check 1: API Key Management (SH-1.1)
    print("\n1. API Key Management (SH-1.1)")
    km = BASE / "lib" / "security" / "key_manager.py"
    cli = BASE / "scripts" / "manage_keys.py"
    auth = BASE / "api" / "auth.py"

    check("key_manager.py exists", km.exists())
    check("manage_keys.py CLI exists", cli.exists())
    if km.exists():
        code = km.read_text()
        check("Uses SHA-256 hashing", "sha256" in code or "hashlib" in code)
        check("Uses secrets module", "secrets" in code)
        check("Has mtos_ prefix", "mtos_" in code)
        check("Has KeyRole enum", "KeyRole" in code or "Role" in code)
        check("Has create_key method", "create_key" in code)
        check("Has validate_key method", "validate_key" in code)
        check("Has revoke_key method", "revoke_key" in code)
        check("Has rotate_key method", "rotate_key" in code)
    if auth.exists():
        code = auth.read_text()
        check(
            "auth.py has multi-key support", "key_manager" in code.lower() or "KeyManager" in code
        )
        check("auth.py sets role in state", "request.state" in code)

    # Check 2: Role-Based Scoping (SH-2.1)
    print("\n2. Role-Based Scoping (SH-2.1)")
    rbac = BASE / "lib" / "security" / "rbac.py"
    middleware = BASE / "lib" / "security" / "middleware.py"

    check("rbac.py exists", rbac.exists())
    check("middleware.py exists", middleware.exists())
    if rbac.exists():
        code = rbac.read_text()
        check("Has Role enum", "Role" in code)
        check("Has VIEWER role", "VIEWER" in code or "viewer" in code)
        check("Has OPERATOR role", "OPERATOR" in code or "operator" in code)
        check("Has ADMIN role", "ADMIN" in code or "admin" in code)
        check("Has require_role", "require_role" in code)
        check("Has check_permission", "check_permission" in code)

    # Check 3: Rate Limiting + CORS (SH-3.1)
    print("\n3. Rate Limiting + CORS + CSP (SH-3.1)")
    rl = BASE / "lib" / "security" / "rate_limiter.py"
    hd = BASE / "lib" / "security" / "headers.py"

    check("rate_limiter.py exists", rl.exists())
    check("headers.py exists", hd.exists())
    if rl.exists():
        code = rl.read_text()
        check("Has RateLimiter class", "RateLimiter" in code)
        check("Thread-safe (Lock)", "Lock" in code)
        check("Has sliding window", "window" in code.lower())
    if hd.exists():
        code = hd.read_text()
        check("Has CORS config", "cors" in code.lower() or "CORS" in code)
        check("Has CSP header", "Content-Security-Policy" in code or "csp" in code.lower())
        check("Has HSTS", "Strict-Transport-Security" in code)
        check("Has X-Frame-Options", "X-Frame-Options" in code)

    # Check 4: Credential Audit (SH-4.1)
    print("\n4. Credential Audit (SH-4.1)")
    audit = BASE / "scripts" / "audit_credentials.py"
    secrets = BASE / "lib" / "security" / "secrets_config.py"
    env_example = BASE / ".env.example"

    check("audit_credentials.py exists", audit.exists())
    check("secrets_config.py exists", secrets.exists())
    check(".env.example exists", env_example.exists())
    if secrets.exists():
        code = secrets.read_text()
        check("Has validate_secrets", "validate_secrets" in code)
        check("Has mask_secret", "mask_secret" in code)
    if env_example.exists():
        env = env_example.read_text()
        check(".env.example has INTEL_API_TOKEN", "INTEL_API_TOKEN" in env)
        check(".env.example has DATABASE_PATH", "DATABASE_PATH" in env)

    # Check 5: Server Integration
    print("\n5. Server Integration")
    server = BASE / "api" / "server.py"
    if server.exists():
        code = server.read_text()
        check("Server has rate limiter", "rate_limiter" in code.lower() or "RateLimiter" in code)
        check(
            "Server has security headers",
            "SecurityHeaders" in code or "security_headers" in code.lower(),
        )

    # Check 6: Test Suite
    print("\n6. Test Suite")
    test_files = [
        "tests/test_key_manager.py",
        "tests/test_rbac.py",
        "tests/test_rate_limiter.py",
        "tests/test_security_headers.py",
        "tests/test_credential_audit.py",
    ]
    existing = [f for f in test_files if (BASE / f).exists()]
    check("All 5 test files exist", len(existing) == 5, f"{len(existing)}/5")

    if existing:
        passed, failed = run_tests(existing)
        check("All Brief 13 tests pass", failed == 0, f"{passed} passed, {failed} failed")
        check("Test count >= 150", passed >= 150, f"{passed} tests")

    # Check 7: Run credential audit
    print("\n7. Credential Audit Scan")
    if audit.exists():
        result = subprocess.run(
            [sys.executable, str(audit)], capture_output=True, text=True, cwd=str(BASE)
        )
        check(
            "Credential audit passes",
            result.returncode == 0,
            "no hardcoded secrets" if result.returncode == 0 else "issues found",
        )

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} checks passed")
    if FAIL == 0:
        print("STATUS: ✅ ALL CHECKS PASSED — Brief 13 VALIDATED")
    else:
        print(f"STATUS: ❌ {FAIL} CHECK(S) FAILED")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
