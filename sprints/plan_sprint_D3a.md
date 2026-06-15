# Sprint D3a — finance honest-framing follow-ons (pnl.abs suppress + drift reframe)

> Answer-quality audit (memory `answer-quality-audit-data-gaps-2026-06-15`) D3a: two NB4 follow-ons. (a) NB4 nulled pnl.pct but pnl.abs STILL shows +$14 with basisUnknown (reads as a gain); (b) the "+62% crypto drift" line reads as "too much crypto" when it's really undeployed cash. Backend-only, small, same finance/service.py.

## Kickoff — 2026-06-15 (architect)

### Verified on disk
- **(a) `_pnl_framed`** (finance/service.py:252) — nulls `pct` when basis_unknown but KEEPS `abs`. Live: crypto `pnl {cost:10637, current:10651, abs:14.02, pct:None}` + basisUnknown:True → the +$14.02 abs still reads as a small gain. **`PnL.abs` is currently `float` (REQUIRED, schema.py)** — so nulling it needs a schema change to `float | None` (mirror pct, which is already `float | None`). Both call sites use `_pnl_framed` (L536 overview + L615 channel-detail) → one fn fix covers both.
- **(b) drift warning** (service.py:523) — `f"{ch}: allocation drift {drift:+.1f}% (target {target}%, actual {pct}%)"` fires for crypto at +62% drift. It's appended BEFORE the stablecoin context (L530) → consumer sees "crypto drift +62%" + a SEPARATE "97% stablecoin" line, disconnected. When stablePct>90 the drift IS undeployed cash, not crypto over-exposure.

### 🔑 DECISIONS (architect calls — decide-and-log)

**(a) pnl.abs suppress when basisUnknown:**
- Make `PnL.abs: float | None` (schema.py) — mirror `pct`. In `_pnl_framed`, when basis_unknown → null BOTH `abs` and `pct` (`model_copy(update={"abs": None, "pct": None})`). Keep `cost` + `current` (those are REAL observable $ — current value is real, cost is the snapshot basis; only the DERIVED gain figures abs/pct are meaningless without per-unit basis).
- A channel with REAL avgCost (basis_unknown False) → abs+pct SHOWN unchanged (the legit manual P&L is NOT hidden — the distinguishing case).
- Rationale: a "+$14 gain" with no real cost basis is as misleading as the "+0.12%" NB4 already killed — same honest-null principle, applied to the other derived field.

**(b) drift reframe when stablePct>90 (crypto only):**
- Compute `stable_pct` for crypto BEFORE the drift-warning append (move the crypto stable_split up, or guard the drift line). When crypto AND `stable_pct > _UNDEPLOYED_PCT (90)` → the drift warning reads as undeployed, e.g. `f"crypto allocation {drift:+.1f}% vs target — but {stable_pct:.0f}% is stablecoin (undeployed cash, not crypto exposure)"` INSTEAD of the plain "drift" line. A real-crypto channel (stablePct low/None) → the PLAIN drift line (unchanged).
- Keep it NEUTRAL (describe the composition; no "deploy it" advice). This makes the drift line INTERPRETABLE — the audit's Q1/Q2/Q4 "leads with 'too much crypto' not '98% cash undeployed'" fix.
- Do NOT remove the existing NB4 stablecoin warning (L530) — the drift reframe + the stablecoin line are complementary; the drift line gains the undeployed context so it's not read in isolation.

### Scope boundary
- Read-path framing ONLY — no write, no channel-model change, no drift-threshold change (the 5% rule + drift number stay; we make the WARNING interpretable). NEUTRAL throughout.
- `cost`/`current` stay real (don't null them — they're observable); only `abs`/`pct` (derived gains) null when no basis.

### Final task list (single backend lane)
- **D3a [backend]** — (a) `PnL.abs` → `float | None`; `_pnl_framed` nulls abs AND pct when basis_unknown (keep cost/current). (b) crypto drift warning reframed to carry undeployed context when stablePct>90. Both finance/service.py + finance/schema.py. Tests for both distinguishing cases.

## Verification (distinguishing cases — locked)
- **(a)** crypto (basisUnknown) → `pnl.abs` None AND `pnl.pct` None (both suppressed); cost+current still present (real $). A MANUAL channel with real avgCost → abs+pct SHOWN (real P&L not hidden). [distinguishing: the value-only channel nulls abs, the real-basis channel keeps it.]
- **(b)** crypto stablePct>90 → the drift warning carries the undeployed framing ("X% stablecoin, undeployed cash, not crypto exposure"); a real-crypto channel (stablePct low/None) → the PLAIN drift line, no undeployed reframe. [distinguishing: stable-heavy reframes, real-crypto doesn't.]
- NEUTRAL: no advice verb in the reframed warning (asserted). Read-only (no disk mutation). Existing finance tests pass (the abs→None must not break a test asserting abs is a number for a real-basis channel — check). Full suite ≥1502, 0 errors/unhandled.

## Assumptions (user-review)
- **(a)** When a channel's basis is unknown (value-only/OKX), BOTH derived P&L figures null: `pnl.abs` AND `pnl.pct` → None (cost/current kept — real $). A real-avgCost channel shows real abs+pct. `PnL.abs` made nullable to allow this.
- **(b)** When crypto stablePct>90, the allocation-drift warning is reframed to "undeployed cash (X% stablecoin), not crypto exposure" instead of a bare "+62% crypto drift" — so the drift isn't misread as over-exposure to volatile crypto. Threshold 90 (= the undeployed band). A real-crypto channel keeps the plain drift line. NEUTRAL, read-path only, drift number/threshold unchanged.
