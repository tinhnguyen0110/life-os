# Sprint W4 — M4 MCP Layer (Wiki) · plan

> Goal: Claude Code (external agent) plugs into life-os via **MCP** to READ the wiki and
> WRITE insights back — but **every write lands as a PROPOSAL** in a human-ratified review
> queue, never a direct mutation. This is the "AI that acts" pillar (Trụ C), enforced by CODE.
>
> North-star litmus (spec §1): notes ARE the knowledge; the LLM is a stateless engine that
> PROPOSES; the human RATIFIES. If an AI write ever lands in the vault without a human accept,
> M4 has failed.

## Spec anchors (docs/WIKI-LLM-SPEC.md)
- **M4 (L139-146):** MCP server over life-os API · per-module tools · immutable audit log.
  Defensive: **separate READ-ONLY and WRITE servers** (least-privilege) · audit every call +
  params + correlation_id · **write tools require confirm gate (approval queue)** · no wildcard
  scope (confused-deputy / tool-poisoning). Gate: external agent reads via MCP; every write
  audited + confirmed; **read server has NO write capability.**
- **Proposals-only (USER DECISION, locked):** every AI mutation = a candidate in the review
  queue, batch-accept in P1. C3 advisory, D8 proposals-only. (L62 candidates-until-accepted,
  L74 agent writes land `status=candidate`, never editing human evergreen in place.)
- **Data model (L90-91):** `agent_writes(id, note_id, agent, content, status, created)` +
  `mcp_audit(id, tool, params, actor, correlation_id, ts)`.

## Decision-and-log (architect autonomous, per CLAUDE.md §3)

### D-W4.1 — Proposal table is GENERAL, not note-body-only
Spec's `agent_writes` only models a note-body write. But proposals also cover **link add/remove**
(L62 "candidates until accepted"), **MOC proposals** (L51), **merge** (L76), **title/rewrite**
(L61). So instead of `agent_writes`, build a single general table:
```
wiki_proposals(
  id INTEGER PK, kind TEXT, target_id INTEGER NULL, payload_json TEXT,
  rationale TEXT, actor TEXT, status TEXT, correlation_id TEXT,
  created TEXT, decided TEXT NULL, decided_by TEXT NULL
)
kind ∈ {note_create, note_edit, link_add, link_remove, merge, moc}
status ∈ {pending, accepted, rejected}
```
**Why:** the P1 Queue screen batch-accepts heterogeneous proposals; one table = one review
surface + one audit path. **How to change:** add a `kind` enum value + an apply-handler.

### D-W4.2 — Apply-on-accept reuses M1 single-writer
A proposal carries the *intent* (payload). On ACCEPT, the apply-handler dispatches the equivalent
M1 mutation **through the existing single-writer changes-queue** (create_note / add link / merge /
refine) — proposals never write files directly. REJECT just flips status + audits; nothing applied.
**Why:** all mutation stays in one auditable place (spec D3). **How to change:** edit the
per-kind apply-handler in service.

### D-W4.3 — Two MCP servers, hard-separated by capability
`mcp/read_server.py` exposes ONLY the 12 read endpoints as tools (search, overview, inbox, graph,
get_note, backlinks, ...). `mcp/write_server.py` exposes write tools that ONLY enqueue proposals
(propose_note, propose_link, propose_merge, propose_moc) — it has NO path to a direct mutation.
Read server importing nothing from service-write. **Why:** least-privilege, read server provably
write-incapable (the M4 gate). **How to change:** capability is structural (separate modules), not
a flag — keep it that way.

### D-W4.4 — Audit is append-only + correlation_id threads a session
Every MCP tool call (read OR write) appends to `wiki_mcp_audit(id, tool, params_json, actor,
correlation_id, ts)`. correlation_id groups one agent session's calls. Reads audited too (cheap,
and the spec says "every call"). **Why:** immutable audit (L141), tool-poisoning forensics.
**How to change:** retention/rotation later; M4 keeps all.

## Sub-sprint breakdown (M4 is ~10-15k LOC → split)

| Sprint | Theme | Owner | Gating? |
|---|---|---|---|
| **W4a** | Proposal/approval-queue backend: `wiki_proposals` table + audit table + CRUD (`POST /wiki/proposals`, `GET /wiki/proposals?status=`, `POST /wiki/proposals/{id}/accept`, `/reject`, batch-accept) + apply-on-accept via single-writer | backend | **GATING** (MCP write + P1 screen both depend) |
| **W4b** | MCP READ-only server: wrap 12 read endpoints as MCP tools; audit each; **zero write capability**; mcp.json/stdio entrypoint | backend | after W4a (shares audit table) |
| **W4c** | MCP WRITE server: propose_* tools → enqueue into W4a queue (never direct); audit + correlation_id; confirm-gate semantics | backend | after W4a + W4b |
| **P1** | Proposal Queue screen (`/wiki/proposals`): list pending by kind, show rationale + diff, accept/reject, **batch-accept**; honest "0 pending" empty state | frontend | parallel after W4a freezes proposal schema |

## Gates (every sub-sprint)
- W4a: propose→GET shows pending→accept→re-GET shows accepted AND the mutation actually landed
  (re-GET the note/link reflects it) · reject→nothing applied · batch-accept N→all applied ·
  audit row per call. (write-form-roundtrip-verify: accept must PERSIST, not just flip status.)
- W4b: `mcp` read tool returns same data as the REST endpoint · read server has NO import path to
  any write/enqueue fn (grep-proven) · audit row per read call.
- W4c: propose_link via MCP → appears in `GET /wiki/proposals` pending → NOT yet on the note ·
  accept (via W4a) → now on the note · audit + correlation_id present · no direct-write path.
- P1: Chrome — pending proposals render with rationale, accept applies + removes from queue,
  batch-accept works, empty state honest ("0 chờ duyệt · AI không bao giờ tự ghi").

## Out of scope (M4)
- finance/projects/journal MCP tools (spec L140 lists them, but M1 is wiki-only this build; add
  per-module later). M4 here = **wiki MCP** only.
- M2 grounded chat (dropped — chat = external Claude Code via this MCP, no in-app LLM).
- M3 sync (next milestone after M4).
