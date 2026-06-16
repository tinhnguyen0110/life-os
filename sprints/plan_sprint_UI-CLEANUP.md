# Sprint UI-CLEANUP — real /exchange + live sidebar badges (Task #65)

Close the last UI stubs: GAP1 /exchange (claimed EmptyScreen) + GAP2 sidebar badges (claimed hardcoded). FE sprint, frontend-2.

## Kickoff — 2026-06-16 (§3.3a — MAJOR DRIFT: both gaps are ALREADY mostly closed)

**The kickoff caught >90% drift — the two flagged gaps are stale claims. Verified live, NOT trusting the memory's "stub"/"hardcoded" labels (the milestone-audit / honest-mirror lesson).**

### GAP 1 — /exchange is ALREADY a real screen (the "EmptyScreen" claim is STALE)
- `app/exchange/page.tsx` (shipped `471678a`) is FULL: tab registry (OKX live / Binance), KPI row (totalUsdValue), balances table (symbol/available/frozen/total/usdValue), positions table (instId/side/qty/avgOpenPrice/unrealizedPnl/margin/lever), sync button, loading/error/unconfigured/data states. tsc clean. Types `OkxBalance/OkxPosition/ExchangeOverview` exist in lib/types.ts; `getExchange/syncExchange` wired.
- The ONLY "stub" is the **Binance "coming soon" tab** — an HONEST placeholder for an unconfigured 2nd exchange (no Binance key). NOT a gap to fix (it's correct: don't fake a sàn we can't read).
- **THE ONE REAL /exchange GAP:** the live `GET /exchange` payload now carries per-coin `accAvgPx` / `spotUpl` / `spotUplRatio` (the finance-arc enrichment), but the FE `OkxBalance` type + the balances table do NOT render them. So /exchange shows balances but NOT the per-coin cost-basis P&L the backend already provides. Surfacing them = the only genuine /exchange work (small, in the finance-arc spirit; null-safe for USDT).

### GAP 2 — sidebar badges are ALREADY wired live (the "hardcoded" claim is STALE)
- `components/Sidebar.tsx` (lines 38-90) ALREADY fetches all 4 sources in parallel (fail-soft `Promise.allSettled`: `getRoutines/getProjects/getMarket/getClaudeUsage`) and renders them LIVE via `badgeText(route, fallback)`:
  - routines → `data.activeCount` (live **8**)
  - projects → `data.summary.total` (live **5**)
  - market → `data.triggers.length` (live **0** → `showBadge` HIDES it — "a red 0 is noise")
  - claude → **`pct5h ?? pct`** (live **7%**) — the comment explicitly says "MATCH the S9 screen + Home tile... NOT raw pct which overflows 100%". So the badge renders **7%, NOT 71%** (the cap-overflow ghost). The distinguishing-case is satisfied — the wired badge ≠ the hardcoded one.
- The `nav.ts` static values (`projects "4"` / `market "2"` / `claude "71%"` / `routines "5"`) are ONLY the FALLBACK (used when a live fetch returns null) — they do NOT render in the normal path.
- **THE ONE REAL badge GAP (cosmetic):** the `nav.ts` fallbacks are STALE/misleading (esp. claude "71%" — if a live fetch ever fails, the sidebar shows 71%, the ghost). Honest fix: update the stale fallbacks to neutral/current values (or drop the badge.text so a failed fetch shows nothing rather than a wrong number). LOW priority — only shows on a fetch failure.

### Live badge sources (curled — verify-fields-exist + the distinguishing-case)
| badge | nav.ts static | LIVE value | source | wired? |
|---|---|---|---|---|
| /projects | "4" | **5** | `projects.summary.total` | ✅ live |
| /market | "2" | **0** (hidden) | `market.triggers.length` | ✅ live |
| /claude-usage | "71%" | **7%** | `claude_usage.pct5h ?? pct` | ✅ live (NOT 71%) |
| /routines | "5" | **8** | `routines.activeCount` | ✅ live |

## REVISED SCOPE (the real residual — tiny, NOT a full sprint)
Both "gaps" are ~90% done. The genuine residual is small:
- **R1 — /exchange per-coin P&L:** widen FE `OkxBalance` type with `accAvgPx?/spotUpl?/spotUplRatio?` (null-safe) + render a per-coin "P&L (cost-basis)" column on the balances table (USDT/null → "—", like the portfolio per-coin work). The backend already provides it.
- **R2 — nav.ts stale fallbacks (cosmetic):** update the `nav.ts` badge fallbacks (esp. claude "71%" → drop or neutral) so a failed live-fetch doesn't surface the cap-overflow ghost. Optional.
- **This is Quick-Fix / Reactive-sprint tier (R1 ~30 lines, R2 ~4 lines), NOT a 3-6 task sprint.** Recommend to team-lead: ship R1 as a small FE task (worth doing — real per-coin P&L on /exchange), R2 as a 1-line cleanup batched with it. Do NOT rebuild the already-working screen + badges.

## Decision (team-lead, 2026-06-16) + Dispatch
team-lead chose **(a) R1+R2** as a small Reactive sprint (Quick-Fix/Reactive tier). team-lead independently Rule#0-verified the kickoff finding (both gaps already done). Dispatched to frontend-2 as ONE small task:
- R1: widen FE `OkxBalance` (+accAvgPx/spotUpl/spotUplRatio) + a per-coin cost-basis P&L column on /exchange balances (null-safe "—" for USDT, mirror portfolio `pnlText`, render-only).
- R2: neutralize the stale nav.ts badge fallbacks (claude "71%" ghost → "—") so a failed live-fetch never surfaces a stale number.
Locks: R1 verify-fields-exist (curled) + null-safe + spotUpl cross-check (PEPE ≈ -57.8%); R2 distinguishing-case (forced fetch-fail shows no "71%"). Commit `fix(sprint-UI-CLEANUP)`. team-lead retiring the stale `sidebar-badges-static-placeholder` memory.

## Note (honest-mirror)
The memory `sidebar-badges-static-placeholder` is STALE — the badges were wired live in a prior sprint (the F2-M4 comment in Sidebar.tsx). Flag to update/retire that memory. This is exactly why kickoff verifies the live surface before dispatch (milestone-audit-grep-all-stubs / honest-mirror).
