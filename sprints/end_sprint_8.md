# End Sprint 8 — Graveyard (S4) [completes the Projects story · reuses shipped abandon data]

> Result doc (CLAUDE.md §3.2). The `graveyard` module: the honest-mirror of abandoned projects (S4 "Nghĩa địa"). Reads Sprint-1's already-shipped abandon data (no new external source), adds pattern stats + a `lesson` field + restore-to-active. Completes the Projects story: S2 list → S3 detail → **S4 Graveyard**.
> Author: architect · 2026-06-06 · Commit: `feat(sprint-8)` on `main`.

---

## 1. What shipped

### Backend — `graveyard` module (registry auto-discovered) + projects extensions
- **`modules/graveyard/`** — `GET /graveyard` → `GraveyardStats{graves[GraveProject], count, avgPeak, commonReasons[{reason,count}], reachedUser, beforeUser, lessons[]}`. REUSES `projects.service` for abandoned-set discovery (no duplication). No routine (read-on-demand). `GraveProject{id,name,peak,reason,lesson|None,died,users,health,repo}` — mock-aligned display vocab; service maps status.md abandoned* → these names.
- **projects extensions:** `ProjectAbandonInput` + `lesson: str|None`; `abandon_project` now snapshots `abandonedUsers` (historical truth); NEW `POST /projects/{id}/restore` (clears abandoned* + abandonedUsers, **PRESERVES lesson**, idempotent: 404 unknown / 200 no-op if not abandoned).

### Frontend — S4 Graveyard screen (`app/graveyard/page.tsx`, replaced EmptyScreen)
- Ported `SCREENS.graveyard`: pattern summary bar (avgPeak% + build-to-90 narrative + reached-vs-before-user), grid/timeline toggle, grave cards (name/peak-bar/reason/💡lesson/died), "Bài học rút ra" lessons panel, "Xuất bài học" export, per-grave Restore button (→ POST /restore → refetch).
- **null-lesson skipped, never fabricated** (`{g.lesson && ...}`); honest empty-states (no graves → "🎉", no lessons → prompt). `useGraveyard.ts` + `getGraveyard()` + types.

### Logic (architect-decided — see §4)
avgPeak (mean abandonedProgress, SKIP missing) · commonReasons (normalized-lowercase group, count desc) · reachedUser/beforeUser (users>0 vs ==0 at abandon) · lessons (distinct non-empty) · restore preserves lesson + snapshots abandonedUsers.

---

## 2. Verification (Rule #0 — architect + team-lead; tester T4 Chrome = the open box)

### Architect 4-step (full functions + live container)
| Check | Result |
|---|---|
| pytest | **499 passed, 0 errors** |
| vitest | **279 passed, solo-stable** (≥268 baseline; the parallel-Chrome-contention "3 failed/10 unhandled" was infra, not real — solo runs clean) |
| tsc | clean |
| Container `/graveyard` | count 1, avgPeak 33.0, reachedUser 1, beforeUser 0, grave "Active Project" (peak 33, reason "pivot", lesson null, health "dead") — all 7 keys |
| **orthogonal-to-health proven on REAL data** | grave health="dead" but IN graveyard because abandoned=true; abandoned EXCLUDED from /projects, INCLUDED in /graveyard ✓ |
| null-lesson (FE page.tsx:140) | `{g.lesson && ...}` skips 💡 line, never fabricates ✓ |
| restore preserves lesson (code + test) | `abandon_keys` excludes lesson; teeth-test in test_projects_reader.py (RED if lesson re-added) ✓ |

### team-lead Rule#0 live value-diff (canonical stack)
✅ Abandoned `crewly` WITH a lesson → S4 rendered value-by-value (card: scope creep · 💡"start tiny, ship at 70%" · ↩Khôi phục · pattern bar · lessons panel · export · toggle, console 0). **RESTORE-PRESERVES-LESSON confirmed LIVE**: restore → crewly left graveyard + rejoined /projects + lesson STILL in status.md. Cleaned up. PASS, pre-greenlit.

### Tester T4 (Gate-3 Chrome UI — PENDING, their lane)
pytest + API curl + Chrome value-by-value + restore behavior-test + orthogonal-to-health.

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema (GraveyardStats/GraveProject frozen 7/7+9/9, ProjectAbandonInput+lesson, restore) · ☑ integration tests · ☑ existing pass · ☑ auto-discovered · ☑ envelope · ☑ codes (200 fail-open, restore 404/200-no-op, abandon 422) · ☑ self-describing (avgPeak carries {sum,count}).

