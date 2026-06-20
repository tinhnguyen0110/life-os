# Sprint WIKI-LINK-CORRECTNESS — #19 (MCP≡REST link/backlink) + #26 (link-write correctness)

> Created 2026-06-21 by architect. Grouped #19+#26 (team-lead-approved — shared link/backlink surface). **STATUS: design LOCKED (re-scope corroborated by team-lead's independent container Rule#0 — all 3 calls confirmed) + HELD undispatched per the milestone pause; dispatches on the user's priority go.** Live-grounded: a pre-design container inspection RE-SCOPED #19 substantially (2 of its 3 dogfood claims were misreads — backlinks-query non-fix dropped, /backlinks-404 was a wrong URL; only wiki_tree-MCP-gap is a real #19 bug).

## ⚠️ Live inspection RE-SCOPED #19 (the value of verify-before-design)
Before designing, I inspected the REAL state on the container. The dogfood evidence for #19 was 3 claims; only ONE is a real bug:

1. **"backlinks(20) → linked:[] empty while wiki_graph(20) shows 10 edges" → NOT A BUG (dogfood misread).**
   - Live: `links_to(20)` (inbound, others→20) = **0**; `links_from(20)` (outbound, 20→others) = **10** (notes 10-19 — #20 is a MOC/index). `backlinks(20)` = `linked:0, outbound:10, unlinked:0`. ego_graph(20) = 38 edges (both-direction BFS over #20's neighbors).
   - So `linked:[]` is CORRECT — there are genuinely 0 inbound links to #20. The 10 are #20's OUTbound (correctly in `outbound`). The dogfood compared graph's undirected/outbound-inclusive edges against backlinks' directed-INbound-only.
   - **A naive "fix backlinks to return 2-way matching graph's 10" would CORRUPT it** (claim 10 phantom inbound links that don't exist). DO NOT do that. The backlinks query is CORRECT.

2. **"/wiki/backlinks/{id} → 404" → endpoint EXISTS at a different path.**
   - Live: `GET /wiki/backlinks/20` → 404, but `GET /wiki/notes/20/backlinks` → **200** (the real route). The dogfood tested the wrong URL. Not a missing endpoint. (Optional: add `/wiki/backlinks/{id}` as an alias for ergonomics — low value; the canonical route works.)

3. **"wiki_tree REST-but-not-MCP" → REAL (the one solid #19 bug).**
   - Live: `wiki_tree` is NOT in the MCP read-server TOOLS (grep 0); `/wiki/tree` REST → 200. Genuine MCP≡REST drift → expose `wiki_tree` to the wiki MCP read-server.

## #26 items (link WRITE correctness — verified real)
1. **propose_link does NOT validate the target exists (REAL).** `write_server.propose_link` (L143) passes `target` straight to the payload; `service/links.py parse_wikilinks` resolves `[[target]]` to an id OR a silent GHOST (unresolved). So a link to a non-existent/mistyped title becomes a ghost with NO signal to the agent (the dogfood "ghost-link without knowing"). FIX: at write time, resolve the target → report `{resolved: id}` / `{ambiguous: [matches]}` / `{notFound}` so the agent KNOWS (don't block — a ghost can be intentional — but SURFACE the resolution status).
2. **correlationId duplicated across independent ops (verify + fix if real).** Dogfood: 2 separate proposals shared a correlationId → trace confusion. Verify the correlationId source; make it per-operation (or document the grouping semantics).
3. **id-confusing → already solved by #25** (write-through returns the real note-id). Drop from #26.

## team-lead's backlink-immediacy lead (the JOIN test — verify, may be real)
propose_link(A→B) → IMMEDIATE GET backlinks(B) → A present? For a single-user in-process store the backlink index should be SYNCHRONOUS (no eventual-consistency gap). tester observed "accepted but backlink not immediately in /backlinks." VERIFY: is the link-edge index (links_to/replace_links) updated synchronously on write-through apply, or is there a reindex lag? If lagged → fix to sync. This is the round-trip that spans #26-write + #19-read — the reason to group them.

## Final scope (re-scoped by the live inspection)
- **#19:** (a) expose `wiki_tree` to MCP [REAL]; (b) OPTIONAL `/wiki/backlinks/{id}` alias [low value — canonical /wiki/notes/{id}/backlinks works]; (c) backlinks-query = NO CHANGE (correct — document the directed-inbound semantic so it's not re-flagged). 
- **#26:** (a) propose_link target-resolution status [REAL]; (b) correlationId per-op [verify]; (c) id — done by #25.
- **Cross:** the backlink-immediacy round-trip [verify sync; fix if lagged].
- Net: this sprint is SMALLER than the raw dogfood suggested — 1 real MCP gap + 1 real write-validation + 2 verify-then-maybe-fix. NOT a 5-alarm link rewrite. (no-overengineering: don't "fix" the non-bugs.)

## Tasks (when dispatched — AFTER the user go)
- **T1 (backend):** expose wiki_tree to MCP (mirror /wiki/tree, like the other read tools); propose_link target-resolution status; correlationId per-op (if confirmed); verify+fix backlink-immediacy (sync index). Tests.
- **T2 (tester):** MCP wiki_tree == REST /wiki/tree; propose_link to a non-existent title → reports notFound/ghost-status (not silent); the immediacy round-trip (propose_link A→B → immediate backlinks(B) has A); the backlinks directed-inbound semantic (a note with real inbound shows them; a MOC like #20 shows outbound not linked — the distinguishing that proves we didn't wrongly fold outbound into linked).

## HARD GATE (distinguishing — incl. the don't-introduce-a-bug guards)
- wiki_tree via MCP == /wiki/tree REST (byte-identical).
- propose_link(non-existent title) → resolution status surfaced (notFound/ambiguous), NOT a silent ghost.
- propose_link(A→B) → immediate backlinks(B) includes A (sync, no lag).
- **backlinks DISTINGUISHING (the don't-corrupt guard):** a note WITH real inbound links → linked shows them; a MOC (#20, 0 inbound + 10 outbound) → linked:[] + outbound:10 (NOT linked:10). Proves we kept the correct directed-inbound semantic + didn't fold outbound into linked.
- pytest green, mypy clean.

## Assumptions (user-review)
- **backlinks `linked` = directed INBOUND only (correct, unchanged)** — the dogfood "linked:[] wrong vs graph-10" was a misread (graph is undirected/outbound-inclusive; #20 has 0 inbound, 10 outbound). NOT changed. **How to change:** only if the product wants `linked` to mean something other than "notes that link TO this one" (it shouldn't).
- **/wiki/notes/{id}/backlinks is the canonical REST route** (the dogfood's /wiki/backlinks/{id} 404 was the wrong URL). Optional alias, low value.
- **propose_link surfaces target-resolution status** (resolved/ambiguous/notFound) but does NOT block a ghost (a ghost can be intentional — the agent decides, informed).

## Notes
- DESIGN-ONLY until the user weighs in (milestone pause). The live inspection prevented 2 near-miss "fixes" of non-bugs (the backlinks-query corruption + the wrong-URL 404 chase) — verify-before-design payoff, same as the #25/#27 arcs.
- Grouped because #26-write + #19-read + the immediacy round-trip are one link/backlink surface (shared wiki service/reader files).
