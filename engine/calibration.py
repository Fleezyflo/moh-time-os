import re
from typing import Any

from .gogcli import run_gog
from .rules_store import RuleOverrides, load_rules, save_rules


FROM_RE = re.compile(r"^from:\s*(.+)$", re.I | re.M)
SUBJ_RE = re.compile(r"^subject:\s*(.+)$", re.I | re.M)


def _extract_from_subject(context: str) -> tuple[str, str]:
    frm = ""
    subj = ""
    if not context:
        return frm, subj
    m = FROM_RE.search(context)
    if m:
        frm = m.group(1).strip()
    m2 = SUBJ_RE.search(context)
    if m2:
        subj = m2.group(1).strip()
    return frm, subj


def _normalize_sender_key(frm: str) -> str:
    # Try to extract domain for stable rule.
    frm_l = frm.lower()
    if "@" in frm_l:
        dom = frm_l.split("@", 1)[1]
        # strip angle bracket suffixes
        dom = dom.replace(">", "").strip()
        return dom
    return frm_l


def ingest_rejections(*, account: str, rejected_list_id: str, rules_path: str | None = None) -> dict[str, Any]:
    """Read tasks in 'Rejected' and turn them into rule overrides.

    Conservative policy:
    - For EMAIL items: add sender domain to archive_sender_substr.
    - For WeTransfer-like subjects: add a subject token.

    This is meant to reduce repeated noise, not to learn complex intent.
    """

    rules = load_rules(rules_path) if rules_path else load_rules()

    page = None
    added = {"archive_sender": 0, "archive_subject": 0, "delegate": 0}
    seen = 0

    while True:
        args = ["tasks", "list", rejected_list_id, "--max=100", "--show-hidden", "--show-completed"]
        if page:
            args.append(f"--page={page}")
        res = run_gog(args, account=account, timeout=240)
        if not res.ok:
            return {"ok": False, "error": res.error}
        data = res.data or {}
        tasks = data.get("tasks") or []
        for t in tasks:
            notes = t.get("notes") or ""
            title = (t.get("title") or "").strip()
            seen += 1

            if title.startswith("[EMAIL"):
                frm, subj = _extract_from_subject(notes)
                dom = _normalize_sender_key(frm)
                if dom and dom not in rules.archive_sender_substr:
                    rules.archive_sender_substr.append(dom)
                    added["archive_sender"] += 1
                # If the subject contains a stable token, store it.
                subj_l = subj.lower()
                for tok in (
                    "has been downloaded",
                    "invitation",
                    "mediation",
                    "open tender",
                    "esupply opportunity",
                    "daily agenda",
                    "public announcement",
                ):
                    if tok in subj_l and tok not in rules.archive_subject_substr:
                        rules.archive_subject_substr.append(tok)
                        added["archive_subject"] += 1

            # Allow delegations to be reinforced via rejection too
            if title.startswith("[EMAIL→KRYSTIE]"):
                # If rejected, remove delegation keyword by adding subject token to archive (avoid loops)
                frm, subj = _extract_from_subject(notes)
                subj_l = subj.lower()
                if subj_l and subj_l not in rules.archive_subject_substr:
                    rules.archive_subject_substr.append(subj_l[:60])
                    added["archive_subject"] += 1

        page = data.get("nextPageToken")
        if not page:
            break

    save_rules(rules, rules_path) if rules_path else save_rules(rules)
    return {"ok": True, "seen": seen, "added": added}
