import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .gogcli import run_gog
from .rules_store import load_rules


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dedupe_key(parts: list[str]) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return h[:24]


@dataclass
class BoardLists:
    proposals: str
    approved: str
    rejected: str
    snoozed: str
    simulated: str


KRYSTIE_EMAIL = "krystie@hrmny.co"


# --- Email routing rules (simulation contract) ---
# Base rules are in-code; user calibration adds to overrides file.
ARCHIVE_SENDER_SUBSTR = [
    "wetransfer",
    "dubaichamber.com",
]
ARCHIVE_SUBJECT_SUBSTR = [
    "has been downloaded",
    "invitation:",
    "settle local",
    "mediation",
    "new horizons roadshow",

    # Moh rules: ignore/archvive these classes
    "daily agenda for molham homsi",
    "public announcement of open tender",
    "public announcement of open",
    "open tender",
    "esupply opportunity",
]

DELEGATE_FINANCE_SUBSTR = [
    "invoice",
    "payment",
    "receipt",
    "billing",
    "funded",
    "paddle.com",
    "macpaw",
    "openai",
]


def list_tasklists(account: str) -> dict[str, str]:
    res = run_gog(["tasks", "lists", "list"], account=account)
    if not res.ok:
        raise RuntimeError(res.error)
    lists = res.data.get("tasklists") or []
    return {(tl.get("title") or ""): (tl.get("id") or "") for tl in lists}


def ensure_board_lists(account: str) -> BoardLists:
    wanted = [
        "TimeOS — Proposals",
        "TimeOS — Approved",
        "TimeOS — Rejected",
        "TimeOS — Snoozed",
        "TimeOS — Simulated Execution",
    ]
    existing = list_tasklists(account)
    for title in wanted:
        if title in existing and existing[title]:
            continue
        res = run_gog(["tasks", "lists", "create", title], account=account)
        if not res.ok:
            raise RuntimeError(res.error)
        existing = list_tasklists(account)

    return BoardLists(
        proposals=existing["TimeOS — Proposals"],
        approved=existing["TimeOS — Approved"],
        rejected=existing["TimeOS — Rejected"],
        snoozed=existing["TimeOS — Snoozed"],
        simulated=existing["TimeOS — Simulated Execution"],
    )


def _cache_path(account: str) -> str:
    os.makedirs("moh_time_os/out", exist_ok=True)
    safe = account.replace("@", "_at_").replace("/", "_")
    return f"moh_time_os/out/tasks-board-cache-{safe}.json"


def build_list_cache(account: str, tasklist_id: str, *, max_pages: int = 20) -> dict[str, dict]:
    """Return {dedupe_key: {taskId, status}} for a given list."""
    mapping: dict[str, dict] = {}
    page = None
    pages = 0
    while True:
        args = ["tasks", "list", tasklist_id, "--max=100", "--show-hidden", "--show-completed"]
        if page:
            args.append(f"--page={page}")
        res = run_gog(args, account=account, timeout=240)
        if not res.ok:
            raise RuntimeError(res.error)
        data = res.data or {}
        tasks = data.get("tasks") or []
        for t in tasks:
            notes = (t.get("notes") or "")
            # MOHOS/v1 header format: "dedupe_key: <dk>"
            for line in notes.splitlines()[:40]:
                if line.startswith("dedupe_key: "):
                    dk = line.split(": ", 1)[1].strip()
                    if dk:
                        mapping[dk] = {"taskId": t.get("id"), "status": t.get("status")}
                    break
        page = data.get("nextPageToken")
        pages += 1
        if not page or pages >= max_pages:
            break
    return mapping


def load_cache(account: str) -> dict:
    path = _cache_path(account)
    if not os.path.exists(path):
        return {}
    try:
        return json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        return {}


