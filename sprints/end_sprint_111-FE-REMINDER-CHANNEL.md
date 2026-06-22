# end_sprint_111-FE-REMINDER-CHANNEL — reminder channel <select> (FE half) (Cairn #111, TRACING-UX T3)

> Result. The #111-BE (2378e56) added a reminder `channel` (in_app/email/discord) routed via the #33 alerts engine, but the tracing add-form had no way to PICK it. Added a Kênh `<select>` in the 🔔 reminder block — only shown when the toggle is on, only-available options enabled (unavailable → disabled + "(chưa cấu hình)"), sends `remindChannel` (camel) in the create body. Commit `<hash>` `feat(sprint-111-fe-reminder-channel): channel <select> in tracing reminder block (#111 FE)`. Status: ✅ verified (frontend-w3-2 built + Chrome live; architect 4-step + tsc + vitest 1022/0 + INDEPENDENT live BE-echo reproduction). Cairn #111 TRACING-UX T3 — FE half **COMPLETES #111** (be+fe). user-CHỐT.

## What shipped (FE — 4 files)
| File | Change |
|---|---|
| `app/tracing/page.tsx` | Kênh `<select>` in the 🔔 block (line 323 `{adding.remindOn && (` … select at 349 … `</>` 358 — HIDDEN until toggle on). Fetches GET /reminders/channels once (`useEffect`, `alive` unmount-guard); only-available enabled, unavailable → `disabled` + "(chưa cấu hình)". Sends `remindChannel: adding.remindOn ? adding.remindChannel : undefined` (only when toggle on). 🔴 render-safe: channels API error/empty → fallback `IN_APP_ONLY` (form never blocks). `EMPTY_ADD` default `remindChannel:"in_app"`. |
| `lib/types.ts` | `RemindChannel` (= BE Literal), `ReminderChannelOption {id,label,available}`, `ReminderChannelList {channels[]}`, `ActivityInput.remindChannel?`. |
| `lib/api.ts` | `getReminderChannels()` → GET /reminders/channels (apiGet pattern). |
| `app/tracing/__tests__/tracing.test.tsx` (+6) | hidden-until-toggle · all-available-enabled · unavailable-disabled+"chưa cấu hình" · pick-discord→`createActivity.calls[0][0].remindChannel==="discord"` · toggle-off→undefined · API-error→fallback in_app-only (form not blocked). |

## Design (LOCKED — toggle-gated select, only-available-enabled, render-safe fallback, camel-wire)
- **select is GATED on the 🔔 toggle:** rendered inside `{adding.remindOn && (...)}` — hidden until the user enables the reminder (a channel only matters when there IS a reminder). Confirmed by read (323→358) + the hidden-until-toggle test.
- **only-available enabled:** options map `disabled={!c.available}` + "(chưa cấu hình)" tag; in_app always available. Reuses the BE `available` flag (one source — /reminders/channels == /alerts/config detection, #111-BE nuance 2).
- **🔴 render-safe fallback:** channels fetch error/empty → `IN_APP_ONLY` (the form is NEVER blocked by a channels-API failure). The `alive` guard prevents a set-state-after-unmount race.
- **camel-wire, toggle-scoped send:** `remindChannel` sent (camel, like remindAt) ONLY when toggle on; toggle off → `undefined` (omitted → BE default in_app). Matches the #75 one-way tracing→reminder link.

## Verification (Gate-2 FE — architect INDEPENDENT)
- **architect 4-step (read FULL):** select nesting confirmed inside the remindOn block (line 323→358, NOT always-rendered); useEffect alive-guard + fallback; submit sends channel only-when-on; types match the BE shape; FE-only stage (no template/backend/data, no #112). ✅
- **tsc** clean (exit 0) · **vitest 88 files / 1022 passed / 0 failed / 0 errors** (independent re-run; was 1016 → +6; "Unhandled Errors Not Green" tail clean). ✅
- **frontend-w3-2 Chrome :3010:** select hidden until toggle; 🔔 on → In-app/Email/Discord all enabled; pick discord + submit → linked reminder `channel:"discord"` (API-confirmed); dark-mode; console clean; cleanup scoped. ✅
- **🔴 architect INDEPENDENT live BE-echo reproduction (Rule#0 — disproved the FYI):** frontend-w3-2 flagged "activity stored remindChannel echoes in_app not discord (possible BE follow-up)". Reproduced on the live container with a VALID payload (goal numeric): create `{remindChannel:"discord"}` → **activity.remindChannel = `discord`** (the response schema HAS remindChannel + echoes it) AND **linked reminder.channel = `discord`**. The FYI was a false alarm (frontend-w3-2's probe likely hit a validation issue — goal must be numeric). **NO #111-BE follow-up needed** — the BE stores AND echoes the chosen channel correctly. Scoped-cleaned the probe (#72: deleted only `arch-echo-probe3`, store back to baseline). ✅

## 3 Gates
- **Gate 2 (Function):** the 6 behavior tests (hidden-until-toggle/enabled/disabled/pick-discord-payload/toggle-off-undefined/api-error-fallback) + tsc + vitest 1022/0 + Chrome live discord-fires + the independent BE-echo reproduction. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step + tsc/vitest + independent live; staged EXACTLY the 4 FE files (NO template/backend/data, no #112); commit format. ✅

## Assumptions (user-review)
- **channel select is gated on the reminder toggle** (only shown when 🔔 on). **How to change:** the `{adding.remindOn && ...}` wrapper in page.tsx.
- **channels-API failure → fallback to in_app-only** (form never blocks). **How to change:** the `IN_APP_ONLY` fallback / the useEffect catch.
- **the FYI "activity echoes in_app not discord" was DISPROVED** (BE echoes discord correctly with a valid payload) → no BE change. **How to change:** n/a (the BE is correct).

## Notes
- Cairn #111 TRACING-UX T3 FE half — **COMPLETES #111** (be 2378e56 + this fe). user-CHỐT (reminder channel select). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). Layered on the committed #111-BE + #110 lean-form (page.tsx one-file serialization — #110 committed 2bf61ff before #111-FE started, no tangle). 🔴 **The Rule#0 win:** frontend-w3-2's honest FYI (activity echoes in_app) was VERIFIED not trusted — reproduced on the live container, found it was a false alarm (a malformed probe payload, not a BE bug; the BE echoes the chosen channel correctly). This is exactly why a flagged discrepancy gets reproduced, not accepted or dismissed. After #111-FE commits → #111 fully closes (be+fe). frontend-w3-2 next = #114 (FE for PROJECTS-UNIFY, dep-blocked on #112✓+#113 — a real dep-wait).
