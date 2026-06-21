# end_sprint_DAILY-TRACING-P3 — FE /tracing S14 screen (Cairn #65 Phase 3)

> Result. The /tracing S14 "Daily Tracing" screen — the user-facing habit board (per-activity cards w/ streak + today progress, 12-week heatmap, score panel, log/add/edit/archive). Commit `<hash>` `feat(sprint-DAILY-TRACING-P3)`. Status: ✅ verified (FE agent + architect 4-step + team-lead). frontend-w3-2 BUILT; architect committed (§3, sole serialized committer, FE-domain commit-hygiene). Shipped per the UI-async rule (FE-verified → commit+push immediately; user reviews look async). Phase 3 of 4 (P1 BE → P2 MCP → **P3 FE** → P4 brief).

## What shipped (7 FE files: 2 new + 5 modified)
| File | Change |
|---|---|
| `app/tracing/page.tsx` (NEW, 20KB) | the S14 screen — per-activity cards (streak badge 🔥≥7/✦≥3/none, today val/goal/pct/done, week bars), score KPI strip (total/done/pct/timeActive/topStreak), 12-week heatmap (band by per-day COUNT), add/edit/archive forms, log-session action, honest-empty state. Ported tokens from the mock (S14 block screens-active.js 53-210) — render-only. |
| `app/tracing/__tests__/tracing.test.tsx` (NEW, 12 tests) | the distinguishing set (streak-badge boundary teeth, honest-empty, log→re-render, heatmap-by-count, error-shape). |
| `lib/useTracing.ts` (NEW) | the data hook — GET board + log/add/edit/archive; log→reload (re-GET) cycle; fail-closed writes (throw→caller surfaces, no optimistic mutation); malformed-body guard; reads the `warning` envelope. |
| `lib/api.ts` | tracing fns: getTracing / logTracingSession (422 on val<0) / createActivity (409 dup, 422 blank) / updateActivity (PUT partial) / archiveActivity (DELETE soft → {archived}). encodeURIComponent on ids. |
| `lib/types.ts` | TracingOverview / ActivityView / TodayStat / TracingScore / Activity / TracingLogInput / ActivityInput / ActivityPatch (mirror the FROZEN tracing/schema.py). |
| `lib/nav.ts` + `lib/__tests__/nav.test.ts` | /tracing nav entry, screen-id "TRACE" (S14 collision avoided; nav-uniqueness asserted). |
| `lib/tokens.css` | tracing screen tokens (ported from mock, no redesign). |

## Design (LOCKED — render-only, honest-mirror)
- RENDER-ONLY: the BE computes ALL derived metrics (streak/pct/week/heatmap/score); the FE displays + POSTs raw sessions, NEVER recomputes (the raw-data-first contract held on the FE side).
- writes are REFETCH-after + FAIL-CLOSED (log→reload re-GET; throw surfaces to the caller; no optimistic mutation that could drift from the server truth).
- heatmap bands by per-day COUNT relative to max (max = active-activity-count; count≤0→empty bg; capped against divide-by-zero) — faithfully adapts the mock's capped 0-4 to our honest COUNT.

## Verification (FE agent + architect 4-step + team-lead)
- **frontend-w3-2:** vitest 876/0/0, tsc --noEmit clean; teeth-tested streak thresholds (🔥≥7/✦≥3/none boundary goes RED when broken); 6 LIVE Chrome distinguishing cases on the container (honest-empty → add → log val=3 → persist post-reload → archive → cleanup back to 0); screen-id "TRACE" (S14 collision avoided); probe cleaned up (user's board back to 0 activities).
- **architect 4-step (read FULL files on disk, not diff):** useTracing.ts log→reload re-GET cycle (fail-closed, no optimistic) ✅; api.ts 5 methods match the LIVE REST contract (I curl-verified those endpoints in P1/P2 — getTracing/log/create/update/archive, encodeURIComponent ids, archive→{archived}) ✅; page.tsx streak badge `streak>=7?🔥:streak>=3?✦:""` EXACT mock thresholds ✅; honest-empty (`acts.length===0`→empty panel) ✅; heatColor bands by COUNT (divide-by-zero capped) ✅; render-only (no client recompute) ✅; the timeline divergence is honest + in-code-documented (below).
- **architect independent re-run:** FULL vitest 876/0/0 (79 files, full tail clean — no unhandled rejection), tsc exit 0. No regression from the api.ts/types.ts/nav.ts touches.
- **team-lead:** FE report PASS; will HTTP/Chrome verify /tracing live (log→persist cycle + dark-mode + console-clean) post-commit + close P3 on Cairn.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest 876/0/0 + tsc clean + Chrome interaction (honest-empty/add/log/persist/archive); streak-badge teeth; fail-closed writes; malformed-body guard. ✅
- **Gate 3 (Sprint):** end-doc; FE-agent + architect 4-step + team-lead verified; commit-hygiene (explicit FE-only stage, git-status-after-stage zero FE-dirty incl. nav.test.ts; no template/data/.mcp/Instruction/other-sprint-doc leak); commit format. ✅

## Assumptions (user-review)
- **/tracing = the S14 user surface** for the habit module: render the BE-computed board + POST raw sessions/activities. Render-only (BE computes all derived). Streak fire badges 🔥≥7/✦≥3 ported from the mock. **How to change:** the page component / the badge thresholds.
- **tracing timeline: per-ACTIVITY row (NOT per-session)** — the mock timeline shows per-session timestamped rows, but the API's TodayStat exposes only sessions-COUNT + the latest note (no per-session list). The FE renders the timeline as one row PER ACTIVITY that has today activity (honest to the API), NOT fabricated session timestamps. honest-mirror over fabrication (team-lead-approved). **How to change:** add a BE `GET /tracing/{id}/sessions` endpoint (a P-future) then render per-session rows.
- **heatmap bands by COUNT relative to max** (not the mock's capped 0-4) — honest to our COUNT semantic. **How to change:** the heatColor band fn.
- Shipped per UI-async rule: FE-verified → commit+push immediately; user tweaks the look later async-reactively (reversible FE).

## Notes
- #65 Phase 3 of 4. Mock = screens-active.js S14 block (53-210); schema = the FROZEN P1 TracingOverview. frontend-w3-2 BUILT; architect committed (§3, FE-domain commit-hygiene). The timeline-divergence is an HONEST faithful-to-contract rendering, not a dropped feature (a P-future BE endpoint can add per-session rows). Next (auto-run): P4 brief-wire (life_brief streak-at-risk rule — plan ready) → #65 EPIC DONE (full G-HABIT: BE+MCP+FE+brief; team-lead surfaces /tracing to the user + reports the mốc lớn). Then #58 (suite-speed, serialized 3rd) → #63 → #64.
