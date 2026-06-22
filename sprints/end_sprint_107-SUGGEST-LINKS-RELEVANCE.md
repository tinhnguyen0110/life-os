# end_sprint_107-SUGGEST-LINKS-RELEVANCE — wiki_suggest_links 1-exp relevance (Cairn #107, #99 follow-up)

> Result. #99 fixed `wiki_search`'s relevance (raw bm25 → 1-exp 0..1) but MISSED `wiki_suggest_links` — it still surfaced the RAW negative bm25 (-27..-7) as `relevance`, which an agent can't read. Same FTS, same disease, the path #99 didn't cover. Fixed (1-line core): `suggest_links` now surfaces the #99 1-exp `relevance` (0..1) that `backlinks.search` ALREADY computes — reused, not recomputed — + carries raw `score` for parity-with-search. Commit `<hash>` `fix(sprint-107-suggest-links-relevance): 1-exp relevance, #99 follow-up (#107)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live teeth — relevance 0..1, order best-first). Cairn #107 LOW — #99 follow-up (the missed path).

## What shipped (suggest.py + surfaces + test)
| File | Change |
|---|---|
| `wiki/reader/suggest.py` (`suggest_links`) | line 62: `{id,title,relevance:hit["score"]}` → `{id,title,score:hit["score"],relevance:hit["relevance"]}` — surface the #99 1-exp `relevance` (0..1, the value `backlinks.search` already computes; REUSED not recomputed) + carry raw `score` for transparency/parity-with-search. Module + fn docstrings updated to the new shape + the #107 rationale. |
| `wiki/mcp/read_server.py` + `wiki/router.py` (`wiki_suggest_links` / `/suggested-links` docstrings) | shape note `[{id,title,relevance}]` → `[{id,title,score,relevance}]` + "relevance = the #99 1-exp 0..1, score = raw bm25". |
| `tests/test_wiki_suggest_links.py` | the contract update: relevance ∈ [0,1) (NOT negative) + raw score kept; order best-first preserved (1-exp monotonic). |

## Design (LOCKED — reuse the #99 transform, parity-with-search, the missed-path fix)
- **the #99 follow-up:** #99 made `backlinks.search` return BOTH `score` (raw bm25) AND `relevance` (1-exp 0..1) per hit. `suggest_links` calls `backlinks.search` (`_fts`) but was reading `hit["score"]` (raw negative) AS its `relevance`. The fix: read `hit["relevance"]` (the 1-exp ALREADY computed). REUSE, zero dup — the transform lives in ONE place (backlinks.search).
- **parity-with-search (the shape choice):** also carry raw `score` → suggest's shape `[{id,title,score,relevance}]` mirrors search's `{…,score,relevance}`. Consistent agent-facing shape across the two FTS surfaces + transparency (the agent can audit the 1-exp from the raw).
- **order unchanged:** 1-exp is monotonic in score; backlinks.search returns best-first; suggest preserves it (exclude-self/already-linked + top-limit cap unchanged).
- **honest 0..1:** an agent reading suggest_links relevance now gets the SAME meaningful 0..1 magnitude as search (higher=stronger), not the unreadable raw negative. The honest-mirror/agent-first 1-exp rationale (absolute per-row magnitude) applies identically.

## Verification (Rule#0 — architect INDEPENDENT, restarted container)
- **architect 4-step (read FULL):** suggest.py reuses `hit["relevance"]` (not recompute) + carries `score`; all 3 surface docstrings updated to the new shape; no FE consumer asserts the old 3-field shape (grep clean → +score doesn't break FE). ✅
- **🔴 INDEPENDENT live teeth (restart-then-call):** suggest_links(10) → 5 results, relevance 0.9999→0.7736 (∈ [0,1), NONE negative — was -27..-7); raw score kept (≤0); shape {id,title,score,relevance}; order best-first (relevance descending). ✅
- **Suite:** test_wiki_suggest_links green; FULL DEFAULT (`-m 'not slow'` deterministic) = **2252 passed / 6 skipped / 0 failed** forward AND reverse; never staged backend/data/.

## 3 Gates
- **Gate 1 (MCP/agent):** relevance is agent-readable 0..1 (not raw negative); raw score kept (transparency); shape mirrors search (parity); MCP≡REST (both via reader.suggest_links). ✅
- **Gate 2 (Function):** the distinguishing teeth (relevance 0..1 not-negative / order-best-first / score-kept / reused-not-recomputed); independent live; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY suggest.py + read_server.py + router.py + test_wiki_suggest_links.py + end doc (NO #108/FE, no data/.env); commit format. ✅

## Assumptions (user-review)
- **suggest_links relevance = the #99 1-exp 0..1** (reused from backlinks.search, not recomputed). **How to change:** it follows whatever backlinks.search's relevance is (one source).
- **raw `score` carried too** (parity-with-search + transparency). **How to change:** drop `score` from the suggest output if a leaner shape is wanted (search keeps it).

## Notes
- Cairn #107 LOW — admin-lead dogfood: #99 fixed search's relevance but the SAME-FTS suggest_links path still surfaced raw negative bm25. The architect pre-scouted it to the exact 1-line core (use the already-computed hit["relevance"]) before dispatch. backend chose the parity option (add raw score → shape mirrors search) — the recommended one. REUSE not recompute (the transform stays in backlinks.search, one source — can't drift from search). Committed separately from #108 (FE Explorer-refresh, landed 4308b32) — surgical be-wiki stage, no FE leak. The #99-follow-up gap closed: both wiki FTS surfaces (search + suggest) now give an agent the same readable 0..1 relevance.
