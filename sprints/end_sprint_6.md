# End Sprint 6 — Notes (S10) [4th backend module, md_store write+git path end-to-end]

> Result doc (CLAUDE.md §3.2). The `notes` module: markdown CRUD via md_store (every write = 1 git commit, the AI-readable shared source), attach to project/finance-channel/standalone, tag + substring search, pin. + the S10 Notes screen. Exercises md_store's write+delete+git path end-to-end on a fresh module.
> Author: architect · 2026-06-06 · Commit: `feat(sprint-6)` on `main`.

---

## 1. What shipped

### Backend — `notes` module (registry auto-discovered, NOT a core edit)
- **`schema.py` (FROZEN)** — `Note{id,title,body,tags[],pinned,attach{type,ref},createdAt,updatedAt}` + `NoteInput{title(min1/max200),body,tags[],pinned,attach}`. `AttachType = Literal["project","channel","none"]`. `model_validator` enforces **ref required when attach.type≠none** (→ 422). id/timestamps server-set.
- **`service.py`** — notes stored as `notes/<id>.md`: YAML front-matter + markdown body. id = `slug(title)-<6hex>` (fallback `note-<6hex>`). Every write/delete = 1 md_store git commit. `list_notes(q,tag,attached,pinned)` fail-opens on a malformed note file (skip + warn, never crash — the stale-store lesson). Sort: **pinned-first → updatedAt desc** (ISO-8601 lexicographic, correct). create: createdAt=updatedAt=now; update: preserve createdAt, bump updatedAt. Search = ci substring over title+body+joined-tags. attached filter = `type` or `type:ref`.
- **`router.py`** — `GET /notes?q=&tag=&attached=&pinned=` · `GET /notes/{id}` · `POST /notes` · `PUT /notes/{id}` (pin toggle = PUT with pinned flipped, no /pin endpoint — north-star) · `DELETE /notes/{id}`. Locked envelope `{success,data,warning?}`. 404 on absent (GET/PUT/DELETE), 422 on bad body. `MODULE = BaseModule(name="notes")` — auto-discovered.

### Store — `md_store.delete_file()` (+39 lines, shared infra)
New `delete_file(path, message)` mirroring `write_file`'s contract: `git rm` + 1 commit (history stays complete), `_write_lock` concurrency-safe, `_resolve_under_root` path-escape rejection, filesystem-unlink fallback for untracked files, idempotent (absent file → None no-op). Needed for notes DELETE; reusable by future modules.

### Frontend — S10 Notes screen (`app/notes/page.tsx`, replaced EmptyScreen)
- **`lib/useNotes.ts`** — mirrors the frozen Note shape; CRUD against `/notes`. **`components/shared/NoteCard.tsx`** — card (title/body-preview/tag-chips/pin-indicator/attach badge). Search box, tag filter, "+ new note" create form (title/body/tags/attach picker), edit/delete. Ports `SCREENS.notes` from the mock.

---

## 2. Verification (Rule #0 — architect pre-staged; tester canonical pending)

### Architect 4-step review (read FULL functions + traced runtime — not just diff)
| Check | Result |
|---|---|
| pytest full suite | **443 passed, 0 failed, 0 skipped** |
| notes tests (3 files: test_notes 68 + test_notes_api 12 + test_notes_backend 19) | **99 passed, 0 skipped** (the `_skip_router` guard is dynamic `find_spec`-based — auto-runs now router exists; earlier "17 skipped" was a pre-T2 snapshot, self-healed) |
| vitest full | **254 passed (29 files)** (≥239 baseline; +15 notes) |
| tsc | clean (exit 0) |
| `/health` lists notes | `['finance','market','notes','projects']` ✓ |
| **Live CRUD round-trip** (POST→GET→DELETE on :8001) | POST success, server-set id, createdAt==updatedAt on create ✓; **md_store git commit landed** (`fe7b16f create note …` in data/ repo — Sprint-13 lesson) ✓; GET reads markdown+front-matter back ✓; DELETE 200 → GET 404 ✓ |
| 422 on attach.type≠none w/o ref | ✓ |
| 404 on unknown id | ✓ |
| Registry auto-discovery (NOT core/main.py edit) | ✓ (`MODULE = BaseModule`) |
| md_store.delete_file: lock + path-escape + git-rm + untracked-fallback + idempotent | ✓ (read full function) |

### Tester canonical verify (Gate 3 — PENDING tester T4)
- Chrome via `docker compose up` (:3010→:8001): create note → appears in list → edit → delete → **value-by-value** rendered cards vs `GET /notes` raw · pin sorts first · 0 unhandled console errors. (Tester's lane — not substituted by architect's :8001 curl pass.)

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema constraints (`title` min_length=1/max_length=200, `Literal` attach type, `model_validator` ref-required) · ☑ integration tests (test_notes_api 12 + section-D endpoint tests run, not skipped) · ☑ existing integration tests pass · ☑ module auto-discovered · ☑ envelope `{success,data,warning?}` · ☑ codes 404 (absent) / 422 (bad body) — no 401/403 (no auth).

