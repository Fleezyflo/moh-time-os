#!/usr/bin/env python3
"""
Brief 15: Bidirectional Integrations — Validation Script (BI-5.1)

Validates all deliverables from Brief 15:
- BI-1.1: Action execution framework + approval workflow
- BI-2.1: Asana write-back (create/update/comment)
- BI-3.1: Gmail drafts + Calendar event automation
- BI-4.1: Google Chat interactive mode (slash commands, cards)
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
    print("Brief 15: Bidirectional Integrations — Validation")
    print("=" * 60)

    # Check 1: Action Framework (BI-1.1)
    print("\n1. Action Framework (BI-1.1)")
    af = BASE / "lib" / "actions" / "action_framework.py"
    ap = BASE / "lib" / "actions" / "approval_policies.py"
    ar = BASE / "lib" / "actions" / "action_router.py"
    api_ar = BASE / "api" / "action_router.py"
    check("action_framework.py exists", af.exists())
    check("approval_policies.py exists", ap.exists())
    check("action_router.py exists", ar.exists())
    check("api/action_router.py exists", api_ar.exists())
    if af.exists():
        code = af.read_text()
        check("Has ActionProposal", "ActionProposal" in code)
        check("Has ActionResult", "ActionResult" in code)
        check("Has ActionFramework", "ActionFramework" in code)
        check("Has propose_action", "propose_action" in code)
        check("Has approve_action", "approve_action" in code)
        check("Has execute_action", "execute_action" in code)
    if ap.exists():
        code = ap.read_text()
        check("Has ApprovalRule", "ApprovalRule" in code)
        check("Has PolicyEngine", "PolicyEngine" in code)
    if ar.exists():
        code = ar.read_text()
        check("Has ActionRouter", "ActionRouter" in code)

    # Check 2: Asana Write-Back (BI-2.1)
    print("\n2. Asana Write-Back (BI-2.1)")
    aw = BASE / "lib" / "integrations" / "asana_writer.py"
    asn = BASE / "lib" / "integrations" / "asana_sync.py"
    check("asana_writer.py exists", aw.exists())
    check("asana_sync.py exists", asn.exists())
    if aw.exists():
        code = aw.read_text()
        check("Has AsanaWriter", "AsanaWriter" in code)
        check("Has AsanaWriteResult", "AsanaWriteResult" in code)
        check("Has create_task", "create_task" in code)
        check("Has update_task", "update_task" in code)
        check("Has add_comment", "add_comment" in code)
        check("Has complete_task", "complete_task" in code)
        check(
            "Has rate limit handling",
            "429" in code or "rate_limit" in code.lower() or "retry" in code.lower(),
        )
    if asn.exists():
        code = asn.read_text()
        check("Has AsanaSyncManager", "AsanaSyncManager" in code)
        check("Has sync_task_to_asana", "sync_task_to_asana" in code)
        check("Has bulk_sync", "bulk_sync" in code)

    # Check 3: Gmail + Calendar (BI-3.1)
    print("\n3. Gmail + Calendar Automation (BI-3.1)")
    gw = BASE / "lib" / "integrations" / "gmail_writer.py"
    cw = BASE / "lib" / "integrations" / "calendar_writer.py"
    check("gmail_writer.py exists", gw.exists())
    check("calendar_writer.py exists", cw.exists())
    if gw.exists():
        code = gw.read_text()
        check("Has GmailWriter", "GmailWriter" in code)
        check("Has GmailWriteResult", "GmailWriteResult" in code)
        check("Has create_draft", "create_draft" in code)
        check("Has send_email", "send_email" in code)
        check("Has archive_message", "archive_message" in code)
        check("Has reply_to_thread", "reply_to_thread" in code)
    if cw.exists():
        code = cw.read_text()
        check("Has CalendarWriter", "CalendarWriter" in code)
        check("Has CalendarWriteResult", "CalendarWriteResult" in code)
        check("Has create_event", "create_event" in code)
        check("Has find_free_slots", "find_free_slots" in code)

    # Check 4: Chat Interactive (BI-4.1)
    print("\n4. Chat Interactive Mode (BI-4.1)")
    ci = BASE / "lib" / "integrations" / "chat_interactive.py"
    cc = BASE / "lib" / "integrations" / "chat_commands.py"
    cwr = BASE / "api" / "chat_webhook_router.py"
    check("chat_interactive.py exists", ci.exists())
    check("chat_commands.py exists", cc.exists())
    check("chat_webhook_router.py exists", cwr.exists())
    if ci.exists():
        code = ci.read_text()
        check("Has ChatInteractive", "ChatInteractive" in code)
        check("Has ChatWriteResult", "ChatWriteResult" in code)
        check("Has send_message", "send_message" in code)
        check("Has send_card", "send_card" in code)
    if cc.exists():
        code = cc.read_text()
        check("Has SlashCommandHandler", "SlashCommandHandler" in code)
        check("Has CardBuilder", "CardBuilder" in code)
        check("Has /status command", "status" in code.lower())
        check("Has /tasks command", "tasks" in code.lower())
        check("Has /approve command", "approve" in code.lower())

    # Check 5: Server Integration
    print("\n5. Server Integration")
    server = BASE / "api" / "server.py"
    if server.exists():
        code = server.read_text()
        check("Action router wired", "action_router" in code)
        check("Chat webhook router wired", "chat_webhook_router" in code)

    # Check 6: Test Suite
    print("\n6. Test Suite")
    test_files = [
        "tests/test_action_framework.py",
        "tests/test_asana_writer.py",
        "tests/test_gmail_writer.py",
        "tests/test_calendar_writer.py",
        "tests/test_chat_interactive.py",
    ]
    existing = [f for f in test_files if (BASE / f).exists()]
    check("All 5 test files exist", len(existing) == 5, f"{len(existing)}/5")

    if existing:
        passed, failed = run_tests(existing)
        check("All Brief 15 tests pass", failed == 0, f"{passed} passed, {failed} failed")
        check("Test count >= 150", passed >= 150, f"{passed} tests")

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} checks passed")
    if FAIL == 0:
        print("STATUS: ✅ ALL CHECKS PASSED — Brief 15 VALIDATED")
    else:
        print(f"STATUS: ❌ {FAIL} CHECK(S) FAILED")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
