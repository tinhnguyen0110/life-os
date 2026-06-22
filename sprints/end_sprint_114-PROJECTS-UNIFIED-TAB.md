# end_sprint_114-PROJECTS-UNIFIED-TAB — FE unified Projects tab (gộp 3→2 + source badge + hide-UI + dev-stat) (Cairn #114, PROJECTS-UNIFY T3)

> Result. The FE now reflects the unified Projects model: sidebar gộp 3→2 (/projects + /graveyard → ONE "Dự án"; /dev-activity stays separate), a /projects sub-tab [Đang chạy | Nghĩa địa], source badges, hide/unhide UI, and a per-row dev-stat strip (from #112, found:false honest). This is the user's ORIGINAL feature that kicked off PROJECTS-UNIFY. Commit `<hash>` `feat(sprint-114-projects-unified-tab)`. Status: ✅ verified (frontend-w3-2 built + Chrome live; architect 4-step + tsc + vitest 1033/0). Cairn #114 PROJECTS-UNIFY T3 — fe-only, CLOSES on this commit → **PROJECTS-UNIFY fully done** (#112/#113/#114/#115). user-CHỐT.

## What shipped (FE — 12 mod + 2 new)
| File | Change |
|---|---|
| `lib/nav.ts` | gộp 3→2: removed the `/graveyard` nav entry (now an in-page sub-tab); "Dự án" section = `/projects` (label "Danh sách", NOT "Dự án" — avoids the getByText label-uniqueness collision) + `/dev-activity` (STAYS separate, distinct git-stats screen, user-CHỐT nav-IA-A). |
| `app/projects/page.tsx` | sub-tab [Đang chạy \| Nghĩa địa] (`role=tablist`); `?tab=graveyard` deep-link via useSearchParams; running→S2 table, graveyard→`<GraveyardView>` in-page. source badge per row (SOURCE_META). hide/unhide (toggle on p.hidden, refetch via nonce). includeHidden toggle → getProjects(includeHidden). dev-stat strip per row (`<ProjectDevStat>`). |
| `app/graveyard/page.tsx` | → REDIRECT (`router.replace("/projects?tab=graveyard")`) + honest interim message. Old URL/bookmarks keep working. |
| `components/GraveyardView.tsx` (NEW) | the S4 graveyard UI extracted (pattern panel/toggle/grave cards/restore/lessons/export — all preserved) so it renders in-page under the sub-tab. |
| `components/ProjectDevStat.tsx` (NEW) | dev-stat strip: GET /projects/{id}/dev-activity. 🔴 honest-mirror — `found:false` → "chưa track git" (+ reason in title), NEVER a fake 0; `found:true` → real commits (commits:0 on a tracked repo is a real 0, distinct from untracked). |
| `lib/types.ts` | mirror the FROZEN #113 schema: `ProjectStatus +source: ProjectSource +hidden: boolean`; `export type ProjectSource`; + `ProjectDevActivity` interface (found honest). |
| `lib/api.ts` | `getProjects(includeHidden)`, `hideProject`/`unhideProject`, `getProjectDevActivity`. |
| `lib/tokens.css` | source-badge + sub-tab + dev-stat tokens (ported, not redesigned). |
| tests (+11, 1022→1033) | nav 3→2, sub-tab/?tab/redirect, source badge, hide/unhide, dev-stat found:false, types-mirror (the frozen schema). |

## Design (LOCKED — gộp 3→2, sub-tab+redirect, render-only, honest dev-stat)
- **gộp 3→2:** /projects+/graveyard merge into one nav entry (graveyard = sub-tab); /dev-activity stays separate (NOT merged — user-CHỐT). The sidebar now shows 2 "Dự án" entries, not 3.
- **sub-tab + URL + redirect:** `?tab=graveyard` deep-links; /graveyard → `router.replace` redirect (old URL preserved). No back-button trap (replace, not push).
- **render-only (raw-data-first):** source/hidden/health/dev-stat ALL from the BE — the FE computes nothing derived. dev-stat is the #112 endpoint, honest found:false mirrored.
- **hide ≠ abandon (soft UI-hide):** in-page hide/unhide (NOT window.confirm); a hidden row leaves the default list, returns under the includeHidden toggle. Distinct from the graveyard (abandoned).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** nav 3→2 (graveyard entry removed, /dev-activity kept, label "Danh sách" avoids the test collision); types mirror the frozen schema EXACTLY (source/hidden/ProjectSource match BE); sub-tab useSearchParams + setTab router.push + /graveyard router.replace redirect; hide/unhide toggles on p.hidden + refetch; ProjectDevStat found:false → honest "chưa track git" (NOT fake 0). FE-only stage (BE tree clean — no cross-lane). ✅
- **architect tsc + vitest:** tsc clean (exit 0); vitest **89 files / 1033 passed / 0 failed** (independent re-run; was 1022 → +11; tail clean, no unhandled). ✅
- **frontend-w3-2 Chrome :3010 (the user payoff — sidebar gộp):** sidebar 2-not-3 "Dự án" entries; sub-tab Đang chạy↔Nghĩa địa; ?tab=graveyard deep-link; /graveyard redirects; source badges (registered/auto); dev-stat real git (cairn "558 commit · 7 giờ", claude-code-agents "87 commit · 2 tháng"); hide termpilot 14→13 → includeHidden toggle shows it → unhide → baseline; dark-mode; console clean; baseline restored. ✅
- **🔴 mock-diff CLEAN (recurring scope-drop risk):** zero S2/S4 feature dropped — S2 (health tabs/KPI/table/badge/progress/new) + S4 (pattern panel/toggle/grave cards/restore/lessons/export) ALL preserved (team-lead + my check). ✅

## 3 Gates
- **Gate 2 (Function):** the +11 tests (nav/sub-tab/redirect/badge/hide-unhide/dev-stat-found:false/types-mirror) + tsc + vitest 1033/0 + Chrome live + mock-diff clean. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step + tsc/vitest; staged EXACTLY the 14 FE files (NO backend/template/data — BE tree clean post-#115, no cross-lane); commit format. ✅

## Assumptions (user-review)
- **gộp 3→2: graveyard = sub-tab, /dev-activity stays separate** (user-CHỐT nav-IA-A). **How to change:** the nav.ts entries + the sub-tab.
- **hide = soft UI-hide, ≠ abandon.** **How to change:** the hide/unhide handlers + the includeHidden toggle.
- **dev-stat found:false → "chưa track git"** (honest, not fake 0). **How to change:** ProjectDevStat (mirrors the BE honest-mirror).

## Notes
- Cairn #114 PROJECTS-UNIFY T3 — **the user's ORIGINAL feature** (the sidebar redesign that kicked off the whole PROJECTS-UNIFY arc). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). 🔴 **Parallel-lane staging (the clean half):** #114 (FE) built in parallel with #115 (BE) in the SAME tree; #115 committed BE-only last (leaving these 12 FE files dirty), and now #114 commits FE-only (BE tree clean → no cross-lane risk). The disjoint-files + serial-commit pattern held across both lanes with zero tangle. **CLOSES #114 → PROJECTS-UNIFY fully done** (#112 slug-join `3ede9ec` + #113 auto-discover `2b693ca` + #115 core/git `2c6caf8` + #114 FE here). The mock-diff-clean check (the recurring scope-drop net) confirmed no S2/S4 feature lost in the merge. After push → team-lead Chrome-verifies the sidebar gộp (the user payoff).