### Gate 2 — Function
☑ unit tests (stats math, restore-preserves-lesson teeth-test in discoverable location, abandonedUsers snapshot, fail-open) · ☑ pytest 499/0 + vitest 279 solo · ☑ edge cases (empty graveyard, missing abandonedProgress, null lesson, restore non-abandoned) · ☑ error path (fail-open) · ☑ tsc clean · ☑ FE Chrome self-verify.

### Gate 3 — Sprint
☑ end_sprint_8 written · ☑ architect 4-step (full functions + live container) · ☐ **tester T4 Chrome — PENDING** · ☑ counts ≥ baseline (pytest 475→499, vitest 268→279) · ☑ findings flagged (§5) · ☑ format `feat(sprint-8)`.

**VERDICT: backend + FE GREEN. Gate 3 holds on tester T4 Chrome + team-lead pre-greenlit → commit on T4 report.**

---

## 4. Assumptions (user-review — decide-and-log)

- **Graveyard membership = the `abandoned` flag, NOT health=dead** (the CRITICAL orthogonal-to-health rule). A health=dead project isn't auto-buried; abandonment is an explicit human decision. To change: would conflate two orthogonal axes — don't.
- **Restore PRESERVES `lesson`** (clears only abandoned* + abandonedUsers). Reason: a revived project's hard-won lesson shouldn't vanish; persists if re-abandoned. To change: add lesson to the restore clear-set (but preserve is more honest-mirror).
- **`abandonedUsers` snapshotted at abandon-time** — so the reached-vs-before-user pattern is historical truth, immune to later status.md edits. To change: read live users instead (less accurate for the pattern).
- **avgPeak SKIPS graves with missing abandonedProgress** (not treated as 0 — that skews the % low). carries {sum,count}. To change: include missing-as-0 (would distort the pattern number).
- **commonReasons = exact normalized-lowercase grouping** (no NLP clustering — north-star). To change: add fuzzy grouping if reasons vary in phrasing.
- **"Xuất bài học" = client-side text download** (no server report gen — simplest). To change: add a server endpoint if a richer export is wanted.
- **Restore is the only Graveyard write** — abandoning happens from Projects S2/S3, not the Graveyard screen. The pattern-check (≥90% & 0-user alert) routine is a separate Automation sprint — Graveyard SHOWS the data, doesn't schedule the alert.

---

## 5. Risks / out-of-scope (future)

- **pattern-check routine** (≥90% & 0-user → alert) — deferred to the Automation sprint (ARCH §9 step 7); Graveyard shows the pattern data, the scheduled alert is separate.
- **Sidebar nav badges static** — carried from S7 (`sidebar-badges-static-placeholder`); wire all together in a shell task.
- **avgPeak=0 copy** — the pattern-bar sentence reads awkwardly when avgPeak=0 (no progress recorded); FE polished the 0/empty case (display-only string guard). [Resolved this sprint as a copy fix.]

---

## 6. Retro (process learnings)

1. **Restore docstring LIED while the code was correct → memory `test-where-the-reader-greps` + reinforced `behavior-test-not-field-read`:** restore preserved lesson (code right), but the docstring said "clear ... + lesson" AND the preserve-test lived in test_graveyard.py not test_projects (where restore_project lives + where team-lead grepped). So the verifier grepped, found no test, fell back to the lying docstring. Fix: docstring corrected + teeth-test moved to the discoverable location. **Lesson: a test belongs where the reader greps (next to the function); a docstring is a claim, behavior-test it.**
2. **3 real-data edge cases the mock's clean data hid** — every mock grave has peak+lesson; real abandons may not. Settled pre-freeze: restore-preserves-lesson, abandonedUsers-snapshot, avgPeak-skip-missing. The mock-vs-real gap is a recurring source of edge bugs.
3. **Reused shipped infra** — Graveyard read Sprint-1's abandon data instead of a new write path; lowest-risk sprint, completes the Projects story cleanly.
4. **Flaky-run discipline** — FE correctly did NOT report off a parallel-Chrome-contention vitest failure (3 failed/10 unhandled under :8001 hammering); solo runs clean (279/279). Gate on solo-stable, not a contended run.

---

## 7. Commit
- `feat(sprint-8): graveyard module (S4) — abandoned-project mirror + pattern stats + lesson + restore + S4 screen` — graveyard module + projects abandon-lesson/abandonedUsers/restore + useGraveyard/graveyard page + plan_8 + end_8. One commit.
- Gated on tester T4 Chrome + the copy-nit polish + team-lead pre-greenlit. After: `sleep 120 && git push` → notify user → Sprint Sync → next sprint (Journal S7).
