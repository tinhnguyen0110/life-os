# end_sprint_TRACING-REMINDERS-FE — /tracing remind-toggle + /reminders source-badge (Cairn #75 FE-half)

> Result. The FE touch-points for the habit→reminder link: a "🔔 Nhắc" toggle on /tracing (set an activity's remindAt/remindRepeat → BE materializes the reminder) + a "from habit" source-badge on /reminders. Commit `<hash>` `feat(sprint-TRACING-REMINDERS-FE)` — committed TOGETHER with the #75-TWEAK BE camel-rename (so the wire is camel everywhere, no send-snake/read-camel window). Status: ✅ verified (FE agent + architect 4-step + team-lead live-integration). frontend-w3-2 BUILT; architect committed (§3). Completes #75 (BE = eef1723 + #75-TWEAK; this = FE).

## What shipped (5 FE files)
| File | Change |
|---|---|
| `app/tracing/page.tsx` | the "🔔 Nhắc" toggle on the activity add/form → when on, an HH:MM + daily/weekdays picker sets `remindAt`/`remindRepeat` (camel) on the activity create/update; off → remindAt null. Shows the current remind ("🔔 07:00 hằng ngày") on the card. RENDER-ONLY — the BE creates the reminder. |
| `app/reminders/page.tsx` | the "from habit" source-badge: `r.source === "tracing"` → a chip (title = the activity); source="manual"/absent → NO badge (honest). Defensive against a missing field. |
| `lib/types.ts` | tracing `remindAt`/`remindRepeat` (CAMEL — the tracing module's wire convention) + reminders `source`/`activity_id` (SNAKE — the reminders module's convention). Each module matches its own wire. |
| `app/tracing/__tests__` + `app/reminders/__tests__` | the toggle + badge distinguishing tests. |

## Design (LOCKED — render-only, within-module convention, honest)
- RENDER-ONLY: the FE sends remindAt on the activity; the BE materializes/syncs the reminder (the ONE-WAY wire). The FE never creates the reminder directly.
- **camel/snake per module**: tracing = camel (remindAt, matches durMin/topStreak), reminders = snake (source/activity_id, matches due_at/done_at). The convention slip (camel everywhere) was caught at 4-step + corrected: the FE had a read-camel/send-SNAKE split → realigned the SEND to camel remindAt (read was already camel). Now camel both ways for tracing.
- honest source-badge: tracing → badge, manual/absent → none (don't badge a manual reminder).

## Verification (FE agent + architect 4-step + team-lead live-integration)
- **frontend-w3-2:** vitest 900/0/0 (snake-clean for reminders + camel-clean for tracing post-realign), tsc clean, Chrome (toggle + badge render).
- **architect 4-step (read full files):** types.ts camel-tracing + snake-reminders (each module correct, documented) ✅; send-side realigned to camel remindAt (was snake — the split fixed) ✅; source-badge tracing-only + honest-no-manual-badge ✅; vitest tracing+reminders 32/0; tsc clean ✅; committed WITH #75-TWEAK so the wire is camel end-to-end (no mismatch window).
- **team-lead live-integration (the decisive proof):** all 5 cases PASS on the running container — create activity remindAt=09:00 daily → reminder source=tracing + activity_id, due 09:00VN=02:00UTC (TZ), repeat=daily (the wire FIRES); manual → source=manual; forge-guard (manual POST source=tracing → stays manual); ONE-WAY cascade (archive activity → its tracing-reminder GONE, manual+forge SURVIVE); camel wire (GET /tracing serializes remindAt). The integration is SOUND.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest 900/0/0 + tsc clean + Chrome toggle/badge + the live integration (team-lead, 5 cases). ✅
- **Gate 3 (Sprint):** end-doc; FE-agent + architect 4-step + team-lead live; commit-hygiene (FE-only joint with #75-TWEAK BE — content-diffed, the FE files separate from the BE tracing files); commit format. ✅

## Assumptions (user-review)
- /tracing "🔔 Nhắc" toggle sets remindAt/remindRepeat (camel) on the activity → BE materializes the reminder (one-way). /reminders shows a "from habit" badge for source=tracing. tracing=camel, reminders=snake (within-module convention). **How to change:** the toggle / the badge.

## Notes
- #75 FE-half. frontend-w3-2 BUILT; architect committed (§3) TOGETHER with #75-TWEAK (the BE camel-rename) so the wire is camel end-to-end. The convention slip (read-camel/send-snake) was caught at 4-step + corrected. **#75 module DONE** = the habit-nudge loop (set a habit → get a daily reminder, with the source-badge + the one-way cascade). team-lead does a light FE Chrome confirm + closes the #75 integration milestone. NOTE: a USER-raised nav-IA decision (group Dev Activity/projects/graveyard) is HELD pending the user — separate from #75. Next: #73 → #64.
