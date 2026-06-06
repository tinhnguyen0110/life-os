# End Sprint 12A — Portfolio LIST (S6 list) [closes the nav stub · all 14 live · sơ bộ xong — HONESTLY]

> Result doc (CLAUDE.md §3.2). Reactive sprint (§3.4b). The closer's milestone audit found `/portfolio` (the S6 LIST, a sidebar nav target) was still an EmptyScreen stub while `/portfolio/[id]` (detail) was real. This builds the missing list. **After this, the whole-app stub audit = 0 navigable stubs → "all 14 screens live (sơ bộ xong)" is HONESTLY true.**
> Author: architect · 2026-06-06 · Commit: `feat(sprint-12A)` on `main`.

---

## 1. What shipped

### Frontend — Portfolio LIST screen (`app/portfolio/page.tsx`, replaced EmptyScreen) — FE-only
- The missing S6 LIST: header ("N vị thế · M kênh" from holdings/allocations) + channel filter tabs + allocation donut + holdings table + "Thêm vị thế" + each row → /portfolio/[channel] (the existing detail).
- **Data from `GET /finance`** (the `""` route = `getFinance()`, NOT `/finance/overview` which returns empty — a stale path flagged for cleanup) — `holdings[]` (channel/symbol/qty/avgCost) + `allocations[]` (channel/value/pct/pnl) + totalValue. FE-only assembly (NO new backend — the data existed).
- **`usePortfolio` hook** + `createHolding` (POST /finance/holdings) — **fail-closed: refetch the overview after POST, NO optimistic splice** (the recomputed allocations/pnl come from the refetch).
- **Honest channel-pnl labeling (the no-fabrication call):** holdings[] carry no per-row price → current/pnl are CHANNEL-level; FE labels it "P&L theo kênh (chi tiết trong từng kênh)" / "P&L KÊNH" col, did NOT fabricate per-holding pnl. Donut hardened (no NaN on value=0 channels — dry/vn excluded honestly).
- "Thêm vị thế" uses the shared Field form (from S12) — per-field 422, write-form round-trip teeth.

---

## 2. Verification (Rule #0) — THE MILESTONE GATE

### The whole-app stub re-audit (the gate to declaring "all 14")
`grep -rln EmptyScreen frontend/app/**/page.tsx` → **ZERO navigable stubs** (architect + team-lead both ran it independently). Every screen has live content; every nav route resolves to a real page. /portfolio was the LAST stub (219 lines now, was 6). **"all 14 live" is TRUE on disk.**

### Architect 4-step (full functions + the re-audit)
| Check | Result |
|---|---|
| vitest | **383 passed** (≥368 baseline; +15 portfolio/donut) |
| tsc | clean |
| portfolio page (read) | real, no EmptyScreen; getFinance() (correct endpoint); donut + holdings table + channel filter ✓ |
| honest channel-pnl label (page.tsx:8-10) | CHANNEL-level pnl, honestly labeled — NO fabricated per-holding pnl ✓ |
| createHolding fail-closed (usePortfolio:72-75) | refetch after POST, no optimistic ✓ |
| **MILESTONE re-audit (independent grep)** | **stub count = 0** ✓✓ |

### team-lead closer value-diff (live Chrome /portfolio vs /finance)
✅ Header "2 vị thế · 2 kênh"; donut $63,143 (Crypto 96%/$60,673 + ETF 4%/$2,470 = matches /finance); holdings BTC 1@$40k +$20,673/+51.7%, FUEVFVND 100@$25 −$10/−0.4%; honest channel-pnl label (no fabrication); donut console-clean (no NaN); row→/portfolio/[channel] nav + add-holding round-trip (fail-closed). PASS. + team-lead's own whole-app 0-stub re-audit.

### Tester T2 (PENDING — independent verify + re-audit, their lane)
list value-by-value + the milestone re-audit (independent grep→0) + row-nav + add-holding write-form teeth.

---

## 3. The 3 Quality Gates

### Gate 1 — API
N/A — FE-only (reuses `GET /finance` + `POST /finance/holdings`, both existing + frozen).

### Gate 2 — Function
☑ unit tests (portfolio renders, holdings value-by-value, channel filter, donut, empty-state, add-holding fail-closed) · ☑ vitest 383/0 · ☑ edge cases (no holdings, null fields, value=0 channels in donut) · ☑ honest channel-pnl (no fabrication) · ☑ tsc clean · ☑ FE Chrome self-verify (NO EmptyScreen) · ☑ write-form teeth (Thêm vị thế).

