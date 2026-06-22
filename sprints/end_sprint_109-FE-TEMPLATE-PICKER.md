# end_sprint_109-FE-TEMPLATE-PICKER — tracing template picker UI (Cairn #109 FE half, TRACING-UX T1)

> Result. #109-BE (2b7a200) shipped the template endpoints but BE-only — the user-facing "tick-template→prefill" was unbuilt. This is the #109 FE half: a template picker above the "Hoạt động mới" form (tick a preset → prefills the add form) + a light manage UI (edit/add/delete/reset/bulk) against the live #109-BE. Commit `<hash>` `feat(sprint-109-fe-template-picker): tracing template picker → prefill add form (#109 FE)`. Status: ✅ verified (frontend-w3-2 built + Chrome live; architect 4-step + tsc + vitest). Cairn #109 FE half — CLOSES #109 (BE 2b7a200 + this FE). user-CHỐT. GATES #110 (now unblocked).

## What shipped (FE — picker + api + types)
| File | Change |
|---|---|
| `components/TracingTemplatePicker.tsx` (NEW) | the picker: chip row (GET /tracing/templates on open) + tick→`onPick` prefill + light manage UI (edit PUT / add-new / delete DELETE / "Reset về mặc định" POST / bulk-select→bulk-delete) — ALL in-page confirms (NOT window.confirm — the Chrome-MCP-blocking dialog); status state-machine (loading/error/ready); render-safe (API error → honest note, the add form still works). source-tagged (seed vs user). |
| `components/__tests__/TracingTemplatePicker.test.tsx` (NEW, 9) | picker renders templates + tick→onPick prefill; manage edit/delete/reset/bulk; render-safe error. |
| `app/tracing/page.tsx` | picker ABOVE the "Hoạt động mới" form; `onPick(t) → setAdding(prev => ({...(prev??EMPTY_ADD), id,name,goal,unit,emoji,color}))` — prefills the activity fields while KEEPING the #75 reminder-toggle state (spreads prev). Form NOT restructured (that's #110). |
| `lib/api.ts` | getTracingTemplates / upsertTracingTemplate / deleteTracingTemplate / resetTracingTemplates / bulkDeleteTracingTemplates (against the frozen #109-BE endpoints). |
| `lib/types.ts` | TracingTemplate {id,name,goal,unit,emoji,color,source} / TracingTemplateList / TracingTemplateInput — mirrors the frozen #109-BE shape. |
| `lib/tokens.css` | `.tpl-*` chip styles. |

## Design (LOCKED — picker-prefills-existing-form, in-page-confirm, render-safe, keeps-reminder)
- **picker prefills, doesn't replace:** tick a template → `onPick` fills the EXISTING `adding` state (the form the user then tweaks + submits via the existing onAdd). Templates are prefill-only (don't create activities — the BE confirmed). The form + its #75 reminder toggle are untouched by the prefill (spread `prev` → only activity fields set, reminder state preserved).
- **in-page confirm (NOT window.confirm):** reset + bulk-delete use in-page confirm state (confirmReset/confirmBulk) — a JS dialog blocks the Chrome MCP (the browser-automation note); also nicer UX.
- **render-safe:** the picker's error never blocks the add form (status state-machine; Array.isArray validation; try/catch + ApiError on every action; honest empty/error note). The form works even if templates fail to load.
- **source-tagged:** seed vs user visually distinct (light) so the user sees which are their overrides.
- **NOT the form-gọn restructure:** that's #110 (the next FE commit, on top of this picker-enabled form).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** onPick spreads prev (keeps reminder state) + sets activity fields; the picker's in-page confirm (no window.confirm); render-safe state-machine + try/catch; FE-only (no #111/#112 BE leak in the staged tree). ✅
- **architect tsc + vitest gate:** `npx tsc --noEmit` clean (exit 0); `npx vitest run` = **1007 passed** (was 998 → +9 picker), 0 failed. ✅
- **frontend-w3-2 Chrome (the load-bearing user-facing flow):** /tracing → picker shows 8 seed chips → tick "Uống nước" → form prefills (id=uong-nuoc/name/goal=8/unit=ly/💧/color) → changed id→__109probe → submit → activity created LIVE (API-confirmed); manage edit/new/bulk + reset=in-page-confirm (window.confirm spy NOT called); dark-mode; console clean; cleanup scoped (probe archived, templates back to 8 seed). ✅ (first-load dev-compile race noted — warm load fine, not a bug.)

## 3 Gates
- **Gate 2 (Function):** the picker tests (render/prefill/manage/render-safe) + tsc + vitest 1007/0 + the Chrome live prefill→create + in-page-confirm (no JS dialog). ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step + tsc/vitest; staged the 6 FE files (NO #111/#112 BE, no data/.env); commit format. ✅

## Assumptions (user-review)
- **picker prefills the existing form** (tick → fill → tweak → submit); templates don't auto-create. **How to change:** add a "create directly from template" shortcut if the user wants one-click.
- **in-page confirm for reset/bulk** (not a JS dialog). **How to change:** the confirm UI in the picker.
- **prefill keeps the reminder toggle** (only activity fields set). **How to change:** the onPick spread in page.tsx.

## Notes
- Cairn #109 FE half — **CLOSES #109** (BE 2b7a200 + this FE picker). The user-facing "tick-template→prefill" is now live (the value the BE-only commit didn't show — the Rule#0 catch that #109 landed BE-only). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). Built in the sensible order (api+types first → picker component) — which briefly looked like "page.tsx idle" but was mid-build (cleared with the full-tree disk check). Committed FE-only from an intermixed tree (#111/#112 BE in flight) — surgical FE stage, no leak. GATES #110 → frontend-w3-2 starts the form-gọn restructure on this picker-enabled form NOW. The combined-sequential FE dispatch (109-FE then #110, one agent/one file) avoids two agents fighting page.tsx.
