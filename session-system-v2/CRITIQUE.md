# Critique of Current Session Persistence System

**Date:** 2026-02-28
**System under review:** MOH Time OS session management (CLAUDE.md, BUILD_STRATEGY.md, BUILD_PLAN.md, SESSION_LOG.md, HANDOFF.md)

---

## What Works

The current system successfully shipped 8 phases across 12 sessions, producing 14 merged PRs. It maintained code quality (zero mypy baseline, zero bypasses, clean CI). The enforcement repo concept — a separate repo with compliance authority over the project — is sound and should be preserved.

Specific strengths:

1. **Enforcement repo separation.** The project cannot modify its own CI or protected files. The enforcement repo has unilateral authority. This is the right architecture.
2. **Protected file restoration.** Every CI job restores blessed copies before running checks. The branch's version is irrelevant. This prevents circumvention.
3. **Pre-commit + CI redundancy.** Local hooks catch issues before push. CI catches issues after push. Neither is optional.
4. **Contract tests.** Schema drift, OpenAPI drift, system map drift — all detected automatically.
5. **Session type classification.** Build, Verification, Plan Update, Investigation — forces intentionality about what a session does.

---

## What Fails

### 1. Documentation is voluntary, not structural

The system relies on the agent choosing to update four files in the right way at the right time. There is no mechanism that prevents a session from ending without updating BUILD_PLAN.md completion markers. The trigger table, the enforcement checklist, the cross-file consistency rules — all exist as prose instructions that the agent can read and then not follow.

**Root cause:** The documentation system is advisory. It describes what should happen but has no structural enforcement. An agent can read "mark phases complete in BUILD_PLAN.md" and simply not do it. There is no CI check, no pre-commit hook, no validation script that catches this.

**Evidence:** Phases 1, 2, 3 went unmarked for three sessions. The instructions to mark them existed the entire time.

### 2. State lives in prose, not in structured data

SESSION_LOG.md is a free-form markdown file. HANDOFF.md is a free-form markdown file. BUILD_PLAN.md uses `✅ COMPLETE` as a marker but has no machine-readable structure. No script can parse these files and answer "which phases are complete?" or "is the handoff consistent with the session log?"

**Root cause:** The system was designed for human reading, not machine validation. An agent reading prose can miss inconsistencies that a script comparing structured fields would catch instantly.

### 3. The plan is monolithic

BUILD_PLAN.md is one massive document covering Phases -1 through 13. Each phase is specified inline. There is no separation between the plan structure (what phases exist, their dependencies, their status) and the plan content (detailed specs for each phase). This means:

- An agent must read the entire document to find the current phase
- Completion status is embedded in section headers, not in a queryable index
- Dependencies are described in prose, not in a graph

### 4. Rules accumulate without categorization

CLAUDE.md grew organically. It has 12 code rules, 6 verification requirements, 4 session discipline items, a documentation rules section with a trigger table, and scattered "Session N learned this" annotations throughout. Rules are not prioritized. An agent reading this file gets equal weight on "no f-string SQL" and "use `--` not em dash in commit messages."

### 5. HANDOFF.md key rules list is a flat dump

32 rules in a numbered list. No grouping. No priority. An agent is expected to absorb all 32 and weight them equally. The most critical rules (don't run git from sandbox, mark phases complete) sit alongside formatting rules (lowercase after prefix).

### 6. No automated consistency checking

There is no script that verifies:
- Every completed phase in SESSION_LOG.md has a ✅ marker in BUILD_PLAN.md
- HANDOFF.md "What Just Happened" matches the latest SESSION_LOG.md entry
- HANDOFF.md doesn't reference "pending" or "unstaged" work that has already been committed
- BUILD_PLAN.md phase dependencies are satisfied before a phase can start

### 7. Enforcement repo wiring is manual and fragile

The current enforcement setup required manual token creation, manual workflow writing, manual protected-files.txt maintenance. The blessed-copy-restore pattern is copy-pasted 10 times in ci.yml (once per job). A new project would need to recreate all of this from scratch.

### 8. No plan decomposition

The system has no mechanism for taking a large plan and breaking it into session-sized work units. BUILD_STRATEGY.md says "one session, one phase section" but provides no tooling to actually decompose a phase into session tasks or to verify that a session's output matches its assigned scope.

### 9. Session boundary is undefined

What constitutes a "session"? When does one end? The system says "update docs before session ends" but there's no structural marker for session boundaries. A session that runs out of context (as happened before Session 12) loses all uncommitted documentation updates.

---

## Design Principles for v2

1. **State is structured data, not prose.** Everything that an agent needs to check can be parsed by a script.
2. **Consistency is validated, not requested.** A pre-commit hook or CI check catches doc inconsistencies, not an instruction that says "please check."
3. **Plans decompose into tasks. Tasks decompose into steps.** Each is independently verifiable.
4. **The agent's context window is the session boundary.** Design around it, don't fight it.
5. **Enforcement is a template.** Setting up a new project with full enforcement takes minutes, not days.
6. **Rules are categorized and prioritized.** Critical rules (data loss, security) are separated from style rules (commit format).
7. **The handoff is a computed artifact.** It's generated from structured state, not written by hand.
