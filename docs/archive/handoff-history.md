# Handoff History — MOH Time OS

Frozen provenance snipped from `HANDOFF.md` §Now before each overwrite. Verbatim. Newest first.

---

## 2026-05-15 — Audit lessons (preserved 2026-05-31 before §Now overwrite)

Kept because these are cross-session lessons about *how the analysis went wrong*, not derivable from `git log` or any check command. The runtime facts from this entry (daemon running, two collectors dead, etc.) are intentionally NOT preserved — they are superseded by the 2026-05-31 §Now and re-derivable via §State checks.

### Mistakes made in the first three audits (author: Claude, with corrections from Molham)

1. **`AUDIT_2026-05-15.md` v1** — claimed "108 sites of `return [] on failure`" by conflating `json.dumps` with `json.dump`; actual was 18. Claimed CORS was "wildcard + credentials" without verifying env defaults. Asserted "200+ endpoints" instead of counting (actual: 275).

2. **`AUDIT_2026-05-15.md` v2** — corrected the counts, but still relied on reading code without checking runtime.

3. **`FLOW_MAP.md`** — biggest error. Declared "the daemon is not running" because it read the repo *template* plist (`ops/com.mohtime.daemon.plist`, stale path `/Users/molham/...`) instead of the installed one (`~/Library/LaunchAgents/com.mohtime.daemon.plist`, correct path). Did not run `ps aux | grep daemon`, `cat daemon.pid`, or look at the actively-written `daemon.log` / `daemon_state.json` — any of which would have shown the daemon was running. Read 5,000 lines of code instead of 5 commands.

4. **The causal chain "plist wrong path → daemon not running" was wrong on both ends.** The repo plist is a template; the installed one is correct. And even if the installed plist were wrong, the running PID falsifies the conclusion. Built a story and stopped checking once it felt consistent.

### Corrected order of operations (the durable lesson)

1. `ps aux | grep <process>` first
2. `ls <data_dir>` and check timestamps
3. Read the data the system has produced
4. THEN read code to explain what you see

Source reading is for understanding mechanism. Runtime checks are for understanding state. The earlier audits conflated them. This lesson held up: the 2026-05-31 root-cause work succeeded specifically because it reproduced the failure under instrumentation instead of inferring from logs.

### Note on a since-corrected code claim

The 2026-05-15 §Now claimed `POST /api/cycle` "always crashes" because it passed `AutonomousLoop(store, collectors, ...)` positionally against a `config_path` constructor. By 2026-05-31 the handler is `AutonomousLoop()` (no args) at `api/server.py:3242` — the TypeError is gone; the real problem is that it runs synchronously in the async event loop. Recorded here so a future reader doesn't chase a bug that was already fixed.
