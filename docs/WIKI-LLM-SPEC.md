# Life OS — Wiki-LLM Knowledge Module · Build Spec for AI Team

> Spine document for the AI dev team. Structure-first (link + metadata core, vector deferred).
> Methodology section is filled from a dedicated architecture-research pass (in progress).
> Owner: team-lead dispatches per §Dispatch. Build native — no Obsidian dependency.

---

## 0. North Star (the load-bearing idea)

**The notes ARE the knowledge; the LLM is a stateless traversal-and-synthesis engine rented per
query over an external memory it does not own.** The corpus is persistent, authoritative ground
truth the model is forced to operate against — never a hint it can override with parametric
memory (NotebookLM source-grounding). Purpose = *augmentation* (Engelbart/Matuschak): expand the
thoughts the user can think by manufacturing emergent connection + surprise — not a faster filing
cabinet or a Q&A box. **Division of labor IS the architecture: the human curates structure
(atomic notes, links, MOCs); the LLM traverses, synthesizes, and PROPOSES new structure the human
ratifies.** Litmus: if at any decision the LLM becomes the authority and notes become mere
context, you've built "a chatbot that read my files" — the failure case.

The wiki is also **agent memory** (CoALA typing): semantic = human evergreen + agent-distilled
notes; episodic = session logs/lessons; procedural = reusable playbooks; working = the chat
thread. Exposed via MCP so agents read context + write insights back, human-in-the-loop.

---

## 1. METHODOLOGY (what software encodes vs leaves to discipline)

### ADOPTED
| Principle | Source | Why |
|---|---|---|
| **Atomicity** — one note = one idea | Luhmann, Matuschak | Precise links/citations/recombination only possible against single-idea notes |
| **Concept-orientation** — factor by IDEA not source/project | Matuschak | Kills per-book silos; connections cross domains |
| **Titles are APIs** — titles = complete declarative claims | Matuschak | Reusable handle + better citation + better match target |
| **Note type = soft mutable STATUS** not hard kind | Matuschak, Doto | Graduate in place (fleeting→developing→evergreen), keep ID + inbound links |
| **Capture→Refine→Link pipeline** with real inbox + ritual refine | Ahrens | Capture without convert-step = junk drawer |
| **Emergent bottom-up structure** from links + use | Luhmann, Milo | Reorg is continuous + normal, not migration |
| **MOCs as writable workstations** | Milo (LYT) | A curated note where connections are made anew ≠ backlinks panel |
| **Grounding + citation + honest-refuse** as hard contract | NotebookLM | The trust boundary; refusal is a gate not a suggestion |
| **Interest-driven resurfacing** | Matuschak | Link-neighborhood + orphan sweep IS the review module (no SR scheduler) |
| **Files = source of truth; index = disposable cache** | Obsidian vs Logseq | Portability + Git, rebuildable SQLite/FTS+graph cache for speed |

### REJECTED
Folders/categories as primary index · rigid note_type enum w/ separate tables · Johnny-Decimal IDs
· vector-first retrieval (deferred, additive later) · auto-linking as silent mutation (→ proposal
queue) · forced spaced-repetition · block-UUID addressing as foundation · AI silently editing human
notes · metrics that optimize capture/accumulation (junk-drawer trap).

### Conflicts resolved
- **Folders vs links → LINKS.** Folders cosmetic, never the index.
- **Categories vs emergence → EMERGENCE.** No upfront taxonomy; tags = tactical entry points; LLM detects clusters → proposes MOCs → human ratifies.
- **Zettelkasten vs PARA → ORTHOGONAL PLANES.** Concept graph (links, permanent) answers "what do I know about X"; PARA facet (project_ref/active/archived as metadata) answers "what's live now". **Archiving a project must NEVER orphan a concept-graph link.**

---

## 2. CORE WORKFLOWS (the spine — status state-machine over a shared link-graph)

The LLM touches all six, owns none — it PROPOSES, the human DISPOSES.

