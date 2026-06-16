# End Sprint UI-CLEANUP — /exchange per-coin cost-basis P&L + honest badge fallbacks (Task #65)

> Status: **REVIEWED — 3 gates green, committing.** Task #65, small Reactive sprint (R1+R2). The kickoff caught that both originally-flagged gaps (/exchange "stub", "hardcoded" badges) were ALREADY done (stale memory); this ships the genuine residual. The LAST UI residual — backlog now genuinely empty.

## What shipped
- **R1 — /exchange per-coin cost-basis P&L column.** The live `GET /exchange .balances[]` carries per-coin `accAvgPx`/`spotUpl`/`spotUplRatio` (the finance-arc OKX enrichment) the FE wasn't rendering. Widened FE `OkxBalance` (lib/types.ts) with `accAvgPx?/spotUpl?/spotUplRatio?` (all `number | null`, mirror backend). Added a "P&L (giá vốn)" column to the balances table via `costPnl(spotUpl, spotUplRatio)`: renders `spotUpl` (abs USD, `fmtSign`) + `spotUplRatio × 100` (%) with pnl tone — **null-safe: a no-basis coin (USDT/ETH → null) → "—", NEVER 0/fabricated** (the honest-null discipline, mirror of portfolio `pnlText`). Render-only — `spotUpl` is the BACKEND's number; FE formats/colors, NEVER recomputes. /exchange is now the per-coin COST-BASIS view (complements /portfolio's per-coin pnl).
- **R2 — honest badge fallbacks.** `lib/nav.ts` badge `.text` values were stale FALLBACKS (the Sidebar renders LIVE via `badgeText`; these show ONLY on a live-fetch failure). Neutralized all 4 (`projects "4"` / `market "2"` / `claude "71%"` / `routines "5"` → `"—"`) so a failed fetch shows an HONEST "no-data" dash, never a stale number — esp the `claude "71%"` cap-overflow ghost. The `badgeText` fallback contract + the badge `cls` styling are intact; only the text is now honest.

### Verified counts (architect re-ran independently — Rule #0)
- **vitest: 816 passed (816), 75 files, 0 errors / 0 unhandled rejections** (was 812; +4 exchange tests; the 2 Sidebar tests updated in place). `npx tsc --noEmit`: **clean** (exit 0).
- **team-lead LIVE Chrome-verified (Rule #0, opened /exchange):** the "P&L (GIÁ VỐN)" column renders live — PEPE −$116 −57.9% (== backend spotUpl), ICP −19.9%, ARB −75.9%, S −80.8%, TRUMP −96.5%, IP −93.3% (real losses); USDT/ETH/LINK = "—" (basis-less honest-null). Sidebar Claude badge = 9% LIVE (not the 71% ghost); nav.ts fallbacks "—".

## Code review (architect — 4-step, the null-safe + render-only-not-recompute + distinguishing-case hardest)
1. **git status/diff** — files STABLE (newest mtime 14:12, reviewed 14:18 — >6min, not in-flight). Scope: types.ts + exchange/page.tsx + nav.ts + exchange.test.tsx (new) + Sidebar.test.tsx + plan/end_sprint. `template/*` + `data/` EXCLUDED.
2. **Read full functions** — `OkxBalance` widening (3 nullable fields + honest-null doc); `costPnl` (null→"—"/hasData:false, sign-tone, `spotUplRatio×100`); the column render (`costPnl(b.spotUpl, b.spotUplRatio)` + tooltip); nav.ts 4 fallbacks → "—".
3. **Verify against plan + the locks** — verify-fields-exist (curled), null-safe, spotUpl cross-check, R2 distinguishing-case. All present + tested.
4. **Hunt additional issues — verified in code:**
   - **R1 null-safe** — `costPnl`: `spotUpl == null || !isFinite → "—", faint, hasData:false`. Test (b): USDT → "—" AND `not.toHaveTextContent("$0")` / `not("0.0%")` (never 0/fabricated). ✅
   - **R1 render-only (NOT recompute) — the distinguishing-case** — test (d) uses a DIVERGENT fixture (`spotUpl -50, spotUplRatio -0.5, usdValue 50` — independent) → asserts "−50.0%" = `spotUplRatio×100`, NOT a recomputed `spotUpl/usdValue` (= -100%, would differ). Proves the FE renders the backend number, doesn't recompute. ✅
   - **R1 spotUplRatio×100 (not raw)** — `fmtPct(spotUplRatio * 100)`; PEPE -0.5786 → -57.9%. ✅
   - **R2 distinguishing-case NOT weakened — STRENGTHENED** — the Sidebar tests flipped from `toHaveTextContent("71%")` (asserting the ghost) to `toHaveTextContent("—")` AND `not.toHaveTextContent("71%")`/`not("4")` on a forced fetch-reject. The teeth now assert the honest fallback, never the stale number. ✅
   - **R2 fail-path coverage (FE's honest note, accepted)** — a live in-browser fetch-fail sim isn't practical (Sidebar fetches mount-only; reload resets the patched fetch) → the forced-fail path is the UNIT test (reject getProjects+getClaudeUsage → assert "—", not 71%/4). team-lead accepted: the unit test is the definitive teeth; live Chrome confirmed the honest live path has no ghost. ✅

## Assumptions (user-review)
- **/exchange per-coin P&L = the backend `spotUpl`/`spotUplRatio` rendered (render-only).** A no-basis coin → "—". **Why:** surface the OKX accAvgPx cost-basis P&L the backend already computes; honest-null for stablecoins. **How to change:** `costPnl` (exchange/page.tsx) — but it's render-only, the derivation is the backend's.
- **nav.ts badge fallbacks = "—" (honest no-data), not a hardcoded number.** **Why:** the Sidebar renders badges live; the fallback only shows on a fetch-fail and must not surface a stale/wrong number (the claude "71%" cap-overflow ghost). **How to change:** the `badge.text` per route in nav.ts (but keep it honest — "—" or a real default).

## The 3 Quality Gates
- **Gate 1 — API:** ☑ no endpoint changes (FE-only; /exchange + the badge sources pre-existed) · ☑ no auth · ☑ render-only (no recompute). **PASS**
- **Gate 2 — Function:** ☑ R1 null-safe ("—" not 0) · ☑ R1 render-only via the divergent-fixture cross-check · ☑ R1 spotUplRatio×100 · ☑ R2 distinguishing-case (forced fail → "—", not 71%/4, strengthened) · ☑ existing tests pass · ☑ **vitest 816, 0 errors** · ☑ tsc clean · ☑ **Chrome self-verify (team-lead live-verified /exchange column + the 9% live badge; R2 fail-path unit-tested)**. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts + the live state · ☑ architect spot-checked full functions (the 4 review points in code) · ☑ counts ≥ baseline (+4) · ☑ team-lead LIVE Chrome-verified · ☑ assumptions logged (2) · ☑ commit format `fix(sprint-UI-CLEANUP)`. **PASS**

## Risks / follow-ups
- **The LAST UI residual is closed.** /exchange now shows per-coin cost-basis P&L; the badge fallbacks are honest. Both originally-flagged "gaps" were already done (the kickoff caught it — the stale `sidebar-badges-static-placeholder` memory is being retired).
- **Backlog is genuinely EMPTY:** per-coin-manual-basis deferred (0 off-OKX consumers — verify-source-before-build); both memory-flagged gaps were stale-already-done; this residual now shipped. Awaiting the user's next direction.
- Process: the kickoff's live-render verify (vs trusting a memory's "stub"/"hardcoded" label) scoped a "full sprint" down to a ~34-line Reactive task — the don't-dispatch-a-stale-plan / honest-mirror discipline saved a rebuild.
