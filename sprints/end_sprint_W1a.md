# End Sprint W1a — Wiki Core foundation (M1: integer-ID notes + op-log/single-writer + CRUD)

> Result doc (CLAUDE.md §3.2). First sprint of the Wiki-LLM module. Pure backend, mock-free. The GATING foundation everything in M1/M3 plugs into.
> Author: architect · 2026-06-13 · Commit: `feat(sprint-W1a)` on `main`.

---

## 1. What shipped

### Backend — new module `backend/modules/wiki/` (registry auto-discovered, ZERO core/main.py edits)
- **`schema.py`** — FROZEN models: `Note` (11 fields: id/title/aliases/status/noteType/trustTier/author/tags/content/created/updated/contentHash) + 3 Literal-locked enums (Status fleeting|developing|evergreen · NoteType concept|literature · TrustTier verified|candidate) + `NoteCreateInput` + `NoteUpdateInput` (partial, whitespace-strip title, max_length 200). FE/tester mirror this verbatim from W1b on.
- **`store.py`** — two-store layer: md+git note files `DATA_DIR/wiki/notes/<id>.md` (source of truth, 1 commit/write via `md_store`) + SQLite cache on the **SHARED `store/db.py` connection** (`wiki_notes` + `wiki_op_log`, `wiki_`-prefixed, idempotent `CREATE TABLE IF NOT EXISTS` at import, `_lock`-guarded against the scheduler thread). `next_note_id()` = `MAX(id)+1` (collision-free inside the single writer). `append_op`/`recent_ops` (append-only op_log). md read/write/delete pass-throughs.
- **`service.py`** — THE single-writer changes-queue (D3): one `queue.Queue` + one daemon worker draining sequentially; HTTP handler enqueues an `Op` + blocks on a `threading.Event`, worker exception re-raised (fail-closed). Apply order per op: assign-id → md write (1 commit, fail-closed) → cache upsert → op_log append. CRUD (`create/get/update/delete_note`). A5 content-hash dirty-check (no-op touch → no commit/no `updated` bump/no op_log row). A4 delete (md remove + hard-delete cache + op_log keeps record).
- **`reader.py`** — `recent_ops` read seam (W1 activity feed later) + `reindex_note` seam (full FTS/graph reindex deferred W1c — honest seam, not a stub-lie).
- **`router.py`** — `/wiki` mount + `MODULE`; `GET /wiki`, `POST /wiki/notes`, `GET/PUT/DELETE /wiki/notes/{id}`; envelope `core.responses.ok`; 404 via `NoteNotFound`→HTTPException, 422 auto.

### Quick-fix (§3.4, batched) — `tests/test_projects.py` 2 fragile asserts
- `test_outboundos_*` hardcoded `health=="act"` but OutboundOS's last commit aged past the act(≤7d) window → `slow`. Changed to relative-age expectation (same class as the ClaudeManager ~29d fix). NOT a wiki change; folded in to land the suite on a clean 0-fail baseline.

---

## 2. Verification (Rule #0 — independent, not relayed)

### Architect §3.1 4-step (read FULL functions, traced runtime, not just diff)
| File | Reviewed | Verdict |
|---|---|---|
| `service.py` | single-writer queue (lazy idempotent worker start, double-checked lock) · enqueue+block+re-raise (fail-closed) · `_apply_create/update/delete` · A5 dirty-check · A1 id-gen on worker thread | ✅ faithful to A1–A5; fail-closed correct; op_log NOT appended on a failed md write (no phantom log) |
| `store.py` | shared-conn `_lock`-guarded statements · parametrized SQL · upsert ON CONFLICT · hard-delete · append-only op_log · id-gen warns "inside writer only" | ✅ clean; correct shared-conn locking vs scheduler thread |
| `router.py` | MODULE wired · envelope · 404 mapping · int path param (→422 on non-int) | ✅ correct HTTP shape + status codes |
| `reader.py` | recent_ops + reindex seam | ✅ honest seam, deferral documented (not a lie) |

### Suite (architect re-ran independently, full tail per `unhandled-errors-not-green`)
- **`pytest -q` → 754 passed, 6 skipped, 0 failed, 0 errors, 0 unhandled** (baseline 674 → +80; wiki +49 additive). NOT just "N passed" — read the full tail, genuinely clean.
- Container behavior-verified by team-lead (:8686): create id=1→GET→PUT(status flip + body+contentHash change, created preserved, updated bumped)→DELETE→GET 404 · no-op PUT → `updated` NOT bumped (A5) · each write = 1 ordered git commit w/ real sha · concurrent-creates test (10 threads → 10 unique ids — risk-(a) neutralized).
- `git diff --cached` confirmed to EXCLUDE `backend/data/` (md_store runtime repo) — explicit-path staging, never `git add -A` (memory `commit-never-stage-data-dir`).

