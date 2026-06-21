# end_sprint_93-WIKI-IMPORT — wiki import .md/.txt → note (Cairn #93, BE)

> Result. User pain "chưa upload được" fixed: `POST /wiki/import` imports a .md (YAML frontmatter) or .txt (plain body) → a wiki note, REUSING the existing machinery (the single frontmatter parser + create_note → _apply_create, so 1 git commit + [[link]] resolution + cache). Multi-file → per-file results (fail-soft); a bad file → an agent-readable error row (NO junk note). Commit `<hash>` `feat(sprint-93-wiki-import): import .md/.txt → note (frontmatter+link-resolve reused) (#93)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT [[link]]-resolves-to-backlink proof + live both-shapes + bad-file-no-note). Cairn #93 BE (FE import button follows). The SERIAL-first of the #93/#94 wiki batch (#94 soft-delete after).

## What shipped (6 wiki files — reuse-first, NO re-implemented parsing)
| File | Change |
|---|---|
| `service/serialize.py` | REFACTOR (behavior-preserving): extracted `extract_frontmatter(content) -> (fm|None, body)` as the SINGLE YAML-frontmatter parse + `FrontmatterError` (malformed `---` block, distinct from no-frontmatter). `_parse` now calls it + KEEPS its None-on-malformed contract (the cache-reindex path unchanged — 185 existing wiki tests green confirm). |
| `service/import_notes.py` (NEW) | the import logic: `import_files([(filename,content)], actor) -> {imported:[rows], createdCount}` + `import_one`. .md → extract_frontmatter → map `_FM_FIELDS` (title/tags/folder/status/trustTier/noteType/author) → NoteCreateInput → `create_note` (→ _apply_create: 1 commit, [[link]] resolve, cache). .txt/no-frontmatter → plain body, title from first non-empty line (tolerates leading `#`) / filename. Per-file fail-soft. |
| `router.py` | `POST /wiki/import` — content-type sniff: multipart `UploadFile[]` (decode utf-8 lenient) OR JSON `{files:[{filename,content}]}` (ImportInput-validated). agent_error on no-files / bad-JSON / bad-body. |
| `schema.py` | `ImportInput {files: [{filename, content}]}` (≥1 file) + the result-row shape. |
| `service/__init__.py` | export import_files/import_one + extract_frontmatter/FrontmatterError. |
| `tests/test_wiki_import.py` (NEW, 14) | .md-fields value-by-value · **[[link]]-resolves-to-backlink** · .txt (first-line + filename-fallback) · bad-file agent-errors (malformed/empty/wrong-ext/bad-status → INVALID_INPUT, NO note) · multi-file fail-soft. |

## Design (LOCKED — reuse the create+parse machinery, honest per-file errors)
- **REUSE, no re-implementation:** one frontmatter parser (`extract_frontmatter`) shared by `_parse` (note md → Note) AND import (md → NoteCreateInput); the note creation goes through the EXISTING `create_note → _apply_create` (1 git commit, **[[link]] resolution**, cache) — NOT a parse-only bypass. This is THE value: imported memory/*.md keep their cross-links.
- **agent-first errors (honest, per-file):** malformed frontmatter / empty / wrong-ext / oversized / a bad Literal field (status/noteType/trustTier out of range) → `agent_error` INVALID_INPUT + message + hint, NO note created. A bad Literal is surfaced (NOT silently defaulted — the file claimed a value we can't honor). create failure → UPSTREAM_DOWN per-file.
- **multi-file fail-soft (DECIDED + logged):** per-file result rows; one bad file yields its error row, the others still import — the batch never fails wholesale.
- **both input shapes:** JSON paste (FE primary) + multipart upload, one endpoint, content-type sniffed.
- **md-first:** only .md / .txt (1 MB cap); image/PDF/binary = P2 (out).

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the _parse refactor is behavior-preserving (extract_frontmatter + _parse keeps None-on-malformed — the reindex path unchanged) ✅; import_one reuses create_note (1 commit, link-resolve) + honest per-file agent-errors (bad Literal → error not silent-default) ✅; router both-shapes + agent_error guards ✅.
- **architect INDEPENDENT [[link]]-resolves proof (own behavior-test):** created a Target note → imported an .md linking `[[Target Note]]` → the imported note RESOLVES into Target's BACKLINKS (a real link row), not just "imported ok". + a malformed-YAML file → agent-error (code+hint) + `count_notes()` UNCHANGED (NO junk note). ✅ (Did NOT trust backend's test — re-ran the behavior.)
- **live both-shapes (non-destructive):** `POST /wiki/import` JSON batch (1 good + 1 bad .md) → HTTP 200, createdCount=1, good→ok/noteId, bad→INVALID_INPUT (fail-soft); cleaned up the imported note. ✅
- **Suite:** the 14-test import file green; the existing wiki tests green (refactor behavior-preserving); DEFAULT (`-m 'not slow'` deterministic) = **2180 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2166→2180 = +14 import tests); never staged backend/data/.

## 3 Gates
- **Gate 1 (API):** `POST /wiki/import` both shapes; `{success,data:{imported,createdCount}}`; agent_error (code/message/hint/retryable) on bad file/body, NO junk note; multi-file fail-soft. ✅
- **Gate 2 (Function):** the distinguishing tests (.md-fields / [[link]]-resolves-to-backlink / .txt / bad-file-no-note / multi-file); independent behavior re-run; refactor behavior-preserving (185 wiki tests green); 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent proof + live both-shapes; staged set EXACTLY the 6 wiki files + end doc (NO #94 work, no data/.env/template); commit format. ✅

## Assumptions (user-review)
- **multi-file = per-file fail-soft** (one bad file → its error row, others import; batch never fails). **How to change:** import_files (make it all-or-nothing).
- **a bad Literal frontmatter field (status/noteType/trustTier) → agent-error, NOT a silent default** (the file claimed a value we can't honor — surface it). **How to change:** the ValidationError branch in import_one.
- **only .md/.txt, 1 MB cap.** image/PDF/binary = P2. **How to change:** _ALLOWED_EXT / _MAX_BYTES.
- **.txt/no-frontmatter title = first non-empty line (tolerating a leading `#`) else filename stem.** **How to change:** _title_from_txt.

## Notes
- Cairn #93 BE (user pain "chưa upload được", "md TRƯỚC"). The SERIAL-first of the #93/#94 wiki batch (BE-vs-BE shared-file risk → serial; #94 soft-delete after #93 fully lands). backend-w3 built; architect committed (§3 sole-committer). Reuses the create + parse machinery (the [[link]]-resolution is the load-bearing value — imported notes keep cross-links). Next: FE-#93 (import button) → then #94-BE (soft-delete, reconcile-safe: keep .md + set status). The frontmatter-parser refactor (extract_frontmatter) is now the single source both _parse + import use.
