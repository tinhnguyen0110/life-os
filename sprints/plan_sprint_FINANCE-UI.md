# Sprint FINANCE-UI — /decision cockpit + portfolio enrich + wire write-forms (Task #63)

The finance-assistant tower (P1-P4 + audit S1/S1B/S2/S3) is backend/MCP-only — the USER has no UI for ANY of it. Close the UI/user-API gap: ONE `/decision` cockpit + nudge per-coin P&L/nav into `/portfolio` + wire the (mostly-existing) write-forms. FE-screen sprint → frontend-2. NEUTRAL is load-bearing into the UI layer.

## Kickoff — 2026-06-16 (§3.3a — all shapes curled LIVE, VERIFY-FIELDS-EXIST)

### Live route shapes (curled on :8686 — the EXACT fields the dispatch names; no phantoms)
All decision routes are mounted at `/decision/*` (registry prefix = module name). Write routes confirmed present.

**GET /decision/weight** → `{weight:0.0238, verdict:"thin", breakdown:[{layer:"q_cycle"|"q_macro"|"q_flow"|"s_asset", q:float, note:str}], bindingConstraint:"s_asset", explanation:str, confidence:0.4281, legend:str}`
  - `weight` = ∏ layer q (signal strength); `confidence` = trust in the measurement (§116 TWO numbers — render BOTH, the `legend` string explains the difference; do NOT conflate).
**GET /decision/macro-cycle** → `{phase:"overheat", axes:[{axis:"growth"|"inflation"|"yield_curve", direction:"up"|"down"|"flat", present:bool, detail:str}], qCycle:{q,freshness,coverage,agreement, breakdown:[{name,present,value,ageDays,freshness,source}], neededInputs,presentInputs,paramsUsed:{tauSeconds{...},...}}}`
**GET /decision/allocation** → `{phase, capitalTier:"small"|"large", targets:{crypto,etf,vn,dry}(pct), rationale:{crypto,etf,vn,dry}(str), vsStaticGoldenPath:{crypto,etf,vn,dry}(delta pp), confidence:0.6786, note:str}`
**GET /decision/guardian** → `{alerts:[{severity:"high"|"low"|..., msg:str(a QUESTION), evidence:{...}, sources:[str]}], confidence:1.0, asOf:iso, note:str|null}`
**GET /decision/nav-history** (`?from&to`) → `{series:[{date:"YYYY-MM-DD", nav:float}], points:int, range:{from,to}, confidence:float, warning:str|null}`

**Write/settings (mostly exist — wiring not build):**
- **PUT /finance/crypto-basis** body `CryptoBasisInput {basis: number}` (required) — CHANNEL-LEVEL (one number for the whole crypto channel). GET returns `{basis, source}`.
- **POST /decision-journal** body `JournalInput {action,asset,reason (required); date,size,px,tag,channel("crypto"|"etf"|"vn"|"dry"),thesis,negationCondition,confidence(0-100),pnl,outcome("open"|"right"|"wrong"),lesson (optional)}`. NOTE: the field is `negationCondition` (NOT falsificationCondition); `expectedEv/worstCase/decisionWeight` are NOT on the create input — do NOT name them.
- **PATCH /settings** — capital-tilt fields confirmed: `riskCapitalSmallUsd:50000.0`, `riskCapitalLargeUsd:500000.0` (on AppConfig + AppConfigPatch).

**Per-coin P&L source (the S12A trap — pnl lives at TWO levels):**
- `GET /finance .holdings[]` (8 live) — PER-COIN: `{channel,symbol,qty,avgCost,source,asOf,price,usdValue,changePct,isDust,count,pnl}`. So per-coin `pnl`/`price`/`changePct`/`usdValue` ARE on each holding (null for USDT/no-basis stablecoins; real for accAvgPx coins). THIS is the per-coin P&L source.
- `GET /finance .allocations[].pnl` = CHANNEL-level `{cost,current,abs,pct}` (abs/pct null when `basisUnknown:true`). DISTINCT from per-coin pnl — name each precisely so FE doesn't conflate.
- `GET /finance/holdings` returns `[]` live — the per-coin array is under `/finance` overview's `.holdings`, NOT this endpoint. Use `/finance` (the `useFinance` hook already fetches it).

