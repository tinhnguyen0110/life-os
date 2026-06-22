# end_sprint_112-PROJECTS-DEV-ACTIVITY — projects↔dev_activity slug-join per-project dev-stat (Cairn #112, PROJECTS-UNIFY T1)

> Result. Projects (id=slug, lowercase) + dev_activity (repo=basename, raw-case) read the SAME git but couldn't join (identity mismatch). Added a per-project dev-stat JOINED by `slug(dev_activity.repo)==project_id` at the read layer — `GET /projects/{id}/dev-activity` + MCP `project_dev_activity`. Commit `<hash>` `feat(sprint-112-projects-dev-activity): slug-join per-project dev-stat (#112)`. Status: ✅ verified (backend-w3 built, FORWARD+REVERSE 2307/0; architect 4-step + INDEPENDENT live teeth — life-os→251 commits, found:false-honest). Cairn #112 PROJECTS-UNIFY T1 — be-only (closes on this commit). Committed SEPARATELY from #111 (the tangle resolved via the (b) hunk-split; #111@48 → #112@49). BLOCKS #113/#114/#115 (auto-unblock).

## What shipped (projects + MCP + test)
| File | Change |
|---|---|
| `projects/service.py` (`dev_stat_for_project`) | the slug-join: `key=slug(project_id)` → `dev_store.rows_since(since)` → filter `slug(r["repo"])==key` → aggregate commits/locNet/lastActiveDay/activeDays, grouped by RAW basename (slug-collision → both). found:false-honest when not scanned. days clamped ≥1. case-insensitive. lazy-import dev_activity (cycle-safe, market↔macro precedent). |
| `projects/schema.py` | `ProjectDevStat` + `RepoDevStat` ({projectId, found, commits, locNet, lastActiveDay, days, activeDays, matches[], reason?, warning?}). |
| `projects/router.py` | `GET /projects/{id}/dev-activity`. |
| `mcp_servers/read_server.py` + CATALOG.md | `project_dev_activity` tool (parity #24; TOOLS 48→49). |
| `tests/test_projects_dev_activity.py` (NEW, 11) | slug-join + found:false + collision + case-insensitive + MCP≡REST parity. |

## Design (LOCKED — slug-join at READ, honest-not-found, collision-both, keep-storage)
- **the join key = slug(dev_activity.repo) == project_id** at the READ layer ONLY. dev_activity KEEPS its raw-basename storage (git-honest — the storage truth); projects keep lowercase slugs (canonical). The mismatch is bridged by slugifying the dev_activity repo at join time. (NOT changing how dev_activity stores — that was explicitly OUT; #113 handles the source.)
- **honest found:false (the distinguishing teeth):** a project whose repo is NOT in the dev_activity scan → `found=false, commits=0, reason="...not in DEV_TRACING_ROOTS / not scanned"` — NEVER a fabricated 0-as-if-real. (The #105-family honest-not-found.)
- **slug-collision → both + warning:** ≥2 repos with the same basename → same slug → found=true, summed, + per-repo `matches[]` + a warning (honest, not silently merged).
- **case-insensitive + days≥1:** project_id slugified (reuses the #105 lookup); days clamped to ≥1 (window ≥ today).
- **MCP≡REST parity:** `GET /projects/{id}/dev-activity` + MCP `project_dev_activity` both via `dev_stat_for_project` (byte-identical, #24).

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the slug-join (key=slug, rows_since filter slug(repo)==key, group-by-basename collision); found:false-honest; lazy-import cycle-safe; the staged diff is #112-ONLY (the 3 "reminders_channels" hits are assert COMMENTS, not #111 code — #111's reminders_channels already committed in 2378e56; verified via grep). ✅
- **🔴 INDEPENDENT live teeth (service path):** `dev_stat_for_project("life-os")` → found=True, **251 commits** (== dev_activity scan + backend's report), lastActive today; unscanned → found=False, commits=0, reason (honest); "LIFE-OS" uppercase → found=True (case-insensitive). ✅
- **Suite:** backend FORWARD + REVERSE = **2307 passed / 0 failed** (the count-asserts==49 now consistent — both tools committed: #111 reminders_channels@2378e56 + #112 project_dev_activity); test_projects_dev_activity 11 green incl MCP≡REST parity; mypy clean. never staged backend/data/.

## 3 Gates
- **Gate 1 (API/MCP/agent):** GET /projects/{id}/dev-activity + MCP project_dev_activity (parity #24); found:false-honest + reason; collision→both+warning; case-insensitive. ✅
- **Gate 2 (Function):** the distinguishing teeth (real-join 251 / found:false-honest / collision / case-insensitive / MCP≡REST); independent live; FORWARD+REVERSE 2307/0; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY the #112 files (read_server now-pure-#112 since #111 committed, CATALOG #112-row, projects/*, test, asserts@49 — NO #111 code-leak, NO #113, no data/.env); commit format. ✅

## Assumptions (user-review)
- **join = slug(dev_activity.repo)==project_id at READ** (dev_activity storage unchanged). **How to change:** the slug-match in dev_stat_for_project; #113 changes the SOURCE.
- **not-scanned → found:false + reason** (honest, not fake-0). **How to change:** n/a (intentional honest-mirror).
- **slug-collision → both summed + warning + matches[].** **How to change:** the by-repo grouping in dev_stat_for_project.

## Notes
- Cairn #112 PROJECTS-UNIFY T1 — user-CHỐT (link Projects↔DevActivity). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The tangle resolution:** #111 + #112 interleaved in read_server.py + the count-asserts (the serialization break — #112 started before #111 committed). Resolved via (b) separate commits: #111@48 (the reminders_channels hunk-split, committed 2378e56) → backend bumped asserts→49 → #112@49 (this commit, read_server now pure-#112 since #111 landed). The disk-truth discipline (re-verify the actual assert state before every commit, never trust a crossed "go") carried it through 6 flip-flops with ZERO broken commits. The slug-join is the read-layer bridge (#84/#85/#105 repo-identity: slug=canonical key, basename=storage truth). BLOCKS #113 (auto-discover) / #114 (FE) / #115 (git-reader dedup) — they auto-unblock. Restart needed for the MCP live-verify (read_server not in reload allowlist) — backend's FORWARD/REVERSE 2307/0 + my service-path teeth cover the logic; team-lead live-verifies the MCP post-push-restart.
