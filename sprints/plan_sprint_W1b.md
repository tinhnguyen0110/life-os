# Plan — Sprint W1b · M1 links (parser + resolver + backlinks + typed graph + D6/D10)

> Second M1 sprint. Pure backend, mock-free → runs immediately on top of W1a's frozen contract (`5124de9`).
> Adds the link layer: `[[47|title]]` parsing, `[[Title]]`→id resolution (on W1a's `wiki_aliases` + `idx_wiki_notes_title` seams), backlinks (linked + unlinked), typed edges, ghost-link auto-resolve, D6 tombstones, D10 archive-never-orphans.
> Spec: `docs/WIKI-LLM-SPEC.md` §M1 + §6 (D5/D6/D10/D1) · Mock contract: `template/Life Command/app/data-wiki.js` (`backlinks`/`graph.edges`/`suggestions` shapes). Author: architect · 2026-06-13.

---

## Objective

Stand up the link graph over the W1a note store: parse wikilinks from bodies, resolve `[[Title]]`→id, persist typed edges in a `wiki_links` table, compute backlinks (linked + unlinked mentions), auto-resolve ghost links when their target is created, and implement **ID-redirect tombstones** (D6, merge) + **archive-never-orphans** (D10) as enforced constraints. Endpoints: `GET /wiki/notes/:id/backlinks` + `POST /wiki/notes/merge`. **No FTS5 full-text search yet** (that's W1c — but unlinked-mentions needs a text scan; see B3 for the W1b-acceptable approach). All mutations still flow through W1a's single-writer queue.

## Scope

**IN:**
- `parse_wikilinks(body) -> list[Link]` — extract `[[47]]`, `[[47|display]]`, `[[Title]]` from a note body (B1).
- `[[Title]]`→id resolver using `wiki_aliases` + `idx_wiki_notes_title` (title→id + alias→id), populated as part of the writer's cache-update step (B2).
- `wiki_links` typed-edge table (`source_id, target_id|target_title, type, is_resolved`) + edge extraction on every note write (re-derive this note's outbound edges) (B2).
- Typed edges: `relates | supports | contradicts | refines | example_of` (default `relates` when untyped) (B1).
- Ghost links: `[[Title]]` with no matching note → `is_resolved=False` edge w/ `target_title`; **auto-resolve on create** — when a new note's title/alias matches a ghost's `target_title`, flip those edges to resolved + set `target_id` (B4).
- Backlinks: `GET /wiki/notes/:id/backlinks` → `{linked:[{id,title,snippet,anchor?}], unlinked:[{id,title,snippet}], outbound:[{id,title,isResolved}|{ghost,isResolved:false}]}` (B3).
- **D6 ID-redirect tombstone:** `POST /wiki/notes/merge {sourceId, targetId}` → source note deleted, a `wiki_redirects(old_id→new_id)` row written, inbound links to source repointed to target (or resolved through the redirect), op_log `merge` (B5).
- **D10 archive-never-orphans:** archiving a note (a PARA-facet flag) must NOT delete/orphan its concept edges — enforced in the edge model + a teeth-test (B6).
- **Rename-no-rewrite invariant teeth-test** [D1]: rename a note's title → all inbound `[[id]]` links stay `is_resolved=True`, 0 link rows rewritten.
- Op_log `kind` extends to include `link`, `merge` (additive — W1a left `kind` a TEXT column).

**OUT (later — name them):**
- FTS5 full-text search endpoint → W1c (B3 uses a simpler scan for unlinked-mentions; see note).
- Ego-graph `GET /wiki/graph` + clusters → W1c.
- Overview stats / inbox / refine ≥1-link gate → W1c.
- AI link suggestions (`GET /wiki/notes/:id/suggestions`) → **empty `[]` at M1** (no embedded AI; populated M4). May stub the endpoint returning `{candidates: []}` if FE needs the route, else defer.
- MCP / proposals / post-verify → W2.
- `^block-id` lifecycle (D7) → W2 (with citations).

## Logic/Algorithm (architect-specified — implement exactly)

### B1 — wikilink parser + typed edges
- `parse_wikilinks(body)` regex over `[[...]]`: forms `[[47]]` (id, no display), `[[47|Display text]]` (id + display), `[[Title]]` (title ref, no id), `[[Title|Display]]`. Typed form: an optional `type:` prefix is OUT (keep simple) — **types are assigned at the edge level**, default `relates`; W1b does NOT parse type syntax from the body (the mock shows typed edges but the human/AI sets type via a later UI/API, not inline markdown). So the parser yields `(target_id|target_title, display)` tuples; `type` defaults `relates`.
  - Rationale: inline `[[supports::47]]`-style typed-link syntax is not in the mock body samples (bodies use plain `[[47|title]]`). Don't invent syntax. Edge typing comes from explicit API later; W1b persists `type='relates'` for parsed links + leaves the column writable for W1c/W2.
- Dedup: same target appearing twice in a body → one edge (or keep count? → one edge, simplest; backlink snippet can show first occurrence).
- Self-link (`[[47]]` in note 47) and circular (47→88→47) → persist without crash; self-link allowed but flagged (low value, don't special-case-reject).

### B2 — resolver + edge persistence (in the writer's cache-update step)
- On every note write (create/update via the W1a queue), AFTER the md write + `wiki_notes` upsert, RE-DERIVE this note's outbound edges: parse body → for each link, resolve `[[Title]]`→id via `wiki_aliases`/title index (exact match; case-insensitive? → **case-insensitive title match**, store titles lowercased in the resolver index or use `COLLATE NOCASE`). `[[47]]` is already an id. Delete this note's old `wiki_links` rows (where `source_id=this`) + insert the fresh set. This keeps edges consistent with the body on every edit (idempotent reindex).
- Populate `wiki_aliases`: on write, replace this note's alias rows ((alias,note_id) for each alias + (title,note_id) for the title) — so the resolver index reflects current title/aliases. This is the W1a seam being filled.
- Resolver collision (two notes share a title): title index is non-unique → pick the **lowest id** deterministically + log a warning (titles SHOULD be unique per Matuschak "titles are APIs" but we don't hard-enforce). Document this.

### B3 — backlinks (linked + unlinked)
- **Linked mentions:** `SELECT source_id FROM wiki_links WHERE target_id = :id AND is_resolved` → for each, the source note's title + a snippet (the body text around the `[[id]]` occurrence, ±N chars). Anchor (`^block-id`) is W2 — `anchor` optional/absent in W1b.
- **Unlinked mentions:** notes whose BODY contains this note's title or an alias as plain text but DON'T link it. W1b has no FTS5 yet → **acceptable W1b approach: a `LIKE %title%` scan over `wiki_notes`... but body isn't in the cache.** Decision: store a lightweight **body-text mirror** is overkill; instead unlinked-mentions reads note bodies from md (bounded — vault is small at M1) OR defer unlinked-mentions to W1c when FTS5 lands. **DECISION: defer unlinked-mentions to W1c** (it naturally belongs with FTS5; doing a full md scan now is the kind of thing FTS5 exists to replace — no-overengineering). W1b returns `unlinked: []` with the shape present (honest-mirror: shape there, populated W1c). Linked + outbound are the W1b deliverables.
- **Outbound:** this note's `wiki_links` rows → resolved ones as `{id,title,isResolved:true}`, ghosts as `{ghost:target_title, isResolved:false}`.

### B4 — ghost links + auto-resolve-on-create
- A `[[Title]]` with no resolvable id → edge with `target_id=NULL, target_title=Title, is_resolved=False`.
- **Auto-resolve on create (the defensive case):** when a note is created/renamed whose title or alias == some ghost edge's `target_title` (case-insensitive) → UPDATE those edges: set `target_id=new note id, is_resolved=True`. This runs in the writer's cache-update step (after the alias index is refreshed). Teeth: create note "Atomicity principle" → the pre-existing ghost `[[Atomicity principle]]` from note 47 flips to resolved pointing at the new id.

### B5 — D6 ID-redirect tombstone (merge)
- `POST /wiki/notes/merge {sourceId, targetId}` (through the queue): validate both exist + differ; delete the source md file + cache row (A4 path); write a `wiki_redirects(old_id, new_id, created)` row; **repoint inbound links**: `UPDATE wiki_links SET target_id=:new WHERE target_id=:old`; op_log `merge` (detail = "merged #old → #new"). 
- **Redirect-follow on read:** `GET /wiki/notes/:id` — if id is a tombstone (in `wiki_redirects`), 301-style: return the target note (or a `{redirectedTo: new_id}` envelope — **DECISION: return the target note's data with a `warning: "note #old merged into #new"`** so a stale citation/link still resolves, never 404s). This is what makes "a cited-then-merged note doesn't break citations."
- Chained redirects (old→mid→new): follow transitively, cap depth (e.g. 10) to avoid a cycle hang.

### B6 — D10 archive-never-orphans (constraint, not discipline)
- Archiving is a PARA-facet flag (a `project_ref`/`archived` metadata field — **W1b adds an `archived: bool` to the note or a facet; if not in the frozen schema, add it additively**). The constraint: **no code path that sets archived touches `wiki_links`.** Concept edges are independent of PARA state by construction.
- Enforce + prove: a test archives a linked note and asserts its inbound + outbound edges all survive unchanged (`is_resolved` intact, row count unchanged).
- NOTE: archiving as a full feature may be light in W1b (no archive endpoint exists yet). Minimal: ensure the edge model has NO cascade from any archive/status change to link deletion, and the teeth-test proves it. If no archive flag exists yet, the test can use status→evergreen or a stub archived flag — the INVARIANT (status/facet change ≠ link change) is what's tested.

## Schema/field list (additive to W1a's FROZEN Note — announce the additions, freeze for W1c/FE)
- **New tables:** `wiki_links(id PK, source_id, target_id NULL, target_title NULL, type DEFAULT 'relates', is_resolved)` + `wiki_redirects(old_id PK, new_id, created)`. Indexes on `wiki_links(target_id)`, `wiki_links(source_id)`.
- **`wiki_aliases`** (W1a seam) — now populated.
- **Backlinks response** (matches mock `data-wiki.js` `backlinks`): `{linked:[{id,title,snippet,anchor?}], unlinked:[{id,title,snippet}], outbound:[{id,title,isResolved}|{ghost,isResolved:false}]}`. `unlinked` ships `[]` in W1b (shape present, populated W1c).
- **Merge input:** `MergeInput{sourceId:int, targetId:int}` (both required, must differ → 422 if equal, 404 if either absent).
- **Note schema additive (if D10 needs it):** consider `archived: bool = False` — additive, optional. Confirm with the mock (mock notes don't show `archived` → may defer the flag, just ensure no cascade). **Backend: do NOT break the frozen W1a Note shape; any addition is optional w/ default.**
- AI `suggestions` endpoint → `{candidates: []}` empty at M1 if FE needs the route; else omit.

## Tasks (3, backend-only)
- **T1 — parser + resolver + edge persistence (GATING).** `parse_wikilinks` (B1) + resolver via wiki_aliases/title index (B2) + `wiki_links` table + re-derive-edges-on-write hook in the queue's cache-update step + populate wiki_aliases. Backend unit tests: parse forms, resolve hit/miss, case-insensitive, self/circular, edge re-derive on edit.
- **T2 — backlinks + ghost auto-resolve.** `GET /wiki/notes/:id/backlinks` (linked + outbound; unlinked=[]) (B3) + ghost auto-resolve-on-create/rename (B4). Tests: linked-mentions w/ snippet, outbound resolved+ghost, ghost flips on target create, **rename-no-rewrite teeth-test (D1)**.
- **T3 — D6 merge tombstone + D10 archive-never-orphans.** `POST /wiki/notes/merge` + `wiki_redirects` + redirect-follow on GET + inbound repoint (B5) + D10 constraint + teeth-test (B6). Tests: merge → source gone + redirect row + inbound repointed + GET old → target+warning (not 404) + chained redirect cap + archive-keeps-edges.

## Runtime / Baseline / Dependencies / Exports / Test split / Verification / Ownership / Idle
- **Runtime:** docker compose up -d (detached); BE **:8686** (verified — memory dev-server-ports updated, NOT :8001); verify on container `curl :8686/wiki/notes/X/backlinks`.
- **Baseline:** pytest **756** (post-W1a), vitest 383. W1b additive → expect >756.
- **Dependencies:** W1a frozen schema + queue + store (`5124de9`, stable). wiki_aliases + title index seams present. Blocks: W1c (FTS/graph/overview) builds on wiki_links; freeze wiki_links shape end of W1b.
- **Exports (tester pre-scaffold):** `parse_wikilinks(body)->list` · `resolve_title(title)->int|None` · `service.merge_notes(src,tgt)` · `reader.backlinks(id)->dict` · endpoints `GET /wiki/notes/:id/backlinks`, `POST /wiki/notes/merge`.
- **Test split:** backend writes unit/API in T1/T2/T3 (`test_wiki.py`). Tester scaffolds the ghost-resolve BEHAVIOR test + rename-no-rewrite teeth + merge-citation-follow + the curl integration — NOT backend's parser unit tests.
- **Verification (ONE bar):** parse all 4 link forms · `[[Title]]` resolves case-insensitively · edges re-derived on every edit · ghost flips to resolved on target create · rename → 0 link rewrites (D1 teeth) · merge → inbound repointed + GET-old-returns-target-with-warning (not 404) + redirect-follow capped · archive → edges survive (D10) · pytest ≥756 + 0 errors/unhandled · all mutations through the queue + op_log. Gates 1+2 per task, Gate 3 at close.
- **Ownership:** pytest fail → backend fixes; tester reports w/ repro; schema/edge-contract conflict → architect.
- **Idle:** each task done → SendMessage team-lead w/ evidence (pytest count + git stat + curl backlinks payload + a merge→redirect DB dump showing inbound repointed) + TaskUpdate. Blocked → SendMessage immediately.

---

## Kickoff — 2026-06-13
### Drift check
- W1a contract STABLE at `5124de9` (verified HEAD). Frozen Note schema unchanged. W1a deliberately stood up the W1b seams: `wiki_aliases` table + `idx_wiki_notes_title` (both empty, documented "W1b populates"). So W1b plugs in with NO W1a schema change — clean.
- Mock-diff (data-wiki.js `backlinks`/`graph.edges`/`suggestions` vs scope): W1b covers linked+outbound+ghost+typed-edges+merge. **unlinked-mentions deferred to W1c** (needs FTS5 — doing a full md scan now is what FTS5 replaces; honest-mirror: ship `unlinked:[]` shape, populate W1c). **suggestions (AI candidates) = empty at M1** (no embedded AI). Both logged so FE/tester know the shape-present-but-empty contract.
### Decisions (decide-and-log → end_sprint_W1b §Assumptions)
- Typed-edge type NOT parsed from inline body syntax (mock bodies use plain `[[id|title]]`); edges default `type='relates'`, type set via explicit API later. Don't invent `[[supports::x]]` syntax.
- Title resolution case-insensitive (COLLATE NOCASE); title collision → lowest id + warning (titles SHOULD be unique, not hard-enforced).
- Merge GET-on-tombstone returns the TARGET note + `warning`, NOT 404 (citations survive). Chained redirects followed, depth-capped.
- unlinked-mentions deferred to W1c; suggestions empty at M1.
- D10: if no archive flag exists, test the invariant via status/facet change ≠ link change (no cascade); add optional `archived` only if needed, additive w/ default.
### Final task list
- T1 parser + resolver + edge persistence (GATING)
- T2 backlinks + ghost auto-resolve + rename-no-rewrite teeth
- T3 D6 merge tombstone + D10 archive-never-orphans
