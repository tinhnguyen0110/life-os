# Sprint NB4 — finance honest-framing (stableValue split + basisUnknown null-pct + dry-powder warning)

> Blank-context dogfood (memory `blank-context-dogfood-2026-06-15`) #1 trust dent. team-lead verified live. Backend-only, read-path framing.

## Kickoff — 2026-06-15 (architect)

### The two dents (team-lead verified the misleading number live)
- **(a) USDT counted as "crypto" → misleading drift.** ~98% USDT in the crypto channel → the drift engine reads "+62% crypto drift, rebalance!" when the user is ~98% in cash-equivalent. Technically right, misleading.
- **(b) avgCost null → aggregate crypto pnl reads as a fake gain.** OKX value-only holdings have no cost basis → crypto pnl `{abs:13.02, pct:0.12%}` = USDT-face-vs-live noise, reads as an investing gain.

### Decisions (decide-and-log) — honest-FRAMING, NO channel re-architecture
- **(a)** Explicit `STABLECOINS` frozenset (USDT/USDC/DAI/BUSD/TUSD/FDUSD/USDD/PYUSD/GUSD/USDP). `_stable_split(entries, channelValue)` → (stableValue, stablePct) for the crypto channel. When `stablePct > STABLE_HEAVY_PCT (50)` → append a NEUTRAL warning "crypto channel is X% stablecoins ($Y) — dry-powder-like, not crypto exposure" (surfaced via the router `ok()` envelope `warning` field — where the consumer reads it).
- **(b)** `_basis_unknown(entries)` → true when holdings majority lack a real avgCost (OKX value-only). `_pnl_framed(cost, current, basis_unknown)` → nulls `pnl.pct` when basis_unknown (keeps cost/current/abs); real-basis channel → unchanged pnl (manual P&L NOT hidden).
- Applied at BOTH ChannelAlloc sites (overview + channel-detail) via the shared helpers so they can't drift.

### Distinguishing cases (verified on disk + live post-reload)
- (a) 98%-USDT → stablePct 97.75 + warning fires; all-volatile → stablePct 0, no warning.
- (b) crypto value-only → basisUnknown:true + pnl.pct None; manual real-avgCost → basisUnknown:false + real pnl.pct shown.

### Note: the "2 gaps" episode was a STALE CONTAINER
team-lead's first live check hit a half-reloaded :8686 (flag landed, framing didn't). Disk code was correct (6 tests + direct fn calls). Resolved by `docker compose restart backend` → re-verify green. Lesson: a "half-landed" live state → check container freshness BEFORE calling it a code bug (the disk is truth).

## Assumptions (user-review)
- Stablecoin set = explicit 10 USD-pegged coins (USDT/USDC/DAI/BUSD/TUSD/FDUSD/USDD/PYUSD/GUSD/USDP). To change: edit `STABLECOINS`.
- `STABLE_HEAVY_PCT = 50` — crypto channel >50% stablecoin fires the dry-powder warning. To change: edit the constant.
- `basisUnknown` = channel holdings majority (by the `_basis_unknown` rule) lack a real avgCost → null `pnl.pct` (keep cost/current/abs). A manual channel with real avgCost shows real pnl unchanged.
- Read-path framing only — no channel-model change, no write, no disk mutation. The drift number itself is unchanged; the warning makes it interpretable.