def save_cache(account: str, cache: dict) -> None:
    path = _cache_path(account)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def upsert_task(account: str, tasklist_id: str, *, title: str, notes: str, dk: str, cache: dict) -> dict:
    entry = (cache.get(tasklist_id) or {}).get(dk)
    if entry and entry.get("taskId"):
        tid = entry["taskId"]
        res = run_gog(["tasks", "update", tasklist_id, tid, f"--title={title}", f"--notes={notes}"], account=account, timeout=360)
        if not res.ok:
            raise RuntimeError(res.error)
        return res.data

    res = run_gog(["tasks", "add", tasklist_id, f"--title={title}", f"--notes={notes}"], account=account, timeout=360)
    if not res.ok:
        raise RuntimeError(res.error)
    # update cache locally (task id included in response shape under task)
    cache.setdefault(tasklist_id, {})[dk] = {"taskId": (res.data.get("task") or {}).get("id") if isinstance(res.data, dict) else None, "status": "needsAction"}
    return res.data


def mark_done(account: str, tasklist_id: str, task_id: str) -> None:
    res = run_gog(["tasks", "done", tasklist_id, task_id], account=account, timeout=240)
    if not res.ok:
        raise RuntimeError(res.error)


def mohos_notes_header(payload: dict[str, Any]) -> str:
    """MOHOS/v1 header. This is the contract between simulator and future executor."""
    lines = [
        "MOHOS/v1",
        f"lane: {payload.get('lane','Unknowns')}",
        f"project: {payload.get('project','(unenrolled)')}",
        f"status: {payload.get('status','proposed')}",
        f"urgency: {payload.get('urgency','low')}",
        f"impact: {payload.get('impact','low')}",
        f"deadline: {payload.get('deadline','soft:')}",
        f"effort: {payload.get('effort','15-30')}",
        f"waiting_for: {payload.get('waiting_for','')}",
        f"sensitivity: {','.join(payload.get('sensitivity',[]) or [])}",
        f"classification: {payload.get('classification','rule')}",
        f"rule_hit: {payload.get('rule_hit','')}",
        f"source: {payload.get('source','')}",
        f"dedupe_key: {payload.get('dedupe_key','')}",
        f"proposed_action: {payload.get('proposed_action','')}",
        "---",
    ]
    ctx = payload.get("context") or ""
    return "\n".join(lines) + ("\n" + ctx if ctx else "")


def email_should_archive(subject: str, sender: str) -> tuple[bool, str]:
    rules = load_rules()
    subj = subject.lower()
    snd = sender.lower()

    # overrides first
    for k in (rules.archive_sender_substr or []):
        if k and k.lower() in snd:
            return True, f"ARCHIVE.override_sender:{k}"
    for k in (rules.archive_subject_substr or []):
        if k and k.lower() in subj:
            return True, f"ARCHIVE.override_subject:{k}"

    # base rules
    for k in ARCHIVE_SENDER_SUBSTR:
        if k in snd:
            return True, f"ARCHIVE.sender:{k}"
    for k in ARCHIVE_SUBJECT_SUBSTR:
        if k in subj:
            return True, f"ARCHIVE.subject:{k}"
    return False, ""


def email_should_delegate_to_krystie(subject: str, sender: str) -> tuple[bool, str]:
    rules = load_rules()
    s = (subject + " " + sender).lower()

    # overrides first
    for k in (rules.delegate_krystie_substr or []):
        if k and k.lower() in s:
            return True, f"DELEGATE.override_krystie:{k}"

    for k in DELEGATE_FINANCE_SUBSTR:
        if k in s:
            return True, f"DELEGATE.krystie:{k}"
    return False, ""


def is_reply_worthy(subject: str, message_count: int) -> tuple[bool, str]:
    subj = subject.lower()
    # Strict: only treat as reply-worthy when there's an actual thread or an explicit reply marker.
    if message_count > 1:
        return True, "REVIEW.thread_depth"
    for k in ("re:", "urgent", "asap", "deadline", "closing"):
        if k in subj:
            return True, f"REVIEW.subject:{k}"
    return False, ""


