# Wiki-LLM Knowledge Module — Architecture Overview (pre-Sprint, for USER approval)

> **Author:** architect · **Date:** 2026-06-13 · **Status:** ⏸ awaiting user approval — NO sprint dispatched, NO code written.
> **Sources read:** `life-os-WIKI-LLM-SPEC.md` (spine, all 4 make-or-break decisions RESOLVED) + `life-os-WIKI-SCREENS-FEATURES.md` (5 screens + 1 panel) + current `backend/` registry + existing `notes` module.
> **What this doc is:** the roadmap overview team-lead asked for — module structure, module↔screen↔sprint map, full M1→M4→M3 roadmap, cross-cutting contracts, and the D5–D10 + C3 decisions architect owns. Approve the shape here → then architect kicks off M1 (Sprint W1) per playbook.

---

## 0. The bet, in one paragraph

The notes ARE the knowledge; the LLM is a **stateless traversal-and-synthesis engine rented per query** over an external memory it does not own. **Division of labor is the architecture: human curates structure (atomic notes, links, MOCs); the LLM traverses, synthesizes, and PROPOSES new structure the human ratifies.** Every AI mutation lands as a *candidate* in a review queue — never silently edits a human's evergreen note. Trust is enforced by **code** (post-verify citations: cited note exists + span actually occurs), not by prompt discipline. This is the same guarantee pattern as OutboundOS's URL-provenance guard: the LLM is free to navigate; its citations must verify or get flagged "ungrounded."

