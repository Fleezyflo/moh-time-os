import html
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _h(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def render_operator_html(
    out_path: str,
    *,
    calendar_events: list[dict],
    chat_unread: dict,
    gmail_threads: list[dict],
    meta: dict[str, Any],
) -> None:
    """Render a local operator console.

    Design targets (v0.3):
    - Reflect **lane**, **urgency**, **sensitivity**, and **state**.
    - Show only decision-relevant views: NOW / NEXT / LATER.
    - Provide actions (Done/Snooze) without a server using browser localStorage.

    Note: execution (sending emails / editing chat) remains gated elsewhere.
    """

    # --- classification helpers (deterministic v0.1) ---
    FIN_KW = (
        "invoice",
        "payment",
        "quote",
        "pricing",
        "po",
        "budget",
        "transfer",
        "vat",
        "receipt",
        "authorization",
        "bank",
    )
    LEGAL_KW = (
        "contract",
        "nda",
        "terms",
        "agreement",
        "signature",
        "clause",
        "ip",
        "liability",
    )
    SEC_KW = (
        "password",
        "access",
        "credentials",
        "breach",
        "2fa",
        "token",
        "dropbox sign in",
    )
    URG_KW = ("urgent", "asap", "today", "eod", "deadline", "closing")

    def classify_lane(kind: str, context: dict) -> str:
        if kind == "chat":
            n = (context.get("space") or "").lower()
            if "finance" in n:
                return "Finance"
            if "procurement" in n:
                return "Ops"
            if "admin" in n:
                return "Admin"
            if "hr" in n or "people" in n:
                return "People"
            if "client" in n:
                return "Client"
            return "Ops"

        if kind == "gmail":
            frm = (context.get("from") or "").lower()
            subj = (context.get("subject") or "").lower()
            txt = frm + " " + subj
            if any(k in txt for k in FIN_KW):
                return "Finance"
            if any(k in txt for k in LEGAL_KW):
                return "Governance"
            if "hrmny.co" in frm:
                return "Ops"
            if "spotify.com" in frm or "moh flow" in subj:
                return "Music"
            return "Ops"

        if kind == "calendar":
            subj = (context.get("summary") or "").lower()
            if "finance" in subj:
                return "Finance"
            if "asics" in subj or "client" in subj:
                return "Client"
            return "Ops"

        return "Ops"

    def sensitivity(context: dict) -> list[str]:
        txt = (context.get("text") or context.get("subject") or "").lower()
        frm = (context.get("from") or "").lower()
        all_txt = f"{txt} {frm}"
        flags = []
        if any(k in all_txt for k in FIN_KW):
            flags.append("financial")
        if any(k in all_txt for k in LEGAL_KW):
            flags.append("legal")
        if any(k in all_txt for k in SEC_KW):
            flags.append("security")
        return flags

    def urgency(context: dict) -> str:
        txt = (context.get("text") or context.get("subject") or "").lower()
        if any(k in txt for k in URG_KW):
            return "high"
        if "follow" in txt and "please" in txt:
            return "medium"
        return "low"

    def is_direct_ask_chat(txt: str) -> bool:
        t = txt.lower()
        # explicit asks: authorization/approve/release/specs
        return any(
            k in t
            for k in (
                "authorization",
                "approve",
                "approval",
                "release",
                "send",
                "spec",
                "quotation",
            )
        )

    def is_noise_mail(m: dict) -> bool:
        subj = (m.get("subject") or "").lower()
        frm = (m.get("from") or "").lower()
        if "calendar-notification" in frm:
            return True
        if "gemini-notes" in frm:
            return True
        if "daily agenda" in subj:
            return True
        return False

    # --- normalize inputs into cards ---
    chat_cards: list[dict] = []
    for space_id, info in (chat_unread or {}).items():
        space_name = (info or {}).get("name") or space_id
        room_id = space_id.split("/")[-1]
        room_url = f"https://chat.google.com/room/{room_id}?cls=11"
        for m in (info or {}).get("messages") or []:
            txt = (m.get("text") or "").strip()
            if not txt:
                continue
            low = txt.lower()
            if "@molham" not in low and "molham homsi" not in low:
                continue
            ctx = {"space": space_name, "text": txt}
            chat_cards.append(
                {
                    "id": m.get("resource") or f"{space_id}:{m.get('createTime')}",
                    "kind": "chat",
                    "lane": classify_lane("chat", {"space": space_name}),
                    "sens": sensitivity(ctx),
                    "urg": urgency(ctx),
                    "space": space_name,
                    "url": room_url,
                    "when": m.get("createTime"),
                    "who": m.get("sender") or m.get("author"),
                    "text": txt,
                }
            )

    cal_cards: list[dict] = []
    for e in calendar_events or []:
        s = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date")
        en = (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date")
        ctx = {"summary": e.get("summary")}
        cal_cards.append(
            {
                "id": e.get("id") or e.get("iCalUID") or e.get("htmlLink"),
                "kind": "calendar",
                "lane": classify_lane("calendar", ctx),
                "sens": sensitivity(ctx),
                "urg": "low",
                "summary": e.get("summary"),
                "start": s,
                "end": en,
                "htmlLink": e.get("htmlLink"),
                "meet": e.get("hangoutLink")
                or ((e.get("conferenceData") or {}).get("entryPoints") or [{}])[0].get(
                    "uri"
                ),
            }
        )

    mail_cards: list[dict] = []
    for t in (gmail_threads or [])[:50]:
        ctx = {"from": t.get("from"), "subject": t.get("subject")}
        mail_cards.append(
            {
                "id": t.get("id"),
                "kind": "gmail",
                "lane": classify_lane("gmail", ctx),
                "sens": sensitivity(ctx),
                "urg": urgency(ctx),
                "subject": t.get("subject"),
                "from": t.get("from"),
                "date": t.get("date"),
            }
        )

    # --- lane/system grouping ---
    now_items: list[dict] = []
    next_items: list[dict] = []
    later_items: list[dict] = []

    for c in chat_cards:
        if is_direct_ask_chat(c.get("text") or "") or c.get("sens"):
            now_items.append(c)
        else:
            next_items.append(c)

    for m in mail_cards:
        if (
            "security" in (m.get("sens") or [])
            or "financial" in (m.get("sens") or [])
            or m.get("urg") == "high"
        ):
            now_items.append(m)
        elif is_noise_mail(m):
            later_items.append(m)
        else:
            next_items.append(m)

    css = """
:root{--bg:#0b0f14;--card:#121a23;--muted:#9fb0c0;--text:#e9f0f7;--accent:#58a6ff;--bad:#ff6b6b;--ok:#2ecc71;--border:#223044;--warn:#f5c542}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1200px;margin:0 auto;padding:18px}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
.title{font-size:22px;font-weight:700}
.meta{color:var(--muted);font-size:13px;line-height:1.4}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px;margin-top:14px}
.col{grid-column:span 12}
@media(min-width:980px){.col-6{grid-column:span 6}.col-4{grid-column:span 4}}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px}
.card h2{margin:0 0 10px 0;font-size:14px;color:#d7e3ef;text-transform:uppercase;letter-spacing:.08em}
.kpi{display:flex;gap:10px;flex-wrap:wrap}
.pill{border:1px solid var(--border);border-radius:999px;padding:6px 10px;color:var(--muted);font-size:12px}
.pill b{color:var(--text)}
.row{padding:10px 0;border-top:1px solid var(--border)}
.row:first-of-type{border-top:none}
.hdr{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.who{color:var(--muted);font-size:12px}
.txt{margin-top:6px;color:var(--text);font-size:13px;line-height:1.35;white-space:pre-wrap}
.tag{font-size:11px;color:var(--muted)}
.badge{display:inline-block;border:1px solid var(--border);border-radius:999px;padding:2px 8px;font-size:11px;color:var(--muted);margin-left:6px}
.badge.urg-high{border-color:rgba(245,197,66,.6);color:var(--warn)}
.badge.urg-med{border-color:rgba(88,166,255,.5);color:rgba(140,200,255,.95)}
.badge.sens{border-color:rgba(255,107,107,.35);color:#ffb3b3}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
button{background:transparent;border:1px solid var(--border);color:var(--text);border-radius:10px;padding:6px 10px;font-size:12px;cursor:pointer}
button:hover{border-color:#335074}
.small{font-size:12px;color:var(--muted)}
details summary{cursor:pointer;color:var(--muted)}
"""

    def badge_html(item: dict) -> str:
        lane = item.get("lane")
        urg = item.get("urg")
        sens = item.get("sens") or []
        out = [f"<span class='badge'>{_h(lane)}</span>"]
        if urg == "high":
            out.append("<span class='badge urg-high'>URGENT</span>")
        elif urg == "medium":
            out.append("<span class='badge urg-med'>FOLLOW-UP</span>")
        for s in sens:
            out.append(f"<span class='badge sens'>{_h(s)}</span>")
        return "".join(out)

    def render_item(item: dict) -> str:
        kind = item.get("kind")
        iid = item.get("id") or ""
        if kind == "calendar":
            links = []
            if item.get("htmlLink"):
                links.append(
                    f"<a href='{_h(item['htmlLink'])}' target='_blank'>open</a>"
                )
            if item.get("meet"):
                links.append(f"<a href='{_h(item['meet'])}' target='_blank'>meet</a>")
            lnk = (" · ".join(links)) if links else ""
            return (
                f"<div class='row' data-id='{_h(iid)}'>"
                f"<div class='hdr'><div><b>{_h(item.get('summary'))}</b>{badge_html(item)}"
                f"<div class='small'>{_h(item.get('start'))} → {_h(item.get('end'))}</div></div>"
                f"<div class='tag'>{lnk}</div></div>"
                f"</div>"
            )

        if kind == "chat":
            return (
                f"<div class='row' data-id='{_h(iid)}'>"
                f"<div class='hdr'><div><b>{_h(item.get('space'))}</b>{badge_html(item)}"
                f"<div class='who'>from: {_h(item.get('who'))} · {_h(item.get('when'))}</div></div>"
                f"<div><a href='{_h(item.get('url'))}' target='_blank'>open</a></div></div>"
                f"<div class='txt'>{_h(item.get('text'))}</div>"
                f"<div class='actions'>"
                f"<button onclick=\"markDone('{_h(iid)}')\">Done</button>"
                f"<button onclick=\"snooze('{_h(iid)}',2)\">Snooze 2h</button>"
                f"<button onclick=\"snooze('{_h(iid)}',24)\">Snooze 1d</button>"
                f"</div></div>"
            )

        # gmail
        return (
            f"<div class='row' data-id='{_h(iid)}'>"
            f"<div class='hdr'><div><b>{_h(item.get('subject'))}</b>{badge_html(item)}"
            f"<div class='who'>{_h(item.get('from'))}</div></div><div class='tag'>{_h(item.get('date'))}</div></div>"
            f"<div class='actions'>"
            f"<button onclick=\"markDone('{_h(iid)}')\">Done</button>"
            f"<button onclick=\"snooze('{_h(iid)}',2)\">Snooze 2h</button>"
            f"<button onclick=\"snooze('{_h(iid)}',24)\">Snooze 1d</button>"
            f"</div></div>"
        )

    html_out: list[str] = [
        "<!doctype html><html><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1' />",
        f"<title>Time OS — Console</title><style>{css}</style></head><body>",
        "<div class='wrap'>",
        "<div class='top'>",
        "<div>",
        "<div class='title'>Time OS — Console</div>",
        f"<div class='meta'>Generated: {_h(_now_iso())} (UTC)</div>",
        "</div>",
        "<div class='meta'>",
        "NOW = explicit asks + financial/security.<br/>NEXT = everything else actionable.<br/>LATER = auto-noise/backlog.",
        "</div>",
        "</div>",
        "<div class='grid'>",
        """
<script>
const keyDone='mohos_done_v1';
const keySnooze='mohos_snooze_v1';
function loadJSON(k,def){try{return JSON.parse(localStorage.getItem(k)||JSON.stringify(def));}catch(e){return def;}}
function saveJSON(k,v){localStorage.setItem(k,JSON.stringify(v));}
function markDone(id){const done=new Set(loadJSON(keyDone,[]));done.add(id);saveJSON(keyDone,[...done]);document.querySelector(`[data-id='${CSS.escape(id)}']`)?.remove();}
function snooze(id,hours){const snooze=loadJSON(keySnooze,{});snooze[id]=Date.now()+hours*3600*1000;saveJSON(keySnooze,snooze);document.querySelector(`[data-id='${CSS.escape(id)}']`)?.remove();}
function isSnoozed(id){const snooze=loadJSON(keySnooze,{});return (snooze[id]||0)>Date.now();}
function isDone(id){return loadJSON(keyDone,[]).includes(id);}
window.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('[data-id]').forEach(el=>{
    const id=el.getAttribute('data-id');
    if(isDone(id) || isSnoozed(id)) el.remove();
  });
});
</script>
""",
    ]

    html_out.append("<div class='col col-4 card'><h2>KPIs</h2><div class='kpi'>")
    html_out.append(f"<div class='pill'><b>{len(now_items)}</b> NOW</div>")
    html_out.append(f"<div class='pill'><b>{len(next_items)}</b> NEXT</div>")
    html_out.append(f"<div class='pill'><b>{len(later_items)}</b> LATER</div>")
    html_out.append(f"<div class='pill'><b>{len(cal_cards)}</b> calendar</div>")
    html_out.append(
        "</div><div class='small' style='margin-top:10px'>State is local to your browser (Done/Snooze). No writes to Google from this UI.</div></div>"
    )

    html_out.append("<div class='col col-4 card'><h2>Calendar (next 24h)</h2>")
    for e in cal_cards:
        html_out.append(render_item(e))
    if not cal_cards:
        html_out.append("<div class='small'>No events.</div>")
    html_out.append("</div>")

    html_out.append(
        "<div class='col col-6 card'><h2>NOW (blocking)</h2><div class='small'>Approvals / explicit asks / financial / security</div>"
    )
    for it in now_items:
        html_out.append(render_item(it))
    if not now_items:
        html_out.append("<div class='small'>Clear.</div>")
    html_out.append("</div>")

    html_out.append("<div class='col col-6 card'><h2>NEXT</h2>")
    for it in next_items:
        html_out.append(render_item(it))
    if not next_items:
        html_out.append("<div class='small'>Nothing queued.</div>")
    html_out.append("<details style='margin-top:12px'><summary>LATER / Noise</summary>")
    for it in later_items:
        html_out.append(render_item(it))
    html_out.append("</details></div>")

    html_out.append("</div></div></body></html>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(html_out))
