# Plan Sprint 4 — Finance (S5 Overview + S6 Portfolio Detail) [ARCH §9 step 3]

> DRAFT (CLAUDE.md §3.3) — refresh via kickoff before dispatch. 3rd backend module (finance: portfolio, P&L, allocation-vs-golden-path, ladder) + S5/S6 screens. Uses Market data (Sprint 3) for current prices. FIRST sprint applying self-describing-raw.
> Spec: SPEC §S5 (Finance Overview) / §S6 (Portfolio Detail). ARCH §9 step 3. Mock: data.js (alloc Crypto38/ETF24/VN18/Dry20). Memory: api-agent-readable-backlog, single-dev-no-overengineering, dev-server-ports (dev stack = `docker compose up`).
> Author: architect · 2026-06-06 · Status: awaiting team-lead greenlight after 3B done.

## Objective
Build the `finance` module (router/schema/service) + S5 Overview + S6 Portfolio Detail. Full feature (SPEC §S5/S6), simple implementation. Holdings + golden-path are user data (md_store); current prices come from the market module; derived metrics (allocation-drift, P&L, ladder-state) computed server-side, **self-describing** (carry their inputs).

## Golden-path data (decide-and-log — file does NOT exist)
`project_investment_golden_path` không tồn tại trong repo (flagged từ ROADMAP). Per data-fallback §5: **decide-and-log a baseline + ship, don't block + Discord-ping user.**
- **Target allocation baseline (from data.js):** Crypto 38% · ETF 24% · VN 18% · Dry 20%. Stored in md_store `finance/golden_path.md` (YAML), user-editable.
- **Ladder baseline:** simple per-channel rung levels (e.g. Crypto entry rungs at -10%/-20%/-30% from a reference) — DECIDE simple defaults, log, user overrides. Don't invent a complex ladder engine (north-star).
- Discord-ping: "Sprint 4 baselined golden-path = Crypto38/ETF24/VN18/Dry20 + ladder defaults; override in finance/golden_path.md."

