# end_sprint_136-FE — Daily Tracing todo-column redesign (the FE half of #136)

> Parent #136 TRACING-TODO-REDESIGN (FE-only per the kickoff — the BE rename/remind fields already existed; un-tick [146f2ed] + the `time` field [fdc23b9] are the two small BE adds the FE surfaced). This is the todo-column UX redesign in `app/tracing/page.tsx`. User flagged the left todo column; team-lead Chrome-verified each finding live.

## What shipped (all in app/tracing/page.tsx + lib/*)
1. **Timeline = default display** (the #126 read view, ungated; edit is per-card now).
2. **Per-CARD edit, NO global "Sửa" toggle** — removed the #126 global edit-mode; each row has its own ⋯ (rename inline / set reminder / set time / delete).
3. **Inline title edit** (the missing CRUD-U) → PUT /tracing/activities/{id} {name}.
4. **Template "+ Từ mẫu" visible in the default view** (not behind a toggle).
5. **Reminder per todo: time + frequency + channel** — the full RemindControls (reuse from #131 notes) replaces the bare 🔔; PUT {remindAt, remindRepeat, remindChannel}. RemindChip now shows the channel on its face (GAP-2).
6. **Tick = TOGGLE** — the headline fix: tick an undone row → done (log val=1); tick a DONE row → un-complete (DELETE /tracing/{id}/sessions → done=false). Removed the old `if (a.today.done) return; // no un-tick` + the `disabled={...|| a.today.done}` that LOCKED a done row. 1-click in the read/timeline view (not gated by edit).
7. **G3 dedicated time** — `railTime(a) = a.time || a.remindAt || null`; the timeline rails + sorts by railTime; per-card "Đặt giờ" → edit(id,{time}) (empty clears). A time WITH NO reminder shows on the rail and nothing fires (the G3-(ii) independence).

## lib changes
- `types.ts`: `time?:string|null` on ActivityView/ActivityInput/ActivityPatch; + `remindChannel?` on ActivityView/ActivityPatch (gap-fill — the BE carried it since #111/#117 but the FE type hadn't declared it on the view/patch).
- `api.ts`: `untickActivity(id)` → DELETE /tracing/{id}/sessions → {activityId,date,deletedSessions}.
- `useTracing.ts`: `untick(id)` callback (untickActivity → reload; fail-closed) + added to the UseTracing interface.

## Verify (architect 4-step + live)
- **Live (architect, on the container):** un-tick toggle BOTH ways — log val=1 → today.done=true, val=1, pct=100, sessions=1, streak=1; DELETE /sessions → today.done=false, val=0, sessions=0, streak=0 ✓ (the headline). G3 time on the rail, time-with-no-reminder independence ✓. (`done` lives at `today.done` = val>=goal, the #122 binary-todo contract.)
- **frontend Chrome (reported):** ⋯ → Đặt giờ → 07:15 (no reminder) → saved → rail shows 07:15, BE persisted {time:"07:15", remindAt:null} ✓; cleaned up after.
- **vitest:** 1074 passed (89 files), 0 errors — tracing 36 tests incl. +3 G3 (dedicated-time-on-rail+sort, ⋯-set-time→PUT, clear-time→{null}) + the un-tick tests. tsc clean (frontend reported).

## Gates
- Gate 2 (Function): unit tests assert behavior (tick-toggle, time-on-rail, set/clear time), edge (empty time clears; done-row un-ticks), tsc clean, Chrome self-verify done (frontend). ✓
- Gate 3 (Sprint): this doc + spot-checked full functions (page.tsx behavior hunks read) + tester counts ≥ baseline (1074). ✓

## Assumptions (user-review)
- **Tick = toggle (un-complete):** ticking a DONE todo again UN-completes it (clears today's log). Why: the user's "tick rồi không hoàn được" complaint = a checkbox you can't un-check; a binary todo should toggle both ways. How to change: if the user wants append-only (no un-tick), revert to the old `if (done) return`.
- **G3 time independent of remind** (the BE Assumption, surfaced FE-side): a scheduled time can exist with no reminder — the rail shows it, nothing nudges.

## Commit
- Hash: (filled at commit) — `feat(sprint-136-fe): tracing todo-column redesign (per-card edit, tick-toggle, dedicated time)`
- Files: frontend/app/tracing/page.tsx + frontend/app/tracing/__tests__/tracing.test.tsx + frontend/lib/{api,types,useTracing}.ts + frontend/lib/tokens.css + this doc.
