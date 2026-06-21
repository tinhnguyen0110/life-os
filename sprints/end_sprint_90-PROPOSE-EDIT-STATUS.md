# end_sprint_90-PROPOSE-EDIT-STATUS — MCP propose_edit `status` param (Cairn #90 GAP-1)

> Result. The wiki-write MCP `propose_edit` exposed only note_id/title/content/rationale — NO `status` → an agent couldn't promote a note fleeting→developing→evergreen via MCP (8 core VERIFIED nodes stuck at `fleeting`; REST PUT could, MCP couldn't). Fixed: added an optional `status` param that flows through the EXISTING chain (payload → NoteUpdateInput → _apply_update — all already status-aware). Commit `<hash>` `feat(sprint-90-propose-edit-status): MCP propose_edit status param (#90)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live status-flip + bad-enum + back-compat teeth on the container + throwaway cleanup). Cairn #90 GAP-1 (GAP-2 delete already shipped by #94 — NOT touched).

## What shipped (write_server.py + test)
| File | Change |
|---|---|
| `wiki/mcp/write_server.py` (`propose_edit`) | added `status: str \| None = None` param + `if status is not None: payload["status"] = status` + docstring naming the param/enum/back-compat/bad-value→agent-error. ~4 lines. |
| `tests/test_wiki_mcp_write.py` (+4) | status-flips-through-chain · bad-enum→not-applied+unchanged+enum-named-in-msg · omitted→unchanged (back-compat) · REST PUT status parity. |

## Design (LOCKED — ~1-line add, the chain already carries status)
- **the gap was ONLY the MCP surface:** `propose_edit` didn't FORWARD status. The rest of the path already handled it end-to-end — `_enqueue`→`create_proposal`→`proposals_service.py:184 NoteUpdateInput(**payload)` (splats the whole payload) → `NoteUpdateInput.status: Status \| None` (schema.py:180) → `_apply_update` (apply.py:162) `new_status = inp.status if inp.status is not None else existing.status`. So forwarding `status` in the payload makes enum-validate + apply happen for FREE.
- **enum-validate is FREE + agent-readable:** a bad value (`"xyz"`) → the `NoteUpdateInput` Status Literal rejects it at apply → the proposal stays PENDING (not applied) + the result's `warning` field NAMES the valid enum ('fleeting', 'developing' or 'evergreen'). NOT a silent accept, NOT a raw uncaught 500. (The message is the pydantic literal_error — readable + names the valid values; a minor polish would trim the pydantic docs URL, logged as a nit, not a blocker.)
- **back-compat:** omitted status → no "status" key in payload → NoteUpdateInput.status defaults None → _apply_update keeps existing.status (unchanged).
- **REST≡MCP:** REST PUT /wiki/notes/{id} already supported status; this brings the MCP propose_edit to parity (same apply path).
- **GAP-2 (delete) NOT touched** — already shipped by #94 (wiki_delete_note/wiki_restore_note). admin-lead's re-scope: #90 = GAP-1 only.

## Verification (Rule#0 — architect INDEPENDENT, live container teeth + cleanup)
- **architect 4-step (read FULL):** the status param + payload pass-through; the docstring names enum/back-compat/bad-value; the chain (verified proposals_service:184 splats payload, NoteUpdateInput has status, _apply_update applies it). ✅
- **🔴 INDEPENDENT live teeth (container, throwaway note id=79, cleaned up):**
  - `propose_edit(status="evergreen")` → applied=True, note.status flips evergreen (read back). ✅
  - `propose_edit(status="xyz-not-a-status")` → applied=False, note UNCHANGED (still evergreen), `warning` NAMES 'fleeting'/'developing'/'evergreen' (agent-readable, not a silent accept). ✅
  - `propose_edit(title="...")` WITHOUT status → status UNCHANGED (back-compat). ✅
  - throwaway scoped-cleaned-up (soft_delete_note by-id — verify-cleanup-scope-delete-not-blanket). ✅
- **Suite:** `test_wiki_mcp_write.py` 31 passed; the BROAD BE suite (all tests except the 2 mid-correction #99 read-files, which are a SEPARATE in-flight task) = **2038 passed / 6 skipped / 0 failed**; #90 breaks nothing. write_server.py has ZERO reader/backlinks/relevance refs → fully independent of #99.

## 3 Gates
- **Gate 1 (MCP/agent):** the status param self-describes (docstring names enum + back-compat + bad-value→agent-error); bad enum → agent-readable warning naming valid values (NOT silent, NOT raw 500); REST≡MCP parity. ✅
- **Gate 2 (Function):** the distinguishing teeth (flip / bad-enum-unchanged / omitted-unchanged / parity); independent live + throwaway cleanup; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY write_server.py + test_wiki_mcp_write.py + end doc (NO #99 files, no data/.env/frontend/template); commit format. ✅

## Assumptions (user-review)
- **status enum = fleeting | developing | evergreen** (the existing `Status` Literal — reused, not new). **How to change:** the `Status` type in schema.py.
- **bad-enum surfaces as the pydantic literal_error in the result `warning`** (readable + names valid values). **How to change:** wrap it to a {code,message,hint} envelope if a cleaner agent-error is wanted (minor polish — logged as a nit; the current message IS readable + names the enum).
- **GAP-2 (delete) is NOT in #90** — already shipped by #94. **How to change:** n/a (intentional re-scope).

## Notes
- Cairn #90 GAP-1 — admin-lead dogfood (curating life-os memory via wiki-write MCP) hit it: couldn't promote 8 core nodes to evergreen via MCP. backend-w3 built; architect committed (§3 sole-committer). The ~1-line add the architect pre-traced (the chain already carried status — only the MCP surface didn't forward it). Committed from an intermixed tree (#99's 1-exp correction in flight on DIFFERENT files — backlinks.py/read_server.py/test_wiki*; #90 surgically staged write_server.py + test_wiki_mcp_write.py only, ZERO cross-contamination). After this lands, admin-lead self-promotes the 8 core nodes. #99 (relevance) committed separately once its correction passes the both-regimes gate.
