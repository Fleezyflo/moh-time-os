#!/usr/bin/env python3
"""
Brief 16: Data Governance & Compliance — Validation Script (DG-5.1)

Validates all deliverables from Brief 16:
- DG-1.1: Data classification & catalog
- DG-2.1: Bulk data export API (JSON/CSV)
- DG-3.1: Subject access & right-to-be-forgotten
- DG-4.1: Governance-grade retention enforcement
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
    print("Brief 16: Data Governance & Compliance — Validation")
    print("=" * 60)

    # Check 1: Data Classification (DG-1.1)
    print("\n1. Data Classification (DG-1.1)")
    dc = BASE / "lib" / "governance" / "data_classification.py"
    cat = BASE / "lib" / "governance" / "data_catalog.py"
    check("data_classification.py exists", dc.exists())
    check("data_catalog.py exists", cat.exists())
    if dc.exists():
        code = dc.read_text()
        check("Has DataSensitivity", "DataSensitivity" in code)
        check("Has DataCategory", "DataCategory" in code)
        check("Has ColumnClassification", "ColumnClassification" in code)
        check("Has TableClassification", "TableClassification" in code)
        check("Has DataClassifier", "DataClassifier" in code)
        check("Has PII detection", "pii" in code.lower() or "PII" in code)
        check("Has pattern detection", "pattern" in code.lower() or "detect" in code.lower())
    if cat.exists():
        code = cat.read_text()
        check("Has DataCatalog", "DataCatalog" in code)
        check("Has compliance_summary", "compliance" in code.lower())

    # Check 2: Data Export (DG-2.1)
    print("\n2. Data Export API (DG-2.1)")
    de = BASE / "lib" / "governance" / "data_export.py"
    anon = BASE / "lib" / "governance" / "anonymizer.py"
    er = BASE / "api" / "export_router.py"
    check("data_export.py exists", de.exists())
    check("anonymizer.py exists", anon.exists())
    check("export_router.py exists", er.exists())
    if de.exists():
        code = de.read_text()
        check("Has ExportFormat", "ExportFormat" in code)
        check("Has ExportRequest", "ExportRequest" in code)
        check("Has ExportResult", "ExportResult" in code)
        check("Has DataExporter", "DataExporter" in code)
        check("Has JSON support", "json" in code.lower())
        check("Has CSV support", "csv" in code.lower())
        check("Has checksum", "sha256" in code.lower() or "checksum" in code.lower())
    if anon.exists():
        code = anon.read_text()
        check("Has Anonymizer", "Anonymizer" in code)
        check("Has anonymize_email", "anonymize_email" in code)
        check("Has anonymize_name", "anonymize_name" in code)

    # Check 3: Subject Access (DG-3.1)
    print("\n3. Subject Access & Deletion (DG-3.1)")
    sa = BASE / "lib" / "governance" / "subject_access.py"
    al = BASE / "lib" / "governance" / "audit_log.py"
    gr = BASE / "api" / "governance_router.py"
    check("subject_access.py exists", sa.exists())
    check("audit_log.py exists", al.exists())
    check("governance_router.py exists", gr.exists())
    if sa.exists():
        code = sa.read_text()
        check("Has SubjectAccessRequest", "SubjectAccessRequest" in code)
        check("Has SubjectAccessManager", "SubjectAccessManager" in code)
        check("Has find_subject_data", "find_subject_data" in code)
        check("Has delete_subject_data", "delete_subject_data" in code)
        check("Has anonymize_subject_data", "anonymize_subject_data" in code)
        check("Has dry_run support", "dry_run" in code)
    if al.exists():
        code = al.read_text()
        check("Has AuditLog", "AuditLog" in code)
        check("Has AuditEntry", "AuditEntry" in code)

    # Check 4: Retention Enforcement (DG-4.1)
    print("\n4. Retention Enforcement (DG-4.1)")
    re = BASE / "lib" / "governance" / "retention_engine.py"
    rs = BASE / "lib" / "governance" / "retention_scheduler.py"
    check("retention_engine.py exists", re.exists())
    check("retention_scheduler.py exists", rs.exists())
    if re.exists():
        code = re.read_text()
        check("Has RetentionPolicy", "RetentionPolicy" in code)
        check("Has RetentionEngine", "RetentionEngine" in code)
        check("Has RetentionReport", "RetentionReport" in code)
        check("Has enforce method", "def enforce" in code)
        check("Has preview_enforcement", "preview" in code.lower())
        check("Has safety guards", "protected" in code.lower() or "PROTECTED" in code)
    if rs.exists():
        code = rs.read_text()
        check("Has RetentionScheduler", "RetentionScheduler" in code)
        check("Has schedule support", "daily" in code or "weekly" in code)

    # Check 5: Package & Server Integration
    print("\n5. Package & Server Integration")
    init = BASE / "lib" / "governance" / "__init__.py"
    server = BASE / "api" / "server.py"
    check("governance __init__.py exists", init.exists())
    if server.exists():
        code = server.read_text()
        has_governance = "governance_router" in code or "export_router" in code
        check("Governance router wired in server", has_governance)

    # Check 6: Test Suite
    print("\n6. Test Suite")
    test_files = [
        "tests/test_data_classification.py",
        "tests/test_data_export.py",
        "tests/test_subject_access.py",
        "tests/test_retention_engine.py",
    ]
    existing = [f for f in test_files if (BASE / f).exists()]
    check("All 4 test files exist", len(existing) == 4, f"{len(existing)}/4")

    if existing:
        passed, failed = run_tests(existing)
        check("All Brief 16 tests pass", failed == 0, f"{passed} passed, {failed} failed")
        check("Test count >= 100", passed >= 100, f"{passed} tests")

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} checks passed")
    if FAIL == 0:
        print("STATUS: ✅ ALL CHECKS PASSED — Brief 16 VALIDATED")
    else:
        print(f"STATUS: ❌ {FAIL} CHECK(S) FAILED")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
