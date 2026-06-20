# Sprint DXY-HONEST — revert the DTWEXBGS-as-DXY mislabel + back out the q_macro inflation (Cairn #15 corrective)

> Created 2026-06-21 by architect. CORRECTIVE for the honest-mirror INCIDENT in 5b380d4 (#15). team-lead APPROVED option (b) + scope (b). PRIORITY (live honest-mirror breach on a pushed commit).

## The incident
Commit `5b380d4` (#15 never-persist-mock) un-shadowed the pre-existing config mislabel `dxy→DTWEXBGS` (core/config.py:177), so `/macro/overview` dxy flipped to **source='fred', val 119.5073, label "US Dollar Index (DXY)", conf 0.77** — presenting FRED's DTWEXBGS (broad TRADE-WEIGHTED dollar) AS the ICE DXY index (a DIFFERENT instrument). This VIOLATES honest-mirror (life-os pillar: never present a near-miss as real) + REVERSES the logged decision plan_sprint_FRED-MACRO.md:20 ("keep DXY mock-labeled, NOT a renamed trade-weighted proxy; honest-mock > near-miss proxy") + the user's re-confirm (real DXY needs a dedicated API, not built → PARK it). And because q_macro = MEAN of ALL indicators' confidence (decision/service.py:575), dxy's fake-real 0.77 INFLATED q_macro 0.5108→0.6211 — an illegitimate lift.

## Fix (option b — keep hardening, revert mislabel, back out inflation; team-lead approved)
- **(a) Remove `dxy→DTWEXBGS`** from `core/config.py` fred_series (L177). dxy then has no real source → honest **source='mock'** + a clear warning "no live DXY feed (ICE DXY needs a dedicated API, not built)". NEVER source='fred'.
- **(b) q_macro EXCLUDES mock/honest-missing indicators from its mean** (decision/service.py:575-576). Currently `macro_qs = [v.confidence for v in overview.indicators]` includes EVERY indicator (a mock conf-0 DRAGS the mean). S1 (mock = absence, never counts) → exclude them: `macro_qs = [v.confidence for v in overview.indicators if v.source != 'mock']` (or `if v.confidence > 0` — but source!='mock' is the precise S1-aligned predicate). Honest landing: **0.596** (the 6 real), NOT 0.62 (inflated) NOR 0.511 (dragged-by-counting-mock-as-0). Consistent with how macro_cycle/q_from_points already drop mock via coverage.
- **(c) KEEP the never-persist-mock hardening** (record_point skip-mock, purge_mock, cold-start, the durable test) — it's correct + helps the 6 real indicators. Do NOT revert.
- DTWEXBGS stays available as its OWN clearly-named indicator LATER if the user wants the trade-weighted dollar (user-gated, NOT called 'dxy'). PARK — don't build now.

## Tasks
- **T1 (backend, gating):** remove dxy→DTWEXBGS (config) + dxy honest-mock warning + q_macro mock-exclude (decision/service.py) + tests. `docker compose restart backend` (config not hot-reloaded → restart). Backend writes pytest.
- **T2 (tester):** live — /macro/overview dxy source='mock' (NOT fred), warning present, real 6 still fred; /decision/weight q_macro == 0.596 (the 6 real), NOT 0.62, NOT 0.511.
- **T3 (architect):** 4-step review + commit (PRIORITY — before the next item).

## HARD GATE (distinguishing — the 0.596-vs-0.511 split is the key)
- dxy → source='mock', NOT 'fred'; honest warning; never presents DTWEXBGS as dxy. [honest-mirror restored]
- q_macro == **0.596** (mean of the 6 REAL indicators only) — NOT 0.62 (the inflated mislabel) NOR 0.511 (mock wrongly counted as 0). **THE distinguishing test: a fixture with N real + 1 mock indicator → q_macro = mean(real only), and asserting it ≠ mean(real + mock-as-0) splits exclude-vs-count-as-0.** [the S1-consistent back-out]
- The 6 real indicators still in the mean, source='fred', unaffected. [no over-reach]
- never-persist-mock tests (from #15) still GREEN (hardening kept). [don't break the good fix]
- pytest green, mypy clean.

## Baseline
pytest 1682 (post-#17). Keep 0-failed; expect +2-3.

## Assumptions (user-review)
- **dxy is honest source='mock' (never 'fred')** — DTWEXBGS (broad trade-weighted dollar) is NOT the ICE DXY index; presenting it as dxy violates honest-mirror. Real DXY PARKED until the user builds a dedicated API. **How to change:** when the user provides a real DXY feed, wire it as 'dxy'; OR add DTWEXBGS as its OWN clearly-named indicator (not 'dxy').
- **q_macro EXCLUDES mock indicators from its mean** (S1-consistent: mock = absence, never inflates NOR drags). Honest q_macro = mean of the real indicators only (0.596 now). **How to change:** the predicate is `v.source != 'mock'` in decision/service.py's macro_qs.

## Notes
- This corrects a honest-mirror breach on a pushed commit — priority over the (clean, verified) #17 + #14.
- The #15 end-doc's "0.51→0.62 synergy" was over-credited (it was the mislabel) — corrected on the record.
