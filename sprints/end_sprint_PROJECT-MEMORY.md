# end_sprint_PROJECT-MEMORY — note↔project link + project_context compose (Cairn #42)

> Result. An agent asking about project X gets its tagged wiki notes injected ("project memory"). Commit `<hash>` `feat(sprint-PROJECT-MEMORY)`. Status: ✅ all 3 gates pass. backend EDITED (projects + wiki-reader); architect 4-step + committed (§3).

## What shipped
| File | Change |
|---|---|
| `modules/wiki/reader/project_notes.py` (NEW) | `project_notes(project_id, limit=10)` — notes tagged `project:<id>`, lean {id,title,status,updated,snippet}, updated DESC, top-10, honest-empty + `project_tag(id)` helper (one place the write/read sides agree on the token). |
| `modules/wiki/store/queries.py` | `notes_with_tag(tag)` — ONE LIKE query (`%"<tag>"%` — the JSON-quoted element, anchored so a substring can't false-match), ordered updated DESC. Exported. |
| `modules/projects/service.py` | `get_context(project_id, notes_limit=10)` — the ONE compose: {project:<metadata>, notes, noteCount} (get_project + wiki.project_notes). None on missing. |
| `modules/projects/router.py` | REST `GET /projects/{id}/context` (404 missing). |
| `mcp_servers/read_server.py` | MCP `project_context` (found:False missing) — calls the SAME service.get_context → byte-identical (#24). Auto-registered (TOOLS.values(), no manual add_tool). Shared-read 41→42. |
| `mcp_servers/CATALOG.md` + 3 count tests | shared-read 41→42 (test_mcp_http, test_mcp_read, test_finance_mcp_shape — the 3rd one backend's ran-the-red caught). |
| `tests/test_project_memory.py` (NEW, 14) | project_notes (tag-scoped distinguishing, lean, top-N, honest-empty, substring-guard, sort) + project_context (compose, zero-notes→[], unknown→404, REST≡MCP byte-identical, MCP unknown→found:False). |

## Design (LOCKED — F1=(a), team-lead-confirmed)
- **Link convention = the tag `project:<id>`** (multi-valued — a note can tag several projects; non-destructive; folder stays for browsing). The tag is AUTHORITATIVE for compose.
- **Compose via a dedicated `project_context(project_id)`** (metadata + tagged notes, lean) — keeps `project_get` lean; project_context is the "everything about X" call. Byte-identical REST≡MCP (#24, service-layer).
- **Substring-guard:** the LIKE matches the JSON-quoted token `"<tag>"` so `project:life` can't false-match `project:life-os`.
- **T3 (write-side tag-suggest) DEFERRED** (decide-and-log): #34 suggest is title-FTS, not tag-aware — a tag-suggest is a separate concern; flagged not built.

## Verification (Rule#0 — backend ran-the-red + architect 4-step)
- **backend ran-the-red:** targeted run green (121) BUT the FULL suite surfaced 3 fails its targeted run missed — (1) a 3rd hardcoded shared-read count consumer (test_finance_mcp_shape len==41) + (2,3) its own 2 tests passing in isolation but failing in full-suite ORDER = a cross-FILE test-isolation leak (the hand-rolled app_client fixture monkeypatched settings.db_path but didn't reset db.DB_PATH — init_db()'s module-global, set by an earlier test, WON over settings.db_path → read a leaked DB). FIXED: the fixture mirrors conftest.isolated_paths (reset db.DB_PATH=None + clear _STATUS_CACHE); reproduced deterministically (test_db THEN test_project_memory → was red, now green). Saved the lesson to memory (hand-rolled-fixture-must-mirror-isolated-paths).
- **architect 4-step:** the substring-guard LIKE pattern correct (`%"<tag>"%` anchors to a whole array element); REST + MCP both call service.get_context (byte-identical by construction); count 41→42 across all 3 consumers; project_context auto-registered (no broken-intermediate); project_notes perf = one LIKE query (not load-all); RE-RAN the exact leak repro (test_db then test_project_memory) → 31 passed (the isolation fix is real, not masked); 12-file dirty set #42-only; git-status-after-stage zero left-dirty.

## 3 Gates — ALL PASS
- **Gate 1 (API):** REST /projects/{id}/context == MCP project_context byte-identical (#24); 404 missing / found:False; envelope. ✅
- **Gate 2 (Function):** the tag-scoped distinguishing (project:other/untagged NOT in project_notes), substring-guard, lean shape, top-N, honest-empty, zero-notes→[], the cross-file isolation fix (deterministic repro green); 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; backend ran-the-red (3 full-suite fails caught+fixed) + architect 4-step; commit format; git-status-clean; #42-only. ✅

## Assumptions (user-review)
- **note↔project link = the tag `project:<id>`** (multi-valued, non-destructive, authoritative for compose); compose via a dedicated `project_context(project_id)` (lean, byte-identical REST≡MCP). **How to change:** project_tag()/notes_with_tag + service.get_context.
- substring-guard via the JSON-quoted-token LIKE; project_notes top-10 updated-DESC; T3 tag-suggest DEFERRED (title-FTS ≠ tag-aware).

## Notes
- backend EDITS (projects + wiki-reader); architect commits (§3). 1900 green (+14). The cross-file test-isolation lesson (hand-rolled fixtures must mirror conftest.isolated_paths incl. db.DB_PATH reset) saved to memory.
- Pipeline: ✅#34 ✅#33 ✅#41 ✅#45 ✅#42 → #46-Phase1 (agent_error — architect dispatches now) → scout/QA backlog.
