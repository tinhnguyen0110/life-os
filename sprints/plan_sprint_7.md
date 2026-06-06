# Plan Sprint 7 — Claude Usage (S9) [5th backend module · real-token-source]

> Author: architect · 2026-06-06 · Status: kickoff DONE (token source verified on disk) · awaiting team-lead mock-diff + greenlight.
> Spec: SPEC §S9. Mock: `template/Life Command/app/screens-system.js` `SCREENS.claude` + `DB.claude` (`data.js:20`) — HAS a mock → PORT. ARCH §6 (SQLite `claude_usage_history`) / §7 (`GET /claude-usage`) / §9 step 4.
> Memory to read: `claude-usage-token-source` (verified source + stub decisions), `claude-usage-reference-claudemanager` (the ClaudeManager parse/pricing/schema reference — user directive), `schema-freeze-gate`, `unhandled-errors-not-green`, `api-agent-readable-backlog`, `mock-diff-catches-dropped-feature`, `dev-server-ports`, `single-dev-no-overengineering`.

> **ClaudeManager reference read at kickoff** (`~/Disk_C/Data/Tinhdev/ClaudeManager`, read-only): its `lib/pricing.ts` = a REAL per-model USD/1M-token rate table (opus 15/75, sonnet 3/15, haiku 1/5; sonnet fallback for unknown) + `computeCost(tokensIn,tokensOut,model)`. Its `conversations/parser.ts` reads `.jsonl` per-message `msg.usage.{input_tokens,output_tokens}` + `msg.model` + cwd. Its `sessions.ts` shape carries `projectPath` + `tokenInputTotal/Total` + `costEstimate` → **per-project attribution IS derivable** (cwd-group the transcripts). Two upgrades vs my first pass: (1) **cost = derive from the pricing table** (kills the stats-cache `costUSD:0` problem), (2) **per-project = derivable** (heavier — keep marked-stub default this sprint per north-star, but the path is real, not impossible). Take pricing + parse-format + field shape; ship the SIMPLEST single-user S9 (user directive).

## Objective
Build the `claude-usage` module (router/schema/service/reader) + the S9 Claude Usage screen, and swap Home's `ComingSoonStub` (page.tsx:139) → a live quota tile. Read REAL usage from `~/.claude/stats-cache.json`; stub the data that isn't on disk (quota cap / reset windows / per-project) honestly with manual-override. Full feature surface per SPEC §S9, simplest impl (north-star).

