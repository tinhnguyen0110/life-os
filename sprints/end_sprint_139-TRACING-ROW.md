# end_sprint_139-TRACING-ROW — activity must have a time + full row content (FE-only)

> Sprint 139 (FE-only). 3 user specs after #136/#137: (1) "hoạt động phải có giờ" — every activity must have a time; (2) "CẢ NGÀY để làm gì" — remove the no-time bucket; (3) "tickbox tên nhắc nhở số lần chanel" — the row shows tickbox · name · reminder(freq+channel). Built on the pushed #137 (24d1cec). No BE (the #136 `time` field + validators exist).

## What shipped (app/tracing/page.tsx + tokens.css + tests)
1. **Add-form TIME input** — `ADD_TIME_DEFAULT = "08:00"` const + `todoTime` state + an `<input type="time" data-testid="todo-time">` in the add form (default 08:00, user-editable before adding); `onAddTodo` sends `time: todoTime || null`; reset to default after add. → every NEW activity is timed (no bare "–").
2. **"CẢ NGÀY" group REMOVED** — dropped the `timeline-anytime-sep` "CẢ NGÀY" header + the conditional wrapper; timed rows render first (ascending, `timelineOrder` untouched), then any legacy timeless rows at the END with NO separate header.
3. **Legacy null-time rows show a PROMINENT "⏰ Đặt giờ" pill** (the team-lead-nuance addendum) — the time cell branches: `railTime(a)` → the real time (clickable "Đổi giờ"); else → a `.tl-settime-pill` "⏰ Đặt giờ" button (accent-tinted, NOT a bare "—") that opens the same per-card time editor. Grid col widened 54→66px. **No auto-backfill** — the pill opens the editor; we never write a guessed time to the user's data (honest-mirror).
4. **Row = tickbox · name · reminder(freq+channel)** — already done (#136-G2 RemindChip: `🔔 {at} · {freqLabel} · {channel}`). Confirmed live. "số lần" = the freq label (hằng ngày/ngày thường), NOT a literal per-day count — the chip covers it (no flag needed).

## Verify (architect 4-step + live Chrome)
- **Read full functions:** add-time default + send + reset; CẢ NGÀY header + wrapper removed; the legacy "⏰ Đặt giờ" pill branch; the tokens.css pill style. All correct; the addendum implemented honestly (no backfill). #139 is cleanly on top of the pushed 24d1cec (HEAD==origin), no #137 residue.
- **Live Chrome (architect, :3010):** add-form has the 08:00 time input ✓; the 6 legacy rows (Tập thể dục, Đọc sách, Ngủ đủ giấc, Thiền, Đi bộ, Học) all show the "⏰ Đặt giờ" pill — NO bare "–" ✓; "Viết nhật ký" shows its real 07:00 ✓; NO "CẢ NGÀY" text anywhere in the page ✓; the row shows tickbox · name · RemindChip ✓. console clean.
- **vitest 1095/0err** (baseline 1090 → +5; tracing.test 39: rewrote the stale CẢ NGÀY test → asserts the header is GONE + ordering preserved; added add-form-time-default test + the legacy-pill test). tsc clean.

## Gates
- Gate 2 (Function): unit tests assert behavior (add-form sends a time; no CẢ NGÀY header; legacy row renders the "Đặt giờ" pill not "–"; ordering preserved), tsc clean, Chrome self-verify done (frontend + architect). ✓
- Gate 3 (Sprint): this doc + spot-checked full functions + live Chrome + count ≥ baseline (1090 → 1095). ✓

## Assumptions (user-review)
- **New activities default to 08:00** (add-form, user-editable before adding) — a fixed sensible default, NOT a hard-required 422 (which would block quick-add + break the template's bare "Đọc sách" member). How to change: a different default or a "now-rounded" default in ADD_TIME_DEFAULT.
- **Legacy null-time rows show a "⏰ Đặt giờ" PROMPT, not an auto-assigned time** — honest-mirror: we never write a guessed time onto the user's real activities (their run might be 06:00). The auto-backfill option (default all 6 to 08:00) was surfaced to the user via team-lead (notify.py); a cheap follow-up if they want it.
- **"số lần" = the reminder freq** (hằng ngày/ngày thường = remindRepeat), already on the RemindChip — NOT a literal per-day count. How to change: the deferred N-per-day reminders-engine model if the user wants a literal count.

## Commit
- Hash: (filled at commit) — `feat(sprint-139-tracing-row): activity must have a time (add-form default + Đặt giờ pill) + remove CẢ NGÀY group`
- Files: frontend/app/tracing/page.tsx + frontend/lib/tokens.css + frontend/app/tracing/__tests__/tracing.test.tsx + this doc.
- FE-only — on top of #137 (24d1cec). 🔴 Push gated on team-lead's Chrome verify (the #136 standing rule — UI affordance).
