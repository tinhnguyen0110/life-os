# End Sprint 4 — Finance (S5 Overview + S6 Portfolio Detail)

> Result doc (CLAUDE.md §3.2). 3rd backend module (finance: portfolio, P&L, allocation-vs-golden-path, ladder) + S5 Overview + S6 Detail. Uses Market prices (Sprint 3). FIRST sprint applying self-describing-raw. Full feature (SPEC §S5/§S6), simple impl (north-star).
> Author: architect · 2026-06-06 · Commit: `feat(sprint-4)` on `main`.

---

## 1. What shipped

### T0 — status.md repo-path fallback (3B layer-4 closed permanently)
`projects/service._tracked_repos`: if a status.md `repo:` path doesn't exist AND the pid is a config built-in → fall back to the config path (a stale/cross-env stored pointer no longer kills an otherwise-tracked project → reads dead). Behavior-test: stale `/nonexistent/...` path → config path + warning. Closes the 3B host-path-pollution recurrence.

### Backend — `modules/finance/` (3rd registry-discovered module, zero core edit)
- **schema.py (FROZEN):** `Channel = Literal["crypto","etf","vn","dry"]` (lowercase id; "Dry powder" is FE display), `Holding{channel,symbol,qty,avgCost,source,asOf}`, `PnL{cost,current,abs,pct}`, `ChannelAlloc{channel,value,pct,target,drift,driftAlert,pnl}`, `LadderState{channel,referencePrice,currentPrice,rungsIn,nextRung,distancePct,ladderRungs}`, `FinanceOverview{totalValue,change,holdings,allocations,pnlTotal,dryPowder,series}`.
- **service.py:** holdings from md_store `finance/holdings.md`; golden-path from `finance/golden_path.md` (absent → baseline Crypto38/ETF24/VN18/Dry20 + ladder -10/-20/-30% + warning). **Prices via `market.service.get_quote(symbol)`** (reuse market reader, fail-open — no duplicate CoinGecko). drift = actual−target, driftAlert = |drift|>5% (backend owns the 5% rule). P&L unrealized (cost=0→null). ladder triggerPrice = ref*(1+rung/100), rungsIn/nextRung/distancePct. **Fail-open on unknown STORED channel** (skip+warn, never 500 — structural).
- **router.py:** GET /finance (S5), GET /finance/{channel} (S6), holdings POST/DELETE, golden-path GET/PUT. Envelope + codes. Auto-discovered.
- **Self-describing-raw (FIRST application):** drift carries {target, actual}, pnl carries {cost,current,abs,pct}, ladder carries {triggerPrice,currentPrice,distancePct}, holdings source+asOf. Raw values (price/qty) no tag. An agent curling /finance understands drift/pnl/ladder without reading the code.

### Frontend — S5 Finance Overview + S6 Portfolio Detail
- `lib/types.ts` mirrors the frozen finance schema. Channel display formatter (`crypto`→"Crypto", `dry`→"Dry powder").
- **S5 `app/finance/page.tsx`:** total + change, allocation (4 channels + drift banner via driftAlert), P&L total + per-channel, dry-powder, click→S6. Render-only.
- **S6 `app/portfolio/[channel]/page.tsx`** (design-from-SPEC §S6, no mock — architect-approved): header+price, position KpiCards, ladder-state panel (rungs in / next + trigger / distance), signals (mock/stub), chart, journal-link stub. Render-only, reuses Sprint-2 shared components, useSafeRouter.

---

## 2. Verification (Rule #0 — architect + team-lead, value-by-value)

| Check | Result |
|---|---|
| pytest (staged tree) | **344 passed** |
| vitest | **213 passed** |
| tsc | clean |
| fail-open guard test (`test_overview_fail_open_on_stale_stored_channel`) | RED without guard → teeth ✓ |
| Live `/finance` value-by-value (team-lead hand-calc diff) | totalValue $63,171, pnlTotal +$20,691/+48.71%, crypto 96.09%/drift+58.09/PnL+51.75%, etf 3.91%/−0.4%, dry+vn pnl null — EVERY value matches |
| Live `/finance/crypto` (S6) | 200, value-diffed |
| Chrome S5 @ :3010 (canonical container) | $63,171 / +$20,691 / channels crypto·dry·etf·vn (no cash/junk) / drift banner / console clean |
| Self-describing dogfood | drift/pnl/ladder carry inputs — agent-readable ✓ |

Verified on the CANONICAL `docker compose up` stack (modules:[finance,market,projects]). Market/CoinGecko mocked in tests. Proportional verify (not full Sprint-1 ritual).

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema constraints (Literal channels, ge bounds) · ☑ integration tests (/finance, /finance/{channel}, holdings CRUD, golden-path) · ☑ existing pass (344) · ☑ auto-discovered (0 core edit) · ☑ envelope · ☑ codes (404 unknown channel, 422 body) · ☑ fail-open guard (unknown stored channel → skip+warn, no 500) · ☑ no auth.

### Gate 2 — Function
☑ Observable-behavior asserts (drift/P&L/ladder math, fail-open) · ☑ existing pass (344+213) · ☑ edge cases (no holdings, cost=0→null, unknown stored channel, golden-path absent→baseline) · ☑ error path (fail-open structural) · ☑ types (mypy + tsc clean) · ☑ no self-confirming · ☑ FE Chrome self-verify (canonical container).

