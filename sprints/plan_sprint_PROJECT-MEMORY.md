# Sprint PROJECT-MEMORY — note↔project link convention + compose flow (Cairn #42, SPEC A2)

> Created 2026-06-21 by architect (NEVER-FREE: designed during backend's #33/#34). Architect-design task (KHÔNG chờ-user, reversible — memory layer; A2 already user-approved in backlog). DESIGN + subtask breakdown to team-lead before build. 3-5d scope.

## Objective
An agent asking about project X should get the relevant wiki notes injected as context ("project memory") — so the agent reasons WITH the project's accumulated notes, not blind. Needs: (1) a note↔project LINK convention, (2) a compose hook that, given a project, returns its notes.

## Grounded against the live schema
- `Project.id` = slug (repo folder name, lowercased, stable) — the natural link key. `project_get(project_id)` already exists (read_server:415) = the natural compose hook.
- Wiki `Note` has BOTH `tags: list[str]` AND `folder` (virtual path; the schema's OWN example is `"Projects/life-os"`). Two candidate conventions.

## ⚠️ FORK F1 (team-lead — the link convention)
- **(a) tag `project:<id>`** — a note relates to a project via a tag. PRO: multi-valued (a note can belong to several projects / a project + a topic), explicit, queryable (`tags contains "project:life-os"`), doesn't move the note. CON: a convention the agent must follow on write.
- **(b) folder-pointer** `Projects/<id>` — reuse the existing virtual-folder (the schema already exemplifies `Projects/life-os`). PRO: zero new concept (the folder exists), visible in the W-Explorer tree. CON: single-valued (a note lives in ONE folder — can't be in two projects), and folder is also used for general organization (overloads it).
- **MY RECOMMENDATION: (a) tag `project:<id>`** — multi-valued + non-destructive + explicit; it's the robust link, and the folder stays free for human organization. (decide-and-log; surface because it's the core convention everything else builds on.) A note can ALSO live in a `Projects/<id>` folder for browsing, but the AUTHORITATIVE link for compose is the tag.

## The compose flow (DECIDED — pending F1)
- A reader `project_notes(project_id)` → the notes tagged `project:<id>` (filter `tags contains "project:<project_id>"`), lean shape `{id, title, status, updated, snippet?}`, sorted updated DESC (most-recent context first), top-N (decide-and-log N=10 — enough context, not the whole vault).
- **Compose hook:** extend `project_get(project_id)` (or a new `project_context(project_id)`) to OPTIONALLY include `notes: project_notes(project_id)` — so an agent calling project_get gets the project's metadata + its wiki memory in one call (the wiki_context-style consolidation #23 precedent). decide-and-log: attach to project_get behind a param (`include_notes=true`) OR a dedicated `project_context` tool — lean toward a dedicated tool so project_get stays lean + project_context is the "give me everything about X" call.
- REST `GET /projects/{id}/context` + MCP `project_context` → byte-identical (#24 gate).

## Subtask breakdown (for BE, after team-lead's F1 + design OK)
- **T1 (BE):** the `project:<id>` tag convention documented + a `reader.project_notes(project_id)` (tag filter + lean shape + sort + top-N). Tests.
- **T2 (BE):** the compose surface — `project_context(project_id)` REST + MCP (project metadata + project_notes), byte-identical, add to the #24 parity gate. Tests.
- **T3 (BE, optional):** a write-side helper so an agent writing a project note tags it `project:<id>` correctly (or the #34 suggest-links could suggest the project tag) — decide-and-log, may defer.
- **T4 (architect):** review + commit.

## HARD GATE (distinguishing)
- A note tagged `project:life-os` → appears in `project_notes("life-os")`; a note tagged `project:other` or untagged → does NOT (the distinguishing: tag-scoped, not all-notes).
- `project_context("life-os")` returns project metadata + its tagged notes (lean), updated DESC, top-N; a project with no notes → `notes: []` (honest-empty).
- REST≡MCP byte-identical (#24). read-only compose (no mutation). pytest green, mypy clean.

## Assumptions (user-review)
- **note↔project link = the tag `project:<id>`** (multi-valued, non-destructive, authoritative for compose) — NOT the folder (folder stays for human browsing; a note MAY also fold under `Projects/<id>` but the tag is the link). **How to change:** the tag convention + the filter in project_notes.
- **compose via `project_context(project_id)`** = project metadata + its tagged notes (lean, updated DESC, top-N=10); a dedicated tool so project_get stays lean. **How to change:** the compose hook + N.

## Notes
- Architect-design task; bring the design + F1 + subtask breakdown to team-lead before BE dispatch. Reversible (memory layer). Separate commit(s) per subtask.
- Reuses the #23 wiki_context consolidation precedent (compose-in-reader → REST≡MCP byte-identical) + the #34 suggest-links could later suggest the project tag. NEVER-FREE: designed during backend's #33/#34.
