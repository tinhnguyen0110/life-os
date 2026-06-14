# Sprint W4c — MCP WRITE server (wiki) · plan — CLOSES THE M4 LOOP

> External Claude Code PROPOSES wiki mutations via MCP — but every write tool ENQUEUES a proposal
> into the W4a queue (status=pending), NEVER touches the vault directly. The human ratifies in P1.
> This closes the M4 loop: Claude Code reads (W4b) → proposes (W4c) → human accepts (P1) → vault.

## Spec anchors
- M4 L139-146: separate READ-ONLY and WRITE servers · write tools require **confirm gate (approval
  queue)** · audit every call + correlation_id · no wildcard scope. Gate: every write audited +
  confirmed; the write server CANNOT mutate the vault directly — it can ONLY enqueue.
- Proposals-only (locked user decision): every AI write = a candidate in the W4a queue.

## Decisions (decide-and-log)

### D-W4c.1 — write tools ENQUEUE, never apply
The write server's tools call `proposals_service.create_proposal(...)` ONLY — which records intent
(W4a verified: create writes nothing to the vault). The write server must NOT import or call
create_note/update_note/merge_notes/delete_note/accept_proposal (accept is the HUMAN's action in
P1, not the agent's). **Why:** the agent proposes, the human ratifies — the whole M4 pillar.
**How to change:** never; this separation is the security model.

### D-W4c.2 — separate server/process from the read server (least-privilege)
`modules/wiki/mcp/write_server.py`, entry `python -m modules.wiki.mcp.write_server`. A DIFFERENT
mcp registration than the read server. The read server (W4b) still has zero write/enqueue capability;
the write server has enqueue-only (no direct mutate, no accept). Two processes, two capability sets.
**Why:** spec L142 separate servers; confused-deputy resistance. **How to change:** never merge them.

### D-W4c.3 — propose tools map to proposal kinds
- `propose_note(title, content, tags?, rationale)` → kind=note_create
- `propose_edit(note_id, title?, content?, rationale)` → kind=note_edit
- `propose_link(from_note_id, target, rationale)` → kind=link_add (payload {target})
- `propose_unlink(note_id, target, rationale)` → kind=link_remove
- `propose_merge(source_id, target_id, rationale)` → kind=merge
- `propose_moc(title, content, rationale)` → kind=moc
Each REQUIRES a `rationale` (spec L62 "with explanation of WHY" — the agent must justify; a write
tool with no rationale is rejected). actor defaults "mcp:writer"; correlation_id per session threads
the agent's proposals so the human sees them grouped in P1.
**Why:** 1:1 with the W4a kinds; rationale-required enforces the explain-your-write norm.

### D-W4c.4 — audit every call (same wiki_mcp_audit)
actor=mcp:writer, tool=propose_*, params + correlation_id. **Why:** immutable audit of what the AI
proposed. The created proposal ALSO lands in the queue (visible in P1) — double trail.

## Scope
IN: `modules/wiki/mcp/write_server.py` (6 propose tools, enqueue-only, audit, rationale-required) ·
README update (register the write server in Claude Code) · tests: each propose tool creates a
pending proposal + writes NOTHING to the vault (the gate) + the no-direct-mutate AST test
(write_server imports create_proposal but NOT create_note/accept/etc.) + audit-per-call.
OUT: the read server (done W4b) · accept/reject from MCP (that's the human in P1, NOT the agent) ·
finance/projects tools · SSE/HTTP · auth.

## Gates (THE M4 LOOP-CLOSE)
- **propose via MCP → proposal appears pending in GET /wiki/proposals → vault UNCHANGED** (the agent
  proposed, nothing landed). Then a human accept (P1/REST) → NOW it lands. Prove the full chain live.
- **no direct-mutate**: write_server imports create_proposal (enqueue) but NOT create_note/
  update_note/delete_note/merge_notes/accept_proposal — AST-proven, like W4b's gate.
- audit row per propose call (actor=mcp:writer).
- rationale required: a propose call with empty rationale → rejected (or stored with a clear flag —
  decide, but the norm is the agent must explain).
- stdio handshake clean; pytest green (≥ baseline+new), mypy clean, no dup-name.