1. **CAPTURE** — raw dump → `status=fleeting`, stamped, into inbox. No categorization at write time. LLM (non-blocking): transcribe/suggest title+summary+role async.
2. **REFINE** (recurring cadence, NOT at capture) — triage inbox → rewrite into atomic prose + claim-title → flip status → **≥1 link before leaving triage (hard gate, w/ cold-start exception)**. LLM: detect non-atomicity, propose titles, draft rewrite, flag dupes, propose links. Atomicity = soft suggestion; ≥1-link = hard gate.
3. **LINK** (continuous, density = quality metric) — manual `[[title]]` OR AI-suggested candidates (ranked, **with explanation of WHY**, accept/reject/pin). **Candidates until accepted — never auto-written.** Persist rejected suggestions.
4. **RETRIEVE** — structure-first retrieval (graph expansion + metadata + FTS) → **confidence gate: below cutoff OR zero notes in region → HONEST REFUSE** → else generate constrained to retrieved passages → inline citations (note ID + anchor) → clickable.
5. **SYNTHESIZE** (the payoff) — detect cluster → synthesis workspace → draft MOC note linking members + articulating throughline. LLM: detect clusters, draft MOC scaffold, **surface contradictions** ("these two notes disagree"). "Challenge my thinking" not "summarize."
6. **REVIEW/RESURFACE** — passive (graph neighborhood while working) + orphan sweep (degree==0/stale) → **routes back into REFINE/LINK** (or corpus rots). Interest-driven, no forced SR queue.

**Cycle closes:** Capture→Refine→Link→[queryable]→Retrieve/Synthesize→Review→(orphans feed back)→Refine. Build status enum + typed edge graph + backlink index FIRST.

---

## 2b. AI LAYER CONTRACT (read/write-back)
- **Grounding:** retrieval bounded strictly to vault; answer only from retrieved notes; mandatory citation; honest-refuse when ungrounded. Human link graph = primary grounding signal.
- **Ranking:** `relevance × recency × importance` where relevance = link-proximity + metadata + FTS (not cosine). **Importance LLM-assigned at write time** (see open decision — advisory vs authoritative).
- **Write-back (trust boundary):** surgical edit via markdown AST, never whole-file rewrite. Agent writes land `status=candidate`, never editing human evergreen body in place. Human promotes candidate→verified. Contradiction-check before commit. Down-weight agent-authored at read.
- **Provenance roles:** concept note ("you concluded Y") vs literature note ("the source said X") — different metadata, the honest-grounding backbone.
- **Consolidation = background "sleep-time" pass** (dedup/merge candidates, distill episodic→semantic, recompute importance/decay, emit MOC proposals + review queue). Never inline — concentrates all mutation in one auditable place.

---

## 3. DATA MODEL (conceptual, follows from methodology)
*(refined after methodology lands; baseline below)*

```
notes(id, path, title, frontmatter_json, content, note_type, created, updated, content_hash)
links(source_id, target_id, type, is_resolved)   -- is_resolved=false → "ghost" link
tags(note_id, tag)
mocs(...)                                          -- map-of-content objects (from methodology)
files_ledger(path, mtime, size, content_hash, last_indexed)
notes_fts                                          -- SQLite FTS5
agent_writes(id, note_id, agent, content, status, created)  -- human-in-loop on agent write-back
mcp_audit(id, tool, params, actor, correlation_id, ts)
```

---

## 4. MODULES & DISPATCH

### M1 — Wiki Core · `modules/wiki/` · ~35-45k LOC · GATING
**IN:** integer-ID notes (`47.md`, title in frontmatter — see D1) · markdown CRUD ·
`[[47|title]]` links + `[[Title]]`→id resolver via index · backlinks (linked + unlinked
mentions) · frontmatter metadata + provenance fields (author/status/trust-tier — see §6 D-list) ·
tags · FTS5 full-text · link graph table · ego-graph view (sigma.js, 1-2 hop) · incremental index
(content-hash dirty check, debounce 500ms) · **changes-queue + op-log + single-writer (D3 foundation
— ALL mutations go through it from day 1; this is also the M3 sync substrate).**
**OUT (Phase 2):** vector embedding · cosmos.gl · global graph >5k notes · NLI verifier.
**Defensive cases (mandatory):** rename → rewrite inbound links · ghost link auto-resolve on
create · touch-no-change → no reindex · delete → cleanup links+FTS, inbound become unresolved ·
circular/self link no crash.
**Exports:** `parse_wikilinks(md)` · `update_backlinks(id)` · `reindex_note(path)` ·
`GET /api/wiki/notes/:id/backlinks` · `GET /api/wiki/graph?note=X&depth=2`
**Gate:** CRUD/rename/delete → graph+backlink+FTS consistent; touch≠reindex; 200 notes ego-graph <1s.

