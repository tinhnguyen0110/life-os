# end_sprint_A2-HARD-DELETE-DOC — document the hard delete_note (Cairn #104, audit A2, DOC-ONLY)

> Result. The audit (A2) flagged the hard `crud.delete_note` as "dead/backdoor". Kickoff (Rule#0) corrected that: it's UNREACHABLE from any wired surface (MCP wiki_delete_note=soft, REST DELETE=soft, #94) BUT not dead — it's the deliberate HUMAN-OVERRIDE hard-delete (agents soft-only), asserted by `test_human_can_override_agent_note`. team-lead decided **(c) leave + document** (removing it discards intentional design; a human-purge endpoint is unwanted overengineering for a single-user app). Shipped: a clear docstring + export comment labeling it. ZERO behavior change. Commit `<hash>` `docs(sprint-A2-hard-delete-doc): label hard delete_note human-override-only, surface-less by design (#104)`. Status: ✅ verified (backend-w3; architect 4-step confirmed doc-only + zero behavior change). Cairn #104 — audit A2 (downgraded MED→LOW doc-clarity).

## What shipped (doc-only, 2 files)
| File | Change |
|---|---|
| `modules/wiki/service/crud.py` (`delete_note` docstring) | clarified: "HARD delete — IRREVERSIBLE … Human-override control ONLY (agents soft #94); NO wired surface reaches this today (REST DELETE + MCP wiki_delete_note both soft); a future human/admin hard-purge would route here; merge uses the store-level hard delete. NOT dead code — the deliberate human-retains-hard vs agent-soft asymmetry, asserted by test_human_can_override_agent_note." |
| `modules/wiki/service/__init__.py` (export) | a 2-line comment above the `delete_note` export pointing to the docstring. |

## Design (LOCKED — document the intent, don't destroy it)
- **(c) leave + document, NOT remove:** the hard delete_note encodes a DELIBERATE asymmetry (humans retain irreversible hard-delete; agents get only soft-delete #94). Removing it would discard that intent on agent judgment — the honest-mirror caution applied to design. Building a human-purge endpoint = unwanted net-new feature (single-user, soft is enough; no-overengineering §2). So: just make the intent + the surface-less-today status explicit in the docstring → removes the "is this dead?/a backdoor?" noise with zero behavior change.
- **ZERO behavior change:** only the docstring text + an export comment changed. `_apply_delete`, the "delete" op-kind, `test_human_can_override_agent_note`, the export itself — all UNCHANGED.

## Verification (Rule#0 — architect 4-step, doc-only)
- **architect 4-step (read FULL diff):** the diff is PURELY docstring (crud.py delete_note) + a comment (service/__init__.py export). No signature, no code line, no behavior. ✅
- **zero-behavior-change gate:** wiki suite (test_wiki + wiki_mcp_write + wiki_soft_delete + wiki_reconcile) = 215 passed; import smoke (`from modules.wiki.service import delete_note, soft_delete_note, create_note`) OK — proves the docstring/comment edit didn't break the module. ✅ (a doc-only change can't fail the full suite — the targeted wiki-area run + import smoke is the proportionate gate; never staged backend/data/.)

## 3 Gates
- **Gate 1 (n/a — no API/MCP behavior change):** the hard path's behavior is unchanged; the doc just clarifies it. ✅
- **Gate 2 (Function):** zero behavior change confirmed (doc-only diff + wiki-area suite 215 passed + import smoke). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step (doc-only diff verified); staged EXACTLY crud.py + __init__.py + end doc (NO A1 files, no data/.env/frontend); commit format `docs(sprint-A2-...)`. ✅

## Assumptions (user-review)
- **hard delete_note = human-override ONLY, surface-less today** — documented, NOT removed, NOT given a new endpoint. **Why:** preserves the deliberate asymmetry; a human-purge endpoint is unwanted now (single-user, soft suffices). **How to change:** if the user later wants a human hard-purge, add a gated endpoint that routes to this fn (the doc already names it as the intended route).

## Notes
- Cairn #104 — audit A2. The arc: my audit over-stated it ("dead backdoor") → kickoff Rule#0 corrected it (unreachable but intentional, a test asserts the intent) → I surfaced 3 options to team-lead instead of dispatching a blind remove → team-lead decided (c) document. The diagnose-first discipline applied to my OWN finding prevented a wasted removal that would've broken a test + discarded design intent. backend-w3 wrote the doc; architect committed (§3 sole-committer). Doc-only — committed separately from #103/A1 (different files). Downgraded MED-cleanup → LOW doc-clarity (the right mismatch for an unreachable item).