## Kickoff — 2026-06-06
### Verified vs current code
- **market service reuse:** `market.service.tracked_assets()` + `get_market()` exist, but NO single `get_quote(symbol)->price`. Finance needs current price per symbol → T1: add `market.service.get_quote(symbol) -> AssetQuote | None` (reuse the same reader/fail-open), Finance calls it. Don't re-fetch CoinGecko.
- **md_store** `write_file/read/exists` ready for holdings + golden_path.md.
- **T0 fix point confirmed:** `projects/service.py:130-132 _tracked_repos()` does `repos[pid] = meta.get("repo")` WITHOUT checking the path exists → that's exactly where the status.md host-path goes dead. Fix: if `repo` path doesn't exist AND pid is in config → use the config path.
### Decisions (decide-and-log)
- **Golden-path baseline DECIDED + Discord-pinged user:** Crypto 38 / ETF 24 / VN 18 / Dry 20 (data.js) + ladder rungs at -10/-20/-30% from a reference price. Stored md_store `finance/golden_path.md` (YAML), user-editable. Logged → §Assumptions.
- **allocation-drift alert threshold N = 5%.**
- **Ladder baseline:** 3 rungs per channel at -10/-20/-30% from a `reference` price in golden_path (simple, NOT an engine). User overrides.
- **Portfolio change-over-time:** reuse market `price_history` for current values; a daily portfolio snapshot is a later add (don't build a snapshot routine this sprint — north-star).
### S5+S6 in one sprint; split panels (not features) if T3/T4 get heavy.

## Task 0 (FIRST, before Finance) — status.md repo-path fallback [carried from 3B]
- **T0 [backend]** — `service`: when a project's `status.md` `repo:` path does NOT exist (stale / cross-environment, e.g. a bare-metal host path inside a container), FALL BACK to the config-resolved path (TINHDEV_ROOT) instead of treating it as a dead repo. Correct fail-open: a registered project shouldn't go dead just because its stored absolute path is stale. + a test (status.md with a nonexistent repo path + the same id in config → resolves to the config path, health correct). This closes the 3B layer-4 root cause permanently (option b, team-lead-ratified). Small: service resolve + 1 test. Do FIRST so Docker stays health-correct without manual data cleanup.

## Tasks (4-5, ≥2 parallel)
- **T1 [backend, GATING] — finance schema + service.**
  - schema: `Holding {channel, symbol, qty, avgCost, ...}`, `ChannelAlloc {channel, value, pct, target, drift, pnl{cost,current,abs,pct}}`, `LadderState {channel, rungsIn, nextRung, triggerPrice, distancePct}`, `FinanceOverview {totalValue, change, allocations, dryPowder, pnlTotal}`.
  - service: holdings from md_store `finance/holdings.md`; current prices from the MARKET module (`market.service` or via internal call — reuse, don't re-fetch); allocation-drift = actual% vs golden-path target%; P&L = (current - cost); ladder-state from golden_path rungs vs current price.
  - **Self-describing-raw (baked in):** every derived field carries inputs — `drift` carries {target, actual}; `pnl` carries {cost, current, abs, pct}; `ladderState` carries {triggerPrice, currentPrice, distancePct}; holdings carry `source`+`asOf`. Raw values (price, qty) NO extra tag. (Litmus: agent understands without reading code.)
  - Gates T2/T3.
- **T2 [backend] — finance router.**
  - `GET /finance` (S5 overview: total, allocations w/ drift, P&L, dry-powder), `GET /finance/{channel}` (S6 detail: holdings, ladder-state, P&L), holdings CRUD (add/edit position → md_store), golden-path get/set. Envelope + codes. Auto-discovered. Blocked by T1.
- **T3 [frontend] — S5 Finance Overview screen** (`app/finance/page.tsx`).
  - Total assets + change, allocation donut/bars (Crypto/ETF/VN/Dry + pct + drift-vs-target with alert), portfolio-value chart, P&L total + per-channel, dry-powder, click channel → S6. Render-only (drift/pnl from backend). Shared components. Blocked by T2.
- **T4 [frontend] — S6 Portfolio Detail screen** (`app/portfolio/page.tsx` or `[channel]`).
  - Current price+change, position (in/avgCost/P&L), **ladder state** (rungs-in / next-rung+trigger / distance), related signals (from market macro), price chart w/ buy marks + trigger levels, channel note, "vào được chưa" status, journal link. Blocked by T2.
- **T5 [tester] — verify.**
  - pytest: allocation-drift math (actual vs target), P&L math, ladder-state, golden-path baseline/override, self-describing fields present. behavior-test the drift/P&L. Chrome live (:3010→:8001 via `docker compose up`): S5/S6 render, drift alerts, numbers match API. Pre-scaffold from T1.

## Logic/Algorithm (architect decides — decide-and-log; finance is non-CRUD)
- **allocation-drift:** `drift = actualPct - targetPct` per channel; alert if |drift| > N% (DECIDE N, e.g. 5). Carries {target, actual} (self-describing).
- **P&L:** `abs = currentValue - costBasis`, `pct = abs/costBasis*100`. Carries {cost, current}. currentValue uses market price (crypto real, etf/vn mock — same source tag as market).
- **ladder-state:** per channel, golden_path defines rung trigger prices; `rungsIn` = count below current, `nextRung` = next trigger below, `distancePct = (current - nextTrigger)/current*100`. Simple — DECIDE baseline rungs, log.
- **dry-powder:** total cash not allocated (a holding with channel="Dry"); "lương dự kiến vào" = a manual field in golden_path.
- **total + change:** sum of holding values; change vs a prior snapshot (price_history or a daily portfolio snapshot — DECIDE: reuse market price_history or add a portfolio snapshot routine).

## Self-describing-raw convention (FIRST application — bake into every derived field)
Per memory `api-agent-readable-backlog`: derived/inferred/mock fields carry their inputs + source/asOf; raw fields don't. So an agent curling `/finance` understands drift/pnl/ladder WITHOUT reading the code. Dogfood: when tester curl-verifies, note "would an agent get this?".

## Defensive (MANDATORY)
- No holdings yet → empty overview, no divide-by-zero (P&L pct on cost=0 → null).
- Market price unavailable (feed down) → use last-known + warning (market already fail-open); finance shows the value with a stale tag.
- golden_path.md absent → baseline defaults + warning (don't crash).
- Channel with 0 cost basis → pct null.

## Dispatch standards
- Runtime: dev stack = `docker compose up` (BE :8001 container, FE :3010 container) — memory dev-server-ports. Baseline pytest 313, vitest 187.
- Ownership: failing test → report, don't edit; re-read cross-file at current mtime; tester runs full suite on staged tree before commit (Sprint-3 lessons).
- FE: mock file data.js (alloc shape) + self-describing schema + "render-only, backend computes drift/pnl/ladder."

## Dispatch ordering
1. T1 GATING (schema + service) alone — locks the finance shape + self-describing pattern.
2. T2 router after T1.
3. T3 + T4 (FE screens) after T2. T5 pre-scaffolds from T1.

## Open items at kickoff
- Ladder rung baseline (decide simple defaults — e.g. -10/-20/-30% rungs).
- Portfolio change-over-time source (reuse price_history vs add a snapshot routine).
- S5+S6 one sprint or split? (per north-star: if heavy, split PANELS not features — ship S5 + S6-core, add chart/signals follow-up. Decide at kickoff.)
- allocation-drift alert threshold N.

## Out of scope (north-star)
- No complex ladder engine / backtest / strategy framework — simple rung levels in config/md.
- No real-time price streaming — the market 5min poll + on-demand is enough.
- Journal (S7) is a separate sprint — finance only LINKS to it.
