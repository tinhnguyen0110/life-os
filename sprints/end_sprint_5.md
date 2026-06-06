# End Sprint 5 — Home v1 (S1 Command Center)

> Result doc (CLAUDE.md §3.2). The first screen the user sees — was an EmptyScreen, now aggregates the 3 shipped modules (Projects/Finance/Market) into the dashboard + honest "coming soon" stubs for the unbuilt ones. Aggregate-incrementally (grows as modules land). FE-only.
> Author: architect · 2026-06-06 · Commit: `feat(sprint-5)` on `main`.

---

## 1. What shipped

### Frontend — Home / Command Center (`app/page.tsx`, replaced EmptyScreen)
- **`lib/useHome.ts`** — composes the 3 live modules: `Promise.allSettled([getFinance(), getProjects(), getMarket()])` (NOT Promise.all — one rejection can't sink the others). A `resolve()` helper makes it **truly fail-open**: rejected → error tile; fulfilled-but-`value?.data` missing (unexpected 200 body / proxy `{}`) → error tile "phản hồi không hợp lệ"; else ready. Per-tile status + a top-level warning naming which tiles failed (fail-open is VISIBLE, not silent).
- **`app/page.tsx`** — ported `SCREENS.home` from the mock (`screens-overview.js`). **4 live tiles:** net worth + allocation bar + P&L per channel (Finance `/finance`), projects table with health/progress/users/NEXT + footer counts (Projects `/projects`), alerts + ticker (Market `/market`). **3 honest "coming soon" stubs** ("Sắp có…", zero fake numbers): Claude quota ring (S9), Brief hôm nay (S11), Activity Feed (S14). Click-through to detail screens. Render-only (every number from the module APIs — Home derives nothing).

### No backend change
FE composes the 3 existing frozen endpoints. Decided AGAINST a `/home` or `/brief` aggregate (ARCH §9: Home = full-aggregate-last; `/brief` is a separate S11 module — building it now conflates two things). Brief is one stub tile on Home, swaps → live when S11 lands.

---

## 2. Verification (Rule #0 — architect + team-lead)

| Check | Result |
|---|---|
| vitest (staged tree) | **239 passed (28 files)** |
| **0 unhandled errors** (new gate — passed-count alone is NOT green) | confirmed (grep clean) |
| tsc | clean |
| fail-open guard teeth (team-lead reverted resolve() → 3 tests FAIL → restored → green) | RED-without-proven ✓ |
| Live canonical Chrome (:3010→:8001 docker compose) value-by-value | Tổng tài sản $63,348 (=/finance), P&L crypto +$20,878/etf −$10/total +$20,868/+49.1% (=allocations+pnlTotal), 6 projects "2 active·1 chậm·3 đứng" (=/projects summary), Cảnh báo BTC (=/market), ticker live — ALL verbatim |
| 3 honest stubs | "Sắp có…", zero fake numbers, layout matches mock |
| Per-tile fail-open | one endpoint down → that tile errors, others render, warning names it |

Verified value-by-value on the CANONICAL `docker compose up` stack (the 3B lesson — diff each number vs raw API, not "tiles appear").

---

## 3. The 3 Quality Gates

### Gate 1 — API
N/A — no backend change (FE composes 3 existing frozen endpoints).

### Gate 2 — Function
☑ resolve() fail-open guard (rejected + malformed-fulfilled both → error tile) · ☑ 3 teeth-tests (home.screen + useHome, RED without guard — team-lead proved) · ☑ per-tile fail-open (one down → others render + warning) · ☑ stubs show no fake numbers · ☑ existing pass (239) · ☑ tsc clean · ☑ **0 unhandled errors** (new gate) · ☑ useSafeRouter · ☑ FE Chrome self-verify (canonical).

### Gate 3 — Sprint
☑ end_sprint_5 written · ☑ architect 4-step (useHome resolve()/allSettled read full — correct structural fail-open) + own run (239/0-unhandled/tsc) · ☑ tester T3 + team-lead canonical value-by-value + teeth-proof · ☑ counts ≥ baseline (213→239 vitest; pytest 344 unchanged, no BE) · ☑ findings (§5) · ☑ format `feat(sprint-5)`.

**VERDICT: ✅ All 3 gates GREEN** (vitest 239 + 0 unhandled, tsc clean, live value-by-value matches, fail-open teeth-proven).

---

## 4. Assumptions (user-review — decide-and-log)

- **Home v1 = FE composes the 3 live module endpoints** (`/finance` + `/projects` + `/market` via Promise.allSettled), NOT a `/home` or `/brief` backend aggregate. Reason: ARCH §9 Home is the full-aggregate-at-the-end; `/brief` is a separate S11 module (template + morning-pull routine). FE composition is the simplest dashboard (north-star). To change: add a `/home` aggregate endpoint if server-side composition is ever needed (not now).
- **3 tiles are "coming soon" stubs** (honest-mirror, zero fake numbers): Claude quota (S9), Brief (S11), Activity Feed (S14) — all in the mock SCREENS.home, all unbuilt. Each swaps → live when its module lands (additive, no Home rewrite). To change: build the module, replace the stub tile.
- **series=[] (Finance) → flat/placeholder net-worth chart** this build (no portfolio snapshot routine yet — north-star). To change: add a daily snapshot routine + reuse price_history.
- **Aggregate-incrementally** — Home grows as modules land; it does NOT wait for all 14 screens (ARCH §9 "Home last" = needs modules to EXIST, and we ship the aggregate of what exists + honest stubs).

---

## 5. Risks / out-of-scope (future)

- **3 stubs until their modules land** — Claude quota (S9), Brief (S11), Activity Feed (S14). Each is a marked placeholder; swap to live when built.
- **Net-worth chart flat** — needs the portfolio daily-snapshot routine (deferred); shows placeholder until then.
- **No /home backend aggregate** — if a future need wants server-side Home composition (e.g. for an external agent to fetch one Home payload), add `/home` then. FE composition is fine for the dashboard now.

---

## 6. Retro (process learnings)

1. **Green-suite MASKED the fail-open gap (the headline lesson) → memory `unhandled-errors-not-green`:** Round 1, frontend made the suite green by switching test mocks to persistent — but the HOOK was still unguarded (`f.value.data` without a null check). The suite passed; the gap remained. team-lead caught it because a green count with UNHANDLED ERRORS in the output is NOT green. **New gate: passed-count + 0 unhandled-errors — read the full vitest tail, not just the number.** Round 2 landed the real `resolve()` guard with teeth-tests.
2. **Vocab-lock (new kickoff step) ran clean** — diffed mock SCREENS.home labels vs SPEC §S1 before dispatch → matched (no Sprint-4-style cash/Dry mismatch). The upstream net works.
3. **Honest-mirror caught a silently-dropped panel** — team-lead diffed scope vs mock, found Activity Feed was being omitted (not in my original 2-stub scope). A panel in the approved design must be a marked stub, not dropped → added as the 3rd stub. (A real-data screen lies by OMISSION too, not just by fake data.)
4. **Architect comms miss** — dispatched T1/T3 then went idle without an explicit "dispatched X" ping; team-lead couldn't tell from outside if it had started (it had — useHome.ts was on disk). Fix: always send an explicit dispatch-confirmation, don't rely on task-board inference (idle-without-ping reads as silent-stall).

---

## 7. Commit
- `feat(sprint-5): home v1 command center (S1) — aggregate live modules` — useHome + Home screen + plan_5 (incl Activity addendum) + end_5. One commit.
- After: `sleep 120 && git push` → signal team-lead "Sprint 5 synced" → Sprint Sync (green-masked-gap = headline retro) + 2-part report → next sprint.
