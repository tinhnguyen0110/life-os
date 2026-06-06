# End Sprint 11 — Brief (S11) [template-based daily report · NO AI · Home now has 0 stubs]

> Result doc (CLAUDE.md §3.2). The `brief` module: a TEMPLATE-based daily report (NO AI — deterministic rules on real data) that assembles the user's actual situation into severity-ranked numbered priorities. + the S11 screen + the Home Brief tile swap — **the LAST Home stub → live**. Penultimate screen (only S12 Settings remains for all 14).
> Author: architect · 2026-06-06 · Commit: `feat(sprint-11)` on `main`.

---

## 1. What shipped

### Backend — `brief` module (template aggregator, NO AI)
- **`brief` module** (registry auto-discovered): `GET /brief` (assemble a brief NOW from live module data) + `GET /brief/history`. REUSES `morning_pull`'s cross-module-read pattern (projects/finance/market/claude/alerts, fail-soft per source).
- **5 deterministic priority RULES** (NO LLM — CLAUDE.md hard rule): market/ladder (rung hit→urgent, near-2%→info), project (build-to-90 progress≥90&users==0&not-abandoned→urgent [abandon-orthogonal, NOT health=dead]; idle>7d→warn), claude quota (pct≥90→urgent, ≥75→warn, stale caps at warn), finance drift (driftAlert→warn), alerts (top non-ladder market alert→warn). Reused pattern_check/idle_hunter/driftAlert verbatim for 3 rules.
- **Brief** `{generatedAt, asOf, source:"template", summary{netWorth,projectsActive,claudePct,alertsToday}, priorities[Priority{n,text,source,severity}], stale, warnings}`. **Display order = severity DESC, tiebreak rule-order** (deterministic); `n` = 1-based display rank. **source="template"** (NOT opus — NO AI). honest-empty → priorities=[] + real summary.

### Frontend — S11 Brief screen (`app/brief/page.tsx`) + Home Brief tile (the LAST stub)
- Ported the briefcard + full screen: header ("template" NOT opus + stale badge), summary tile, severity-styled numbered priorities (urgent=red/warn=amber/info=neutral), brief history, fail-soft warnings.
- **Honest-empty = a CALM green state** ("✓ Ổn định — không có việc khẩn"), NOT an error/blank.
- **Home Brief tile swap (page.tsx:176)** — ComingSoonStub → live brief tile. **Home now has ZERO stubs — every tile live** (netWorth/P&L/Claude/projects/alerts/Activity/Brief).

---

## 2. Verification (Rule #0)

### The brief assembles the user's REAL situation (NO AI, deterministic)
team-lead + tester verified `GET /brief` on the container serves real-data priorities: "[warn] crewly đứng 69 ngày" (rule 2 idle — a genuinely 69d-idle repo), "[warn] crypto +58.1% drift — rebalance?" (rule 4 — real allocation), "[warn] BTC alert hôm nay" (rule 5). source="template", stale=True (claude cache 7wk, honest), summary real. A genuinely useful + honest + no-AI daily report.

### Architect 4-step (full functions + live container)
| Check | Result |
|---|---|
| pytest | **641 passed** (tester-reported; brief tests + the suite) |
| vitest | **347 passed** (≥329 baseline; +18 brief/Home) |
| tsc | clean |
| Container `/brief` | 7 keys, source="template", stale=True, 3 real severity-ranked priorities, real summary |
| template-not-opus (page.tsx:4) | NO AI label ✓ |
| severity styling (17-19, .pr.urgent/warn/info) | ✓ |
| honest-empty calm (line 8) | "ổn định" green state, not error ✓ |
| Home stubs | **ZERO ComingSoonStub** — every tile live ✓ |
| home.test.tsx rewrite (FE) | proper sync-to-reality (asserts stubs GONE, not a mask) — `tester-scaffold-ownership` exception, flagged + routed to tester ✓ |

### team-lead Rule#0 live value-diff
✅ /brief real priorities (crewly/drift/alert), source=template, severity-ranked, summary real, stale honest — deterministic + no-AI, genuinely useful. PASS, pre-greenlit.

