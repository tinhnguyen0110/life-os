# Plan — Sprint W1c · M1 retrieval (FTS5 + ego-graph + overview/inbox readers + refine gate)

> Third + LAST M1 backend sprint. Pure backend, mock-free → runs on top of W1a+W1b frozen base (`67f2924`).
> Adds the read/retrieval surfaces every Wiki screen consumes: full-text search, the deferred unlinked-mentions, the ego-graph, vault overview stats, the inbox, and the REFINE ≥1-link hard gate. After this, M1 backend is complete → W1-FE screens.
> Spec: `docs/WIKI-LLM-SPEC.md` §M1 + §2 (workflows) + D9 · Mock: `template/Life Command/app/data-wiki.js` (`stats`/`graph`/`inbox`/`orphans`/`recentActivity` shapes). Author: architect · 2026-06-13.

---

## Objective

Stand up the retrieval + overview layer over W1a/W1b: FTS5 full-text index, search endpoint, **populate the W1b-deferred unlinked-mentions** (now that FTS5 exists), the ego-graph build (1–2 hop, <1s gate), the vault-overview stats reader, the inbox reader, recent-activity from the op-log, and the **REFINE ≥1-link hard gate** (D9, configurable cold-start exception). All read paths; refine is a mutation through the W1a queue. Completes M1 backend — the FE↔BE contract for W1/W2/W3/W4 is fully frozen after this.

## Scope

**IN:**
- **FTS5 index** `notes_fts` (contentless/external-content over `wiki_notes`+body) on the SHARED conn; rebuild-from-md (disposable cache). Indexed on title + body + aliases + tags. Kept in sync in the writer's cache-update step (C1).
- **Search** `GET /wiki/search?q=...` (or `GET /wiki?q=` per mock) → `[{id, title, snippet, status}]` ranked by FTS5 rank (C1).
- **Unlinked-mentions populate** (the W1b-deferred B3 piece): for a note, find notes whose body contains its title/alias as text but DON'T link it → via FTS5 MATCH on the title/alias terms, minus the already-linked set (C2). Fills `backlinks.unlinked`.
- **Ego-graph** `GET /wiki/graph?note=X&depth=2` → `{center, nodes:[{id,title,status,degree}], edges:[{source,target,type,isResolved}], clusters:[{label,noteIds,density,mocSuggestion}]}`. Degree from edge counts; clusters = a simple density heuristic (C3). **Gate: 200-note ego-graph <1s.**
- **Overview stats** `GET /wiki/overview` → `{stats:{totalNotes,byStatus,totalLinks,orphanCount,ghostLinkCount,pctWithLink,asOf}, inbox:[...], orphans:[...], recentActivity:[...], proposalCount}` (C4). Empty-vault: `pctWithLink` 0 notes → **None + warning** (risk-(e), NOT div-by-zero).
- **Inbox reader** `GET /wiki/inbox` → fleeting notes awaiting triage `[{id,title,status,rawContent/snippet,captured,captureSource,linkCount,aiSuggest:null}]` (C5). `aiSuggest:null` (no embedded AI — M4).
- **REFINE ≥1-link hard gate** `POST /wiki/notes/:id/refine {title,content,status,tags}` through the queue → flips status, but **422 if the note would have 0 links AND vault not in cold-start** (D9). Cold-start: `totalNotes < settings.wiki_cold_start_min_notes` (default 5, configurable) → gate WAIVED + a warning (C6).
- **Recent-activity** from op_log (already have `recent_ops` from W1a) → mapped to `{ts,op,actor,noteId,noteTitle,detail}` (C4).
- **Settings:** add `wiki_cold_start_min_notes: int = 5` to `core/config.py` (env-overridable, mirrors `claude_usage_cap`).

**OUT (later — name them):**
- AI fields: `aiSuggest` (inbox), `suggestions.candidates`, `clusters.mocSuggestion` AI-detected, `proposals` → **empty/null at M1** (no embedded AI; M4 populates). `proposalCount: 0`. Clusters = a deterministic density heuristic, NOT AI.
- MCP / post-verify / consolidation → W2.
- MOC workspace (W5) + Proposal queue (P1) → later (need M4 agent write-back).
- All Wiki SCREENS (W1/W2/W3/W4) UI → W1-FE.
- `^block-id` lifecycle → W2.

