# end_sprint_102-TRACING-PERF — heatmap perf MEASURE-FIRST → YAGNI-close + slow regression-pin (Cairn #102, HIGH)

> Result. admin-lead flagged `_derive_heatmap` (tracing) as a suspected O(activity×84day×logs) perf-cliff at scale (100 act × 1yr). MEASURE-FIRST (the HARD rule: no blind optimization): benchmarked at 100act×365d (~36.5k logs) → `overview()` ~46ms / `_derive_heatmap` ~10ms / POST log ~2ms — ALL 10×+ under the 500ms budget → **NO cliff, YAGNI-CLOSE, NO prod change.** The deliverable is the measurement + a committable `@pytest.mark.slow` regression-pin (catches a FUTURE cliff). Commit `<hash>` `test(sprint-102-tracing-perf): slow regression-pin, YAGNI-no-fix at 100act×1yr (#102)`. Status: ✅ verified (backend-w3 measured; architect INDEPENDENTLY re-measured — the slow-pin passes the budget + correctness). Cairn #102 — HIGH scale-pain, measure-first close.

## What shipped (TEST-ONLY — no prod code change)
| File | Change |
|---|---|
| `tests/test_tracing.py` (+1, `@pytest.mark.slow`) | `test_102_overview_perf_at_scale`: seeds 100 act × 365 days (~36.5k logs) on the isolated `db` fixture → asserts `overview() < 1.0s` (20× headroom over the measured ~46ms — catches a real O(act×day×logs) regression, tolerates slow CI) + the heatmap correctness (len 84, `any(count>0)` = real per-day counts NOT blanked, `max ≤ n_act`). slow-marked → OUT of the default suite. |

## Design (LOCKED — measure-first, YAGNI-close, regression-pin, semantics-guarded)
- **🔴 MEASURE-FIRST (the HARD rule):** the cliff was a HYPOTHESIS (board had ~0 activity). Measured at the worst realistic scale (100act×1yr) BEFORE any fix. ~46ms overview → 10×+ under the 500ms budget → close-no-fix. Optimizing without a measured cliff = blind/YAGNI (admin-lead's own rule). **Closing-no-fix on a fast measurement is a VALID complete outcome, not a non-result.**
- **why no cliff (the root the worry missed):** `logs_since(window_start)` BOUNDS the read to the 84-day window (NOT full-year) → 1-year history does NOT widen the per-derive cost. The logs are read ONCE into a `by_act_day` dict, then it's an 84×activity lookup loop → **O(logs_in_window + 84×activity), NOT O(logs×84×activity)**. Trivial at any personal scale.
- **the committable deliverable = a regression-pin:** even with no fix, the `@pytest.mark.slow` test PINS the budget — a FUTURE change that reintroduces an O(×logs×day) scan (or blanks the heatmap) fails the pin. slow-marked so it's opt-in (`-m slow`), out of the default suite (count unaffected).
- **semantics guarded:** the pin also asserts the heatmap carries REAL per-day counts (`any(c>0)`, `max≤n_act`) — so a future "optimization" that blanks/breaks the heatmap fails the pin, not just a perf regression.
- **future-lever (documented, NOT built):** if scale ever 10×'s (1000+ act, or the window widens), `CREATE INDEX tracing_logs(date)` / incremental pre-derive on log-write are the levers — noted here, built only when measured.

## Verification (Rule#0 — architect INDEPENDENT re-measure)
- **architect INDEPENDENT re-measure (perf claim = Rule#0-verified, my own number not backend's):**
  - `_derive_heatmap` (isolated, 100 act × 84-day window = 8,400 rows) = **4.16 ms/call**; 3× stress (300 act × 25,200 rows) = **13.96 ms/call** — both << 500ms.
  - RAN the slow-pin myself: `test_102_overview_perf_at_scale` **PASSED** (overview() < 1.0s at 100act×365d + the heatmap-correctness asserts). ✅
- **🔴 NO prod code change:** `git status` — only `tests/test_tracing.py` touched; tracing service.py/store.py/reader.py UNTOUCHED (heatmap semantics / VN-day bucketing / 84-day window all unchanged). ✅
- **default suite unaffected:** the slow-pin is DESELECTED from `-m 'not slow'` (`12 passed, 1 deselected` on the tracing file) → the 2240 default count is unchanged. ✅
- **live store untouched:** the pin seeds the isolated `db` fixture (not the real container); no seed-leak (#72 held). ✅

## 3 Gates
- **Gate 1 (n/a — no API/prod change):** the measure-first close changes no behavior; the heatmap is already well-bounded. ✅
- **Gate 2 (Function):** the regression-pin asserts BOTH perf (<1.0s) AND correctness (real heatmap counts); independent re-measure (4ms + the pin passes); isolated fixture; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc (with the measurement + the YAGNI rationale + the future-lever); architect independent re-measure; staged EXACTLY test_tracing.py + end doc (NO prod code, no data/.env); commit format `test(sprint-102-...)`. ✅

## Assumptions (user-review)
- **#102 closed WITHOUT a fix** — measured 46ms @ 100act×1yr, 10×+ under budget. **Why:** no measured cliff → optimizing is blind (YAGNI). **How to change:** if real scale ever exceeds the budget (the slow-pin will catch it), the future-lever is an index on tracing_logs(date) + incremental heatmap derive.
- **budget ceiling = 1.0s in the pin** (20× over the measured 46ms). **Why:** catches a real cliff while tolerating slow CI hardware. **How to change:** the `assert elapsed < 1.0` in the pin.
- **the heatmap reads the 84-day window only** (not full-year) — the reason there's no cliff. **How to change:** n/a (the window bound is the design; widening it would reintroduce the cost — the pin would catch it).

## Notes
- Cairn #102 HIGH — admin-lead's QA-pain-finder (suspected heatmap perf-cliff at scale). The HARD measure-first rule worked exactly as intended: the cliff was a hypothesis → measured → no cliff → close-no-fix (NOT blind-optimize). backend-w3 measured (~46ms) + wrote the slow-pin; architect INDEPENDENTLY re-measured (4ms _derive_heatmap + ran the pin green — a perf claim gets the same Rule#0 as any finding). The architect's scout PRE-dispatch already predicted this (O(logs+84×N) not O(logs×84×N) — logs read once into a dict) → the dispatch was measure-first with the YAGNI-close as the expected valid outcome. TEST-ONLY commit (the pin); zero prod change; the live tracing store untouched. This + #101 (c47a4a2) clear both HIGH scale-pains. The slow regression-pin is the durable value: future-proofs the heatmap budget + its semantics without a premature optimization.