### Gate 3 — Sprint
☑ end_sprint_12A written · ☑ architect 4-step + the independent milestone re-audit (0 stubs) · ☐ **tester T2 — PENDING** · ☑ counts ≥ baseline (vitest 368→383) · ☑ **THE GATE: whole-app 0-stub re-audit PASSES** · ☑ format `feat(sprint-12A)`.

**VERDICT: FE GREEN + the milestone gate (0 navigable stubs) PASSES. Gate 3 holds on tester T2 → commit → all 14 live HONESTLY.**

---

## 4. Assumptions (user-review — decide-and-log)

- **Portfolio LIST = FE-only assembly of `GET /finance`** (holdings + allocations) — NO new backend (the data existed). To change: add a dedicated /portfolio-list endpoint if richer per-position pricing is wanted.
- **Per-holding pnl is CHANNEL-level, honestly labeled** — holdings[] carry qty/avgCost but no per-row current price; the pnl shown is the channel's (allocations[].pnl). FE labeled it so, did NOT fabricate per-row pnl. To change: add per-holding live pricing to the finance holdings reader.
- **`/finance/overview` returns empty** (a stale/wrong path) — S12A uses `GET /finance` (the `""` route). Flag: clean up or remove /finance/overview later.
- **Row → /portfolio/[channel]** — the detail is per-channel (/finance/{channel}); a holding row navigates to its channel's detail.
- **Add-holding fail-closed** — POST /finance/holdings → refetch the overview (recomputed allocations/pnl), no optimistic splice.

---

## 5. ALL 14 SCREENS LIVE — sơ bộ xong (HONESTLY, after the 0-stub re-audit)

**14 screens, ZERO navigable stubs** (S1 Home · S2 Projects · S3 Detail · S4 Graveyard · S5 Finance · **S6 Portfolio LIST + Detail** · S7 Journal · S8 Market · S9 Claude Usage · S10 Notes · S11 Brief · S12 Settings · S13 Routines · S14 Activity). Every nav route resolves to a real page. 11 backend modules, scheduler + 6 routines + run-log, md+git + SQLite, open API, command bar, template brief. The app is active + transparent + configurable + complete.

**Phase 2 (DEFERRED — honestly, per ARCH §11):** MCP/AI-actor (FastMCP + Claude-Code-generated brief/routines) · sidebar badges (3 of 4 static) · per-project token attribution (S9) · live 5h/weekly reset (S9) · AI-generated brief (S11) · GCP 24/7 scheduler · net-worth daily-snapshot chart · errorChannel→Discord + timezone/displayName consumers (S12) · /finance/overview cleanup.

---

## 6. Retro (process learnings)

1. **The closer milestone audit caught a false "done" (the headline) → memory `milestone-audit-grep-all-stubs`:** the build declared "all 14" after S12, but `/portfolio` (S6 LIST, a nav target) was still an EmptyScreen stub — S6 was counted "done" off its DETAIL surface while the LIST was never built. Every sprint-scoped verify correctly missed a pre-existing stub in a months-old screen. The whole-app grep (EmptyScreen ∩ nav targets) is the only check that catches it. **The closer's definition-of-done = the milestone audit, not just the last sprint's gates.** Caught one commit before the false "done" went out.
2. **FE-only reactive close** — Rule#0 found the data already existed in /finance → no new backend, low-risk. The endpoint correction (/finance not the empty /finance/overview) caught at scope-time.
3. **Honest no-fabrication on the closer** — FE labeled the channel-level pnl honestly rather than faking per-holding pnl the data doesn't carry. The honest-mirror discipline to the last screen.

---

## 7. Commit
- `feat(sprint-12A): portfolio list (S6 list screen — closes the nav stub, all 14 live)` — portfolio page + usePortfolio + spark donut + api.createHolding + plan_12A + end_12A. One commit.
- Gated on tester T2 + the 0-stub re-audit (PASSES). Commit hygiene: settled tree + grep the new symbols + explicit-path (exclude backend/data + .claude). After: push → report hash → the FINAL Sprint Sync + "all 14 sơ bộ xong" Discord (honestly).
