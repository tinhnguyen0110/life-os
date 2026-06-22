# end_sprint_122-TRACING-2COL — /daily-tracing 2-col redesign (todos | note) (Cairn #122, TRACING-UX2 T2)

> Result. The corrected /daily-tracing redesign (user-CHỐT — hard-code templates REJECTED): a 2-col screen — LEFT todos (text + tick + optional inline 🔔-remind) | RIGHT day-note (text + optional 🔔-remind, wired to #121). Dropped the chip-row/emoji/color/goal-field/heavy-form/template-picker; kept streak+heatmap small/collapsed. Commit `<hash>` `feat(sprint-122-tracing-2col)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + tsc + vitest 1030/0 + count-drop audit). Cairn #122 TRACING-UX2 T2 — fe-only, CLOSES on this commit → **TRACING-UX2 redesign DONE** (#121 BE + #122 FE). user-CHỐT. Disjoint from #121.

## What shipped (FE — 4 mod + 1 new)
| File | Change |
|---|---|
| `app/tracing/page.tsx` (REWRITTEN) | 2-col: LEFT Hoạt động (add-via-text → createActivity(text, goal:1); tick → log(id,{val:1}) → today.done flips; done todo = checked/line-through/not-re-loggable; optional inline 🔔-remind via RemindControls #111) + RIGHT Note (textarea + optional 🔔-remind → /tracing/notes #121). Streak+heatmap in a collapsed `<details>`. RENDER-ONLY (BE computes done/streak/heatmap/score). |
| `lib/useTracingNotes.ts` (NEW) | the /tracing/notes data hook (list/create/delete + refetch). |
| `lib/types.ts` | `TracingNote`/`TracingNoteInput` mirror the #121 FROZEN shape {id,text,remindAt,remindRepeat,remindChannel,created} — named `Tracing*` to avoid colliding with the wiki `NoteInput`. |
| `lib/api.ts` | createTracingNote/deleteTracingNote/getTracingNotes (the #121 endpoints). |
| `app/tracing/__tests__/tracing.test.tsx` (net −5: −27 dropped-feature, +22 new-behavior) | the 2-col + todos(add/tick/done/remind/archive/empty) + note(add/remind/delete/empty/load-error) + inverted-mock-diff + KEPT-from-#65 (streak/heatmap/loading/error). |

## Design (LOCKED — binary-todo on the measured-habit BE, ZERO BE change)
- **🔴 "todo" = an activity with a hidden goal=1; "tick" = log one session (val=1) → val≥goal → today.done flips.** So a binary todo is expressed on the EXISTING measured-habit BE — ZERO backend change (render-only + the existing activity/log endpoints). Clean reuse.
- **2-col, simple:** LEFT add-via-text (no chips/emoji/color/goal-field/heavy-form); RIGHT a polished note card. Both reuse the #111 RemindControls (time+repeat+channel). Streak/heatmap KEPT but in a collapsed `<details>` (not the focus).
- **DROPPED (the user-rejected set):** the 8-preset-chip row, emoji/color/goal fields, the heavy multi-field add-form, the TracingTemplatePicker usage (file kept standalone, unused).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** the binary-todo design (add→goal:1, tick→log val:1, done flips — ZERO BE change); 2-col + useTracingNotes wired to #121; types mirror the frozen shape (Tracing* names avoid the wiki collision); RemindControls reused. FE-only stage (BE tree clean post-#121 — no cross-lane). ✅
- **🔴 COUNT-DROP AUDIT (Gate-3 — verified legitimate, NOT rubber-stamped):** vitest 1030 < the 1035 anchor. I read the REMOVED tests + the NEW tests: the −27 removed are DROPPED-FEATURE tests (#110 heavy-add-form/auto-slug, #111 channel-in-old-form, the template-picker, emoji/goal fields); the +22 new RE-COVER every SURVIVING behavior — streak thresholds (≥7🔥/≥3✦), heatmap 84-cells, tick=log, remind-sends-fields, honest-empty (todos+notes), error paths (GET error→retry, notes-error-doesn't-break-page), archive. **No real coverage lost** — the net −5 is genuinely obsolete dropped-feature tests. Gate-3 count-drop-with-reason-and-removed-feature = legitimate. ✅
- **tsc clean; vitest 89 files / 1030 passed / 0 failed** (independent re-run, tail clean). ✅
- **frontend-w3-2 Chrome :3010:** 2-col; add-todo→tick→green+streak; note+🔔→chip; collapsed heatmap expands; NO chips/emoji/goal/form/template; dark-mode; console clean; inverted mock-diff (dropped=0 present, kept present); scoped cleanup. ✅

## 3 Gates
- **Gate 2 (Function):** the 22 new-behavior tests + tsc + vitest 1030/0 + Chrome 2-col flow + the binary-todo design. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step; **count-drop AUDITED legitimate** (−5 = obsolete dropped-feature, surviving behavior re-covered — the explicit-count-with-reason convention, verified not trusted); staged EXACTLY the 5 FE files (NO #121 BE / template / data leak); commit format. ✅

## Assumptions (user-review)
- **"todo" = activity goal=1, "tick" = log val=1 → done** (binary todo on the measured-habit BE, no BE change). **How to change:** the add/tick handlers in page.tsx.
- **streak/heatmap KEPT but collapsed** (not the focus). **How to change:** the `<details>` in page.tsx.
- **dropped: chips/emoji/color/goal-field/heavy-form/template-picker** (user-rejected). **How to change:** re-add to page.tsx (the user rejected them).

## Notes
- Cairn #122 TRACING-UX2 T2 — **COMPLETES the TRACING-UX2 redesign** (#121 BE day-notes + this #122 FE 2-col). user-CHỐT (the corrected text+action direction; the stale hard-code-template spec was REJECTED + never built — the kickoff-catches-drift discipline held: team-lead rewrote the spec, I dispatched the corrected one, frontend built the right thing). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). 🔴 **The Gate-3 count-drop audit is the standout:** a count DROP (1035→1030) "with reason" is a real scope-drop RISK — I didn't accept the rationale, I read the removed vs new tests + confirmed every SURVIVING behavior (streak/heatmap/tick=log/remind/honest-empty/error) is re-covered by the new 22, so the −5 is genuinely obsolete dropped-feature tests, not lost coverage. (The honest-mirror of the mock-diff lesson, inverted: a redesign DROPS features on purpose — verify it dropped EXACTLY the rejected set + kept the rest.) The binary-todo-on-measured-habit-BE design = ZERO backend change (clean reuse). **Parallel-lane staging (6th clean):** committed FE-only; #121 BE was committed+landed first (no cross-lane). No restart (FE). After push → team-lead Chrome-verifies the 2-col (the user payoff) + dispatches #123 (Dev Activity: you-only + sort-recent + GitHub-heatmap).
