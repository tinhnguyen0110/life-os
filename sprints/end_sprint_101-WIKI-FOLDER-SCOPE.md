# end_sprint_101-WIKI-FOLDER-SCOPE — wiki_search folder filter, non-blocking (Cairn #101, HIGH scale-pain)

> Result. An agent across 10-15 project-folders calling `wiki_search` drowned in cross-project noise — no folder-scope (wiki_tree had it; search did NOT). Fixed (insight #83 — scope is a FILTER, NOT a block): an OPTIONAL `folder` param threaded through 3 layers (MCP wiki_search → reader.search → fts_search) + REST; `folder=X` → that folder + its subtree; `folder=None` → whole vault (the unchanged default). Commit `<hash>` `feat(sprint-101-wiki-folder-scope): wiki_search folder filter, non-blocking (#101)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live teeth on the container). Cairn #101 — HIGH scale-pain (admin-lead QA-pain-finder).

## What shipped (3-layer thread + 2 tests)
| File | Change |
|---|---|
| `wiki/store/fts.py` (`fts_search`) | `+folder: str\|None=None`; the JOIN already had `wiki_notes n` → add `AND (n.folder = ? OR n.folder LIKE ?)` (folder itself OR subtree `folder/%`) ANDed AFTER the MATCH (FTS5 req); folder is a SQL PARAM (special-char safe). empty/None → no clause (whole vault). |
| `wiki/reader/backlinks.py` (`search`) | `+folder` → pass to fts_search; the #99 1-exp relevance computed over the FILTERED set (unchanged). |
| `wiki/mcp/read_server.py` (`wiki_search`) | `+folder` → pass to reader.search + docstring ("scope to folder+subtree; None=whole vault, a FILTER not a block") + audit the folder. |
| `wiki/router.py` (`/search`) | `+folder` query param → same reader.search (MCP≡REST parity #24). |
| `tests/test_wiki.py` + `test_wiki_mcp_read.py` (+N) | folder=X→X+subtree only · folder=None→whole vault preserved · bad folder→[] · MCP≡REST · subtree match. |

## Design (LOCKED — filter not block, FTS5-correct, parity, relevance-orthogonal)
- **🔴 non-blocking default (the load-bearing #83 property):** `folder=None`/`''` → WHOLE vault (byte-unchanged from pre-#101). The scope FILTERS (narrows when set), it does NOT BLOCK (an agent without a folder still gets everything). Threaded as `folder=None` default at EVERY layer.
- **folder + subtree:** `n.folder = folder OR n.folder LIKE folder + '/%'` → folder='Memory' catches 'Memory' AND 'Memory/Agents/.../sessions'. The exact folder + its descendants.
- **FTS5 correctness:** the MATCH constraint stays FIRST in the WHERE (FTS5 requires it); the folder clause is ANDed AFTER as a parameterized SQL param (FTS-special chars safe — the folder isn't part of the MATCH; the q MATCH is sanitized separately).
- **MCP≡REST parity:** both wiki_search + /wiki/search call the SAME reader.search(q, folder=) → byte-identical by construction (the #24 gate).
- **relevance orthogonal (#99 preserved):** the 1-exp relevance is computed over the FILTERED result set (relevance within the scoped results) — correct, unchanged.
- **wiki_tree** already had folder-scope (the OUT item — verified unchanged).

## Verification (Rule#0 — architect INDEPENDENT, restarted container)
- **architect 4-step (read FULL):** the fts_search SQL (MATCH first, folder ANDed as param, subtree LIKE); the 3-layer thread (folder=None default at each); relevance over the filtered set; parity by shared reader.search. ✅
- **🔴 INDEPENDENT live teeth (restart-then-call):**
  - [1] folder=None → 35 (whole vault); MCP wiki_search(no folder) == reader (35) — **non-blocking default PRESERVED**. ✅
  - [2] folder='Career' → 5 (narrows from 35; all in Career). ✅
  - [3] bad/nonexistent folder → [] honest (no 500). ✅
  - [4] MCP wiki_search(folder=Career) == reader scoped (5) — parity. ✅
  - [5] relevance on scoped: all in [0,1], raw score kept (#99 over the filtered set). ✅
  - [6] subtree: folder='Memory' includes nested 'Memory/Agents/.../sessions'. ✅
- **Suite:** the #101 test files green; FULL DEFAULT (`-m 'not slow'` deterministic) = **2240 passed / 6 skipped / 0 failed** forward AND reverse (2235→2240 = +5 #101 tests; deselected 3↔4 = known env-skip variance, 0-failed invariant holds); never staged backend/data/.

## 3 Gates
- **Gate 1 (MCP/agent):** folder-scope is agent-readable (self-describing docstring: filter-not-block, None=full); honest bad-folder→[]; MCP≡REST parity; non-blocking default. ✅
- **Gate 2 (Function):** the distinguishing teeth (folder=X-narrows / folder=None-full-preserved / bad→[] / parity / subtree / relevance-intact); independent live; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY fts.py + backlinks.py + read_server.py + router.py + 2 tests + end doc (NO #102/tracing, no data/.env); commit format. ✅

## Assumptions (user-review)
- **folder scopes to the folder + its subtree** (`= folder OR LIKE folder/%`). **How to change:** drop the `= folder` for subtree-only, or the LIKE for exact-only.
- **folder=None/'' → whole vault** (non-blocking default — the #83 property). **How to change:** n/a (intentional — scope must never block).
- **relevance computed over the FILTERED set** (relevance within the scoped results, not the whole vault). **How to change:** n/a (correct — "how relevant among what I asked for").

## Notes
- Cairn #101 HIGH — admin-lead's QA-pain-finder (an agent across many project-folders drowns in cross-project search noise). backend-w3 built; architect committed (§3 sole-committer). The architect pre-scouted (the fts_search JOIN already had n.folder → the fix is a WHERE clause + a 3-layer thread) so the dispatch named the exact SQL + the non-blocking-default load-bearing property + its regression test. FTS5 correctness (MATCH-first) confirmed by reading the SQL. Committed separately from #102 (tracing measure-first, in flight). The non-blocking default (folder=None→full vault) is the load-bearing property — proven by the live teeth (MCP==reader at 35 with no folder).
