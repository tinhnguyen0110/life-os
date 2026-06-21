# end_sprint_MCP-PROPOSE-FOLDER — propose_note/propose_moc gain folder (Cairn #80)

> Result. The MCP `propose_note`/`propose_moc` tools silently DROPPED a `folder` arg → a note proposed via MCP always landed at root → repo_memory (folder=="Repos") couldn't find an MCP-proposed repo-memory note. Added `folder: str|None=None` → threaded into the payload → the generic-MCP-tool note-create round-trip honors the folder. Commit `<hash>` `fix(sprint-MCP-PROPOSE-FOLDER #80)`. Status: ✅ all gates pass. backend-w3 BUILT; architect 4-step + committed (§3). The Errno-13 the task ORIGINALLY named is closed-as-not-reproducible (a harness artifact, NOT the real surface — see below); #80 was re-scoped to the real folder-drop bug.

## The re-scope (4th Rule#0 catch this stretch — implementer-corrects-architect)
The dispatch's premise ("MCP wiki-write auto-apply fails Errno-13 for a non-root caller → fix the writer-identity") was WRONG. backend diagnosed-FIRST (per the dispatch) + flagged; architect verified BOTH ways:
- The in-container MCP write-server (`/mcp/wiki-write/mcp`) runs as ROOT (the container is uid=0) → it CAN write the root:root data dir → auto-apply WORKS live (architect's own curl: propose_note → {noteId, applied:true, warning:null}; no Errno-13).
- The Errno-13 came from the HOST-harness `mcp__lifeos-wiki-write__*` tool (runs as watercry, OUTSIDE the container) — a harness-vs-container identity artifact, NOT a server bug. → Errno-13 CLOSED not-reproducible, NO compose/perm/user change (avoided risky container-user churn for a phantom).
- The REAL bug: `propose_note` (write_server.py) had no `folder` param → folder silently dropped → MCP-proposed notes land at root. THAT was the generic-tool gap.

## What shipped (2 files — folder-param only, NO compose/perm/count change)
| File | Change |
|---|---|
| `modules/wiki/mcp/write_server.py` | `propose_note` + `propose_moc` gain `folder: str|None=None` → `if folder: payload["folder"]=folder` → NoteCreateInput honors it (the apply-handler already supported folder; only the MCP signature dropped it). folder=None/'' → root (back-compat — existing callers unaffected). |
| `tests/test_wiki_mcp_write.py` (+4) | the folder distinguishing set (RED-proven). |

## Design (LOCKED — additive, back-compat, matches REST)
- folder is an OPTIONAL param (default None → root) → existing propose_note/propose_moc calls are unaffected; an agent that WANTS a folder (e.g. "Repos" for repo-memory) now can. Matches the REST create (which already took folder) → MCP≡REST folder parity. NO new tool → NO read-count change (stays 46).

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full):** the folder thread (propose_note:172/179 + propose_moc:229/234, `if folder:` only) ✅; back-compat (None/''→root, documented) ✅; NO count-change (param-add, count stays 46) ✅; 2-file surface (no compose/core/schema) ✅; the Errno-13 re-scope verified independently (in-container MCP write auto-lands via my own curl — the host-harness was the artifact) ✅.
- **backend-w3 evidence:** 4 RED-proven tests (folder="Repos"→lands folder=="Repos" [verify the STORED note]; omitted→root back-compat; propose_moc folder + noteType=moc; the #64-P2 round-trip via MCP). RED proof: the folder tests FAIL without the thread. mypy clean. DEFAULT 2071/0 (= 2067 + 4). LIVE on :8686 (restarted for the wiki-write MCP): propose_note(folder="Repos") → landed folder=="Repos" (was '' before) → repo_memory("p80fix") found:true → **the #64-P2 round-trip works END-TO-END via MCP** (the dropped-folder gap closed). SCOPED cleanup (by-name + md removed). backend caught + fixed a mid-function test mis-insert via run-the-red.
- **architect re-run:** wiki_mcp_write + code_insight 45/0.

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** propose_note/propose_moc honor folder (MCP≡REST folder parity); back-compat None→root; no new tool/count-change. ✅
- **Gate 2 (Function):** the folder distinguishing (RED-proven) + the #64-P2-via-MCP round-trip + back-compat; DEFAULT 2071/0; mypy clean. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + backend RED-proof + live round-trip; the Errno-13 re-scope (not-repro, no churn) reconciled; 2-file surgical stage; commit format. ✅

## Assumptions (user-review)
- MCP propose_note/propose_moc accept an OPTIONAL `folder` (None→root, back-compat) → an agent can file a note in a folder (esp Repos/ for repo-memory). Matches REST. **How to change:** the param.
- Errno-13 (the original #80 title) = a host-harness-vs-container identity artifact (the real in-container MCP write-server is root + works) — closed not-reproducible, NO perm/compose change. The 6 pending proposals (Errno-13-window orphans from the host-harness) = human-accept (the #60 review-gate, unchanged).

## Notes
- Cairn #80 (re-titled "MCP propose_note DROPS folder param"; the Errno-13 closed not-repro). The 4th Rule#0 catch this stretch (migration-order #75-BE, #77-premise, #73-reorder-attribution, #80-premise) — diagnose-first caught the bad premise BEFORE compose churn. backend BUILT; architect committed (§3). The generic-MCP-tool note-folder round-trip now works (completes the agent-can-file-a-foldered-note path; #64-P2's own propose_memory was already folder-correct — this fixes the GENERIC propose_note tool). Next: #79 → #78 (test-infra) → #64-P3 (FE). The standing roadmap's feature work is delivered; these are the tail.
