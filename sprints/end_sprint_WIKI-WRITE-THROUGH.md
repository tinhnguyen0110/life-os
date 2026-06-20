# end_sprint_WIKI-WRITE-THROUGH — agent write-through (noteId-only) + human-override + stale-.tmp hardening (Cairn #25)

> Result. The wiki-batch FOUNDATION (unblocks #19-24,26). A LOCKED trust-boundary REVERSAL (user CHỐT'd, team-lead approved all 4 forks + heads-up'd the user). Commit `<hash>` `fix(sprint-WIKI-WRITE-THROUGH)`. Status: ✅ all 3 gates pass.

## Objective (met)
Wiki is agent-centric; memory is REVERSIBLE → the agent writes THROUGH (note created now), the human TRACES + OVERRIDES (edit/delete), NOT a pre-approval gate. Reverses "AI proposes, human ratifies" → "AI writes through, human traces/overrides" for the wiki. Gate only IRREVERSIBLE actions; wiki notes are reversible → no gate. The dogfood gap (propose_note → pending, note not created, id=proposal-id ≠ note-id → agent confused) is closed.

## What shipped (all 4 forks team-lead-APPROVED + the hardening)
| File | Change |
|---|---|
| `modules/wiki/mcp/write_server.py` | the 6 write tools (`propose_note/edit/link/unlink/merge/moc`) pass `auto_apply_eligible=True`; rationale OPTIONAL; the result LEADS with the real top-level `noteId` (the applied note) — NOT the proposal-id. Docstrings name `noteId` (consumer reads it). |
| `modules/wiki/proposals_service.py` | reuse the W4d chokepoint: create_proposal → auto-accept (decidedBy "agent:auto") when eligible + autonomous → the note lands NOW; accept empty rationale; the 75-proposal queue archived (superseded), pending #75 rejected. |
| `modules/settings/schema.py` | `wikiAgentAutonomous` default flipped → ON (write-through default; OFF = the escape hatch back to proposals-only). |
| `store/md_store.py` | **stale-.tmp hardening:** clear a stale `.<name>.tmp` before the write (fail-soft `unlink(missing_ok=True)` + OSError-log-continue), atomicity preserved (write→fsync→os.replace) — kills the transient Permission-denied fragility. |
| 6 test files (test_md_store, test_settings, test_settings_api, test_wiki_mcp_read/write, test_wiki_proposals) | the M4 gate-test REWORK to the new boundary + the stale-tmp + the toggle-OFF distinguishing. |

## Design decisions (the forks)
1. **Reuse the create_proposal→auto-accept chokepoint** (not a new write path) — single audited route, op-log free.
2. **Keep `wikiAgentAutonomous`, default flipped ON** — reversible escape hatch (OFF → proposals-only).
3. **Archive the 75-proposal queue** (audit history kept), reject pending #75.
4. **Rework the M4 gate tests** to the NEW boundary (write-through + op-log + human-override + verify_citations + the toggle-OFF-still-gates distinguishing — REPLACE not delete).
- **noteId-only (no `appliedNoteId` alias):** the id ships at top-level as `noteId` (clear, get→found:true, DoD met); a duplicate alias = redundancy, not a fix (no-overengineering — reconciled with team-lead).
- **KEEP (pillars surviving the reversal):** verify_citations (anti-fabrication), op-log (every mutation traced/rollback-able), human-override.

## The live-verify arc (why this took multiple rounds — the immune system working)
The structural change worked first-try on disk + unit tests, but container live-verify surfaced (then dissolved) 2 false-blockers + 1 real fragility + 1 real consistency-check:
- **FALSE: "Permission-denied host-path leak"** → TRANSIENT host-venv `.tmp` collision (backend tested in host venv → left artifacts colliding with the container). Clean restart → works. (architect's clean-container reproduction dissolved it.)
- **FALSE: "appliedNoteId still null"** → a top-level-vs-nested parse error: the id ships as top-level `noteId`; reading top-level `appliedNoteId` (absent) saw null. Contract correct.
- **REAL (folded in): stale-.tmp fragility** → the hardening above.
- **Reconciled: noteId-only** (no alias) after the alias was briefly approved-then-dropped.
LESSON: verify on the CONTAINER, not the host venv (host-venv "applied=True" was false); a transient + a parse-error both LOOKED like code blockers — Rule#0 on the real shape/clean-container dissolved both. Cross-check (team-lead flagged, architect refined, team-lead retracted) converged on truth in both directions.

## Verification (Rule #0 — 3-way + container)
- **architect:** 3 Rule#0 refinements (transient / id-IS-noteId / .tmp-hardening); read the .tmp-hardening fn (fail-soft, atomicity preserved); confirmed write-through works on a clean container (notes minted fresh ids, get→found:true), cleaned up all probe notes.
- **team-lead independent container Rule#0:** propose_note (no rationale) → top-level noteId=23, applied=True, accepted; GET /wiki/notes/23 → 200 (write-through persisted); DELETE → 200, GET-after → 404 (human-override + cleanup); live MCP tools/list shows the write-through schema description; rationale not required.
- **tester:** 16/16 PASS, 1712 pytest / 0 fail / 0 errors, +5 tests (write-through + stale-tmp + toggle-OFF distinguishing).

## 3 Gates — ALL PASS
- **Gate 1 (API):** the 6 wiki write tools write-through (real noteId, get→found); error/envelope intact; verify_citations kept. ✅
- **Gate 2 (Function):** 1712 pass/0 fail/0 err, mypy clean; the toggle-OFF distinguishing (OFF→pending/noteId=None — proves a flipped-default, not a deleted gate); stale-tmp test; M4 gate-tests reworked with teeth. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; tester 16/16 + team-lead independent container + architect Rule#0; commit format. ✅

## Assumptions (user-review)
- **Wiki agent-write is WRITE-THROUGH by default** (reverses proposals-only; user CHỐT'd — memory-reversible, gate only irreversible). Control is post-write: op-log + human edit/delete + verify_citations. **How to change:** `wikiAgentAutonomous` OFF → proposals-only.
- **rationale OPTIONAL** on wiki writes. **noteId-only** return (no appliedNoteId alias). **stale-.tmp cleared before write** (defensive). The 75-proposal queue archived, #75 rejected.
- **verify_citations + op-log KEPT** (anti-fabrication + audit pillars survive the reversal).

## Follow-up (logged, NOT this commit — for #3 docs)
- A long-lived MCP CLIENT caches the tool schema at connect — a consumer must reconnect to pick up the new (rationale-optional) schema (team-lead's session still showed rationale-required though the server made it optional). NOT a #25 bug (server is correct). Worth a line in MCP-CONFIG.md (#3).

## Notes
- FOUNDATION of the wiki batch — #19-24,26 build on this write surface.
- Built on the W4d `wikiAgentAutonomous` precedent (memory `wiki-autonomy-toggle-d8-reversed`) — #25 flips its default.
