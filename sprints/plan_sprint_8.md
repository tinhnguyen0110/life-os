# Plan Sprint 8 — Graveyard (S4) [reuses Projects data · completes the Projects story]

> Author: architect · 2026-06-06 · Status: kickoff DONE · awaiting team-lead mock-diff + greenlight.
> Spec: SPEC §S4 (Nghĩa địa). Mock: `template/Life Command/app/screens-projects.js` `SCREENS.graveyard` + `DB.graveyard` (`data.js:54`) — HAS a mock → PORT. ARCH §9 (Graveyard = "ghép từ projects data"). Completes S2 list → S3 detail → **S4 Graveyard**.
> Memory: `abandon-orthogonal-to-health` (CRITICAL — abandoned = explicit human flag, NOT health=dead), `schema-freeze-gate`, `unhandled-errors-not-green`, `mock-diff-catches-dropped-feature`, `dev-server-ports`, `single-dev-no-overengineering`.

## Objective
Replace the Graveyard EmptyScreen with the real S4 "Nghĩa địa" — the honest-mirror of abandoned projects. Reads the ALREADY-shipped Projects abandon data (Sprint 1: `POST /projects/{id}/abandon` writes `abandoned/abandonedReason/abandonedAt/abandonedProgress` to status.md). Adds pattern stats (avg abandon %, common reasons, reached-user vs abandoned-before-user, build-to-90 reflection) + restore-to-active + a `lesson` field. Mostly a service+FE sprint (no new external source, no new write-store pattern). Full feature per SPEC §S4, simplest impl (north-star).

## What ALREADY exists (Sprint 1 — Rule#0 verified at kickoff)
- `POST /projects/{id}/abandon` (ProjectAbandonInput: `reason`, `progress?`) → writes status.md `abandoned/abandonedReason/abandonedAt/abandonedProgress`.
- `list_projects()` EXCLUDES abandoned · `get_project(id)` INCLUDES abandoned · `_is_abandoned(meta)` helper.
- So the abandoned SET exists in the store; Graveyard READS it + aggregates. No new write path for abandonment itself.

## Gaps to close this sprint (kickoff findings)
1. **ProjectStatus does NOT expose the abandon fields** — `abandoned/abandonedReason/abandonedAt/abandonedProgress` are written to status.md but NOT in the frozen ProjectStatus response shape. Graveyard needs them. → add to the Graveyard read shape (a `GraveProject` view), NOT necessarily ProjectStatus (keep that frozen; graveyard has its own shape).
2. **No `lesson` field** — the mock has `lesson:` per grave (the "bài học"). `ProjectAbandonInput` has `reason` but no `lesson`. → ADD `lesson` to abandon input + status.md + the grave shape.
3. **No restore endpoint** — SPEC §S4 "Phục hồi dự án về active (tùy chọn)". → ADD `POST /projects/{id}/restore` (clears the abandoned flag).
4. **No pattern-stats aggregation** — avg abandon %, common reasons, reached-user-vs-not. → new derived in the graveyard service.

## Honest-mirror — every SCREENS.graveyard panel (none dropped)
| Mock panel | Data | Sprint 8 |
|---|---|---|
| Title + "Xuất bài học" button | export lessons (text/markdown) | **LIVE** (export = client download of the lessons list; simplest) |
| Pattern summary bar ("68% avg" + build-to-90 narrative) | derived: avg abandonedProgress + count | **LIVE** |
| Lưới / Dòng-thời-gian toggle | grid vs timeline (sort by died) | **LIVE** (toggle, both render the same graves) |
| Grave cards grid (name/peak%/reason/lesson/died) | abandoned set | **LIVE** |
| "Bài học rút ra" panel (aggregated lessons) | distinct lessons from graves | **LIVE** |
| (SPEC) reached-user vs abandoned-before-user stat | derived: count users>0 vs users==0 at abandon | **LIVE** (SPEC §S4, not explicit in mock — honest superset) |
| (SPEC) restore to active | `POST /projects/{id}/restore` | **LIVE** |