### Gate 2 — Function
☑ unit tests assert observable behavior (markdown round-trip, git-commit landed, sort order, fail-open skip) · ☑ existing pass (pytest 443 / vitest 254) · ☑ edge cases (empty dir→[], malformed front-matter→skip+warn, unknown id→404) · ☑ error path explicit (fail-open list; absent→404) · ☑ types complete (tsc clean) · ☑ no self-confirming asserts · ☑ FE Chrome self-verify — **pending tester** (FE-touching).

### Gate 3 — Sprint
☑ end_sprint_6 written · ☑ architect spot-checked actual files (full functions + live runtime) · ☐ **tester: vitest 100% + pytest + Chrome value-by-value — PENDING T4** · ☑ counts ≥ baseline (pytest 344→443, vitest 239→254) · ☑ out-of-scope flagged (§5) · ☑ commit format `feat(sprint-6)`.

**VERDICT: backend + FE code review GREEN. Gate 3 holds on tester T4 Chrome canonical verify + team-lead Rule#0 value-diff before commit.**

---

## 4. Assumptions (user-review — decide-and-log)

- **Note id = `slug(title)-<6hex>`** (readable filename + collision-safe; empty/symbol-only title → `note-<6hex>`). To change: edit `_new_id` in service.py.
- **`tags[]` plural** (superset of mock's singular `tag` — multi-tag ≥ single, full-feature north-star). FE renders chips. To change: cap to one tag in the form.
- **`pinned` ADDED** (mock has it — sort pinned-first + indicator). Pin toggle = PUT with pinned flipped (no dedicated /pin endpoint — one update path, north-star). To change: add `PATCH /notes/{id}/pin` if a one-click toggle is wanted.
- **`attach{type,ref}` nested, free-form ref, NO cross-module validation** (single-user soft tag — a note can reference a project/channel that the validator doesn't confirm exists). To change: add an existence check against /projects + /finance if dangling refs become a problem.
- **Search = ci substring over title+body+tags, no index/ranking** (one dev, small N — north-star). To change: add a real index only if N grows large + search feels slow.
- **Daily-log (SPEC §S10) = a tag convention this build, not a dedicated feature.** To change: build a daily-log note type if the user wants structured daily entries.
- **Malformed note file → skipped + warned** (fail-open, same as projects status.md / finance). To change: surface a louder error if silent skips hide data.

---

## 5. Risks / out-of-scope (future)

- **Project-attached notes NOT yet surfaced in Project Detail** — the attach is stored (`attach.type="project"`, ref=project id); wiring the cross-display into the Projects screen is a later small follow-up (this sprint = the Notes module + screen only).
- **No rich markdown editor** — textarea + raw markdown stored; rendered display is plain (no WYSIWYG). North-star.
- **No daily-log dedicated feature** — tag convention suffices; revisit if user asks.
- **attach ref can dangle** — references a project/channel id with no existence check (single-user soft tag). Acceptable now; add validation if dangling refs cause confusion.

---

## 6. Retro (process learnings)

1. **The "17 skipped API tests" alarm was a stale snapshot, not a real gap → reinforces verify-on-current-disk.** I flagged it from an earlier reading; on re-inspection the `_skip_router` guard is `skipif(not find_spec("modules.notes.router"))` — dynamic, auto-runs once the router exists. The skips were from BEFORE T2 landed. Lesson re-confirmed: a "skip count" is a point-in-time artifact; re-read the guard's CONDITION before treating a skip as a coverage hole. (Memory: verify-don't-trust-snapshot.)
2. **md_store grew a shared method (`delete_file`) mid-feature — reviewed as infra, not feature.** A +39-line change to a store used by 4 modules gets the full-function read + the contract-mirror check (lock, path-escape, idempotency, untracked-fallback), not a glance. New shared infra = higher review bar than module-local code.
3. **Pre-staged the review while tester ran** — ran my 4-step (full suite + live CRUD + git-commit-landed + 422/404) in parallel with tester T4 so the gate verdict is immediate on their report, not a fresh start. Keeps the sprint-close tight.

---

## 7. Commit
- `feat(sprint-6): notes module (S10) — md_store CRUD + git-per-write + attach/tag/pin + S10 screen` — notes module (schema/service/router) + md_store.delete_file + useNotes/NoteCard/notes page + plan_6 + end_6. One commit.
- Gated on tester T4 Chrome canonical value-by-value + team-lead Rule#0 value-diff. After commit: `sleep 120 && git push` (background) → notify user → next sprint.
