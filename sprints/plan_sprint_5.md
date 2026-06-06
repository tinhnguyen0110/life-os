# Plan Sprint 5 — Home v1 (S1 Command Center) [aggregate the 3 live modules]

> DRAFT (CLAUDE.md §3.3) — refresh via kickoff before dispatch. The first screen the user sees, currently an EmptyScreen stub. Composes the 3 SHIPPED modules (Projects/Finance/Market) into the dashboard NOW + clearly-marked "coming soon" slots for the unbuilt ones. Aggregate-incrementally (NOT breaking ARCH §9 aggregate-last — Home grows as modules land).
> Spec: SPEC §S1 (Command Center). Mock: `template/Life Command/app/screens-overview.js` `SCREENS.home` (HAS a mock → PORT it, don't design-from-SPEC). ARCH §9.
> Author: architect · 2026-06-06 · Status: awaiting team-lead scope-confirm + greenlight.

## Objective
Replace the Home EmptyScreen with a real Command Center that aggregates the 3 live modules. Mostly an FE sprint (pure composition of live module APIs — no new backend module, no new business logic). Port the mock layout. North-star: full feature where data exists, honest "coming soon" where it doesn't, simplest impl.

## Tile mapping — LIVE now vs COMING-SOON stub (the scope decision)
| Mock tile (SCREENS.home) | Data source | Sprint 5 |
|---|---|---|
| Net worth card (total + day/week change + area chart + allocation bar) | Finance `GET /finance` (totalValue, change, allocations) | **LIVE** (chart = series[] is [] this build → flat/placeholder, honest) |
| P&L per channel (mrow list) | Finance `/finance` allocations[].pnl | **LIVE** |
| Claude quota ring (%) | S9 Claude Usage — NOT built | **COMING SOON stub** (ring placeholder + "sắp có") |
| Projects table (health/progress/users/activity/NEXT + footer counts) | Projects `GET /projects` (+ summary) | **LIVE** |
| Brief today (numbered priorities) | S11 Brief — NOT built | **COMING SOON stub** ("brief sắp có") |
| Floating alerts (dot + source + time) | Market `GET /market` triggers/alertHistory | **LIVE** (market alert triggers) |
| Ticker tape (bottom) | Market `/market` quotes | **LIVE** (already wired Sprint 3) |
| **Activity Feed (panel)** | S14 Activity — NOT built (/health = projects/market/finance only) | **COMING SOON stub** (mock has this panel → honest-mirror needs a marked stub, not silent omission) |

→ 4 live tiles (net worth, P&L, projects, alerts/ticker) + **3 honest stubs (Claude quota, Brief, Activity Feed)**. Each is a clearly-marked "sắp có" placeholder, NOT a fake number — honest-mirror. (team-lead diffed scope vs mock + caught Activity Feed being silently dropped — a panel in the approved design must be a marked stub, not omitted, or the user re-asks "where's the section I saw in the mock?". Swap→live when S9/S11/S14 land.)

## Tasks (3-4, mostly FE)
- **T1 [frontend, GATING] — Home composition hook + shared tile components.**
  - `lib/useHome.ts` — fetch `/finance` + `/projects` + `/market` in parallel (Promise.all), expose `{finance, projects, market, loading, error}`. Reuse existing `getProjects`/`getFinance`/`getMarket` (don't add a backend `/home` aggregate — FE composes, simpler/north-star). Loading/error/partial states (one module down → render the others + a warning, don't blank the whole Home).
  - Any new shared tile not already in `components/shared/` (most exist: KpiCard, DataTable, HealthChip, ProgressBar). Gates T2.
- **T2 [frontend] — S1 Home screen** (`app/page.tsx`, replace EmptyScreen).
  - Port `SCREENS.home` layout (net-worth card + allocbar, P&L mrow, quota-ring STUB, projects dtable, brief STUB, alerts) from the mock using `tokens.css` classes (glowcard/allocbar/mrow/quotacard/briefcard already in tokens.css? verify at kickoff). Wire live tiles to useHome; click-through: net-worth→/finance, project row→/projects/{id}, alert→/market. Render-only.
- **T3 [tester] — verify Home.**
  - vitest (Home renders, live tiles show real data, stubs show "coming soon" not fake numbers, partial-failure resilience). Chrome via `docker compose up` (:3010→:8001): Home renders all tiles, **value-by-value diff** net-worth/projects-summary/P&L vs `/finance` + `/projects` raw (the 3B lesson), ticker live, console clean, dark mode.
- (Optional T4 [backend] — ONLY if we decide a server-side `/home` aggregate is worth it. Default: NO — FE composition is simpler. Skip unless kickoff finds a reason.)

## Logic/Algorithm
N/A — pure composition + display. NO new derived metrics (Finance/Projects/Market already compute everything: drift, P&L, health, summary). Home DISPLAYS their outputs. The only client logic = Promise.all orchestration + partial-failure handling. (If a Home-specific rollup is ever needed — e.g. a cross-module "today's priorities" — that's the Brief module S11, not Home v1.)

## Defensive (MANDATORY)
- Any of the 3 module APIs down → render the tiles that loaded + a warning on the failed one (Home must NOT blank out if Finance is down but Projects is up). Per-tile fail-open.
- Empty data (no holdings / no projects) → empty-state tiles, not crash.
- `series=[]` (Finance, this build) → flat/placeholder chart, honest (not a fake line).
- Stubs (Claude quota, Brief) → "sắp có" placeholder, NEVER a fabricated number (honest-mirror).
- null fields → "—".

## Dispatch standards
- Runtime: dev stack = `docker compose up` (FE :3010 → BE :8001 container). Baseline pytest 344, vitest 213.
- FE: mock = `screens-overview.js` SCREENS.home (PORT it — S1 has a mock, match it, that's what the user wants); schemas = the 3 frozen module shapes (ProjectStatus, FinanceOverview, AssetQuote) — mirror, don't re-fetch logic; "render-only, modules computed everything."
- Ownership: failing test → report; full-suite-on-staged before commit; value-by-value vs source on canonical (3B lesson); useSafeRouter; tsc before report.

## Dispatch ordering
1. T1 GATING (useHome hook + any missing tile component) alone.
2. T2 (Home screen) after T1.
3. T3 (tester) pre-scaffolds from T1; Chrome after T2.

## Kickoff — 2026-06-06
### Vocab-lock (NEW kickoff step — diff tile labels vs SPEC §S1 + mock BEFORE dispatch)
Mock `SCREENS.home` labels match SPEC §S1 exactly: "Tổng tài sản", "P&L theo kênh", "Dự án đang chạy", "Cảnh báo", quota, brief. No vocab mismatch (unlike Sprint-4 cash/Dry). FE ports these labels verbatim from the mock. Reuse the frozen module field names (ProjectStatus/FinanceOverview/AssetQuote) — no new vocab introduced (Home is display-only).
### Architecture decision (decide-and-log — the FE-compose vs /brief fork team-lead raised)
**Home v1 = FE composes the 3 live endpoints directly. NO backend aggregate, NOT the /brief module.** Why:
- ARCH §9 step 8 = "Graveyard + Brief; **Home đầy đủ**" → Home is the FULL aggregate at the END. `GET /brief` (ARCH §7/§11) is a SEPARATE module (S11, template-based + a `morning-pull` 8h routine) — building it now to back Home conflates two things + is more work.
- The mock has a Brief *tile* on Home → Brief is one tile, and it's a STUB this sprint (S11 unbuilt).
- FE-composing 3 live endpoints (Promise.all) is the simplest thing serving the dashboard (north-star). No new backend module/logic.
- When S11 Brief lands its own sprint, Home swaps the Brief stub → the live /brief tile (additive). Clean split, no conflation.
→ Confirmed: Sprint 5 = FE-only, 0 backend tasks.

## Open items at kickoff
- Verify `tokens.css` has the Home-specific classes (glowcard/allocbar/quotacard/briefcard/mrow/chartbg) — if missing, T1/T2 ports them from screens.css.
- Confirm `getFinance`/`getMarket` client fns exist in `lib/api.ts` (Sprint 3/4 added them) — reuse.
- Decide stub styling for Claude-quota + Brief (a consistent "coming soon" tile pattern, reusable when S9/S11 land).

## Out of scope (north-star)
- No `/home` backend aggregate (FE composes 3 endpoints — simpler; add only if a real need appears).
- No Brief generation logic (S11), no Claude usage fetch (S9) — honest stubs only.
- Home grows incrementally: when S9/S11/S10/S14 land, swap their stub → live tile (additive, no Home rewrite).
