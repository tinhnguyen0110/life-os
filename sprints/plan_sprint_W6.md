# Sprint W6 — Wiki completion · A1a (M3 sync) + A1b (citation post-verify) · PLAN

> Maps to DISPATCH backlog "Sprint 1: A1a + A1b (hoàn thiện wiki core — gating)".
> Numbered W6 (continues the W-series; W5b FE MOC screen is the last in-flight item).

## Objective
Close the two remaining **wiki-core** gaps that make the trust loop trustworthy across devices and across citations:
- **A1b — Citation post-verify layer** (smaller, higher north-star): deterministic code that checks every `{claim, note_id, span}` an external agent emits — note_id exists + span occurs verbatim in that note → else reject/flag "ungrounded". This is Trụ C ("code guarantees, prompt only reduces").
- **A1a — M3 sync (multi-device CRDT)**: extend the existing `wiki_op_log` + single-writer into a cross-device merge — device registry, offline op-queue, block-level LWW, conflict surfacing.

Both touch wiki core → **gating sprint, backend-only**, sequential. FE conflict-resolution UI (A1a) is a thin follow-on, deferred to the parallel FE sprint (Sprint 2 / A1c) unless trivial.

---

## Kickoff — 2026-06-14

### What I verified against the actual shipped code (not the dispatch's claims)
Read: `store.py`, `service.py`, `proposals_service.py`, `proposals_schema.py`, `mcp/read_server.py`, `mcp/write_server.py`, `router.py`, `WIKI-LLM-SPEC.md`, `end_sprint_W5a.md`, memory `wiki-llm-m1-m4-complete` + `wiki-autonomy-toggle-d8-reversed`.

**The dispatch's "wiki backend + MCP + proposals done (M1+M4)" claim is ACCURATE.** Concretely confirmed on disk:
- **Single-writer queue** (`service.py`): all mutation flows through ONE FIFO + one worker thread. `Op` dataclass, `enqueue()` blocks for result, `_apply_*` per kind (create/update/delete/merge/refine). This IS the M3 substrate — A1a extends it, does NOT replace it.
- **op_log** (`wiki_op_log`, store.py): append-only, `seq` AUTOINCREMENT monotonic apply order, columns `(op_id, kind, note_id, actor, ts, commit_sha, detail)`. `append_op()` / `recent_ops()`. Ready to be the sync replay log.
- **D6 tombstones** (`wiki_redirects` + `follow_redirect`): a cited-then-merged note never 404s — `resolve_note()` follows the redirect chain. **Citation post-verify (A1b) MUST reuse `resolve_note()`** so a citation to a merged-away id still verifies against the merge target.
- **MCP servers**: read (8 tools, AST-proven no-write) + write (6 propose_* tools, enqueue-only). A1b's verify layer is a **NEW read-side capability** (deterministic check, no mutation) → it belongs as a read-server tool + a REST endpoint, NOT the write server.
- **Note identity** = integer id, filename = `<id>.md`, title mutable in frontmatter (D1). `_parse()` returns `Note.content` = the body (frontmatter stripped). **A1b's "span occurs in note" check runs against `Note.content` (the body), and must decide whether the title/frontmatter is in scope — see A1b logic below.**

### Drift / corrections vs the DISPATCH + spec
1. **M2 grounded-chat is DROPPED** (memory-confirmed: chat = external Claude Code via MCP, no in-app LLM). The spec (L113-127) describes A1b's post-verify as living *inside* the M2 chat flow. **That home no longer exists.** → A1b must be re-homed as a **stateless verify service the EXTERNAL agent calls** (MCP tool + REST endpoint), not a check buried in an in-app chat endpoint. This is the central placement decision (detailed below). The DISPATCH itself half-anticipates this ("a verify endpoint the external agent calls? a check at proposal-accept?") — answered below.
2. **Citation `span` granularity is unspecified.** Spec promised `^block-id` anchors (D7) but those were never built (no block-id lifecycle in M1 — confirmed: no `^block` code anywhere). → A1b uses **literal substring span matching against the note body** (the simplest thing that delivers the anti-fabrication guarantee), NOT block-ids. Logged as an assumption.
3. **A1a M3 "device-prefixed integer id" (D1 upgrade path)** is a real schema change (id `47` → `d-47`). Spec says "add a prefix column, existing IDs default to desktop prefix, NOT a rebuild." For a **single-user** app the multi-device need is real but small — A1a should ship the op-log-sync mechanism + conflict surfacing, and treat the id-prefix migration as a guarded additive column, not a big-bang. Scope-trim candidate (see open question to team-lead).

### Recommendation: **A1b FIRST, then A1a** (within this sprint, sequential)
- A1b is **smaller, self-contained, higher north-star** (it directly hardens Trụ C, the trust boundary that is the whole point of the wiki). It's a pure read-side deterministic checker — no schema migration, no queue changes, low blast radius. Ship it first → quick win + it's the thing the external agent uses every query.
- A1a is **larger + riskier** (touches the op-log/writer, schema migration, conflict semantics, CRDT merge). It deserves the back half of the sprint with more care. It does NOT depend on A1b, so if A1a runs long it can split to W6a without blocking A1b's value.

### Final task list (W6)
- **T1 (A1b) — Citation post-verify service + endpoint + MCP tool** [backend, FIRST]
- **T2 (A1a) — M3 sync: device registry + offline op-queue + LWW merge + conflict surfacing** [backend, after T1 lands]
- **T3 — tester verification** (parallel, scaffolds from T1/T2 exports)
- FE conflict UI for A1a → deferred to Sprint 2 (A1c) unless T2 surfaces a trivial render-only need.

---

## Assumptions (user-review) — to be finalized in end_sprint_W6.md
- A1b span match = literal substring vs note body (no `^block-id` — never built). Case/whitespace-normalized? (decided in dispatch T1 logic).
- A1b verify surface = stateless REST `POST /wiki/citations/verify` + MCP read tool `wiki_verify_citations`; NOT a check at proposal-accept (proposals are structural intents, not claims-with-citations).
- A1a single-user multi-device: op-log replay + LWW; id-prefix migration as guarded additive column (deferred actual multi-device until a 2nd device exists).
