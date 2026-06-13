# End Sprint W1b — Wiki links (parser + resolver + backlinks + ghost auto-resolve + D6 tombstone + D10)

> Result doc (CLAUDE.md §3.2). Second M1 sprint. Pure backend, mock-free. Builds the link graph over W1a's note store (`5124de9`).
> Author: architect · 2026-06-13 · Commit: `feat(sprint-W1b)` on `main`.

---

## 1. What shipped (all in `backend/modules/wiki/`, on the W1a single-writer queue)

### B1 — wikilink parser (`service.parse_wikilinks`)
- Regex over `[[...]]`: 4 forms `[[47]]` · `[[47|disp]]` · `[[Title]]` · `[[Title|disp]]`. All-digit inner token = id link; else title link. Dedup by normalized key (id / lowercased title), first display wins. Empty `[[]]` skipped. NO inline typed-link syntax (edge type set via API later, default `relates`).

### B2 — resolver + edge persistence (`service._derive_links`, `store.resolve_title`)
- On every note write (create/update through the queue, after md write + cache upsert): re-derive THIS note's outbound edges (parse → resolve → `replace_links` — idempotent full replace). `[[Title]]`→id via `wiki_aliases` + `idx_wiki_notes_title` (the W1a seams, now populated), **case-insensitive**. Collision (2 notes same title) → lowest id + logged warning. `wiki_links` typed-edge table (`source_id, target_id, target_title, type DEFAULT relates, is_resolved`).

### B3 — backlinks (`reader.backlinks`, `GET /wiki/notes/:id/backlinks`)
- `{linked, unlinked, outbound}`. **linked** = inbound resolved edges + source title + `_mention_snippet` (body text around the `[[id]]`). **outbound** = this note's edges (resolved→`{id,title,isResolved}`, ghost→`{ghost,isResolved:false}`). **unlinked = `[]`** — shape present, deferred to W1c (see §4). Matches mock `data-wiki.js backlinks`.

### B4 — ghost links + auto-resolve-on-create (`service._resolve_ghosts_for`, `store.resolve_ghosts_to`)
- `[[Title]]` with no match → unresolved edge (`target_id=NULL`, `target_title`, `is_resolved=False`). On create/rename, any ghost whose `target_title` matches the new note's title/alias (case-insensitive) flips to resolved + `target_id`. Runs after the alias-index refresh in the writer.

### B5 — D6 ID-redirect tombstone (`service._apply_merge` / `resolve_note`, `POST /wiki/notes/merge`)
- `merge {sourceId,targetId}` through the queue: validate differ (MergeError→422) + both exist (NotFound→404) → delete source (md+cache+its aliases/edges) → `wiki_redirects(old→new)` → repoint inbound (`UPDATE wiki_links target_id old→new`) → op_log `merge` w/ repointed count.
- **Citation-preserving GET:** `resolve_note` follows a tombstone → a merged-away id returns the TARGET note + `warning:"note #old merged into #new"` (HTTP 200, NOT 404). Chained redirects followed, **depth-capped (10) + cycle-guarded** (`follow_redirect`).
- Plain delete (not merge): inbound links **ghostified** (keep deleted title so a re-created note auto-resolves) — NOT dangling, NOT redirected. The two destructive ops are correctly distinguished.

### B6 — D10 archive-never-orphans (structural)
- No code path that changes status/facet touches `wiki_links` — concept edges independent of PARA state by construction. Teeth-test asserts a linked note's edges survive a status/facet change.

---

## 2. Verification (Rule #0 — architect independent, not relayed)

