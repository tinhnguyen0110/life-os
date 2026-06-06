# Plan Sprint 12A — Portfolio LIST (S6 list) [reactive · the missed navigable stub · FE-only]

> Author: architect · 2026-06-06 · Status: kickoff DONE · awaiting team-lead scope-confirm + greenlight. Reactive sprint (§3.4b) — same theme as the finance/portfolio screens.
> Trigger: team-lead's closer milestone-audit (grep EmptyScreen across ALL page.tsx) found `/portfolio` is a navigable STUB (nav.ts:44 "Danh mục" → EmptyScreen). The "all 14 done" was premature — 1 navigable coming-soon remains.
> Spec: SPEC §S6 (the mock has TWO S6 surfaces: the LIST `SCREENS.portfolio` "Danh mục · N vị thế · M kênh" + the DETAIL `/portfolio/[id]` which IS built). Mock: `screens-finance.js` `SCREENS.portfolio`. Memory: `mock-diff-catches-dropped-feature`, `unhandled-errors-not-green`, `dev-server-ports`, `single-dev-no-overengineering`.

## The gap (Rule#0-confirmed on disk)
- `frontend/app/portfolio/page.tsx` = EmptyScreen stub (6 lines). nav.ts:44 links "Danh mục" → /portfolio. → user clicks Danh mục, lands on coming-soon.
- AUDIT: grep EmptyScreen across ALL page.tsx → **portfolio is the ONLY navigable stub** (one gap from done).
- Two S6 surfaces in the mock: the LIST (`/portfolio`, nav target — STUB) + the DETAIL (`/portfolio/[id]`, real, reached by clicking a channel on Finance). We shipped the detail, never the list.

## THE DATA ALREADY EXISTS — FE-only (Rule#0-confirmed, no new backend)
`GET /finance` returns: `holdings: [Holding{symbol, qty, avgCost, pnl, source, asOf}]` + `allocations: [ChannelAlloc{channel, value, pct, target, drift, pnl}]` + `totalValue` + `dryPowder` + `series`. The Portfolio LIST is **FE-assembly of this existing data** (the allocation donut + the holdings table) — like the S12 settings hub. NO new backend endpoint. (The detail `/portfolio/[id]` uses `/finance/{channel}`; the list uses the top-level `/finance`.)

## Honest-mirror — SCREENS.portfolio panels (the list)
| Mock panel | Data | S12A |
|---|---|---|
| Title "Danh mục · N vị thế · M kênh" + channel tabs (Tất cả/Crypto/ETF/VN) + "Thêm vị thế" | finance holdings/allocations | **LIVE** |
| Allocation donut (per-channel pct) + total in center | allocations[].pct + totalValue | **LIVE** |
| Holdings table (symbol/name/qty/avg-cost/current/pnl%) | holdings[] (priced) | **LIVE** |
| Each holding row → click | → /portfolio/[id] (the channel detail) | **LIVE** (row → the holding's channel detail) |
| "Thêm vị thế" | POST /finance/holdings (EXISTS) | **LIVE** (or link to where add lives — decide; the endpoint exists) |

## Tasks (S12A — 2, FE-only reactive)
- **T1 [frontend] — Portfolio LIST screen** (`app/portfolio/page.tsx`, replace EmptyScreen). Mirror `SCREENS.portfolio`: header (N vị thế · M kênh from holdings/allocations counts) + channel filter tabs + allocation donut (reuse the finance allocation data) + holdings table (symbol/name/qty/cost/current/pnl% — from `/finance` holdings) + row→/portfolio/[id] (the channel detail) + "Thêm vị thế" (POST /finance/holdings exists, or link). Reuse `getFinance()` (already in api.ts). Per-tile fail-open. Blocked by nothing (data exists).
- **T2 [tester] — verify portfolio list.** vitest (renders, holdings table value-by-value vs /finance, channel filter, row-nav, donut, empty-state no-holdings). Chrome `docker compose up -d`: /portfolio renders the holdings + donut value-by-value vs GET /finance, channel tabs filter, click a row → /portfolio/[id], NO EmptyScreen, console 0. **+ re-run the milestone audit: grep EmptyScreen across ALL page.tsx → ZERO navigable stubs.**

## Logic/Algorithm
- **N vị thế** = holdings.length · **M kênh** = allocations.length (or distinct channels in holdings).
- **donut** = allocations[].pct (the channel allocation — already computed by finance).
- **holdings table:** symbol, name (from holding or a symbol→name map), qty, avgCost, current (priced — from holding's pnl/current), pnl% (holding.pnl.pct). null-safe → "—".
- **channel filter tabs:** filter holdings by their channel (crypto/etf/vn). "Tất cả" = all.
- **row → /portfolio/[id]:** the [id] = the holding's CHANNEL (the detail is per-channel). So a BTC row → /portfolio/crypto (the crypto channel detail). (Confirm the detail's id scheme — it's `/finance/{channel}`, so id = channel.)

## Defensive (MANDATORY)
- /finance down / null → error tile + retry. No holdings → empty-state ("Chưa có vị thế nào"), not crash.
- null holding fields (price unavailable) → "—". Empty allocations → donut empty-state.
- row-nav to a channel with no detail → handle gracefully.

## Dispatch standards
- Runtime: `docker compose up -d` (DETACHED, no --build for FE). Baseline: vitest 368 (post-S12).
- **`## Read first` per role:** FE → `mock-diff-catches-dropped-feature`, `unhandled-errors-not-green`, `dev-server-ports`; tester → `verify-live-app-not-just-suite` (the audit that caught this), `behavior-test-not-field-read`.
- Reactive sprint (§3.4b): same gates, FE-only, ~1-2 tasks.

## Out of scope (north-star)
- NO new backend — /finance already serves holdings + allocations. (If "Thêm vị thế" needs a richer add-form than POST /finance/holdings, link to where it lives — don't rebuild.)
- The DETAIL (/portfolio/[id]) is already built — this is ONLY the list.

## The milestone re-audit (the close-it-honestly step)
After S12A: re-run `grep -rln EmptyScreen frontend/app/**/page.tsx` → must be ZERO. THEN declare "all 14 (sơ bộ xong)" honestly. The lesson: the closer needs a MILESTONE AUDIT (grep all stubs across the whole app), not just the last sprint's verify — a pre-existing stub hides from sprint-scoped checks. → memory candidate: `closer-milestone-audit`.
