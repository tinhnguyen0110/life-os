# End Sprint 7 — Claude Usage (S9) [5th module · real token source, real cost]

> Result doc (CLAUDE.md §3.2). The `claude-usage` module: reads REAL usage from `~/.claude/stats-cache.json`, derives cost from a pricing table (ClaudeManager-sourced), stubs honestly what's not on disk (quota cap / reset windows / per-project). + the S9 screen + Home quota-stub→live swap. The first module reading a host-file data source through the container.
> Author: architect · 2026-06-06 · Commit: `feat(sprint-7)` on `main`.

---

## 1. What shipped

### Backend — `claude-usage` module (registry auto-discovered)
- **`schema.py` (FROZEN)** — `ClaudeUsage{model,used,cap,pct,remaining,resetIn|None,weekly|None,series[DayBurn],today,avgPerDay,peak,byModel[ModelBurn],costUSD,byProject:None,asOf,stale,source}` + `DayBurn{date,label,tokens}` + `ModelBurn{model,inputTokens,outputTokens,cacheReadTokens,cacheCreateTokens,total,costUSD}` + `ManualOverride{cap,resetIn,weekly}`.
- **`reader.py`** — parse `~/.claude/stats-cache.json` (env-overridable `LIFEOS_CLAUDE_STATS_PATH`). Fail-open: missing/malformed → manual mode (used=0, source="manual", warning), never 500.
- **`pricing.py`** — per-model USD/1M rate table (opus-4-7/4-6 **15/75**, sonnet **3/15**, haiku **1/5**, sonnet fallback) from ClaudeManager's `lib/pricing.ts`. `cost = (in*inR + out*outR + cacheRead*0.1*inR + cacheCreate*1.25*inR)/1e6`.
- **`service.py`** — assemble + derive pct/cost/today/series/avg/peak. **Claude-only filter** (`model.startswith("claude-")`) on byModel/used/today/series/avg/peak/cost/model — non-Claude models excluded.
- **`router.py`** — `GET /claude-usage` (+ `?window=`) + `PUT /claude-usage/override`. Envelope, fail-open 200, 422 bad override. Auto-discovered.

### Infra — docker-compose `~/.claude` mount (architect)
Mount `${CLAUDE_HOST_DIR:-${HOME}/.claude}:/claude-home:ro` + `LIFEOS_CLAUDE_STATS_PATH=/claude-home/stats-cache.json` — so the canonical container reads the real cache (without it, fail-open to empty). → memory `host-file-source-must-mount`.

### Frontend — S9 screen (`app/claude-usage/page.tsx`) + Home swap
- Ported `SCREENS.claude`: gauge (pct/used/cap/remaining/weekly), 3 stat cards, daily-bar chart (series), per-model segment, per-project marked stub. `useClaudeUsage.ts` + `getClaudeUsage()` + types.
- **Ruling 1 — prominent stale badge** (lines 62-70): ⚠ pill near title "dữ liệu tính đến <asOf> · chưa cập nhật" + relative time. Not a footnote.
- **Ruling 2 — cost composition** (lines 95-103): headline total costUSD + cache-read $ breakout ("trong đó ~$X cache-read") computed FE-side from byModel.cacheReadTokens (self-describing-raw).
- Honest stubs: resetIn "chưa nối", weekly "—", per-project "Sắp có — cần parse transcripts (xem ClaudeManager)".
- **Home tile swap** (`app/page.tsx:141`): ComingSoonStub → `<HomeClaudeTile />` (live pct ring, self-fetches, per-tile fail-open).

---

## 2. Verification (Rule #0 — architect + team-lead; tester T4 = the open box)

### Architect 4-step (read FULL functions + live container)
| Check | Result |
|---|---|
| pytest | **475 passed, 0 errors** |
| vitest | **268 passed (30 files)** (≥254 baseline; +14 S9) |
| tsc | clean (exit 0) |
| Container `/claude-usage` (canonical, rebuilt) | 17-field shape, byModel **all claude-* (6, 0 non-Claude)**, source=stats-cache, stale=True, asOf=2026-04-17, costUSD=$39,145, byProject=null, resetIn/weekly=null |
| Ruling 1 stale badge (read page.tsx:62-70) | prominent pill, not footnote ✓ |
| Ruling 2 cost breakout (read page.tsx:20-25,95-103) | `cacheReadUSD()` helper + headline + sub-line, data-testid present ✓ |
| Home swap (page.tsx:141) | HomeClaudeTile live, old stub gone ✓ |
| Claude-only filter | verified on container — no MiniMax/glm/arcee ✓ |

### team-lead Rule#0 value-diff (live canonical, rebuilt with --build)
✅ Chrome S9 every value = API = real stats-cache (gauge 18.9%, 37.7k/200k, $39,146, 3 stats, 7 bars, 6 claude-* with cost) · stale handling PROMINENT · honest stubs · Home tile swapped live · console 0 errors. PASS, pre-greenlit.

### Tester T4 (Gate-3 UI verify — PENDING, their lane)
pytest + API curl + Chrome value-by-value on canonical + behavior-test fail-open (rename stats-cache → manual mode) + 0-unhandled.

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema constraints (Literal source/attach, ManualOverride validation) · ☑ integration tests · ☑ existing pass · ☑ auto-discovered · ☑ envelope · ☑ codes (200 fail-open, 422 override) · ☑ self-describing-raw (pct carries {used,cap}, costUSD provenance-tagged).

