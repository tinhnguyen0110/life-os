# Operating Model — life-os (Mode B full-auto)

> The team's operating contract. STATIC rules that don't change per-sprint → versioned in git (unlike sprint-to-sprint learnings, which live in project memory and are read on-demand). CLAUDE.md §3 references this file. team-lead + all agents follow it.
> Chốt: 2026-06-06 (user-directed).

---

## 0. Autonomy — decide by default, never block

team-lead RUNS the team autonomously. Default for any fork / ambiguity / missing logic = **DECIDE and proceed**, not ask. User wants the final result, not the per-sprint play-by-play. Sprints/steps are internal — user does not need to know how many sprints a step takes.

**Escalation (the only path when something genuinely should surface to user):**
1. `python .claude/process/notify.py "<msg>"` — Discord ping.
2. `ScheduleWakeup` ~300s — short window for user to weigh in.
3. No reply by wakeup → team-lead **decides and continues**. No further blocking.

Never use `AskUserQuestion` (hard rule, CLAUDE.md §4). A plain-text "tôi sắp làm X" to the user is fine but is NOT a blocking gate — proceed unless user says "no/wait/hold".

**Logic ownership chain:** architect proposes the algorithm → team-lead reviews "reasonable?" → team-lead is final decider. Don't pull the user into logic calls. Log decisions to `end_sprint_X.md` §Assumptions for async review.

---

## 1. Mode B — full-auto loop

The team runs `sprint → push → next sprint` **continuously**, pings but does NOT block on the user (user chose Mode B over checkpoint mode, 2026-06-06). Speed is the point; the two immune rules below (§2, §3) replace the safety a checkpoint pause would have given.

After push: team-lead auto-starts the next sprint (notify "starting Sprint X+1", proceed unless user says no/wait/hold). The loop only stops on a true blocker or a "100% pass" failure.

---

## 2. Rule #0 — Trust NO teammate's claim (verify-don't-trust)

A teammate reporting "done / pass / works" is a CLAIM, not truth. Nothing is accepted without team-lead or tester independently confirming with REAL evidence:
- "tests pass" → re-run the command, read the actual counts
- "file written / DB updated" → read the file on disk / query the row / `git log -1 --stat`
- "endpoint works" → curl it, inspect the payload
- "reader returns the shape" → run it on a REAL repo, diff against the locked shape

Claim without reproducible evidence = NOT done. This is the defense that replaces Mode B's dropped checkpoint pauses. Applies to backend, frontend, tester, architect — and team-lead applies it to itself.

### 2.1 — Teammates MUST reply to team-lead via `SendMessage` (HARD)

Every teammate (architect/backend/frontend/tester) MUST send their reply, report, readiness check, blocker, or question to team-lead through `SendMessage({to:"team-lead", ...})`. **Plain-text output is invisible to the rest of the team** (the tool itself warns: "Your plain text output is NOT visible to other agents"). A teammate that "answers" in plain text without SendMessage has, from team-lead's view, said nothing — this is the #1 cause of silent-stall.