### Gates (CLAUDE.md §3.6)
- **Gate 1 (API):** ☑ Literal enums + max_length + whitespace validator · ☑ integration/behavior test for endpoints · ☑ existing tests pass · ☑ module auto-discovered (no core/main.py edit) · ☑ `{success,data}` envelope · ☑ 404/422 codes (no auth — single-user). 
- **Gate 2 (Function):** ☑ unit tests assert behavior (queue order, id-gen, dirty-check, fail-closed) · ☑ existing pass · ☑ edge cases (missing→404, malformed→None, no-op touch) · ☑ fail-closed explicit · ☑ types complete · ☑ no self-confirming asserts · ☑ suite 0 errors/unhandled.
- **Gate 3 (Sprint):** ☑ this doc w/ verified counts · ☑ architect read full functions · ☑ suite 754/0 (≥baseline) · ☑ out-of-scope flagged (below) · ☑ commit format.

---

## 3. Risks / findings (out-of-scope, flagged for later)
- **id-reuse after delete (conscious deferral → W1b):** `next_note_id()=MAX(live id)+1` + hard-delete means a deleted id can be reused. The full **D6 ID-redirect tombstone** (so a cited-then-deleted note's citations auto-follow) lands in W1b WITH the links table — it has no value until links/citations exist. This is per-plan A1+A4, NOT a missed edge.
- **GET returns 404 on a malformed file** (not 500) — acceptable: a malformed note md is effectively "not a valid note." If we ever want to distinguish, add a 422-on-corrupt path later.
- **`reindex_note` is a seam** (keeps cache/contentHash consistent) — full FTS5 + graph reindex is W1c. Documented as a seam, does not claim to reindex FTS yet.
- Unrelated modified `template/Life Command/**` files present in the working tree (not W1a, not staged) — left untouched; flagged so they're not swept into this commit.

---

## 4. Assumptions (user-review — decide-and-log)
- **SQLite = SHARED `store/db.py` connection** (REVERSED from the initial wiki-local `wiki.db` call). Why: the shared conn is already WAL+`_lock`+multithread-proven (674 tests); a 2nd db/connection/lock + future ATTACH is more moving parts → violates the no-overengineering north star. Cache disposability ("rebuildable-from-md") holds either way. *How to change:* split to wiki.db only if a real measured contention problem appears (none expected, single-user).
- **op_log = separate append-only SQLite table** (`wiki_op_log`), NOT git history — git mixes commits + isn't replay-structured.
- **No file-watcher daemon** — the single-writer queue serializes; a read-only reindex watcher is a W1c add only if needed.
- **Hard-delete cache row on DELETE** — op_log keeps the historical `delete`; full ID-redirect tombstone (D6) is W1b.
- **contentHash = sha256(body only)** — stored in cache, not frontmatter (derived, not authored); lets a frontmatter-only edit be distinguished from a body edit.
- **id-reuse-after-delete** acceptable in W1a (no citations yet); tombstone protection arrives W1b with links.
- **trustTier = frontmatter field** (not folder/namespace); **AI-derived fields = empty/null at M1** (populated at M4 via Claude-Code-over-MCP); **cold-start ≥1-link threshold configurable** (default 5, lands W1c); **touch-debounce service-level**, not a watcher.

> Process note: the shared-db decision was initially the implementer's silent reversal of the architect's wiki.db call (caught by team-lead's Rule#0 disk-read); architect ground-truthed + agreed on merits. Lesson logged in memory `implementer-flag-before-reversing-decision` (surface a disagreement before coding the opposite).

---

## 5. Next — W1b (links/backlinks/typed-graph + D6 tombstone)
Dispatch W1b after this push: `[[47|title]]` parser + `[[Title]]`→id resolver + ghost-link auto-resolve-on-create + `links` typed-edge table + backlinks (linked + unlinked mentions, live-compute via FTS) + **D6 ID-redirect tombstone** on merge/delete + **D10 archive-never-orphans** constraint+test + the rename-no-rewrite invariant teeth-test (D1). Builds directly on this sprint's frozen schema + queue.