## GraveProject + GraveyardStats SHAPE (full field list — goes IN the T1 gating dispatch msg #1)
```
GET /graveyard response .data:
GraveyardStats {
  graves:        list[GraveProject]
  count:         int                 # number abandoned
  avgPeak:       float               # avg abandonedProgress across graves (the "68%" — carries {sum,count})
  commonReasons: list[{reason, count}]  # reasons grouped+counted, desc
  reachedUser:   int                 # graves with users>0 at abandon
  beforeUser:    int                 # graves with users==0 (the build-to-90/0-user pattern count)
  lessons:       list[str]           # distinct non-empty lessons (for the "Bài học rút ra" panel + export)
}
GraveProject {
  id:        str                     # project id (for restore)
  name:      str
  peak:      int                     # abandonedProgress (% at abandon; falls back to progress, else 0)
  reason:    str                     # abandonedReason
  lesson:    str | None              # NEW field (status.md lesson:, else None)
  died:      str                     # abandonedAt (ISO-8601 → FE formats "MM/YYYY")
  users:     int                     # users at abandon (for reached-user vs before-user)
  health:    str                     # still expose commit-age health (abandoned ≠ dead — orthogonal)
  repo:      str
}
```
Plus: `ProjectAbandonInput` gains `lesson: str | None` (max 2000). New `POST /projects/{id}/restore` (no body) → clears abandoned*, returns ProjectStatus.

## Tasks (4: BE gating → FE → tester)
- **T1 [backend, GATING] — graveyard module + abandon `lesson` + restore.**
  - NEW `backend/modules/graveyard/` (schema/service/reader OR reuse projects reader) → `GET /graveyard` returns GraveyardStats. Reads the abandoned set via the projects store (`_is_abandoned` + status.md fields).
  - EXTEND projects: `ProjectAbandonInput` + `lesson`; status.md write includes lesson; NEW `POST /projects/{id}/restore`.
  - Pattern stats derivation (avgPeak/commonReasons/reachedUser/beforeUser/lessons). FREEZE field-by-field + announce serving + curl payload.
  - Gates T2/T3.