This honors the project north-star (`single-dev-no-overengineering`): **full feature set per spec, simplest implementation.** Concretely that means — no vectors (agentic retrieval over FTS+graph), no file locks (single-writer queue), no embedded LLM in-app (chat = Claude Code via MCP), no separate sync subsystem (M3 extends M1's op-log).

---

## 1. Where it plugs into life-os (module/registry — zero core edits)

The wiki is **one new module folder** under the locked `BaseModule` registry pattern. Adding it = adding `backend/modules/wiki/`; the registry auto-discovers it via `pkgutil.iter_modules` + `MODULE` attribute. **No edit to `core/` or `main.py`.** (Verified against `core/base.py` + `core/registry.py`.)

```
backend/modules/wiki/
  __init__.py        # exposes MODULE = BaseModule(name="wiki", router=router, routines=[...])
  router.py          # FastAPI endpoints (mounted at /wiki)
  schema.py          # Pydantic: Note, Link, Proposal, Op, frontmatter models
  service.py         # business logic: link-graph, backlinks, status state-machine, single-writer queue
  reader.py          # read-side: overview stats, graph build, FTS query, derived metrics (raw-data-first)
  store.py           # md+git note files (47.md) + SQLite cache (FTS5, links, op-log) — wiki-local store
  consolidation.py   # the "sleep-time" background pass (D8) — proposals-only
  # later (M2/M4): retrieve.py (agentic retrieval tools, read-only) · mcp_tools.py
```

**Stores (reuse the existing two-store split — ARCH):**
- **md+git** (`store/md_store.py` pattern) → the note files `47.md` (frontmatter + body). **Source of truth, portable, every write = 1 commit.**
- **SQLite** (`store/db.py`) → the **disposable, rebuildable cache**: `notes_fts` (FTS5), `links` graph table, `tags`, `files_ledger`, `op_log`, `proposals`, `agent_writes`, `redirects` (tombstones). Per the methodology's "files = source of truth; index = disposable cache" — the SQLite side can be dropped and rebuilt from the md files at any time.

### Relationship to the EXISTING `notes` module (important — they are DIFFERENT)
The current `notes` module (S5 screen, `frontend/app/notes`) is **simple string-ID notes that attach to a project/channel** (`Note{id:str, title, body, tags, pinned, attach}`). The **wiki is a separate, richer module** — integer-ID identity, link-graph, status state-machine, provenance/trust-tier, candidate queue. They do **not** merge in this build. Recommendation: keep `notes` as-is (quick scratch notes); `wiki` is the PKM knowledge graph. If the user later wants them unified, that's a deliberate phase-2 migration, not part of this roadmap. **Flagging for user: confirm you want wiki as a NEW module alongside notes, not a rewrite of notes.** (My recommendation: new module — they serve different jobs.)

---

## 2. Module → Screen → Sprint map

| Module | What it is | Screens it powers | Sprint(s) |
|---|---|---|---|
| **M1 — Wiki Core** (~35–45k LOC, split 3 backend sprints + 1 FE) | integer-ID notes, markdown CRUD, `[[47\|title]]` links + resolver, backlinks (linked+unlinked), frontmatter+provenance, tags, FTS5, link-graph table, ego-graph build, incremental index, **op-log + single-writer queue** | W2 (Note View/Edit) · W3 (Inbox/Refine) · W1 (Vault Overview) · W4 (Graph) | **W1a** store+ID+op-log (GATING) · **W1b** links/backlinks · **W1c** FTS/graph/readers · **W1-FE** screens |
| **M4 — MCP Layer** | MCP server exposing life-os APIs (read-only + write servers split); write tools land as candidates; immutable audit log; post-verify citations | feeds P1 (Proposal Queue) — agent write-back · W5 (MOC) · enables Claude Code as the "chat" | **W2** (MCP backend mock-free; FE for P1/W5) |
| **M3 — Sync Engine** | multi-device CRDT — **extends M1's op-log** (not a new subsystem); device registry, block-level LWW merge, conflict UI, offline queue | (no new screen; Top-bar Sync indicator) | **W3** (last) |
| ~~M2 — Embedded Chat~~ | **DROPPED.** Chat = Claude Code connected via MCP (M4). No in-app chat box, no API key/provider. | — | — |

> **M2 is intentionally NOT built.** The spec's "grounded chat" capability is delivered by Claude Code talking to the wiki **through M4 MCP** — the agentic-retrieval + post-verify-citation contract lives there, not in an embedded LLM. This keeps the no-AI-embedded property (CLAUDE.md §2) intact.

### Screen build priority (spec §"Ưu tiên build", architect-confirmed)
```
1. W2 (Note View/Edit) + W3 (Inbox/Refine)   ← capture→refine→link core, usable from note #1
2. W1 (Vault Overview)                         ← entry point, stats
3. P1 (Proposal Queue)                         ← once M4 MCP agent write-back exists
4. W4 (Graph Explorer) + W5 (MOC Workspace)    ← synthesize layer, the payoff, last
```

**Backend-first within each sprint** (life-os convention): backend freezes the schema + endpoints, announces freeze (`schema-freeze-gate`), THEN frontend ports the screen against the frozen shape + tester verifies live. The screen DATA shapes in `WIKI-SCREENS-FEATURES.md` are the FE↔BE contract.

---

## 3. Full roadmap M1 → M4 → M3

M1 is ~35–45k LOC — **too large for one sprint.** It splits into **4 backend sprints (W1a–W1d) that build the foundation bottom-up**, then screens layer on. M4 MCP (W2) follows. M3 Sync (W3) is independent + last. Each sprint below is 3–6 tasks, one shippable session.

> **⚡ PARALLELIZATION NOTE (per team-lead):** **M1 backend (W1a–W1d) and M4 MCP (W2) are PURE BACKEND — no mock UI needed.** They can be built BEFORE the user delivers Wiki screen mocks. The screen sprints (W2-FE onward) consume the user's mock + the frozen backend schema. So the critical path is: backend foundation runs now (mock-independent) ∥ user designs mocks → screens port when both are ready. This is the big schedule win — we don't idle waiting on mocks.

### Sprint W1a — M1 foundation: integer-ID notes + store + op-log (GATING, pure backend)
The bedrock everything else plugs into. **Build the op-log/single-writer FIRST** — it's the substrate for all mutations (D3) and the M3 sync engine.
- Note identity: **integer ID** (`47.md`, `id:47` in frontmatter, title mutable metadata). ID gen = SQLite `MAX(id)+1` (single machine, no collision). [D1 RESOLVED]
- `modules/wiki/store.py` — md+git note files (source of truth) + SQLite cache (`notes`, `files_ledger`, `op_log`). md write = git commit (reuse `md_store.py` pattern).
- **Changes-queue + op-log + single-writer** (D3) — ALL mutations are ops pushed to ONE FIFO queue; a single writer applies sequentially → file → cache. The 3 writers (human/MCP/consolidation) never write files directly; file-watcher is read-only (reindex trigger, not a 4th writer).
- Markdown CRUD: `POST/PUT/DELETE/GET /wiki/notes/:id` through the queue.
- Frontmatter + provenance schema: `status` (fleeting/developing/evergreen), `noteType` (concept/literature), `trustTier` (verified/candidate), `author`, `aliases`, `tags`, `contentHash`.
- **Gate:** create→read→edit→delete round-trips through the op-log; every mutation appears in `op_log` with actor; file + cache stay consistent; touch-no-change → no reindex (content-hash dirty check, debounce 500ms).

### Sprint W1b — M1 links: parser + resolver + backlinks + typed graph (pure backend)
- `parse_wikilinks(md)` → canonical `[[47|title]]` + typed `[[Title]]`→id resolver via cache index.
- `links` table (typed edges: `relates/supports/contradicts/refines/example_of`) + `is_resolved` (ghost links).
- `update_backlinks(id)` — **linked mentions** (`[[47]]` from other notes) + **unlinked mentions** (title/alias appears in another note's text, not yet linked).
- Ghost-link auto-resolve on target create; rename title → links point at ID so **NO rewrite needed** (verify this invariant holds — it's D1's whole payoff).
- **D5/D6/D10 land here:** edges-as-candidates-not-prose (D5) · ID-redirect tombstone on merge (D6) · archive-never-orphans-a-link constraint + test (D10).
- **Endpoints:** `GET /wiki/notes/:id/backlinks`, `POST /wiki/notes/merge`.
- **Gate:** rename 100× → 0 link breaks · delete → inbound become ghost (not dangling) · merge → old citations follow redirect · circular/self-link no crash · archive a linked note → edges survive (tested invariant).

### Sprint W1c — M1 retrieval surfaces: FTS5 + ego-graph + overview/inbox readers (pure backend)
- FTS5 full-text index (`notes_fts`) + `GET /wiki` search.
- Ego-graph build (1–2 hop) — server computes node/edge/cluster shape for W4.
- Status state-machine + **≥1-link hard gate on REFINE** (D9 cold-start exception: vault < 5 notes waives gate w/ visible warning).
- Reader-computed derived metrics (raw-data-first): overview stats (totals, byStatus, orphanCount, ghostLinkCount, pctWithLink), orphan sweep (degree=0/stale), inbox list, recent-activity from op-log.
- **Endpoints:** `GET /wiki/overview` · `GET /wiki/inbox` · `POST /wiki/notes/:id/refine` (422 if linkCount==0 & not cold-start) · `GET /wiki/graph?note=X&depth=2`.
- **Gate:** 200-note ego-graph < 1s · overview metrics match a known fixture · refine gate enforces ≥1-link except cold-start.

### Sprint W1-FE — Wiki screens W2 + W3 then W1 + W4 (FE, after backend freeze + user mock)
Backend-first: W1a–W1c schema/endpoints frozen + announced (`schema-freeze-gate`) → FE ports against the frozen shape + the user's mock. **Order:** W2 (Note View/Edit) + W3 (Inbox/Refine) = the capture→refine→link core (usable from note #1) → W1 (Vault Overview) → W4 (Graph Explorer, sigma.js). W5 (MOC) + P1 (Proposal Queue) slip to the M4 sprint (they need agent write-back).
- **Gate:** write/form round-trip verify (`write-form-roundtrip-verify` memory) — submit→2xx→re-GET reflects→persists post-reload; refine ≥1-link gate visible in UI; ghost links render distinctly + "create this note" button.

### Sprint W2 — M4 MCP Layer + P1 Proposal Queue + W5 MOC (pure backend MCP + FE for P1/W5)
**M4 is where "grounded chat" lives — Claude Code IS the LLM, via MCP.** No embedded model.
- MCP server over life-os API; per-module tools (wiki + finance + projects + journal).
- **Two servers, least-privilege:** READ-ONLY server (provably no write capability) + WRITE server (write tools require a confirm gate → land in P1 candidate queue). Immutable audit log: every call + params + actor + correlation-id.
- **Agentic retrieval + post-verify (D2, Trụ C):** Claude Code calls read tools (FTS+graph+metadata), greps/reads notes, refuses-by-judgment, answers with `{claim, note_id, span}`. **Deterministic code post-verifies** the citations Claude Code returns: note_id EXISTS + span actually occurs in that note → ungrounded claims flagged. This is the anti-fabrication guarantee that survives even though the LLM is external.
- **D7/D8/C3 land here:** `^block-id` lifecycle + drift warning (D7) · consolidation pass = proposals-only background routine (D8) · importance = advisory (C3).
- **FE:** P1 Proposal Queue (agent write-back review: accept/reject/pin) + W5 MOC Workspace (cluster→MOC draft, surface contradictions).
- **Gate:** external Claude Code reads notes/portfolio via MCP · every write audited + confirmed · read server has no write capability · every shown claim cites a real note + a span that EXISTS · ask-not-in-vault → refuse, never fabricate.

### Sprint W3 — M3 Sync Engine (the hard CRDT work; independent, last)
- Extends M1's op-log across devices (NOT a new subsystem — same changes-queue, wider merge scope). Device registry · block-level LWW CRDT merge (ref: sqlite-sync) · conflict UI for true conflicts · offline queue → sync on reconnect.
- ID upgrade: integer → **device-prefixed integer** (`d-47`, `p-12`) — add a prefix column, existing IDs default to desktop prefix. Migration, not rebuild. [D1 upgrade path]
- **Gate:** 2 devices edit same note offline → reconnect → converge, 0 data loss · real conflict → UI asks, no silent overwrite · mid-sync disconnect → idempotent resume.

### Phase 2 (only when vault > 5k notes — DEFERRED, additive)
Vector layer · cosmos.gl global graph · NLI verifier · auto-MOC · Adamic-Adar link suggestion. **Not in this roadmap** — the agentic-retrieval + structure-first design works from note #1, vectors stay deferred for good unless mature-vault recall demands it.

### Roadmap at a glance
```
W1a  M1 store + integer-ID + op-log/single-writer   (GATING, pure backend, mock-free) ─┐
W1b  M1 links + resolver + backlinks + typed graph   (pure backend, mock-free)         │ critical path
W1c  M1 FTS + ego-graph + overview/inbox readers     (pure backend, mock-free)         │ runs NOW,
W2   M4 MCP + post-verify + consolidation + P1/W5    (backend MCP mock-free; FE P1/W5) ─┘ mock-independent
W1-FE  Wiki screens W2→W3→W1→W4   (needs backend freeze + USER MOCK) ─── parallel to user designing mocks
W3   M3 Sync CRDT                  (independent, last)
```

---

## 4. Cross-cutting contracts (apply to EVERY wiki screen + endpoint)

1. **Integer-ID identity** — file `47.md` (filename = ID, never changes); `id:47` + mutable `title` in frontmatter; canonical link form `[[47|title]]`; LLM cites "note 47"; code post-verifies. [D1]
2. **Op-log / single-writer** — ALL mutations (human/MCP/consolidation) go through ONE changes-queue → one writer → file + cache. No direct file writes. Built in M1, is the M3 sync substrate. [D3]
3. **Post-verify citations** — any cited `{note_id, span}` is checked by deterministic code: note exists + span occurs; failing claims → flagged "ungrounded." The trust boundary that keeps the chat honest. [D2]
4. **Trust-tier / candidate queue** — human notes = `verified`; agent writes = `candidate`, land in P1, never edit a human evergreen body in place. Human promotes candidate→verified. [trust boundary]
5. **Files = truth, cache = disposable** — md+git is authoritative; SQLite (FTS/graph/op-log) is rebuildable.
6. **Two orthogonal planes** — concept graph (links, permanent) ⟂ PARA facet (project_ref/active/archived as metadata). **Archiving a project must never orphan a concept-graph link** (enforced, see D10).
7. **Command bar verbs** (extend existing command bar): `note <text>` (capture→inbox) · `link <id> <id>` · `open note <id>` · `find <query>` (FTS).
8. **Sidebar group "Tri thức"** — Wiki Home · Inbox (badge N fleeting) · Graph · Proposals (badge N pending). (Note: ties into the existing `sidebar-badges-static-placeholder` debt — wire these live, not hardcoded.)
9. **Response envelope + error codes** — `{success, data, warning?}`, REST codes 400/404/422/500, **no auth** (single-user, localhost — CLAUDE.md §2). REFINE without ≥1 link → 422 (unless cold-start).

---

## 5. The D5–D10 + C3 decisions architect OWNS (decided here, per decide-and-log)

These are mine to decide (CLAUDE.md decide-and-log — architect decides logic autonomously, logs to `## Assumptions`, team-lead pings user for async review). My decisions below; each will be logged when its owning sprint ships. **User can override any of these later.**

| # | Decision | My call | Why | How to change |
|---|---|---|---|---|
| **D5** | Auto-link write target (contradiction C2: appending `## Related` to a note = editing human's note in place) | **Edges live in the edge table + frontmatter `links:` field as candidates — NOT prose appended to body.** | Keeps "agent writes land in candidate namespace" invariant; body stays human-owned. | Spec locks this; flip only if user wants visible inline related-sections. |
| **D6** | Merge/delete tombstone semantics (a cited-then-merged note breaks every prior citation) | **ID-redirect tombstones**: merge source→target writes a `redirects(old_id→new_id)` row; citations + op-log refs auto-follow the redirect. Delete → inbound links become ghost (unresolved), not dangling. | Citations and episodic-log refs depend on stable resolution; a redirect is cheap (int→int) and never breaks a prior cite. | Add a "hard delete (no redirect)" admin path later if needed. |
| **D7** | `^block-id` lifecycle (LLM cites `^a1b2`, human edits that paragraph → silent citation drift = trust failure) | **Assign block-id at write time when a paragraph is first cited (lazy, not every block).** On edit of an anchored paragraph (content-hash of the block changes) → mark the citation **"may have drifted"** + surface the warning in W2 (spec already shows this). Do NOT silently move the anchor. | Eager block-ids on every paragraph = noise; lazy-on-cite covers the only case that matters (a cited span). Drift = visible warning, never silent. | Switch to eager block-ids if passage-citation density grows. |
| **D8** | Consolidation pass scope (the 4th writer, automated/bulk — most dangerous) + C3 | **Proposals-only. The consolidation pass READS the vault (dupes, orphans, clusters, stale candidates) and WRITES only proposals into P1 — it has NO autonomous edit authority.** Runs as a background routine (APScheduler), goes through the same single-writer queue, emits: dedup/merge suggestions, MOC proposals, orphan-review items, recomputed importance/decay. | The North Star litmus: if the pass autonomously prunes/edits, the LLM becomes the salience authority → "chatbot that read my files" failure. Proposals-only keeps human-disposes. | If the user later trusts auto-merge of obvious dupes, add a per-kind "auto-apply above confidence X" toggle — but default proposals-only. |
| **C3** | Importance/decay: advisory or authoritative? | **ADVISORY.** Importance is LLM-assigned at write time as a *signal* feeding ranking + the orphan/review sweep — it never gates pruning or auto-deletes. | Authoritative importance = LLM exercising editorial authority over salience → violates North Star. Advisory still powers resurfacing without ceding control. | Make it authoritative only with explicit user opt-in per-vault. |
| **D9** | REFINE invocation trigger + ≥1-link cold-start exception | **Trigger:** inbox badge (N fleeting) in sidebar + a `journal-nudge`-style routine that pings when inbox > threshold or oldest fleeting > N days. NOT pure user-initiative (→ junk drawer). **Cold-start exception:** if total vault notes < threshold (proposed **5**), the ≥1-link gate is waived with a visible warning ("vault too small to link — refine anyway"). | User-initiative-only never fires; a nudge routine makes refine happen. The first notes have nothing to link to → the hard gate is unsatisfiable → must carve the exception explicitly. | Tune the nudge threshold / cold-start count in settings (already a configurable-constants pattern from S12). |
| **D10** | "Archive never orphans a concept link" — needs enforcement, not discipline | **Constraint in the edge model:** archiving sets a `project_ref` facet flag on the note; it does NOT touch the `links` table. Concept edges are independent of PARA state by construction — there is no code path where archiving deletes a link. Add a test that archives a linked note and asserts its edges survive. | The doc's own thesis: disciplines-not-mechanisms reproduce failures. Make it structurally impossible, then test it. | N/A — this is an invariant, not a tunable. |

### Remaining open decisions (spec §6, recommendation taken)
- **Candidate trust tier storage:** **frontmatter field** (`trustTier: candidate`) over folder/namespace — keeps one note entity, simpler with integer-ID files, MCP scopes by querying the field. (Spec leaned folder for bulk-review; I prefer frontmatter for single-entity cleanliness + the op-log already gives auditability. Low-stakes, revisit at M4.)
- **Inbox:** dedicated inbox (`status=fleeting` query) over daily-note. Simpler, surfaces old unprocessed items by default.
- **Edge rationale:** LLM-drafted, human-optional (required kills velocity; absent kills emergence).
- **Episodic log:** separate append-only journal (the op-log already is this), NOT git history.

---

## 6. What I need from the user before kicking off Sprint W1

1. **Approve the module shape** — wiki as a NEW module alongside the existing `notes` module (not a rewrite). [My rec: yes, new module.]
2. **Approve the build order** — M1 (W2+W3→W1→W4) gating → M4 MCP → M3 Sync; M2 chat stays dropped (chat = Claude Code via MCP). 
3. **Sanity-check the D5–D10 + C3 calls** above — these are decided (won't block on them), but flag any you'd steer differently. Especially **C3 advisory** and **D8 proposals-only** (the North-Star-protecting calls) and **D9's cold-start threshold = 5 notes**.
4. **Confirm the first sprint = W1a** — M1 backend foundation only: integer-ID notes + md+git/SQLite store + the op-log/single-writer changes-queue + CRUD. **Pure backend, mock-free → starts immediately, no waiting on UI mocks.** W1b (links) → W1c (FTS/graph/readers) → W2 (MCP) follow, all backend, all mock-independent — that's the critical path. Wiki screens (W1-FE) port once the user delivers mocks + backend schema is frozen, in parallel with the user designing them.

**On approval → I run the §3.3a kickoff (re-read both specs + current code + last end_sprints + spot-check the registry/store patterns), write `plan_sprint_W1a.md`, and dispatch backend-first per §3.3b.** Until then: holding, no code, no dispatch.