### Tester T4 (PENDING API+Chrome — their lane; pre-scaffolded with build-to-90 distinguishing teeth)
pytest (each rule fires/not; build-to-90 abandon-orthogonal distinguishing; fail-soft; honest-empty; severity-sort) + API + Chrome.

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema (Brief/Priority frozen, Literal source/severity) · ☑ integration tests · ☑ existing pass · ☑ auto-discovered · ☑ envelope · ☑ codes (200 fail-soft) · ☑ self-describing (priority carries source+severity; summary structured).

### Gate 2 — Function
☑ unit tests (5 rules fire/not; **build-to-90 abandon-orthogonal distinguishing**; fail-soft per source; honest-empty; severity-sort) · ☑ pytest 641 + vitest 347/0 · ☑ edge cases (source down, all-down, no-conditions, stale, empty data) · ☑ tsc clean · ☑ FE Chrome self-verify · ☑ NO AI (deterministic — same input → same brief).

### Gate 3 — Sprint
☑ end_sprint_11 written · ☑ architect 4-step · ☐ **tester T4 — PENDING** · ☑ counts ≥ baseline (pytest 612→641, vitest 329→347) · ☑ findings flagged (§5) · ☑ format `feat(sprint-11)`.

**VERDICT: backend + FE GREEN. Gate 3 holds on tester T4 + team-lead pre-greenlit → commit on T4 report.**

---

## 4. Assumptions (user-review — decide-and-log)

- **Brief = TEMPLATE (deterministic rules), NO AI** (CLAUDE.md + SPEC + ARCH §11 hard). source="template", not "opus". AI-generated brief is the later MCP phase. To change: that's the future Claude-Code build.
- **5 priority rules + thresholds:** market rung-hit→urgent/near-2%→info; build-to-90→urgent / idle>7d→warn (abandon-orthogonal, NOT health); claude pct≥90→urgent/≥75→warn/<75→none (stale caps warn); finance driftAlert→warn; alerts top-non-ladder→warn. To change: edit the rule thresholds.
- **Display = severity DESC, tiebreak rule-order** (deterministic for a testable template, not recency). `n` = display rank.
- **honest-empty** = priorities:[] + real summary; the "ổn định" calm text is FE-side. NEVER fabricate urgency.
- **summary structured** (4 fields, FE composes the string) — agent-readable. asOf=min(source asOf); stale=any source stale.
- **history** — [] until T2 persistence lands (morning-pull writes brief/<date>.md). This sprint = on-demand generation; history is a thin follow-up.

---

## 5. Risks / out-of-scope (future)

- **Brief persistence/history** (T2) — md_store brief/<date>.md when morning-pull runs; history reads them. Thin follow-up (or this sprint if folded).
- **AI-generated brief** — the later MCP/Claude-Code phase. This is template.
- **Container flap** — recurring (5th+); for the Sprint Sync: a CLAUDE.md §dev "stack must be detached (`up -d`)" rule so it's the default everyone starts from (architect can draft).
- **Home stub milestone** — Home now has 0 stubs (every tile live). The app's first screen is fully real.

---

## 6. Retro (process learnings)

1. **Backend's textbook escalation** — it split "already-locked (build now)" from "decide-and-log (won't invent)" + named exactly the 3 thresholds the rules prose left soft (claude 90/75 cutoffs, ladder near-%, alert-vs-ladder dedup). Resolved with concrete numbers. The decide-and-log discipline working from the implementer side.
2. **Reused 3 rules verbatim** — finance driftAlert, pattern_check (build-to-90), idle_hunter — the brief composes existing logic, doesn't re-implement. Rule#0-at-kickoff found morning_pull + these rules already exist.
3. **FE's home.test sync-to-reality** — removing the LAST Home stub turned 2 stale stub-asserting tests RED (a TRUE change); FE rewrote them to assert the live reality (stubs GONE), not a mask. The `tester-scaffold-ownership` exception, flagged + routed to tester. (Sync to ratified reality OK; mask NOT.)
4. **Home now has 0 stubs** — every tile live. The aggregate-incrementally approach (Home grows as modules land) completed.

---

## 7. Commit
- `feat(sprint-11): brief module (S11) — template daily report + 5 priority rules + S11 screen + Home Brief tile (last stub→live)` — brief module + brief page + useBrief + Home swap + plan_11 + end_11. One commit.
- Gated on tester T4 + team-lead pre-greenlit. After: `sleep 120 && git push` → notify user → Sprint Sync → S12 Settings (the FINAL screen → all 14).