### Gate 2 — Function
☑ unit tests (reader parse, fail-open, cost math, Claude-only filter teeth-test, stale) · ☑ pytest 475/0 + vitest 268/0-unhandled · ☑ edge cases (missing file, malformed, empty series, cap=0, unknown model) · ☑ error path (fail-open manual mode) · ☑ tsc clean · ☑ FE Chrome self-verify (FE-touching).

### Gate 3 — Sprint
☑ end_sprint_7 written · ☑ architect 4-step (full functions + live container) · ☐ **tester T4 — PENDING** · ☑ counts ≥ baseline (pytest 344→475, vitest 254→268) · ☑ findings flagged (§5) · ☑ format `feat(sprint-7)`.

**VERDICT: backend + FE + infra GREEN. Gate 3 holds on tester T4 + team-lead pre-greenlit → commit on T4 report.**

---

## 4. Assumptions (user-review — decide-and-log)

- **Token source = `~/.claude/stats-cache.json`** (verified real). Usage/history/today/avg/peak/byModel = REAL. To change: point `LIFEOS_CLAUDE_STATS_PATH` elsewhere.
- **Cost = DERIVED from a pricing table** (stats-cache costUSD is 0). Opus-4.x **15/75** (ClaudeManager-authoritative; the claude-api skill's 5/25 is wrong/older). Cache read 0.1×, write 1.25× input rate. To change: edit `pricing.py`.
- **Claude-only filter** — byModel/used/cost include ONLY `claude-*` models; the real cache also has MiniMax (4.66B tok)/glm/arcee which would mis-price to $55k garbage. It's the Claude Usage screen → non-Claude excluded. To change: add an "other models" line if the user wants total-machine usage.
- **Quota cap = configurable 200_000** (mock-matching) + manual override; **pct = % of token cap**, not a USD budget. To change: PUT /claude-usage/override or edit config.
- **5h/weekly reset = honest stub** (None) — window state not persisted anywhere readable (not in stats-cache/settings/ClaudeManager). Manual-entry fallback. To change: wire if Claude Code ever exposes window state.
- **Per-project = marked stub** — derivable via `.jsonl` cwd-parse (ClaudeManager proves it) but heavier; "Sắp có — xem ClaudeManager". To change: a follow-up sprint parses transcripts.
- **Stale display** — cache was ~7wk old (asOf 2026-04-17); stale=True + prominent badge; "today" = last-computed day labeled asOf, never implied-live. stats-cache refreshes only when Claude Code recomputes (outside our control).
- **Cost composition** — $39k headline is ~95% cache-read (legitimate: 19.36B cache-read tokens / 3,913 sessions); FE shows the cache-read $ breakout so it's honest, not a scary context-free number.

---

## 5. Risks / out-of-scope (future)

- **Per-project attribution** — deferred (path real via ClaudeManager .jsonl cwd-parse); marked stub now.
- **Live reset countdown** — not readable; stub + manual-entry.
- **Cache-token pricing** — input/output + cache included; if exact billing wanted, refine cache rates.
- **Stale cache** — refreshes outside our control; we display honestly. A daily snapshot routine into SQLite `claude_usage_history` could give trend continuity if stats-cache rotates (deferred).
- **Sidebar badge hardcoded "71%"** (`lib/nav.ts:52`) — tester finding, NON-BLOCKING (out of T3 scope; the S9 screen + Home tile both show the correct live 18.9%). The sidebar nav badge is still the mock's static "71%", not wired to /claude-usage. Follow-up: wire the nav badge to the live pct (a small Quick-Fix or fold into a nav-polish sprint).

---

## 6. Retro (process learnings)

1. **3 real-cache bugs the fixture + empty container hid (the headline) → memory `host-file-source-must-mount` + `verify-live-app`:** (a) container couldn't read ~/.claude (no mount → fail-open empty); (b) non-Claude MiniMax priced at Claude rates → $55k garbage (Claude-only filter); (c) handcalc float test. All caught by team-lead's Rule#0 on the REAL container, NOT the fixture or bare-metal. Bare-metal-green ≠ canonical-correct.
2. **Stale-image verify trap → memory rule #6:** `docker compose up -d` reuses the OLD image; a code-fix re-verify needs `--build` or you curl stale behavior and mis-conclude "fix isn't there" (team-lead's own miss, logged). Rebuilt-≠-recreated, one layer below confirmed-in-chat-≠-in-code.
3. **ClaudeManager directive turned cost stub→live:** the user-pointed reference had a real pricing table → cost moved from "stub/out-of-scope" to a live derived field. Reusing the user's proven work beat building blind.
4. **Read-first rule's first live sprint** — every dispatch named the per-role memory files; backend investigated the source first (its S6 lesson) instead of freezing on a guess.

---

## 7. Commit
- `feat(sprint-7): claude-usage module (S9) — real stats-cache + derived cost + Claude-only + S9 screen + Home swap` — module (schema/reader/pricing/service/router) + docker-compose mount + useClaudeUsage/HomeClaudeTile/claude-usage page + plan_7 + end_7. One commit.
- Gated on tester T4 + team-lead pre-greenlit. After: `sleep 120 && git push` → notify user → Sprint Sync → next sprint.
