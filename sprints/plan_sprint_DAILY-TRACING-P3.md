# Sprint DAILY-TRACING-P3 — FE /tracing S14 screen (Cairn #65 Phase 3)

> Created 2026-06-21 by architect (designed ∥ while #65-P2 commits). #65 Phase 3 of 4. The user-facing screen for the tracing module. HOLD dispatch until #65-P2 commits (sequential pipeline). frontend-w3-2 BUILDS; architect commits (§3, FE-domain commit-hygiene). Ship per the UI-async rule (FE-verified → commit+push immediately; user feedback async-reactive).

## Context
P1 built the BE (modules/tracing/, GET /tracing). P2 shipped the MCP agent surface. P3 = the human surface: the S14 "Daily Tracing" screen — the user sees today's habit board (per-activity cards w/ streak + today progress), a 12-week heatmap, the score panel, and can LOG a session + add/edit activities. Render-only — BE computes ALL derived metrics (streak/pct/heatmap/score); FE displays + POSTs raw sessions.

## Scope
IN: `frontend/app/tracing/page.tsx` (NEW, the S14 screen) + `lib/useTracing.ts` (data hook) + `lib/api.ts` tracing fns + `lib/types.ts` Tracing types + `lib/nav.ts` /tracing entry + `lib/tokens.css` tracing tokens (ported from mock) + tests (page + nav + api). Port tokens/layout from the mock — do NOT redesign.
OUT: P4 brief-wire. NO change to the BE (P1/P2 frozen). NO new derived logic in FE (BE computes; FE renders).

## Mock to port (EXACT source)
**`template/Life Command/app/screens-active.js` lines 53-210** — the "S14 Daily Tracing" render block. Port its structure:
- per-activity card: emoji/icon + name, streak badge (fire 🔥 if streak≥7, ✦ if ≥3, none else — line 80), today val/goal + pct + done state, week bars (line ~204 "Nd streak").
- the SCORE panel: total/done/pct, timeActive, topStreak (the "Streak tốt nhất" stat, lines 148-149).
- the TIMELINE + 12-week HEATMAP grid (lines 167-204): `heatmap12w` rendered as a 12×7 grid, each cell colored by its day-COUNT (0-N activities met; mock uses 0-4 score→color band — port the band; note our heatmap is COUNT not capped-4, so band by count, max = active-activity-count).
- Mock data shape (`data.js` 110-158) ↔ our schema (below) — they ALIGN, just wire real API.

## Backend schema shape FE consumes (GET /tracing → TracingOverview, render-only)
```
TracingOverview { date:str, activities: ActivityView[], heatmap12w:int[84] (per-day COUNT met), score: TracingScore }
ActivityView { id, name, emoji, icon, unit, color, goal:float,
               today: { done:bool, val:float, dur:str("Hh Mm"), durMin:int, note:str|null, pct:int(0-100), sessions:int },
               streak:int (consec goal-met VN-days), week:float[7] (Mon→Sun Σval), history12w:float[84] }
TracingScore { total:int, done:int, pct:int(0-100), timeActive:str("Hh Mm"), topStreak:int }
```
- honest-empty: 0 activities → `activities:[]`, heatmap all-0, score all-0 → render an empty-state ("No activities yet — add one"), NOT a crash/blank.
- **BE computes streak/pct/heatmap/score — FE renders only. Do NOT recompute any derived metric client-side.**

## Actions FE wires (write endpoints — all REST, BE owns logic)
- **Log a session:** `POST /tracing/{id}/log` body `{val:float, dur_min?:int, note?:str}` → returns updated ActivityView (re-render the card). val<0 → 422 w/ agent_error {error:{code,message,hint}} → show the message.
- **Add activity:** `POST /tracing/activities` body `{id, name, goal, unit?, emoji?, icon?, color?}` → 409 dup-id (agent_error), 422 blank/val<0.
- **Edit activity:** `PUT /tracing/activities/{id}` (partial). **Archive:** `DELETE /tracing/activities/{id}` (soft — logs survive; the card disappears from the board).
- Error shape = the post-#46/#70 `{error:{code,message,hint,retryable}}` — use the existing `errorFromBody`/`ApiError` (already reads {error} first, legacy fallback) from lib/api.ts. Show `hint` to the user on a retryable error.

## Runtime
FE `npm run dev` :3010 (NOT :3000/:3100 — memory dev-server-ports). BE container :8686 already up (I restarted it for the tracing mount). GET /tracing live-returns honest-empty now (no activities) — create one via the screen to see cards.

## Baseline
vitest = post-#31 count (856 + the new tracing tests). tsc --noEmit clean. Keep 0-failed/0-errors.

## Test ownership split
frontend: page render (cards/heatmap/score/empty-state) + log-session interaction + add-activity + the error-shape display (422/409 hint shown); nav entry; api fns. tester (team-lead's verify): Chrome /tracing live render + log-a-session round-trip on :3010.

## HARD GATE (distinguishing)
- honest-empty: GET /tracing with 0 activities → empty-state renders (not a blank/crash).
- log a session via the screen → the card's today val/pct/streak UPDATES (the write→re-render round-trip).
- streak badge: streak≥7 → 🔥, ≥3 → ✦, else none (port the mock's exact thresholds).
- heatmap: 84 cells, colored by per-day COUNT (0=empty band).
- error: log val<0 → the agent_error message/hint shown (not a silent fail).
- tsc clean; vitest 0-failed/0-errors (NOT "N passed" w/ rejections — memory unhandled-errors-not-green); Chrome self-verify (FE agent) per Gate-2.

## Assumptions (user-review)
- /tracing = the S14 user surface for the habit module: render the BE-computed board + POST raw sessions/activities. Render-only (BE computes all derived). Streak fire badges 🔥≥7/✦≥3 ported from the mock. **How to change:** the page component / the badge thresholds.
- Ship per UI-async rule: FE-verified (tsc+vitest+Chrome) → commit+push immediately; user tweaks the look later async-reactively (reversible FE).

## Notes
- #65 Phase 3 of 4. Mock = screens-active.js S14 block (53-210); schema = P1 TracingOverview. frontend-w3-2 BUILDS; architect commits feat(sprint-DAILY-TRACING-P3) (FE-domain commit-hygiene: explicit FE-only stage, no template/backend/data/.mcp leak; git-status-after-stage zero FE-dirty incl. all touched test files). HOLD until P2 commits. Next: P4 brief-wire (life_brief streak-at-risk rule) → #65 DONE (mốc lớn) → #63 → #64.