- **T2 [backend] — graveyard router** (if separate from T1's module file). `GET /graveyard`. Envelope, fail-open (empty graveyard → empty stats, not 500). `MODULE` auto-discovered. (May fold into T1 if the module is small — decide at dispatch.)
- **T3 [frontend] — S4 Graveyard screen** (`app/graveyard/page.tsx`, replace EmptyScreen).
  - Port SCREENS.graveyard: pattern summary bar, grid/timeline toggle, grave cards (name/peak-bar/reason/lesson/died), "Bài học rút ra" panel, "Xuất bài học" (client download), reached-user-vs-before stat. Restore button per grave (→ POST /restore → refetch). Blocked by T1 frozen + serving.
- **T4 [tester] — verify graveyard.**
  - pytest (graveyard reads abandoned set; abandon w/ lesson round-trips; restore clears the flag + project reappears in list_projects; pattern stats math: avgPeak/commonReasons/reachedUser/beforeUser on known fixtures; empty graveyard → empty stats not crash). API curl (`GET /graveyard` envelope; POST abandon+lesson; POST restore; abandoned excluded from /projects, included in /graveyard). Chrome `docker compose up -d`: S4 renders, value-by-value graves vs `GET /graveyard`, restore round-trips (grave → active), export works, console 0, 0 unhandled. Pre-scaffold from T1.

## Logic/Algorithm (architect-decided — decide-and-log)
- **graves:** the abandoned set = all tracked projects where `_is_abandoned(meta)`. For each: peak=abandonedProgress (else progress, else 0), reason=abandonedReason, lesson=status.md lesson, died=abandonedAt, users=status.md users, health=commit-age (orthogonal — abandoned still shows its health).
- **avgPeak:** mean of graves' peak (round 1 dp); 0 if no graves. carries {sum, count} (agent-readable).
- **commonReasons:** group graves by reason (exact, trimmed), count, sort desc. (Simple — no NLP clustering, north-star.)
- **reachedUser / beforeUser:** count graves with users>0 vs users==0 at abandon (the build-to-90/0-user pattern = beforeUser).
- **lessons:** distinct non-empty `lesson` strings across graves (for the panel + export).
- **restore:** clears `abandoned/abandonedReason/abandonedAt/abandonedProgress/abandonedUsers` from status.md (md_store write = 1 commit) → project returns to list_projects. **PRESERVES `lesson`** (Edge 1 ruled — honest-mirror, lesson is hard-won history; persists if re-abandoned). Idempotent: 404 unknown id, **200 no-op if already not-abandoned**.
- **abandonedUsers snapshot (Edge 2 ruled):** `abandon_project` ALSO writes `abandonedUsers = current users` at abandon-time (current code does NOT). The grave `users` reads `abandonedUsers` (fallback current users, else 0) → reached/before-user pattern is historical truth, immune to later status.md edits.
- **avgPeak skips missing (Edge 3 ruled):** mean over graves WITH a valid abandonedProgress — None is SKIPPED, NOT treated as 0 (treating-as-0 skews the % low). 0.0 if no valid graves. carries {sum,count}.
- **Field names = mock vocab** (resolved vs backend's recs): API response uses `graves/peak/reason/lesson/died` (mock-aligned, FE mirrors 1:1); status.md keeps `abandonedReason/abandonedProgress/abandonedAt/abandonedUsers` keys — the service maps store→display.
- **abandoned ≠ health** (the CRITICAL memory): Graveyard uses the `abandoned` flag for membership, `health` only as a displayed attribute. NEVER filter graveyard by health=dead.

## Defensive (MANDATORY)
- Empty graveyard (no abandoned projects) → `{graves:[], count:0, avgPeak:0, commonReasons:[], reachedUser:0, beforeUser:0, lessons:[]}`, 200 not 500.
- Abandoned project with missing abandonedProgress → peak falls back to progress, else 0 (no crash).
- Missing lesson → null (panel skips it; never fabricate a lesson).
- Malformed status.md in an abandoned project → skip+warn (same fail-open as projects list).
- restore unknown id → 404; restore non-abandoned → 200 no-op (or 404 — decide: 200 no-op, idempotent).
- abandon with empty reason → 422 (reason already min_length 1).

## Dispatch standards
- Runtime: `docker compose up -d` (FE :3010 → BE :8001). Baseline: pytest 475, vitest 268 (post-S7).
- **`## Read first (memory)` per role** (Graveyard: BE → `abandon-orthogonal-to-health` + `schema-freeze-gate` + `unhandled-errors-not-green`; FE → `mock-diff-catches-dropped-feature` + `unhandled-errors-not-green` + `dev-server-ports`; tester → `verify-live-app-not-just-suite` + `behavior-test-not-field-read` + `workaround-then-ask-why-accepted`).
- **Full field list in T1 msg #1** (GraveyardStats + GraveProject + the abandon-lesson + restore additions). Freeze field-by-field.
- Test-ownership-split line. FE: mock = SCREENS.graveyard, mirror frozen shape render-only.

## Dispatch ordering
1. T1 GATING (graveyard module + abandon-lesson + restore) alone → freeze.
2. T2 (router) after T1 (or folded into T1).
3. T3 (FE) after schema frozen + serving. T4 pre-scaffolds from T1.

## Out of scope (north-star)
- No NLP reason-clustering — exact-match grouping for commonReasons.
- No abandonment from the Graveyard screen (abandon happens from Projects S2/S3 — Graveyard is the view + restore).
- "Xuất bài học" = a simple client-side text/markdown download of the lessons list (no server-side report gen).
- pattern-check routine (≥90% & 0 user alert) — that's an Automation-sprint routine; Graveyard SHOWS the data, the routine is separate (ARCH §9 step 7). This sprint = the screen + read, not the scheduled alert.
