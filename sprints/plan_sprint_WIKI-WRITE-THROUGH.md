# Sprint WIKI-WRITE-THROUGH — agent write-through (drop the proposal-gate default) (Cairn #25)

> Created 2026-06-21 by architect. The FOUNDATION of the wiki batch (BLOCKS #19-23,26). A LOCKED trust-boundary REVERSAL — user CHỐT'd; team-lead approved all 4 forks + is heads-up'ing the user. Design surfaced + sanity-checked pre-dispatch.

## The change (user CHỐT 2026-06-20)
Wiki is agent-centric: memory is REVERSIBLE → the agent writes THROUGH (note created now), the human TRACES + OVERRIDES (edit/delete), NOT a pre-approval gate. Reverses "AI proposes, human ratifies" → "AI writes through, human traces/overrides" for the wiki. Gate only IRREVERSIBLE actions (principle_human_gate_irreversible); wiki notes are reversible → no gate. (cairn wiki #244 did the same.)

## Current state (verified live, not memory)
- wiki write tools (`propose_note/edit/link/unlink/merge/moc`, write_server.py) → `_enqueue` → `create_proposal(rationale REQUIRED)` → returns a PENDING proposal (proposal-id, NOT note-id). Agent write → pending → note NOT created until a human accepts (the dogfood complaint: `get note` → found:false; id = proposal-id ≠ note-id → agent confused).
- A W4d toggle EXISTS: `create_proposal(inp, auto_apply_eligible=False)` + `wikiAgentAutonomous` setting (default OFF) → when ON+eligible, auto-accepts via the `accept_proposal` chokepoint (decidedBy "agent:auto", fully audited). The write-server does NOT pass `auto_apply_eligible=True` + the setting defaults OFF → write-through isn't the default. **#25 flips this to default.**

## Design (all 4 forks team-lead-APPROVED)
1. **Reuse the chokepoint (NOT a new direct-write path).** The write-server's `_enqueue` passes `auto_apply_eligible=True`; flip `wikiAgentAutonomous` DEFAULT → ON (write-through). create_proposal → auto-accept (the existing single audited chokepoint) → the note lands NOW. The tool returns the APPLIED note-id (from the accept's applied_note_id), NOT the proposal-id. Less code, single chokepoint, op-log for free.
2. **Keep `wikiAgentAutonomous`, flip default to ON.** A user wanting the old proposals-only posture flips it OFF (reversible escape hatch). Default ON = write-through.
3. **Archive the 75-proposal queue** (mark "superseded by write-through", keep audit history — don't destroy trace). Pending #75 (dogfood artifact) → reject.
4. **Rework the M4 capability-gate tests** to assert the NEW boundary (below).
- **rationale → OPTIONAL** (drop the required-friction; the write tools' `rationale` param becomes optional/defaulted).
- **KEEP (non-negotiable pillars):** verify_citations (anti-fabrication — honest-mirror) + op-log (every mutation traced/rollback-able) + human-override (edit/delete the agent's note via recent_ops).

## Tasks
- **T1 (backend, gating):** write-server passes auto_apply_eligible=True + returns the applied note-id (not proposal-id); rationale optional; flip wikiAgentAutonomous default ON; archive the proposal queue + reject #75; rework the M4 gate tests (T2-spec below); REST parity (the REST wiki write path, if separate, write-through too). `docker compose restart backend` (config default change). Backend writes pytest.
- **T2 (tester):** live — wiki_write (MCP + REST) → note created NOW, returns real note-id, get(note)→found:true; rationale omitted works; op-log records it; human edit/delete the agent's note works; verify_citations still runs; toggle OFF → reverts to proposals-only (the escape-hatch distinguishing).
- **T3 (architect):** 4-step review + commit.

## M4 capability-gate TEST rework (HIGH-STAKES — security-gate tests; spec precisely)
The old tests (test_mcp_write, test_wiki_proposals, test_agent_proposals_apply) assert "agent write → pending, agent CANNOT apply its own proposal." The NEW boundary:
- assert agent wiki_write → note CREATED (write-through), returns real note-id, found:true. [the new default]
- assert the op-log records every agent mutation (trace intact — the control). 
- assert human-override works (edit/delete the agent's note). [the control moved post-write]
- assert verify_citations still runs (anti-fabrication pillar kept).
- assert toggle OFF → proposals-only restored (agent write → pending, not applied — the escape hatch). [the distinguishing that proves it's a flipped-default, NOT a removed gate]
- DO NOT just delete the old proposals-only asserts — REPLACE them with the new-boundary asserts (give the new tests teeth; a toothless "agent can write" without the toggle-off-still-gates case = a false-green that can't tell flipped-default from removed-gate).

## HARD GATE (distinguishing)
- wiki_write → note NOW + REAL note-id (not proposal-id) + get(note)→found:true. [the dogfood fix]
- rationale OPTIONAL (omitting works).
- op-log records the mutation (trace).
- human edit/delete the agent's note (override).
- verify_citations still runs (anti-fabrication kept).
- **toggle OFF → proposals-only (agent write → pending, not applied)** — the escape-hatch distinguishing (proves flipped-default, not removed-gate).
- the 75-queue archived (audit history kept), #75 rejected.
- REST + MCP both write-through (consistent surface).
- pytest green, mypy clean.

## Baseline
pytest 1707 (post-bundle). Keep 0-failed; expect a NET change (old proposals-only tests reworked, not just added).

## Assumptions (user-review)
- **Wiki agent-write is WRITE-THROUGH by default** (reverses proposals-only; user CHỐT'd — memory-reversible, gate only irreversible). The control is post-write: op-log trace + human edit/delete + verify_citations. **How to change:** `wikiAgentAutonomous` toggle OFF → back to proposals-only.
- **rationale OPTIONAL** on wiki writes (was required friction). **How to change:** the write tools' rationale param.
- **Reuse the create_proposal→auto-accept chokepoint** (not a new write path) — single audited route. The 75 old proposals archived (superseded), #75 rejected.
- **verify_citations + op-log KEPT** (the honest-mirror + audit pillars survive the reversal).

## Kickoff/verify addendum (2026-06-21 — the live-verify arc)
The structural change worked first-try on disk + unit tests, but live container-verify surfaced (then dissolved) 2 false-blockers + 1 real fragility:
- **FALSE: "Permission-denied host-path leak"** — TRANSIENT host-venv `.tmp` collision (backend tested in the host venv → left `.22.md.tmp` artifacts that briefly collided with the container's write of the same id). Clean restart → write-through works. NOT a code bug.
- **FALSE: "appliedNoteId still null"** — a top-level-vs-nested PARSE error: the created id IS returned as top-level `noteId` (+ nested `proposal.appliedNoteId`); reading top-level `appliedNoteId` (absent) saw null. Contract is correct; NO return-shape fix.
- **REAL (folded in): stale-.tmp fragility** — a leftover `.<name>.tmp` (from a crashed/cross-process write) can block the next write (the Permission-denied team-lead actually hit). HARDENING: md_store._atomic_write clears a stale `.<name>.tmp` before the write (fail-soft, atomicity preserved) + a test (stale .tmp present → write succeeds).
LESSON (reinforced): verify on the CONTAINER, not the host venv (host-venv "applied=True" was false); a transient + a parse-error both LOOKED like code blockers — Rule#0 reading the real shape/clean-container dissolved both. Cross-check (team-lead flagged, architect refined) caught both directions.

## Assumptions addendum
- **stale-.tmp cleanup before md_store write** (defensive — a leftover .tmp can't block a write). **How to change:** the unlink-stale-tmp in md_store._atomic_write.

## Notes
- FOUNDATION of the wiki batch — #19-24 build on this write surface. Do it FIRST.
- A trust-boundary reversal — team-lead heads-up'd the user. Memory `wiki-autonomy-toggle-d8-reversed` is the W4d precedent this builds on (flips its default).
- Memory-reversible → write-through is safe; verify_citations stays the anti-fabrication guard.
