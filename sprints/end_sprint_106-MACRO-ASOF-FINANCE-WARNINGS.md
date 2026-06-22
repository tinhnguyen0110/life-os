# end_sprint_106-MACRO-ASOF-FINANCE-WARNINGS — macro asOf shape-stable + finance warning dedup (Cairn #106, dogfood)

> Result. Two agent-first shape/noise bugs: (1) `/market` macro had a mixed `asOf` shape — live entries carried an ISO string, Brent (+ n/a fallbacks) carried `null` → an agent iterating `macro[]` doing `asOf[:10]` CRASHED on the null; (2) `finance_analytics` returned ~6 warnings — the stablecoin observation phrased twice + per-channel drift boilerplate for every channel. Fixed: asOf is now ALWAYS a string (`""` for no-live, type tightened to `str`); finance warnings deduped at source + the noisy drift WARNING fires only >30% (the driftAlert FIELD@5% unchanged). Commit `<hash>` `fix(sprint-106-macro-asof-finance-warnings): asOf shape-stable + warning dedup/threshold (#106)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live teeth — asOf-all-string no-crash + warning count ~6→1). Cairn #106 LOW — dogfood (team-lead Rule#0-confirmed both).

## What shipped (market + finance + tests)
| File | Change |
|---|---|
| `market/service.py` (`macro_signals`) | Brent + the F&G/BTC.d n/a fallbacks: `asOf=None` → `asOf=""` (shape-stable — ALWAYS a string; live entries keep their ISO ts). source="mock"/value="n/a" still signal not-live. |
| `market/schema.py` (`MacroSignal`) | `asOf: str \| None = None` → `asOf: str = ""` (TYPE tightened — provably never None, not just runtime). |
| `finance/service.py` (`_get_overview_impl`) | (a) DEDUP at source: the undeployed-stablecoin REFRAME line (crypto >90% stablecoin + notable drift) now SUPPRESSES the separate dry-powder line — the same stablecoin story isn't told twice; (b) the per-channel drift WARNING fires only at `abs(drift) > WARNING_DRIFT_PCT (30)` — NOT every >5% channel. The driftAlert FIELD stays at >5% (DRIFT_ALERT_PCT, unchanged — the precise structured signal). |
| `tests/test_market_fng_honest.py` | the n/a-fallback asserts updated `asOf is None` → `asOf == ""` (the new shape-stable contract). |
| `tests/test_finance_mcp_shape.py` + `test_finance_okx.py` (+1) | warning-shape updated; NEW `test_106_mid_drift_no_warning_but_field_still_alerts` — a 5-30% drift → driftAlert FIELD True (>5%) but NO noisy WARNING (>30%) — the field-vs-warning distinction. |

## Design (LOCKED — shape-stability, dedup-at-source, field-vs-warning split)
- **PART 1 — asOf shape-stable (never null mid-string-field):** an agent iterating `macro[]` must be able to do `asOf[:10]` on EVERY entry without a None-crash. Fix: `asOf=""` for any mock/no-live entry (NOT None, NOT a fabricated date — honest-mirror: "" means "no timestamp", source="mock" signals it). The schema TYPE is now `str` (not `str|None`) → provably shape-stable. Live entries keep their real ISO ts.
- **PART 2a — dedup at the SOURCE (not a blanket list-dedup):** the dry-powder line and the undeployed-stablecoin reframe line were the SAME stablecoin observation phrased twice. Fix at the source: when the reframe fires (crypto >90% stablecoin AND notable drift), it tells the whole story → SUPPRESS the separate dry-powder line. One stablecoin warning, not two. (Better than a blanket `dict.fromkeys` dedup — they were phrased-differently-same-meaning, so source-suppression is correct.)
- **PART 2b — the field-vs-warning split (the load-bearing distinction):** the per-channel `driftAlert` FIELD stays precise at >5% (the structured per-channel signal an agent reads) — UNCHANGED. The noisy human/agent-attention WARNING now fires only at >30% (a notable, actionable drift), so finance_analytics isn't a wall of 5%-boilerplate. Two different thresholds for two different purposes: the field is the precise signal, the warning is the "look at this" nudge.

## Verification (Rule#0 — architect INDEPENDENT, restarted container)
- **architect 4-step (read FULL):** asOf="" at all macro_signals no-live sites + the schema type tightened to str; the finance reframe-suppresses-dry-powder dedup (one-or-the-other, never both); notable_drift>30 gates the warning, driftAlert>5 the field (unchanged). ✅
- **🔴 INDEPENDENT live teeth (restart-then-call):**
  - PART 1: macro_signals → F&G/BTC.d asOf='2026-06-21' (str), Brent asOf='' (str, was None); **agent `[s.asOf[:10] for s in macro]` → NO crash** (all str). ✅
  - PART 2: finance get_overview → warning count **1** (was ~6); the single warning is the undeployed-stablecoin reframe (the dry-powder line SUPPRESSED — dedup); 0 boilerplate per-channel drift warnings. ✅
- **the field-vs-warning regression test** (test_finance_okx :106): a 5-30% drift → driftAlert FIELD True + NO warning — the distinction holds. ✅
- **Suite:** FULL DEFAULT (`-m 'not slow'` deterministic) = **2252 passed / 6 skipped / 0 failed** forward AND reverse (resolves the 3 #106-WIP failures that were red mid-implementation); never staged backend/data/.

## 3 Gates
- **Gate 1 (API/MCP/agent):** asOf shape-stable (str always, no null-crash); finance warnings deduped + noise-cut (agent-readable, lean); honest (asOf="" not a fake date; the reframe tells the real story); driftAlert field unchanged. ✅
- **Gate 2 (Function):** the distinguishing teeth (asOf-all-string-no-crash / warning-count-drop / dedup-one-stablecoin / field-vs-warning-split); independent live; 0 errors fwd+reverse. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY market/service.py + market/schema.py + finance/service.py + the 3 test files + end doc (NO #105/projects, no data/.env); commit format. ✅

## Assumptions (user-review)
- **asOf="" for a no-live/mock entry** (shape-stable string, NOT None, NOT a fake date). **How to change:** the asOf= values in macro_signals + the schema type.
- **finance drift WARNING threshold = 30% (WARNING_DRIFT_PCT)**; the driftAlert FIELD stays 5% (DRIFT_ALERT_PCT). **Why:** the field is the precise per-channel signal; the warning is the notable-drift attention-grab (not 5%-boilerplate). **How to change:** WARNING_DRIFT_PCT.
- **the undeployed-stablecoin reframe SUPPRESSES the dry-powder line** (dedup: one stablecoin story, not two). **How to change:** the reframe_fires suppression logic.

## Notes
- Cairn #106 LOW — admin-lead dogfood (asOf-null agent-crash + finance warning wall). backend-w3 built BOTH parts; architect committed (§3 sole-committer). **Mid-implementation catch:** while verifying #105's full suite, the architect found 3 RED tests that were #106-WIP (backend changed the CODE but not the contract-encoding tests: test_market_fng asOf-None→"" ×2 + test_finance_shape warning-count ×1) → flagged backend-w3 to update its own tests → backend completed them (+ a new field-vs-warning regression test). The 3 failures were the contract change #106's code makes, NOT a regression — diagnosed + attributed correctly (#106-WIP on disjoint files), so #105 committed independently green while #106 finished. backend's source-dedup (suppress dry-powder when the reframe fires) was BETTER than the dispatch's blanket-dedup suggestion. Committed separately from #105 (projects). Both #105+#106 = the 2 dogfood bugs admin-lead filtered from 7 QA-claims.