### Gate 3 — Sprint
☑ end_sprint_4 + counts (use 344 full-suite, not the excl-scaffold 295) · ☑ architect 4-step (service fail-open + drift/PnL/ladder math read full) · ☑ tester + team-lead value-by-value canonical + Chrome · ☑ counts ≥ baseline (313→344 pytest, 187→213 vitest) · ☑ findings flagged (§5) · ☑ format `feat(sprint-4)`.

**VERDICT: ✅ All 3 gates GREEN** (pytest 344, vitest 213, tsc clean, live value-by-value matches, fail-open teeth-proven).

---

## 4. Assumptions (user-review — decide-and-log)

- **Channel ids = lowercase `crypto/etf/vn/dry`** (machine id), **display = "Crypto/ETF/VN/Dry powder"** (FE formats). Chose `dry` not `cash` to match SPEC §S5 "Dry powder" + the Discord-pinged baseline ("Dry 20%"). To change: edit the Channel Literal + FE display map (single-source the id).
- **Golden-path baseline** (Discord-pinged user, decide-and-log): targets Crypto38/ETF24/VN18/Dry20 + ladder rungs -10/-20/-30% from a reference price. md_store `finance/golden_path.md`, user-editable. To change: PUT /finance/golden-path or edit the file.
- **driftAlert = |drift| > 5%** (the 5% threshold is a backend-owned business rule — single-source, agent-visible; FE does NOT re-threshold). To change: the DRIFT_ALERT_PCT constant.
- **P&L = unrealized** (price−avgCost)×qty; cost=0 → pct null. Current price via market (crypto real CoinGecko / etf+vn mock, source-tagged).
- **Ladder = simple rungs** (-10/-20/-30% from reference in golden_path), NOT an engine (north-star). triggerPrice/rungsIn/nextRung/distancePct self-describing.
- **series = []** this build (no portfolio daily-snapshot routine — north-star; reuse price_history later for the over-time chart).
- **Signals (oil/ETF/CPI/Fed/FTSE) = mock/stub** on S6 (data-fallback, render now, real feeds later). **Journal-link = stub button** (Journal S9 not built).
- **ladder request/response asymmetry (backend flagged):** golden_path stores `ladder` (rung %s); the response exposes `ladderRungs` (computed trigger prices). In (config) vs out (computed) intentionally differ — the response carries the derived values self-describing.

---

## 5. Reactive bugs caught + fixed THIS sprint

1. **Live /finance 500 — stale `targets.cash` in stored golden_path.md** (old naming, pre cash→dry). pytest green (tmp dirs can't see the real-disk stale store). Fix = data cleanup (cash→dry via PUT) + **structural fail-open** in get_overview (unknown stored channel → skip+warn, never raise). **2nd stale-stored-artifact crash** (cf 3B status.md host-path) → the service must be resilient to its OWN store carrying old-format data. Logged to memory `verify-live-app-not-just-suite`.
2. **5 S6 portfolio vitest failures** — test-isolation: dup-text (`getByText`→`getAllByText`), a `vi.mock` named-fn gotcha (mocked `getChannelDetail` not `apiGet`), removed a redundant local `afterEach` racing the global one. Frontend fixed (its own scaffold).

---

## 6. Risks / out-of-scope (future)

- **series chart empty** — portfolio value over time needs a daily snapshot routine (deferred). The over-time chart on S5 shows flat/empty until then.
- **Signals + Journal are stubs** — real macro signals + the Journal write (S9) are later sprints.
- **The stale-stored-channel class** — fail-open guard handles unknown channels gracefully now, but any future enum rename should migrate stored data (a PUT or a small migration), not just rely on skip+warn (the user loses that channel's data silently until re-set).
- **/portfolio overview list (donut + all holdings)** — the mock's `SCREENS.portfolio` overview is NOT this sprint (S5 has the allocation panel; a dedicated list is a possible later task).

---

## 7. Retro (process learnings)

1. **schema-freeze-gate caught the channel mismatch BEFORE the FE handoff** — the cash-vs-Dry disagreement surfaced at the freeze checkpoint (15 failing tests on the staged tree), not after FE had mirrored. Holding the FE-mirror gate until "schema frozen + agreed" is exactly what prevented a Sprint-3-style cascade. The gate works.
2. **2nd stale-stored-artifact crash** (golden_path `cash`, after 3B status.md host-path) → a service must be fail-open against its OWN persisted store carrying old-format data, not just against external feeds. Structural guard (skip+warn unknown) > data cleanup (recurs).
3. **id-vs-display separation** resolved the naming conflict cleanly — lowercase machine id (single-source, agent-friendly) + a display formatter (user's terms). Better than forcing one casing everywhere.
4. **Self-describing-raw shipped clean** (first application) — derived fields carry inputs, raw don't; the dogfood ("agent understands without reading code") passed on /finance.

---

## 8. Commit
- `feat(sprint-4): finance overview + portfolio detail (S5/S6)` — finance module + T0 status.md-fallback + S5/S6 FE + the 2 reactive fixes + plan/end docs. One commit.
- After: `sleep 120 && git push` → signal team-lead "Sprint 4 synced" → Sprint Sync (Standup→Retro) + user report → Sprint 5/next.
