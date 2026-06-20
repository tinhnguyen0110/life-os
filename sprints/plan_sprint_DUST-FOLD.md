# Sprint DUST-FOLD — fold sub-$1 dust in exchange_overview (Cairn #17, dogfood-R4 GAP-5)

> Created 2026-06-21 by architect. LOW. Reuse finance's existing dust-fold philosophy on the exchange balance list. Runs in PARALLEL-pipeline with #15 (different module: exchange vs macro).

## The gap
`exchange_overview` lists true-zero dust as full balance rows (ETH 3.95e-7=$0.0000007, LINK, DOGE 6.6e-7). `finance_overview` ALREADY folds sub-$1 dust (one `·dust` summary, value preserved); `finance_guardian` even flags "3 sub-$1 dust" — but the raw exchange read doesn't fold, so an agent must filter manually. Apply the SAME fold philosophy to `exchange_overview` balances.

## Reuse, with a shape adaptation (NOT a blind import)
finance's `_fold_dust`/`_is_dust` operate on `Holding` (has `price` + `usdValue` + `channel`). Exchange uses `OkxBalance` (has `usdValue: float|None`, NO `price`, NO `channel` — one flat list). So:
- **Dust predicate for exchange:** `usdValue is not None AND usdValue < DUST_USD_THRESHOLD ($1)`. (Drop the `price is not None` clause — OkxBalance has no price field; usdValue is the value signal.) **null-usdValue stays VISIBLE** (unknown ≠ small — same lock as finance).
- **`< $1` STRICT** (exactly $1.00 stays visible) — same as finance.
- **Flat fold (no channel grouping):** collapse all dust balances into ONE `·dust` summary `OkxBalance` (symbol="·dust", usdValue=sum, a count, total/available=0 or the summed totals — pick one + document; usdValue=sum is the value-preserving one). 0 dust → no dust row.
- **DISPLAY-only:** the overview's `total_usd` was already computed from the full set — the fold must NOT change the total (value preserved, just grouped). Assert Σ(folded incl dust summary) == pre-fold total.

## Implementation
- Reuse the `DUST_USD_THRESHOLD = 1.00` constant — import it from finance.service (single source) OR define an exchange-local mirror with a comment pointing at finance (architect pick: IMPORT from finance.service to keep one threshold — confirm no circular import; if circular, mirror w/ a comment). Do NOT hardcode a 2nd magic number.
- Add `_fold_dust_balances(balances: list[OkxBalance]) -> list[OkxBalance]` in exchange/service.py (the flat-list analogue of finance's `_fold_dust`). Apply it in `get_overview` to the `balances` list AFTER `_parse_balances` computed total_usd (so total is unaffected).
- OkxBalance may need an `isDust: bool = False` + `count: int | None = None` additive field (mirror finance's Holding.isDust) so the FE/agent can render the summary — additive/nullable, no break. Confirm + add to schema if absent.

## Tasks
- **T1 (backend, gating):** `_fold_dust_balances` + apply in get_overview + the OkxBalance isDust/count additive fields (if needed) + the threshold reuse + tests. `docker compose restart backend`. Backend writes pytest.
- **T2 (tester):** live `/exchange/overview` → sub-$1 balances folded into one `·dust` row (count = the dust coins, ETH/LINK/DOGE sub-cent gone as individual rows); total_usd UNCHANGED (value preserved); a ≥$1 balance + a null-usdValue balance stay individual (distinguishing).
- **T3 (architect):** 4-step review + commit (SERIAL — after #15's commit, 1 committer/tree).

## HARD GATE (distinguishing)
- Sub-$1 priced dust (ETH 7e-7) → folded into `·dust` (count includes it). [the fix]
- A ≥$1 balance → stays an individual row. [not over-folding]
- A null-usdValue balance → stays VISIBLE (unknown ≠ small — the finance lock). [the distinguishing — a naive "usdValue<1 or None" would wrongly fold unknowns]
- total_usd identical before/after the fold (Σ preserved — DISPLAY-only).
- pytest green, mypy clean.

## Baseline
pytest (post-#15, TBD — anchor at #17 dispatch). Keep 0-failed; expect +2-3.

## Assumptions (user-review)
- **exchange_overview folds sub-$1 priced dust into one `·dust` summary** (usdValue=sum, count), same $1 threshold + same philosophy as finance (null-usdValue stays visible = unknown≠small). DISPLAY-only, total unchanged. **How to change:** edit DUST_USD_THRESHOLD (shared w/ finance) or the predicate; the fold is in exchange/service._fold_dust_balances.

## Notes
- Independent of #15 (macro) + #14 (decision-journal) — parallel-pipeline per the new §1.5 rule; COMMIT serial.
- Single-user no-overengineering: reuse finance's proven philosophy, don't reinvent.
