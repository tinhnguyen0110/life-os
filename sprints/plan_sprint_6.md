# Plan Sprint 6 — Notes (S10) [4th backend module]

> DRAFT (CLAUDE.md §3.3) — refresh via kickoff before dispatch. 4th feature module: markdown notes via md_store (1 git commit per write), attach to project/channel/standalone, tag + search. + S10 screen. Exercises the md_store write+git path end-to-end on a fresh module.
> Spec: SPEC §S10. Mock: `template/Life Command/app/screens-system.js` `SCREENS.notes` (HAS a mock → PORT). ARCH §6 (md_store markdown+git) / §7 (`GET /notes` · `POST /notes`). Memory: single-dev-no-overengineering, schema-freeze-gate, unhandled-errors-not-green.
> Author: architect · 2026-06-06 · Status: awaiting team-lead scope-confirm + greenlight.

## Objective
Build the `notes` module (router/schema/service) + S10 Notes screen. Markdown CRUD via md_store (every write = 1 git commit — the AI-readable shared source). Attach a note to a project / finance channel / standalone. Tag + search. Full feature (SPEC §S10), simple impl (north-star — no full-text-index engine; substring search over title+body+tags is enough for one dev).

## Vocab-lock (kickoff) — diff SPEC §S10 + mock labels BEFORE dispatch
SPEC + mock `SCREENS.notes`: "Ghi chú" (Notes), tag/tagchip, search pill, attach to "dự án/kênh/standalone". Mock note shape = `{id, title, tag, pinned, updated, body}`.
**Decisions (decide-and-log):**
- **`pinned` ADDED** (team-lead honest-mirror catch — mock has it, sort pinned first + indicator). Was dropped in first scope; folded in.
- **`tags[]` (plural) not mock's singular `tag`** — superset (multi-tag ≥ single, full-feature north-star); FE renders chips. Logged divergence.
- **`updatedAt` (ISO) stored** → FE formats relative ("hôm nay / 2 ngày trước") — covers mock's `updated`.
- **`attach {type, ref}` nested** (backend's rec) — cleaner than flat. type ∈ project/channel/none, ref free-form (NO cross-module validation — single-user soft tag, north-star).

## Tasks (4, BE gating → FE → tester)
- **T1 [backend, GATING] — notes schema + service.**
  - `schema.py`: `Note {id, title, body, tags, attachedType, attachedId, createdAt, updatedAt}` + `NoteInput {title, body, tags, attachedType?, attachedId?}` (id/timestamps server-set).
  - `service.py`: notes stored as md_store `notes/<id>.md` — YAML front-matter (id/title/tags/attachedType/attachedId/createdAt/updatedAt) + markdown body. `list_notes(query?, tag?, attached?)`, `get_note(id)`, `create_note(input)`, `update_note(id, input)`, `delete_note(id)`. Every write = `md_store.write_file` (1 git commit). Search = case-insensitive substring over title+body+tags (simple, north-star). Project-attached notes also surfaced to Projects detail later (out of scope this sprint — just store attachedType="project"/attachedId).
  - Gates T2/T3.
- **T2 [backend] — notes router.**
  - `GET /notes?q=&tag=&attached=` (list+filter), `GET /notes/{id}`, `POST /notes` (create), `PUT /notes/{id}` (update), `DELETE /notes/{id}`. Envelope + codes (404 unknown id, 422 body). `MODULE` auto-discovered. Blocked by T1.
- **T3 [frontend] — S10 Notes screen** (`app/notes/page.tsx`, replace EmptyScreen).
  - Port `SCREENS.notes`: note cards (title/body-preview/tagchips), search box (client-filter or ?q=), tag filter, "+ new note" → create form/modal (title/body markdown/tags/attach), edit/delete. Render-only for list; create/edit POST/PUT. Blocked by T2.
- **T4 [tester] — verify notes.**
  - pytest (CRUD behavior: create→read-back the markdown+front-matter, **md_store git-commit landed** per Sprint-13 lesson, search/tag filter, update/delete, attach). Chrome via `docker compose up` (:3010→:8001): create a note → appears in list → edit → delete → value-by-value the rendered cards vs `GET /notes`. Pre-scaffold from T1.

## Logic/Algorithm (architect-decided — decide-and-log; the non-CRUD parts)
- **Note id:** `slug(title)` + short suffix to dedupe (e.g. `my-note-3f2a`), OR a timestamp/uuid-short. DECIDE: `slug(title)-<6char>` (readable filename + unique). Empty title → `note-<6char>`.
- **Storage:** `notes/<id>.md` with YAML front-matter `---\nid/title/tags/attachedType/attachedId/createdAt/updatedAt\n---\n<markdown body>`. 1 md_store write = 1 git commit (free history, AI reads raw). Same pattern as projects status.md.
- **attachedType:** `Literal["project","channel","none"]` (channel = finance crypto/etf/vn/dry). attachedId = the project id or channel id (None when "none"). Validation: if attachedType≠none, attachedId required.
- **Search (`?q=`):** case-insensitive substring over title + body + joined tags. No index/ranking (north-star — one dev, small N). Empty q → all.
- **Tag filter (`?tag=`):** exact tag match. **attached filter (`?attached=`):** by attachedType or attachedId.
- **Timestamps:** ISO-8601 UTC, createdAt on create, updatedAt on every write.

## Defensive (MANDATORY)
- Empty notes/ dir → `[]`, no crash. Malformed front-matter in a note file → skip+warn (don't crash the list — same fail-open as projects status.md, the stale-store lesson).
- Unknown id (GET/PUT/DELETE) → 404. attachedType≠none but attachedId missing → 422.
- Title/body empty → allow empty body, but title min_length 1 (or auto-id if empty — decide; lean: title required, body optional).
- Search/tag no match → `[]`, not error.

## Dispatch standards
- Runtime: dev stack = `docker compose up` (FE :3010 → BE :8001 container). Baseline pytest 344, vitest 239.
- Ownership: failing test → report; **full-suite-on-staged + 0-unhandled-errors before commit** (Sprint-5 lesson); value-by-value vs raw API on canonical (3B); re-read cross-file at current mtime; useSafeRouter; tsc before report.
- FE: mock = `screens-system.js` SCREENS.notes; schema = frozen Note shape (mirror, render-only).
- **Logic-in-message-body:** the full §Logic above goes IN the T1 SendMessage dispatch (recurring lesson — not a pointer).
- **Schema-freeze-gate:** backend freezes `notes/schema.py` + announces "FROZEN: [fields]" (endpoint serving + curl payload, not just file-exists) → THEN I ping FE mirror.

## Dispatch ordering
1. T1 GATING (schema + service) alone → freeze.
2. T2 (router) after T1.
3. T3 (FE) after schema frozen + T2 serving. T4 pre-scaffolds from T1.

## Open items at kickoff
- Note id scheme (lean slug-title + 6char suffix) — confirm at dispatch.
- Whether `attached` filter is by type or id (support both — `?attached=project` or `?attached=project:devcrew`).
- Daily-log (SPEC §S10) — a special note type or just a tag convention? Lean: a tag/convention this sprint (don't build a separate daily-log feature — north-star), revisit if user wants it.

## Out of scope (north-star)
- No full-text search index / ranking — substring over title+body+tags.
- No rich markdown editor — a textarea + markdown stored raw (rendered display is fine, no WYSIWYG).
- Project-attached notes showing IN Project Detail — store the attach now, wire the cross-display in a later sprint (or a small follow-up). This sprint = the Notes module + screen.
- No daily-log dedicated feature (tag convention suffices).
