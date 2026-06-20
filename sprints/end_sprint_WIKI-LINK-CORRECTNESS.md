# end_sprint_WIKI-LINK-CORRECTNESS — #19 (MCP≡REST link/backlink) + #26 (link-write) (Cairn #19+#26)

> Result. LANE 1 (parallel to reminders #28). Design LOCKED + re-scoped by live inspection. Commit `<hash>` `feat(sprint-WIKI-LINK-CORRECTNESS)`. Status: ✅ all 3 gates pass.

## Objective (met) — re-scoped by live inspection
The dogfood flagged 3 #19 items; a pre-design live container inspection (architect + team-lead) found 2 were MISREADS, so the sprint is the REAL items only:
1. **backlinks(20)→linked:[] = NOT a bug** — #20 has 0 inbound / 10 outbound (a MOC); `linked` = directed-inbound (correct), the 10 are in `outbound`. The dogfood compared graph's undirected edges vs backlinks' inbound. NO change to the backlinks query (a "match graph's 10" would inject 10 phantom inbound = corruption).
2. **/wiki/backlinks/{id} 404** = wrong URL; the route exists at /wiki/notes/{id}/backlinks (200). No alias.
3. **wiki_tree REST-but-not-MCP** = the ONE real #19 bug → fixed.

## What shipped
| File | Change |
|---|---|
| `modules/wiki/mcp/read_server.py` | **`wiki_tree` MCP tool** — mirrors REST `/wiki/tree`, returns `reader.folder_tree()` DIRECTLY ({name,path,folders,notes}), BYTE-IDENTICAL to REST `data` (NOT wrapped in {tree:...} — the wrapper drift caught in review + fixed). wiki-read TOOLS 11→12. |
| `modules/wiki/mcp/write_server.py` | **propose_link target-resolution STATUS** — resolves the target at write time + surfaces `targetResolved:<id>` / `targetAmbiguous:[...]` / `targetGhost:true+note` (don't block — a ghost can be intentional; just inform). + per-op correlationId (distinct per call). |
| test_wiki_mcp_read/write, test_mcp_http | the wiki_tree MCP≡REST byte-identical test (FULL result vs REST data, not inner-only) + propose_link resolution tests + the don't-corrupt MOC-#20 regression + wiki-read count 11→12. |

## The wiki_tree wrapper drift (caught in review — the byte-identical sub-lesson)
backend's first impl returned `{tree: <folder_tree>}` — the INNER tree was identical to REST but the WRAPPER wasn't. The "byte-identical: TRUE" self-report compared the inner tree, missing the wrapper → a parity violation slipped past. Caught by team-lead's independent FULL-result comparison + architect's confirm. FIX: return the tree dict directly. The test now compares the FULL MCP result vs REST `data` (sort_keys dumps) so a wrapper drift fails RED. (Same class as the #27 tz bug: a self-report that compared the wrong scope.)

## Verification (Rule #0 — 3-way + container)
- **architect 4-step:** confirmed the wiki_tree wrapper drift (REST data keys [folders,name,notes,path] vs MCP [tree]); after the fix, MCP wiki_tree == reader.folder_tree() directly; the backlinks query was NOT touched; propose_link resolution-status is clean.
- **team-lead independent container:** wiki_tree byte-identical `json.dumps(REST.data,sort_keys)==json.dumps(MCP,sort_keys) → TRUE`; #26 propose_link ghost→targetGhost+note, resolved→targetResolved:11, per-op correlationId distinct, no note-12 pollution; don't-corrupt MOC #20 still linked:0/outbound:10; immediacy sync.

## 3 Gates — ALL PASS
- **Gate 1 (API):** wiki_tree MCP == REST (byte-identical, the MCP≡REST drift closed); propose_link surfaces resolution status; backlinks unchanged (correct). ✅
- **Gate 2 (Function):** wiki_tree full-result byte-identical test (catches wrapper drift); propose_link ghost/resolved/ambiguous; per-op correlationId; the don't-corrupt MOC-#20 regression guard (kept directed-inbound, didn't fold outbound into linked); 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; architect + team-lead container; commit format. ✅

## Assumptions (user-review)
- **backlinks `linked` = directed INBOUND (correct, UNCHANGED)** — the dogfood "linked:[] vs graph-10" was a misread (graph is undirected/outbound-inclusive; #20 has 0 inbound). **How to change:** only if the product redefines `linked` (it shouldn't).
- **propose_link surfaces target-resolution status but does NOT block a ghost** (a ghost can be intentional — the agent decides, informed).
- **wiki_tree on the wiki-read server** (where wiki tools live per MCP-DEDUP), byte-identical to REST.

## Notes
- Re-scoped by live inspection — caught 2 dogfood misreads (would've been a near-miss backlinks corruption + a wrong-URL chase). Memory `wiki-write-through-2026-06-21` family.
- LANE 1, separate commit from #28 reminders.
