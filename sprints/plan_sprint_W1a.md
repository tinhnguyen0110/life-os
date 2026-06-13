# Plan — Sprint W1a · M1 Wiki Core foundation (GATING, pure backend)

> First sprint of the Wiki-LLM module. Pure backend, **mock-free → starts immediately** (no waiting on UI mocks).
> Lays the bedrock everything else plugs into: integer-ID notes + md+git/SQLite store + **op-log/single-writer changes-queue** (D3 — the substrate for ALL mutations and the M3 sync foundation).
> Overview approved by user 2026-06-13 (all 4 §6 decisions). Spec: `docs/WIKI-LLM-SPEC.md` §M1 + §6/§7 · Roadmap: `sprints/OVERVIEW_wiki_llm.md`.
> Author: architect · 2026-06-13.

---

## Objective

Stand up `backend/modules/wiki/` as a registry-discovered module with: integer-ID note identity (`47.md`), the md+git + SQLite two-store split, and the **single-writer changes-queue + op-log** through which ALL note mutations flow. CRUD endpoints round-trip through the queue. **No links/FTS/graph yet** (W1b/W1c) — this sprint is identity + store + the mutation substrate, frozen so W1b builds on a stable base.

## Scope

**IN:**
- `modules/wiki/` package, registry-discovered (`MODULE` in `router.py`), mounted at `/wiki`. ZERO edits to `core/` or `main.py`.
- Integer-ID identity: file `<id>.md`, frontmatter `id` + mutable `title` + `aliases` + `status` + `noteType` + `trustTier` + `author` + `tags` + `created`/`updated` + `contentHash`. ID = `MAX(id)+1` from SQLite.
- `modules/wiki/store.py` — md+git note files (source of truth, reuse `store/md_store.py`) + **SQLite cache on the SHARED `store/db.py` connection** (`wiki_`-prefixed tables registered idempotently at module import — see kickoff decision, reversed from wiki.db). W1a tables: `wiki_notes`, `wiki_op_log` (+ a title/alias→id index seam for the W1b ghost-resolver). `CREATE TABLE IF NOT EXISTS` mirroring the time-series pattern, guarded by `_lock` against the scheduler thread.
- **Changes-queue + op-log + single-writer** (`service.py`): every mutation = an op enqueued to ONE in-process FIFO; a single worker applies sequentially → md_store write (1 git commit) → SQLite cache upsert → op_log append. No code path writes a note file outside the queue.
- CRUD endpoints (through the queue): `POST /wiki/notes` (create fleeting) · `GET /wiki/notes/{id}` · `PUT /wiki/notes/{id}` · `DELETE /wiki/notes/{id}`.
- Status state-machine values present (`fleeting`/`developing`/`evergreen`) — stored + editable; the ≥1-link REFINE gate is W1c (no links yet here).
- `reindex_note(path)` stub/seam — content-hash dirty check exists (touch-no-change → no cache rewrite), but full FTS/graph reindex is W1c. Here it just keeps `wiki_notes` + `contentHash` consistent.

**OUT (later sprints — name them so nobody builds ahead):**
- Links / wikilink parser / resolver / backlinks / typed graph → **W1b**
- FTS5 / ego-graph / overview+inbox readers / refine ≥1-link gate → **W1c**
- MCP / post-verify / consolidation pass / proposals → **W2 (M4)**
- Multi-device CRDT / device-prefixed IDs → **W3 (M3)**
- Any Wiki screen (W1/W2/W3/W4/W5) UI → **W1-FE** (needs user mock)
- Vector / global graph → Phase 2

## Logic/Algorithm (architect-specified — implementer does NOT improvise)