### Architect §3.1 4-step (read FULL functions, traced runtime)
| Function | Traced | Verdict |
|---|---|---|
| `parse_wikilinks` | 4 forms, dedup, empty-skip, no type-syntax | ✅ correct |
| `_derive_links` | full-replace idempotent, id-resolved-iff-exists, title collision→lowest+warn | ✅ correct |
| `_apply_merge` | validate→delete source→redirect→repoint inbound→op_log | ✅ correct |
| `resolve_note` + `follow_redirect` | live/tombstone/absent branches; **depth-cap 10 + `seen` cycle guard** (A→B→A won't hang) | ✅ verified the cap exists |
| `_apply_delete` | ghostify inbound (not dangling), distinct from merge's repoint | ✅ correct distinction |
| `_resolve_ghosts_for` / `_mention_snippet` | ghost flip on title/alias match; snippet around `[[id]]` | ✅ correct |
| `router` | GET uses `resolve_note` (surfaces warning); merge 422/404 mapping | ✅ correct HTTP shape |

### Suite (architect re-ran independently, full tail per `unhandled-errors-not-green`)
- **`pytest -q` → 803 passed, 6 skipped, 0 failed, 0 errors, 0 unhandled** (baseline 756 → +47 wiki additive).
- **`test_wiki.py` → 97 collected == 97 `def test_` lines** (no shadowed/duplicate-name tests — W1a lesson applied).
- Container behavior-verified by team-lead (:8686): merge A→B → GET A → HTTP 200 + note B + warning (citation survives) · rename → 0 link breaks (D1) · ghost→create-target→auto-resolve (B4).
- Frozen W1a Note RESPONSE schema UNCHANGED (only +tables +MergeInput) → W1a freeze intact; FE/tester mirror still valid.

### Gates (CLAUDE.md §3.6)
- **Gate 1 (API):** ☑ MergeInput Literal/int validation · ☑ backlinks+merge integration/behavior tests · ☑ existing pass · ☑ auto-discovered (no core edit) · ☑ envelope+warning · ☑ 404/422 (merge same-id→422, absent→404; no auth).
- **Gate 2 (Function):** ☑ unit tests assert behavior (parse forms, resolve, ghost flip, merge repoint, redirect-follow, D10 invariant) · ☑ existing pass · ☑ edge cases (self/circular link, empty `[[]]`, chained+cyclic redirect, collision) · ☑ fail-closed via queue · ☑ types · ☑ no self-confirming asserts · ☑ 0 errors/unhandled.
- **Gate 3 (Sprint):** ☑ this doc + verified counts · ☑ architect read full functions · ☑ 803/0 ≥ baseline · ☑ out-of-scope flagged · ☑ commit format.

---

## 3. Risks / findings (flagged)
- **id-link to a non-existent/deleted note → "ghost by id-string"** (`target_title=str(id)`, unresolved). It can't auto-resolve via title-match (B4 resolves by title), so an `[[47]]` to a deleted #47 stays ghost until that exact id is recreated. Acceptable for W1b (id reuse is rare + tombstones handle the merge case); noted for W1c/W2 if it matters.
- **unlinked-mentions = `[]`** (deferred W1c) — see §4. NOT a dropped feature; tester must not fail W1b on empty `unlinked`.
- **Title uniqueness not hard-enforced** — collision resolves to lowest id + warning (titles SHOULD be unique per Matuschak but we don't reject). Fine for single-user.
- Unrelated modified `template/Life Command/**` files + untracked `sprints/OVERVIEW/ROADMAP/end_sprint_0` in the working tree — NOT staged (explicit-path commit, as W1a).

---

## 4. Assumptions (user-review — decide-and-log)
- **Edge `type` defaults `relates`; NOT parsed from inline body syntax** — mock bodies use plain `[[id|title]]`; typed edges (supports/contradicts/…) set via explicit API later. Don't invent `[[supports::x]]`. *Change:* add a typing API/UI in W1c/W2.
- **`[[Title]]`→id resolution case-insensitive** (COLLATE NOCASE); collision → lowest id + warning.
- **unlinked-mentions: shape present (`unlinked:[]`) but EMPTY in W1b; live-FTS populate at W1c** (FTS5 sprint). Deferred-by-design (unlinked = full-text scan = needs FTS5; brute LIKE now = anti-no-overengineering). **Tester: empty `unlinked` is NOT a dropped feature — real teeth at W1c.**
- **Merge GET on a tombstone → target note + warning, NOT 404** (citations survive); chained redirects followed, depth-capped 10 + cycle-guarded.
- **Plain delete ghostifies inbound** (keep title for re-create auto-resolve), distinct from merge's repoint. Closes W1a's id-reuse-after-delete concern: a deleted note's inbound become ghost, not dangling.
- **D10 archive-never-orphans is STRUCTURAL** (no cascade from status/facet to links) — no separate archive flag added in W1b; the invariant is tested via status/facet change ≠ link change.
- **id-link to deleted note = ghost-by-id-string** (can't title-auto-resolve) — accepted W1b.

---

## 5. Next — W1c (FTS5 + ego-graph + overview/inbox readers + refine gate) — last M1 backend sprint
Dispatch W1c after push: FTS5 full-text (`notes_fts`) + `GET /wiki` search + **unlinked-mentions populate** (the deferred B3 piece, 1-query add on FTS5) + ego-graph `GET /wiki/graph?note=X&depth=2` (nodes/edges/clusters, <1s gate) + overview stats reader (`GET /wiki/overview`: totals/byStatus/orphan/ghost/pctWithLink — empty-vault → None+warning, not div-by-zero) + inbox reader + **refine ≥1-link hard gate** (`POST /wiki/notes/:id/refine`, 422 if linkCount==0 unless cold-start; threshold configurable default 5). Then W1-FE (W2 note + W3 inbox screens, bám mock). Builds on W1b's frozen `wiki_links`.