## Logic/Algorithm (architect-specified — implement exactly)

### C1 — FTS5 index + search
- `CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(title, body, aliases, tags)` on the shared conn (FTS5 is stdlib), **rowid = note id**. **PLAIN FTS5, NOT contentless** — CORRECTED 2026-06-13 (backend flagged + team-lead decided-A): a contentless (`content=''`) table CANNOT `snippet()`, but search + unlinked-mentions both NEED snippets → plain FTS5 is required. It is STILL disposable/rebuildable-from-md (the actual principle — the md file stays source-of-truth; this table can be dropped + rebuilt), just stores a copy of the indexed text so snippet() works. (Contentless + manual snippet-slicing = a 2nd code path + md re-read per hit = anti-no-overengineering — rejected.) On every note write (create/update in the writer's cache-update step), DELETE the note's fts row + INSERT fresh (rowid=note id). On delete/merge, DELETE the fts row.
- Search: `SELECT rowid, snippet(notes_fts,...) FROM notes_fts WHERE notes_fts MATCH :q ORDER BY rank LIMIT N` → join `wiki_notes` for title/status. Sanitize `q` (FTS5 query syntax can throw on bad input → wrap in quotes / catch + fall back to a prefix match; never 500 on a weird query). Empty `q` → empty list (not all-notes).

### C2 — unlinked-mentions (the W1b deferral, now via FTS5)
- For note N (title T, aliases A): FTS5 MATCH on the phrase(s) T/A → candidate source notes. EXCLUDE: N itself + notes already in N's linked-mentions (those that `[[N]]`). The remainder = unlinked mentions → `{id, title, snippet}` (snippet = FTS5 snippet around the term).
- Phrase match: search the title as a quoted phrase (`"knowledge work accretes"`) to avoid matching each word separately. Aliases too.
- Cap the result (e.g. top 20 by rank) — unlinked is a hint, not exhaustive.

### C3 — ego-graph (1–2 hop, <1s gate)
- Input `note=X, depth∈{1,2}`. BFS from X over `wiki_links` (both directions — in+out edges) to `depth` hops. Nodes = visited notes `{id,title,status,degree}` (degree = total edges touching that note, from a count query). Edges = the `wiki_links` rows among the visited set `{source,target,type,isResolved}`. Include ghost edges (isResolved=false) as edges to a ghost node? → **resolved edges only between real nodes in W1c; ghost edges shown as a flag on the source, not a phantom node** (keep graph clean; mock shows ghost nodes but that's a W4-FE rendering choice — backend returns real nodes + an `isResolved` edge flag, FE renders ghosts).
- **Performance (the <1s gate):** bound by depth-2 BFS + a single edges-in-set query. For 200 notes this is well under 1s with the `idx_wiki_links` indexes. Don't load the whole graph — only the ego neighborhood.
- Clusters: a SIMPLE deterministic heuristic (NOT AI) — e.g. connected dense sub-groups within the ego set by edge density; `mocSuggestion` flag when density > threshold. Keep minimal; AI cluster-detection is M4. If too fuzzy to do deterministically well, ship `clusters: []` (honest — don't fake AI clustering).

### C4 — overview stats + recent activity
- `totalNotes` = COUNT(wiki_notes). `byStatus` = GROUP BY status. `totalLinks` = COUNT(wiki_links WHERE is_resolved). `orphanCount` = notes with degree 0 (no in/out resolved edges). `ghostLinkCount` = COUNT(wiki_links WHERE NOT is_resolved). **`pctWithLink`** = notes-with-≥1-link / totalNotes × 100 → **if totalNotes==0 → None + warning "empty vault"** (risk-(e), NEVER 0 or div-by-zero). `asOf` = now ISO.
- `orphans` = notes degree 0 OR stale `[{id,title,status,degree,lastTouched}]`.
- `recentActivity` = `recent_ops(limit)` mapped to `{ts,op,actor,noteId,noteTitle,detail}` (join wiki_notes for title; a merged/deleted note's title may be absent → use op_log detail).
- `proposalCount: 0` (M4).

### C5 — inbox reader
- `GET /wiki/inbox` → notes WHERE status='fleeting', oldest→newest `[{id,title,status,rawContent(snippet of body),captured(=created),captureSource,linkCount,aiSuggest:null}]`. `captureSource`: stored at create if provided, else default `command_bar`/`quick_add` — **add `captureSource` to NoteCreateInput?** It's in the mock inbox. **DECISION: add optional `captureSource` to NoteCreateInput (default "quick_add"), additive** — store in frontmatter + cache. `linkCount` from wiki_links count. `aiSuggest: null` (M4).

### C6 — REFINE ≥1-link hard gate (D9)
- `POST /wiki/notes/:id/refine {title?,content?,status?,tags?}` through the queue (it's a mutation → an update variant). Computes the note's link count AFTER applying the refine edit (the new body's outbound links + existing inbound). **If linkCount == 0:** check cold-start: `totalNotes < settings.wiki_cold_start_min_notes (5)` → ALLOW + `warning: "cold-start: refined without a link (vault < N notes)"`. Else → **422 "refine requires ≥1 link"** (the hard gate). If linkCount ≥ 1 → apply normally (status flip etc.).
- Refine is essentially `update_note` + the gate + a `refine` op_log kind. Reuse the update path; add the gate + op kind.

## Schema/field list (additive — FROZEN at W1c close = the COMPLETE M1 backend contract for W1-FE)
- **New table:** `notes_fts` (FTS5 virtual). No new persistent columns on wiki_notes EXCEPT optional `capture_source TEXT DEFAULT 'quick_add'` (C5).
- **NoteCreateInput += `captureSource: str = "quick_add"`** (additive, optional — mock inbox needs it).
- **Responses** (match mock `data-wiki.js`): `/wiki/overview` (stats+inbox+orphans+recentActivity+proposalCount), `/wiki/graph` (center+nodes+edges+clusters), `/wiki/inbox` (items[]), `/wiki/search` ([{id,title,snippet,status}]), `/wiki/notes/:id/refine` (the updated Note + optional warning). `backlinks.unlinked` now POPULATED.
- AI fields everywhere → empty/null (`aiSuggest:null`, `clusters:[]` or heuristic-only, `proposalCount:0`).
- **Note RESPONSE schema** stays as W1a froze (+ contentHash etc.) — do not break it.

## Tasks (3, backend-only)
- **T1 — FTS5 + search + unlinked-mentions (GATING).** notes_fts virtual table + sync in writer + `GET /wiki/search` (C1) + populate `backlinks.unlinked` via FTS (C2). Query sanitization (no 500 on bad q). Tests: index sync on write/delete, search rank, unlinked excludes self+linked, bad-query no-crash.
- **T2 — ego-graph + overview/inbox readers.** `GET /wiki/graph` (C3, <1s gate) + `GET /wiki/overview` (C4, empty-vault None) + `GET /wiki/inbox` (C5) + recent-activity mapping. Tests: ego BFS depth 1/2, degree, 200-note <1s perf, empty-vault pctWithLink=None+warning, inbox fleeting-only.
- **T3 — refine ≥1-link gate + captureSource.** `POST /wiki/notes/:id/refine` (C6) + cold-start config + `captureSource` on create. Tests: refine w/ link → ok+status flip, refine 0-link non-cold-start → 422, refine 0-link cold-start (vault<5) → ok+warning, config threshold toggle (vault=4 waived / vault=6 gated WITHOUT seeding 5 notes — set the config).

## Runtime / Baseline / Deps / Exports / Test split / Verification / Ownership / Idle
- **Runtime:** docker compose up -d (detached); BE **:8686**; verify on container (`curl :8686/wiki/overview`, `/wiki/graph?note=1&depth=2`, `/wiki/search?q=...`).
- **Baseline:** pytest **803** (post-W1b), vitest 383. Additive → expect >803, 0 fail/error.
- **Deps:** W1a+W1b frozen base (`67f2924`): queue, wiki_notes, wiki_links, wiki_redirects, recent_ops, resolve_title. FTS5 in stdlib sqlite3. Blocks: W1-FE screens build on the W1c-frozen contract → freeze ALL endpoints at W1c close + announce (the full M1 backend contract).
- **Exports (tester):** `reader.search(q)` · `reader.unlinked_mentions(id)` · `reader.ego_graph(id,depth)` · `reader.overview()` · `reader.inbox()` · `service.refine_note(id,inp)` · endpoints GET /wiki/search · /wiki/graph · /wiki/overview · /wiki/inbox · POST /wiki/notes/:id/refine.
- **Test split:** backend writes unit/API in T1/T2/T3 (`test_wiki.py`). Tester scaffolds: the <1s graph PERF teeth + the refine-gate BEHAVIOR (verify-with-distinguishing-case: 0-link-non-coldstart 422 vs 0-link-coldstart ok vs ≥1-link ok — 3 divergent cases) + empty-vault None teeth + unlinked-populate behavior — NOT backend's reader unit tests.
- **Verification (ONE bar):** FTS sync on every write/delete · search ranks + no-500 on bad q · unlinked excludes self+already-linked · ego-graph depth 1/2 correct + 200-note <1s · overview stats correct + empty-vault None+warning (not 0/div-zero) · inbox fleeting-only · refine gate: ≥1-link ok / 0-link+non-coldstart 422 / 0-link+coldstart ok+warning · pytest ≥803 + 0 errors · all mutations through queue. Gates 1+2 per task, Gate 3 at close.
- **Ownership:** pytest fail → backend; tester reports w/ repro; contract conflict → architect (flag, don't silently change — memory implementer-flag-before-reversing-decision).
- **Idle:** task done → SendMessage team-lead w/ evidence (pytest count + git stat + curl /overview + /graph payloads + the 3 refine-gate cases) + TaskUpdate. Blocked/disagree → SendMessage FIRST.

---

## Kickoff — 2026-06-13
### Drift check
- Base STABLE at `67f2924` (W1b). wiki_links/wiki_redirects/wiki_aliases all present + frozen. recent_ops + resolve_title available. FTS5 confirmed in stdlib (no dep add).
- Mock-diff (`data-wiki.js` stats/graph/inbox/orphans/recentActivity vs scope): W1c covers ALL of them. AI-derived sub-fields (aiSuggest, clusters.mocSuggestion as AI, proposals) → empty/null at M1 (logged, honest-mirror — tester: NOT dropped, deferred to M4). unlinked-mentions now POPULATED (the W1b deferral closes here).
### Decisions (decide-and-log → end_sprint_W1c §Assumptions)
- FTS5 = **PLAIN** (title/body/aliases/tags, rowid=note id), NOT contentless (CORRECTED — contentless can't snippet(), which search+unlinked need; still disposable/rebuildable-from-md). Query sanitized (bad q → fallback/empty, never 500).
- Ego-graph returns REAL nodes + `isResolved` edge flag; ghost links are a flag, NOT phantom nodes (FE renders ghost visuals). clusters = deterministic density heuristic OR `[]` if not cleanly doable (NO fake AI clustering — M4 does real clustering).
- pctWithLink empty-vault → None + warning (risk-(e)).
- `captureSource` added to NoteCreateInput (additive, default "quick_add") — mock inbox needs it.
- Cold-start threshold = `core/config.py wiki_cold_start_min_notes=5` (env-overridable; promote to the settings module only if user wants live-toggle).
- refine = update-path + ≥1-link gate + `refine` op kind.
### Final task list
- T1 FTS5 + search + unlinked-mentions populate (GATING)
- T2 ego-graph + overview/inbox readers
- T3 refine ≥1-link gate + captureSource