def make_board_items_from_inputs(*, chat_json_path: str, gmail_json_path: str, calendar_json_path: str) -> list[dict[str, Any]]:
    """Create storyboard items (proposals vs simulated execution).

    - Proposals: require Moh attention (approvals, explicit asks)
    - Simulated: what the system would do automatically (archive, forward, blocks)
    """

    out: list[dict[str, Any]] = []

    # --- Chat: explicit @Molham asks ---
    chat = json.loads(open(chat_json_path, "r", encoding="utf-8").read())
    for space_id, info in chat.items():
        space_name = (info or {}).get("name") or space_id
        for m in (info or {}).get("messages") or []:
            txt = (m.get("text") or "").strip()
            if not txt:
                continue
            if "@Molham Homsi" not in txt and "@molham" not in txt.lower():
                continue

            t = txt.lower()
            if not any(k in t for k in ("request", "need", "please", "authorization", "approve", "release", "send")):
                continue

            lane = "Finance" if "finance" in space_name.lower() else ("Admin" if "admin" in space_name.lower() else "Ops")
            sens = ["financial"] if any(k in t for k in ("payment", "bank", "authorization")) else []
            urg = "high" if ("today" in t or "authorization" in t) else "medium"

            # If it's bank/payment authorization → approval required (Moh)
            if any(k in t for k in ("authorization", "bank", "payment")):
                action = "approval_required"
                title_prefix = "[APPROVAL_REQUIRED]"
                rule_hit = "CHAT.approval"
            else:
                action = "chat_reply_draft"
                title_prefix = "[CHAT→REPLY]"
                rule_hit = "CHAT.reply"

            dk = dedupe_key(["chat", space_id, m.get("thread") or "", txt[:80]])
            out.append(
                {
                    "bucket": "proposals",
                    "dedupe_key": dk,
                    "lane": lane,
                    "proposed_action": action,
                    "urgency": urg,
                    "impact": "medium" if sens else "low",
                    "deadline": "soft:",
                    "sensitivity": sens,
                    "classification": "rule",
                    "rule_hit": rule_hit,
                    "source": f"chat:{space_id}:{m.get('thread')}",
                    "context": txt,
                    "title": f"{title_prefix} {space_name}: {txt[:80]}",
                    "open_url": f"https://chat.google.com/room/{space_id.split('/')[-1]}?cls=11",
                }
            )

    # --- Gmail: simulate archive/delegate; propose reply drafts only if reply-worthy ---
    gmail = json.loads(open(gmail_json_path, "r", encoding="utf-8").read())
    for t in gmail[:120]:
        subj = (t.get("subject") or "").strip()
        frm = (t.get("from") or "").strip()
        tid = t.get("id") or ""
        if not subj or not tid:
            continue

        mc = int(t.get("messageCount") or 1)

        arch, arch_hit = email_should_archive(subj, frm)
        if arch:
            dk = dedupe_key(["gmail", tid, "archive"])
            out.append(
                {
                    "bucket": "simulated",
                    "dedupe_key": dk,
                    "lane": "Ops",
                    "proposed_action": "email_archive",
                    "urgency": "low",
                    "impact": "low",
                    "deadline": "soft:",
                    "sensitivity": [],
                    "classification": "rule",
                    "rule_hit": arch_hit,
                    "source": f"email_thread:{tid}",
                    "context": f"ARCHIVE\nfrom: {frm}\nsubject: {subj}\ndate: {t.get('date')}\nmessageCount: {mc}",
                    "title": f"[EMAIL→ARCHIVE] {subj}",
                    "open_url": None,
                }
            )
            continue

        delg, delg_hit = email_should_delegate_to_krystie(subj, frm)
        if delg:
            dk = dedupe_key(["gmail", tid, "delegate", KRYSTIE_EMAIL])
            out.append(
                {
                    "bucket": "simulated",
                    "dedupe_key": dk,
                    "lane": "Finance",
                    "proposed_action": "email_forward_to_krystie",
                    "urgency": "low",
                    "impact": "low",
                    "deadline": "soft:",
                    "sensitivity": ["financial"],
                    "classification": "rule",
                    "rule_hit": delg_hit,
                    "source": f"email_thread:{tid}",
                    "context": f"FORWARD TO: {KRYSTIE_EMAIL}\nfrom: {frm}\nsubject: {subj}\ndate: {t.get('date')}\nmessageCount: {mc}",
                    "title": f"[EMAIL→KRYSTIE] {subj}",
                    "open_url": None,
                }
            )
            continue

        reply, reply_hit = is_reply_worthy(subj, mc)
        if not reply:
            dk = dedupe_key(["gmail", tid, "archive_low_value"])
            out.append(
                {
                    "bucket": "simulated",
                    "dedupe_key": dk,
                    "lane": "Ops",
                    "proposed_action": "email_archive",
                    "urgency": "low",
                    "impact": "low",
                    "deadline": "soft:",
                    "sensitivity": [],
                    "classification": "rule",
                    "rule_hit": "ARCHIVE.low_value",
                    "source": f"email_thread:{tid}",
                    "context": f"ARCHIVE (low value)\nfrom: {frm}\nsubject: {subj}\ndate: {t.get('date')}\nmessageCount: {mc}",
                    "title": f"[EMAIL→ARCHIVE] {subj}",
                    "open_url": None,
                }
            )
            continue

        # Instead of an empty "draft" with no decision context, create a REVIEW proposal.
        dk = dedupe_key(["gmail", tid, "review"])
        out.append(
            {
                "bucket": "proposals",
                "dedupe_key": dk,
                "lane": "Ops",
                "proposed_action": "email_review",
                "urgency": "medium" if mc > 1 else "low",
                "impact": "low",
                "deadline": "soft:",
                "sensitivity": [],
                "classification": "rule",
                "rule_hit": reply_hit,
                "source": f"email_thread:{tid}",
                "context": f"from: {frm}\nsubject: {subj}\ndate: {t.get('date')}\nmessageCount: {mc}\n\nNEEDS: determine if reply needed, or file/label/close.",
                "title": f"[EMAIL→REVIEW] {subj}",
                "open_url": None,
            }
        )

    # --- Calendar simulated blocks (minimal) ---
    cal = json.loads(open(calendar_json_path, "r", encoding="utf-8").read())
    for e in cal[:50]:
        summary = (e.get("summary") or "").strip()
        if not summary:
            continue
        if summary.lower() in ("asics",):
            dk = dedupe_key(["calendar_block", summary, (e.get("start") or {}).get("dateTime") or ""]) 
            out.append(
                {
                    "bucket": "simulated",
                    "dedupe_key": dk,
                    "lane": "Client",
                    "proposed_action": "calendar_block_simulated",
                    "urgency": "low",
                    "impact": "low",
                    "deadline": "soft:",
                    "sensitivity": [],
                    "classification": "rule",
                    "rule_hit": "CAL.block_sim",
                    "source": f"calendar:{e.get('id')}",
                    "context": f"SIMULATED BLOCK\nEvent: {summary}\nStart: {(e.get('start') or {}).get('dateTime')}\nEnd: {(e.get('end') or {}).get('dateTime')}\nLink: {e.get('htmlLink')}",
                    "title": f"[CAL→BLOCK] {summary} ({(e.get('start') or {}).get('dateTime')})",
                    "open_url": e.get("htmlLink"),
                }
            )

    return out


