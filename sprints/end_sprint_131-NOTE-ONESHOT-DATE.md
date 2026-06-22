# end_sprint_131-NOTE-ONESHOT-DATE — note future-date one-shot picker (Cairn #131, = the #125-FE half)

> Result. The note remind UI gained a future-DATE one-shot picker — completing "nhắc 2 loại" end-to-end (the #125 BE one-shot was landed but had no FE picker; #126 was built before #125). The NOTE remind now has a "Lặp lại | Một lần" segment: Một-lần → date(min=today)+time → remindDate+remindAt repeat=off → the BE makes a repeat="once" reminder. Activity remind stays daily (no date picker — scope-guarded). Commit `<hash>` `feat(sprint-131-note-oneshot-date)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + tsc + vitest 1049/0 + the activity-no-date scope-guard). Cairn #131 — fe-only (= my #125-FE dispatch, reconciled to one ID), CLOSES on this commit. Disjoint from any BE.

## What shipped (FE)
| File | Change |
|---|---|
| `lib/types.ts` | +`remindDate: string \| null` on TracingNote (read-back) + `remindDate?` on TracingNoteInput/Update (mirror the #125 frozen shape). |
| `app/tracing/page.tsx` | `RemindControls` +`allowOnce` prop. NOTE card → `allowOnce` → a "Lặp lại \| Một lần" segment; "Một lần" → date picker (`type=date`, min=todayVnDate) + time + channel → body `remindDate` + `remindRepeat:"off"` (BE → repeat="once"); "Lặp lại" → daily/weekdays (no date). Default = recurring. 🔴 the ACTIVITY (todo) RemindControls is called WITHOUT allowOnce → NO date picker (activity stays daily). Chip: one-shot "🔔 <date> lúc <time>" vs recurring "🔔 <time> hằng ngày". Guards: blank date → "Chọn ngày…" no-POST; past date → BE 422 (note_remind_in_past) surfaced honestly. |
| `tracing.test.tsx` (+6 → 1049) | one-shot→remindDate+repeat-off / recurring→no-date / blank-guard→no-POST / past→422-hint / one-shot-chip / 🔴 activity-has-NO-date-picker. |

## Design (LOCKED — note-only one-shot, scope-guarded, default recurring)
- **the note remind = 2 kinds (the FE for #125):** "Một lần" (one-shot) = date(min=today)+time → remindDate+remindAt, repeat="off" → the BE one-shot (repeat="once"); "Lặp lại" (recurring) = time+repeat. Default = recurring.
- **🔴 date is NOTE-ONLY (scope-guard):** `allowOnce` is passed to the NOTE RemindControls only; the ACTIVITY (todo) RemindControls gets the default `allowOnce=false` → no date picker → activity stays daily-recurring (the #125 contract: one-shot is note-only). Asserted by a test.
- guards: blank one-shot date → client error, no POST; past date → the BE 422 hint surfaced (honest, not silent).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** the one-shot body (remindDate set + repeat="off" → BE repeat="once"); 🔴 **the scope-guard CONFIRMED** — activity RemindControls (line 380) has NO allowOnce, note (line 449) has it → date picker is note-only (the picker is gated on `allowOnce && kind==="once"`); blank-guard + past-422; types mirror #125. FE-only stage (BE clean). ✅
- **tsc clean; vitest 89 files / 1049 passed / 0 failed** (independent; +6 incl the 🔴 activity-no-date-picker test). ✅
- **frontend-w3-2 Chrome :3010:** "Một lần" → date picker min=today; a 2026-06-28 one-shot → persisted + the date chip; toggle swap recurring↔once; default recurring; dark-mode; console clean; probe cleaned. ✅

## 3 Gates
- **Gate 2 (Function):** the 6 tests (one-shot/recurring/blank-guard/past-422/chip/activity-no-date) + tsc + vitest 1049/0 + Chrome. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step; staged EXACTLY the 3 FE files (NO backend/template leak); commit format. ✅

## Assumptions (user-review)
- **note remind one-shot = date(min=today)+time → repeat="once"; recurring = repeat; default recurring.** **How to change:** the RemindControls kind segment.
- **date picker is NOTE-ONLY** (activity stays daily). **How to change:** pass allowOnce to the todo RemindControls (NOT recommended — #125 was note-only).

## Notes
- Cairn #131 — fe-only; **= my "#125-FE" dispatch reconciled to team-lead's #131 (one ID, built once — clean dedup).** **Completes "nhắc 2 loại" END-TO-END** (#125 BE one-shot + this FE picker). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). 🔴 **The scope-guard is the load-bearing check:** the one-shot date is NOTE-ONLY (activity remind stays daily — the #125 contract) — enforced by passing `allowOnce` to the note RemindControls only, asserted by the activity-no-date-picker test. This closed the cross-feature-timing gap (#126's note-UI built before #125's remindDate landed → no picker; team-lead flagged it, I confirmed in the committed code, dispatched the fix). **Parallel-lane staging (12th clean):** FE-only (BE clean post-#129-BE). After push → team-lead Chrome-verifies the date-picker. **🔓 FE lane FREE after this → the merged /mcp-keys FE (#128+#129-FE) dispatches next** (catalog frozen at #129-BE e9b4324, REST GET /mcp_keys/catalog).