## Token source — VERIFIED at kickoff (the SPEC-flagged item) → memory `claude-usage-token-source`
- **REAL (`stats-cache.json`):** `dailyModelTokens` (41 days, tokensByModel) · `modelUsage` (per-model in/out/cache tokens, costUSD often 0) · `dailyActivity` (msg/session/toolCall counts) · `lastComputedDate`, `totalSessions`.
- **NOT on disk anywhere** (grep-verified ~/.claude/*.json + settings + stats-cache): quota CAP, %-burned-vs-limit, 5h/weekly RESET countdown, per-project attribution.
- **Decision (verify-or-stub-and-log):** usage = real; cap = configurable default 200_000 + manual override (SPEC "fallback nhập tay"); %burned = used/cap (derived, carries {used,cap}); reset countdown + per-project panel = honest MARKED STUBS (mock has them → not dropped, per mock-diff lesson). Surface `asOf=lastComputedDate` — cache can be stale (~7wk at kickoff), never imply live.

## Vocab-lock (diff mock labels vs SPEC §S9 BEFORE dispatch)
Mock `SCREENS.claude` / `DB.claude` labels: "Claude Usage", "cửa sổ 5 giờ", "Quota hiện tại", "% đã đốt", "reset trong <resetIn>", "used/cap tokens", "Còn lại", "Weekly %", "~ session sâu", "Hôm nay / Trung bình·ngày / Đỉnh", "Token đốt theo ngày" (daily bar), "Đốt token theo dự án / routine" (per-project panel), segment "5H / Tuần / Tháng". SPEC §S9: token used/remaining/%burned · reset countdown (5h+weekly) · daily/weekly history chart · quota warning. **Match — FE ports mock labels verbatim.** Field names below mirror the mock keys (pct/used/cap/resetIn/weekly/series/model) so FE maps 1:1.

## Honest-mirror — every mock panel = live OR marked-stub (NOT dropped)
| Mock panel (SCREENS.claude) | Data | Sprint 7 |
|---|---|---|
| Quota gauge (pct/resetIn/used/cap, Còn lại, Weekly, ~session sâu) | used=real, cap=configured, pct=derived; resetIn/weekly=stub | **LIVE (real used) + stub reset** |
| 5H/Tuần/Tháng segment | dailyModelTokens windows | **LIVE** (today / 7d / 30d aggregations) |
| 3 stat cards (Hôm nay / TB·ngày / Đỉnh) | dailyModelTokens | **LIVE** |
| Daily token bar chart ("Token đốt theo ngày") | dailyModelTokens last 7d | **LIVE** |
| Per-project/routine burn panel | NOT on disk (model-only) | **MARKED STUB** ("sắp có — cần parse transcripts", honest, not dropped) |
| Home quota tile (page.tsx:139 ComingSoonStub) | this module's /claude-usage | **SWAP stub → LIVE** |

## ClaudeUsage SHAPE (FULL field list — goes IN the T1 gating dispatch msg #1, freeze field-by-field)
```
ClaudeUsage (GET /claude-usage response data):
  model:        str            # primary/most-used model label (mock: "claude-opus-4")
  used:         int            # tokens burned in the active window (default=today's total from dailyModelTokens)
  cap:          int            # configured quota cap (default 200_000; manual-override) — NOT from disk
  pct:          float          # derived: round(used/cap*100, 1) — carries {used, cap} (agent-readable)
  remaining:    int            # derived: max(cap - used, 0)
  resetIn:      str | None     # STUB: None (or manual) — 5h-window reset not readable from disk
  weekly:       int | None     # STUB: None (or manual) — weekly % not readable
  series:       list[DayBurn]  # last 7 days: [{date, label, tokens}] from dailyModelTokens (chart)
  today:        int            # today's (or lastComputedDate's) tokens
  avgPerDay:    int            # 7-day average tokens
  peak:         DayBurn        # highest-burn day in the window {date,label,tokens}
  byModel:      list[ModelBurn]# [{model, inputTokens, outputTokens, cacheReadTokens, cacheCreateTokens, total, costUSD}]
  costUSD:      float          # derived: sum over byModel of computeCost(in,out,model) via the ClaudeManager pricing table — NOT stats-cache's costUSD (often 0). carries provenance (agent-readable).
  byProject:    list | None    # MARKED STUB: None this sprint (derivable via .jsonl cwd-group per ClaudeManager, but heavier — screen shows "sắp có" marker, not dropped; wire real in follow-up)
  asOf:         str            # lastComputedDate from stats-cache (freshness — UI shows "data as of <date>")
  stale:        bool           # derived: asOf < today (cache behind → label honestly)
  source:       str            # "stats-cache" | "manual" (agent-readable provenance tag)

  DayBurn:   {date: str, label: str, tokens: int}   # label = weekday short (T2..CN)
  ModelBurn: {model: str, inputTokens: int, outputTokens: int, cacheReadTokens: int, cacheCreateTokens: int, total: int}

ManualOverride (PUT /claude-usage/override body — the SPEC "nhập tay" fallback, optional):
  cap?: int   resetIn?: str   weekly?: int   # only the fields the user wants to set manually
```
Envelope `{success, data, warning?}`. warning surfaces stale-cache / "stats-cache.json not found → manual mode".

## Tasks (4: BE gating → FE → tester)
- **T1 [backend, GATING] — claude-usage schema + reader + service.**
  - `schema.py`: the FULL shape above (ClaudeUsage / DayBurn / ModelBurn / ManualOverride). FREEZE field-by-field, announce serving + curl payload.
  - `reader.py`: parse `~/.claude/stats-cache.json` (path via core/config, env-overridable for tests — mirror finance's TINHDEV_ROOT pattern). Fail-open: file missing/malformed → `warning` + manual-mode defaults (used=0, source="manual"), NEVER crash. Compute today/avg/peak/series(7d)/byModel from dailyModelTokens+modelUsage. asOf=lastComputedDate, stale=asOf<today.
  - `service.py`: assemble ClaudeUsage; cap from config default (200_000) + any stored manual override; pct/remaining derived; resetIn/weekly = override-or-None; byProject=None (stub).
  - Gates T2/T3.
- **T2 [backend] — claude-usage router.** `GET /claude-usage` (+ optional `?window=5h|week|month` for the segment) · optional `PUT /claude-usage/override` (manual cap/reset/weekly). Envelope + codes (422 bad override body; 200 always for GET — fail-open). `MODULE` auto-discovered. Blocked by T1.
- **T3 [frontend] — S9 screen + Home swap.** `app/claude/page.tsx` (port SCREENS.claude: gauge/segment/3-stats/daily-bar/per-project-stub) + `lib/useClaudeUsage.ts` + `lib/api.ts` getClaudeUsage. **Swap Home page.tsx:139 ComingSoonStub → live quota tile** (pct ring + reset). Honest stub for the per-project panel + reset countdown (no fake countdown). Blocked by T2 serving + schema frozen.
- **T4 [tester] — verify.** pytest (reader parses real stats-cache shape; fail-open on missing/malformed file; today/avg/peak/series/byModel math; derived pct carries {used,cap}; stale flag). API curl (`GET /claude-usage` envelope + window param + override 422). Chrome via `docker compose up`: S9 renders, value-by-value gauge/stats/bars vs `GET /claude-usage` raw, Home quota tile live (was stub), per-project shows marked stub (not fake), console 0, **0 unhandled**. Pre-scaffold from T1.

## Logic/Algorithm (architect-decided — decide-and-log)
- **today:** tokensByModel summed for the latest `dailyModelTokens` entry (= lastComputedDate's day). If stale, that's the most recent real day, labeled via asOf.
- **series (7d):** last 7 `dailyModelTokens` entries → `[{date, label=weekday(date), tokens=sum(tokensByModel.values())}]`. Missing days → tokens=0 (mock shows 0-height bars for T7/CN).
- **avgPerDay:** mean of the 7d series tokens (round int).
- **peak:** max-tokens DayBurn in the series.
- **byModel:** from `modelUsage` → per model {input,output,cacheRead,cacheCreate, total=in+out, costUSD}. Sort by total desc.
- **cost (derived, NOT stats-cache's costUSD which is often 0):** per model `costUSD = (inputTokens*rate.input + outputTokens*rate.output)/1e6`, summed for the top-level `costUSD`. Rate table (USD per 1M tokens, from ClaudeManager `lib/pricing.ts` — copy into a small `pricing.py` const, single-user simplest):
  ```
  opus-4-7/4-6: in 15, out 75 · sonnet-4-6/4-5: in 3, out 15 · haiku-4-5(-20251001): in 1, out 5 · haiku-3-5: in 0.8, out 4
  unknown model → FALLBACK sonnet (in 3, out 15)
  ```
  **Cache cost INCLUDED** (refined at T1 dispatch, backend's good catch): `cost = (inTok*inRate + outTok*outRate + cacheReadTok*0.1*inRate + cacheCreateTok*1.25*inRate)/1e6` — cache-read ≈ 0.1× input rate, cache-write ≈ 1.25× input rate. Tag provenance "derived:pricing-table".
  **Rate-conflict ruling:** backend's claude-api-skill quoted opus 5/25; ClaudeManager's lib/pricing.ts (user-directed ref, re-verified on disk) = opus-4-7/4-6 **15/75** (matches real Anthropic Opus-4.x). ClaudeManager wins → 15/75.
- **pct:** `round(used/cap*100, 1)`, cap default 200_000 (configurable). carries {used,cap}. used default = today.
- **window param (5h/week/month):** 5h≈today (no sub-day data → today's total, labeled "cửa sổ 5 giờ"); week=last 7d sum; month=last 30d sum. (5h is approximated by today — log it; sub-day granularity isn't in stats-cache.)
- **resetIn / weekly:** None unless manual override set — NOT fabricated (no disk source). Screen shows "—" / "nhập tay" honestly.
- **stale:** `asOf < (today - 1 day)` → true (allow a 1-day lag as fresh; a cache computed yesterday isn't stale). UI shows "dữ liệu tính đến <asOf>". **FE MUST render staleness PROMINENTLY** (team-lead honest-mirror point): not a footnote — a badge near the title/gauge ("dữ liệu tính đến 17/4 · chưa cập nhật") + the chart's x-axis/last-bar labeled with asOf, NOT implied-live. "Today's usage" = the cache's last-computed day's tokens, labeled with asOf — never "hôm nay" implying live. The real cache was ~7wk stale at kickoff (lastComputedDate 2026-04-17) — the screen must NOT look live when data is weeks old. stats-cache only refreshes when Claude Code recomputes it (outside our control — we display honestly, never fake freshness).

## Defensive (MANDATORY)
- `stats-cache.json` missing → fail-open: `used=0, source="manual", warning="stats-cache.json not found — manual mode"`, 200 (never 500). Same fail-open as projects status.md / finance.
- Malformed JSON / missing keys → skip the bad part, warn, serve what parses (don't crash the whole response).
- `dailyModelTokens` empty → series=[], today=0, peak=zero-day, no crash.
- cap=0 (bad override) → guard div-by-zero (pct=0 + warning), 422 on the override write.
- stale cache → serve + `stale:true` + asOf (honest, not hidden).
- resetIn/weekly None → FE renders "—"/stub, never a fabricated countdown.

## Dispatch standards
- Runtime: `docker compose up` (FE :3010 → BE :8001). Baseline: pytest 443, vitest 254 (post-S6).
- **`## Read first (memory)` line in EVERY dispatch** (new standing rule, first live sprint) — per-role files listed at top.
- **Full ClaudeUsage shape in T1 msg #1** (no stub-then-confirm) — freeze field-by-field-diff.
- Backend reader: env-overridable stats-cache path (test isolation — mirror TINHDEV_ROOT). FE: mock=SCREENS.claude, mirror frozen shape render-only. Tester: value-by-value vs raw on canonical, 0-unhandled, behavior-test the fail-open (rename stats-cache → manual mode).

## Dispatch ordering
1. T1 GATING (schema+reader+service) alone → freeze + announce serving.
2. T2 (router) after T1.
3. T3 (FE screen + Home swap) after schema frozen + T2 serving. T4 pre-scaffolds from T1.

## Out of scope (north-star)
- **Per-project/routine token attribution** — IS derivable (`.jsonl` cwd-group, per ClaudeManager's `sessions.projectPath`), but parsing every `~/.claude/projects/*/*.jsonl` is heavier than the stats-cache read path → **marked stub this sprint** (honest "sắp có", not dropped), real wire = follow-up if the user wants it. (Upgraded from "impossible" to "deferred" after the ClaudeManager read.)
- **Cache-token pricing** — costUSD this sprint prices input+output only (the ClaudeManager base table). Cache-read/write rates added later if exact billing is wanted.
- **Live 5h/weekly reset countdown** — window state not readable from disk (confirmed not in stats-cache, settings, or ClaudeManager); stub + manual-entry. (If Claude Code ever exposes it, wire then.)
- **Full `.jsonl` deep parse** — ClaudeManager's per-message/per-session tracing is richer but heavier; S9 reads stats-cache (aggregated, cheap) for the screen + uses ONLY the pricing table from ClaudeManager. Deep per-session parse = a later sprint if needed.
- **SQLite `claude_usage_history` snapshot routine** — optional daily mirror for trend continuity; add only if stats-cache rotates and trends break. Read path uses stats-cache directly.

## Real-cache bugs (team-lead Rule#0 on the CONTAINER + real ~/.claude — fixture/empty-container hid them)
- **BUG1 (3B-class mount gap):** docker container couldn't read `~/.claude/stats-cache.json` → fail-open to empty manual mode on the canonical stack (bare-metal curl looked fine). **Fix (architect, docker-compose):** mount `${CLAUDE_HOST_DIR:-${HOME}/.claude}:/claude-home:ro` + `LIFEOS_CLAUDE_STATS_PATH=/claude-home/stats-cache.json`. → memory `host-file-source-must-mount`.
- **BUG2 (non-Claude mispricing):** real cache has MiniMax/glm/arcee models (MiniMax-M2.7 = 4.66B tok); sonnet-fallback priced them → $55,514 garbage headline. **Fix (backend, decide-and-log):** filter byModel/used/today/series/avg/peak/cost/model to `claude-*` ONLY. Sonnet-fallback now only catches unknown CLAUDE models. → $39,146 legitimate.
- **Infra note:** canonical stack must be `docker compose up -d` (DETACHED) — foreground exits when the shell ends (container-down/HTTP-000).

## COST DISPLAY ruling (decide-and-log — architect, T3)
costUSD ($39,146) is LEGITIMATE (team-lead hand-verified: 19.36B cache-read tokens over 3,913 sessions, correctly priced ~95% cache-read). To avoid a scary context-free number: **headline = total costUSD; sub-line/tooltip = cache-read $ breakout** (computed FE-side from byModel.cacheReadTokens × 0.1 × inRate — self-describing-raw, the data's in the API). Honest about composition. Logged to end_7 §Assumptions.

## NOTE — cost is now IN scope (changed at kickoff after ClaudeManager read)
costUSD moved from "stub/out-of-scope" → **LIVE derived** via the ClaudeManager pricing table (the stats-cache `costUSD:0` problem is solved by computing tokens×rate ourselves). This is the verify-or-stub-and-log pattern resolving toward REAL because a verified local reference (ClaudeManager) proved the rates. Logged to `## Assumptions` in end_7.
