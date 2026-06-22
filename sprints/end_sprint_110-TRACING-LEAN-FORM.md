# end_sprint_110-TRACING-LEAN-FORM — lean add-form (3 default + advanced disclosure + auto-slug) (Cairn #110, TRACING-UX T2)

> Result. The "Hoạt động mới" form was 6 manual fields → friction. Restructured on top of the #109 picker (ab42da5): minimal DEFAULT = Tên + Mục tiêu + Đơn vị; id/emoji/màu moved to a collapsed "Nâng cao" disclosure; the id AUTO-SLUGS from the name (so the user never types an id). Commit `<hash>` `fix(sprint-110-tracing-lean-form): lean add-form + advanced disclosure + auto-slug id (#110)`. Status: ✅ verified (frontend-w3-2 built + Chrome live; architect 4-step + tsc + vitest). Cairn #110 TRACING-UX T2 — COMPLETES the TRACING-UX FE (#109-FE + #110). user-CHỐT.

## What shipped (FE — page.tsx restructure + slugifyVi)
| File | Change |
|---|---|
| `app/tracing/page.tsx` | lean form: **Tên + Mục tiêu + Đơn vị** visible by default; **id + emoji + màu** in a collapsed **"Nâng cao" disclosure**. id auto-slugs from the name (faint `id: …` preview), editable in Advanced (an `idManual` flag stops the auto-slug once the user overrides it). The #109 picker prefills name/goal/unit AND the advanced fields (sets idManual:true on a pick so the template's id sticks). |
| `lib/format.ts` | `slugifyVi(name)` — NFD diacritic-strip + đ→d + lowercase + non-alnum→hyphen + collapse/trim. Produces a sensible kebab id (e.g. "Tập thể dục"→"tap-the-duc"). |
| `lib/__tests__/format.test.ts` (+4) | slugifyVi against the real seed ids (Uống nước→uong-nuoc, Đọc sách→doc-sach, …). |
| `app/tracing/__tests__/tracing.test.tsx` (+5, 3 updated) | lean-form (3 default fields) + Nâng cao disclosure toggle + auto-slug; the 3 existing tests that typed `a-id` updated to rely on auto-slug (a-id now in the collapsed Advanced). |

## Design (LOCKED — lean-default, advanced-disclosure, auto-slug, picker-prefills-all)
- **lean by default:** only the 3 essentials (Tên/Mục tiêu/Đơn vị) show; the power-user fields (id/emoji/màu) are one "Nâng cao" click away. Cuts the per-habit friction the user flagged.
- **auto-slug id (the user never types an id):** `slugifyVi(name)` derives a kebab id live (preview shown); `idManual` flag = once the user edits the id in Advanced (or a template-pick sets it), the auto-slug stops overwriting. 🔴 **BE accepts the FE id VERBATIM** (create_activity uses `id=inp.id`, does NOT re-slug) → slugifyVi just needs to be a valid+consistent FE id, no BE-match required; it conveniently matches the seed ids so a seed-named habit reuses the seed id (the override model wants that).
- **picker integration preserved:** the #109 picker (committed ab42da5) prefills name/goal/unit + the advanced id/emoji/color (idManual:true so the template id sticks). The lean restructure layered ON the committed picker (one-file serialization: #109-FE committed before #110 started).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** slugifyVi (NFD+đ+kebab) matches the seed ids; the BE takes the FE id verbatim (create_activity id=inp.id — no re-slug, no mismatch); idManual stops auto-slug on override/pick; FE-only (no #111 `remindChannel`/BE leak in the staged set). ✅
- **architect tsc + vitest gate:** tsc clean (exit 0); vitest **1016 passed** (was 1007 → +5 tracing +4 slug), 0 failed. ✅
- **frontend-w3-2 Chrome (the lean-form live):** default form = ONLY Tên/Mục tiêu/Đơn vị (id/emoji/màu hidden); type "Tập thể dục"→id preview "tap-the-duc"; expand Nâng cao→id/emoji/màu appear with the auto-slug; tick template "Uống nước"→prefills name/goal/unit + advanced id=uong-nuoc/💧/color; lean submit→create LIVE (API-confirmed); dark-mode; console clean; cleanup scoped. ✅

## 3 Gates
- **Gate 2 (Function):** the lean-form/disclosure/auto-slug tests + slugifyVi-matches-seed-ids + tsc + vitest 1016/0 + the Chrome live lean-create + picker-prefills-advanced. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step + tsc/vitest; staged EXACTLY the 4 #110 FE files (NO #111 remindChannel/BE, no data/.env); commit format. ✅

## Assumptions (user-review)
- **3 default fields (Tên/Mục tiêu/Đơn vị); id/emoji/màu in Advanced.** **How to change:** the field grouping in page.tsx.
- **id auto-slugs from name (slugifyVi), idManual stops it on override.** **How to change:** slugifyVi / the idManual flag.
- **BE takes the FE id verbatim** (no re-slug) → slugifyVi is FE-consistency only. **How to change:** n/a (the BE contract).

## Notes
- Cairn #110 TRACING-UX T2 — **COMPLETES the TRACING-UX FE** (#109-FE ab42da5 picker + this #110 lean-form). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). Layered on the committed #109-FE (one-file serialization on page.tsx — #109-FE committed before #110 started, no tangle). FE-only stage (the #111 `remindChannel` in the working tree is a separate BE lane — kept OUT). The auto-slug means the user types a name + gets a valid id free; the BE-verbatim-id confirm (create uses inp.id) means no FE/BE slug-mismatch risk. After #110 commits → page.tsx SETTLES → team-lead runs ONE combined Chrome pass (#109 picker + #110 form-gọn) on the settled code. frontend-w3-2 then idle-correct (next FE = #114, dep-blocked on #112+#113 — a real dep-wait, not NEVER-FREE).
