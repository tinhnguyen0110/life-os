# end_sprint_99-WIKI-SEARCH-RELEVANCE — wiki_search 1-exp absolute relevance (Cairn #99, honest-mirror)

> Result. `wiki_search`/`/wiki/search` returned raw FTS5 bm25 `score` (negative, near-flat for a common term: -2e-6→-9e-7, spread ~1e-6) → an agent couldn't tell the top hit from the bottom; "RANKED, score so the agent sees WHY" was a near-meaningless number. Fixed: add a `relevance` (0..1, higher=stronger) = **`1 - exp(score)`** — an ABSOLUTE per-result magnitude. Raw `score` KEPT (transparency). Commit `<hash>` `fix(sprint-99-wiki-search-relevance): 1-exp absolute relevance, raw score kept (#99)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live BOTH-regimes gate — the gate that BLOCKED the first min-max attempt). Cairn #99 — tool-hardening lane 3.

## What shipped (reader.search + the MCP tool docstring + tests)
| File | Change |
|---|---|
| `wiki/reader/backlinks.py` (`search`) | per-result `relevance = round(1 - math.exp(r["score"]), 4)` (score≤0 → ∈[0,1)); PER-ROW (no set-span/div0/branch); raw `score` kept; docstring = ABSOLUTE 1-exp (not relative). |
| `wiki/mcp/read_server.py` (`wiki_search` docstring) | self-describes `relevance` as ABSOLUTE per-result magnitude (1-exp), "flat/all-weak → all-LOW, NOT relative-within-the-set". Consistent with backlinks.py. |
| `tests/test_wiki_mcp_read.py` + `test_wiki.py` (+5 / updates) | specific→top>tail distinguishable + monotonic order · weak-single→<0.5 (NOT forced-1.0 — the min-max-lie) · flat-all-weak→max<0.9 + spread<0.5 (no manufactured spread) · raw score kept · REST relevance present. |

## Design (LOCKED — 1-exp ABSOLUTE, the honest-mirror correction)
- **1-exp per-row absolute magnitude (CORRECTED from min-max):** `relevance = 1 - exp(bm25 score)`. score≤0 → exp∈(0,1] → relevance∈[0,1). A strong match (score=-9) → ≈0.9999; a weak match (score≈0) → ≈0.0. PER-ROW: no min/max/span over the set → no div-by-zero, no fragile empty branch, no "forced-1.0" lie. Order UNCHANGED (1-exp monotonic in score → still best-first). Raw `score` KEPT for transparency.
- **🔴 the honest-mirror property (the load-bearing reason for the correction):** a flat/all-weak result set (e.g. the common term `q="e"`, all scores ≈0) → ALL relevance ≈0.0 = honest "all weak, no real signal to rank on" — NOT a manufactured 1→0 spread. A specific query → a real spread (top high, tail lower). The magnitude is ABSOLUTE (how relevant IS this), not relative-within-the-set.
- **the rejected first attempt (min-max) + WHY:** the initial build used min-max `(worst-score)/span`. It passed the unit tests (a packed-vs-mention fixture has a real spread) but FAILED the architect's independent live BOTH-regimes gate: for the real flat `q="e"` (microscopic ~1e-6 span), min-max STRETCHED that to a full relevance `1.0,0.998,…,0.0` — a FABRICATED distinction reading "top far more relevant than bottom" when bm25 says they're all ~equally weak. That's an honest-mirror breach (present a near-nothing as a real signal). team-lead had named "flat→all ≈low, NOT a faked spread" as load-bearing → min-max was BLOCKED → swapped to 1-exp (decide-and-log; user re-notified of the corrected algorithm).
- **REST≡MCP parity (auto):** both `/wiki/search` and `wiki_search` call the same `reader.search` → ONE fix → both surfaces; the parity gate holds automatically.

## Verification (Rule#0 — architect INDEPENDENT, the BOTH-regimes gate)
- **architect 4-step (read FULL):** the per-row 1-exp (no span/branch); the docstrings (backlinks.py + read_server.py) BOTH say ABSOLUTE 1-exp, NOT relative-within-set (no self-describe contradiction — the half-applied mid-state was caught + completed); raw score kept; order unchanged. ✅
- **🔴 INDEPENDENT live BOTH-regimes gate (the gate that FAILED min-max — re-run on the container):**
  - A specific `q="investment framework strategy"` → relevance **0.9999 → 0.5042** (REAL spread, top distinguishable), descending best-first, order unchanged, raw score kept. ✅
  - B flat `q="e"` (THE dogfood bug query) → relevance **ALL 0.0** (honest "all weak", max<0.9, spread 0.0 — NO manufactured spread). ✅✅ the load-bearing honest property min-max breached.
- **the min-max-lie regression test:** a lone WEAK single match → relevance <0.5 (1-exp reports its true low magnitude; min-max forced it to 1.0). ✅
- **Suite:** the #99 files 188 passed; FULL DEFAULT (`-m 'not slow'` deterministic, `-p no:randomly`) = **2226 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse; never staged backend/data/.

## 3 Gates
- **Gate 1 (MCP/agent):** relevance is agent-readable (0..1 higher=stronger, self-describing docstring) + HONEST (flat→all-low, no fake spread) + raw score kept (transparency) + REST≡MCP parity. ✅
- **Gate 2 (Function):** the distinguishing teeth (specific-spread / weak-single-not-forced / flat-no-manufactured-spread / order-unchanged / raw-kept); INDEPENDENT live both-regimes; 0 errors fwd+reverse. ✅
- **Gate 3 (Sprint):** end-doc (incl. the min-max→1-exp correction arc); architect 4-step + independent live; staged EXACTLY backlinks.py + read_server.py + test_wiki_mcp_read.py + test_wiki.py + end doc (NO #90 write_server.py, no data/.env/frontend); commit format. ✅

## Assumptions (user-review)
- **relevance = 1 - exp(bm25 score)** (ABSOLUTE per-result magnitude, 0..1, higher=stronger). **Why:** honest in both regimes — a flat/all-weak query is all-low (no fake ranking); a strong match is high. **How to change:** the relevance expr in reader.search (e.g. a saturating `-s/(-s+k)` if a gentler curve is wanted).
- **CORRECTED from min-max** (the first attempt) — min-max manufactured a spread from microscopic flat-data, an honest-mirror breach caught by the live both-regimes gate + BLOCKED before commit. **How to change:** n/a (the correction is the point).
- **raw `score` kept alongside relevance** (transparency — the agent can audit the transform). **How to change:** drop `score` if the raw bm25 is deemed noise (NOT recommended — it's the transparency anchor).

## Notes
- Cairn #99 — admin-lead dogfood: wiki_search score near-flat → ranking meaningless to an agent. backend-w3 built; architect committed (§3 sole-committer). **The arc:** spec'd min-max → backend built it (green tests) → architect's INDEPENDENT live both-regimes gate caught it MANUFACTURES a spread on flat data (honest-mirror breach) → BLOCKED commit → team-lead approved swap to 1-exp → backend re-built → gate PASSES (flat→all-0.0, specific→real-spread). The unit-tests-green-but-dishonest case is why the architect's live both-regimes verify on REAL data (not the spread-built fixture) is load-bearing — logged to memory (`min-max-manufactures-spread-not-honest`). Committed separately from #90 (different files; surgical stage). #99+#90 = the agent-first tool-hardening batch; #98+hash-validate were cairn (dropped). Next: the dogfood round (gated on #99+#90 both landed).