Rules:
- **Done / report** → `SendMessage` to team-lead with the evidence (per Rule #0). Plus `TaskUpdate status:completed`. The message is the source of truth; a `[completed]` task with no message = team-lead asks for the report before moving on.
- **Blocked / question / needs a decision** → `SendMessage` to team-lead (NEVER AskUserQuestion, NEVER just print it). Team-lead decides per §0.
- **Readiness / acknowledgement** → `SendMessage` to team-lead, then go idle.
- Use `TaskUpdate` for status transitions, `SendMessage` for the actual content. Don't send structured JSON status as a message — plain text content.

If a teammate is silent >20 min after dispatch, or TaskList shows `in_progress` but `git status`/`ls` shows no change → team-lead pings `[STATUS check]` (CLAUDE.md §3). But the teammate's standing obligation is to PROACTIVELY SendMessage, not wait to be chased.

---

## 3. Sprint Sync — the 2-phase ritual after every sprint

Run by team-lead after push, BEFORE starting the next sprint. Two directions catch DIFFERENT problems:
- **Top-down Retro** catches errors a teammate doesn't know they made (claimed pass, DB empty).
- **Bottom-up Standup** catches process/dispatch/coordination friction only the people who did the work can feel (vague dispatch → backend guessed; tester tested too early; missing fixture path). A bad dispatch repeats EVERY sprint until someone speaks up.

### PHASE 1 — Standup (bottom-up; team-lead asks each participating teammate via SendMessage)
Ask ONLY teammates who worked the sprint (usually all 4; light sprint may be 2-3). Three questions:
1. "Sprint vừa rồi vướng gì? Cần gì để làm nhanh hơn?"
2. "Theo bạn lý do là gì — do bạn / dispatch / phối hợp / context thiếu?"
3. "Đề xuất cải thiện?"
Teammate answers short (blocker / need / suggestion). Silence = "no friction."

### PHASE 2 — Retro (top-down; team-lead JUDGES — Rule #0 applies to standup claims too)
A teammate saying "I was blocked by X" is itself a CLAIM — could be real (fix the process) or blame-shifting (it actually skipped reading the spec). team-lead verifies against evidence, does NOT auto-record the teammate's words:
1. Cross-check each standup claim vs real evidence (git log, files, test output, the actual dispatch text).
2. What error REALLY happened / who / ROOT cause (not the self-report, not the symptom).
3. Fix + how to prevent recurrence.
4. Write the learning to the RIGHT place (see §4).
5. team-lead self-retro: was MY dispatch vague? did a gate leak? what process to fix?

→ THEN start the next sprint.

### PHASE 3 — Discord report (MANDATORY after every Sprint Sync — user directive 2026-06-06)
After Standup + Retro, team-lead sends the user a Discord report (`python .claude/process/notify.py "<msg>"`) — user directive (2026-06-06): **after EVERY sprint, report TWO things: (1) the sprint RESULT, (2) the MEETING (Sprint Sync).** The user reads these async to stay in the loop without watching every step. Two clearly-labelled parts:

**PART 1 — SPRINT RESULT** (what the team produced):
- **Shipped** — what landed + commit hash + headline counts (pytest/vitest).
- **Verification** — team-lead's Rule #0 re-run result (pass/fail with numbers).
- **Features delivered** — the user-visible capability this sprint added (e.g. "Projects screen now reads your real git repos").
- **Next sprint** — what's coming + any notable decide-and-log call the user may want to review.

**PART 2 — THE MEETING (Sprint Sync)** (how the team worked):
- **What the immune system caught** — bugs/claims Rule #0 + guards stopped (signal the process works).
- **Incidents handled** — any failures + how recovered (no work lost).
- **Standup highlights** — teammate friction + convergent asks + accountability.
- **Learnings logged** — count + where (memory/playbook/process).

Keep it skimmable (the two headers + bullets). Send it as ONE Discord message (or two if long). This is the user's primary async window into the team — both the output AND the process, every sprint.

**Who sends it:** team-lead sends the Discord report (team-lead did the independent Rule #0 verification → has the full picture of both result + process). In full-auto, architect runs Standup+Retro then signals team-lead "Sprint X synced"; team-lead writes + sends the 2-part report. Never skip it — every sprint, both parts, even a clean sprint (then PART 2 is short: "clean, no incidents").

**Ordering matters:** Standup FIRST (collect raw signal from the people who did the work) → Retro SECOND (filter real-vs-blame + assign root cause) → Discord report THIRD (summarize for the user). Retro-first = team-lead judges blind, misses friction only teammates feel. Standup-only = trusts teammates blindly, violates Rule #0.

### Handling "I need X to go faster"
- **Within team-lead's reach** (more fixtures, earlier mock API, clearer dispatch context, a fixture repo path) → grant immediately, no asking the user.
- **Outside reach** (paid API, a new repo to track, scope change) → batch + notify user; decide-and-log if no reply.

---

## 4. Where learnings go — static vs dynamic (do NOT get this wrong)

Playbooks (`.claude/agents/<role>.md`) are FROZEN into a teammate's system prompt at spawn. Editing one while that teammate is alive does NOTHING for the current run — it only lands on respawn. So:

| Learning type | Where | Why |
|---|---|---|
| Needed THIS / next sprint | **project memory** | read on-demand, never stale, no respawn needed |
| Recurring (≥2 sprints) / permanent law | **that role's playbook** | takes effect on next spawn; promote only once proven |
| Stable operating rule (this file's topics) | **this file** (git) | versioned, synced, the contract |
| Clean sprint | one line "clean", no invented lesson | avoid ritual bloat |

`## Assumptions (user-review)` in each `end_sprint_X.md` is the async review queue — every algorithm/business rule architect decided that sprint, one line: `<feature>: <rule> — <why> — <how to change>`.

---

## 5. Data-source fallback — never wait for paid data

When a data source is missing/unverified (claude-usage path, market feeds, finance golden-path, project git readers), work top to bottom, NEVER block:
1. **Research docs** — official/local docs for how to obtain it.
2. **WebSearch** — how others fetch it (free endpoints, formats, parse strategy).
3. **Verify at local** — inspect the real payload/file on this machine now (e.g. `~/.claude/stats-cache.json`, transcript `.jsonl` for claude-usage) before coding against it.
4. **Crawl / build a tool** — if no clean API, write a reader/crawler.
5. **Paid-API-only → BUILD MOCKDATA, do not wait.** Ship realistic mock now (use mock `template/Life Command/app/data.js` shapes); wire the real source later.

**Core principle:** system LOGIC is identical whether data is real or mock — only the source swaps. Never stall a sprint waiting for real data. Build against the schema with mock, swap the reader later (mock-first, then real — user-confirmed pattern).

Known-unverified sources: claude-usage (S9, source verified local: stats-cache + jsonl) · market price (S8, per-asset-class; CoinGecko free for crypto, mock ETF/VN) · finance golden-path (S5/S6, file absent → architect decides ladder+allocation via decide-and-log, baseline = data.js alloc Crypto38/ETF24/VN18/Dry20).
