# end_sprint_137-T2-template-modal — the template-SET MODAL (FE half of #137)

> Sprint 137 Task T2 (FE). The user rejected the 1-word CHIP "mẫu" model. A "mẫu" = a saved LIST of rich activities (a routine), edited/imported/reset in an in-page MODAL. FE-only, mirrors the FROZEN #137-T1 BE shape (8e4fd22, live on origin). Built on top of #137-T1.

## What shipped (FE-only)
- **lib/types.ts:** TemplateSet `{id,name,activities:TemplateMember[]}` + TemplateMember `{content,time,remindRepeat,remindChannel}` + TemplateSetList + TemplateSetInput + TemplateImportResult — mirrored the frozen BE shape (verified live first).
- **lib/api.ts:** the 6 fns — getTemplateSets / createTemplateSet / updateTemplateSet / deleteTemplateSet / importTemplateSet / resetTemplateSets (correct endpoints, encodeURIComponent).
- **app/tracing/TemplateSetsModal.tsx (NEW):** in-page modal (role=dialog aria-modal, NO window.*) — LIST view (each set: name + count + a RICH preview "07:00 Uống nước · 07:30 Tập thể dục · …" + Import/Sửa/Xóa), CREATE/EDIT view (rename + member list, each = content + time(HH:MM) + reminder on/off + freq(daily/weekdays) + channel + add/remove member → PUT/POST), reset-to-default. 422 → hint.
- **app/tracing/page.tsx:** "+ Từ mẫu" now opens the MODAL (was the chip row). REMOVED the old #124 chip-picker block + its state/handlers + the getTracingTemplates/addTemplateToToday/addAllTemplates imports; a toast "Đã thêm N việc" after import + reload.

## Verify (architect 4-step + live Chrome)
- **Read full functions:** the chip-picker→modal swap is clean (ONLY the chip ROW removed; the chip API fns kept in lib/api.ts for parity; the standalone TracingTemplatePicker component + tests untouched/dormant). The modal has no window.* dialogs (Chrome-MCP-safe). All 6 api fns wired to the frozen endpoints.
- **Live Chrome (architect, :3010):** "+ Từ mẫu" → modal opens; the default "Buổi sáng · 3 việc" shows the RICH preview "07:00 Uống nước · 07:30 Tập thể dục · 08:00 Đọc sách" (a rich LIST, NOT 1-word chips — the rejected model is gone); Import/Sửa/✕/+ Tạo mẫu/Khôi phục mặc định all present; the old chip row is gone. (The import→goal=1+presets round-trip is verified at the BE layer in #137-T1 [my live round-trip] + frontend's FE Chrome verify + the vitest import test; not re-imported here to avoid polluting the live store.)
- **vitest 1086/0err** (+13 TemplateSetsModal tests; TracingTemplatePicker 9 still green; tracing 36→35 = the 2 chip tests → 1 modal-open+chip-gone, net -1 deliberate swap). tsc clean.
- **mock-diff:** chip ROW removed from the tracing UI · modal added · chip API fns KEPT · #121-136 tracing features intact.

## Gates
- Gate 2 (Function): unit tests assert behavior (list/empty/error, import→onImported(count,skipped), delete+reload, reset, create-2-member-set body shape, edit-rename, remove-member, blank-name guard, 422-hint), tsc clean, Chrome self-verify done (frontend + architect). ✓
- Gate 3 (Sprint): this doc + spot-checked full functions + live Chrome + count ≥ baseline (1074 → 1086). ✓

## Assumptions (user-review)
- **The 1-word chip ROW is removed from the tracing UI; the chip API stays dormant** (REST GET /tracing/templates + MCP `tracing_templates` parity + count-asserts read it). The standalone TracingTemplatePicker component is left in place (not rendered on the tracing page). How to change: a deliberate parity-aware removal if the chip surface is ever fully retired.
- **import toast** = "Đã thêm N việc · M đã có sẵn" (N=created.length, M=skipped.length). A simple confirmation; the board refetches.

## UX fix (folded in before push — team-lead's Chrome gate caught 2 user-flagged gaps)
team-lead's pre-push Chrome gate (the #136 standing rule) caught 2 user UX gaps in the first commit (40573e3, held, never pushed): (1) click OUTSIDE the modal didn't close it (only "Đóng"); (2) a daily-task edit required re-clicking the EXACT same icon to close. Fix (amended into the unpushed commit, one clean #137-T2 commit):
- **lib/useClickAway.ts (NEW):** `active`-gated hook — `mousedown` (fires before a re-render swallows the target) + `setTimeout(0)` defer-attach (so the OPENING click doesn't self-close) + a `cb` ref (latest callback, no re-subscribe) + cleanup. No global cost when closed.
- **TemplateSetsModal.tsx:** backdrop onMouseDown closes + box stopPropagation + Escape; the EDIT view stays open on a backdrop click (an in-progress edit isn't lost — good nuance).
- **page.tsx:** useClickAway wired to BOTH the modal AND every per-card affordance — TimelineRow (⋯ menu + time editor + reminder editor) + NoteCard (⋯ menu + reminder editor). So an outside click closes them all (not just the modal — the full scope of the user's gap #2).
- Verify: team-lead's live Chrome — modal backdrop→closes; Tập thể dục ⋯ → click outside → closes (no re-click); console clean. My 4-step: read the full hook + wiring (scope covered), vitest 1090/0err (+4 click-away), tsc clean.

## Commit
- Hash: (filled at commit) — `feat(sprint-137-t2-template-modal): the template-SET modal (list/edit/import/reset, chip row removed) + click-away UX`
- Files: frontend/app/tracing/page.tsx + frontend/app/tracing/TemplateSetsModal.tsx (NEW) + frontend/lib/useClickAway.ts (NEW) + frontend/app/tracing/__tests__/{tracing.test.tsx, TemplateSetsModal.test.tsx (NEW)} + frontend/lib/api.ts + frontend/lib/types.ts + this doc.
- FE-only — after #137-T1 (8e4fd22, landed). Push gated on team-lead's Chrome verify (the #136 standing rule) — GATE LIFTED (both UX gaps verified) → pushed.
