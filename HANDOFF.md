# HANDOFF — MOH Time OS

This file is **point-in-time**, rewritten each session — not an append-only log. §State holds claims that can go stale but are always re-derivable via their `Check:` command. §Now is the current snapshot and gets replaced wholesale each session. History lives in `docs/archive/handoff-history.md`.

The remediation plans being executed are in `docs/superpowers/plans/2026-06-01-*.md` (INDEX + WS1–WS9). This session's enforced-verification record is `audit-remediation/VERIFICATION_LOG_S_ws1-5_autonomous.md`.

---

## §State (re-verify before quoting)

- **System is LIVE.** Both launchd agents up. Check: `launchctl list | grep -i mohtime` → `<pid> <exit> com.mohtime.daemon` and `<pid> 0 com.mohtimeos.api`. (NOTE: the daemon's middle column may show a stale non-zero `LastExitStatus` from the transient-network restart below — that's *history*, not current health; trust the running PID + fresh `daemon_state.json`, not that integer.)
- **Live processes:** API (`-m api.server`, PID was 22888) + daemon (`-m lib.daemon start`, PID was 60570). Check: `ps aux | grep -E "[m]oh_time_os/.venv/bin/python"` → two lines.
- **API:** authenticated, listening on `127.0.0.1:8420`. Check: `curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:8420/api/health` → `200`; unauth `curl -X DELETE .../api/tasks/x` → `401`; with `-H "Authorization: Bearer $(cat /tmp/moh_api_key.txt)"` GET `/api/actions/pending` → `200`.
- **API key:** generated this session, in `/tmp/moh_api_key.txt`, wired into `~/Library/LaunchAgents/com.mohtimeos.api.plist` (MOH_TIME_OS_API_KEY), the daemon plist copy, and `time-os-ui/.env.local` (VITE_API_TOKEN, gitignored). NOT in git. Check: `python3 -c "import plistlib,pathlib; print('MOH_TIME_OS_API_KEY' in plistlib.loads((pathlib.Path.home()/'Library/LaunchAgents/com.mohtimeos.api.plist').read_bytes())['EnvironmentVariables'])"` → True.
- **Daemon cycle:** 8 registered stages, 0 orphans, advancing. Check: `python3 -c "import json;d=json.load(open('$HOME/.moh_time_os/data/daemon_state.json'));print(sorted(d['jobs']),'orphans=',set(d['jobs'])&{'autonomous','backup'},'updated=',d['updated_at'])"` → 8 stages (collect/detection/intelligence/lane_assignment/morning_brief/notify/snapshot/truth_cycle), `orphans= set()`.
- **launchctl quirk:** `launchctl bootstrap gui/$(id -u) <plist>` returned `5: Input/output error` in this session; legacy `launchctl load -w <plist>` WORKED. Use `load -w` / `unload` here. Check: n/a (operational note).
- **main HEAD:** `ef9cc69` (2026-06-04; merged since `6b7c3fd`: #152 statestore-write-path base, #153 task-project-linker store-migration, #154 key_manager test+tz fix, #155 test_change_bundles fixture, #156 daemon-resilience test repair + `_run_job` broad-catch restore). Check: `git fetch origin main && git rev-parse --short origin/main`.
- **Working checkout:** on `main`, in sync with origin. Check: `git rev-parse --abbrev-ref HEAD` → `main`; `git rev-list --left-right --count HEAD...origin/main` → `0	0`. (The daemon runs `lib.daemon` FROM this main checkout — keep it on `main` after merges or the live daemon runs stale code. 2026-06-03: this checkout was found 12 commits behind origin/main with the daemon (then PID 37192) running pre-#140 code; fast-forwarded to `6b7c3fd` and the daemon was `kickstart -k` restarted (now PID 91174) to load it.)
- **Trajectory perf (WS5, #140) fully resolved + measured.** `portfolio_health_trajectory` uses the bulk path AND threads `client_name` from `client_portfolio_overview` rows, so the per-client `client_deep_profile` lookup (4 fresh ro-connections/client — the residual N×4 blowup) is skipped. Check (live DB): `python3 -c "import time;from pathlib import Path;from lib.intelligence.trajectory import TrajectoryEngine as T;e=T(db_path=Path.home()/'.moh_time_os/data/moh_time_os.db');t=time.perf_counter();r=e.portfolio_health_trajectory();print(round(time.perf_counter()-t,3),'s',len(r),'trajs')"` → ~0.28s / 134 (was 160s un-optimized; 579.8×; output 134/134 byte-identical to the per-entity path). Commits `58a5c41` (bulk) + `7a755ab` (deep-profile skip).
- **Xero refresh token:** still empty (len 0) → live Xero sync fails `invalid_client`. Check: `python3 -c "import json;print(len(json.load(open('config/.xero_token_cache.json')).get('refresh_token','')))"` → `0`. (BLOCKED on operator OAuth — see §Now.)
- **DB size:** ~301 MB. Check: `ls -la data/moh_time_os.db`.
- **Enforcement repo coupling: REMOVED (PR #113).** `ci.yml` on main has 0 enforcement refs; "protected files" are editable. Main Gate requires only: Python Quality, Python Tests, UI Quality, System Invariants, Security Audit, API Smoke. Governance Checks (ADR + change-size) is NON-blocking. Check: `git show origin/main:.github/workflows/ci.yml | grep -c enforcement` → 0.

---

## 1. What this is

MOH Time OS: a ~134k-LOC Python personal-intelligence system. Collectors pull from Asana/Xero/Gmail/Calendar/Chat/Drive into a SQLite DB; an in-process 8-stage daemon (`lib/daemon.py`: collect → lane_assignment → truth_cycle → detection → intelligence → snapshot → morning_brief → notify) runs the cycle; a FastAPI server (`api/server.py`, port 8420) serves a dashboard. Two launchd agents: `com.mohtimeos.api` (uvicorn) and `com.mohtime.daemon` (the scheduler).

## 2. Architecture facts that bite (always-on reference)

- **The daemon runs from the MAIN checkout** `/Users/molhamhomsi/clawd/moh_time_os` (plist `WorkingDirectory`). A merged fix isn't live in the daemon until the main checkout is on `origin/main`. Keep it on `main`.
- **Credentials propagation:** launchd plists carry env inline so daemon/API subprocesses inherit them. Cron/manual shells do NOT. `config/.credentials.json` is a Google service-account file (no `xero` key) — misnamed; not a multi-vendor store. The daemon plist now also carries `ASANA_PAT=$ASANA_TOKEN` (the WS4 Asana fix, applied early at bring-up — Asana syncs live).
- **WS2 auth is now wired (PR #123):** a global ASGI `AuthMiddleware` enforces a Bearer token on every non-allowlisted route; the SSE stream self-validates `?token=` (EventSource can't set headers). `api/auth.py:_API_KEY` is captured at IMPORT — tests/reloads must `importlib.reload(api.auth)` after setting `MOH_TIME_OS_API_KEY`. The API needs a persistent key in its plist or it generates a random one each restart (see [[moh-bringup-needs-api-key-env]]).
- **`QueryEngine._execute` opens a new read-only SQLite connection per call** — deadly in loops; the C2/C2b bulk paths (on main) fixed the detection hotspot (full-mode `detect_all_signals` now ~24s, was ~1800s).
- **Test harness for `api.server`:** the reliable pattern is fixture DB + `monkeypatch.setattr(lib.paths, "db_path"/"data_dir", ...)` + reset `StateStore._instance=None` + reload `api.auth` then `api.server` + plain `TestClient` (NOT context manager). Setting `MOH_TIME_OS_DB` alone is insufficient (StateStore is a process-wide singleton). NEVER open the infinite SSE stream in a TestClient assertion (it hangs).

## 3. Daemon health-check entry

`HealthChecker` (NOT `HealthMonitor` — that name is stale in old docs). `from lib.observability.health import HealthChecker; HealthChecker()._check_daemon_health()`.

## 9. Health checks (read-only; re-derive §State)

```
launchctl list | grep -i mohtime
ps aux | grep -E "[m]oh_time_os/.venv/bin/python"
curl -s -o /dev/null -w '%{http_code}\n' --max-time 6 http://127.0.0.1:8420/api/health
python3 -c "import json;d=json.load(open('$HOME/.moh_time_os/data/daemon_state.json'));print(sorted(d['jobs']),d['updated_at'])"
git fetch origin main && git rev-parse --short origin/main
```

---

## 10. Now

**As of 2026-06-04 (StateStore write-path COMPLETE — all 3 PRs merged).**

**Most recent shipped (all MERGED to `origin/main`, HEAD `b6aef19`):**
- **StateStore write-path completion** (follow-on to #152 `execute_write`/`transaction` + #154). Migrated all 11 write-via-`query()` call sites to `store.execute_write()`, then added a read-only guard to `StateStore.query()`. Shipped as 3 sequenced PRs (merge order was load-bearing — guard last):
  - **PR [#157](https://github.com/Fleezyflo/moh-time-os/pull/157)** (`8b7d7a9`, `lib/autonomous_loop.py`): the LIVE daemon path — `_process_commitment_truth:1310` marks emails processed. 1 site.
  - **PR [#158](https://github.com/Fleezyflo/moh-time-os/pull/158)** (`48cfaf5`, 5 truth helpers): `capacity_truth/debt_tracker.py` (1), `client_truth/linker.py` (**2** — the brief listed 1; a re-grep found the `UPDATE client_projects` in `link_project_to_client:62`), `commitment_truth/commitment_manager.py` (4), `state_tracker.py` (1), `time_truth/block_manager.py` (2).
  - **PR [#160](https://github.com/Fleezyflo/moh-time-os/pull/160)** (`4334316`, `lib/state_store.py`): `query()` now raises `RuntimeError("query() is read-only; use execute_write()")` for INSERT/UPDATE/DELETE/REPLACE/CREATE/DROP/ALTER/TRUNCATE/VACUUM/ATTACH/DETACH/REINDEX. Allows SELECT/WITH/EXPLAIN/PRAGMA. `_first_sql_keyword()` strips leading whitespace + `--`/`/* */` comments. Implementation at `lib/state_store.py:307-308` (guard), `:25` (`_WRITE_KEYWORDS`), `:49` (`_first_sql_keyword`).
- New tests (all on main): `tests/test_autonomous_loop_write_path.py` (3), `tests/test_truth_helpers_write_path.py` (15), `tests/test_state_store_query_guard.py` (11). Verification log: `audit-remediation/VERIFICATION_LOG_S_writepath_query_guard.md`.

**What works right now (verified THIS session on this Mac):**
- **The read-only `query()` guard is LIVE on `origin/main`** and on this checkout. `TestWritePathRule` (3) + `TestWritePathBehavioralExtended` (7) are green; full write-path surface = **41 tests pass** on `b6aef19`.
- **Migrated writers still work WITH the guard live** (18 writer tests pass) — `query()` reads work, `execute_write()` persists, `query()` writes raise "read-only".
- **Full-suite regression delta from the writer migration + guard: 98 → 91 failures, 0 introduced** (6 write-path guard tests fixed). The 91 remaining are pre-existing rot (CI gates only 7 subdirs).
- This checkout is **on `main`, synced with origin** (`git rev-list --left-right --count HEAD...origin/main` → `0 0`), so the daemon runs the code with the guard + migrated writers.
- ruff/bandit clean, mypy strict islands 0, all PRs passed full CI.

**Live state caveats:**
- **Daemon NOT restarted this session.** The running daemon process started before these merges, so it still runs pre-migration code in memory. It's safe either way (the guard only matters once it restarts; the running process used the old `query()`-write path which still worked). To pick up the guard + migrated writers in the live daemon: `launchctl unload ~/Library/LaunchAgents/com.mohtime.daemon.plist && launchctl load -w ~/Library/LaunchAgents/com.mohtime.daemon.plist`. Operator's call — not done automatically.
- **launchd/API/daemon health NOT re-checked this session** (the work was code + merges). Run §9 before trusting "system is LIVE".
- **`lib/state_store.py` was NOT blocked by an Enforcement Gate** — PR #160 merged cleanly through full CI, confirming it is not blessed-protected (or the Gate is inactive per PR #113's decoupling).

**Concurrent-agent note (this session):** two other agents worked in this shared checkout simultaneously — PR [#156](https://github.com/Fleezyflo/moh-time-os/pull/156) (daemon resilience, `lib/daemon.py`) and PR [#159](https://github.com/Fleezyflo/moh-time-os/pull/159) (`test_task_project_linker` singleton rot). Both MERGED. Their files had ZERO overlap with the write-path 7; I branched each of my PRs from `origin/main` and `git add`ed only my files. #159 left stale leftovers (`tests/test_task_project_linker.py` mod + an untracked log) that blocked the final `git pull` — cleared after confirming they matched/were superseded by the merged versions (backup at `/tmp/chip_singleton_log_backup.md`).

**Open items, in priority order:**
1. **Schema drift (worth a follow-up):** live `commitments` has `commitment_id` PK; canonical `schema_engine`/fixture has `id` and NO `commitment_id`. `commitment_manager` link/mark SQL targets the live shape, so its behavioral tests build the table with the live shape. The fixture schema is behind the live DB here. Out of scope for the write-path work; a real fix reconciles `schema_engine` with the live `commitments` table.
2. **Two OPERATOR actions still outstanding:**
   - **Xero OAuth:** `config/.xero_token_cache.json` refresh_token len 0 → live Xero sync fails `invalid_client`. Run `.venv/bin/python -m cli.xero_auth` (browser consent, port 8742) once.
   - **Rotate the leaked GCP SA key** in `config/.credentials.json` per `docs/runbooks/rotate-sheets-to-xero-sa-key.md`, then point `CREDENTIALS_JSON_FILE` at the out-of-repo path.
3. **Pre-existing test rot persists** (~91 full-suite failures outside the 7 CI-gated subdirs). The `test_task_project_linker` pair was fixed by #159 this session; the rest remain.

**Pick up here:**
- **The write-path task is DONE.** No follow-on action required for it. If verifying: `git rev-parse --short HEAD` → `b6aef19`, then `.venv/bin/python -m pytest tests/test_state_store_query_guard.py tests/test_truth_helpers_write_path.py tests/test_autonomous_loop_write_path.py -q` → 29 passed.
- **If a writer regresses in CI later:** the guard is the likely tripwire — grep the failing module for `.query(` with a write keyword on the call/next line and move it to `store.execute_write()` (pattern: `lib/task_project_linker.py`).
- **This shell runs directly on the Mac** — run git/sqlite/gh/pre-commit/launchctl yourself. Commits need `source .venv/bin/activate` first (pre-commit calls bare `python`). The `Sync UI generated types` pre-commit hook can fail the FIRST commit attempt by regenerating `time-os-ui/src/types/generated.ts`; if `generated.ts` then shows no diff, just re-run the same commit (it passes on the 2nd attempt). `large-change`/`Deletion rationale:` go in the HEAD commit msg only ([[moh-ci-gates-and-merge]]).
- **Shared checkout:** other agents may move HEAD / leave dirty files here mid-task ([[moh-shared-checkout-concurrent-agent-hazard]]). Always branch PRs from `origin/main` and `git add` explicit paths only; never `git add -A`. Keep this checkout on `main` after merges (the daemon runs from it).