def reconcile_and_write(
    *,
    account: str,
    lists: BoardLists,
    items: list[dict[str, Any]],
    throttle_ms: int,
    max_items: int,
) -> dict[str, Any]:
    """Upsert items into target lists and close items that moved buckets.

    Also ingests manual calibration:
    - If a dedupe_key is present in Rejected → suppress + close from other lists.
    - If present in Snoozed → suppress while snoozed + close from other lists.
    """

    cache = load_cache(account)
    # Refresh caches for all board lists
    cache[lists.proposals] = build_list_cache(account, lists.proposals)
    cache[lists.simulated] = build_list_cache(account, lists.simulated)
    cache[lists.rejected] = build_list_cache(account, lists.rejected)
    cache[lists.snoozed] = build_list_cache(account, lists.snoozed)
    cache[lists.approved] = build_list_cache(account, lists.approved)
    save_cache(account, cache)

    rejected_keys = set((cache.get(lists.rejected) or {}).keys())
    snoozed_keys = set((cache.get(lists.snoozed) or {}).keys())

    written = {"proposals": 0, "simulated": 0, "migrated": 0, "suppressed": 0}

    def _close_if_present(dk: str, tasklist_id: str) -> None:
        entry = (cache.get(tasklist_id) or {}).get(dk)
        if entry and entry.get("taskId"):
            mark_done(account, tasklist_id, entry["taskId"])
            cache.get(tasklist_id, {}).pop(dk, None)

    def write_item(it: dict, target_list: str, other_list: str) -> None:
        nonlocal written
        dk = it["dedupe_key"]

        # Manual calibration suppression
        if dk in rejected_keys or dk in snoozed_keys:
            written["suppressed"] += 1
            # Ensure it doesn't remain in proposals/simulated
            _close_if_present(dk, lists.proposals)
            _close_if_present(dk, lists.simulated)
            return

        title = it["title"]
        notes = mohos_notes_header(
            {
                "lane": it.get("lane"),
                "status": "proposed",
                "urgency": it.get("urgency", "low"),
                "impact": it.get("impact", "low"),
                "deadline": it.get("deadline", "soft:"),
                "effort": "15-30",
                "sensitivity": it.get("sensitivity"),
                "classification": it.get("classification", "rule"),
                "rule_hit": it.get("rule_hit", ""),
                "source": it.get("source"),
                "dedupe_key": dk,
                "proposed_action": it.get("proposed_action"),
                "waiting_for": KRYSTIE_EMAIL if it.get("proposed_action") == "email_forward_to_krystie" else "",
                "context": (it.get("context") or "") + ("\n\nopen: " + it.get("open_url") if it.get("open_url") else ""),
            }
        )

        upsert_task(account, target_list, title=title, notes=notes, dk=dk, cache=cache)

        # If exists in the other list, close it to avoid drift.
        _close_if_present(dk, other_list)
        if other_list in (lists.proposals, lists.simulated):
            written["migrated"] += 1

    # Cap writes deterministically
    for it in items[:max_items]:
        bucket = it.get("bucket")
        if bucket == "proposals":
            write_item(it, lists.proposals, lists.simulated)
            written["proposals"] += 1
        else:
            write_item(it, lists.simulated, lists.proposals)
            written["simulated"] += 1
        time.sleep(throttle_ms / 1000.0)

    save_cache(account, cache)

    return {
        "ok": True,
        "written": written,
        "ts": now_iso(),
        "note": "Proposals = requires Moh attention. Simulated Execution = auto-actions (archive/delegate/blocks). Drift is auto-closed via reconcile.",
    }


def write_board_from_collector_outputs(
    *,
    account: str,
    lists: BoardLists,
    chat_json_path: str,
    gmail_json_path: str,
    calendar_json_path: str,
    throttle_ms: int = 140,
    max_items: int = 90,
) -> dict[str, Any]:
    items = make_board_items_from_inputs(
        chat_json_path=chat_json_path,
        gmail_json_path=gmail_json_path,
        calendar_json_path=calendar_json_path,
    )

    # Sort: proposals first (Moh), then simulated
    def sort_key(it: dict) -> tuple:
        b = 0 if it.get("bucket") == "proposals" else 1
        u = it.get("urgency")
        um = {"high": 0, "medium": 1, "low": 2}.get(u, 2)
        return (b, um)

    items.sort(key=sort_key)

    return reconcile_and_write(account=account, lists=lists, items=items, throttle_ms=throttle_ms, max_items=max_items)