### M2 — Grounded Chat · `modules/wiki/chat/` · ~20-25k LOC · (Trụ C — build carefully)
**AGENTIC retrieval (D2 decision), NOT a fixed pipeline.** The LLM drives retrieval itself over the
index + metadata + FTS (grep/open notes, read more if insufficient) — like Claude Code over a repo.
No vector. Honest-refuse = LLM judgment after searching, not a numeric threshold.
**Flow:** query → LLM autonomously searches (FTS5 + wikilink graph + metadata as TOOLS it calls) →
reads notes it deems relevant, iterates if thin → answers with citation schema `{claim, note_id, span}`
→ if after searching nothing supports an answer → HONEST REFUSE ("not in your notes") → render claim→click→note+span.
**Post-verify (code, deterministic — this is what keeps Trụ C):** cited note_id EXISTS · span actually
occurs in that note (anti-fabrication) · claim with no valid citation → flagged "ungrounded" to user.
**Defensive cases:** cited note doesn't exist / span not in note → reject that claim · empty vault →
refuse, never fabricate from parametric memory · log every refuse (over-refusal calibration) ·
retrieval tools must be READ-ONLY (chat can't mutate notes).
**Gate:** every shown claim cites a REAL note + click jumps to a span that EXISTS; ask-not-in-vault →
refuse; 0 claims shown with a non-verifiable citation.

### M3 — Sync Engine (multi-device, single-user) · `modules/sync/` · ~15-20k LOC · EXTENDS M1's op-log
**Not a separate subsystem — extends the M1 changes-queue/op-log across devices (D3=M3).**
**IN:** device registry · block-level LWW CRDT merge (ref: sqlite-sync) · conflict UI for true
conflicts · offline queue → sync on reconnect · per-device sync state. (Op-log + single-writer already
built in M1, so M3 is the cross-device merge + transport layer only — smaller than first estimated.)
**Defensive cases:** 2 devices edit same note offline → merge no data loss · clock skew ·
delete-on-A + edit-on-B → tombstone, ask user · mid-sync disconnect → idempotent resume ·
rename + edit concurrent.
**Gate:** 2 devices edit offline → reconnect → converge, 0 data loss; real conflict → UI asks,
no silent overwrite.

### M4 — MCP Layer (expose ALL life-os APIs) · ~10-15k LOC
**IN:** MCP server over life-os API · per-module tools (wiki, finance, projects, journal) ·
immutable audit log.
**Defensive cases (MCP security):** separate READ-ONLY and WRITE servers (least-privilege) ·
audit every call + params + correlation id · write tools require confirm gate (approval queue) ·
no wildcard scope (confused-deputy / tool-poisoning).
**Gate:** external agent reads notes/portfolio via MCP; every write audited + confirmed; read
server has no write capability.

---

## 5. DISPATCH ORDER
```
Sprint 1: M1 Wiki Core            (gating — everything plugs in)
Sprint 2: M2 Grounded Chat + M4 MCP   (parallel; both need M1)
Sprint 3: M3 Sync Engine          (independent; the hard-token CRDT work)
Phase 2 (when vault >5k notes): vector layer · cosmos.gl · NLI verifier · auto-MOC · Adamic-Adar link suggest
```

## 6. ⛔ DECIDE BEFORE WRITING CODE (adversarial gap-check — these break the build if missed)

> An implementer-agent read the architecture adversarially and found the seams where idealized
> invariants collide with mechanical reality. Items 1-4 can INVALIDATE the central bet
> (portable-files / vector-deferred / structure-first). Resolve in order, BEFORE Sprint 1.

### THE 4 MAKE-OR-BREAK DECISIONS (each can invalidate the architecture)

**D1 — Link addressing + rename/alias. ✅ RESOLVED 2026-06-13 → INTEGER sequential ID (NOT UUID).**
Decision: **stable INTEGER ID is the identity; title is mutable metadata.** Same separation that
fixes "rename breaks links" (link points at the ID, not the title), BUT chosen INTEGER over UUID
deliberately: **a short integer (`note 47`) is far less hallucination-prone for the LLM to cite than
a long UUID string (`a3f9-2b1c-8e4d…`)** — directly protects citation accuracy (Trụ C). UUID's only
edge (collision-free offline generation) isn't needed at M1 (single machine).
```
File on disk:   47.md                (filename = integer ID, NEVER changes)
Frontmatter:    id: 47  ·  title: "Knowledge work accretes"  ·  aliases: [...]
Links in body:  [[47|Display title]]  (canonical)  — typed [[Title]] resolves Title→id via index
LLM cites:      "note 47" → code post-verify: id 47 exists + span occurs in it
```
- ID stable ✅ (rename title 100× → links point at 47, never break)
- Title freely mutable ✅ (edit frontmatter only, zero link rewrites)
- LLM-citation-safe ✅ (short int, hard to miscopy — beats UUID for grounding)
- "Obsidian-portable" leg of triangle C1 dropped on purpose (native build, files still plain md+git)
→ **ID generation: SQLite autoincrement (`MAX(id)+1`), one machine = no collision.**
→ **M3 upgrade path (write into spec, don't build now):** when multi-device sync lands, switch to
**device-prefixed integer** (`d-47`, `p-12`) — still short + LLM-friendly, collision-free across
devices. Migration = add a prefix column (existing IDs default to the desktop prefix). NOT a rebuild.
This defers the only thing UUID bought (offline collision-safety) to exactly when it's needed.
→ Resolver: maintain `title→id` + `alias→id` index in the disposable cache; canonical stored form
is `[[47|title]]`; body never rewritten on title change.

**D2 — Honest-refuse trigger WITHOUT vectors. ✅ RESOLVED 2026-06-13 → AGENTIC RETRIEVAL.**
Decision: do NOT build a pipeline scalar-threshold gate. Instead the LLM **drives retrieval
itself** (like Claude Code over a codebase): it reads the index/metadata, decides which notes to
grep/open, reads more if insufficient, and **refuses by JUDGMENT** ("after searching, this isn't in
your notes") — not by a numeric cutoff. Modern LLM reasoning + self-retrieve is good enough; no
vector needed, and this dissolves the cold-start problem (agent grep/read works on a 10-note vault).
→ **TRUST IS PRESERVED BY A CHEAP POST-VERIFY (keeps Trụ C "code guarantees, prompt only reduces"):**
after the LLM answers with `{claim, note_id, span}` citations, deterministic code checks: (a) cited
note_id EXISTS, (b) span actually occurs in that note (anti citation-fabrication), (c) any claim
with no valid citation → flagged "ungrounded" to the user. LLM free to navigate; citations must
verify. Same pattern as the OutboundOS URL-provenance guard.

**D3 — File-layer concurrency. ✅ RESOLVED 2026-06-13 → single-writer queue + changes-queue (= M3).**
Decision: NO file locks. The 3 writers (human editor / MCP agent / consolidation pass) **never write
files directly** — every mutation is an op pushed to ONE FIFO changes-queue; a SINGLE writer process
applies them sequentially → writes file → updates cache. File-watcher is READ-ONLY (triggers reindex,
never writes — not a 4th writer). No two concurrent writers → no race → no lock needed (offline-first
standard pattern: Adalo, DevelopersVoice, sqlite-sync).
→ **KEY: D3 (local concurrency) and M3 (multi-device sync) are the SAME architecture** — both are
"many mutation sources → one changes-queue/op-log → consistent merge", differing only in merge scope:
```
D3 local:   human + MCP + consolidation → changes-queue → 1 writer
M3 device:  device A + device B          → op-log        → CRDT merge   (same queue, wider scope)
```
Use **block-level LWW CRDT** (agent edits `## Related`, human edits body → both preserved after sync)
— ref impl: sqlite-sync (CRDT offline-first for SQLite), TS CRDT toolkits. **Build the changes-queue +
op-log in M1**, so D3 works immediately and M3 is just extending the same mechanism across devices —
NOT a separate subsystem. Saves tokens + keeps one coherent architecture.

**D4 — Cold-start signal problem. ✅ RESOLVED 2026-06-13 → dissolved by D2's agentic retrieval.**
The cold-start fear assumed a pipeline that needs dense graph/vectors to function. With LLM-driven
retrieval (D2), a sparse young vault is FINE — the agent just greps/reads the (few) notes directly,
exactly as it would read a small codebase. No bootstrap embedding index needed. Link-suggestion on a
sparse vault stays weak (accepted, low stakes early) — the chat/retrieve flagship works from note #1.
Vectors remain DEFERRED (additive later if mature-vault recall ever needs it), not required for v1.

### THE 6 LOCALIZED-BUT-EXPENSIVE RETROFITS

**D5 — Auto-link write target (contradiction C2).** "Append `## Related` to the note" = editing the
human's note in place, which contradicts "agent writes land in candidate namespace." Resolve:
edges live in the **edge table / frontmatter `links:` field as candidates**, NOT prose appended to body.

**D6 — Merge/delete/tombstone semantics.** REFINE merges dupes, SYNTHESIZE merges clusters — merge
is the most common destructive graph op AND there's no tombstone model. A cited-then-merged note
breaks every prior citation. Design **ID-redirect tombstones** now (citations + episodic-log refs depend on it).

**D7 — `^block-id` lifecycle.** Promised for passage citation but: who assigns, when? If LLM cites
`^a1b2` and human edits that paragraph → silent citation drift (a TRUST failure). Define: assign at
write time + policy for "block content changed under stable anchor." It's a consistency protocol, not a schema field.

**D8 — Consolidation pass + SSGM reconcile concrete spec.** It's the 4th writer and most dangerous
(automated, bulk). Define what it READS, what it's ALLOWED to write (proposals-only vs autonomous),
and resolve C3: **is importance/decay advisory or authoritative?** If authoritative, LLM exercises
editorial authority over salience → violates North Star. If advisory, it can't gate pruning. Decide.

**D9 — REFINE invocation trigger + ≥1-link cold-start exception.** What fires the ritual (cron/
badge/user-initiative)? User-initiative → never happens → junk drawer. And the first note ever
refined has nothing to link to → the ≥1-link hard gate is unsatisfiable → carve the exception explicitly.

**D10 — "Archive never orphans a concept link" needs ENFORCEMENT, not discipline.** Both planes ride
one note entity; make it a constraint in the edge model (the doc's own thesis: disciplines-not-mechanisms reproduce failures).

### OPEN DECISIONS (flagged, recommendation given)
- Candidate trust tier: **folder/namespace** (simplest bulk-review + clean MCP scoping) vs frontmatter field
- Auto-link approval: **candidates-until-accepted**, high-confidence batched into review queue (not auto-applied)
- Inbox: dedicated inbox vs daily-note (if daily, MUST surface unprocessed old items)
- Edge rationale: **LLM-drafted, human-optional** (required kills velocity; absent kills emergence)
- Episodic log: **separate append-only journal**, NOT git history (git mixes human+agent commits, not replay-structured)

### Primary sources (where calls are load-bearing)
NotebookLM source-grounding (adjacentpossible.substack.com) · Matuschak evergreen notes
(notes.andymatuschak.org) · Milo LYT/MOCs · Ahrens · CoALA (arXiv 2309.02427) · Generative Agents
(2304.03442) · A-MEM (2502.12110) · MemGPT/Letta (2310.08560) · Reflexion (2303.11366) · SSGM
(2603.11768) + VerificAgent (2506.02539) governance · Basic Memory (closest MCP-markdown substrate to fork).

---

## 7. DISPATCH NOTE FOR TEAM
**ALL 4 make-or-break RESOLVED 2026-06-13:**
- D1 (link addressing) → **integer-ID** (`47.md`, title in frontmatter, `[[47|title]]`; LLM cites "note 47"; → device-prefixed int at M3)
- D2 (honest-refuse) → **agentic retrieval** (LLM drives search, refuse-by-judgment) + **code post-verify citations**
- D3 (concurrency) → **single-writer + changes-queue/op-log** (= M3 sync substrate, build in M1)
- D4 (cold-start) → **dissolved** by D2's agentic retrieval. Vectors deferred for good.

Architect still owns, decided in/before owning sprint:
- D5 auto-link write target = **edge table/frontmatter `links:`, NOT prose-in-body** (recommendation locked)
- D6 merge → **ID-redirect tombstones** (easy now: UUID redirects to UUID; citations auto-follow)
- D7 `^block-id` lifecycle · D9 REFINE trigger + ≥1-link cold-start exception · D10 archive-never-orphans constraint
- C3 importance advisory-vs-authoritative → decide before the background/consolidation pass

**Build order:** M1 (incl. UUID-identity + op-log foundation) → M2 (agentic chat + post-verify) + M4
(MCP) parallel → M3 (extend op-log to multi-device CRDT). No Sprint-0 blocker remains — architect can
kick off M1 directly; the spec's open items are localized, not foundational.