### A1 — Integer-ID generation + file layout [D1]
- ID source of truth = SQLite `wiki_notes.id` (INTEGER PRIMARY KEY). New note: `next_id = (SELECT COALESCE(MAX(id),0)+1 FROM wiki_notes)` inside the single-writer (serialized → no race).
- File on disk: `notes/<id>.md` under the wiki data root (md_store DATA_DIR; subdir `wiki/` to keep it separate from other modules' md files → path `wiki/notes/47.md`).
- File format: YAML frontmatter + markdown body.
  ```
  ---
  id: 47
  title: "Knowledge work accretes"
  aliases: []
  status: fleeting          # fleeting | developing | evergreen
  noteType: concept         # concept | literature
  trustTier: verified       # verified (human) | candidate (agent)
  author: human             # human | agent:<name>
  tags: []
  created: 2026-06-13T08:12:00Z
  updated: 2026-06-13T08:12:00Z
  ---
  <markdown body>
  ```
- `contentHash` = sha256 of the **body** (not frontmatter) — so a title/status edit (frontmatter-only) is detectable separately from a body edit (matters for W1c reindex + W2 block-id drift). Store in `wiki_notes.content_hash`, NOT in frontmatter (it's derived cache, not authored).
- Filename NEVER changes (id immutable). Title edit = frontmatter rewrite only.

### A2 — The changes-queue / single-writer [D3, the load-bearing piece]
- One process-level FIFO queue (`queue.Queue` or an asyncio queue) + ONE worker that drains it. All of `create/update/delete` build an `Op` and `enqueue` it, then block on the op's result (a `Future`/`Event`) so the HTTP handler still returns synchronously to the caller.
- `Op` shape: `{op_id, kind: create|update|delete, note_id, payload, actor, ts}`. `actor` ∈ {`human`, `agent:<name>`, `consolidation`} — for W1a everything is `human` (the API has no auth, single user) but the field is recorded so W2/M4 agent writes slot in unchanged.
- Worker applies an op atomically in this order: (1) compute/assign id, (2) `md_store.write_file` (the 1 git commit = durable source of truth), (3) upsert `wiki_notes` cache row, (4) append `wiki_op_log` row. If step 2 (md write) raises → op FAILS CLOSED (raise to caller, nothing partially applied — see `fail-closed-write-fail-soft-addon` memory: a primary write fails closed/visible). Cache/op_log steps after a successful md write should not silently swallow (log + raise).
- **No file locks. No file-watcher daemon in W1a** (single writer already serializes; a watcher is a read-only reindex trigger we add in W1c if needed — not a 4th writer). Keep it simple (no-overengineering): the queue IS the concurrency model.
- Ordering guarantee: ops apply in enqueue order → `wiki_op_log` is a faithful replay log (this is also the M3 sync substrate + the W1 "recent activity" source).

### A3 — op_log schema (this is the episodic/replay log, NOT git history) [open-decision: separate append-only journal]
- `wiki_op_log(seq INTEGER PRIMARY KEY AUTOINCREMENT, op_id TEXT, kind TEXT, note_id INTEGER, actor TEXT, ts TEXT, commit_sha TEXT, detail TEXT)`.
- `kind` enum (W1a subset): `create | edit | delete`. (W1b adds `link/link_candidate`, W1c `refine`, W2 `merge/moc_proposal` — additive, don't constrain now beyond a TEXT column.)
- `commit_sha` = the md_store commit hash for that op (audit trail tying op → git). Delete may have a sha (the removal commit) or null.
- Append-only: never UPDATE/DELETE a row. This is what W1's "recent activity" feed reads.

### A4 — delete semantics (W1a minimal) [D6 full tombstone is W1b]
- `DELETE /wiki/notes/{id}`: remove the md file (md_store delete = 1 commit), mark cache row (soft: `wiki_notes.deleted_at` set, OR hard delete row — **decision: HARD delete the cache row + git commit removes the file**; the op_log retains the `delete` row as the historical record). No links table yet so no inbound-cleanup here — W1b's delete handler extends this to "inbound links become ghost."
- Deleting a non-existent id → 404.

### A5 — content-hash dirty check (touch ≠ rewrite)
- On `PUT`: compute new body sha256. If `new_body_hash == stored content_hash` AND frontmatter unchanged → it's a no-op touch: do NOT write a new git commit, do NOT bump `updated`, return the existing note (200). (md_store.write_file already no-ops on identical content — rely on it but ALSO short-circuit before enqueue to avoid a pointless op_log entry.) If body OR frontmatter changed → real edit: write, bump `updated`, op_log `edit`.

## Schema/field list (FROZEN — backend implements once against this, announces freeze before W1b)

**`Note` (response model, `GET /wiki/notes/{id}`):**
| field | type | default | notes |
|---|---|---|---|
| `id` | int | — | immutable identity |
| `title` | str | "" | mutable; "" allowed for a raw fleeting capture (no title yet) |
| `aliases` | list[str] | `[]` | |
| `status` | Literal[`fleeting`,`developing`,`evergreen`] | `fleeting` | soft mutable |
| `noteType` | Literal[`concept`,`literature`] | `concept` | |
| `trustTier` | Literal[`verified`,`candidate`] | `verified` | human=verified |
| `author` | str | `human` | `human` \| `agent:<name>` |
| `tags` | list[str] | `[]` | |
| `content` | str | "" | markdown body |
| `created` | str (ISO8601) | — | |
| `updated` | str (ISO8601) | — | |
| `contentHash` | str | — | sha256 of body (derived; surfaced for W1c/W2) |

**`NoteCreateInput` (`POST /wiki/notes`):** `content: str = ""` · `title: str = "" (max_length 200)` · `status` default `fleeting` · `noteType` default `concept` · `tags: list[str] = []` · `author: str = "human"`. (Capture = raw dump; title/links come at REFINE.)
**`NoteUpdateInput` (`PUT`):** all of title/content/status/noteType/trustTier/aliases/tags optional (partial update); `field_validator` strips whitespace on title; `title` max_length 200; reject unknown status/noteType via Literal.
**Envelope:** every endpoint returns `core.responses.ok(data=...)` → `{success, data, warning?}`. Errors via `HTTPException` (404 missing note, 422 validation — FastAPI/Pydantic auto).

> Mock reference: matches `docs/WIKI-SCREENS-FEATURES.md` W2 `GET /api/wiki/notes/47` shape (id/title/aliases/status/noteType/trustTier/author/tags/content/created/updated/contentHash). `frontmatter:{raw}` field from the mock is OPTIONAL — skip in W1a (FE doesn't need raw frontmatter for W2; add only if a screen requires it).

## Tasks (3, backend-only, sequential within the sprint)

- **T1 — module scaffold + store + schema (GATING).** Create `modules/wiki/{__init__,router,schema,service,reader,store}.py`. `store.py`: wiki SQLite tables (`wiki_notes`, `wiki_op_log`) idempotent init + md_store path helpers (`wiki/notes/<id>.md`). `schema.py`: the frozen models above. Empty router mounted at `/wiki` (`MODULE` wired). Verify registry auto-discovers it (`GET /wiki/...` reachable, `/health` lists it). **Backend writes its own unit tests for store + schema.**
- **T2 — changes-queue / single-writer + CRUD (the core).** `service.py`: the FIFO queue + single worker (A2), `Op` model, `create_note/get_note/update_note/delete_note` going through the queue, id-gen (A1), content-hash dirty check (A5), op_log append (A3), delete (A4). `router.py`: the 4 CRUD endpoints. **Backend writes unit (queue ordering, id-gen, dirty-check, fail-closed) + API (curl round-trip) tests in T2.**
- **T3 — op_log read seam + reindex seam.** `reader.py`: `recent_ops(limit)` reading `wiki_op_log` (feeds W1's activity later) + `reindex_note(path)` seam keeping `wiki_notes`/`contentHash` consistent (full FTS/graph reindex deferred to W1c — leave a clear seam, don't stub-lie). Co-locate the behavior tests in `test_wiki.py` (memory `test-where-the-reader-greps`).

## Runtime
- BE: canonical stack `docker compose up -d` (DETACHED), BE on `:8686` (memory `dev-server-ports`). Hot-reload from bind-mount — no `--build` for code. Verify on the CONTAINER, `curl localhost:8686/wiki/...` + `/health`.
- No FE this sprint.

## Baseline (regression anchor)
- pytest **674** passed, vitest 383 (FE untouched). New wiki tests are ADDITIVE → expect pytest > 674, vitest unchanged at 383.

## Dependencies
- Available now: `store/md_store.py` (write/read/delete + git), `store/db.py` (get_conn/init_db), `core/base.py` (BaseModule/Routine), `core/responses.py` (ok), the registry. All present + verified.
- Blocks: W1b (links) + W1c (FTS/graph) build directly on this sprint's store + queue → **schema + queue API must FREEZE at end of W1a** (memory `schema-freeze-gate`).

## Exports (for tester pre-scaffold)
- `service.create_note(input) -> Note` · `get_note(id) -> Note|None` · `update_note(id, input) -> Note` · `delete_note(id) -> None` (404 via router).
- `service.enqueue(op) -> result` (the queue entry point) · `Op` model.
- `store.next_note_id() -> int` · `store.upsert_note_cache(note)` · `store.append_op(...)`.
- `reader.recent_ops(limit=50) -> list[dict]`.
- Endpoints: `POST /wiki/notes` · `GET /wiki/notes/{id}` · `PUT /wiki/notes/{id}` · `DELETE /wiki/notes/{id}`.

## Test ownership split
- **Backend** writes unit + API tests in T1/T2/T3 (`test_wiki.py`): store init, id-gen monotonic, queue applies in order, content-hash dirty-check no-ops, fail-closed on md write error, op_log append + replay, CRUD curl round-trips.
- **Tester** scaffolds ONLY the integration/curl round-trip verify + the **behavior-test** of the queue (POST create → GET reflects → PUT edit → GET reflects → op_log has create+edit in order) + DB-state assertions. NOT service unit tests (backend owns those).

## Verification (ONE bar)
- **Pass bar:** create→get→update→delete round-trips through the queue; every mutation produces exactly one git commit + one op_log row in enqueue order; touch-no-change makes NO new commit; id-gen monotonic across creates; delete of missing id → 404; pytest ≥ 674 + 0 errors/unhandled (memory `unhandled-errors-not-green`); module auto-discovered (no core/main.py edit — `git diff` shows only `modules/wiki/**` + tests).
- Gates: **Gate 1 (API)** + **Gate 2 (Function)** apply (Gate 3 at sprint close). Verify on the CONTAINER (`:8686`), not bare-metal.

## Ownership (failing test → report, don't cross-fix)
- pytest failures → backend owns the fix. Tester REPORTS with repro (curl + DB query + op_log dump), never edits source. Schema/queue-contract conflict → architect decides (the dispatch + app convention is authority, memory `run-the-red-before-naming-its-cause`).

## Idle behavior
- Backend: done → SendMessage team-lead with evidence (pytest count + `git log -1 --stat` + a curl round-trip payload + an op_log dump showing ordered ops) + TaskUpdate completed, then idle.
- Blocked → SendMessage team-lead immediately (don't stall silently).

---

## Kickoff — 2026-06-13

### Drift since overview was written
- Specs moved into repo at `docs/WIKI-LLM-SPEC.md` + `docs/WIKI-SCREENS-FEATURES.md` (were parent-dir). Content verified IDENTICAL to what the overview was built on — no spine drift.
- Confirmed against current code: registry discovers `MODULE` from `router.py` (projects' `__init__.py` has no MODULE — fallback path used). Envelope = `core.responses.ok`. `md_store.write_file` returns commit sha + no-ops on identical content (leverage for A5). `db.init_db` is idempotent boot hook; module-local `CREATE TABLE IF NOT EXISTS` is the established pattern for time-series tables → wiki tables follow it in `store.py`.
- There is an existing `notes` module (string-ID, attach-to-project) — wiki is SEPARATE (user-approved new module). No collision: different name (`wiki` vs `notes`), different md subdir (`wiki/notes/` vs notes' path), different tables.

### Plan revisions vs overview
- M1 W1a scoped DOWN to identity + store + queue + CRUD only (links/FTS/graph explicitly OUT → W1b/W1c). The overview's "W1a" bullet already said this; this plan nails the exact endpoints + frozen schema + the 3 logic blocks (A1–A5).
- Added A5 (content-hash dirty check) + A3 (op_log as the episodic journal, the approved open-decision) explicitly — they were implied in the overview, now specified so backend doesn't improvise.

### Final task list
- T1 module scaffold + store + frozen schema (GATING)
- T2 changes-queue/single-writer + CRUD endpoints (the core)
- T3 op_log read seam + reindex seam

### Assumptions logged (→ end_sprint_W1a §Assumptions at close, decide-and-log)
- **op_log = separate append-only SQLite table** (not git history) — git mixes commits + isn't replay-structured (spec open-decision, recommendation taken).
- **No file-watcher daemon in W1a** — single-writer queue already serializes; a read-only reindex watcher is a W1c add only if needed (no-overengineering).
- **Hard-delete cache row on DELETE** (op_log keeps the historical `delete` record); full ID-redirect tombstone (D6) lands in W1b with the links table.
- **contentHash = sha256(body only)**, stored in cache not frontmatter (derived, not authored).

### ARCHITECT DECISIONS — fork + 6 dev questions + backend risks (resolved at kickoff from recon; logged for user async review)
- **SQLite → SHARED `store/db.py` connection** (REVERSED 2026-06-13 from the initial wiki-local-`wiki.db` call, after ground-truthing backend's T1 on disk). Why the reversal: my original fork reason was "keep db.py thuần time-series" — a conceptual-cleanliness argument that does NOT survive the no-overengineering north star. The shared connection is already built for exactly this: `check_same_thread=False` + WAL + a `_lock`, documented for "scheduler thread + request threads share one connection" (proven across 674 tests). The db.py docstring's "ONLY things queried by time" is ORGANIZATIONAL, not a technical constraint — adding `wiki_*` tables (incl. the W1c FTS5 virtual table) to the same file inherits the proven WAL+lock model with FEWER moving parts than a 2nd db file + 2nd connection + 2nd lock + a future ATTACH. The disposability invariant ("files=truth, cache rebuildable-from-md") holds regardless of WHICH file the cache lives in. Backend's instinct was better than my fork. **Decision: SHARED db, accepted.** Caveats locked: (1) wiki tables stay `wiki_`-prefixed so the shared schema stays legible; (2) W1c FTS5 virtual table must coexist cleanly on the shared conn (tester confirms — it will: FTS5 is just another table, doesn't touch time-series tables). How to change: split to wiki.db ONLY if a real measured contention/locking problem appears (none expected single-user). *Process note:* implementer reversed an architect decision without flagging first — outcome is correct so no rework, but next time surface the disagreement via team-lead before coding the opposite. Logged, not penalized.
- **Rename = frontmatter-title change ONLY, NO inbound-link rewrite** [D1]. The overview's "rewrite inbound links" defensive line was STALE — D1 (links point at integer ID `[[47]]`, not title) is the authority and the WHOLE REASON integer-ID was chosen. Teeth-test: rename 100× → all inbound links stay `is_resolved=True`, 0 rewrites. (Links table is W1b; the invariant is asserted there. In W1a, title edit just rewrites that one note's frontmatter.)
- **Q1 — AI-derived fields ship as EMPTY/NULL shape at M1** (no embedded AI; populated at M4 via Claude-Code-over-MCP). `aiSuggest: null`, `suggestions.candidates: []`, `clusters: []`, `proposals: []`. FE contract stays stable (mock has the shape); M4 fills it. (W1a itself has none of these — they're W1b/W1c/M4 endpoints — but the rule is locked now so nobody fabricates AI output.)
- **Q2 — unlinked-mentions = live-compute via FTS each read** (W1b/W1c). No perf gate on backlinks; only the ego-graph has the <1s gate. (Not W1a.)
- **Q3 — trustTier = frontmatter field** (`trustTier: candidate|verified`), not folder/namespace. Clean with single-file integer-ID; op_log already gives audit. (Already in the W1a frozen schema.)
- **Q4 — post-verify is an M4 concern, NOT in M1/W1.** No `/wiki/verify-citation` endpoint in W1. (Citations are verified inside the M4 MCP accept-flow. Tester: nothing to curl in W1 for post-verify.)
- **Q5 — cold-start threshold = CONFIGURABLE** (S12 settings pattern, default **5**). Lives in settings, not hardcoded → tester can test vault=4 waived / vault=6 gate-fires by toggling config, no need to seed 5+ notes. (Gate itself is W1c; the config key is defined now.)
- **Q6 — touch-no-change debounce = SERVICE-LEVEL** (in the update path / dirty-check A5), NOT a file-watcher. Consistent with "no watcher daemon" — the 500ms debounce is on the service reindex call, tester teeth it at the service layer.

### Backend RISKS folded into W1a defensive cases (from backend recon)
- **(a) integer-ID gen MUST be atomic INSIDE the single-writer** — `MAX(id)+1` allocated in the worker, never in the router, or 2 concurrent captures grab the same id. (A1 already says this — reinforced.)
- **(b) wiki-queue ⟂ md_store `_write_lock`** — the wiki changes-queue is the OUTER serialization owning the whole logical op (op-order + op_log append + cache upsert + md write). md_store's internal `_write_lock` is INNER. Don't let them deadlock/fight; wiki queue owns the transaction boundary. A single worker thread draining the queue = no contention.
- **(c) ghost-resolver** = title→id + alias→id index in the wiki cache; on create, auto-resolve any inbound ghost links pointing at the new note's title/alias. (Index lives in cache; the update is part of the writer's cache-upsert step. Full resolver is W1b — in W1a just stand up the index table/columns.)
- **(e) empty-vault derived stats** — `pctWithLink` on 0 notes → return **None + a warning**, NEVER divide-by-zero or a misleading 0 (lesson: avgPeak). (Stats are W1c; the rule is locked now.)
