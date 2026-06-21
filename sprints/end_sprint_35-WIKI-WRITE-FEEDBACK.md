# end_sprint_35-WIKI-WRITE-FEEDBACK — agent learns WHY a human overrode its note (Cairn #35)

> Result. When a HUMAN overrides (edits/deletes) an AGENT-written wiki note, an optional `{reason: enum, text}` is captured into the EXISTING op-log `detail`; a consumer-agent reads it back via `wiki_my_feedback` (MCP) / `GET /wiki/feedback` (REST) to write less junk. Reuses the op-log — NO new store. Commit `<hash>` `feat(sprint-35-wiki-feedback): structured write-feedback {enum+text} on human-override (#35)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT distinguishing-case + live REST≡MCP parity + suite fwd/rev). Batch 2 Lane A (∥ #36).

## What shipped (9 prod wiki files + 5 tests)
| File | Change |
|---|---|
| `wiki/schema.py` | NEW `OverrideReason` Literal (off-scope\|wrong\|duplicate\|low-quality\|outdated\|other) + `OverrideKind` (edit\|delete) + `FeedbackRow` model (self-describing read-back row). |
| `wiki/service/apply.py` | NEW `_override_feedback_detail(note_id, op, original_title)` — the actor-gate: returns the feedback JSON IFF op.actor=='human' AND the note's MOST-RECENT PRIOR op actor != 'human' (agent-written) AND a reason was supplied; else None. Called BEFORE `_commit_note`/delete (so `latest_op_for_note` reads the PRIOR op) in both `_apply_update` + `_apply_delete`; the detail is passed to `append_op`. originalTitle snapshotted from `existing.title` (survives a delete). |
| `wiki/service/crud.py` | `update_note`/`delete_note` gain optional `feedback: dict\|None` → threaded into the Op payload. |
| `wiki/store/oplog.py` | NEW `latest_op_for_note(note_id)` (most-recent op = the actor-gate input) + `feedback_ops(limit)` (cheap `detail LIKE '%"feedback"%'` pre-filter; reader does the authoritative parse). |
| `wiki/reader/oplog.py` | NEW `my_feedback(limit)` — parses each feedback op's detail JSON, validates `reason in _VALID_REASONS`, drops malformed/false-positives silently (honest, never crash/fabricate), returns lean rows `{noteId, reason, text, overriddenAt, originalTitle, overrideKind}` + honest-empty `{feedback:[], count:0}`. |
| `wiki/router.py` | `PUT /notes/{id}` + `DELETE /notes/{id}` gain optional `overrideReason` (Literal Query → bad value 422) + `overrideText`; NEW `GET /wiki/feedback` REST mirror. |
| `wiki/mcp/read_server.py` | NEW `wiki_my_feedback(limit)` MCP tool (in TOOLS + build_server), returns `{**data, found: count>0}` (byte-identical data + the MCP found-wrapper). |
| `wiki/store/__init__.py`, `wiki/reader/__init__.py` | export wiring. |
| tests (5): `test_wiki_write_feedback.py` (NEW, the distinguishing set) + `test_wiki_rest_mcp_parity_gate.py` (pairs wiki_my_feedback ↔ GET /wiki/feedback + adds it to the completeness set) + `test_mcp_read.py` / `test_mcp_http.py` / `test_wiki_mcp_read.py` (catalog/handshake sync). |

## Design (LOCKED — reuse op-log, actor-gate, agent-first read-back)
- **Actor-gate (the "agent learns" point):** feedback captured ONLY when a HUMAN overrides an AGENT-written note (prior-op actor != 'human'). A human overriding their OWN note is NOT feedback to an agent → no row. **Decided:** only the FIRST human override of agent work is the signal (a 2nd human edit's prior op is human → not captured). Logged to Assumptions.
- **honest:** silent override (no reason) → no feedback detail. Malformed/false-positive LIKE match → dropped in the reader. Empty → `{feedback:[], count:0}`. Never fabricated.
- **agent-first read-back:** lean self-describing rows; REST≡MCP byte-identical (modulo the MCP `found` wrapper) — enforced by the parity GATE (paired, not exempted).
- **NO new store:** reuses `wiki_op_log.detail` (TEXT, JSON). originalTitle snapshotted to survive deletes.

## Verification (Rule#0 — architect INDEPENDENT, not just backend's report)
- **architect 4-step (read FULL functions):** `_override_feedback_detail` actor-gate correct (op.actor=='human' + prior-op-actor!='human' + reason-present, captured BEFORE the commit so latest_op reads the PRIOR op) ✅; `my_feedback` honest (validates reason, drops malformed, honest-empty) ✅; router Literal-Query → 422 on bad reason ✅; MCP tool registered + found-wrapper ✅.
- **architect INDEPENDENT distinguishing-case (own throwaway, not backend's test):** agent-note override → captured (+1, exact row: noteId/reason/originalTitle="ArchAgent"/overrideKind="edit") ✅; human-note override WITH the same feedback → NOT captured (count unchanged) ✅ → the actor-gate is REAL, not a catch-all. (Throwaway cleaned up.)
- **parity gate:** wiki_my_feedback PAIRED with GET /wiki/feedback (n_strip_found normalizer) + in the completeness set (the gate fails RED if a new tool is unpaired). **LIVE HTTP confirm:** MCP `{count:0,feedback:[],found:false}` vs REST `{count:0,feedback:[]}` → byte-identical modulo found (verified on the live :8686 MCP mount, not import-cache).
- **6 pending proposals (90-93,127,128):** ALL still `pending` (by-id GET) — user-gate untouched. ✅
- **Suite (independent re-run):** the new feedback file 36-test block green; DEFAULT (`-m 'not slow'`) deterministic = **2121 passed / 6 skipped / 3 deselected / 0 failed / 0 errors**, REVERSE-order = **2121 / 0 failed** (identical → no isolation leak, coheres #73/#79). NOTE: passed-count varies ±10 across `pytest-randomly` seeds (23 runtime-conditional env-skips in the suite) — the INVARIANT is 0-failed/0-error + forward==reverse, which holds; backend reported 2111 (a different seed's conditional-skip outcome, not a discrepancy).

## 3 Gates
- **Gate 1 (API/MCP):** Literal-validated overrideReason (bad→422); GET /wiki/feedback + wiki_my_feedback agent-readable; REST≡MCP parity gated; response `{success,data}` / MCP `{...,found}`. ✅
- **Gate 2 (Function):** distinguishing tests (agent-captures / human-NOT-captures count==0 / first-override-only / silent / honest-empty / text-optional / REST-put); independent re-run; honest read-back; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent distinguishing + live parity; counts 2095→2121; staged set EXACTLY the 9 prod + 5 test wiki files (no data/.env/template); commit format. ✅

## Assumptions (user-review)
- **Override-feedback gate = FIRST human override of agent work** (prior-op actor != 'human'). A human overriding their own note, or a 2nd human edit (whose prior op is human), is NOT captured. **Why:** the first human override IS the learning signal; later human edits aren't feedback TO an agent. **How to change:** `_override_feedback_detail` (use last-AGENT-op-anywhere-in-history instead of immediate-prior-op).
- **enum = off-scope|wrong|duplicate|low-quality|outdated|other** (closed Literal). **How to change:** `OverrideReason` in schema.py + `_VALID_REASONS` in reader/oplog.py (keep them in sync — NOTE: a single source via `get_args(OverrideReason)` would be DRY-er; both currently agree).
- **Input path = optional query params on PUT/DELETE** (overrideReason/overrideText), feedback OPTIONAL. **How to change:** the router signatures.

## Notes
- Cairn #35 Batch 2 Lane A (∥ with #36). backend-w3 built; architect 4-step + committed (§3 sole-committer, serial — #36 commits AFTER this lands). Reuses op-log (no new store), agent-first read-back (REST≡MCP), the 6 user-gate proposals untouched. Low-risk nit (logged): `_VALID_REASONS` duplicates the `OverrideReason` Literal — both agree now; a `get_args` single-source would be DRY-er (future cleanup, not a defect). Next: #36 (daily_brief wiki-context) → then #78 last (risk-assess).
