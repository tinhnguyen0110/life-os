# end_sprint_113-PROJECTS-AUTO-DISCOVER — Projects auto-discover from DEV_TRACING_ROOTS + hidden flag (Cairn #113, PROJECTS-UNIFY T2)

> Result. Projects (config + registered status.md, manual) and Dev Activity (DEV_TRACING_ROOTS .git scan) were 2 independent repo sources → divergent lists. Unified: a `.git` repo under DEV_TRACING_ROOTS is now AUTO-discovered as a project (`source="auto"`, no manual register), with a `hidden` flag (≠ abandoned) + REST `/hide`·`/unhide` to drop the ones you don't care about. Commit `<hash>` `feat(sprint-113-projects-auto-discover)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT mypy --no-incremental + suite re-run). Cairn #113 PROJECTS-UNIFY T2 — be-only, CLOSES on this commit. UNBLOCKS #114 (FE) + #115 (cleanup).

## What shipped (projects src + tests)
| File | Change |
|---|---|
| `projects/service.py` (+222/-46) | `_auto_repos()` (3rd source — lazy-imports dev_activity `scan_roots`+`_find_repos`, id=slug(basename), fail-soft, ROOTS-unset→{}). `_tracked_repos()` WIDENED → `dict[id→(path, source)]`, 3-source overlay auto<config<registered (registered/config WINS on collision, debug-log NOT warning — NG5). `_tracked_repo_paths()` compat. `_is_hidden` (mirrors `_is_abandoned`, INDEPENDENT). `read_one(...source=)` stamps source+hidden. `list_projects(include_hidden=False)` excludes abandoned ALWAYS + hidden unless requested. `hide_project`/`unhide_project` (scoped md_store write of ONLY that id's status.md, idempotent no-op, minimal `{hidden:true,repo}` for an auto-repo with none). All 9 `_tracked_repos` callers unpack the tuple. |
| `projects/schema.py` (+17) | `ProjectSource = Literal["config","registered","auto"]` (exported #114 contract type). `ProjectStatus +source` (field 14, default "config") `+hidden` (field 15, default False). Fields 1-13 byte-identical (additive-only). |
| `projects/router.py` (+35) | `GET /projects?include=hidden`; `POST /projects/{id}/hide`·`/unhide` (agent-readable 404 + hint; idempotent 200 no-op). |
| `projects/reader.py` (±4) | 🔴 the Gate-2 fix: both direct `ProjectStatus(...)` sites (`_dead_status` :231, `read_project` :317) now pass `source="config", hidden=False` (read_one overrides from the merge/meta — the literal is the schema default for a direct reader call). REQUIRED because this repo has no pydantic mypy plugin → defaulted fields read as required → every direct constructor must pass them. |
| `tests/conftest.py` (+6) | autouse `monkeypatch.delenv("DEV_TRACING_ROOTS")` — neutralize auto-discovery by default so isolated projects tests are deterministic regardless of the runner's env (a container shell with ROOTS set would leak real repos). test_projects_unify re-sets it (monkeypatch.setenv). |
| `tests/test_projects.py`(+8) · `test_projects_reader.py`(±9) · `test_projects_unify.py`(NEW 21) | the 7 distinguishing cases + reconcile the existing tests to the source/hidden fields. |

## Design (LOCKED — 3-source merge, hidden≠abandoned≠dead, REST-only, scoped-write)
- **3-source merge, precedence registered > config > auto** (human/config truth wins; auto is fallback-discovery). Shadowed-auto dropped silently (debug, NG5). DEV_TRACING_ROOTS unset → auto {} → list == pre-#113 (backward-compat).
- **auto ids = slug(basename)** via DRY reuse of dev_activity's own scan (lazy-import, #112 cycle-safe precedent) → auto-projects EXACTLY == dev_activity-scanned repos → the #112 slug-join stays consistent.
- **hidden ≠ abandoned ≠ health=="dead" — 3 INDEPENDENT flags** (abandon-orthogonal-to-health). list_projects excludes hidden+abandoned; graveyard (S4) = abandoned-only; hidden has `?include=hidden`.
- **REST-only hide/unhide** (team-lead call): WRITE actions = REST endpoints, NOT MCP tools (read-server stays read-only). source+hidden auto-flow into the EXISTING MCP read tools via `_jsonable`/model_dump → ZERO read_server.py edit, MCP≡REST parity free, no count-assert/CATALOG change → #113 fully disjoint (no shared-file serialization).
- **scoped-write (#72):** hide writes ONLY that id's status.md (minimal for an auto-repo with none); NEVER auto-writes status.md for every roots-repo (no spam). Idempotent.

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL functions):** the 3-source overlay + precedence; ALL 9 `_tracked_repos` callers unpack `(path, source)` correctly; **#112 `dev_stat_for_project` UNAFFECTED** (it joins by `slug(r["repo"])==key` against dev_store directly, never reads `_tracked_repos` — verified by reading its body); hidden≠abandoned independence; scoped idempotent hide/unhide; additive-only schema. Staged is #113-only (no read_server/data/template/docs leak). ✅
- **🔴 Gate-2 mypy CAUGHT + FIXED (the block):** my first 4-step found `reader.py:213+295: Missing named argument source/hidden [call-arg]` — a #113 regression (the new required-by-mypy fields, untouched reader.py constructors). Blocked the commit, routed the 2-line fix. backend-w3's initial "mypy clean" was a STALE `.mypy_cache` (incremental served the pre-#113 reader.py result) + dirty-file scoping. **Re-verified `mypy --no-incremental backend/modules/projects/` on disk → ZERO #113 errors** (the only 8 are pre-existing yaml `[import-untyped]` library-stub warnings, present at HEAD, codebase-wide, not this sprint). ✅
- **INDEPENDENT suite:** projects+unify **175 passed** (forward + a second run, deterministic) WITH the reader.py fix. backend-w3: FORWARD 2332/0 == REVERSE 2332/0 (isolation invariant). ✅
- **LIVE migrated container (backend-w3, ROOTS set):** 14 projects source-tagged, hide/unhide round-trip, SCOPED by-id cleanup (re-appears auto, NO blanket delete). MCP `projects_list` carries source+hidden (auto-emit confirmed). verify-on-migrated-db honored. ✅

## 3 Gates
- **Gate 1 (API/MCP/agent):** ?include=hidden; /hide·/unhide agent-readable 404+hint, idempotent; source+hidden self-describing; MCP≡REST parity (auto-emit). ✅
- **Gate 2 (Function):** 7 distinguishing cases + 175 passed + **mypy --no-incremental disk-clean** (zero #113 errors) + additive schema + scoped-write + backward-compat; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent mypy/suite; staged EXACTLY #113 (4 src + 4 test, NO read_server/data/template/docs/#114 leak); commit format. ✅

## Assumptions (user-review)
- **auto-discover precedence registered > config > auto** (human/config wins). **How to change:** the overlay order in `_tracked_repos`.
- **hidden = not-interested, INDEPENDENT of abandoned** (graveyard) **and health=="dead"** (git). **How to change:** the `_is_hidden` filter in `list_projects`.
- **hide writes a minimal status.md for an auto-repo with none** (scoped). **How to change:** `hide_project`. unhide does NOT delete the file (a written file is a human record).
- **DEV_TRACING_ROOTS unset → auto-source empty** (backward-compat). **How to change:** set ROOTS (the same env dev_activity uses).

## Notes
- Cairn #113 PROJECTS-UNIFY T2 — user-CHỐT (hướng B: unify Projects↔DevActivity sources). backend-w3 built; architect committed (§3 sole-committer). 🔴 **Two Rule#0 catches this task:** (1) my 4-step + independent mypy caught a Gate-2 failure (reader.py source/hidden [call-arg]) the green 175-test suite masked → blocked the commit, fix folded in. (2) backend-w3's "mypy clean" claim didn't survive my disk re-verify (stale `.mypy_cache` + dirty-file scoping) → re-ran `--no-incremental` on the package to confirm disk-clean before committing. Lessons recorded: `new-required-schema-field-breaks-untouched-constructors` (a defaulted pydantic field breaks every direct `Model(...)` site in this no-plugin repo; 4-step must `mypy <whole module>` on disk) + the #117 `verify-the-reported-surface-not-an-adjacent-one`. The 3-source unify + the #112 slug-join now make Projects == the repos you actually work in. UNBLOCKS #114 (FE gộp tab + source badges + hide-UI) + #115 (cleanup). No restart (modules/ hot-reloads; REST-only).