### Existing FE pattern (FE PORTS, doesn't redesign)
- `lib/api.ts`: `apiGet<T>("/path")` → `{success,data,warning?}`; hooks per resource (`useFinance`/`usePortfolio`/`useDecisionJournal`/`useMacro`/`useSettings`) own loading/error/warning + types mirror backend schema in `lib/types.ts`. **SELF-DESCRIBING RAW: backend computes; FE renders/formats/colors, NEVER recomputes — a wrong number is a backend bug, reported not patched.**
- Routes exist: `/portfolio` (236L), `/finance` (316L), `/decision-journal` (294L, ALREADY a screen). NO `/decision` route, NO `useDecision.ts` — those are NEW.
- 25 routes live + real (only `/exchange` stub). Design tokens: `lib/tokens.css` + the existing finance/portfolio screens — port them.

### Per-coin basis flag (RESOLVED — channel-level now, per-coin = a flagged follow-up)
PUT /finance/crypto-basis is CHANNEL-LEVEL (`{basis}`). Per-coin basis = OKX `accAvgPx` (read-only, auto). For OFF-OKX coins there's NO per-coin set-basis endpoint. **DECISION: wire channel-level set-basis now (the existing endpoint covers the real need — the crypto channel's manual basis). Per-coin manual set-basis for off-OKX coins = a SMALL backend API add (POST /finance/holdings already sets avgCost on a manual holding — that path exists) — flagged as a follow-up, NOT in this sprint.** No backend work needed for FINANCE-UI; backend-2 idle unless the user later wants off-OKX per-coin manual basis.

### Final task list
- **T1 (gating) — `useDecision.ts` hook + types** mirroring the 5 decision route shapes in `lib/types.ts` (the contract FE builds on). apiGet each; one hook exposing weight/macroCycle/allocation/guardian/navHistory (or a small hook each — FE's call). Freeze the types first.
- **T2 — `/decision` cockpit screen** folding the 4 tower tools + nav line: W gauge (weight + verdict + bindingConstraint + 4-layer breakdown with per-layer q + note), Investment-Clock phase + axes, guardian alert cards (render msg AS-IS = questions), allocation weights + vsGoldenPath delta + rationale, nav-history line. Render `confidence` everywhere (low q → "thin"/de-emphasized; the §116 weight≠confidence two-number legend rendered, not conflated). NEUTRAL copy.
- **T3 — /portfolio enrich (no new route):** per-coin P&L from `/finance .holdings[]` (pnl/price/changePct, null-safe for no-basis) + nav-history line. Channel pnl stays where it is.
- **T4 — wire write-forms (REDUCED — decision-journal create ALREADY wired):** the `/decision-journal` screen ALREADY has a full create form (`useDecisionJournal.create`, `dj-create-submit`, fail-closed) — DONE, don't duplicate. T4 = the TWO not-yet-wired: (a) PUT crypto-basis channel-level set-basis form, (b) PATCH settings capital-tilt (riskCapitalSmall/Large). Both via the existing `apiPut`/`apiPatch` (fail-closed). WRITE-FORM ROUND-TRIP: submit→2xx→re-GET reflects→persists post-reload.

## CRITICAL LOCKS (folded into the dispatch)
- **NEUTRAL into the UI (load-bearing):** the payloads are NEUTRAL by backend design; FE must NOT add advice imperatives in labels/copy (no "buy"/"sell"/"should"/"rebalance"/"move"). Render the verdict WORD + guardian QUESTIONS verbatim. Same no-advice discipline the backend tools pass, extended to the UI.
- **VERIFY-FIELDS-EXIST (done):** every field named above was curled live. FE renders ONLY these. `negationCondition` (not falsification...); per-coin pnl on `.holdings[]` not the empty `/finance/holdings`; channel pnl on `.allocations[].pnl`.
- **Render confidence honestly:** each tool carries q/confidence — the cockpit renders it (low → "thin signal"/de-emphasized, matching verdict="thin"). Don't show a confident-looking W when confidence is low (render weight AND confidence, the legend explains).
- **FE recomputes NOTHING:** backend-computed values rendered/formatted/colored only (the established self-describing-raw rule). A wrong number → report to team-lead, don't patch in the UI.

## Risks / seams
- The S12A trap: per-coin pnl (`.holdings[].pnl`) vs channel pnl (`.allocations[].pnl{}`) — two shapes, named distinctly. null when no basis (USDT/off-OKX) → render "—"/basisUnknown, never fabricate a number.
- W is "thin" (0.0238) HONESTLY — the cockpit must convey low conviction (de-emphasize, show confidence 0.43), NOT a big green "go" gauge. Honest confidence is the whole point.
- nav-history has only 2 points live (short series, confidence 0.066) — render the `warning` ("still accumulating"), don't draw a confident trend line from 2 points.
- decision-journal screen ALREADY exists — T4's journal-form may extend it, not duplicate. FE checks the existing screen first.
