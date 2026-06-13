# End Sprint W1c — Wiki retrieval (FTS5 + ego-graph + overview/inbox + refine gate) · M1 BACKEND COMPLETE 🎉

> Result doc (CLAUDE.md §3.2). Third + LAST M1 backend sprint. Pure backend, mock-free. After this, the FULL M1 backend contract is frozen → W1-FE screens.
> Author: architect · 2026-06-13 · Commit: `feat(sprint-W1c)` on `main`.

---

## 1. What shipped (`backend/modules/wiki/` + `core/config.py`)

### C1 — FTS5 search (`store.fts_search/fts_upsert/fts_delete`, `reader.search`, `GET /wiki/search`)
- `notes_fts` **PLAIN FTS5** (title/body/aliases/tags, rowid=note id) — NOT contentless (corrected: contentless can't `snippet()`, which search+unlinked need; still disposable/rebuildable-from-md). Synced DELETE+INSERT in the writer's cache-update step; `fts_delete` on delete/merge.
- `GET /wiki/search?q=` → `[{id,title,status,snippet}]` ranked by FTS5 rank, `<b>`-highlighted snippet. **Query sanitized** (`_sanitize_fts_query` + try-guard) → bad/empty q → `[]`, NEVER 500.

### C2 — unlinked-mentions POPULATE (closes the W1b deferral) (`reader.unlinked_mentions`)
- FTS5 phrase-match on a note's title/aliases → candidate sources, EXCLUDE self + already-linked → `backlinks.unlinked[]` `{id,title,snippet}`. The "live-compute via FTS" is now real (was `[]` in W1b by design).

### C3 — ego-graph (`reader.ego_graph`, `GET /wiki/graph?note=X&depth=2`)
- BFS over RESOLVED edges (both directions) to depth∈{1,2}; real nodes `{id,title,status,degree}`; edges `{source,target,type,isResolved}` among the visited set. Ghost links = an edge flag, NOT phantom nodes. `clusters:[]` (deterministic clustering deferred — NO fake AI; M4 does real). Returns None→404 if center absent. **Perf: ego_graph 0.2ms, well under the 200-note <1s gate.**

### C4 — overview stats (`reader.overview`, `GET /wiki/overview`)
- `{stats:{totalNotes,byStatus,totalLinks,orphanCount,ghostLinkCount,pctWithLink,asOf}, inbox, orphans, recentActivity, proposalCount}`. **`pctWithLink` empty-vault → None + warning** (risk-(e), NEVER 0/div-by-zero — avgPeak lesson). orphans = degree-0 notes. recentActivity from op_log mapped. `proposalCount:0` (M4).

### C5 — inbox (`reader.inbox`, `GET /wiki/inbox`) + captureSource
- Fleeting notes oldest→newest `{id,title,status,rawContent,captured,captureSource,linkCount,aiSuggest:null}`. `captureSource` added to NoteCreateInput (additive, default `quick_add`) → stored in frontmatter + a new `capture_source` cache column (idempotent `_migrate` column-guard for a pre-existing db). `aiSuggest:null` (M4).

### C6 — REFINE ≥1-link gate (`service._apply_refine` / `_would_be_link_count`, `POST /wiki/notes/:id/refine`)
- Computes the post-edit link count WITHOUT writing (gate-before-mutate). **3 distinguishing cases:** linkCount≥1 → apply + status flip + op_log `refine`; linkCount==0 AND vault < threshold (cold-start) → ALLOW + warning; linkCount==0 AND vault ≥ threshold → **RefineGateError → 422**. Threshold = `core/config.py wiki_cold_start_min_notes:int=5` (env-overridable Settings field — a plan-directed config addition, NOT registry/main.py wiring; no-core-edit rule intact).

---

## 2. Verification (Rule #0 — architect independent, not relayed)

### Architect §3.1 4-step (read FULL functions, traced runtime)
| Function | Traced | Verdict |
|---|---|---|
| `_apply_refine` + `_would_be_link_count` | gate-before-write; outbound(new body)+resolved-inbound; 3 cases (≥1 apply / 0+coldstart warn / 0+non-coldstart 422) | ✅ correct, no collapse |
| `ego_graph` | depth-clamp {1,2}, BFS resolved-neighbors both dirs, real nodes, ghost=edge-flag, clusters=[], None→404 | ✅ genuine depth-2 traversal |
| `overview` | empty-vault pctWithLink=None+warning, orphans=degree-0, byStatus explicit, proposalCount 0 | ✅ risk-(e) handled |
| `fts_search` + `_sanitize_fts_query` | sanitize upfront + try-guard around MATCH → never 500; empty q→[] | ✅ double-protected |
| `_migrate` | PRAGMA column-check before ALTER (idempotent, handles pre-existing db) | ✅ correct |
| `fts_upsert`/`fts_delete` synced in writer; `_apply_delete`/`_apply_merge` drop fts row | ✅ index stays consistent |

### Suite (architect re-ran independently, full tail per `unhandled-errors-not-green`)
- **`pytest -q` → 853 passed, 6 skipped, 0 failed, 0 errors, 0 unhandled** (baseline 803 → +50).
- **`test_wiki.py` → 147 def == 147 collected** (no shadowed tests — held across W1a/W1b/W1c).
- Container behavior-verified by team-lead (:8686): refine 3-case (0-link>5→422, link→200+flip, cold-start<5→200+warning) · graph depth-2 real (C→B→A: depth1→[A,B], depth2→[A,B,C]) + perf 0.2ms · FTS bad-query×5→200 · unlinked populate real · overview empty→None+warning.
- W1a Note RESPONSE schema UNCHANGED (captureSource lives in frontmatter+cache, NOT the Note model) → W1a freeze intact through 3 sprints.

### Gates — all 3 green (853/0; full functions read; counts ≥ baseline; commit format; out-of-scope flagged).

---

## 3. FULL M1 BACKEND CONTRACT — FROZEN (the W1-FE mirror target)
12 endpoints: `GET /wiki` · `GET /wiki/search` · `GET /wiki/overview` · `GET /wiki/inbox` · `GET /wiki/graph` · `POST /wiki/notes` · `GET/PUT/DELETE /wiki/notes/:id` · `GET /wiki/notes/:id/backlinks` · `POST /wiki/notes/:id/refine` · `POST /wiki/notes/merge`. Envelope `{success,data,warning?}`. Note shape per W1a freeze. AI fields empty/null at M1 (aiSuggest/clusters/proposals/proposalCount — honest-mirror, M4 populates). Matches mock `data-wiki.js`.

---

## 4. Assumptions (user-review — decide-and-log)
- **FTS5 = PLAIN** (title/body/aliases/tags, rowid=id), NOT contentless — `snippet()` is a hard output requirement (search + unlinked); still disposable/rebuildable-from-md, synced DELETE+INSERT in the writer. **Plan §C1 "contentless" SUPERSEDED** (backend flagged the contradiction properly; team-lead decided-A). 
- **pctWithLink empty-vault → None + warning** (never 0/div-by-zero).
- **clusters = `[]` in W1c** — deterministic clustering deferred; NO fake AI (real cluster-detection is M4).
- **refine cold-start threshold configurable** = `core/config.py wiki_cold_start_min_notes=5` (env-overridable; promote to the settings module only if live-toggle wanted).
- **captureSource** added to NoteCreateInput (additive, default `quick_add`); stored frontmatter + `capture_source` cache column (idempotent `_migrate`).
- **FTS index going forward:** any future note text change must keep the fts row synced in the writer (the one mutation path) — it's not auto-maintained by SQLite (plain FTS5 external rowid).
- (carried) shared-db · op_log append-only · no watcher daemon · merge-GET→target+warning · delete-ghostifies-inbound · D10 structural · case-insensitive resolve.

---

## 5. Next — W1-FE (W2 Note view/edit + W3 Inbox screens) — frontend's FIRST Wiki work
M1 backend is COMPLETE → switch to **FE-first-after-freeze**. Dispatch W1-FE: frontend ports W2 (Note view/edit — header/status pill/body editor/backlinks panel linked+unlinked+outbound+ghost/provenance badge) + W3 (Inbox/Refine — fleeting list + refine panel + the ≥1-link hard gate UI + status flip), mirroring this frozen M1 contract + the mock `template/Life Command/app/screens-wiki.js` + `data-wiki.js` + `wiki.css`. Render-only for AI-derived fields (aiSuggest/suggestions empty at M1 — show the empty state, don't fabricate). New FE components: WikiLinkRenderer + markdown viewer/editor + BacklinksPanel (per frontend recon). W4 graph + W5 MOC + P1 proposal-queue = later. Write-form round-trip verify (memory `write-form-roundtrip-verify`) on the refine submit.
