# end_sprint_126-TRACING-TIMELINE — /daily-tracing timeline redesign (Cairn #126, TRACING-UX2 T5)

> Result. The /daily-tracing VIEW redesigned to the user's mock: DEFAULT = a vertical TIMELINE read-view (giờ·dot·tick·việc·chi tiết, timed-first + "Cả ngày" bucket) + an EDIT-mode toggle (read=clean+1-click-tick; edit=add/remind/archive/"+Từ mẫu") + NOTE as a multi-list. Base KEPT (todo=goal=1/tick=log/note→#121); only the VIEW changed. Commit `<hash>` `feat(sprint-126-tracing-timeline)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + tsc + vitest 1043/0). Cairn #126 TRACING-UX2 T5 — fe-only, CLOSES on this commit. Disjoint from #125/#129-BE (BE, parallel).

## What shipped (FE — page.tsx rewrite + api + tests)
| File | Change |
|---|---|
| `app/tracing/page.tsx` (REWRITTEN view) | DEFAULT = timeline read-view (`timelineOrder`: TIMED by remindAt asc, then un-timed under "CẢ NGÀY"; rows = giờ·dot·tick·việc·chi tiết). 🔴 read-only + **1-click tick (NOT gated behind edit)**. EDIT-mode toggle ("Sửa"/"Xong") → reveals add-via-text + remind + archive + "+ Từ mẫu" (#124 add-one/all). NOTE = MULTI-LIST (multiple cards, add-multiple, per-note remind+delete). |
| `lib/api.ts` | getTracingTemplates / addTemplateToToday / addAllTemplates (#124 endpoints). |
| `app/tracing/__tests__/tracing.test.tsx` (+3 net; replaced #122 view-tests in-place → 1043) | default-timeline-read (add-tools hidden until Sửa), 🔴 tick-in-read-mode (no edit needed), timeline-order, done-line-through, archive-only-in-edit, "+ Từ mẫu" add-one/all/error, multi-list notes (multiple cards + add-multiple + remind + delete), honest-empty + error-paths-don't-break. |

## Design (LOCKED — timeline VIEW, edit-mode, tick-in-read, multi-list, base kept)
- **DEFAULT = timeline read-view** (the user's mock): a vertical time-rail, timed activities first (by remindAt), un-timed under "Cả ngày". Clean read surface.
- **🔴 EDIT-mode toggle, tick stays 1-click in READ:** read-only = view + 1-click tick (ticking is the core daily action, NOT gated behind edit — the load-bearing UX, tested). "Sửa" → edit-mode reveals add/remind/archive/"+ Từ mẫu".
- **NOTE = multi-list** (not the #122 single textarea): multiple cards + add-multiple + per-note remind/delete.
- **base UNCHANGED:** todo=activity goal=1, tick=log val=1→done, note→#121 /tracing/notes, #111 channels. Only the VIEW changed (no BE).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** timelineOrder (timed-first + CẢ NGÀY); editMode toggle; 🔴 the tick-in-read test ("ticking an undone todo in read-mode → log(id,{val:1}); no edit needed") — the load-bearing UX confirmed; multi-list notes; "+ Từ mẫu" wires the #124 endpoints. FE-only stage (read_server #129-BE left dirty — disjoint parallel). ✅
- **tsc clean; vitest 89 files / 1043 passed / 0 failed** (independent; +3 net, replaced #122 view-tests in-place). ✅
- **frontend-w3-2 Chrome :3010:** default timeline read-view; tick 1-click in read; "Sửa"→edit reveals add-tools; multi-list notes (add-multiple/remind/delete); "+ Từ mẫu" 8 templates add-one/all → goal=1 tickable (the #124 contract); inverted mock-diff (base kept); dark-mode; console clean. ✅

## 3 Gates
- **Gate 2 (Function):** the timeline/edit-mode/tick-in-read/multi-list/"+Từ mẫu" tests + tsc + vitest 1043/0 + Chrome. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step; count is +3 (replaced #122 view-tests in-place, not a drop — the surviving behaviors re-covered); staged EXACTLY the 3 FE files (NO #129-BE read_server / template leak); commit format. ✅

## Assumptions (user-review)
- **DEFAULT = timeline read-view; tick 1-click in read** (not gated behind edit). **How to change:** the editMode gate in page.tsx (but tick stays ungated — it's the core action).
- **NOTE = multi-list** (vs #122 single textarea). **How to change:** the note render.
- **timeline order = timed-by-remindAt then "Cả ngày"** for un-timed. **How to change:** timelineOrder.

## Notes
- Cairn #126 TRACING-UX2 T5 — **completes the TRACING-UX2 FE redesign** (the timeline view over the #121/#124/#125 BE). user-CHỐT (the mock). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). The tick-1-click-in-read is the load-bearing UX (ticking is the daily action — read-only must allow it; verified by test + Chrome). **2 findings TRIAGED by team-lead (Rule#0):** (1) "GET /tracing 28s" — NOT a BE bug (team-lead curl'd 6ms; the 28s was transient build-storm load or the FE Tailscale path — investigate only if it recurs on a quiet container); (2) template-add on an ARCHIVED activity → added:false + invisible (no un-archive) — a real small UX gap, logged low-pri, not blocking. (7 lingering template-probe activities = test residue, left + surfaced, no auto-purge — the user decides.) **Parallel-lane staging (10th clean):** committed FE-only while #129-BE (read_server) is in flight — disjoint, leak-check clean. After push → team-lead Chrome-verifies. The merged /mcp-keys FE pass (#128+#129-FE) is next on the FE lane (after #129-BE freezes). No BE change, no restart.
